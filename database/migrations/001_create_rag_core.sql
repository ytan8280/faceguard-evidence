BEGIN;

CREATE SCHEMA IF NOT EXISTS rag;

CREATE TABLE rag.source_documents (
    source_document_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    source_id TEXT NOT NULL,
    content_sha256 TEXT NOT NULL,
    title TEXT NOT NULL,
    source_category TEXT NOT NULL,
    publisher TEXT NOT NULL,
    authors TEXT[] NOT NULL,
    source_version TEXT NOT NULL,
    published_at DATE NOT NULL,
    canonical_url TEXT NOT NULL,
    license_name TEXT NOT NULL,
    license_url TEXT NOT NULL,
    content_path TEXT NOT NULL,
    content TEXT NOT NULL,
    content_bytes INTEGER NOT NULL,
    content_lines INTEGER NOT NULL,
    metadata JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT source_documents_identity_unique
        UNIQUE (source_id, content_sha256),
    CONSTRAINT source_documents_source_id_not_blank
        CHECK (BTRIM(source_id) <> ''),
    CONSTRAINT source_documents_sha256_format
        CHECK (content_sha256 ~ '^[A-F0-9]{64}$'),
    CONSTRAINT source_documents_content_bytes_positive
        CHECK (content_bytes > 0),
    CONSTRAINT source_documents_content_lines_positive
        CHECK (content_lines > 0),
    CONSTRAINT source_documents_content_bytes_matches
        CHECK (content_bytes = OCTET_LENGTH(content)),
    CONSTRAINT source_documents_authors_not_empty
        CHECK (CARDINALITY(authors) > 0),
    CONSTRAINT source_documents_content_not_blank
        CHECK (BTRIM(content) <> '')
);

CREATE TABLE rag.corpus_revisions (
    corpus_revision_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    corpus_sha256 TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    chunker_version TEXT NOT NULL,
    max_chunk_chars INTEGER NOT NULL,
    overlap_chars INTEGER NOT NULL DEFAULT 0,
    source_count INTEGER NOT NULL,
    chunk_count INTEGER NOT NULL,
    manifest JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT corpus_revisions_sha256_format
        CHECK (corpus_sha256 ~ '^[A-F0-9]{64}$'),
    CONSTRAINT corpus_revisions_name_not_blank
        CHECK (BTRIM(name) <> ''),
    CONSTRAINT corpus_revisions_chunker_not_blank
        CHECK (BTRIM(chunker_version) <> ''),
    CONSTRAINT corpus_revisions_max_chunk_chars_positive
        CHECK (max_chunk_chars > 0),
    CONSTRAINT corpus_revisions_overlap_nonnegative
        CHECK (overlap_chars >= 0),
    CONSTRAINT corpus_revisions_source_count_positive
        CHECK (source_count > 0),
    CONSTRAINT corpus_revisions_chunk_count_nonnegative
        CHECK (chunk_count >= 0)
);

CREATE TABLE rag.corpus_sources (
    corpus_revision_id BIGINT NOT NULL,
    source_document_id BIGINT NOT NULL,
    source_order INTEGER NOT NULL,
    PRIMARY KEY (corpus_revision_id, source_document_id),
    CONSTRAINT corpus_sources_revision_fk
        FOREIGN KEY (corpus_revision_id)
        REFERENCES rag.corpus_revisions (corpus_revision_id)
        ON DELETE CASCADE,
    CONSTRAINT corpus_sources_document_fk
        FOREIGN KEY (source_document_id)
        REFERENCES rag.source_documents (source_document_id)
        ON DELETE RESTRICT,
    CONSTRAINT corpus_sources_order_positive
        CHECK (source_order > 0),
    CONSTRAINT corpus_sources_order_unique
        UNIQUE (corpus_revision_id, source_order)
);

