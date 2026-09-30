# Readability verification

The 2026-09-30 pass changes local CSS and the browser's motion preference handling. It preserves extraction, source-line/span validation, Decimal comparison, source approval state, reviewer authorization and acknowledgement semantics. No model request was made during verification.

| Actual browser measurement | Before | After |
|---|---:|---:|
| Source/full-line quote text | 11px / 9px desktop; 10px / 8px mobile | 14px |
| Smallest rendered direct text | 7px desktop; 6px mobile | 14px |
| Lowest normal-text contrast | 1.999:1 | 4.701:1 |
| Korean long explanations / controls | Mostly 8–11px | 16px |
| Mobile CSS viewport / scale | Captured and recorded | 390px / 1 |

The minimum measurements inspect rendered direct text nodes in the loaded P001 source, result, review and audit workspace, excluding disabled controls. They use computed text colors over ancestor background colors and do not constitute a complete accessibility audit. The driver also verifies native width, scale and absence of document overflow rather than accepting browser auto-shrink. Original unaltered lines can scroll inside their source panes; comparison quotes wrap.

| View | Actual before | Actual after |
|---|---|---|
| Desktop source | [Before](demo/readability/before/desktop-source.png) | [After](demo/readability/after/desktop-source.png) |
| Desktop comparison | [Before](demo/readability/before/desktop-result.png) | [After](demo/readability/after/desktop-result.png) |
| Mobile source | [Before](demo/readability/before/mobile-source.png) | [After](demo/readability/after/mobile-source.png) |
| Mobile comparison | [Before](demo/readability/before/mobile-result.png) | [After](demo/readability/after/mobile-result.png) |

Native captures settle browser paint and record viewport width, scale and scroll position. No screenshot compositing, retouching or synthetic replacement was used. The original video remains historical evidence of the preceding typography.

The actual Chrome regression covers three synthetic parts, original whole-line highlight, declared nominal conversion, suffix/finish differences, missing thickness, engineer review limits, candidate draft retention, follow-up/audit, duplicate writes and the manual-source confirmation gate. Its failure response is explicitly mocked over a baseline backend request. Under emulated prefers-reduced-motion, both original-source scrolls and stored-history reopening use auto; spinner animation is disabled. Seven current regression screenshots are separate from the eight before/after captures.

Validation: 72 engineering tests passed, 16/16 frozen synthetic rule cases passed, JavaScript syntax passed, native Chrome regression passed. These are separate test sets, not an industrial model accuracy claim. Runtime never reads frozen answers.

Reproduce with the sandboxed Chrome CDP listener and application loopback listener available:

```sh
python3 scripts/browser_check.py --readability after --output artifacts/readability-after
python3 scripts/browser_check.py --output artifacts/browser-readability
python3 -m unittest discover -s tests
python3 scripts/evaluate_frozen.py
node --check static/app.js
```

The before captures were taken before the CSS change; running the current source cannot reconstruct the old view. The driver opens and closes only its own tab and makes no actual-model call.
