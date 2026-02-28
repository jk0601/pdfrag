"""
rag 패키지
===========
RAG(Retrieval-Augmented Generation) 파이프라인의 핵심 모듈들을 제공합니다.

[초보자 안내]
RAG란?
- Retrieval: 질문과 관련된 문서 조각을 '검색'하고
- Augmented: 그 조각들을 AI 모델의 입력에 '추가'하여
- Generation: 정확한 답변을 '생성'하는 기술

왜 RAG가 필요할까?
- AI 모델은 학습 데이터에 없는 정보(예: 회사 내부 문서)를 모릅니다
- RAG를 사용하면 우리의 문서를 AI가 참고하여 답변할 수 있습니다

RAG 파이프라인 3단계:
1. 청킹(Chunking): 긴 문서를 적절한 크기로 나누기
2. 임베딩(Embedding): 텍스트를 숫자 벡터로 변환하기
3. 검색(Retrieval): 질문과 유사한 문서 조각 찾기
"""

from rag.chunker import SemanticChunker
from rag.embedder import Embedder
from rag.retriever import Retriever

__all__ = ["SemanticChunker", "Embedder", "Retriever"]
