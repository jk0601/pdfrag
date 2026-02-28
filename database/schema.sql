-- ============================================================
-- Supabase 데이터베이스 스키마 (v2 - 수정본)
-- ============================================================
-- 이 SQL을 Supabase 대시보드의 SQL Editor에서 실행하세요.
--
-- ⚠️ 이전에 v1을 실행했다면, 아래 "마이그레이션" 섹션만 실행하세요.
-- ============================================================

-- 1단계: pgvector 확장 활성화
CREATE EXTENSION IF NOT EXISTS vector;

-- 2단계: 문서 정보 테이블
CREATE TABLE IF NOT EXISTS documents (
    id          BIGSERIAL PRIMARY KEY,
    filename    TEXT NOT NULL,
    file_type   TEXT NOT NULL,
    file_size   BIGINT,
    page_count  INT,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

-- 3단계: 문서 청크 테이블
CREATE TABLE IF NOT EXISTS document_chunks (
    id            BIGSERIAL PRIMARY KEY,
    document_id   BIGINT REFERENCES documents(id) ON DELETE CASCADE,
    chunk_index   INT NOT NULL,
    content       TEXT NOT NULL,
    metadata      JSONB DEFAULT '{}'::JSONB,
    embedding     VECTOR(1536),
    created_at    TIMESTAMPTZ DEFAULT NOW()
);

-- 4단계: 인덱스
-- ⚠️ ivfflat 대신 HNSW 사용 (적은 데이터에서도 정확하게 동작)
-- 이전 ivfflat 인덱스가 있다면 먼저 삭제
DROP INDEX IF EXISTS idx_document_chunks_embedding;

CREATE INDEX IF NOT EXISTS idx_chunks_embedding_hnsw
ON document_chunks
USING hnsw (embedding vector_cosine_ops);

CREATE INDEX IF NOT EXISTS idx_document_chunks_document_id
ON document_chunks(document_id);

-- 5단계: 벡터 유사도 검색 함수 (수정: 타입 캐스팅 개선)
-- 이전 함수가 있다면 교체
DROP FUNCTION IF EXISTS match_documents(VECTOR(1536), FLOAT, INT);

CREATE OR REPLACE FUNCTION match_documents(
    query_embedding VECTOR(1536),
    match_threshold FLOAT DEFAULT 0.3,
    match_count INT DEFAULT 5
)
RETURNS TABLE (
    id BIGINT,
    document_id BIGINT,
    content TEXT,
    metadata JSONB,
    similarity FLOAT
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT
        dc.id,
        dc.document_id,
        dc.content,
        dc.metadata,
        (1 - (dc.embedding <=> query_embedding))::FLOAT AS similarity
    FROM document_chunks dc
    WHERE dc.embedding IS NOT NULL
      AND (1 - (dc.embedding <=> query_embedding)) > match_threshold
    ORDER BY dc.embedding <=> query_embedding
    LIMIT match_count;
END;
$$;

-- ============================================================
-- 🔧 마이그레이션 전용 (이전 v1에서 업그레이드하는 경우)
-- 아래만 복사하여 SQL Editor에서 실행하세요:
-- ============================================================
-- DROP INDEX IF EXISTS idx_document_chunks_embedding;
-- CREATE INDEX IF NOT EXISTS idx_chunks_embedding_hnsw
-- ON document_chunks USING hnsw (embedding vector_cosine_ops);
--
-- DROP FUNCTION IF EXISTS match_documents(VECTOR(1536), FLOAT, INT);
-- (그 다음 위의 CREATE OR REPLACE FUNCTION 부분 실행)
-- ============================================================
