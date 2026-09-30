"""Independent synthetic notation review state. No evaluation labels or model tools."""
import hashlib
import json
import math
import secrets
import sqlite3
import threading
import time
import uuid
from pathlib import Path

from .extraction import document_envelope, extract_document
from .comparison import compare_documents, fingerprint, pair_envelope

ROLES = ("engineer", "reviewer")


def _id():
    return uuid.uuid4().hex


def _text(value, limit, name):
    if not isinstance(value, str) or not value or len(value) > limit:
        raise ValueError("invalid_" + name)
    return value


def _now():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


class StaleComparisonError(ValueError):
    pass


class Store:
    def __init__(self, corpus_path, db_path):
        self.corpus_path = Path(corpus_path)
        self._lock = threading.RLock()
        self._sessions = {}
        self._db = sqlite3.connect(str(db_path), check_same_thread=False, timeout=10)
        self._db.execute("PRAGMA journal_mode=WAL")
        self._db.executescript("""
            CREATE TABLE IF NOT EXISTS comparisons (
                id TEXT PRIMARY KEY, site TEXT NOT NULL, part_number TEXT NOT NULL,
                payload TEXT NOT NULL, validation_fingerprint TEXT NOT NULL,
                invalidated INTEGER NOT NULL DEFAULT 0);
            CREATE TABLE IF NOT EXISTS reviews (
                comparison_id TEXT PRIMARY KEY, payload TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS audit (
                sequence INTEGER PRIMARY KEY AUTOINCREMENT, site TEXT NOT NULL,
                part_number TEXT NOT NULL, comparison_id TEXT NOT NULL, payload TEXT NOT NULL);
        """)
        self._db.commit()
        self._refresh()

    def close(self):
        with self._lock:
            self._db.close()

    def _refresh(self):
        data = json.loads(self.corpus_path.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or not isinstance(data.get("parts"), list) or not isinstance(data.get("documents"), list):
            raise ValueError("invalid_corpus")
        parts = {}
        for part in data["parts"]:
            if not isinstance(part, dict):
                raise ValueError("invalid_part")
            _text(part.get("id"), 200, "part")
            _text(part.get("revision"), 200, "part_revision")
            if part["id"] in parts:
                raise ValueError("duplicate_part")
            parts[part["id"]] = part
        documents = {}
        latest = {}
        invalid = set()
        for document in data["documents"]:
            if not isinstance(document, dict):
                raise ValueError("invalid_document")
            for field in ("id", "part_number", "part_revision", "document_role", "approval_state", "site"):
                _text(document.get(field), 200, field)
            revision = document.get("document_revision")
            roles = document.get("roles")
            if not isinstance(revision, int) or isinstance(revision, bool) or revision < 1:
                raise ValueError("invalid_document_revision")
            if not isinstance(roles, list) or not roles or any(role not in ROLES for role in roles):
                raise ValueError("invalid_document_acl")
            if document["site"] not in ("A", "B") or document["id"] in documents:
                raise ValueError("invalid_document_identity")
            documents[document["id"]] = document
            try:
                document_envelope(document)
            except ValueError:
                invalid.add(document["id"])
            key = self._source_key(document)
            previous = latest.get(key)
            if previous is not None and previous["document_revision"] == revision:
                raise ValueError("ambiguous_document_revision")
            if previous is None or revision > previous["document_revision"]:
                latest[key] = document
        self._parts, self._documents, self._latest, self._invalid = parts, documents, latest, invalid

    @staticmethod
    def _source_key(document):
        return (document["part_number"], document["part_revision"], document["document_role"])

    def profiles(self):
        return [{"id": site + "-" + role, "site": site, "role": role,
                 "label": site + " / " + role + " (synthetic demo login)"}
                for site in ("A", "B") for role in ROLES]

    def session(self, profile):
        value = next((p for p in self.profiles() if p["id"] == profile), None)
        if value is None:
            raise ValueError("unknown_demo_profile")
        principal = {key: value[key] for key in ("id", "site", "role")}
        token = secrets.token_urlsafe(32)
        with self._lock:
            self._sessions[token] = principal
        return {"token": token, "principal": dict(principal)}

    def principal(self, token):
        with self._lock:
            value = self._sessions.get(token)
            if value is None:
                raise PermissionError("authentication_required")
            return dict(value)

    @staticmethod
    def _check_principal(principal):
        if not isinstance(principal, dict) or principal.get("site") not in ("A", "B") or principal.get("role") not in ROLES:
            raise PermissionError("invalid_principal")
        if principal.get("id") != principal["site"] + "-" + principal["role"]:
            raise PermissionError("invalid_principal")

    @staticmethod
    def _role_access(principal, document):
        return document["site"] == principal["site"] and principal["role"] in document["roles"]

    def _current(self, document):
        part = self._parts.get(document["part_number"])
        return (part is not None and document["part_revision"] == part["revision"]
                and self._latest.get(self._source_key(document), {}).get("id") == document["id"])

    def _part(self, principal, part_id):
        self._check_principal(principal)
        part = self._parts.get(part_id)
        visible = [d for d in self._latest.values()
                   if d["part_number"] == part_id and self._current(d) and self._role_access(principal, d)]
        if part is None or not visible:
            raise KeyError("part_not_found")
        return dict(part, site=principal["site"])

    def parts(self, principal):
        with self._lock:
            self._refresh()
            self._check_principal(principal)
            result = []
            for part_id in self._parts:
                try:
                    result.append(self._part(principal, part_id))
                except KeyError:
                    continue
            return result

    def part(self, principal, part_id):
        with self._lock:
            self._refresh()
            part = self._part(principal, part_id)
            documents = [dict(d) for d in self._latest.values()
                         if d["part_number"] == part_id and self._current(d)
                         and self._role_access(principal, d) and d["id"] not in self._invalid]
            documents.sort(key=lambda d: (d["document_role"], d["id"]))
            return {"part": part, "documents": documents}

    def _document(self, principal, doc_id):
        self._check_principal(principal)
        document = self._documents.get(doc_id)
        if document is None or not self._role_access(principal, document) or not self._current(document):
            raise KeyError("document_not_found")
        if doc_id in self._invalid:
            raise ValueError("source_validation_failed")
        document_envelope(document)
        return dict(document)

    def document(self, principal, doc_id):
        with self._lock:
            self._refresh()
            return self._document(principal, doc_id)

    @staticmethod
    def _validation_fingerprint(reference, candidate, target_part):
        value = {"comparison": fingerprint(reference, candidate, target_part),
                 "source_roles": [sorted(set(reference["roles"])), sorted(set(candidate["roles"]))]}
        return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()

    def _audit_event(self, principal, part_number, comparison_id, action, **fields):
        event = {"id": _id(), "timestamp": _now(), "part_number": part_number,
                 "comparison_id": comparison_id, "actor_id": principal["id"], "action": action, **fields}
        self._db.execute("INSERT INTO audit(site,part_number,comparison_id,payload) VALUES(?,?,?,?)",
                         (principal["site"], part_number, comparison_id, json.dumps(event, ensure_ascii=False)))

    def _invalidate(self, principal, row):
        if not row["invalidated"]:
            changed = self._db.execute("UPDATE comparisons SET invalidated=1 WHERE id=? AND invalidated=0", (row["id"],))
            if changed.rowcount:
                self._audit_event(principal, row["part_number"], row["id"], "comparison_invalidated",
                                  reason="source_identity_or_policy_changed")
            row["invalidated"] = True

    def _comparison_row(self, principal, comparison_id):
        self._check_principal(principal)
        selected = self._db.execute(
            "SELECT id,site,part_number,payload,validation_fingerprint,invalidated FROM comparisons WHERE id=?",
            (comparison_id,)).fetchone()
        if selected is None or selected[1] != principal["site"]:
            raise KeyError("comparison_not_found")
        row = dict(zip(("id", "site", "part_number", "payload", "validation_fingerprint", "invalidated"), selected))
        payload = json.loads(row["payload"])
        sources = []
        stale = bool(row["invalidated"])
        authorized = True
        for envelope in (payload["reference"], payload["candidate"]):
            current = self._documents.get(envelope["id"])
            if current is None:
                stale = True
                continue
            if not self._role_access(principal, current):
                authorized = False
            latest = self._latest.get(self._source_key(current))
            if latest is not None and not self._role_access(principal, latest):
                authorized = False
            if current["id"] in self._invalid or not self._current(current):
                stale = True
            sources.append(current)
        part = self._parts.get(row["part_number"])
        if part is None or len(sources) != 2 or any(d["part_revision"] != part["revision"] for d in sources):
            stale = True
        if not stale:
            try:
                expected = self._validation_fingerprint(sources[0], sources[1], row["part_number"])
                stale = expected != row["validation_fingerprint"]
            except ValueError:
                stale = True
        # Only source identity/policy changes invalidate shared state.
        # A caller lacking access to unchanged sources merely gets a denial.
        if stale:
            self._invalidate(principal, row)
        if not authorized:
            raise KeyError("comparison_not_found")
        return row, payload

    @staticmethod
    def _invalidated_shell(row):
        return {"id": row["id"], "target_part": row["part_number"], "status": "invalidated",
                "review_state": "invalidated", "stale": True, "review": None,
                "extractions": [], "checks": [], "overall": "needs_review",
                "required_coverage": {"observed": 0, "required": 3, "complete": False},
                "invalidation_reason": "source_identity_or_policy_changed"}

    def compare(self, principal, part_id, reference_id, candidate_id, mode="baseline"):
        if mode not in ("baseline", "model"):
            raise ValueError("invalid_mode")
        started = time.perf_counter()
        with self._lock:
            self._refresh()
            self._part(principal, part_id)
            reference = self._document(principal, reference_id)
            candidate = self._document(principal, candidate_id)
            if reference["part_revision"] != self._parts[part_id]["revision"]:
                raise ValueError("different_part_revision")
            pair_envelope(reference, candidate, part_id)
            observed = [extract_document(reference), extract_document(candidate)]
            selected_fingerprint = self._validation_fingerprint(reference, candidate, part_id)
        extractions = observed
        model_state = "not_requested"
        metrics = {"synthetic": True, "requested_mode": mode, "scope": "notation_review_only"}
        if mode == "model":
            model_state = "failed"
            try:
                from .llm import extract_document_with_model
                # Independent sequential calls: neither sees the other document.
                proposed = [extract_document_with_model(reference), extract_document_with_model(candidate)]
                compare_documents(reference, candidate, part_id, extractions=proposed)
                if any(item.get("model_state") != "source_verified" for item in proposed):
                    raise ValueError("model_extraction_not_verified")
                extractions = proposed
                model_state = "source_verified"
                allowed_metrics = {"latency_ms", "trace_id", "thinking_chars", "model", "done_reason",
                                   "eval_count", "prompt_eval_count", "total_duration", "load_duration",
                                   "prompt_eval_duration", "eval_duration", "requested_think",
                                   "thinking_off_verified", "context_limit", "concurrency", "mock"}
                model_calls = []
                for document, extraction in zip((reference, candidate), proposed):
                    source_metrics = extraction.get("metrics", {})
                    call = {"document_id": document["id"]}
                    if isinstance(source_metrics, dict):
                        call.update({key: value for key, value in source_metrics.items()
                                     if key in allowed_metrics and isinstance(value, (str, int, float, bool))
                                     and len(str(value)) <= 500
                                     and (not isinstance(value, float) or math.isfinite(value))})
                    model_calls.append(call)
                metrics["model_calls"] = model_calls
                metrics["model_call_count"] = len(model_calls)
                def total(field):
                    return sum(call.get(field, 0) for call in model_calls
                               if isinstance(call.get(field, 0), (int, float))
                               and not isinstance(call.get(field, 0), bool))
                metrics["model_latency_ms"] = round(total("latency_ms"), 3)
                metrics["generated_tokens"] = total("eval_count")
                metrics["prompt_tokens"] = total("prompt_eval_count")
                metrics["model_total_duration_ns"] = total("total_duration")
            except (TimeoutError, RuntimeError, OSError, ValueError, ImportError, TypeError, KeyError):
                extractions = observed
                metrics["model_error_kind"] = "model_extraction_failed"
        result = compare_documents(reference, candidate, part_id, extractions=extractions)
        result.update({"id": _id(), "site": principal["site"], "mode": mode, "model_state": model_state,
                       "status": "pending_manual_review" if model_state == "failed" else "pending_review",
                       "review_state": "unreviewed", "review": None, "audit": [],
                       "stale": False, "metrics": metrics})
        result["metrics"]["total_ms"] = round((time.perf_counter() - started) * 1000, 3)
        with self._lock:
            self._refresh()
            # Recheck identities and ACL after any slow inference, before publishing.
            current_ref = self._document(principal, reference_id)
            current_candidate = self._document(principal, candidate_id)
            if self._validation_fingerprint(current_ref, current_candidate, part_id) != selected_fingerprint:
                raise StaleComparisonError("source_changed_during_comparison")
            with self._db:
                self._db.execute("INSERT INTO comparisons(id,site,part_number,payload,validation_fingerprint) VALUES(?,?,?,?,?)",
                                 (result["id"], principal["site"], part_id, json.dumps(result, ensure_ascii=False),
                                  selected_fingerprint))
                self._audit_event(principal, part_id, result["id"], "comparison_created", mode=mode,
                                  model_state=model_state, overall=result["overall"])
            return self.comparison(principal, result["id"])

    def comparison(self, principal, comparison_id):
        with self._lock:
            self._refresh()
            denied = None
            with self._db:
                try:
                    row, result = self._comparison_row(principal, comparison_id)
                except KeyError as error:
                    denied = error
                if denied is None:
                    if row["invalidated"]:
                        return self._invalidated_shell(row)
                    review = self._db.execute("SELECT payload FROM reviews WHERE comparison_id=?", (comparison_id,)).fetchone()
                    if review:
                        result["review"] = json.loads(review[0])
                        result["review_state"] = result["review"]["decision"]
                        result["status"] = "review_recorded"
                    result["audit"] = self._events(principal, row["part_number"], comparison_id)
            if denied is not None:
                raise denied
            return result

    def review(self, principal, comparison_id, decision, comment="", manual_confirmation=False):
        self._check_principal(principal)
        if principal["role"] != "reviewer":
            raise PermissionError("reviewer_required")
        if decision not in ("reviewed", "needs_followup"):
            raise ValueError("invalid_decision")
        if not isinstance(comment, str) or len(comment) > 2000:
            raise ValueError("invalid_comment")
        if not isinstance(manual_confirmation, bool):
            raise ValueError("invalid_manual_confirmation")
        with self._lock:
            self._refresh()
            # Persist invalidation even when the later review transaction refuses it.
            denied = None
            with self._db:
                try:
                    row, result = self._comparison_row(principal, comparison_id)
                except KeyError as error:
                    denied = error
            if denied is not None:
                raise denied
            if row["invalidated"]:
                raise StaleComparisonError("comparison_invalidated")
            with self._db:
                self._db.execute("BEGIN IMMEDIATE")
                # Another backend instance may have invalidated it since the first read.
                row, result = self._comparison_row(principal, comparison_id)
                if row["invalidated"]:
                    raise StaleComparisonError("comparison_invalidated")
                existing = self._db.execute("SELECT payload FROM reviews WHERE comparison_id=?", (comparison_id,)).fetchone()
                if existing:
                    return {"review": json.loads(existing[0]), "duplicate": True}
                if result["model_state"] == "failed" and not manual_confirmation:
                    raise ValueError("manual_confirmation_required")
                review = {"id": _id(), "comparison_id": comparison_id, "decision": decision,
                          "comment": comment, "manual_confirmation": manual_confirmation,
                          "reviewer_id": principal["id"], "timestamp": _now(),
                          "scope": "acknowledgement_or_followup_not_design_approval"}
                self._db.execute("INSERT INTO reviews VALUES(?,?)", (comparison_id, json.dumps(review, ensure_ascii=False)))
                self._audit_event(principal, row["part_number"], comparison_id, "review_recorded",
                                  decision=decision, comment=comment, manual_confirmation=manual_confirmation,
                                  reviewer_id=principal["id"])
                return {"review": review, "duplicate": False}

    def _events(self, principal, part_id, comparison_id=None):
        query = "SELECT comparison_id,payload FROM audit WHERE site=? AND part_number=?"
        params = [principal["site"], part_id]
        if comparison_id is not None:
            query += " AND comparison_id=?"
            params.append(comparison_id)
        query += " ORDER BY sequence"
        events = []
        for selected_id, payload in self._db.execute(query, params).fetchall():
            try:
                row, _ = self._comparison_row(principal, selected_id)
            except KeyError:
                continue
            # Missing source identity cannot establish current ACL for history.
            original = json.loads(row["payload"])
            if any(envelope["id"] not in self._documents for envelope in (original["reference"], original["candidate"])):
                continue
            event = json.loads(payload)
            event["historical"] = bool(row["invalidated"])
            if row["invalidated"]:
                # Historical comments may quote obsolete source content.
                event.pop("comment", None)
            events.append(event)
        return events

    def audit(self, principal, part_number):
        with self._lock:
            self._refresh()
            self._part(principal, part_number)
            with self._db:
                # Validate before fetching so the first invalidation event is included.
                comparisons = self._db.execute("SELECT id FROM comparisons WHERE site=? AND part_number=?",
                                               (principal["site"], part_number)).fetchall()
                for (comparison_id,) in comparisons:
                    try:
                        self._comparison_row(principal, comparison_id)
                    except KeyError:
                        continue
                return self._events(principal, part_number)
