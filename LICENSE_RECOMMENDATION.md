# License Recommendation

This document is engineering guidance, not legal advice. The project owner must make the final decision before public release.

## Recommended default: Apache License 2.0

Apache-2.0 fits an open-core library when the goal is broad external adoption while preserving the ability to develop a separate proprietary product. It is permissive, includes an express patent grant, and does not require an application that merely uses the library to disclose its own source code.

## Alternatives

| License | Practical effect for this project |
|---|---|
| MIT | Very simple and permissive; lacks Apache-2.0's explicit patent language. |
| Apache-2.0 | Permissive with patent terms and contribution protections; recommended for review. |
| MPL-2.0 | File-level copyleft; modifications to covered files remain open, while separate proprietary files may remain closed. |
| GPL-3.0 | Strong copyleft for distributed combined works; can complicate proprietary integration. |
| AGPL-3.0 | Extends strong copyleft to network use; highest risk of conflicting with the intended private product boundary. |

## Decision checklist

- Confirm ownership of every code contribution included in the initial release.
- Confirm whether patent language is important.
- Decide whether third parties may embed the library in closed-source products.
- Decide whether changes to the core must remain public.
- Obtain qualified legal review if the private and public components will be distributed together.
- Add the exact license text as `LICENSE` and update `pyproject.toml` before publishing.

