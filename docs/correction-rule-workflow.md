# Correction Rule Workflow

This guide demonstrates how to add a quality inspection or correction rule to DQ QuestionBank Core from start to finish.

## Public Boundary and Access

You **do not need access** to the private application, production databases, or proprietary question banks to contribute quality and correction rules.

All public core models, quality checks, synthetic test fixtures, and visual workspace interfaces are fully defined in this repository. All rules run against synthetic English data on your local machine.

---

## Deterministic LaTeX Repair Rule Set

Beyond detection rules, `src/dq_questionbank/latex_repair.py` ships a small
set of deterministic, fail-closed repair rules with a shared contract:

- every rule has a stable ID (`latex-missing-closing-brace`,
  `latex-bare-function-names`, `latex-delimiter-spacing`,
  `latex-operator-spacing`);
- each outcome keeps the original `source` next to the proposed `latex`, so
  the workflow always shows the result **before** a question is changed;
- `repair_latex_source` composes the safe rules in a fixed order and reports
  every applied rule ID on `applied_rules`;
- ambiguous input — mismatched plain delimiters such as `(x+1]`, a missing
  opening brace, multiple brace breaks — is never rewritten; it is returned
  as a `finding_code` + `finding_message` pair for manual review.

Synthetic before/after specimen pairs live in
`tests/fixtures/quality/` (`missing-brace-repair`, `rule-set`) and are
executed by `tests/test_latex_repair.py`, including idempotency and the
preserved-prose guarantee (`\text{a  +  b}` stays verbatim).

## Repository Layout: Where Code and Assets Belong

When contributing a new correction rule, files are organized as follows:

| Category | Location | Purpose |
|---|---|---|
| **Core Validation Rules** | `src/dq_questionbank/validation.py` | Structural, identifier, asset, and schema rules for canonical Python models. |
| **Workspace Quality Rules** | `src/dq_questionbank_local/web/app.js` (`runQualityChecks`) | Frontend inspection rules that populate the Quality Center and Editor Center. |
| **Fixtures** | `tests/fixtures/` or `examples/` | Synthetic English question payloads demonstrating valid and invalid states. |
| **Python Tests** | `tests/test_validation.py` or `tests/test_local_server.py` | Unit and integration tests verifying rule detection and passing behavior. |
| **Documentation** | `docs/` and `CONTRIBUTING.md` | Technical specifications, API guides, and contribution references. |

---

## End-to-End Example: Adding a Bounded Correction Rule

The following example walks through adding a bounded rule that detects when a single-choice question contains duplicate choice labels (for instance, two choices both labeled `"A"`).

### 1. Add the Bounded Rule

For core Python validation (`src/dq_questionbank/validation.py`), extend `validate_question`:

```python
def validate_question(question: Question) -> list[ValidationIssue]:
    issues = []
    # ...
    if question.type in ("single_choice", "multiple_choice") and question.choices:
        labels = [choice.id for choice in question.choices if choice.id]
        if len(labels) != len(set(labels)):
            issues.append(
                ValidationIssue(
                    code="duplicate_choice_id",
                    message="Question choice identifiers must be unique.",
                    path=f"questions[{question.id}].choices",
                    severity="error",
                )
            )
    return issues
```

For the local visual workspace (`src/dq_questionbank_local/web/app.js`), ensure `runQualityChecks` flags the issue for the Editor Center Correction Panel:

```javascript
// In runQualityChecks() inside app.js:
const choices = question.choices || [];
const ids = choices.map((choice) => choice.id).filter(Boolean);
if (new Set(ids).size !== ids.length) {
  findings.push(
    makeFinding(
      "error",
      question,
      questionIndex,
      "choices",
      "Duplicate choice label detected."
    )
  );
}
```

### 2. Add Before and After Fixtures

Create synthetic English fixtures illustrating the issue before correction and after correction.

**Before Correction (`before.json` - triggers finding):**

```json
{
  "schema_version": "1.0",
  "id": "sample-set",
  "title": "Synthetic Algebra Set",
  "language": "en",
  "questions": [
    {
      "schema_version": "1.0",
      "id": "q-101",
      "type": "single_choice",
      "language": "en",
      "stem": { "blocks": [{ "type": "text", "text": "Solve x + 2 = 5." }] },
      "choices": [
        { "id": "A", "content": { "blocks": [{ "type": "text", "text": "3" }] } },
        { "id": "A", "content": { "blocks": [{ "type": "text", "text": "5" }] } }
      ],
      "answer": { "kind": "choice", "value": "A" }
    }
  ]
}
```

**After Correction (`after.json` - passes check):**

```json
{
  "schema_version": "1.0",
  "id": "sample-set",
  "title": "Synthetic Algebra Set",
  "language": "en",
  "questions": [
    {
      "schema_version": "1.0",
      "id": "q-101",
      "type": "single_choice",
      "language": "en",
      "stem": { "blocks": [{ "type": "text", "text": "Solve x + 2 = 5." }] },
      "choices": [
        { "id": "A", "content": { "blocks": [{ "type": "text", "text": "3" }] } },
        { "id": "B", "content": { "blocks": [{ "type": "text", "text": "5" }] } }
      ],
      "answer": { "kind": "choice", "value": "A" }
    }
  ]
}
```

### 3. Add a Focused Test

Add a test case in `tests/test_validation.py` verifying that the invalid payload produces the expected finding and the corrected payload passes:

```python
def test_duplicate_choice_ids_are_rejected(self):
    question_invalid = Question(
        "q-101",
        "single_choice",
        Content.text("Solve x + 2 = 5."),
        choices=[Choice("A", Content.text("3")), Choice("A", Content.text("5"))],
        answer=Answer("choice", "A"),
    )
    issues = validate_question(question_invalid)
    self.assertIn("duplicate_choice_id", {issue.code for issue in issues})

    question_valid = Question(
        "q-101",
        "single_choice",
        Content.text("Solve x + 2 = 5."),
        choices=[Choice("A", Content.text("3")), Choice("B", Content.text("5"))],
        answer=Answer("choice", "A"),
    )
    self.assertEqual([], validate_question(question_valid))
```

### 4. Expose the Finding in the Correction Workflow

Quality findings integrate directly with the local visual workspace:

1. **Finding Severity & Target Field:** Each finding specifies `severity` (`"error"` or `"warning"`), `questionId`, `questionIndex`, `field` (such as `"stem"`, `"choices"`, `"answer"`, or `"solution"`), and a human-readable `message`.
2. **Quality Center Queue:** In the Quality Center view, findings are listed in a review queue. Clicking **Open in Editor** focuses the specific question and navigates directly to the relevant field.
3. **Editor Center Correction Panel:** When editing a question, the Correction Panel re-runs deterministic checks against the current in-memory edits, displaying live status and score metrics before saving.

### 5. Run Relevant Local Checks

Before submitting a pull request, run the repository's local check suite:

```bash
# Code style and linting
python -m ruff check src tests scripts

# Unit and integration test suite
python -m unittest discover -s tests -v

# Public repository tree and secret safety audit
python scripts/audit_public_tree.py

# Documentation link verification
python scripts/check_docs.py
```

Refer to [`CONTRIBUTING.md`](../CONTRIBUTING.md) for pull request guidelines and contribution standards.
