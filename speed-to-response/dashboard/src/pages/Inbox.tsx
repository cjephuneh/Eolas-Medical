import { useCallback, useEffect, useRef, useState } from "react";
import { api, type Lead, type EmailMessage } from "../api";

type InboxTab = "email" | "linkedin";

export function Inbox() {
  const [tab, setTab] = useState<InboxTab>("email");
  const [emails, setEmails] = useState<EmailMessage[]>([]);
  const [leads, setLeads] = useState<Lead[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedLead, setSelectedLead] = useState<Lead | null>(null);
  const [selectedEmail, setSelectedEmail] = useState<EmailMessage | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [sending, setSending] = useState(false);
  const [sendResult, setSendResult] = useState<{ ok: boolean; message: string } | null>(null);
  const detailRef = useRef<HTMLDivElement>(null);

  const loadEmailInbox = useCallback(() => {
    setLoading(true);
    setError(null);
    api
      .inboxEmail(100)
      .then((e) => setEmails(Array.isArray(e) ? e : []))
      .catch((err) => setError(err instanceof Error ? err.message : String(err)))
      .finally(() => setLoading(false));
  }, []);

  const loadLinkedInbox = useCallback(() => {
    setLoading(true);
    setError(null);
    api
      .inboxLinkedin()
      .then((l) => setLeads(Array.isArray(l) ? l : []))
      .catch((err) => setError(err instanceof Error ? err.message : String(err)))
      .finally(() => setLoading(false));
  }, []);

  const loadInbox = useCallback(() => {
    if (tab === "email") loadEmailInbox();
    else loadLinkedInbox();
  }, [tab, loadEmailInbox, loadLinkedInbox]);

  useEffect(() => {
    loadInbox();
  }, [loadInbox]);

  useEffect(() => {
    setSelectedLead(null);
    setSelectedEmail(null);
    setSendResult(null);
  }, [tab]);

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

  const canReply = (lead: Lead): boolean => Boolean(lead.linkedin_url);

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

  if (loading && emails.length === 0 && leads.length === 0) {
    return (
      <div className="loading-wrap">
        <div className="spinner" aria-hidden />
        <span>Loading inbox…</span>
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

  const emailList = Array.isArray(emails) ? emails : [];
  const leadList = Array.isArray(leads) ? leads : [];

  return (
    <section className="inbox" aria-label="Inbox">
      <div className="page-header">
        <div>
          <h1 className="page-title">Inbox</h1>
          <p className="page-subtitle">
            {tab === "email"
              ? "Prospect senders only (Instantly). Rows where From is your mailbox show the external contact as sender. Set EXCLUDE_SENDER_EMAILS or EXCLUDE_SENDER_DOMAINS in .env."
              : "LinkedIn messages from Prosp. Run a cycle to pull the latest."}
          </p>
        </div>
        <div className="page-header-actions">
          <div className="inbox-tabs" role="tablist" aria-label="Inbox type">
            <button
              type="button"
              role="tab"
              aria-selected={tab === "email"}
              className={tab === "email" ? "tab active" : "tab"}
              onClick={() => setTab("email")}
            >
              Email
            </button>
            <button
              type="button"
              role="tab"
              aria-selected={tab === "linkedin"}
              className={tab === "linkedin" ? "tab active" : "tab"}
              onClick={() => setTab("linkedin")}
            >
              LinkedIn
            </button>
          </div>
          <button
            type="button"
            className="btn primary"
            onClick={loadInbox}
            disabled={loading}
            aria-label="Refresh inbox"
          >
            {loading ? "Loading…" : "Refresh"}
          </button>
        </div>
      </div>

      {tab === "email" && (
        <>
          <p className="lead-count">Total: {emailList.length}</p>
          {selectedEmail && (
                <div ref={detailRef} className="card wide lead-detail" role="region" aria-label="Email detail">
                  <div className="lead-detail-header">
                    <h3>Email — {selectedEmail.lead_name || selectedEmail.email || "—"}</h3>
                    <button
                      type="button"
                      className="btn secondary"
                      onClick={() => setSelectedEmail(null)}
                      aria-label="Close"
                    >
                      Close
                    </button>
                  </div>
                  <dl className="lead-detail-dl">
                    <dt>Sender (respondent)</dt>
                    <dd>
                      <a href={`mailto:${selectedEmail.email}`}>{selectedEmail.email || selectedEmail.lead_name || "—"}</a>
                    </dd>
                    {selectedEmail.our_mailbox || selectedEmail.from_email ? (
                      <>
                        <dt>Your mailbox</dt>
                        <dd className="muted">{selectedEmail.our_mailbox || selectedEmail.from_email}</dd>
                      </>
                    ) : null}
                    <dt>Company</dt>
                    <dd>{selectedEmail.company || "—"}</dd>
                    <dt>Campaign</dt>
                    <dd>{selectedEmail.campaign || "—"}</dd>
                    <dt>Date</dt>
                    <dd>{selectedEmail.timestamp ? new Date(selectedEmail.timestamp).toLocaleString() : "—"}</dd>
                    <dt>Message</dt>
                    <dd className="lead-detail-reply">{selectedEmail.reply_text || "—"}</dd>
                  </dl>
                </div>
              )}
              {emailList.length === 0 ? (
                <div className="table-wrap">
                  <div className="empty-state">No email messages. Check Instantly connection and EXCLUDE_SENDER_EMAILS.</div>
                </div>
              ) : (
                <div className="table-wrap">
                  <table>
                    <thead>
                      <tr>
                        <th>Sender</th>
                        <th>Message</th>
                        <th>Campaign</th>
                        <th>Date</th>
                      </tr>
                    </thead>
                    <tbody>
                      {emailList.map((msg) => (
                        <tr
                          key={msg.id}
                          onClick={() => setSelectedEmail(msg)}
                          className={selectedEmail?.id === msg.id ? "selected" : ""}
                          role="button"
                          tabIndex={0}
                          onKeyDown={(e) => {
                            if (e.key === "Enter" || e.key === " ") {
                              e.preventDefault();
                              setSelectedEmail(msg);
                            }
                          }}
                          aria-label={`View email from ${msg.lead_name || msg.email}`}
                        >
                          <td>{msg.email || msg.lead_name || "—"}</td>
                          <td className="message-preview">
                            {(msg.reply_text || "").replace(/\s+/g, " ").trim().slice(0, 60)}
                            {(msg.reply_text || "").length > 60 ? "…" : ""}
                          </td>
                          <td>{msg.campaign || "—"}</td>
                          <td>{msg.timestamp ? new Date(msg.timestamp).toLocaleString() : "—"}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
        </>
      )}

      {tab === "linkedin" && (
        <>
          <p className="lead-count">Total: {leadList.length}</p>
          {leadList.length === 0 ? (
            <div className="table-wrap">
              <div className="empty-state">
                No LinkedIn messages yet. Run a cycle to pull replies from Prosp campaigns.
              </div>
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
                      onClick={() => {
                        setSelectedLead(null);
                        setSendResult(null);
                      }}
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
                        <dt>LinkedIn</dt>
                        <dd>
                          {selectedLead.linkedin_url ? (
                            <a
                              href={selectedLead.linkedin_url}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="campaign-lead-link"
                            >
                              View profile
                            </a>
                          ) : (
                            "—"
                          )}
                        </dd>
                        <dt>Company</dt>
                        <dd>{selectedLead.company || "—"}</dd>
                        <dt>Campaign</dt>
                        <dd>{selectedLead.campaign || "—"}</dd>
                        <dt>Their message</dt>
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
                          <span className="muted">Reply not available (missing LinkedIn URL for this lead).</span>
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
                      <th>Classification</th>
                      <th>Notified</th>
                    </tr>
                  </thead>
                  <tbody>
                    {leadList.map((lead) => (
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
        </>
      )}
    </section>
  );
}
