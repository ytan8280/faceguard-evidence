const ASSESSMENT_LABELS = {
  insufficient_evidence: "Insufficient Evidence",
  requires_verification: "Requires Verification",
  supported_limited_conclusion: "Supported, Limited Conclusion"
};

function ReferenceBadges({ observationIds = [], detectorIds = [], citations = [] }) {
  const references = [
    ...observationIds.map((value) => ({ value, type: "observation" })),
    ...detectorIds.map((value) => ({ value, type: "detector" })),
    ...citations.map((value) => ({ value, type: "evidence" }))
  ];

  if (!references.length) return null;

  return (
    <div className="evidence-reference-row" aria-label="Conclusion evidence basis">
      {references.map(({ value, type }) => (
        <span className={`evidence-reference evidence-reference-${type}`} key={`${type}-${value}`}>
          {value}
        </span>
      ))}
    </div>
  );
}

function SectionHeading({ eyebrow, title, description }) {
  return (
    <div className="evidence-section-heading">
      <p className="report-kicker">{eyebrow}</p>
      <h3>{title}</h3>
      {description ? <p>{description}</p> : null}
    </div>
  );
}

function CitationLink({ source }) {
  const isExternal = /^https?:\/\//i.test(source.canonical_url || "");
  const location = source.page_number ? `Page ${source.page_number}` : source.heading || source.source_id;

  return (
    <article className="evidence-source-card">
      <div className="evidence-source-topline">
        <span className="evidence-citation-id">{source.citation_id}</span>
        <span className="evidence-source-rank">
          L{source.lexical_rank ?? "–"} · S{source.semantic_rank ?? "–"}
        </span>
      </div>
      <h4>{source.source_title}</h4>
      <p>{location}</p>
      {isExternal ? (
        <a href={source.canonical_url} target="_blank" rel="noreferrer">
          Open authoritative source
        </a>
      ) : (
        <code>{source.canonical_url}</code>
      )}
    </article>
  );
}

function formatCost(value) {
  const numeric = Number(value || 0);
  if (!Number.isFinite(numeric)) return String(value || "0");
  return `$${numeric.toFixed(6)}`;
}

