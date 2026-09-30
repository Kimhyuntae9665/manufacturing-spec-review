# Observed failures and repairs
First actual P001 request: Coating thickness: : 10 µm quote had an extra colon. Full-line validation rejected it, despite HTTP success/valid JSON. CPU inspection remained available and manual confirmation required.
Repair: enum all full original source lines/null, no field-specific answer or evaluator label. Raw values remain proposed, wrong-field/partial/ambiguous quotations remain checked.
2026-09-30 09:27 UTC same development corpus rerun: 3pairs/6requests source_verified. Prior failure retained; no heldout claim.
Independent review found unauthorized engineer GET/audit invalidated unchanged reviewer-only comparisons. Authorization and source-policy change detection are now separate, with core/HTTP regressions.
No actual timeout occurred; persistent timeout barrier is mocked/subprocess-tested. Server cancellation/recovery is not claimed.
