# Security

- **Never commit** API keys, GitHub PATs, or `dbutils.secrets` values to this repository.
- Use **Databricks secret scope** `nyaya-dhwani` and/or a local `.env` file that is gitignored.
- If credentials were exposed (chat, screenshots, CI logs), **rotate** them at the provider (Sarvam, GitHub, Databricks) and update secrets only through secure channels.

See [WORKSPACE_SETUP.md](WORKSPACE_SETUP.md) for storing secrets in the Free Edition workspace.