CREATE TABLE rag.evidence_chunks (
    corpus_revision_id BIGINT NOT NULL,
    chunk_id TEXT NOT NULL,
    source_document_id BIGINT NOT NULL,
    source_title TEXT NOT NULL,
    ordinal INTEGER NOT NULL,
    heading_path TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[],
    heading_text TEXT NOT NULL DEFAULT '',
    page_number INTEGER,
    content TEXT NOT NULL,
    content_sha256 TEXT NOT NULL,
    char_count INTEGER NOT NULL,
    oversized BOOLEAN NOT NULL DEFAULT FALSE,
    chunker_version TEXT NOT NULL,
    search_vector TSVECTOR GENERATED ALWAYS AS (
        SETWEIGHT(
            TO_TSVECTOR('english'::REGCONFIG, COALESCE(source_title, '')),
            'A'
        )
        ||
        SETWEIGHT(
            TO_TSVECTOR(
                'english'::REGCONFIG,
                heading_text
            ),
            'A'
        )
        ||
        SETWEIGHT(
            TO_TSVECTOR('english'::REGCONFIG, content),
            'B'
        )
    ) STORED,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (corpus_revision_id, chunk_id),
    CONSTRAINT evidence_chunks_corpus_source_fk
        FOREIGN KEY (corpus_revision_id, source_document_id)
        REFERENCES rag.corpus_sources (corpus_revision_id, source_document_id)
        ON DELETE CASCADE,
    CONSTRAINT evidence_chunks_source_ordinal_unique
        UNIQUE (corpus_revision_id, source_document_id, ordinal),
    CONSTRAINT evidence_chunks_chunk_id_not_blank
        CHECK (BTRIM(chunk_id) <> ''),
    CONSTRAINT evidence_chunks_ordinal_positive
        CHECK (ordinal > 0),
    CONSTRAINT evidence_chunks_heading_text_consistent
        CHECK (
            heading_text = COALESCE(ARRAY_TO_STRING(heading_path, ' > '), '')
        ),
    CONSTRAINT evidence_chunks_page_positive
        CHECK (page_number IS NULL OR page_number > 0),
    CONSTRAINT evidence_chunks_content_not_blank
        CHECK (BTRIM(content) <> ''),
    CONSTRAINT evidence_chunks_sha256_format
        CHECK (content_sha256 ~ '^[A-F0-9]{64}$'),
    CONSTRAINT evidence_chunks_char_count_matches
        CHECK (char_count = CHAR_LENGTH(content)),
    CONSTRAINT evidence_chunks_chunker_not_blank
        CHECK (BTRIM(chunker_version) <> '')
);

CREATE TABLE rag.ingestion_runs (
    ingestion_run_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    corpus_revision_id BIGINT,
    status TEXT NOT NULL,
    application_revision TEXT NOT NULL,
    started_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMPTZ,
    source_count INTEGER,
    chunk_count INTEGER,
    error_message TEXT,
    CONSTRAINT ingestion_runs_revision_fk
        FOREIGN KEY (corpus_revision_id)
        REFERENCES rag.corpus_revisions (corpus_revision_id)
        ON DELETE SET NULL,
    CONSTRAINT ingestion_runs_status_allowed
        CHECK (status IN ('running', 'completed', 'failed')),
    CONSTRAINT ingestion_runs_application_revision_not_blank
        CHECK (BTRIM(application_revision) <> ''),
    CONSTRAINT ingestion_runs_completed_state
        CHECK (
            (status = 'running' AND completed_at IS NULL)
            OR
            (status IN ('completed', 'failed') AND completed_at IS NOT NULL)
        ),
    CONSTRAINT ingestion_runs_source_count_nonnegative
        CHECK (source_count IS NULL OR source_count >= 0),
    CONSTRAINT ingestion_runs_chunk_count_nonnegative
        CHECK (chunk_count IS NULL OR chunk_count >= 0),
    CONSTRAINT ingestion_runs_error_state
        CHECK (
            (status = 'failed' AND error_message IS NOT NULL)
            OR
            (status <> 'failed' AND error_message IS NULL)
        )
);

CREATE INDEX source_documents_source_id_idx
    ON rag.source_documents (source_id);

CREATE INDEX evidence_chunks_search_vector_idx
    ON rag.evidence_chunks
    USING GIN (search_vector);

CREATE INDEX evidence_chunks_source_page_idx
    ON rag.evidence_chunks (
        corpus_revision_id,
        source_document_id,
        page_number
    );

CREATE INDEX ingestion_runs_started_at_idx
    ON rag.ingestion_runs (started_at DESC);

COMMIT;
