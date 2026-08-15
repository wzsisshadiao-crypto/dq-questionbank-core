# Reference Filesystem Storage

`FilesystemStorageAdapter` is a small reference implementation of the
`StorageAdapter` protocol. It stores one canonical JSON question set at:

```text
<root>/question_sets/<question-set-id>.json
```

Question-set identifiers are restricted to ASCII letters, digits, dots,
hyphens, and underscores. Empty identifiers, path separators, parent-directory
segments, and symbolic-link targets are rejected. The deterministic layout is
intended for local tools and test fixtures, not as a database replacement.

`save()` writes a temporary file in the target directory, flushes it, and uses
an atomic replacement operation. Existing content remains intact if the final
replacement fails. `load()` verifies that the serialized identifier matches the
requested identifier.

The adapter does not implement concurrent writer coordination, user access
control, media lifecycle, encryption, databases, or remote storage. Applications
with those requirements should implement `StorageAdapter` in a separate package.

```python
from pathlib import Path

from dq_questionbank import FilesystemStorageAdapter

storage = FilesystemStorageAdapter(Path("local-question-sets"))
storage.save(question_set)
same_question_set = storage.load(question_set.id)
```
