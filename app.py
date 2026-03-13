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
import json
import csv
import io
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
# 비밀번호 인증
# ──────────────────────────────────────────────
def check_password() -> bool:
    """비밀번호 확인. Secrets에 APP_PASSWORD가 없으면 인증 없이 통과."""
    try:
        password = st.secrets.get("APP_PASSWORD", "")
    except Exception:
        password = os.getenv("APP_PASSWORD", "")

    if not password:
        return True

    if st.session_state.get("authenticated"):
        return True

    st.markdown(
        "<h1 style='text-align:center; margin-top:80px'>📚 PDF-RAG 문서 챗봇</h1>"
        "<p style='text-align:center; color:gray'>접근하려면 비밀번호를 입력하세요</p>",
        unsafe_allow_html=True,
    )

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        with st.form("login_form"):
            pw_input = st.text_input("비밀번호", type="password", placeholder="비밀번호 입력")
            submitted = st.form_submit_button("로그인", use_container_width=True, type="primary")

            if submitted:
                if pw_input == password:
                    st.session_state.authenticated = True
                    st.rerun()
                else:
                    st.error("❌ 비밀번호가 틀렸습니다.")

    return False


if not check_password():
    st.stop()


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
        ["💬 챗봇", "📤 파일 업로드", "📋 문서 관리", "📥 데이터 내보내기", "⚙️ 설정"],
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

    # --- 사이드바: 챗봇 설정 슬라이더 ---
    with st.sidebar:
        st.divider()
        st.subheader("🎛️ 챗봇 설정")

        top_k = st.slider(
            "참고 청크 수 (top_k)",
            min_value=1, max_value=20, value=5,
            help="질문에 답할 때 참고할 문서 조각 수. 높을수록 더 많은 내용을 참고하지만 비용 증가",
        )
        threshold = st.slider(
            "유사도 임계값",
            min_value=0.0, max_value=1.0, value=0.2, step=0.05,
            help="0에 가까울수록 느슨하게 검색, 1에 가까울수록 엄격하게 검색",
        )

        st.caption(
            f"📊 예상 참고량: 약 {top_k * Config.CHUNK_SIZE:,}자\n\n"
            f"- 참고 청크 수 ↑ → 넓고 상세한 답변\n"
            f"- 유사도 임계값 ↑ → 관련성 높은 것만"
        )

    # 설정이 변경되면 챗봇 인스턴스 갱신
    chatbot = get_chatbot()
    if chatbot.top_k != top_k or chatbot.threshold != threshold:
        chatbot.top_k = top_k
        chatbot.threshold = threshold

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
# 페이지: 데이터 내보내기
# ──────────────────────────────────────────────
def page_export():
    st.header("📥 데이터 내보내기")
    st.caption("RAG 처리된 데이터를 다운로드하여 다른 데이터베이스에 넣을 수 있습니다")

    errors = check_config()
    if errors:
        st.warning("먼저 ⚙️ 설정 페이지에서 API 키를 설정해 주세요.")
        return

    try:
        db = SupabaseDB()
        documents = db.list_documents()
    except Exception as e:
        st.error(f"데이터베이스 연결 오류: {e}")
        return

    if not documents:
        st.info("📭 저장된 문서가 없습니다.")
        return

    # --- 문서 선택 ---
    st.subheader("1. 내보낼 문서 선택")

    doc_options = {"📚 전체 문서": None}
    for doc in documents:
        chunk_count = db.count_chunks(doc["id"])
        label = f"{doc['filename']} ({chunk_count}청크)"
        doc_options[label] = doc["id"]

    selected_label = st.selectbox("문서 선택", list(doc_options.keys()))
    selected_doc_id = doc_options[selected_label]

    # --- 옵션 ---
    st.subheader("2. 내보내기 옵션")

    col1, col2 = st.columns(2)
    with col1:
        export_format = st.radio("파일 형식", ["CSV", "JSON", "SQL (INSERT문)"])
    with col2:
        include_embedding = st.checkbox(
            "임베딩 벡터 포함",
            value=False,
            help="벡터 DB로 마이그레이션할 때 필요. 파일 용량이 매우 커집니다.",
        )
        include_metadata = st.checkbox("메타데이터 펼치기", value=True,
            help="metadata JSON을 개별 컬럼으로 분리합니다.")

    st.divider()

    # --- 미리보기 ---
    st.subheader("3. 미리보기")

    chunks = db.export_chunks(document_id=selected_doc_id, include_embedding=include_embedding)

    if not chunks:
        st.warning("내보낼 데이터가 없습니다.")
        return

    # 미리보기용 데이터 가공
    preview_data = []
    for c in chunks[:5]:
        row = {
            "chunk_id": c["id"],
            "document_id": c["document_id"],
            "chunk_index": c["chunk_index"],
            "content": c["content"][:100] + "..." if len(c["content"]) > 100 else c["content"],
        }
        if include_metadata and c.get("metadata"):
            meta = c["metadata"] if isinstance(c["metadata"], dict) else {}
            row["filename"] = meta.get("filename", "")
            row["file_type"] = meta.get("file_type", "")
            row["page_number"] = meta.get("page_number", "")
        if include_embedding:
            emb = c.get("embedding")
            if emb:
                row["embedding"] = f"[{len(emb) if isinstance(emb, list) else '?'}차원 벡터]"
        preview_data.append(row)

    st.dataframe(preview_data, use_container_width=True)
    st.caption(f"총 {len(chunks)}개 청크 중 상위 5개 미리보기")

    st.divider()

    # --- 다운로드 ---
    st.subheader("4. 다운로드")

    # 내보내기용 전체 데이터 가공
    # DB 스키마와 필드 순서/이름 일치 (chunk_id, document_id, chunk_index, content, filename, file_type, page_number, created_at, embedding)
    CSV_FIELDS = ["chunk_id", "document_id", "chunk_index", "content", "filename", "file_type", "page_number", "created_at", "embedding"]
    export_rows = []
    for c in chunks:
        meta = c.get("metadata") or {}
        if not isinstance(meta, dict):
            meta = {}
        row = {
            "chunk_id": c["id"],
            "document_id": c["document_id"],
            "chunk_index": c["chunk_index"],
            "content": c["content"],
            "filename": meta.get("filename", ""),
            "file_type": meta.get("file_type", ""),
            "page_number": meta.get("page_number", ""),
            "created_at": c.get("created_at", ""),
            "embedding": "",
        }
        if include_embedding and c.get("embedding"):
            emb = c["embedding"]
            row["embedding"] = json.dumps(emb) if isinstance(emb, list) else str(emb)
        export_rows.append(row)

    file_suffix = f"_{documents[0]['filename'].split('.')[0]}" if selected_doc_id else "_all"

    if export_format == "CSV":
        output = io.StringIO()
        if export_rows:
            writer = csv.DictWriter(output, fieldnames=CSV_FIELDS, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(export_rows)
        csv_data = "\ufeff" + output.getvalue()  # UTF-8 BOM: Excel에서 한글 정상 표시

        st.download_button(
            label=f"⬇️ CSV 다운로드 ({len(export_rows)}행)",
            data=csv_data,
            file_name=f"rag_chunks{file_suffix}.csv",
            mime="text/csv",
            type="primary",
            use_container_width=True,
        )

    elif export_format == "JSON":
        json_data = json.dumps(export_rows, ensure_ascii=False, indent=2)

        st.download_button(
            label=f"⬇️ JSON 다운로드 ({len(export_rows)}행)",
            data=json_data,
            file_name=f"rag_chunks{file_suffix}.json",
            mime="application/json",
            type="primary",
            use_container_width=True,
        )

    elif export_format == "SQL (INSERT문)":
        sql_lines = []
        table_name = "document_chunks"
        for row in export_rows:
            cols = list(row.keys())
            vals = []
            for v in row.values():
                if v is None:
                    vals.append("NULL")
                elif isinstance(v, (int, float)):
                    vals.append(str(v))
                else:
                    escaped = str(v).replace("'", "''")
                    vals.append(f"'{escaped}'")
            sql_lines.append(
                f"INSERT INTO {table_name} ({', '.join(cols)}) VALUES ({', '.join(vals)});"
            )
        sql_data = "\n".join(sql_lines)

        st.download_button(
            label=f"⬇️ SQL 다운로드 ({len(export_rows)}행)",
            data=sql_data,
            file_name=f"rag_chunks{file_suffix}.sql",
            mime="text/plain",
            type="primary",
            use_container_width=True,
        )

    # --- 문서 메타데이터도 별도 다운로드 ---
    st.divider()
    with st.expander("📄 문서 메타데이터도 다운로드"):
        doc_data = db.export_documents()
        doc_json = json.dumps(doc_data, ensure_ascii=False, indent=2)
        st.download_button(
            label=f"⬇️ 문서 목록 JSON ({len(doc_data)}개)",
            data=doc_json,
            file_name="documents_metadata.json",
            mime="application/json",
            use_container_width=True,
        )

    # --- MySQL 가이드 ---
    st.divider()
    with st.expander("🐬 MySQL에 넣는 방법 안내"):
        st.markdown("""
**⚠️ 한글 인코딩**: CSV는 UTF-8(BOM)으로 저장됩니다. Excel에서 열면 한글이 정상 표시됩니다.

**1. MySQL 테이블 생성** (한글을 위해 `utf8mb4` 사용)

```sql
CREATE DATABASE my_rag CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE my_rag;

CREATE TABLE document_chunks (
    chunk_id BIGINT PRIMARY KEY,
    document_id BIGINT,
    chunk_index INT,
    content LONGTEXT CHARACTER SET utf8mb4,
    filename VARCHAR(255),
    file_type VARCHAR(50),
    page_number INT,
    created_at DATETIME,
    embedding JSON
);
```

**2. CSV로 가져오기**

```sql
LOAD DATA INFILE '/path/to/rag_chunks.csv'
INTO TABLE document_chunks
CHARACTER SET utf8mb4
FIELDS TERMINATED BY ','
ENCLOSED BY '"'
LINES TERMINATED BY '\\n'
IGNORE 1 ROWS;
```

**3. 또는 SQL INSERT문 실행**

```bash
mysql -u root -p --default-character-set=utf8mb4 my_rag < rag_chunks.sql
```
""")


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
elif page == "📥 데이터 내보내기":
    page_export()
elif page == "⚙️ 설정":
    page_settings()
