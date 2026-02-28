"""
image_processor.py - 이미지 파일 처리기
=========================================
이미지 파일에서 텍스트를 추출합니다 (OCR).

[초보자 안내]
- OCR (Optical Character Recognition): 이미지 속 글자를 인식하여 텍스트로 변환하는 기술
- Tesseract: Google이 만든 무료 OCR 엔진
  - Windows: https://github.com/UB-Mannheim/tesseract/wiki 에서 설치
  - 설치 시 "Korean" 언어팩도 함께 선택하세요
- OpenAI Vision: 이미지를 이해하는 AI 모델 (Tesseract보다 정확하지만 API 비용 발생)

[처리 흐름]
  이미지 파일 → Tesseract OCR or OpenAI Vision → 텍스트 추출
"""

import os
import base64
import io

from PIL import Image

from config import Config


class ImageProcessor:
    """
    이미지에서 텍스트를 추출하는 프로세서

    두 가지 모드를 지원합니다:
    1. Tesseract OCR (무료, 로컬 실행, 설치 필요)
    2. OpenAI Vision API (유료, 클라우드, 더 정확)

    사용 예시:
        processor = ImageProcessor(use_vision_api=False)
        result = processor.process("스크린샷.png")
        print(result["full_text"])
    """

    def __init__(self, use_vision_api: bool = False):
        """
        Args:
            use_vision_api: True면 OpenAI Vision 사용, False면 Tesseract 사용
        """
        self.use_vision_api = use_vision_api

        if not use_vision_api:
            try:
                import pytesseract

                self.pytesseract = pytesseract
                self.tesseract_available = True
            except ImportError:
                self.tesseract_available = False
        else:
            self.tesseract_available = False

    def process(self, file_path: str) -> dict:
        """
        이미지 파일을 처리하여 텍스트를 추출합니다.

        Args:
            file_path: 이미지 파일 경로

        Returns:
            dict: {
                "filename": 파일 이름,
                "file_type": "image",
                "file_size": 파일 크기,
                "page_count": 1,
                "full_text": 추출된 텍스트,
            }
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"파일을 찾을 수 없습니다: {file_path}")

        img = Image.open(file_path)
        text = self.extract_text_from_image(img)

        return {
            "filename": os.path.basename(file_path),
            "file_type": "image",
            "file_size": os.path.getsize(file_path),
            "page_count": 1,
            "full_text": text,
        }

    def extract_text_from_image(self, image: Image.Image) -> str:
        """
        PIL Image 객체에서 텍스트를 추출합니다.
        (PDF 프로세서에서도 호출하기 위해 별도 메서드로 분리)
        """
        if self.use_vision_api:
            return self._extract_with_vision_api(image)
        elif self.tesseract_available:
            return self._extract_with_tesseract(image)
        else:
            return "[OCR 불가: Tesseract가 설치되지 않았습니다]"

    def _extract_with_tesseract(self, image: Image.Image) -> str:
        """Tesseract OCR로 텍스트 추출"""
        try:
            text = self.pytesseract.image_to_string(image, lang="kor+eng")
            return text.strip()
        except Exception as e:
            return f"[OCR 오류: {e}]"

    def _extract_with_vision_api(self, image: Image.Image) -> str:
        """OpenAI Vision API로 이미지 분석"""
        try:
            from openai import OpenAI

            client = OpenAI(api_key=Config.OPENAI_API_KEY)

            buffer = io.BytesIO()
            image_format = "PNG" if image.mode == "RGBA" else "JPEG"
            image.save(buffer, format=image_format)
            base64_image = base64.b64encode(buffer.getvalue()).decode("utf-8")
            mime_type = "image/png" if image_format == "PNG" else "image/jpeg"

            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": (
                                    "이 이미지에 포함된 모든 텍스트를 추출해 주세요. "
                                    "표가 있다면 표 형태를 유지하고, "
                                    "그래프나 차트가 있다면 내용을 설명해 주세요. "
                                    "한국어와 영어 모두 추출해 주세요."
                                ),
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:{mime_type};base64,{base64_image}"
                                },
                            },
                        ],
                    }
                ],
                max_tokens=2000,
            )
            return response.choices[0].message.content or ""
        except Exception as e:
            return f"[Vision API 오류: {e}]"
