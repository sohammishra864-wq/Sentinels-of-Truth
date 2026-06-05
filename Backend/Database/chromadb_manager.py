import chromadb
from sentence_transformers import SentenceTransformer

class Chromamanager:
    def __init__(self, client: chromadb.PersistentClient, collection_name: str, embedding_model: SentenceTransformer):
        self.client = client
        self.embedding_model = embedding_model
        self.collection = client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"}
        )

    def add_claim(self, claim_id: str, claim_text: str, metadata: dict) -> None:
        embedding = self.embedding_model.encode(claim_text).tolist()
        self.collection.add(
            ids=[claim_id],
            embeddings=[embedding],
            documents=[claim_text],
            metadatas=[metadata]
        )

    def search_similar(self, claim_text: str, n_results: int = 3) -> list[dict]:
        embedding = self.embedding_model.encode(claim_text).tolist()
        results = self.collection.query(
            query_embeddings=[embedding],
            n_results=n_results,
            include=["metadatas", "distances"]
        )
        formatted = []
        if results["ids"] and results["ids"][0]:
            for i, claim_id in enumerate(results["ids"][0]):
                distance = results["distances"][0][i]
                formatted.append({
                    "claim_id": claim_id,
                    "distance": distance,
                    "similarity": 1.0 - distance,
                    "metadata": results["metadatas"][0][i] if results.get("metadatas") else {}
                })
        return formatted

    def get_by_claim_id(self, claim_id: str) -> dict | None:
        results = self.collection.get(
            ids=[claim_id],
            include=["documents", "metadatas"]
        )
        if not results["ids"]:
            return None
        return {
            "claim_id": results["ids"][0],
            "claim_text": results["documents"][0],
            "metadata": results["metadatas"][0]
        }

    def delete_claim(self, claim_id: str) -> None:
        self.collection.delete(ids=[claim_id])

    def count(self) -> int:
        return self.collection.count()