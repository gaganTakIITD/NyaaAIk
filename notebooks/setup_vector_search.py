# Databricks notebook source
# MAGIC %md
# MAGIC # Setup Databricks Vector Search for NyaaAIk
# MAGIC
# MAGIC This notebook creates a Vector Search endpoint and Delta Sync index
# MAGIC backed by the `main.india_legal.legal_rag_corpus` table.
# MAGIC
# MAGIC **Prerequisites:**
# MAGIC - Run `india_legal_policy_ingest.ipynb` (creates the corpus table)
# MAGIC - Run `build_rag_index.ipynb` (optional — FAISS index for fallback)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. Configuration

# COMMAND ----------

VS_ENDPOINT_NAME = "nyaya_vs_endpoint"
VS_INDEX_NAME = "main.india_legal.legal_rag_corpus_index"
SOURCE_TABLE = "main.india_legal.legal_rag_corpus"
# Databricks-managed embedding model (no need to run sentence-transformers in the app)
EMBEDDING_MODEL = "databricks-bge-large-en"
PRIMARY_KEY = "chunk_id"
EMBEDDING_SOURCE_COLUMN = "text"

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. Create Vector Search Endpoint
# MAGIC
# MAGIC Standard type: 20-50ms query latency, suitable for <1M rows.

# COMMAND ----------

from databricks.sdk import WorkspaceClient
from databricks.sdk.service.vectorsearch import EndpointType
import time

w = WorkspaceClient()

# Check if endpoint already exists
existing = [ep for ep in w.vector_search_endpoints.list_endpoints() if ep.name == VS_ENDPOINT_NAME]
if existing:
    ep_status = getattr(existing[0], "status", None) or getattr(existing[0], "endpoint_status", None)
    print(f"Endpoint '{VS_ENDPOINT_NAME}' already exists (status: {ep_status})")
