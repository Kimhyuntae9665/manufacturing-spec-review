# Evaluation manifest
Frozen before model extraction at 2026-09-30T08:42:33Z: 3 parts, 6 documents, 16 synthetic cases.
Gold SHA256: 3a73755e9e86a228222ca7f67aa90dd46e557c5f212e83f63397c96dcedd9272.
Corpus SHA256: fddb4a47cd32a94183279f1c16b503ecf1bf7f1de1f36b181e501b1003dcafc0.
No expert validation or real-factory/heldout claim. Runtime never imports gold. Evaluator checks hashes.
72 engineering tests are separate from 16/16 frozen rule cases and actual-model development examples.
An initial actual request invented a colon in a quote and failed. A source-line enum repair then passed 6 separate document requests in 3 fixed pairs, not a new heldout score.
Per-pair total server time 5699.762 / 3769.609 / 3665.245ms, peak observed VRAM3610MiB. Stop reason and thinking_chars0 observed; general thinking suppression remains unproven.
Browser coverage: provenance, nominal conversion, suffix difference, missing field, retained draft, engineer no-review, whole-line quote, followup/audit, duplicate write guard, mobile. Injected browser failure is explicitly mocked and requests baseline backend.
