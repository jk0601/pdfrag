"""
pipeline.py - 문서 처리 파이프라인
====================================
파일 업로드부터 Supabase 저장까지의 전체 흐름을 관리합니다.
CLI(main.py)와 웹(app.py) 모두에서 사용할 수 있도록 콜백 방식으로 설계되었습니다.

[처리 흐름]
  파일 읽기 → 텍스트 추출 → 청크 분할 → 임베딩 생성 → DB 저장
"""

import os
from typing import Callable

from config import Config
from processors.pdf_processor import PDFProcessor
from processors.image_processor import ImageProcessor
from processors.pptx_processor import PPTXProcessor
from rag.chunker import SemanticChunker
from rag.embedder import Embedder
from database.supabase_client import SupabaseDB

# 파일 확장자별 지원 형식
SUPPORTED_EXTENSIONS = {
    ".pdf": "pdf",
    ".png": "image",
    ".jpg": "image",
    ".jpeg": "image",
    ".gif": "image",
    ".bmp": "image",
    ".tiff": "image",
    ".webp": "image",
    ".pptx": "pptx",
}


def get_file_type(file_path: str) -> str | None:
    """파일 확장자로 파일 종류를 판별합니다."""
    ext = os.path.splitext(file_path)[1].lower()
    return SUPPORTED_EXTENSIONS.get(ext)


def process_file(
    file_path: str,
    ocr_enabled: bool = True,
    use_vision_api: bool = False,
) -> dict:
    """파일을 읽어서 텍스트를 추출합니다."""
    file_type = get_file_type(file_path)

    if file_type is None:
        ext = os.path.splitext(file_path)[1]
        raise ValueError(
            f"지원하지 않는 파일 형식입니다: {ext}\n"
            f"지원 형식: {', '.join(SUPPORTED_EXTENSIONS.keys())}"
        )

    if file_type == "pdf":
        processor = PDFProcessor(ocr_enabled=ocr_enabled)
    elif file_type == "image":
        processor = ImageProcessor(use_vision_api=use_vision_api)
    elif file_type == "pptx":
        processor = PPTXProcessor(ocr_enabled=ocr_enabled)
    else:
        raise ValueError(f"알 수 없는 파일 유형: {file_type}")

    return processor.process(file_path)


def ingest_file(
    file_path: str,
    ocr_enabled: bool = True,
    use_vision_api: bool = False,
    on_progress: Callable[[int, str], None] | None = None,
) -> dict:
    """
    파일을 처리하고 Supabase에 저장하는 전체 파이프라인을 실행합니다.

    Args:
        file_path: 처리할 파일 경로
        ocr_enabled: OCR 활성화 여부
        use_vision_api: OpenAI Vision 사용 여부
        on_progress: 진행률 콜백 함수 (percent: 0~100, message: 상태 메시지)
                     None이면 진행률을 출력하지 않습니다.

    Returns:
        처리 결과 딕셔너리
    """
    file_path = os.path.abspath(file_path)

    def report(percent: int, message: str):
        if on_progress:
            on_progress(percent, message)

    # --- 1단계: 텍스트 추출 ---
    report(5, "📄 파일에서 텍스트를 추출하는 중...")
    result = process_file(file_path, ocr_enabled, use_vision_api)
    full_text = result.get("full_text", "")

    if not full_text.strip():
        return {"error": "파일에서 텍스트를 추출할 수 없습니다."}

    report(
        25,
        f"✅ 텍스트 추출 완료 — {len(full_text):,}자, "
        f"{result.get('page_count', 1)}페이지",
    )

    # --- 2단계: 청크 분할 ---
    report(30, "✂️ 텍스트를 청크(조각)로 분할하는 중...")
    chunker = SemanticChunker()
    base_metadata = {
        "filename": result["filename"],
        "file_type": result["file_type"],
    }

    if result["file_type"] == "pdf" and "pages" in result:
        pages_data = [
            {"page_number": p.page_number, "text": p.full_text}
            for p in result["pages"]
        ]
        chunks = chunker.split_pages(pages_data, base_metadata=base_metadata)
    else:
        chunks = chunker.split_text(full_text, metadata=base_metadata)

    if not chunks:
        return {"error": "텍스트를 청크로 분할할 수 없습니다."}

    report(50, f"✅ {len(chunks)}개의 청크로 분할 완료")

    # --- 3단계: 임베딩 생성 ---
    report(55, f"🧠 {len(chunks)}개 청크의 임베딩 벡터를 생성하는 중...")
    embedder = Embedder()
    chunk_texts = [c.content for c in chunks]
    embeddings = embedder.embed_texts(chunk_texts)
    report(80, f"✅ {len(embeddings)}개의 임베딩 생성 완료")

    # --- 4단계: Supabase 저장 ---
    report(85, "💾 Supabase 데이터베이스에 저장하는 중...")
    db = SupabaseDB()

    doc_record = db.insert_document(
        filename=result["filename"],
        file_type=result["file_type"],
        file_size=result["file_size"],
        page_count=result.get("page_count"),
    )

    chunk_data = []
    for chunk, embedding in zip(chunks, embeddings):
        chunk_data.append(
            {
                "content": chunk.content,
                "embedding": embedding,
                "metadata": chunk.metadata,
            }
        )

    db.insert_chunks(doc_record["id"], chunk_data)
    report(100, "✅ 데이터베이스 저장 완료!")

    return {
        "document_id": doc_record["id"],
        "filename": result["filename"],
        "chunk_count": len(chunks),
        "file_type": result["file_type"],
        "text_length": len(full_text),
        "page_count": result.get("page_count", 1),
    }
