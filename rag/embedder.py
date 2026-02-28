"""
embedder.py - 텍스트 임베딩 생성기
=====================================
텍스트를 숫자 벡터(임베딩)로 변환합니다.

[초보자 안내]
임베딩(Embedding)이란?
- 텍스트의 '의미'를 숫자 배열로 표현한 것
- 예: "고양이" → [0.23, -0.45, 0.67, ...] (1536개의 숫자)
- 의미가 비슷한 텍스트는 비슷한 숫자 배열을 가짐
  "고양이"와 "강아지" → 벡터가 비슷 (가까움)
  "고양이"와 "자동차" → 벡터가 다름 (멀리)

왜 임베딩이 필요할까?
- 컴퓨터는 텍스트를 직접 비교하기 어렵습니다
- 숫자로 바꾸면 수학적으로 "얼마나 비슷한지" 계산할 수 있습니다
- 이를 통해 "질문과 가장 관련 있는 문서 조각"을 찾을 수 있습니다

모델 선택:
- text-embedding-3-small: 빠르고 저렴, 대부분의 용도에 충분
- text-embedding-3-large: 더 정확하지만 비용이 높음
"""

from openai import OpenAI

from config import Config


class Embedder:
    """
    OpenAI API를 사용하여 텍스트를 임베딩 벡터로 변환하는 클래스

    사용 예시:
        embedder = Embedder()
        vector = embedder.embed_text("안녕하세요")
        vectors = embedder.embed_texts(["텍스트1", "텍스트2"])
    """

    def __init__(self):
        self.client = OpenAI(api_key=Config.OPENAI_API_KEY)
        self.model = Config.EMBEDDING_MODEL
        self.dimension = Config.EMBEDDING_DIMENSION

    def embed_text(self, text: str) -> list[float]:
        """
        하나의 텍스트를 임베딩 벡터로 변환합니다.

        Args:
            text: 변환할 텍스트

        Returns:
            임베딩 벡터 (float 리스트, 길이 = EMBEDDING_DIMENSION)
        """
        text = text.replace("\n", " ").strip()
        if not text:
            return [0.0] * self.dimension

        response = self.client.embeddings.create(
            input=text,
            model=self.model,
            dimensions=self.dimension,
        )
        return response.data[0].embedding

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """
        여러 텍스트를 한 번에 임베딩 벡터로 변환합니다.

        OpenAI API는 한 번의 호출로 여러 텍스트를 처리할 수 있어서
        하나씩 보내는 것보다 훨씬 빠르고 효율적입니다.

        Args:
            texts: 변환할 텍스트 리스트

        Returns:
            임베딩 벡터 리스트
        """
        cleaned = [t.replace("\n", " ").strip() for t in texts]
        # 빈 텍스트는 제외하고 처리
        non_empty_indices = [i for i, t in enumerate(cleaned) if t]
        non_empty_texts = [cleaned[i] for i in non_empty_indices]

        if not non_empty_texts:
            return [[0.0] * self.dimension] * len(texts)

        # OpenAI API는 한 번에 최대 2048개까지 처리 가능
        # 안전하게 100개씩 나누어 처리합니다
        all_embeddings: dict[int, list[float]] = {}
        batch_size = 100

        for start in range(0, len(non_empty_texts), batch_size):
            batch_texts = non_empty_texts[start : start + batch_size]
            batch_indices = non_empty_indices[start : start + batch_size]

            response = self.client.embeddings.create(
                input=batch_texts,
                model=self.model,
                dimensions=self.dimension,
            )

            for j, emb_data in enumerate(response.data):
                original_index = batch_indices[j]
                all_embeddings[original_index] = emb_data.embedding

        # 결과 조합: 빈 텍스트는 영벡터로 채움
        result = []
        for i in range(len(texts)):
            if i in all_embeddings:
                result.append(all_embeddings[i])
            else:
                result.append([0.0] * self.dimension)

        return result
