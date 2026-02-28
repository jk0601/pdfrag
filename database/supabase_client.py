"""
supabase_client.py - Supabase 데이터베이스 클라이언트
=====================================================
문서와 청크 데이터를 Supabase에 저장하고 검색하는 기능을 제공합니다.
"""

from supabase import create_client, Client
from config import Config


class SupabaseDB:
    """Supabase 데이터베이스 작업을 담당하는 클래스"""

    def __init__(self):
        self.client: Client = create_client(
            Config.SUPABASE_URL,
            Config.SUPABASE_KEY,
        )

    # ------------------------------------------------------------------
    # 문서(Document) 관련
    # ------------------------------------------------------------------

    def insert_document(
        self,
        filename: str,
        file_type: str,
        file_size: int,
        page_count: int | None = None,
    ) -> dict:
        """새 문서 레코드를 DB에 저장합니다."""
        data = {
            "filename": filename,
            "file_type": file_type,
            "file_size": file_size,
            "page_count": page_count,
        }
        result = self.client.table("documents").insert(data).execute()
        return result.data[0]

    def get_document(self, document_id: int) -> dict | None:
        """문서 ID로 문서 정보를 조회합니다."""
        result = (
            self.client.table("documents")
            .select("*")
            .eq("id", document_id)
            .execute()
        )
        return result.data[0] if result.data else None

    def list_documents(self) -> list[dict]:
        """저장된 모든 문서 목록을 반환합니다."""
        result = (
            self.client.table("documents")
            .select("*")
            .order("created_at", desc=True)
            .execute()
        )
        return result.data

    def delete_document(self, document_id: int) -> bool:
        """문서와 관련된 모든 청크를 삭제합니다."""
        self.client.table("documents").delete().eq("id", document_id).execute()
        return True

    # ------------------------------------------------------------------
    # 청크(Chunk) 관련
    # ------------------------------------------------------------------

    def insert_chunks(
        self,
        document_id: int,
        chunks: list[dict],
    ) -> list[dict]:
        """문서 청크들을 일괄 저장합니다."""
        records = []
        for i, chunk in enumerate(chunks):
            records.append(
                {
                    "document_id": document_id,
                    "chunk_index": i,
                    "content": chunk["content"],
                    "embedding": chunk["embedding"],
                    "metadata": chunk.get("metadata", {}),
                }
            )

        batch_size = 50
        all_results = []
        for start in range(0, len(records), batch_size):
            batch = records[start : start + batch_size]
            result = self.client.table("document_chunks").insert(batch).execute()
            all_results.extend(result.data)

        return all_results

    def search_similar_chunks(
        self,
        query_embedding: list[float],
        match_threshold: float = 0.3,
        match_count: int = 5,
    ) -> list[dict]:
        """
        질문과 의미적으로 유사한 청크를 검색합니다.
        RPC 함수 호출이 실패하면 직접 쿼리로 폴백합니다.
        """
        # 임베딩을 문자열로 변환 (PostgreSQL VECTOR 타입 호환)
        embedding_str = "[" + ",".join(str(x) for x in query_embedding) + "]"

        try:
            result = self.client.rpc(
                "match_documents",
                {
                    "query_embedding": embedding_str,
                    "match_threshold": match_threshold,
                    "match_count": match_count,
                },
            ).execute()

            if result.data:
                return result.data
        except Exception:
            pass

        # RPC 실패 시 폴백: 전체 청크를 가져와서 Python에서 유사도 계산
        return self._fallback_search(query_embedding, match_threshold, match_count)

    def _fallback_search(
        self,
        query_embedding: list[float],
        threshold: float,
        limit: int,
    ) -> list[dict]:
        """
        RPC 함수가 작동하지 않을 때의 폴백 검색.
        모든 청크를 가져와 Python에서 코사인 유사도를 계산합니다.
        """
        result = (
            self.client.table("document_chunks")
            .select("id, document_id, content, metadata")
            .execute()
        )

        if not result.data:
            return []

        # 코사인 유사도 계산
        import math

        def cosine_similarity(a: list[float], b: list[float]) -> float:
            dot = sum(x * y for x, y in zip(a, b))
            norm_a = math.sqrt(sum(x * x for x in a))
            norm_b = math.sqrt(sum(x * x for x in b))
            if norm_a == 0 or norm_b == 0:
                return 0.0
            return dot / (norm_a * norm_b)

        # 각 청크의 임베딩을 가져와서 유사도 계산
        scored = []
        for chunk in result.data:
            # 청크의 임베딩을 별도로 조회
            emb_result = (
                self.client.table("document_chunks")
                .select("embedding")
                .eq("id", chunk["id"])
                .execute()
            )
            if not emb_result.data or not emb_result.data[0].get("embedding"):
                continue

            chunk_embedding = emb_result.data[0]["embedding"]
            if isinstance(chunk_embedding, str):
                chunk_embedding = [
                    float(x) for x in chunk_embedding.strip("[]").split(",")
                ]

            sim = cosine_similarity(query_embedding, chunk_embedding)
            if sim > threshold:
                scored.append({**chunk, "similarity": sim})

        scored.sort(key=lambda x: x["similarity"], reverse=True)
        return scored[:limit]

    def get_chunks_by_document(self, document_id: int) -> list[dict]:
        """특정 문서의 모든 청크를 순서대로 반환합니다."""
        result = (
            self.client.table("document_chunks")
            .select("*")
            .eq("document_id", document_id)
            .order("chunk_index")
            .execute()
        )
        return result.data

    def count_chunks(self, document_id: int | None = None) -> int:
        """청크 수를 셉니다. document_id가 None이면 전체 개수."""
        query = self.client.table("document_chunks").select("id", count="exact")
        if document_id is not None:
            query = query.eq("document_id", document_id)
        result = query.execute()
        return result.count or 0

    def get_chunk_sample(self, document_id: int, limit: int = 3) -> list[dict]:
        """특정 문서의 청크 샘플을 반환합니다 (진단용)."""
        result = (
            self.client.table("document_chunks")
            .select("id, chunk_index, content, metadata")
            .eq("document_id", document_id)
            .order("chunk_index")
            .limit(limit)
            .execute()
        )
        return result.data

    def check_embeddings_exist(self, document_id: int) -> dict:
        """문서의 임베딩 저장 상태를 확인합니다 (진단용)."""
        all_chunks = (
            self.client.table("document_chunks")
            .select("id, embedding")
            .eq("document_id", document_id)
            .execute()
        )
        total = len(all_chunks.data)
        with_embedding = sum(
            1 for c in all_chunks.data if c.get("embedding") is not None
        )
        return {
            "total_chunks": total,
            "with_embedding": with_embedding,
            "without_embedding": total - with_embedding,
        }
