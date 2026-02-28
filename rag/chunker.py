"""
chunker.py - 문서 텍스트 분할기
=================================
긴 문서 텍스트를 RAG에 적합한 크기의 청크(조각)로 나눕니다.

[초보자 안내]
왜 문서를 나눠야 할까?
- AI 모델에 한 번에 보낼 수 있는 텍스트 양에 제한이 있습니다
- 너무 긴 텍스트를 보내면 비용도 많이 들고, 정확도도 떨어집니다
- 작은 조각으로 나누면 질문과 관련된 부분만 정확히 찾을 수 있습니다

청킹 전략:
1. 고정 크기 분할: 단순히 N자마다 자르기 (가장 기본)
2. 재귀적 분할: 문단 → 문장 → 단어 순서로 자연스럽게 나누기 (우리가 사용)
3. 시맨틱 분할: 의미 단위로 나누기 (고급, 임베딩 비용 추가 발생)

overlap(겹침)이란?
- 청크 사이에 일부 텍스트를 겹치게 하는 것
- 예: "A B C | C D E | E F G" (C, E가 겹침)
- 겹침이 없으면 청크 경계에서 맥락이 끊어질 수 있습니다
"""

from dataclasses import dataclass

from langchain_text_splitters import RecursiveCharacterTextSplitter

from config import Config


@dataclass
class Chunk:
    """하나의 청크(텍스트 조각)를 나타내는 데이터 클래스"""

    content: str
    metadata: dict

    def __repr__(self) -> str:
        preview = self.content[:50] + "..." if len(self.content) > 50 else self.content
        return f"Chunk(len={len(self.content)}, preview='{preview}')"


class SemanticChunker:
    """
    문서 텍스트를 의미 있는 청크로 분할하는 클래스

    LangChain의 RecursiveCharacterTextSplitter를 사용하여
    자연스러운 경계(문단, 문장, 단어)에서 텍스트를 나눕니다.

    사용 예시:
        chunker = SemanticChunker()
        chunks = chunker.split_text(
            "아주 긴 문서 텍스트...",
            metadata={"source": "보고서.pdf", "page": 1}
        )
    """

    def __init__(
        self,
        chunk_size: int | None = None,
        chunk_overlap: int | None = None,
    ):
        """
        Args:
            chunk_size: 청크 최대 크기 (글자 수). None이면 config에서 가져옴
            chunk_overlap: 청크 간 겹침 크기. None이면 config에서 가져옴
        """
        self.chunk_size = chunk_size or Config.CHUNK_SIZE
        self.chunk_overlap = chunk_overlap or Config.CHUNK_OVERLAP

        # RecursiveCharacterTextSplitter가 텍스트를 나누는 순서:
        # 1. "\n\n" (빈 줄, 문단 경계) → 가장 자연스러운 분할
        # 2. "\n" (줄바꿈)
        # 3. ". " (마침표+공백, 문장 경계)
        # 4. " " (공백, 단어 경계)
        # 5. "" (글자 단위, 최후의 수단)
        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
            separators=["\n\n", "\n", ". ", " ", ""],
            length_function=len,
        )

    def split_text(
        self,
        text: str,
        metadata: dict | None = None,
    ) -> list[Chunk]:
        """
        텍스트를 청크로 분할합니다.

        Args:
            text: 분할할 텍스트
            metadata: 모든 청크에 공통으로 붙일 메타데이터

        Returns:
            Chunk 객체 리스트
        """
        if not text or not text.strip():
            return []

        base_metadata = metadata or {}
        documents = self.splitter.create_documents(
            [text],
            metadatas=[base_metadata],
        )

        chunks = []
        for i, doc in enumerate(documents):
            chunk_metadata = {**doc.metadata, "chunk_index": i}
            chunks.append(
                Chunk(content=doc.page_content, metadata=chunk_metadata)
            )

        return chunks

    def split_pages(
        self,
        pages: list[dict],
        base_metadata: dict | None = None,
    ) -> list[Chunk]:
        """
        페이지별로 나뉜 텍스트를 청크로 분할합니다.
        페이지 번호 정보를 메타데이터에 포함시킵니다.

        Args:
            pages: [{"page_number": 1, "text": "..."}, ...] 형태의 리스트
            base_metadata: 공통 메타데이터

        Returns:
            Chunk 객체 리스트
        """
        all_chunks: list[Chunk] = []
        base = base_metadata or {}

        for page in pages:
            page_meta = {**base, "page_number": page.get("page_number", 0)}
            page_text = page.get("text", "")
            if page_text.strip():
                chunks = self.split_text(page_text, metadata=page_meta)
                all_chunks.extend(chunks)

        # 전체 청크에 대해 인덱스 재정렬
        for i, chunk in enumerate(all_chunks):
            chunk.metadata["chunk_index"] = i

        return all_chunks
