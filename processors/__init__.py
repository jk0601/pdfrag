"""
processors 패키지
==================
다양한 파일 형식(PDF, 이미지, PPTX)에서 텍스트를 추출하는 프로세서들을 제공합니다.

[초보자 안내]
- 프로세서(processor): 파일을 읽어서 텍스트로 변환하는 역할
- 각 파일 형식마다 별도의 프로세서가 필요합니다
  (PDF를 읽는 방법과 PPTX를 읽는 방법이 다르기 때문)
"""

from processors.pdf_processor import PDFProcessor
from processors.image_processor import ImageProcessor
from processors.pptx_processor import PPTXProcessor

__all__ = ["PDFProcessor", "ImageProcessor", "PPTXProcessor"]
