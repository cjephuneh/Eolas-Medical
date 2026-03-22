import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api, type Lead } from "../api";
import { buildEditableReplyFromLead } from "../utils/suggestedReply";

const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";

type LeadFilterTab = "all" | "pending" | "replied";

function leadIsReplied(lead: Lead): boolean {
  return Boolean((lead.replied_at || "").trim());
}

export function Leads() {
  const [leads, setLeads] = useState<Lead[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedLead, setSelectedLead] = useState<Lead | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [sending, setSending] = useState(false);
  const [sendResult, setSendResult] = useState<{ ok: boolean; message: string } | null>(null);
  const [replyDraft, setReplyDraft] = useState("");
  const [filterTab, setFilterTab] = useState<LeadFilterTab>("all");
  const detailRef = useRef<HTMLDivElement>(null);

  const loadLeads = useCallback(() => {
    api
      .leads()
      .then((l) =>
        setLeads(
          Array.isArray(l)
            ? l.filter((x) => (x.channel || "").toLowerCase() === "email")
            : []
        )
      )
      .catch((err) => setError(err instanceof Error ? err.message : String(err)))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    loadLeads();
  }, [loadLeads]);

  useEffect(() => {
    if (!selectedLead) return;
    setReplyDraft(buildEditableReplyFromLead(selectedLead));
  }, [selectedLead?.id, selectedLead?.suggested_response]);

  const list = Array.isArray(leads) ? leads : [];

  const statusCounts = useMemo(() => {
    let pending = 0;
    let replied = 0;
    for (const l of list) {
      if (leadIsReplied(l)) replied += 1;
      else pending += 1;
    }
    return { all: list.length, pending, replied };
  }, [list]);

  const filteredList = useMemo(() => {
    if (filterTab === "pending") return list.filter((l) => !leadIsReplied(l));
    if (filterTab === "replied") return list.filter((l) => leadIsReplied(l));
    return list;
  }, [list, filterTab]);

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
      const uuid =
        (lead.reply_to_uuid || "").trim() ||
        (lead.id.startsWith("instantly:") ? lead.id.slice("instantly:".length) : "");
      const to = (lead.email || lead.lead_name || "").trim();
      const hasRecipient = to.includes("@");
      return Boolean(uuid && hasRecipient);
    }
    if (lead.channel === "linkedin") {
      return Boolean(lead.linkedin_url);
    }
    return false;
  };

  const handleSendReply = () => {
    if (!selectedLead) return;
    const full = replyDraft.trim();
    if (!full) {
      setSendResult({ ok: false, message: "No reply text to send. Edit the response above or add text." });
      return;
    }
    setSending(true);
    setSendResult(null);
    const leadId = selectedLead.id;
    api
      .sendReply(leadId, full)
      .then((res) => {
        const ts = (res.replied_at || "").trim() || new Date().toISOString();
        setSendResult({ ok: true, message: "Reply sent." });
        setSelectedLead((prev) => (prev && prev.id === leadId ? { ...prev, replied_at: ts } : prev));
        setLeads((prev) => prev.map((l) => (l.id === leadId ? { ...l, replied_at: ts } : l)));
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
        <span>Loading emails…</span>
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

  return (
    <section className="leads">
      <div className="page-header">
        <div>
          <h1 className="page-title">Emails</h1>
          <p className="page-subtitle">Processed email replies from Instantly. Run a cycle to pull the latest into this list.</p>
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
      <div className="leads-toolbar">
        <p className="lead-count" role="status">
          Total: {statusCounts.all}
          <span className="lead-count-sep" aria-hidden>
            {" "}
            ·{" "}
          </span>
          <span className="muted">Pending: {statusCounts.pending}</span>
          <span className="lead-count-sep" aria-hidden>
            {" "}
            ·{" "}
          </span>
          <span className="muted">Replied: {statusCounts.replied}</span>
        </p>
        <div className="lead-filter-tabs" role="tablist" aria-label="Filter by reply status">
          {(
            [
              { id: "all" as const, label: "All" },
              { id: "pending" as const, label: "Pending" },
              { id: "replied" as const, label: "Replied" },
            ] as const
          ).map(({ id, label }) => (
            <button
              key={id}
              type="button"
              role="tab"
              aria-selected={filterTab === id}
              aria-controls="emails-table-panel"
              id={`filter-tab-${id}`}
              className={`btn filter-tab ${filterTab === id ? "active" : "secondary"}`}
              onClick={() => setFilterTab(id)}
            >
              {label}
              {id === "all" ? ` (${statusCounts.all})` : id === "pending" ? ` (${statusCounts.pending})` : ` (${statusCounts.replied})`}
            </button>
          ))}
        </div>
      </div>
      {list.length === 0 ? (
        <div className="table-wrap">
          <div className="empty-state">No email leads yet. Run a cycle or wait for new replies.</div>
        </div>
      ) : filteredList.length === 0 ? (
        <div className="table-wrap">
          <div className="empty-state" role="status">
            No leads match this filter. Try <strong>All</strong> or another tab.
          </div>
        </div>
      ) : (
        <>
          {(selectedLead || detailLoading) && (
            <div ref={detailRef} className="card wide lead-detail" role="region" aria-label="Email details">
              <div className="lead-detail-header">
                <h3>Email details</h3>
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
                    <dt>Sender (respondent)</dt>
                    <dd>
                      {(selectedLead.email || selectedLead.lead_name) ? (
                        <a href={`mailto:${selectedLead.email || selectedLead.lead_name}`}>
                          {selectedLead.email || selectedLead.lead_name}
                        </a>
                      ) : (
                        "—"
                      )}
                    </dd>
                    {selectedLead.from_email ? (
                      <>
                        <dt>Your mailbox (received at)</dt>
                        <dd className="muted">{selectedLead.from_email}</dd>
                      </>
                    ) : null}
                    <dt>Company</dt>
                    <dd>{selectedLead.company || "—"}</dd>
                    <dt>Campaign</dt>
                    <dd>{selectedLead.campaign || "—"}</dd>
                    <dt>Reply status</dt>
                    <dd>
                      {leadIsReplied(selectedLead) ? (
                        <span className="badge replied">
                          Replied
                          {selectedLead.replied_at ? (
                            <span className="replied-at"> · {new Date(selectedLead.replied_at).toLocaleString()}</span>
                          ) : null}
                        </span>
                      ) : (
                        <span className="badge pending-reply">Pending</span>
                      )}
                    </dd>
                    <dt>Their reply</dt>
                    <dd className="lead-detail-reply">{selectedLead.reply_text || "—"}</dd>
                    <dt id="email-response-label">Email response</dt>
                    <dd className="lead-detail-reply-edit-wrap">
                      <textarea
                        id="email-response-draft"
                        className="lead-detail-reply-textarea"
                        rows={12}
                        value={replyDraft}
                        onChange={(e) => setReplyDraft(e.target.value)}
                        aria-labelledby="email-response-label"
                        aria-describedby="email-response-hint"
                        disabled={detailLoading}
                      />
                      <p id="email-response-hint" className="muted small-hint reply-edit-hint">
                        Edit before sending. Sign-off from the AI suggestion is included; you can change it here.
                      </p>
                      <button
                        type="button"
                        className="btn secondary btn-reset-reply"
                        onClick={() => setReplyDraft(buildEditableReplyFromLead(selectedLead))}
                        disabled={sending || detailLoading}
                        aria-label="Reset email response to original AI suggestion"
                      >
                        Reset to original
                      </button>
                    </dd>
                  </dl>
                  <div className="lead-detail-actions">
                    <button
                      type="button"
                      className="btn primary"
                      onClick={handleSendReply}
                      disabled={sending || !canReply(selectedLead) || !replyDraft.trim()}
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
          <div className="table-wrap" id="emails-table-panel" role="tabpanel" aria-labelledby={`filter-tab-${filterTab}`}>
            <table>
              <thead>
                <tr>
                  <th>Sender</th>
                  <th>Company</th>
                  <th>Status</th>
                  <th>Channel</th>
                  <th>Classification</th>
                  <th>Notified</th>
                </tr>
              </thead>
              <tbody>
                {filteredList.map((lead) => (
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
                    aria-label={`View lead ${lead.channel === "email" ? lead.email || lead.lead_name : lead.lead_name}`}
                  >
                    <td>
                      {lead.channel === "email"
                        ? (lead.email || lead.lead_name || "—")
                        : (lead.lead_name || "—")}
                    </td>
                    <td>{lead.company || "—"}</td>
                    <td>
                      {leadIsReplied(lead) ? (
                        <span className="badge replied">Replied</span>
                      ) : (
                        <span className="badge pending-reply">Pending</span>
                      )}
                    </td>
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
