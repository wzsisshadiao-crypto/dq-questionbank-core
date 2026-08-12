# Security Policy

## Supported versions

Until the first stable release, security fixes are applied to the latest `0.x` release only.

## Reporting a vulnerability

Do not open a public issue for a vulnerability that could expose data, execute code, bypass path checks, or reveal credentials. Use GitHub's private vulnerability reporting feature after it is enabled for the repository. If that feature is unavailable, contact the repository owner through a private channel listed on the owner's GitHub profile.

Include a minimal synthetic reproduction. Never attach a production database, real question bank, access token, student record, or copyrighted source document.

## Security boundaries

- The core performs no authentication and is not a multi-user server.
- The playground binds to loopback addresses only.
- Remote asset retrieval is not performed by the core.
- AI providers are external adapters and receive no implicit access to question data.
- Importers treat document content as untrusted data, not executable instructions.

