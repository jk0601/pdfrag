# 📚 PDF-RAG: 문서 기반 AI 챗봇

PDF, 이미지, PowerPoint 파일을 업로드하면 AI가 문서 내용을 바탕으로 질문에 답변하는 RAG(Retrieval-Augmented Generation) 시스템입니다.

---

## 🤔 RAG란 무엇인가요?

**RAG (Retrieval-Augmented Generation)** 는 AI가 답변할 때 외부 문서를 참고하도록 하는 기술입니다.

### 일반 ChatGPT vs RAG 챗봇

| | 일반 ChatGPT | RAG 챗봇 (이 프로젝트) |
|---|---|---|
| 지식 범위 | 학습 데이터만 | 우리가 업로드한 문서 포함 |
| 회사 문서 | 모름 ❌ | 답변 가능 ✅ |
| 출처 표시 | 불가 | 참고한 문서 표시 |
| 환각(거짓답변) | 자주 발생 | 문서 기반으로 최소화 |

### RAG 작동 원리 (5단계)

```
1. 📄 문서 업로드     "보고서.pdf"를 시스템에 넣기
       ↓
2. ✂️ 텍스트 분할     긴 문서를 작은 조각(청크)으로 나누기
       ↓
3. 🧠 임베딩 생성     각 조각의 "의미"를 숫자 벡터로 변환
       ↓
4. 💾 DB 저장         벡터와 텍스트를 Supabase에 저장
       ↓
5. 🔍 질문 & 답변     질문과 유사한 조각을 찾아 AI에게 전달
```

---

## 📁 프로젝트 구조

```
pdfrag/
├── main.py                  # 프로그램 시작점 (CLI)
├── config.py                # 설정 관리
├── pipeline.py              # 전체 처리 파이프라인
├── .env.example             # 환경변수 예시 파일
├── requirements.txt         # Python 패키지 목록
│
├── processors/              # 파일 처리기들
│   ├── pdf_processor.py     # PDF 텍스트/이미지 추출
│   ├── image_processor.py   # 이미지 OCR 처리
│   └── pptx_processor.py    # PowerPoint 처리
│
├── rag/                     # RAG 핵심 모듈
│   ├── chunker.py           # 텍스트 분할 (청킹)
│   ├── embedder.py          # 임베딩 벡터 생성
│   └── retriever.py         # 유사 문서 검색
│
├── database/                # 데이터베이스
│   ├── schema.sql           # Supabase 테이블 설계
│   └── supabase_client.py   # Supabase 연결 클라이언트
│
├── chatbot/                 # 챗봇
│   └── chat.py              # RAG 기반 대화 엔진
│
└── uploads/                 # 업로드 파일 저장 폴더
```

---

## 🚀 시작하기 (Step by Step)

### 1단계: Python 환경 준비

Python 3.11 이상이 필요합니다.

```bash
# Python 버전 확인
python --version

# 가상환경 생성 (프로젝트 전용 Python 환경)
python -m venv venv

# 가상환경 활성화
# Windows PowerShell:
.\venv\Scripts\Activate.ps1
# Windows CMD:
.\venv\Scripts\activate.bat
# Mac/Linux:
source venv/bin/activate

# 패키지 설치
pip install -r requirements.txt
```

> **가상환경이란?** 프로젝트마다 별도의 Python 패키지 공간을 만드는 것입니다. 다른 프로젝트와 패키지가 충돌하지 않게 해줍니다.

### 2단계: API 키 발급

