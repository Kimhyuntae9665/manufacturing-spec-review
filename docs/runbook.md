# Runbook
Start python -m spec_review.server --port 19081; use local demo profiles. SQLite state under data/ is ignored by Git. Keep loopback.
Baseline requires no model. Existing localhost qwen3:4b may run the serial live evaluator. Preserve shared inference path; never bypass a blocked timeout marker.
Model failure is manual inspection, not verified extraction. Reviewers explicitly confirm original sources.
Source/revision/role/approval/hash changes invalidate old comparisons; recompare current authorized documents.
Input API is read-only, with no upload/filesystem/shell/production/physical control.
For a fresh synthetic demo use a separate new --db path. Prior records are preserved; no automatic deletion.
