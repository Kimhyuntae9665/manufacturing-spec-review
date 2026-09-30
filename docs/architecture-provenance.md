# Architecture diagram provenance

Browser requests the loopback Python API. Current authorized JSON documents feed CPU extraction/provenance and Decimal comparison. Optional Qwen extraction submits the reference and candidate separately and serially through Ollama. Exact whole-line source validation precedes comparison. Human reviewer acknowledgements and audits are stored in SQLite. No PDF/OCR/CAD geometry or active n8n is depicted.

PNG is the inline README asset; SVG is the editable, fully embedded source. Six compact cards use actual technology glyphs where available. JSON braces are a locally authored functional symbol. Browser contains the JavaScript glyph for the vanilla client. The undirected Ollama/Qwen link denotes runtime/model association; dashed arrows are optional requests and returned proposals, not parallel GPU workers. The solid Python/SQLite arrow denotes server-owned persistence after human review.

Inspected source commit: 727dbf7fed8dcdaad767e0e9a15a9fb4888c5d55. Diagram generation does not rerun a model or change benchmark results. Final PNG pixels and an actual 360px-wide CPU browser capture were visually inspected; technology labels are 28px in the 720px source (14px at 360px display).

Reference style: user-supplied synthetic-logo-rendering-compatibility-test.png, version1, 800x510, SHA256 c6ad5fda762ea72fb40020e56e6242d74b86c9adff00d95b8027f7981e250df8. The supported Library consumer download was completed with verified identity/version metadata on Linux and its actual pixels were viewed on the consumer workspace. Windows does not support the helper extended attributes; the original Linux materialization retains them. Its synthetic model topology is not copied.

## Glyph sources

- [python](https://raw.githubusercontent.com/simple-icons/simple-icons/develop/icons/python.svg) · SHA256 ad9468e1c4903f73ae7eebfbe980f0f727a10db695be3d914e7d8bd25356a862 · Simple Icons community glyph; CC0 project source. Color and size adapted for documentation.
- [javascript](https://raw.githubusercontent.com/simple-icons/simple-icons/develop/icons/javascript.svg) · SHA256 c9be35a7a861ebe80ae4ee706d05004b99ee59fc63db69da6dcc10776718434b · Simple Icons community glyph; CC0 project source. Color and size adapted for documentation.
- [sqlite](https://raw.githubusercontent.com/simple-icons/simple-icons/develop/icons/sqlite.svg) · SHA256 71d4153bc9661dfe6b92dad70f737ec2b6c7c839311e502b4ca66fe664fe12b6 · Simple Icons community glyph; CC0 project source. Color and size adapted for documentation.
- [ollama](https://raw.githubusercontent.com/simple-icons/simple-icons/develop/icons/ollama.svg) · SHA256 9c62bf0159ee96c8b58c86a732f33b002b4b3bb165ec86e8ecca51ad6a82dab6 · Simple Icons community glyph; CC0 project source. Color and size adapted for documentation.
- [qwen](https://raw.githubusercontent.com/simple-icons/simple-icons/develop/icons/qwen.svg) · SHA256 36854c60b26bfa5a0cc0d4123727c0ef559efba6f129c0dfa623f3c443fe3e5b · Simple Icons community glyph; CC0 project source. Color and size adapted for documentation.

[Simple Icons CC0 license](https://github.com/simple-icons/simple-icons/blob/develop/LICENSE.md). Technology names and marks identify components, without implying endorsement. No image/font/CDN loads are needed for these diagrams.

## Inspected implementation

- spec_review/core.py SHA256 44e297d92bc10f2b97155a226c26b5fe15262267643cd9e1d0c0510786b0ea55
- spec_review/extraction.py SHA256 be8abe40425ef32f69e80fa41bb5c3b92f55ae989549ccb4f818fedcf5adf288
- spec_review/comparison.py SHA256 30af6fdbba37ea218f58409f688163dce2edb2ee16fb34721986dec556c073b4
- spec_review/llm.py SHA256 ba5c41e652875d39ce7e1f5639027c0b08866120a8068f84320f2e3d6885a14e
