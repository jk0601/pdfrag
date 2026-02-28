"""
app.py - Streamlit 웹 애플리케이션
====================================
브라우저에서 파일 업로드, 문서 관리, RAG 챗봇을 사용할 수 있는 웹 UI입니다.

[실행 방법]
  streamlit run app.py

[초보자 안내]
- Streamlit: Python 코드만으로 웹 앱을 만들 수 있는 라이브러리
- st.session_state: 페이지가 새로고침되어도 데이터를 유지하는 저장소
- st.chat_message: 챗봇 UI를 쉽게 만들어주는 컴포넌트
"""

import os
import tempfile

import streamlit as st

from config import Config
from pipeline import ingest_file, SUPPORTED_EXTENSIONS
from chatbot.chat import RAGChatbot
from database.supabase_client import SupabaseDB


# ──────────────────────────────────────────────
# 페이지 기본 설정
# ──────────────────────────────────────────────
st.set_page_config(
    page_title="PDF-RAG 문서 챗봇",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ──────────────────────────────────────────────
# 세션 상태 초기화
# ──────────────────────────────────────────────
if "chat_messages" not in st.session_state:
    st.session_state.chat_messages = []

if "chatbot" not in st.session_state:
    st.session_state.chatbot = None


def get_chatbot() -> RAGChatbot:
    """챗봇 인스턴스를 가져오거나 생성합니다."""
    if st.session_state.chatbot is None:
        st.session_state.chatbot = RAGChatbot()
    return st.session_state.chatbot


def check_config() -> list[str]:
    """설정 검증 후 오류 목록을 반환합니다."""
    return Config.validate()


# ──────────────────────────────────────────────
# 사이드바: 네비게이션 + 설정 상태
# ──────────────────────────────────────────────
with st.sidebar:
    st.title("📚 PDF-RAG")
    st.caption("문서 기반 AI 챗봇")

    st.divider()

    page = st.radio(
        "메뉴",
        ["💬 챗봇", "📤 파일 업로드", "📋 문서 관리", "⚙️ 설정"],
        label_visibility="collapsed",
    )

    st.divider()

    # 설정 상태 표시
    errors = check_config()
    if errors:
        st.error("⚠️ 설정 필요")
        for err in errors:
            st.caption(f"• {err}")
        st.caption("⚙️ 설정 페이지에서 확인하세요")
    else:
        st.success("✅ 설정 완료")

    st.divider()
    st.caption("지원 형식: PDF, 이미지, PPTX")


# ──────────────────────────────────────────────
# 페이지: 챗봇
# ──────────────────────────────────────────────
def page_chat():
    st.header("💬 문서 기반 AI 챗봇")
    st.caption("업로드된 문서를 바탕으로 질문에 답변합니다")

    errors = check_config()
    if errors:
        st.warning("먼저 ⚙️ 설정 페이지에서 API 키를 설정해 주세요.")
        return

    # DB 상태 표시
    try:
        db = SupabaseDB()
        docs = db.list_documents()
        total_chunks = db.count_chunks()
        if docs:
            doc_names = ", ".join(d["filename"] for d in docs[:5])
            extra = f" 외 {len(docs) - 5}개" if len(docs) > 5 else ""
            st.info(f"📚 로드된 문서 {len(docs)}개 ({doc_names}{extra}) · 총 {total_chunks}개 청크")
        else:
            st.warning("📭 저장된 문서가 없습니다. 먼저 📤 파일 업로드에서 문서를 추가해 주세요.")
    except Exception:
        pass

    col1, col2 = st.columns([6, 1])
    with col2:
        if st.button("🔄 대화 초기화", use_container_width=True):
            st.session_state.chat_messages = []
            chatbot = get_chatbot()
            chatbot.reset_history()
            st.rerun()

    # 이전 대화 표시
    for msg in st.session_state.chat_messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # 질문 입력
    if question := st.chat_input("문서에 대해 궁금한 것을 질문하세요..."):
        st.session_state.chat_messages.append(
            {"role": "user", "content": question}
        )
        with st.chat_message("user"):
            st.markdown(question)

        with st.chat_message("assistant"):
            chatbot = get_chatbot()
            response = st.write_stream(chatbot.stream_answer(question))

        st.session_state.chat_messages.append(
            {"role": "assistant", "content": response}
        )


# ──────────────────────────────────────────────
# 페이지: 파일 업로드
# ──────────────────────────────────────────────
def page_upload():
    st.header("📤 파일 업로드")
    st.caption("PDF, 이미지, PPTX 파일을 업로드하면 AI가 분석하여 데이터베이스에 저장합니다")

    errors = check_config()
    if errors:
        st.warning("먼저 ⚙️ 설정 페이지에서 API 키를 설정해 주세요.")
        return

    # 파일 업로더
    uploaded_files = st.file_uploader(
        "파일을 드래그하거나 클릭하여 선택하세요",
        type=["pdf", "png", "jpg", "jpeg", "gif", "bmp", "tiff", "webp", "pptx"],
        accept_multiple_files=True,
        help="지원 형식: PDF, PNG, JPG, JPEG, GIF, BMP, TIFF, WEBP, PPTX",
    )

    if not uploaded_files:
        # 안내 카드
        st.info(
            "**사용 방법**\n\n"
            "1. 위 영역에 파일을 드래그하거나 클릭하여 파일을 선택합니다\n"
            "2. 여러 파일을 한 번에 선택할 수 있습니다\n"
            "3. 아래 '처리 시작' 버튼을 눌러 DB에 저장합니다\n"
            "4. 저장이 완료되면 💬 챗봇에서 질문할 수 있습니다"
        )
        return

    # 업로드된 파일 미리보기
    st.subheader(f"📁 선택된 파일 ({len(uploaded_files)}개)")

    for f in uploaded_files:
        size_kb = f.size / 1024
        if size_kb > 1024:
            size_str = f"{size_kb / 1024:.1f} MB"
        else:
            size_str = f"{size_kb:.1f} KB"

        ext = os.path.splitext(f.name)[1].lower()
        icon = {"pdf": "📄", "pptx": "📊"}.get(ext.lstrip("."), "🖼️")
        st.text(f"  {icon}  {f.name}  ({size_str})")

    st.divider()

    # 옵션
    col1, col2 = st.columns(2)
    with col1:
        use_vision = st.checkbox(
            "🔍 OpenAI Vision으로 이미지 분석",
            value=False,
            help="이미지 내 텍스트를 더 정확하게 추출합니다 (API 비용 추가 발생)",
        )
    with col2:
        ocr_enabled = st.checkbox(
            "📝 OCR 활성화 (Tesseract)",
            value=True,
            help="이미지에서 텍스트를 추출합니다. Tesseract 설치 필요",
        )

    st.divider()

    # 처리 시작 버튼
    if st.button("🚀 처리 시작 — DB에 저장", type="primary", use_container_width=True):
        total = len(uploaded_files)
        success_count = 0
        fail_count = 0

        for idx, uploaded_file in enumerate(uploaded_files):
            st.divider()
            st.subheader(f"처리 중 ({idx + 1}/{total}): {uploaded_file.name}")

            progress_bar = st.progress(0)
            status_text = st.empty()

            def on_progress(percent: int, message: str):
                progress_bar.progress(percent)
                status_text.text(message)

            # 임시 파일로 저장 후 처리
            suffix = os.path.splitext(uploaded_file.name)[1]
            with tempfile.NamedTemporaryFile(
                delete=False, suffix=suffix
            ) as tmp:
                tmp.write(uploaded_file.getbuffer())
                tmp_path = tmp.name

            try:
                result = ingest_file(
                    tmp_path,
                    ocr_enabled=ocr_enabled,
                    use_vision_api=use_vision,
                    on_progress=on_progress,
                )

                if "error" in result:
                    st.error(f"❌ 실패: {result['error']}")
                    fail_count += 1
                else:
                    st.success(
                        f"✅ **{uploaded_file.name}** 처리 완료!  \n"
                        f"문서 ID: `{result['document_id']}` · "
                        f"청크: {result['chunk_count']}개 · "
                        f"텍스트: {result.get('text_length', 0):,}자"
                    )
                    success_count += 1
            except Exception as e:
                st.error(f"❌ 오류 발생: {e}")
                fail_count += 1
            finally:
                os.unlink(tmp_path)

        st.divider()
        if success_count > 0:
            st.balloons()
        st.info(
            f"**처리 완료** — 성공: {success_count}개, 실패: {fail_count}개  \n"
            f"💬 챗봇 페이지에서 업로드한 문서에 대해 질문해 보세요!"
        )


# ──────────────────────────────────────────────
# 페이지: 문서 관리
# ──────────────────────────────────────────────
def page_documents():
    st.header("📋 문서 관리")
    st.caption("저장된 문서를 조회하고 삭제할 수 있습니다")

    errors = check_config()
    if errors:
        st.warning("먼저 ⚙️ 설정 페이지에서 API 키를 설정해 주세요.")
        return

    if st.button("🔄 새로고침"):
        st.rerun()

    try:
        db = SupabaseDB()
        documents = db.list_documents()
    except Exception as e:
        st.error(f"데이터베이스 연결 오류: {e}")
        return

    if not documents:
        st.info(
            "📭 저장된 문서가 없습니다.  \n"
            "📤 파일 업로드 페이지에서 문서를 추가해 보세요."
        )
        return

    st.write(f"총 **{len(documents)}개**의 문서가 저장되어 있습니다.")

    for doc in documents:
        size = doc.get("file_size", 0)
        if size > 1_000_000:
            size_str = f"{size / 1_000_000:.1f} MB"
        elif size > 1_000:
            size_str = f"{size / 1_000:.1f} KB"
        else:
            size_str = f"{size} B"

        file_type = doc.get("file_type", "")
        icon = {"pdf": "📄", "pptx": "📊", "image": "🖼️"}.get(file_type, "📁")
        created = doc.get("created_at", "")[:19].replace("T", " ")

        with st.container(border=True):
            col1, col2, col3, col4 = st.columns([5, 2, 1, 1])

            with col1:
                st.markdown(f"**{icon} {doc['filename']}**")
                chunk_count = db.count_chunks(doc["id"])
                st.caption(
                    f"ID: {doc['id']} · "
                    f"종류: {file_type.upper()} · "
                    f"크기: {size_str} · "
                    f"페이지: {doc.get('page_count', '-')} · "
                    f"청크: {chunk_count}개"
                )

            with col2:
                st.caption(f"📅 {created}")

            with col3:
                if st.button("🔍", key=f"diag_{doc['id']}", help="진단 정보 보기"):
                    st.session_state[f"show_diag_{doc['id']}"] = True

            with col4:
                if st.button("🗑️", key=f"del_{doc['id']}", help="이 문서 삭제"):
                    db.delete_document(doc["id"])
                    st.success(f"'{doc['filename']}' 삭제 완료!")
                    st.rerun()

            # 진단 정보 표시
            if st.session_state.get(f"show_diag_{doc['id']}", False):
                with st.expander("🔍 진단 정보", expanded=True):
                    emb_status = db.check_embeddings_exist(doc["id"])
                    st.write(
                        f"- 전체 청크: **{emb_status['total_chunks']}개**\n"
                        f"- 임베딩 있음: **{emb_status['with_embedding']}개**\n"
                        f"- 임베딩 없음: **{emb_status['without_embedding']}개**"
                    )

                    if emb_status["without_embedding"] > 0:
                        st.warning("⚠️ 임베딩이 없는 청크가 있습니다. 문서를 삭제 후 다시 업로드해 주세요.")

                    samples = db.get_chunk_sample(doc["id"], limit=3)
                    if samples:
                        st.write("**청크 샘플 (처음 3개):**")
                        for s in samples:
                            preview = s["content"][:200] + "..." if len(s["content"]) > 200 else s["content"]
                            st.text(f"[청크 {s['chunk_index']}] {preview}")

                    if st.button("닫기", key=f"close_diag_{doc['id']}"):
                        st.session_state[f"show_diag_{doc['id']}"] = False
                        st.rerun()


# ──────────────────────────────────────────────
# 페이지: 설정
# ──────────────────────────────────────────────
def page_settings():
    st.header("⚙️ 설정 확인")
    st.caption("프로젝트 설정 상태를 확인합니다")

    errors = check_config()

    if errors:
        st.error("❌ 아래 설정을 완료해 주세요:")
        for err in errors:
            st.markdown(f"- {err}")

        st.divider()
        st.subheader("📝 설정 방법")
        st.markdown(
            "1. 프로젝트 폴더의 `.env.example` 파일을 `.env`로 복사합니다\n"
            "2. `.env` 파일을 열어 실제 API 키를 입력합니다\n"
            "3. 이 페이지를 새로고침합니다"
        )

        with st.expander("📄 .env 파일 예시"):
            st.code(
                "OPENAI_API_KEY=sk-실제API키\n"
                "SUPABASE_URL=https://프로젝트.supabase.co\n"
                "SUPABASE_KEY=실제anon키\n",
                language="bash",
            )
    else:
        st.success("✅ 모든 설정이 정상입니다!")

    st.divider()
    st.subheader("현재 설정값")

    col1, col2 = st.columns(2)
    with col1:
        st.metric("임베딩 모델", Config.EMBEDDING_MODEL)
        st.metric("임베딩 차원", Config.EMBEDDING_DIMENSION)
        st.metric("챗봇 모델", Config.CHAT_MODEL)
    with col2:
        st.metric("청크 크기", f"{Config.CHUNK_SIZE}자")
        st.metric("청크 겹침", f"{Config.CHUNK_OVERLAP}자")
        supabase_display = Config.SUPABASE_URL[:35] + "..." if Config.SUPABASE_URL else "미설정"
        st.metric("Supabase URL", supabase_display)

    st.divider()
    st.subheader("🗄️ 데이터베이스 스키마")
    st.markdown(
        "`database/schema.sql` 파일을 Supabase SQL Editor에서 실행해야 합니다.  \n"
        "이 SQL은 문서 테이블, 청크 테이블, 벡터 검색 함수를 생성합니다."
    )

    if st.button("📋 schema.sql 내용 보기"):
        try:
            schema_path = os.path.join(os.path.dirname(__file__), "database", "schema.sql")
            with open(schema_path, "r", encoding="utf-8") as f:
                st.code(f.read(), language="sql")
        except FileNotFoundError:
            st.error("schema.sql 파일을 찾을 수 없습니다.")


# ──────────────────────────────────────────────
# 라우팅: 선택된 페이지 렌더링
# ──────────────────────────────────────────────
if page == "💬 챗봇":
    page_chat()
elif page == "📤 파일 업로드":
    page_upload()
elif page == "📋 문서 관리":
    page_documents()
elif page == "⚙️ 설정":
    page_settings()