#### OpenAI API 키
1. [OpenAI Platform](https://platform.openai.com/) 접속 및 로그인
2. 좌측 메뉴 → API Keys → "Create new secret key" 클릭
3. 생성된 키를 복사 (sk-...로 시작)

> **비용 안내**: text-embedding-3-small 모델 기준, 100만 토큰당 약 $0.02 (매우 저렴)

#### Supabase 프로젝트 생성
1. [Supabase](https://supabase.com/) 접속 및 회원가입 (무료)
2. "New Project" 클릭하여 프로젝트 생성
3. Project Settings → API에서 확인:
   - **Project URL**: `https://xxxx.supabase.co`
   - **anon/public key**: `eyJ...`로 시작하는 긴 문자열

### 3단계: 환경변수 설정

```bash
# .env.example을 .env로 복사
copy .env.example .env    # Windows
# cp .env.example .env    # Mac/Linux
```

`.env` 파일을 열고 실제 값을 입력합니다:

```env
OPENAI_API_KEY=sk-실제API키
SUPABASE_URL=https://실제프로젝트.supabase.co
SUPABASE_KEY=실제anon키
```

### 4단계: Supabase 데이터베이스 설정

1. Supabase 대시보드 → SQL Editor 접속
2. `database/schema.sql` 파일의 내용을 전체 복사
3. SQL Editor에 붙여넣기 후 "Run" 클릭

> 이 SQL은 문서와 청크를 저장할 테이블, 벡터 검색 인덱스, 유사도 검색 함수를 생성합니다.

### 5단계: 설정 확인

```bash
python main.py check
```

"모든 설정이 정상입니다!" 메시지가 나오면 준비 완료!

---

## 📖 사용법

### 파일 업로드

```bash
# PDF 파일 업로드
python main.py upload 보고서.pdf

# 여러 파일 한 번에 업로드
python main.py upload 파일1.pdf 파일2.pptx 이미지.png

# uploads 폴더에 파일을 넣고 경로 지정도 가능
python main.py upload uploads/분석자료.pdf
```

### 챗봇으로 질문하기

```bash
python main.py chat
```

실행하면 대화형 인터페이스가 시작됩니다:
```
❓ 질문: 2024년 매출은 얼마인가요?
🤖 답변: 제공된 문서에 따르면, 2024년 매출은...

❓ 질문: quit    ← 종료
```

### 문서 관리

```bash
# 저장된 문서 목록 보기
python main.py list

# 특정 문서 삭제
python main.py delete 1
```

---

## 🔧 핵심 개념 상세 설명

### 1. 임베딩 (Embedding)

텍스트의 "의미"를 1536개의 숫자로 표현한 것입니다.

```
"고양이가 쥐를 잡는다"  → [0.23, -0.45, 0.67, ..., 0.12]  (1536개 숫자)
"강아지가 쥐를 쫓는다"  → [0.21, -0.43, 0.65, ..., 0.11]  ← 비슷!
"주식 시장이 폭락했다"  → [-0.89, 0.34, -0.12, ..., 0.78]  ← 매우 다름!
```

의미가 비슷한 문장은 비슷한 숫자 배열을 가지므로, 수학적으로 "유사도"를 계산할 수 있습니다.

### 2. 청킹 (Chunking)

긴 문서를 작은 조각으로 나누는 것입니다.

**왜 나눌까?**
- AI 모델에 한 번에 보낼 수 있는 텍스트 양에 제한이 있음
- 작은 조각이 질문에 대한 정확한 답변을 찾기 더 쉬움
- 비용도 절약됨

**겹침(Overlap)이란?**
```
원본: "A B C D E F G H I J"

겹침 없이 나누면:    [A B C D E] [F G H I J]
                     → "E"와 "F" 사이의 맥락이 끊어짐

겹침 있게 나누면:    [A B C D E] [D E F G H] [G H I J]
                     → "D E"가 겹쳐서 맥락이 이어짐
```

### 3. 코사인 유사도 (Cosine Similarity)

두 벡터가 얼마나 같은 방향을 가리키는지 측정합니다 (0~1).

```
유사도 1.0 = 완전히 같은 의미
유사도 0.7 = 꽤 비슷한 의미
유사도 0.3 = 별로 관련 없음
유사도 0.0 = 전혀 다른 의미
```

### 4. pgvector

PostgreSQL 데이터베이스에서 벡터를 저장하고 유사도 검색을 할 수 있게 해주는 확장입니다. Supabase는 pgvector를 기본 지원합니다.

---

## ⚙️ 설정 커스터마이징

`.env` 파일에서 조정 가능한 설정들:

| 설정 | 기본값 | 설명 |
|------|--------|------|
| `EMBEDDING_MODEL` | text-embedding-3-small | 임베딩 모델 (small이 가성비 좋음) |
| `EMBEDDING_DIMENSION` | 1536 | 벡터 차원 수 |
| `CHAT_MODEL` | gpt-4o-mini | 챗봇 답변 모델 |
| `CHUNK_SIZE` | 1000 | 청크 최대 크기 (글자 수) |
| `CHUNK_OVERLAP` | 200 | 청크 간 겹침 크기 |

### 청크 크기 가이드
- **500자**: 짧은 문서, 정확한 검색 원할 때
- **1000자** (기본): 대부분의 용도에 적합
- **2000자**: 긴 문맥이 필요한 문서

---

## 🧪 Tesseract OCR 설치 (이미지 텍스트 추출용, 선택사항)

이미지나 PDF 내 이미지에서 텍스트를 추출하려면 Tesseract가 필요합니다.

### Windows
1. [Tesseract 설치 페이지](https://github.com/UB-Mannheim/tesseract/wiki) 에서 다운로드
2. 설치 시 "Additional language data" → "Korean" 체크
3. 설치 후 환경변수 PATH에 Tesseract 경로 추가

### Mac
```bash
brew install tesseract tesseract-lang
```

### 대안: OpenAI Vision API
Tesseract 설치가 어려우면 OpenAI Vision API를 사용할 수 있습니다 (더 정확하지만 API 비용 발생).

---

## 🔍 문제 해결

### "OPENAI_API_KEY가 설정되지 않았습니다"
→ `.env` 파일에 올바른 API 키가 입력되어 있는지 확인

### "relation "documents" does not exist"
→ `database/schema.sql`을 Supabase SQL Editor에서 실행했는지 확인

### "Could not find the function match_documents"
→ `schema.sql`의 `match_documents` 함수 부분만 다시 실행

### OCR이 작동하지 않음
→ Tesseract가 설치되어 있는지 확인하거나, Vision API 모드 사용

---

## 📊 비용 예상

| 작업 | 모델 | 비용 (대략) |
|------|------|------------|
| 임베딩 생성 | text-embedding-3-small | 100만 토큰당 $0.02 |
| 챗봇 답변 | gpt-4o-mini | 100만 입력토큰당 $0.15 |
| 이미지 분석 | gpt-4o-mini (Vision) | 이미지당 ~$0.01 |
| Supabase | Free tier | 무료 (500MB DB) |

100페이지 PDF 1개 처리 시 예상 비용: **약 $0.01~$0.05**

---

## 📜 라이선스

이 프로젝트는 교육/학습 목적으로 자유롭게 사용할 수 있습니다.
