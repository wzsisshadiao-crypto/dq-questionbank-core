# Architecture

This page is the complete architecture guide: what the pieces are, how they
fit together, and where every hard boundary sits. For how a single mechanism
works internally, see [Mechanisms](Mechanisms.md).

## The three-layer picture

```text
+-------------------------------------------------------------+
|  dq_questionbank_local   (application layer)                |
|  visual workspace server - loopback HTTP, workspace files,  |
|  editor / bank / quality / paper UI, reviewed case adapter   |
+-------------------------------------------------------------+
              |  imports only the stable public API
              v
+-------------------------------------------------------------+
|  dq_questionbank         (core library)                     |
|  canonical model - validation - migrations - intake -       |
|  quality findings - safe repair - latex engines -           |
|  format adapters - storage adapters - CLI - plugins          |
+-------------------------------------------------------------+
              |  pure Python, stdlib-only, no I/O by default
              v
+-------------------------------------------------------------+
|  your data                 (ownership layer)                |
|  QuestionSet JSON files / SQLite database / Word documents  |
|  - created locally, owned by you, never uploaded            |
+-------------------------------------------------------------+
```

The dependency arrow points one way: the application layer may use the
core, never the reverse. The core library performs no network access,
spawns no processes, and writes nothing unless a caller hands it a path.

## Core library module map

| Area | Modules | Responsibility |
|---|---|---|
| Model | `models.py`, `schema.py`, `exceptions.py` | The recursive `QuestionSet -> Question -> Content -> ContentBlock` data model, versioned JSON Schema dispatch, catchable error hierarchy |
| Validation | `validation.py` | Structural rules, asset-path safety, unified `validate_with_schema()` |
| Evolution | `migration.py` | Registered, fail-closed schema migrations (`1.0 -> 1.1` ships built in) |
| Intake | `intake.py`, `import_triage.py`, `import_preflight.py`, `mapping_import.py` | Review-first import: bundle -> candidates -> digest-bound review -> export; triage classes; duplicate preflight; field mappings |
| Structure inference | `subpart_structure.py`, `passage_splitter.py`, `bilingual_splitter.py` | Deriving subquestions, shared passages, and bilingual stems from imported text |
| Quality | `quality_findings.py`, `safe_repair.py`, `quality_scan_runs.py`, `math_consistency.py` | Deterministic findings with severity/decision states, repair safety gates, resumable batch scans, conservative arithmetic checks |
| LaTeX | `latex_repair.py`, `latex_normalize.py`, `latex_compat.py` | Broken-source repair, graded normalization (autoFixable vs reviewReason), PDF-degradation compatibility repairs |
| Formats | `formats/`, `registry.py`, `plugins.py` | JSON/Markdown/LaTeX/DOCX adapters behind protocol-enforcing registry; explicit plugin discovery |
| Storage | `storage.py`, `sqlite_storage.py` | Atomic filesystem adapter; stdlib SQLite adapter |
| Publishing | `word_publishing.py`, `omml_import.py`, `formula_images.py`, `asset_repair.py`, `image_position_mapper.py` | Word envelope with fingerprinted content controls, OMML math import, formula-image transcription, image repair evidence |
| PDF intake | `pdf_splitter.py`, `pdf_workset.py`, `pdf_skeleton.py`, `pdf_postflight.py`, `pdf_metadata.py`, `pdf_identity.py` | Synthetic-PDF toolchain and the post-publication gates |
| Agent contracts | `coding_agent_workfile.py`, `word_macro_id.py` | Work-file contract for workspace-access coding agents; Word macro short-ID expansion |
| Operations | `cli.py`, `workspace_audit.py` | The `dq` command surface; read-only health audit |

## Application layer

`dq_questionbank_local` is a loopback-only HTTP server (`dq-local`, or
`python run.py`, or double-click `start.bat`). It serves the static
workspace UI, a small JSON API over your local workspace directory, and the
reviewed synthetic case database. It binds `127.0.0.1` only, stores
everything under an ignored `workspace/` directory, and never contacts the
network. The older `web/` static playground inside the core package is the
minimal no-API variant used by `dq serve`.

## The question lifecycle (data flow)

```text
source document (docx / pdf / json / markdown / latex)
   |  importer or coding-agent work file        extraction + evidence
   v
candidate questions         intake.py            nothing persisted yet
   |  triage + preflight + validation           deterministic gates
   v
review session              decisions file       human accept/reject per field
   |  export reviewed questions
   v
canonical QuestionSet       models.py            the single source of truth
   |  save (atomic) / load                      storage adapters
   v
quality loop                quality_findings    findings open the exact field
   |  safe repairs + re-scan after save
   v
paper assembly + export     word_publishing      refreshable Word blocks
```

Every arrow is an explicit transition a caller chooses; nothing flows
automatically from left to right. A plausible parse is never persisted
without a review decision, and a review decision never rewrites evidence.

## Hard boundaries

- **Local-first:** no telemetry, no update pings, no cloud sync. Servers
  bind loopback only.
- **Public/private:** the repository is a clean re-implementation. Private
  extraction rules, production questions, provider wiring, and operational
  records never enter the tree (audited by `scripts/audit_public_tree.py`).
- **Synthetic-only data:** every checked-in example and fixture is
  original, synthetic, or clearly licensed - real exam banks are excluded.
- **Engine-free AI:** the core defines the `AIProvider` interface and
  proposal boundaries but bundles no model, prompt, or credential.
- **English-only contract:** public API, CLI, docs, and this Wiki are
  English; question content itself is multilingual.

## Extension points

1. **Format plugins** - entry-point group `dq_questionbank.plugins`
   ([Plugin Development](Plugin-Development.md)).
2. **Storage adapters** - implement `StorageAdapter` (`load`/`save`).
3. **Schema migrations** - register edge functions in `migration.py`.
4. **Import profiles** - source-specific extraction behind the shared
   bundle/evidence contract ([importers](../importers.md)).
5. **AI providers** - bounded, review-gated proposals via `AIProvider`.

## How correctness is enforced

CI runs on every push and pull request: ruff, the full unittest suite,
deterministic regeneration of the installed import cases, the stable public
API manifest check, the public-tree audit (secrets, private data, file
types), documentation link checking, Wiki source/export verification, and
distribution builds. A weekly benchmark workflow enforces the performance
budgets in `benchmarks/workspace-budgets.json`. Nothing merges on a red
check.

Continue with [Mechanisms](Mechanisms.md) for how each engine works, or
back to [Home](Home.md).

