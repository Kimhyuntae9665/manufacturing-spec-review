"""Bounded loopback API checks with temporary synthetic sources and mocked model."""
import concurrent.futures
import http.client
import json
import threading
import unittest

from test_core import Fixture
from spec_review.server import MAX_BODY, make_server


class HTTPTests(Fixture):
    def setUp(self):
        super().setUp()
        self.static = self.root / "static"
        self.static.mkdir()
        for name in ("index.html", "app.js", "styles.css"):
            (self.static / name).write_text("synthetic " + name)
        self.server = make_server(self.store, port=0, static_dir=self.static)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.port = self.server.server_port
        self.tokens = {profile: self.store.session(profile)["token"]
                       for profile in ("A-engineer", "A-reviewer", "B-reviewer")}

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        super().tearDown()

    def request(self, method, path, body=None, profile="A-engineer", headers=None, raw=None):
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        request_headers = {}
        if profile:
            request_headers["Authorization"] = "Bearer " + self.tokens[profile]
        if body is not None:
            raw = json.dumps(body)
            request_headers["Content-Type"] = "application/json"
        request_headers.update(headers or {})
        connection.request(method, path, body=raw, headers=request_headers)
        response = connection.getresponse()
        data = response.read()
        status, response_headers = response.status, dict(response.getheaders())
        connection.close()
        if response_headers.get("Content-Type", "").startswith("application/json"):
            data = json.loads(data)
        return status, data, response_headers

    def create(self, mode="baseline"):
        return self.request("POST", "/api/parts/PA/compare",
                            {"reference_id": "PA-ref", "candidate_id": "PA-candidate", "mode": mode})

    def test_loopback_health_demo_session_and_static_whitelist(self):
        self.assertEqual(self.server.server_address[0], "127.0.0.1")
        status, health, headers = self.request("GET", "/api/health", profile=None)
        self.assertEqual(status, 200)
        self.assertTrue(health["synthetic"])
        self.assertNotIn("Access-Control-Allow-Origin", headers)
        self.assertIn("frame-ancestors 'none'", headers["Content-Security-Policy"])
        status, session, _ = self.request("POST", "/api/session", {"profile": "A-engineer"}, profile=None)
        self.assertEqual(status, 200)
        self.assertEqual(session["principal"]["role"], "engineer")
        for path in ("/", "/index.html", "/app.js", "/styles.css"):
            self.assertEqual(self.request("GET", path, profile=None)[0], 200)
        for path in ("/data/documents.json", "/evaluations/gold_v1.json", "/../docs/contract.md",
                     "/%2e%2e/data/documents.json", "/spec_review/core.py"):
            self.assertEqual(self.request("GET", path, profile=None)[0], 404)

    def test_all_http_acl_surfaces_and_no_identity_header_spoof(self):
        status, result, _ = self.create()
        id = result["comparison"]["id"]
        self.assertEqual(self.request("GET", "/api/parts", profile=None,
                                      headers={"X-Site": "A", "X-Role": "reviewer"})[0], 403)
        for path in ("/api/parts/PB", "/api/documents/PB-ref", "/api/audit?part_number=PB"):
            self.assertEqual(self.request("GET", path)[0], 404)
        self.assertEqual(self.request("GET", "/api/comparisons/" + id, profile="B-reviewer")[0], 404)
        self.assertEqual(self.request("POST", "/api/comparisons/" + id + "/review",
                                      {"decision": "reviewed"}, profile="B-reviewer")[0], 404)
        self.assertEqual(self.request("POST", "/api/comparisons/" + id + "/review",
                                      {"decision": "reviewed"})[0], 403)
        status, parts, _ = self.request("GET", "/api/parts", headers={"X-Site": "B"})
        self.assertEqual({p["site"] for p in parts["parts"]}, {"A"})

    def test_host_origin_and_bounded_json(self):
        self.assertEqual(self.request("GET", "/api/health", headers={"Host": "evil.example"})[0], 403)
        self.assertEqual(self.request("GET", "/api/parts", headers={"Origin": "https://evil.example"})[0], 403)
        self.assertEqual(self.request("POST", "/api/session", raw="{}", profile=None)[0], 400)
        for raw in ("[]", "{"):
            self.assertEqual(self.request("POST", "/api/session", raw=raw, profile=None,
                                          headers={"Content-Type": "application/json"})[0], 400)
        self.assertEqual(self.request("POST", "/api/session", raw="x" * (MAX_BODY + 1), profile=None,
                                      headers={"Content-Type": "application/json"})[0], 413)
        self.assertEqual(self.request("GET", "/api/audit?part_number=PA&part_number=PB")[0], 400)

    def test_http_timeout_manual_confirmation_and_safe_error(self):
        context, call = self.model_patch(error=TimeoutError("private runtime error"))
        with context:
            status, body, _ = self.create("model")
        self.assertEqual(status, 200)
        self.assertEqual(body["comparison"]["model_state"], "failed")
        self.assertNotIn("private runtime", json.dumps(body))
        id = body["comparison"]["id"]
        self.assertEqual(self.request("POST", "/api/comparisons/" + id + "/review",
                                      {"decision": "reviewed"}, profile="A-reviewer")[0], 400)
        status, review, _ = self.request("POST", "/api/comparisons/" + id + "/review",
                                         {"decision": "reviewed", "manual_confirmation": True}, profile="A-reviewer")
        self.assertEqual(status, 200)
        self.assertFalse(review["duplicate"])

    def test_http_stale_comparison_sanitized_and_review_conflict(self):
        status, body, _ = self.create()
        id = body["comparison"]["id"]
        self.request("POST", "/api/comparisons/" + id + "/review",
                     {"decision": "reviewed", "comment": "old"}, profile="A-reviewer")
        self.edit_content("PA-candidate", self.source("PA-candidate")["content"].replace("AL5052", "AL6061"))
        status, body, _ = self.request("GET", "/api/comparisons/" + id)
        self.assertEqual(status, 200)
        self.assertEqual(body["comparison"]["status"], "invalidated")
        self.assertEqual(body["comparison"]["extractions"], [])
        self.assertIsNone(body["comparison"]["review"])
        self.assertEqual(self.request("POST", "/api/comparisons/" + id + "/review",
                                      {"decision": "reviewed"}, profile="A-reviewer")[0], 409)

    def test_http_source_hash_corruption_and_acl_revocation(self):
        _, body, _ = self.create()
        id = body["comparison"]["id"]
        self.source("PA-ref")["roles"] = ["reviewer"]
        self.save()
        self.assertEqual(self.request("GET", "/api/documents/PA-ref")[0], 404)
        self.assertEqual(self.request("GET", "/api/comparisons/" + id)[0], 404)
        status, audit, _ = self.request("GET", "/api/audit?part_number=PA")
        self.assertEqual(audit["events"], [])
        self.source("PA-ref")["content"] += "corrupted secret"
        self.save()
        self.assertEqual(self.request("GET", "/api/documents/PA-ref", profile="A-reviewer")[0], 400)
        status, body, _ = self.request("GET", "/api/comparisons/" + id, profile="A-reviewer")
        self.assertEqual(body["comparison"]["status"], "invalidated")
        self.assertNotIn("corrupted secret", json.dumps(body))

    def test_engineer_read_and_audit_do_not_invalidate_reviewer_only_comparison(self):
        self.source("PA-ref")["roles"] = ["reviewer"]
        self.save()
        status, body, _ = self.request("POST", "/api/parts/PA/compare",
            {"reference_id": "PA-ref", "candidate_id": "PA-candidate", "mode": "baseline"}, profile="A-reviewer")
        self.assertEqual(status, 200)
        comparison_id = body["comparison"]["id"]
        self.assertEqual(self.request("GET", "/api/comparisons/" + comparison_id)[0], 404)
        status, audit, _ = self.request("GET", "/api/audit?part_number=PA")
        self.assertEqual(status, 200)
        self.assertEqual(audit["events"], [])
        status, body, _ = self.request("GET", "/api/comparisons/" + comparison_id, profile="A-reviewer")
        self.assertEqual(status, 200)
        self.assertFalse(body["comparison"]["stale"])
        status, review, _ = self.request("POST", "/api/comparisons/" + comparison_id + "/review",
            {"decision": "reviewed"}, profile="A-reviewer")
        self.assertEqual(status, 200)
        self.assertFalse(review["duplicate"])
        self.assertEqual(self.request("GET", "/api/comparisons/" + comparison_id)[0], 404)
        self.request("GET", "/api/audit?part_number=PA")
        status, body, _ = self.request("GET", "/api/comparisons/" + comparison_id, profile="A-reviewer")
        self.assertEqual(body["comparison"]["review_state"], "reviewed")
        self.assertFalse(body["comparison"]["stale"])

    def test_concurrent_http_reviews_only_one_decision_and_audit(self):
        _, body, _ = self.create()
        id = body["comparison"]["id"]
        def submit(index):
            return self.request("POST", "/api/comparisons/" + id + "/review",
                                {"decision": "reviewed", "comment": "request " + str(index)}, profile="A-reviewer")
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
            responses = list(executor.map(submit, range(16)))
        self.assertEqual({r[0] for r in responses}, {200})
        self.assertEqual(sum(not r[1]["duplicate"] for r in responses), 1)
        self.assertEqual(len({r[1]["review"]["id"] for r in responses}), 1)
        _, audit, _ = self.request("GET", "/api/audit?part_number=PA", profile="A-reviewer")
        self.assertEqual(sum(e["action"] == "review_recorded" for e in audit["events"]), 1)


if __name__ == "__main__":
    unittest.main()
