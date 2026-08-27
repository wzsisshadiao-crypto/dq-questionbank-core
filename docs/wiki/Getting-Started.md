# Getting Started

Three ways in - pick the one that matches how you got the code.

## Path A - downloaded a ZIP or cloned the repository (fastest)

1. Make sure Python 3.10+ is installed (`python --version`).
   If not, get it from [python.org](https://www.python.org/downloads/).
2. Double-click **`start.bat`** (Windows) or run **`sh start.sh`**
   (macOS/Linux). That is the whole step.
3. Your browser opens `http://127.0.0.1:8766` - the visual workspace,
   served from your machine only. Your data lives in the local
   `workspace/` directory, which Git ignores.

The launcher resolves Python via the `py` launcher or `PATH`, always runs
from the checkout root, and shows a readable message (not a window flash)
if Python is missing. Command-line equivalent: `python run.py`.

## Path B - installed from PyPI

```bash
python -m pip install dq-questionbank-core
dq-local
```

`dq-local` starts the same visual workspace. The `dq` CLI (see
[CLI Commands](CLI-Commands.md)) covers validate / convert / intake /
publish flows without the UI.

## Path C - contributor checkout

```bash
git clone https://github.com/wzsisshadiao-crypto/dq-questionbank-core
cd dq-questionbank-core
python -m pip install -e ".[docx,dev]"
python -m unittest discover -s tests    # everything green in ~20 s
python run.py
```

## Your first five minutes in the workspace

1. **Open the bundled public case** - ten original synthetic questions
   with tables, offline KaTeX math, answers, and analysis.
2. Browse with the year / subject / type / field filters.
3. Pick a question, edit a field in the Editor Center, save - the save is
   atomic and local.
4. Run the quality view: deterministic findings link straight to the exact
   question and field they refer to.
5. Try one import case headlessly: `dq intake cases`, then
   `dq intake run coding-pdf -o workspace/coding-pdf`.

Nothing you do in the workspace leaves your computer. Do not load private
or production question data; the project is for your own legally usable
material.

## Where to go next

- [Architecture](Architecture.md) - the complete system guide
- [Mechanisms](Mechanisms.md) - how every engine works
- Import a real paper with OCR + AI coding: [ocr-ai-coding-import](https://github.com/wzsisshadiao-crypto/dq-questionbank-core/blob/main/docs/ocr-ai-coding-import.md)
- LaTeX rules and locked edge cases: [latex-regression](https://github.com/wzsisshadiao-crypto/dq-questionbank-core/blob/main/docs/latex-regression.md)
- [Schema Reference](Schema-Reference.md) and [Format Guide](Format-Guide.md)
- [FAQ](FAQ.md)
