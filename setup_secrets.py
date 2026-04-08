# Databricks notebook source
# MAGIC %md
# MAGIC # NyaaAIk — Secret Scope Setup
# MAGIC
# MAGIC Run this notebook **once** to create the `nyaya-dhwani` secret scope and store all API keys.
# MAGIC After running, the NyaaAIk app will automatically pick them up at startup — no keys in any config file.
# MAGIC
# MAGIC > **Run each cell one at a time. Fill in your real API keys before running cells 3 and 4.**

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 1 — Create the secret scope (skip if it already exists)

# COMMAND ----------

# Create the scope (Databricks-managed, no Azure Key Vault needed)
try:
    dbutils.secrets.createScope(scope="nyaya-dhwani")
    print("✅ Scope 'nyaya-dhwani' created.")
except Exception as e:
    if "already exists" in str(e).lower():
        print("ℹ️  Scope 'nyaya-dhwani' already exists — skipping.")
    else:
        raise

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 2 — Verify the scope is visible

# COMMAND ----------

scopes = [s.name for s in dbutils.secrets.listScopes()]
assert "nyaya-dhwani" in scopes, "Scope not found — re-run Step 1"
print("Scopes available:", scopes)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 3 — Store the Indian Kanoon API token
# MAGIC
# MAGIC Get your token from [indiankanoon.org/api](https://api.indiankanoon.org/)

# COMMAND ----------

INDIAN_KANOON_TOKEN = "PASTE_YOUR_INDIAN_KANOON_TOKEN_HERE"   # <-- replace this

assert INDIAN_KANOON_TOKEN != "PASTE_YOUR_INDIAN_KANOON_TOKEN_HERE", \
    "Please replace the placeholder with your actual Indian Kanoon API token"

dbutils.secrets.put(
    scope="nyaya-dhwani",
    key="indian_kanoon_api_token",
    string_value=INDIAN_KANOON_TOKEN,
)
print("✅ indian_kanoon_api_token stored.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 4 — Store the Sarvam API key
# MAGIC
# MAGIC Get your key from [dashboard.sarvam.ai](https://dashboard.sarvam.ai/)
# MAGIC Used for voice input (Saaras v3 STT) across 10 Indian languages.

# COMMAND ----------

SARVAM_API_KEY = "PASTE_YOUR_SARVAM_API_KEY_HERE"   # <-- replace this

assert SARVAM_API_KEY != "PASTE_YOUR_SARVAM_API_KEY_HERE", \
    "Please replace the placeholder with your actual Sarvam API key"

dbutils.secrets.put(
    scope="nyaya-dhwani",
    key="sarvam_api_key",
    string_value=SARVAM_API_KEY,
)
print("✅ sarvam_api_key stored.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 5 — Verify all keys are stored (values are redacted for security)

# COMMAND ----------

keys = [k.key for k in dbutils.secrets.list("nyaya-dhwani")]
print("Keys in scope 'nyaya-dhwani':", keys)

expected = {"indian_kanoon_api_token", "sarvam_api_key"}
missing  = expected - set(keys)

if missing:
    print(f"⚠️  Missing keys: {missing} — re-run the relevant step above")
else:
    print("✅ All secrets configured. Redeploy the NyaaAIk app to pick them up.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Done
# MAGIC
# MAGIC | Secret key | Used for |
# MAGIC |---|---|
# MAGIC | `indian_kanoon_api_token` | Live case search from indiankanoon.org |
# MAGIC | `sarvam_api_key` | Voice input — Sarvam Saaras v3 STT (10 Indian languages) |
# MAGIC
# MAGIC **Next step:** Go to **Compute → Apps → NyaaAIk → Deploy** to restart the app with the new secrets.
# MAGIC
# MAGIC The app logs will show:
# MAGIC ```
# MAGIC INFO - Indian Kanoon API: configured
# MAGIC INFO - Sarvam STT (Saaras): configured
# MAGIC ```
