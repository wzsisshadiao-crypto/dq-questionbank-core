# Test Fixture Contributions

The project welcomes small question specimens that help exercise importers,
renderers, editors, validators, exporters, and schema compatibility. A fixture
must be legally redistributable in this repository. The fact that a document is
available on a public website is not, by itself, permission to copy it.

## Accepted provenance

Submit one of the following, with evidence in `provenance.json`:

- **Original or synthetic**: written by the contributor for this repository or
  generated as a deliberately non-identifying test case.
- **Public domain or CC0**: include the jurisdiction or declaration when it is
  relevant.
- **Openly licensed**: for example CC BY, CC BY-SA, or another license that
  permits redistribution in this repository. Include the exact license and
  required attribution. Copyleft or share-alike terms must be called out before
  review.
- **Contributor-owned**: the contributor owns the copyright and grants this
  project permission to redistribute the submitted material under the
  repository's license or a clearly stated fixture license.
- **Licensed public dataset**: include the dataset name, version, license,
  source URL, and the subset or transformation used.

Do not submit private application data, production database extracts, answer
keys or exam papers whose redistribution rights are unclear, credentials,
personal data, or content copied from a publisher merely because it is online.
When a source cannot be redistributed, submit a synthetic surrogate, a
format-only specimen, or metadata and expected behavior without the protected
content.

## Accepted input formats

We want coverage across the full intake boundary. Small files are preferred,
and a specimen may be submitted even when an importer is not implemented yet,
provided it is marked `unsupported` and includes the intended canonical result
or a short parsing expectation.

- Plain text, Markdown, HTML, and rich text extracts
- JSON, YAML, XML, CSV, TSV, and spreadsheet tables such as XLSX
- LaTeX, MathML, and AsciiMath, including formulas mixed with prose
- DOCX and ODT documents, including inline images and structured tables
- PDF documents and scanned PNG, JPEG, or TIFF pages, with OCR notes where
  applicable
- Formula or diagram images, referenced assets, and table-heavy questions
- QTI and other education interchange formats when their license permits
  redistribution
- Deliberately malformed, partial, Unicode, multilingual, or mixed-format
  samples that test rejection and recovery behavior

The format list is intentionally broad rather than a promise that every format
is already supported. Importers must treat all input as untrusted: no macros,
scripts, implicit network fetches, or execution of embedded instructions.

## Fixture package

Put each contribution in a focused directory such as
`tests/fixtures/community/<slug>/`:

```text
source.<original-extension>
expected.json             # when a canonical result is available
provenance.json           # required
README.md                 # scope, handling notes, and expected behavior
```

Keep source files small and deterministic. Remove unnecessary metadata and
personal information. Binary files should be limited to the smallest specimen
that demonstrates the behavior; do not commit databases, archives, or large
collections.

`provenance.json` should record, at minimum:

```json
{
  "source_type": "original | synthetic | public_domain | open_license | owned",
  "format": "markdown",
  "license": "CC0-1.0",
  "attribution": "Optional required attribution",
  "source_url": "https://example.invalid/source",
  "author": "Name or organization",
  "accessed": "YYYY-MM-DD",
  "permission_note": "Why redistribution is permitted",
  "redistribution_status": "cleared",
  "language": "en",
  "encoding": "UTF-8",
  "redactions": "None"
}
```

Use `source_url: null` for original or synthetic material and explain that
choice in `permission_note`. If a field does not apply, use `null` rather than
silently omitting provenance.

## Review path

1. Open the **Test fixture contribution** issue form and describe the source,
   format, license, and behavior to exercise.
2. A maintainer checks provenance, size, privacy, and public-tree policy before
   asking for a pull request.
3. The pull request adds the smallest fixture package, expected canonical
   output when possible, and focused importer or compatibility tests.
4. CI runs the public-tree audit and the normal test suite. A maintainer may
   request a synthetic replacement or remove a fixture if its rights cannot be
   verified.

Fixtures are test inputs, not an endorsement of the source or a commitment to
support its format. Please keep the public technical contract and documentation
in English; the question payload itself may use any language when its license
and encoding are documented.
