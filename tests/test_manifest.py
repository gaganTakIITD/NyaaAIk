import json
from pathlib import Path

from nyaya_dhwani.manifest import RAGManifest, utc_now_iso


def test_manifest_roundtrip(tmp_path: Path):
    m = RAGManifest(
        embedding_model="sentence-transformers/all-MiniLM-L6-v2",
        embedding_dim=384,
        faiss_index_file="corpus.faiss",
        chunks_parquet_file="chunks.parquet",
        num_vectors=10,
        catalog="main",
        schema="india_legal",
        source_table="legal_rag_corpus",
        created_at_utc=utc_now_iso(),
    )
    p = tmp_path / "manifest.json"
    p.write_text(m.to_json(), encoding="utf-8")
    loaded = RAGManifest.load(p)
    assert loaded.embedding_dim == 384
    assert loaded.num_vectors == 10
    data = json.loads(p.read_text(encoding="utf-8"))
    assert data["metric"] == "inner_product"
