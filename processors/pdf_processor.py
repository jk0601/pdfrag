"""
pdf_processor.py - PDF 파일 처리기
====================================
PDF 파일에서 텍스트와 이미지를 추출합니다.

[초보자 안내]
- PyMuPDF(fitz): PDF 파일을 읽고 분석하는 강력한 Python 라이브러리
- PDF 안에는 텍스트뿐만 아니라 이미지, 표 등도 포함될 수 있습니다
- 이 프로세서는:
  1. 각 페이지의 텍스트를 추출하고
  2. 페이지 안의 이미지도 추출하여 OCR로 텍스트화합니다

[처리 흐름]
  PDF 파일 → 페이지별 텍스트 추출 → 이미지 내 텍스트 OCR → 결합
"""

import os
import io
from dataclasses import dataclass, field

import fitz  # PyMuPDF
from PIL import Image

from processors.image_processor import ImageProcessor


@dataclass
class PageContent:
    """한 페이지에서 추출된 내용을 담는 데이터 클래스"""

    page_number: int
    text: str
    has_images: bool = False
    image_texts: list[str] = field(default_factory=list)

    @property
    def full_text(self) -> str:
        """텍스트와 이미지 텍스트를 합친 전체 내용"""
        parts = [self.text]
        for img_text in self.image_texts:
            if img_text.strip():
                parts.append(f"\n[이미지 내용]: {img_text}")
        return "\n".join(parts)


class PDFProcessor:
    """
    PDF 파일에서 텍스트와 이미지를 추출하는 프로세서

    사용 예시:
        processor = PDFProcessor()
        result = processor.process("보고서.pdf")
        print(result["full_text"])
    """

    def __init__(self, ocr_enabled: bool = True):
        """
        Args:
            ocr_enabled: 이미지 OCR 활성화 여부 (기본: True)
                        Tesseract가 설치되지 않은 경우 False로 설정
        """
        self.ocr_enabled = ocr_enabled
        self.image_processor = ImageProcessor() if ocr_enabled else None

    def process(self, file_path: str) -> dict:
        """
        PDF 파일을 처리하여 텍스트를 추출합니다.

        Args:
            file_path: PDF 파일 경로

        Returns:
            dict: {
                "filename": 파일 이름,
                "file_type": "pdf",
                "file_size": 파일 크기,
                "page_count": 페이지 수,
                "pages": [PageContent, ...],  # 페이지별 내용
                "full_text": 전체 텍스트,
            }
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"파일을 찾을 수 없습니다: {file_path}")

        doc = fitz.open(file_path)
        pages: list[PageContent] = []

        for page_num in range(len(doc)):
            page = doc[page_num]
            page_content = self._extract_page(page, page_num + 1)
            pages.append(page_content)

        doc.close()

        full_text = "\n\n".join(
            f"--- 페이지 {p.page_number} ---\n{p.full_text}" for p in pages
        )

        file_size = os.path.getsize(file_path)

        return {
            "filename": os.path.basename(file_path),
            "file_type": "pdf",
            "file_size": file_size,
            "page_count": len(pages),
            "pages": pages,
            "full_text": full_text,
        }

    def _extract_page(self, page: fitz.Page, page_number: int) -> PageContent:
        """한 페이지에서 텍스트와 이미지를 추출합니다."""
        text = page.get_text("text")
        image_texts = []
        has_images = False

        if self.ocr_enabled and self.image_processor:
            image_list = page.get_images(full=True)
            if image_list:
                has_images = True
                doc = page.parent
                for img_info in image_list:
                    try:
                        xref = img_info[0]
                        base_image = doc.extract_image(xref)
                        image_bytes = base_image["image"]
                        img = Image.open(io.BytesIO(image_bytes))
                        img_text = self.image_processor.extract_text_from_image(img)
                        if img_text.strip():
                            image_texts.append(img_text)
                    except Exception:
                        continue

        return PageContent(
            page_number=page_number,
            text=text.strip(),
            has_images=has_images,
            image_texts=image_texts,
        )
