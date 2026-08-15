# Format Guide

| Format | Import | Export | Guarantee |
| --- | --- | --- | --- |
| JSON | Yes | Yes | Canonical and deterministic |
| Markdown | Yes | Yes | Canonical for generated files |
| LaTeX | Yes | Yes | Canonical for generated files |
| DOCX | Yes | Yes | Documented core fields |

Use JSON for interchange and storage. Generated Markdown and LaTeX preserve
machine-readable markers for deterministic re-import. DOCX uses a visible
label convention and extracts embedded images to a caller-selected directory.

See [importers](../importers.md), [exporters](../exporters.md), and the
[compatibility policy](../compatibility.md) for limits and safety rules.
