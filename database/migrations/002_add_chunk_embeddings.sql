CREATE EXTENSION IF NOT EXISTS vector;

ALTER TABLE rag.evidence_chunks
    ADD CONSTRAINT evidence_chunks_content_identity_unique
    UNIQUE (corpus_revision_id, chunk_id, content_sha256);

CREATE TABLE rag.embedding_models (
    embedding_model_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    provider TEXT NOT NULL,
    deployment_name TEXT NOT NULL,
    model_name TEXT NOT NULL,
    model_version TEXT NOT NULL,
    api_version TEXT NOT NULL,
    region TEXT NOT NULL,
    dimensions INTEGER NOT NULL,
    distance_metric TEXT NOT NULL,
    document_input_version TEXT NOT NULL,
    query_input_version TEXT NOT NULL,
    version_upgrade_policy TEXT NOT NULL,
    metadata JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT embedding_models_identity_unique
        UNIQUE (
            provider,
            deployment_name,
            model_name,
            model_version,
            api_version,
            region,
            dimensions,
            distance_metric,
            document_input_version,
            query_input_version
        ),
    CONSTRAINT embedding_models_provider_not_blank
        CHECK (BTRIM(provider) <> ''),
    CONSTRAINT embedding_models_deployment_not_blank
        CHECK (BTRIM(deployment_name) <> ''),
    CONSTRAINT embedding_models_name_not_blank
        CHECK (BTRIM(model_name) <> ''),
    CONSTRAINT embedding_models_version_not_blank
        CHECK (BTRIM(model_version) <> ''),
    CONSTRAINT embedding_models_api_version_not_blank
        CHECK (BTRIM(api_version) <> ''),
    CONSTRAINT embedding_models_region_not_blank
        CHECK (BTRIM(region) <> ''),
    CONSTRAINT embedding_models_dimensions_supported
        CHECK (dimensions = 1536),
    CONSTRAINT embedding_models_distance_metric_supported
        CHECK (distance_metric = 'cosine'),
    CONSTRAINT embedding_models_document_input_not_blank
        CHECK (BTRIM(document_input_version) <> ''),
    CONSTRAINT embedding_models_query_input_not_blank
        CHECK (BTRIM(query_input_version) <> ''),
    CONSTRAINT embedding_models_upgrade_policy_not_blank
        CHECK (BTRIM(version_upgrade_policy) <> '')
);

CREATE TABLE rag.embedding_runs (
    embedding_run_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    embedding_model_id BIGINT NOT NULL,
    corpus_revision_id BIGINT NOT NULL,
    status TEXT NOT NULL,
    application_revision TEXT NOT NULL,
    started_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMPTZ,
    target_chunk_count INTEGER NOT NULL,
    embedded_chunk_count INTEGER,
    reused_chunk_count INTEGER,
    failed_chunk_count INTEGER,
    prompt_tokens BIGINT,
    api_latency_ms NUMERIC(14, 3),
    input_price_per_million_tokens NUMERIC(20, 10),
    pricing_currency TEXT,
    pricing_checked_at DATE,
    calculated_cost NUMERIC(20, 12),
    error_message TEXT,
    CONSTRAINT embedding_runs_model_fk
        FOREIGN KEY (embedding_model_id)
        REFERENCES rag.embedding_models (embedding_model_id)
        ON DELETE RESTRICT,
    CONSTRAINT embedding_runs_corpus_fk
        FOREIGN KEY (corpus_revision_id)
        REFERENCES rag.corpus_revisions (corpus_revision_id)
        ON DELETE RESTRICT,
    CONSTRAINT embedding_runs_identity_unique
        UNIQUE (
            embedding_run_id,
            embedding_model_id,
            corpus_revision_id
        ),
    CONSTRAINT embedding_runs_status_allowed
        CHECK (status IN ('running', 'completed', 'failed')),
    CONSTRAINT embedding_runs_application_revision_not_blank
        CHECK (BTRIM(application_revision) <> ''),
    CONSTRAINT embedding_runs_completed_state
        CHECK (
            (status = 'running' AND completed_at IS NULL)
            OR
            (status IN ('completed', 'failed') AND completed_at IS NOT NULL)
        ),
    CONSTRAINT embedding_runs_target_chunk_count_nonnegative
        CHECK (target_chunk_count >= 0),
    CONSTRAINT embedding_runs_embedded_count_nonnegative
        CHECK (
            embedded_chunk_count IS NULL
            OR embedded_chunk_count >= 0
        ),
    CONSTRAINT embedding_runs_reused_count_nonnegative
        CHECK (
            reused_chunk_count IS NULL
            OR reused_chunk_count >= 0
        ),
    CONSTRAINT embedding_runs_failed_count_nonnegative
        CHECK (
            failed_chunk_count IS NULL
            OR failed_chunk_count >= 0
        ),
    CONSTRAINT embedding_runs_prompt_tokens_nonnegative
        CHECK (prompt_tokens IS NULL OR prompt_tokens >= 0),
    CONSTRAINT embedding_runs_latency_nonnegative
        CHECK (api_latency_ms IS NULL OR api_latency_ms >= 0),
    CONSTRAINT embedding_runs_price_nonnegative
        CHECK (
            input_price_per_million_tokens IS NULL
            OR input_price_per_million_tokens >= 0
        ),
    CONSTRAINT embedding_runs_cost_nonnegative
        CHECK (calculated_cost IS NULL OR calculated_cost >= 0),
    CONSTRAINT embedding_runs_pricing_consistent
        CHECK (
            (
                input_price_per_million_tokens IS NULL
                AND pricing_currency IS NULL
                AND pricing_checked_at IS NULL
                AND calculated_cost IS NULL
            )
            OR
            (
                input_price_per_million_tokens IS NOT NULL
                AND pricing_currency IS NOT NULL
                AND BTRIM(pricing_currency) <> ''
                AND pricing_checked_at IS NOT NULL
                AND calculated_cost IS NOT NULL
            )
        ),
    CONSTRAINT embedding_runs_error_state
        CHECK (
            (
                status = 'failed'
                AND error_message IS NOT NULL
                AND BTRIM(error_message) <> ''
            )
            OR
            (status <> 'failed' AND error_message IS NULL)
        )
);

