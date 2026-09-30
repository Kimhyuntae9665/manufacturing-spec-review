# NOTA UI

The Korean manufacturing annotation workbench is built with plain local HTML, CSS and JavaScript. It is explicitly a synthetic workflow reproduction test and does not decide engineering equivalence, manufacturing suitability, design approval or CAD geometry.

## Workflow

- Select one server-allowlisted A/B engineer/reviewer demo profile. The opaque bearer is kept in memory/sessionStorage and appears only in the Authorization header; there is no enterprise SSO claim.
- Select a part with its equipment, production line and business review purpose.
- Read the approved reference specification and retained candidate drawing draft side by side. Part revision and document revision are separate badges. Server-provided source ID, approval state, permitted roles and full source hash are available in the provenance disclosure.
- Execute a rule baseline or explicitly request independent per-document model proposals. No inference runs during login, navigation, document loading or quote inspection.
- Inspect exactly three fields: material, finish and nominal coating thickness. Original full-line quote buttons fetch the current document and validate the line plus Unicode character span against server text before highlighting it. Unicode offsets use Array.from, avoiding UTF-16 offset drift. Missing values are never displayed as zero.
- Declared nominal mm/µm Decimal conversion is stated separately from engineering equivalence. Alternatives, qualifiers, ranges, tolerances, bounds, unsupported units and missing fields remain review conditions according to the backend's states.
- A reviewer records acknowledgement (reviewed) or follow-up (needs_followup). The UI contains no design-approval action. Model failure is explicit; a manual original-source confirmation checkbox is required before either reviewer record action.
- Stored comparisons can be reopened from audit history. An invalidated comparison shows no old fields/quotes/review decision and disables re-review. Changing source selections clears the old comparison.

## Boundaries

The frontend calls only the contract endpoints: health/profiles/session, parts/detail, documents/detail, compare, stored comparisons, review and audit. Hashes and identity/approval envelopes are server-provided. The browser does not compute or trust model-provided source hashes or approval states. Runtime UI reads no evaluation files or answers.

The server owns authorization, current revision selection, document-pair validation, extraction verification, Decimal conversion, stale detection and idempotent reviews. The UI supplements this with selection explanations and disabled controls.

All original/model/audit text uses textContent, DOM node creation and text nodes. No HTML interpolation, external CDN, package dependency or new API surface is used. Native forms/fieldsets, keyboard focus, polite status messages, a skip link and reduced-motion support are included.

GET deadlines are 15 seconds; explicit compare mutations have a 180-second client deadline. Writes are single-flight and never automatically retried. An uncertain timeout warns that server work may continue and checks audit with safe reads. Review timeout/stale conflict reloads the stored comparison with GET, never repeats a write. Expired sessions clear saved identity and enable reconnect. 403/404, connection failure, empty documents and partial read failures have explicit states.

## Verification

The UI worker validated JavaScript syntax, all 58 unique HTML IDs and 44 literal references, safe DOM use and a deterministic in-memory mock-DOM workflow. The focused mock checks passed source provenance/draft retention, full raw unit display, three-field coverage, single-flight comparison, engineer permission limits, astral-Unicode plus CRLF whole-line spans, failed-model manual confirmation, acknowledgement recording, duplicate blocking, sanitized stale shells and 401 reconnect. These checks make no real model request. Actual sandboxed Chrome integration passed on the live loopback backend for three synthetic parts, engineer/reviewer permissions, whole-line quote highlighting, Decimal nominal display, material/finish differences, missing thickness, follow-up acknowledgement with candidate draft retained, duplicate UI write prevention and mobile overflow. A browser-response failure mock rewrites model requests to baseline before the server and explicitly labels the mocked failure screenshot; no model inference is used by that check. The helper also reopened one genuine root-owned failed-model record and three source-verified per-document model comparisons read-only, producing four additional screenshots with no new inference. A total of eleven screenshots distinguish actual baseline UI, explicit browser failure mock, genuine model failure and stored verified extraction. Source verification does not assert engineering equivalence or design approval. Artifacts are in artifacts/browser-check/. Model requests remain root-coordinated.


## Remaining accessibility work

A dedicated accessibility pass is not complete. The follow-up target is at least 14px for body/original-source/badge small text and a measured 4.5:1 contrast ratio for normal text, including muted labels. Existing native controls, focus styles and mobile checks do not establish that these typography and contrast targets have been met.


## Actual UI video

artifacts/ui-video/nota-workflow.mp4 is an 8.959-second, silent H.264 recording at 1600×1200. It shows actual baseline P001 sources, P002 material difference, P003 finish difference/missing thickness, a read-only stored actual-model P002 comparison, and verified original-line highlighting. No model request or mocked failure/success was introduced during recording. Thirty-five native Chrome screencast JPEGs and their acquisition timestamps remain in native-frames.json; encoding retains all frames in order and repeats the last original frame to retain its hold duration (36 encoded frames). The helper reconstructs presentation times from native metadata at microsecond precision; only even-dimension padding is permitted as a pixel transform. probe.json records codec, dimensions, frame count and duration. The capture retains native browser UI rather than adding narration or captions. Visual checks found no bearer value or personal path in the viewport. The small-text and contrast follow-up above remains open.
