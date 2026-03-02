import { useEffect, useState } from "react";
import { api, type Health, type Lead, type SourcesResponse } from "../api";

export function Overview() {
  const [health, setHealth] = useState<Health | null>(null);
  const [leads, setLeads] = useState<Lead[]>([]);
  const [sources, setSources] = useState<SourcesResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([api.health(), api.leads(), api.sources()])
      .then(([h, l, s]) => {
        setHealth(h);
        setLeads(Array.isArray(l) ? l : []);
        setSources(s);
      })
      .catch((err) => setError(err instanceof Error ? err.message : String(err)))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="loading-wrap">
        <div className="spinner" aria-hidden />
        <span>Loading data…</span>
      </div>
    );
  }
  if (error) {
    return (
      <div className="page-message error" role="alert">
        Error: {error}. Check that the backend is running at{" "}
        {import.meta.env.VITE_API_URL || "http://localhost:8000"}.
      </div>
    );
  }

  const recentLeads = leads.slice(0, 10);
  const instCount = sources?.instantly?.count ?? 0;
  const prospCount = sources?.prosp?.count ?? 0;

  return (
    <section className="overview">
      <h1 className="page-title">Overview</h1>
      <p className="page-subtitle">Speed-to-response at a glance</p>
      <div className="cards overview-cards">
        <div className="card">
          <h3>Status</h3>
          <p className="status">{health?.status ?? "—"}</p>
        </div>
        <div className="card">
          <h3>Processed leads</h3>
          <p className="stat">{leads.length}</p>
        </div>
        <div className="card">
          <h3>Email (unread)</h3>
          <p className="stat">{instCount}</p>
        </div>
        <div className="card">
          <h3>LinkedIn (unread)</h3>
          <p className="stat">{prospCount}</p>
        </div>
      </div>
      <div className="card wide">
        <h3>Recent leads</h3>
        {recentLeads.length === 0 ? (
          <p className="muted">No leads yet. Run a cycle or wait for the next poll.</p>
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Lead</th>
                  <th>Company</th>
                  <th>Channel</th>
                  <th>Classification</th>
                  <th>Notified</th>
                </tr>
              </thead>
              <tbody>
                {recentLeads.map((lead) => (
                  <tr key={lead.id}>
                    <td>{lead.lead_name || "—"}</td>
                    <td>{lead.company || "—"}</td>
                    <td>
                      <span className="badge channel">{lead.channel}</span>
                    </td>
                    <td>
                      <span className={`badge ${lead.classification}`}>
                        {(lead.classification || "").replace("_", " ")}
                      </span>
                    </td>
                    <td>{lead.notified_at ? new Date(lead.notified_at).toLocaleString() : "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </section>
  );
}
