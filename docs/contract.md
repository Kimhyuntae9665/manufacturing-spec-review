# Manufacturing annotation review contract v1
This is a synthetic document-notation comparison workflow for a manufacturing design/quality reviewer. It is not engineering equivalence, design approval, manufacturing suitability or CAD geometry validation.

## Frozen inputs and evaluator isolation
data/documents.json: 3 parts, 6 text documents. evaluations/gold_v1.json: 16 independent synthetic outcomes fixed before any model extraction; evaluations/freeze_manifest.json stores hashes and zero pre-freeze requests. Only evaluators read evaluations/. The backend and model never read gold. Parts retain equipment/line associations to explain business purpose.
Each document carries id, part_number, part_revision, document_revision, document_role (reference_spec/candidate_drawing), approval_state (approved/draft), site, roles, title, content, source_hash, extraction_state, review_state. source_hash is verified/computed by server, never by model. part_revision and document_revision are different dimensions.

## Comparison policy
The selected approved reference_spec and candidate_drawing must belong to the target part and same part_revision. Candidate draft is valid for review. Do not globally discard draft documents or compare revision numbers between different document roles. Choose the latest document_revision separately within part+part_revision+role; no inaccessible-current to old fallback. Reference approval and candidate draft are retained in the displayed provenance envelope. Invalid identity/revision/role/approval blocks comparison; no automatic repair.
The checked fields are material_grade, finish_code, nominal coating_thickness with an explicit mm/µm unit. Each document is extracted independently. Never give reference values to candidate extraction.

## Extraction and quotation
Output fields retain whole original field/cell, original line number, exact full-line quote, start/end Unicode character offsets, raw value and unit, extraction state. Recompute source_hash and recover line/span from server original text. Reject fabricated quotes, partial substring values, duplicated/ambiguous quote matches, and conflicts.
SUS304 is not a valid extraction from SUS304L or SUS304 or SUS316. Qualifiers, negation, alternatives, tolerance, range, lower/upper bounds and GD&T are needs_review, not nominal values. Missing/null never means zero or not-applicable. Empty/partial extraction cannot create all-match.
Model proposes a typed per-document extraction. Only validated source-supported proposals are model_verified; untrusted text never creates tools or writes. Identifiers/hash/approval are server envelope.
Thickness conversion uses Decimal from full raw numeral. Only declared nominal mm/µm conversion (1 mm=1000 µm), no floating equality. >=, ±, ranges, 이상/이하, 以上/以下, unsupported units remain needs_review.

## Outputs
Extraction: document_id, provenance, fields {material_grade,finish_code,coating_thickness}; each field {raw_value,unit,state,quote,line,span_start,span_end}; model metadata if requested.
Comparison: id, target_part, reference, candidate, extractions, checks[{field,state,reference_value,candidate_value,explanation}], overall, required_coverage, model_state, review_state, fingerprint, audit, review.
States: same_notation / same_declared_nominal / notation_difference / information_missing / unsupported_unit / needs_review. overall annotations_match only when all three fields are present, unambiguous, supported nominal and match. All other cases needs_review. Model failure preserves deterministic original/field inspection for explicit human manual review; never labels a model failure model_verified.

## API and authorization
Opaque server-allowlisted synthetic profiles A-engineer/A-reviewer/B-engineer/B-reviewer. Demo login, not enterprise SSO.
GET /api/health, /api/profiles public; POST /api/session {profile}.
Authenticated GET /api/parts -> {parts}; GET /api/parts/{id} -> {part,documents}; GET /api/documents/{id} -> {document}.
POST /api/parts/{id}/compare {reference_id,candidate_id,mode:baseline|model} -> {comparison}. Validation/auth precede any inference.
GET /api/comparisons/{id} -> {comparison}; GET /api/audit?part_number=...
POST /api/comparisons/{id}/review {decision:reviewed|needs_followup,comment,manual_confirmation:bool}. reviewer only; review records acknowledgement/follow-up, does not approve the candidate design/document. If model failed, manual_confirmation must be true. Unique decision per comparison, duplicate is idempotent.
All lists/details/comparisons/citations/reviews/audit recheck site-role and source identities. On source hash/revision/role/approval change, previous comparison and review are invalidated; refuse another review on stale comparison. Retain old audit history. Document content API is read-only; no upload/control/shell endpoints.
SQLite safe transactions and bounded input; loopback19081; exact static whitelist and Host/Origin checks, no external CDN, no raw tokens/logged prompts.
UI: part list, reference vs candidate documents, per-field comparisons, original source line highlights, pending/manual/review state and audit. Not a chat-only interface.

## Inference/runtime
Existing localhost Ollama qwen3:4b only, no model download or update; max 4096 context/256-512 bounded output, think:false requested but installed template may not disable reasoning. Per-document schema extraction, two serial document requests. Use the same explicit AX_LAB_INFERENCE_LOCK or documented per-user cache default as project01 after portable-lock patch. One GPU request globally at a time, busy rejects, timeout latches with no automatic duplicate retry. No gold/shell/Docker/CAD geometry in model input.
No heavy packages required. Existing pdftotext is optional later; text originals are the first checkpoint. Never copy code without source commit/hash provenance in docs/reuse.md.
