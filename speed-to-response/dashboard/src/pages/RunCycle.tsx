import { useState } from "react";
import { api, type RunCycleCounts } from "../api";

export function RunCycle() {
  const [counts, setCounts] = useState<RunCycleCounts | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const run = () => {
    setLoading(true);
    setError(null);
    api
      .runCycle()
      .then((r) => setCounts(r.counts))
      .catch((err) => setError(err instanceof Error ? err.message : String(err)))
      .finally(() => setLoading(false));
  };

  return (
    <section className="run-cycle">
      <h1 className="page-title">Run cycle</h1>
      <p className="muted">
        Poll Instantly + Prosp, classify replies, notify interested leads to Slack, and optionally auto-reply by email and LinkedIn.
      </p>
      <button
        type="button"
        onClick={run}
        disabled={loading}
        className="btn primary"
        aria-label={loading ? "Running…" : "Run cycle now"}
      >
        {loading ? "Running…" : "Run cycle now"}
      </button>
      {error && <div className="error-msg" role="alert">{error}</div>}
      {counts && (
        <div className="counts">
          <div className="count-item">
            <span className="label">Fetched</span>
            <strong>{counts.fetched ?? 0}</strong>
          </div>
          <div className="count-item">
            <span className="label">Interested</span>
            <strong>{counts.interested ?? 0}</strong>
          </div>
          <div className="count-item">
            <span className="label">Notified</span>
            <strong>{counts.notified ?? 0}</strong>
          </div>
          <div className="count-item">
            <span className="label">Skipped (already processed)</span>
            <strong>{counts.skipped_already_processed ?? 0}</strong>
          </div>
        </div>
      )}
    </section>
  );
}