CREATE TABLE rag.chunk_embeddings (
    corpus_revision_id BIGINT NOT NULL,
    chunk_id TEXT NOT NULL,
    chunk_content_sha256 TEXT NOT NULL,
    embedding_model_id BIGINT NOT NULL,
    embedding_run_id BIGINT NOT NULL,
    input_sha256 TEXT NOT NULL,
    input_char_count INTEGER NOT NULL,
    prompt_tokens INTEGER NOT NULL,
    api_latency_ms NUMERIC(14, 3) NOT NULL,
    calculated_cost NUMERIC(20, 12),
    response_model TEXT NOT NULL,
    vector_sha256 TEXT NOT NULL,
    embedding VECTOR(1536) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (
        corpus_revision_id,
        chunk_id,
        embedding_model_id
    ),
    CONSTRAINT chunk_embeddings_chunk_identity_fk
        FOREIGN KEY (
            corpus_revision_id,
            chunk_id,
            chunk_content_sha256
        )
        REFERENCES rag.evidence_chunks (
            corpus_revision_id,
            chunk_id,
            content_sha256
        )
        ON DELETE CASCADE,
    CONSTRAINT chunk_embeddings_run_identity_fk
        FOREIGN KEY (
            embedding_run_id,
            embedding_model_id,
            corpus_revision_id
        )
        REFERENCES rag.embedding_runs (
            embedding_run_id,
            embedding_model_id,
            corpus_revision_id
        )
        ON DELETE RESTRICT,
    CONSTRAINT chunk_embeddings_chunk_id_not_blank
        CHECK (BTRIM(chunk_id) <> ''),
    CONSTRAINT chunk_embeddings_content_sha256_format
        CHECK (chunk_content_sha256 ~ '^[A-F0-9]{64}$'),
    CONSTRAINT chunk_embeddings_input_sha256_format
        CHECK (input_sha256 ~ '^[A-F0-9]{64}$'),
    CONSTRAINT chunk_embeddings_input_char_count_positive
        CHECK (input_char_count > 0),
    CONSTRAINT chunk_embeddings_prompt_tokens_positive
        CHECK (prompt_tokens > 0),
    CONSTRAINT chunk_embeddings_latency_nonnegative
        CHECK (api_latency_ms >= 0),
    CONSTRAINT chunk_embeddings_cost_nonnegative
        CHECK (calculated_cost IS NULL OR calculated_cost >= 0),
    CONSTRAINT chunk_embeddings_response_model_not_blank
        CHECK (BTRIM(response_model) <> ''),
    CONSTRAINT chunk_embeddings_vector_sha256_format
        CHECK (vector_sha256 ~ '^[A-F0-9]{64}$')
);

CREATE INDEX embedding_runs_started_at_idx
    ON rag.embedding_runs (started_at DESC);

CREATE INDEX embedding_runs_corpus_model_idx
    ON rag.embedding_runs (
        corpus_revision_id,
        embedding_model_id,
        status
    );

CREATE INDEX chunk_embeddings_corpus_model_idx
    ON rag.chunk_embeddings (
        corpus_revision_id,
        embedding_model_id
    );

CREATE INDEX chunk_embeddings_embedding_hnsw_cosine_idx
    ON rag.chunk_embeddings
    USING HNSW (embedding vector_cosine_ops);