export default function EvidenceReportPanel({ payload }) {
  const evidenceReport = payload?.evidence_report;
  const report = evidenceReport?.report;
  if (!report) return null;

  const assessment = ASSESSMENT_LABELS[report.overall_assessment] || report.overall_assessment;
  const metadata = payload.metadata || {};
  const detector = payload.detector || {};
  const metrics = evidenceReport.metrics || {};
  const configuration = evidenceReport.configuration || {};

  return (
    <section className="evidence-report">
      <header className={`evidence-assessment evidence-assessment-${report.overall_assessment}`}>
        <div>
          <p className="report-kicker">FaceGuard Evidence Assessment</p>
          <h2>{assessment}</h2>
          <p>
            This report separates direct observations, detector output, retrieved evidence,
            supported conclusions, and claims that cannot be established.
          </p>
        </div>
        <div className="evidence-assessment-model">
          <span>Detector signal</span>
          <strong>{detector.label || "Unknown"}</strong>
          <small>{((detector.fake_probability || 0) * 100).toFixed(2)}% fake probability</small>
        </div>
      </header>

      <div className="evidence-report-grid">
        <section className="panel evidence-section">
          <SectionHeading
            eyebrow="Observed Facts"
            title="What the file directly showed"
            description="These statements come from upload and metadata inspection, not the AI detector."
          />
          <div className="evidence-list">
            {(report.observed_facts || []).map((item, index) => (
              <article className="evidence-fact-card" key={`${item.statement}-${index}`}>
                <p>{item.statement}</p>
                <ReferenceBadges observationIds={item.observation_ids} />
              </article>
            ))}
          </div>
          <dl className="evidence-metadata-grid">
            <div><dt>Format</dt><dd>{metadata.format_name || "Unknown"}</dd></div>
            <div><dt>Dimensions</dt><dd>{metadata.width} × {metadata.height}</dd></div>
            <div><dt>EXIF</dt><dd>{metadata.has_exif ? "Present" : "Not present"}</dd></div>
            <div>
              <dt>Content Credentials</dt>
              <dd>{metadata.content_credentials_status === "not_inspected" ? "Not inspected" : metadata.content_credentials_status}</dd>
            </div>
          </dl>
        </section>

        <section className="panel evidence-section">
          <SectionHeading
            eyebrow="Detector Output"
            title="One probabilistic signal"
            description="The detector result is reported separately and is not the final conclusion."
          />
          <article className="evidence-detector-card">
            <div className="evidence-detector-score">
              <span>{detector.label}</span>
              <strong>{((detector.fake_probability || 0) * 100).toFixed(2)}%</strong>
              <small>Threshold: {Number(detector.threshold || 0).toFixed(2)}</small>
            </div>
            <div>
              <p>{report.detector_output?.statement}</p>
              <ReferenceBadges detectorIds={report.detector_output?.detector_ids} />
              {(report.detector_output?.caveats || []).length ? (
                <ul className="evidence-caveat-list">
                  {report.detector_output.caveats.map((caveat) => <li key={caveat}>{caveat}</li>)}
                </ul>
              ) : null}
            </div>
          </article>
        </section>
      </div>

      <section className="panel evidence-section">
        <SectionHeading
          eyebrow="Retrieved Evidence"
          title="Sources used by the report"
          description="Citation IDs in conclusions map to these exact versioned chunks."
        />
        <div className="evidence-source-grid">
          {(evidenceReport.evidence || []).map((source) => (
            <CitationLink source={source} key={source.citation_id} />
          ))}
        </div>
        <div className="evidence-statement-list">
          {(report.retrieved_evidence || []).map((item, index) => (
            <article key={`${item.statement}-${index}`}>
              <p>{item.statement}</p>
              <ReferenceBadges citations={item.citations} />
            </article>
          ))}
        </div>
      </section>

      <div className="evidence-report-grid evidence-conclusion-grid">
        <section className="panel evidence-section evidence-supported-section">
          <SectionHeading
            eyebrow="Supported Conclusions"
            title="What the current evidence supports"
          />
          <div className="evidence-list">
            {(report.supported_conclusions || []).map((item, index) => (
              <article className="evidence-conclusion-card" key={`${item.statement}-${index}`}>
                <p>{item.statement}</p>
                <small>{item.qualification}</small>
                <ReferenceBadges
                  observationIds={item.observation_ids}
                  detectorIds={item.detector_ids}
                  citations={item.citations}
                />
              </article>
            ))}
          </div>
        </section>

        <section className="panel evidence-section evidence-unsupported-section">
          <SectionHeading
            eyebrow="Unsupported Conclusions"
            title="What cannot be established"
          />
          <div className="evidence-list">
            {(report.unsupported_conclusions || []).map((item, index) => (
              <article className="evidence-unsupported-card" key={`${item.claim}-${index}`}>
                <h4>{item.claim}</h4>
                <p>{item.reason}</p>
              </article>
            ))}
          </div>
        </section>
      </div>

      <section className="panel evidence-section">
        <SectionHeading
          eyebrow="Verification"
          title="Recommended next steps"
          description="These actions provide evidence beyond a single model score."
        />
        <ol className="evidence-steps">
          {(report.recommended_verification_steps || []).map((item, index) => (
            <li key={`${item.step}-${index}`}>
              <strong>{item.step}</strong>
              <p>{item.rationale}</p>
            </li>
          ))}
        </ol>
      </section>

      <details className="panel evidence-diagnostics">
        <summary>Technical diagnostics and measured cost</summary>
        <div className="evidence-diagnostic-grid">
          <div><span>Query embedding</span><strong>{metrics.query_embedding_latency_ms?.toFixed?.(1) || metrics.query_embedding_latency_ms} ms</strong></div>
          <div><span>Lexical retrieval</span><strong>{metrics.lexical_latency_ms?.toFixed?.(1) || metrics.lexical_latency_ms} ms</strong></div>
          <div><span>Semantic retrieval</span><strong>{metrics.semantic_latency_ms?.toFixed?.(1) || metrics.semantic_latency_ms} ms</strong></div>
          <div><span>Local reranker</span><strong>{metrics.reranker_latency_ms?.toFixed?.(1) || metrics.reranker_latency_ms} ms</strong></div>
          <div><span>Generation</span><strong>{metrics.generation_latency_ms?.toFixed?.(1) || metrics.generation_latency_ms} ms</strong></div>
          <div><span>Measured cloud cost</span><strong>{formatCost(metrics.total_measured_cost)}</strong></div>
        </div>
        <p className="evidence-config-line">
          {configuration.pipeline_version} · {configuration.prompt_version} · {configuration.answer_schema_version}
        </p>
      </details>
    </section>
  );
}
