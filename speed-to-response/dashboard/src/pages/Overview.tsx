import { useRef, useEffect, useState } from "react";
import { api, type Health, type Lead, type SourcesResponse } from "../api";

function messagePreview(text: string, maxLen: number = 80): string {
  if (!text || !String(text).trim()) return "—";
  const s = String(text).replace(/\s+/g, " ").trim();
  return s.length <= maxLen ? s : s.slice(0, maxLen) + "…";
}

function leadFirstName(lead: Lead): string {
  const name = (lead.lead_name || "").trim();
  if (!name) return "there";
  if (name.includes("@")) return name.split("@")[0].trim() || "there";
  const first = name.split(/\s+/)[0]?.trim();
  return first ? first.charAt(0).toUpperCase() + first.slice(1).toLowerCase() : "there";
}

const SENDER_NAME = (import.meta.env.VITE_SENDER_NAME as string)?.trim() || "Eolas";

function personalizeReply(text: string, lead: Lead): string {
  if (!text || !String(text).trim()) return text;
  const first = leadFirstName(lead);
  let out = String(text)
    .replace(/\[Name\]/gi, first)
    .replace(/\[Lead's Name\]/gi, first)
    .replace(/\[Lead Name\]/gi, first)
    .replace(/\[Recipient's Name\]/gi, first)
    .replace(/\[Recipient\]/gi, first)
    .replace(/\[lead name\]/gi, first);
  out = out.replace(/\[Your name\]/gi, SENDER_NAME);
  return out;
}

export function Overview() {
  const [health, setHealth] = useState<Health | null>(null);
  const [leads, setLeads] = useState<Lead[]>([]);
  const [sources, setSources] = useState<SourcesResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedLead, setSelectedLead] = useState<Lead | null>(null);
  const [sending, setSending] = useState(false);
  const [sendResult, setSendResult] = useState<{ ok: boolean; message: string } | null>(null);
  const detailRef = useRef<HTMLDivElement>(null);

  const canReply = (lead: Lead): boolean => {
    if (lead.channel === "email") return Boolean(lead.reply_to_uuid && (lead.email || lead.lead_name));
    if (lead.channel === "linkedin") return Boolean(lead.linkedin_url);
    return false;
  };

  const handleSendReply = () => {
    if (!selectedLead) return;
    const body = personalizeReply(selectedLead.suggested_response || "", selectedLead);
    if (!body.trim()) {
      setSendResult({ ok: false, message: "No reply to send." });
      return;
    }
    setSending(true);
    setSendResult(null);
    api
      .sendReply(selectedLead.id, body)
      .then(() => setSendResult({ ok: true, message: "Reply sent." }))
      .catch((err) => setSendResult({ ok: false, message: err instanceof Error ? err.message : String(err) }))
      .finally(() => setSending(false));
  };

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

  useEffect(() => {
    if (selectedLead && detailRef.current) {
      detailRef.current.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  }, [selectedLead]);

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

  const recentLeads = leads.slice(0, 15);
  const instCount = sources?.instantly?.count ?? 0;
  const prospCount = sources?.prosp?.count ?? 0;

  return (
    <section className="overview">
      <h1 className="page-title">Overview</h1>
      <p className="page-subtitle">Speed-to-response at a glance. Click a message to see full text and generated reply.</p>
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

      {selectedLead && (
        <div ref={detailRef} className="card wide lead-detail overview-message-detail" role="region" aria-label="Message detail">
          <div className="lead-detail-header">
            <h3>Message — {selectedLead.lead_name || "—"} ({selectedLead.channel})</h3>
            <button
              type="button"
              className="btn secondary"
              onClick={() => { setSelectedLead(null); setSendResult(null); }}
              aria-label="Close message detail"
            >
              Close
            </button>
          </div>
          <dl className="lead-detail-dl">
            <dt>Their message</dt>
            <dd className="lead-detail-reply">{selectedLead.reply_text || "—"}</dd>
            <dt>Generated reply (prefilled with {leadFirstName(selectedLead)} and {SENDER_NAME})</dt>
            <dd className="lead-detail-suggested">{personalizeReply(selectedLead.suggested_response || "", selectedLead) || "—"}</dd>
          </dl>
          <div className="lead-detail-actions">
            <button
              type="button"
              className="btn primary"
              onClick={handleSendReply}
              disabled={sending || !canReply(selectedLead)}
              aria-label="Send reply to lead"
            >
              {sending ? "Sending…" : "Send"}
            </button>
            {!canReply(selectedLead) && (
              <span className="muted">Send not available (missing reply metadata for this lead).</span>
            )}
            {sendResult && (
              <span className={sendResult.ok ? "send-ok" : "send-error"} role="status">
                {sendResult.message}
              </span>
            )}
          </div>
        </div>
      )}

      <div className="card wide">
        <h3>Recent messages</h3>
        {recentLeads.length === 0 ? (
          <p className="muted">No messages yet. Run a cycle or wait for the next poll.</p>
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Lead</th>
                  <th>Message</th>
                  <th>Channel</th>
                  <th>Classification</th>
                  <th>Notified</th>
                </tr>
              </thead>
              <tbody>
                {recentLeads.map((lead) => (
                  <tr
                    key={lead.id}
                    onClick={() => setSelectedLead(lead)}
                    className={selectedLead?.id === lead.id ? "selected" : ""}
                    role="button"
                    tabIndex={0}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" || e.key === " ") {
                        e.preventDefault();
                        setSelectedLead(lead);
                      }
                    }}
                    aria-label={`View message from ${lead.lead_name}`}
                  >
                    <td>{lead.lead_name || "—"}</td>
                    <td className="message-preview">{messagePreview(lead.reply_text)}</td>
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
