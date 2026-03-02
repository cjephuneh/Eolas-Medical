import { useEffect, useState } from "react";
import { api, type SourcesResponse } from "../api";

export function Sources() {
  const [data, setData] = useState<SourcesResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .sources()
      .then(setData)
      .catch((err) => setError(err instanceof Error ? err.message : String(err)))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="loading-wrap">
        <div className="spinner" aria-hidden />
        <span>Fetching source counts…</span>
      </div>
    );
  }
  if (error) {
    return (
      <div className="page-message error" role="alert">
        Error: {error}
      </div>
    );
  }

  const inst = data?.instantly;
  const prosp = data?.prosp;

  return (
    <section className="sources">
      <h1 className="page-title">Sources</h1>
      <p className="page-subtitle">Live signal counts from Instantly (email) and Prosp (LinkedIn)</p>
      <div className="cards">
        <div className="card">
          <h3>Instantly (Email)</h3>
          <p className="big">{inst?.count ?? 0}</p>
          <p className="muted">unread signals</p>
        </div>
        <div className="card">
          <h3>Prosp (LinkedIn)</h3>
          <p className="big">{prosp?.count ?? 0}</p>
          <p className="muted">signals</p>
        </div>
      </div>
    </section>
  );
}
