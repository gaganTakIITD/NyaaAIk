# Free Edition workspace setup

## Security first

**If you ever pasted API keys or a GitHub token into chat, email, or a ticket, assume they are compromised.**

1. **Sarvam:** [Sarvam dashboard](https://dashboard.sarvam.ai) — revoke the old key and create a new one.
2. **GitHub:** [Settings → Developer settings → Personal access tokens](https://github.com/settings/tokens) — revoke the old PAT and create a new fine-grained or classic token with **repo** scope (for Databricks Repos).
3. **Databricks:** If a key was stored in a notebook or file, rotate it and use **Secrets** only (below).

Do **not** commit `.env`, tokens, or `dbutils.secrets` values to git.

---

## 1. CLI auth (`free-aws` profile)

See [README.md](../README.md). Verify:

```bash
export DATABRICKS_CONFIG_PROFILE=free-aws
databricks current-user me
```

---

## 2. Databricks secret scope: `nyaya-dhwani`

Create the scope once (requires permission to create scopes; on some workspaces only admins can — ask an admin if this fails):

```bash
databricks secrets create-scope nyaya-dhwani --profile free-aws 2>/dev/null || true
```

Store secrets **without echoing them in shell history** (interactive; paste when prompted):

```bash
databricks secrets put-secret nyaya-dhwani sarvam_api_key --profile free-aws
# paste new Sarvam API key, then newline and Ctrl-D (macOS/Linux)
```

Repeat for `datagov_api_key` if you use data.gov.in APIs.

Notebook access:

```python
sarvam = dbutils.secrets.get(scope="nyaya-dhwani", key="sarvam_api_key")
```

---

## 3. GitHub + Databricks Repos

Use a **new** GitHub PAT (never commit it to the repo).

1. In **Databricks** workspace: **Workspace** → **Repos** → **Add Repo**.
2. Choose **GitHub**, authorize or paste **HTTPS** URL: `https://github.com/<org>/nyaya-dhwani-hackathon.git`
3. When prompted for credentials, use your GitHub username and the **PAT** as the password (or use the GitHub app integration if available).

Alternatively: **User Settings** → **Linked accounts** / **Git** integration per [Databricks Repos docs](https://docs.databricks.com/en/repos/index.html).

After clone, open `notebooks/india_legal_policy_ingest.ipynb` from the Repo path and attach compute.

---

## 4. Build RAG index on a Volume

After `legal_rag_corpus` exists, run the index builder (cluster or serverless notebook) — see [notebooks/build_rag_index.ipynb](../notebooks/build_rag_index.ipynb).

Default output directory (matches ingestion Volume layout):

`/Volumes/main/india_legal/legal_files/nyaya_index/`

Contents: `manifest.json`, `corpus.faiss`, `chunks.parquet`.

---

## 5. Troubleshooting

| Issue | Action |
|-------|--------|
| `create-scope` denied | Admin creates scope `nyaya-dhwani` and grants you `PUT` on secrets |
| Invalid token on CLI | Re-run `databricks auth login --host https://dbc-6651e87a-25a5.cloud.databricks.com --profile free-aws` |
| Repo clone fails | PAT needs `repo` scope; HTTPS URL must match the repository |
