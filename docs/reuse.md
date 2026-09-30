# Reuse boundaries
Independent project checkout/runtime. Corpus/UI/API/reviews do not depend on project01.
The bounded Ollama transport and portable-lock regression patterns were copied from project01 source commit721949d17891bbb009b31b19a20469bd0946991c. Both subsequently received persistent timeout barriers. Incident rules/schema were not copied.
Only intentional runtime sharing: documented user-private OS lease/timeout marker. No concurrent model requests.

The engineering-only CI workflow was copied from the same project01 checkpoint, with an additional independent frozen synthetic evaluator step. It never invokes the actual-model script.
