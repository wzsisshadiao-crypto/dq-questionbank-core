# Configurable Document-to-Question Mapping

Different sources label the same question fields differently — `Prompt`
vs `Question`, `Explanation` vs `Rationale`. `dq_questionbank.mapping_import`
applies an explicit mapping configuration so an adapter can be adjusted
without changing the canonical model.

## The mapping configuration

```json
{
  "set_id": "training-exam",
  "labels": [
    { "source": "Prompt", "canonical": "stem" },
    { "source": "Question", "canonical": "stem" },
    { "source": "Options", "canonical": "choices" },
    { "source": "Correct answer", "canonical": "answer" },
    { "source": "Explanation", "canonical": "analysis" },
    { "source": "Rationale", "canonical": "analysis" },
    { "source": "Worked solution", "canonical": "solution" },
    { "source": "Topic", "canonical": "subject" }
  ]
}
```

The documented alternates (`Question` for `Prompt`, `Rationale` for
`Explanation`) show a real, modest customization: two sources with
different heading vocabularies map through one configuration. Mapping
targets are limited to canonical fields (`analysis` lands in
`metadata.analysis`, matching the canonical model); duplicate source
labels and unknown targets fail closed.

## Applying the mapping

```python
from pathlib import Path

from dq_questionbank import apply_mapping, load_mapping

mapping = load_mapping(Path("examples/question_mapping.json"))
records = json.loads(Path("examples/mapped_source_records.json").read_text())
result = apply_mapping(mapping, records)
result["question_set"]       # canonical question-set payload
result["unmapped_labels"]    # per-record labels the mapping did not cover
result["unmapped_records"]   # records with no mapped stem at all
```

**Unmapped content is reported for review rather than silently
discarded**: every label the configuration did not cover appears in
`unmapped_labels` (in the bundled example, `Difficulty`), and a record
without any mapped stem is listed in `unmapped_records` instead of
vanishing.

The bundled example (`examples/question_mapping.json` +
`examples/mapped_source_records.json`) uses only synthetic English data,
and `tests/test_mapping_import.py` proves the mapped result equals the
hand-written canonical JSON exactly.
