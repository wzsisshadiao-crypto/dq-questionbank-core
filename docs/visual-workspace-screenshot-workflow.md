# Visual Workspace Screenshot Workflow

This guide explains how to update the README workspace screenshot after an intentional UI change.

## Prerequisites

- Python 3.10–3.12
- A clean source checkout
- No private questions, production databases, credentials, or private application screenshots

## Steps

### 1. Set up the local workspace

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e ".[docx,dev]"
```

### 2. Launch with a temporary workspace directory

Use a temporary workspace directory so no personal data is written into your
checkout. The command below resolves an OS-provided temp path on Linux, macOS,
and Windows alike:

```bash
python run.py --workspace "$(python -c "import tempfile; print(tempfile.mkdtemp())")"
```

This creates a temporary directory for the workspace session (for example
`/tmp/...` on Linux/macOS or `%TEMP%\...` on Windows).

### 3. Open the bundled synthetic case

- In the application, navigate to the synthetic case
- The synthetic case is located at `src/dq_questionbank_local/data/synthetic-case.sqlite3`

### 4. Select the group-table question

- Find and select the group-table question from the question list
- This question type demonstrates the Editor Center quality panel

### 5. Verify rendered KaTeX

- Ensure KaTeX math rendering is working correctly
- Check that equations display properly in the question view

### 6. Verify the Editor Center quality panel

- Open the Editor Center
- Verify the quality panel is visible and functioning
- Check that all quality metrics are displayed

### 7. Capture the desktop screenshot

- Use your OS screenshot tool to capture the application window
- Match the existing `docs/assets/question-bank-workspace.png` (1425×990) so the
  README screenshot stays consistent with the repository's current convention
- Ensure the screenshot shows:
  - The question view with rendered KaTeX
  - The Editor Center quality panel
  - No private content or credentials

### 8. Update the social-preview composition

- Compose the social preview at 1280×640 to match the existing
  `docs/assets/social-preview.png` (the repository's documented convention)
- Place the screenshot in `docs/assets/`
- Update `README.md` to reference the new screenshot
- Ensure no private content is visible in the composition

## Important Restrictions

**DO NOT include:**
- Private questions or question banks
- Production databases or real exam content
- Credentials, API keys, or private URLs
- Private application screenshots
- Real user data

**DO use:**
- Synthetic fixtures only
- The bundled synthetic case
- Public, non-sensitive data

## Verification

After updating the screenshot:

1. Run documentation link checks:
   ```bash
   python scripts/audit_public_tree.py
   ```

2. Verify the README renders correctly on GitHub

3. Ensure the screenshot file size is reasonable (< 1MB recommended)

## Troubleshooting

### KaTeX not rendering
- KaTeX is vendored and rendered offline from `src/dq_questionbank_local/web/vendor/katex/`; no internet connection or CDN is required
- Hard-refresh the browser and clear its cache for the local workspace origin
- Check the browser console for errors

### Editor Center panel not showing
- Verify the synthetic case is loaded correctly
- Check that the question type supports the quality panel

### Screenshot quality issues
- Use a high-resolution display
- Ensure the application is in focus
- Clear any debug overlays before capturing
