"""
retriever.py - 문서 검색기
============================
사용자의 질문과 가장 관련 있는 문서 조각을 찾아주는 모듈입니다.

[초보자 안내]
검색(Retrieval) 과정:
1. 사용자가 질문을 입력합니다
   예: "2024년 매출은 얼마인가요?"

2. 질문을 임베딩 벡터로 변환합니다
   "2024년 매출은 얼마인가요?" → [0.12, -0.34, ...]

3. DB에 저장된 모든 청크의 임베딩과 코사인 유사도를 비교합니다
   코사인 유사도: 두 벡터가 같은 방향을 가리키는 정도 (0~1)
   1에 가까울수록 의미가 비슷

4. 유사도가 높은 상위 N개의 청크를 반환합니다
"""

from database.supabase_client import SupabaseDB
from rag.embedder import Embedder


class Retriever:
    """
    질문과 관련된 문서 청크를 검색하는 클래스

    사용 예시:
        retriever = Retriever()
        results = retriever.search("2024년 매출은?")
        for r in results:
            print(r["content"], r["similarity"])
    """

    def __init__(self):
        self.db = SupabaseDB()
        self.embedder = Embedder()

    def search(
        self,
        query: str,
        top_k: int = 5,
        threshold: float = 0.2,
    ) -> list[dict]:
        """
        질문과 유사한 문서 청크를 검색합니다.

        Args:
            query: 사용자 질문
            top_k: 반환할 최대 결과 수
            threshold: 최소 유사도 임계값 (0~1)

        Returns:
            검색 결과 리스트. 각 항목:
            {
                "id": 청크 ID,
                "document_id": 문서 ID,
                "content": 청크 텍스트,
                "metadata": 메타데이터,
                "similarity": 유사도 점수,
            }
        """
        query_embedding = self.embedder.embed_text(query)

        results = self.db.search_similar_chunks(
            query_embedding=query_embedding,
            match_threshold=threshold,
            match_count=top_k,
        )

        return results

    def search_with_context(
        self,
        query: str,
        top_k: int = 5,
        threshold: float = 0.2,
    ) -> str:
        """
        검색 결과를 AI 모델에 전달하기 좋은 형태의 텍스트로 변환합니다.

        Returns:
            컨텍스트 문자열 (AI 프롬프트에 삽입할 용도)
        """
        results = self.search(query, top_k, threshold)

        if not results:
            return "관련 문서를 찾을 수 없습니다."

        context_parts = []
        for i, result in enumerate(results, 1):
            similarity_pct = round(result["similarity"] * 100, 1)
            metadata = result.get("metadata", {})
            source_info = ""
            if "filename" in metadata:
                source_info += f" (출처: {metadata['filename']}"
                if "page_number" in metadata:
                    source_info += f", {metadata['page_number']}페이지"
                source_info += ")"

            context_parts.append(
                f"[참고자료 {i}]{source_info} (유사도: {similarity_pct}%)\n"
                f"{result['content']}"
            )

        return "\n\n---\n\n".join(context_parts)
