"""
config.py - 프로젝트 설정 관리
================================
설정값을 두 가지 방식으로 읽습니다:
  1. Streamlit Cloud 배포 → st.secrets 에서 읽기
  2. 로컬 실행 → .env 파일에서 읽기

[초보자 안내]
- 로컬에서는 .env 파일에 API 키를 적어두면 됩니다.
- Streamlit Cloud에 배포할 때는 앱 설정 → Secrets에 입력합니다.
  코드가 알아서 둘 중 사용 가능한 곳에서 값을 가져옵니다.
"""

import os
from dotenv import load_dotenv

load_dotenv()


def _get(key: str, default: str = "") -> str:
    """Streamlit Secrets → 환경변수 순서로 설정값을 찾습니다."""
    # 1순위: Streamlit Secrets (클라우드 배포 시)
    try:
        import streamlit as st

        if key in st.secrets:
            return str(st.secrets[key])
    except Exception:
        pass

    # 2순위: 환경변수 / .env 파일 (로컬 실행 시)
    return os.getenv(key, default)


class Config:
    """모든 설정값을 한 곳에서 관리하는 클래스"""

    # --- OpenAI 설정 ---
    OPENAI_API_KEY: str = _get("OPENAI_API_KEY")

    # --- Supabase 설정 ---
    SUPABASE_URL: str = _get("SUPABASE_URL")
    SUPABASE_KEY: str = _get("SUPABASE_KEY")

    # --- 임베딩 설정 ---
    EMBEDDING_MODEL: str = _get("EMBEDDING_MODEL", "text-embedding-3-small")
    EMBEDDING_DIMENSION: int = int(_get("EMBEDDING_DIMENSION", "1536"))

    # --- 챗봇 모델 ---
    CHAT_MODEL: str = _get("CHAT_MODEL", "gpt-4o-mini")

    # --- 청크 설정 ---
    CHUNK_SIZE: int = int(_get("CHUNK_SIZE", "1000"))
    CHUNK_OVERLAP: int = int(_get("CHUNK_OVERLAP", "200"))

    # --- 파일 업로드 경로 ---
    UPLOAD_DIR: str = os.path.join(os.path.dirname(__file__), "uploads")

    @classmethod
    def validate(cls) -> list[str]:
        """필수 설정값이 모두 입력되었는지 검증합니다."""
        # 클래스 속성을 최신 값으로 갱신 (Streamlit은 런타임에 secrets가 로드됨)
        cls.OPENAI_API_KEY = _get("OPENAI_API_KEY")
        cls.SUPABASE_URL = _get("SUPABASE_URL")
        cls.SUPABASE_KEY = _get("SUPABASE_KEY")

        errors = []
        if not cls.OPENAI_API_KEY or cls.OPENAI_API_KEY.startswith("sk-여기"):
            errors.append("OPENAI_API_KEY가 설정되지 않았습니다.")
        if not cls.SUPABASE_URL or "여기에" in cls.SUPABASE_URL:
            errors.append("SUPABASE_URL이 설정되지 않았습니다.")
        if not cls.SUPABASE_KEY or "여기에" in cls.SUPABASE_KEY:
            errors.append("SUPABASE_KEY가 설정되지 않았습니다.")
        return errors