else:
    print(f"Creating endpoint '{VS_ENDPOINT_NAME}'...")
    w.vector_search_endpoints.create_endpoint(
        name=VS_ENDPOINT_NAME,
        endpoint_type=EndpointType.STANDARD,
    )
    print("Endpoint creation started.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. Wait for Endpoint to be ONLINE

# COMMAND ----------

print(f"Waiting for endpoint '{VS_ENDPOINT_NAME}' to be ONLINE...")
for i in range(60):  # up to 10 minutes
    ep = w.vector_search_endpoints.get_endpoint(VS_ENDPOINT_NAME)
    # SDK versions vary: try .status, .endpoint_status, or inspect the object
    status = getattr(ep, "status", None) or getattr(ep, "endpoint_status", None) or str(ep)
    print(f"  [{i * 10}s] Status: {status}")
    if "ONLINE" in str(status).upper():
        print("Endpoint is ONLINE!")
        break
    time.sleep(10)
else:
    print("WARNING: Endpoint not ONLINE after 10 minutes. Check the UI.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. Verify Source Table

# COMMAND ----------

count = spark.table(SOURCE_TABLE).count()
print(f"Source table '{SOURCE_TABLE}' has {count} rows")
display(spark.table(SOURCE_TABLE).limit(3))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4b. Enable Change Data Feed
# MAGIC
# MAGIC Delta Sync indexes require Change Data Feed (CDF) on the source table.

# COMMAND ----------

spark.sql(f"ALTER TABLE {SOURCE_TABLE} SET TBLPROPERTIES (delta.enableChangeDataFeed = true)")
print(f"Change Data Feed enabled on {SOURCE_TABLE}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 5. Create Delta Sync Index with Managed Embeddings
# MAGIC
# MAGIC The index auto-computes embeddings from the `text` column using
# MAGIC `databricks-bge-large-en`. No need to pre-compute or store embeddings.

# COMMAND ----------

from databricks.sdk.service.vectorsearch import (
    DeltaSyncVectorIndexSpecRequest,
    EmbeddingSourceColumn,
    VectorIndexType,
    PipelineType,
)

# Check if index already exists
try:
    existing_idx = w.vector_search_indexes.get_index(VS_INDEX_NAME)
    idx_status = getattr(existing_idx, "status", None) or getattr(existing_idx, "index_status", None)
    print(f"Index '{VS_INDEX_NAME}' already exists (status: {idx_status})")
except Exception:
    print(f"Creating Delta Sync index '{VS_INDEX_NAME}'...")
    w.vector_search_indexes.create_index(
        name=VS_INDEX_NAME,
        endpoint_name=VS_ENDPOINT_NAME,
        primary_key=PRIMARY_KEY,
        index_type=VectorIndexType.DELTA_SYNC,
        delta_sync_index_spec=DeltaSyncVectorIndexSpecRequest(
            source_table=SOURCE_TABLE,
            embedding_source_columns=[
                EmbeddingSourceColumn(
                    name=EMBEDDING_SOURCE_COLUMN,
                    embedding_model_endpoint_name=EMBEDDING_MODEL,
                )
            ],
            pipeline_type=PipelineType.TRIGGERED,
        ),
    )
    print("Index creation started.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 6. Trigger Sync and Wait

# COMMAND ----------

print("Triggering index sync...")
try:
    w.vector_search_indexes.sync_index(VS_INDEX_NAME)
except Exception as e:
    print(f"Sync trigger note: {e}")

print(f"Waiting for index '{VS_INDEX_NAME}' to be ready...")
for i in range(60):
    try:
        idx = w.vector_search_indexes.get_index(VS_INDEX_NAME)
        status = idx.status
        print(f"  [{i * 10}s] Status: {status}")
        if "ONLINE" in str(status) or "READY" in str(status):
            print("Index is ready!")
            break
    except Exception as e:
        print(f"  [{i * 10}s] Waiting... ({e})")
    time.sleep(10)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 7. Smoke Test — Similarity Search

# COMMAND ----------

test_query = "What is theft under BNS?"
print(f"Testing query: '{test_query}'")

results = w.vector_search_indexes.query_index(
    index_name=VS_INDEX_NAME,
    columns=["chunk_id", "text", "title", "source", "doc_type"],
    query_text=test_query,
    num_results=5,
)

# Response is a dataclass — use as_dict() to get a plain dict, or access attributes directly.
resp = results.as_dict() if hasattr(results, "as_dict") else results
if isinstance(resp, dict):
    data_array = resp.get("result", {}).get("data_array", [])
else:
    data_array = getattr(getattr(resp, "result", None), "data_array", []) or []

print(f"\nResults ({len(data_array)} rows):")
for row in data_array:
    print(f"  {row[0]}: {row[2]} ({row[3]})")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 8. Service Principal Permissions
# MAGIC
# MAGIC For the Databricks App's service principal to query this index, grant:
# MAGIC
# MAGIC ```sql
# MAGIC -- Run in a SQL editor or notebook
# MAGIC GRANT USE CATALOG ON CATALOG main TO `<service-principal-app-id>`;
# MAGIC GRANT USE SCHEMA ON SCHEMA main.india_legal TO `<service-principal-app-id>`;
# MAGIC GRANT SELECT ON TABLE main.india_legal.legal_rag_corpus TO `<service-principal-app-id>`;
# MAGIC ```
# MAGIC
# MAGIC Also in the UI: **Compute → Vector Search → nyaya_vs_endpoint → Permissions → Add → CAN_QUERY**
# MAGIC
# MAGIC ## 9. Configure the App
# MAGIC
# MAGIC Add to `app.yaml`:
# MAGIC ```yaml
# MAGIC env:
# MAGIC   - name: "NYAYA_RETRIEVAL_BACKEND"
# MAGIC     value: "vector_search"
# MAGIC   - name: "NYAYA_VS_ENDPOINT_NAME"
# MAGIC     value: "nyaya_vs_endpoint"
# MAGIC   - name: "NYAYA_VS_INDEX_NAME"
# MAGIC     value: "main.india_legal.legal_rag_corpus_index"
# MAGIC ```
# MAGIC
# MAGIC Then redeploy. The app will use Vector Search as primary and fall back to FAISS if VS fails.
