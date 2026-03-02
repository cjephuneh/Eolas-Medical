import { useCallback, useEffect, useRef, useState } from "react";
import { api, type Lead } from "../api";

const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";

export function Leads() {
  const [leads, setLeads] = useState<Lead[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedLead, setSelectedLead] = useState<Lead | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [sending, setSending] = useState(false);
  const [sendResult, setSendResult] = useState<{ ok: boolean; message: string } | null>(null);
  const detailRef = useRef<HTMLDivElement>(null);

  const loadLeads = useCallback(() => {
    api
      .leads()
      .then((l) => setLeads(Array.isArray(l) ? l : []))
      .catch((err) => setError(err instanceof Error ? err.message : String(err)))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    loadLeads();
  }, [loadLeads]);

  const onSelectLead = (lead: Lead) => {
    setSendResult(null);
    setSelectedLead(null);
    setDetailLoading(true);
    api
      .lead(lead.id)
      .then((full) => {
        setSelectedLead(full);
        setDetailLoading(false);
        requestAnimationFrame(() => detailRef.current?.scrollIntoView({ behavior: "smooth", block: "start" }));
      })
      .catch(() => setDetailLoading(false));
  };

  const canReply = (lead: Lead): boolean => {
    if (lead.channel === "email") {
      return Boolean(lead.reply_to_uuid && (lead.email || lead.lead_name));
    }
    if (lead.channel === "linkedin") {
      return Boolean(lead.linkedin_url);
    }
    return false;
  };

  const handleSendReply = () => {
    if (!selectedLead) return;
    const body = (selectedLead.suggested_response || "").trim();
    if (!body) {
      setSendResult({ ok: false, message: "No suggested reply to send." });
      return;
    }
    setSending(true);
    setSendResult(null);
    api
      .sendReply(selectedLead.id, body)
      .then(() => {
        setSendResult({ ok: true, message: "Reply sent." });
      })
      .catch((err) => {
        setSendResult({
          ok: false,
          message: err instanceof Error ? err.message : String(err),
        });
      })
      .finally(() => setSending(false));
  };

  if (loading) {
    return (
      <div className="loading-wrap">
        <div className="spinner" aria-hidden />
        <span>Loading leads…</span>
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

  const list = Array.isArray(leads) ? leads : [];

  return (
    <section className="leads">
      <div className="page-header">
        <div>
          <h1 className="page-title">Leads</h1>
          <p className="page-subtitle">Processed interest signals from email and LinkedIn</p>
        </div>
        <button
          type="button"
          onClick={() => window.open(`${API_BASE}/leads/export`, "_blank")}
          className="btn primary"
          aria-label="Export leads as CSV"
        >
          Export CSV
        </button>
      </div>
      <p className="lead-count">Total: {list.length}</p>
      {list.length === 0 ? (
        <div className="table-wrap">
          <div className="empty-state">No leads yet. Run a cycle or wait for new replies.</div>
        </div>
      ) : (
        <>
          {(selectedLead || detailLoading) && (
            <div ref={detailRef} className="card wide lead-detail" role="region" aria-label="Lead details">
              <div className="lead-detail-header">
                <h3>Lead details</h3>
                <button
                  type="button"
                  className="btn secondary"
                  onClick={() => { setSelectedLead(null); setSendResult(null); }}
                  aria-label="Close lead details"
                >
                  Close
                </button>
              </div>
              {detailLoading ? (
                <div className="loading-wrap">
                  <div className="spinner" aria-hidden />
                  <span>Loading lead…</span>
                </div>
              ) : selectedLead ? (
                <>
                  <dl className="lead-detail-dl">
                    <dt>Name</dt>
                    <dd>{selectedLead.lead_name || "—"}</dd>
                    <dt>Email / contact</dt>
                    <dd>
                      {selectedLead.channel === "email" && (selectedLead.email || selectedLead.lead_name) ? (
                        <a href={`mailto:${selectedLead.email || selectedLead.lead_name}`}>
                          {selectedLead.email || selectedLead.lead_name}
                        </a>
                      ) : selectedLead.channel === "linkedin" && selectedLead.linkedin_url ? (
                        <a href={selectedLead.linkedin_url} target="_blank" rel="noopener noreferrer">
                          {selectedLead.linkedin_url}
                        </a>
                      ) : (
                        selectedLead.lead_name || "—"
                      )}
                    </dd>
                    <dt>Company</dt>
                    <dd>{selectedLead.company || "—"}</dd>
                    <dt>Campaign</dt>
                    <dd>{selectedLead.campaign || "—"}</dd>
                    <dt>Their reply / message</dt>
                    <dd className="lead-detail-reply">{selectedLead.reply_text || "—"}</dd>
                    <dt>AI-generated reply</dt>
                    <dd className="lead-detail-suggested">{selectedLead.suggested_response || "—"}</dd>
                  </dl>
                  <div className="lead-detail-actions">
                    <button
                      type="button"
                      className="btn primary"
                      onClick={handleSendReply}
                      disabled={sending || !canReply(selectedLead)}
                      aria-label="Send reply to lead"
                    >
                      {sending ? "Sending…" : "Reply"}
                    </button>
                    {!canReply(selectedLead) && (
                      <span className="muted">Reply not available (missing email/LinkedIn metadata for this lead).</span>
                    )}
                    {sendResult && (
                      <span className={sendResult.ok ? "send-ok" : "send-error"} role="status">
                        {sendResult.message}
                      </span>
                    )}
                  </div>
                </>
              ) : null}
            </div>
          )}
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
                {list.map((lead) => (
                  <tr
                    key={lead.id}
                    onClick={() => onSelectLead(lead)}
                    className={selectedLead?.id === lead.id ? "selected" : ""}
                    role="button"
                    tabIndex={0}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" || e.key === " ") {
                        e.preventDefault();
                        onSelectLead(lead);
                      }
                    }}
                    aria-label={`View lead ${lead.lead_name}`}
                  >
                    <td>{lead.lead_name}</td>
                    <td>{lead.company || "—"}</td>
                    <td>
                      <span className={`badge channel`}>{lead.channel}</span>
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
        </>
      )}
    </section>
  );
}
