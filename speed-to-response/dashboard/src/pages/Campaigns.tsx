import { useCallback, useEffect, useRef, useState } from "react";
import {
  api,
  type CampaignLeadWithMessages,
  type CampaignLeadsResponse,
  type ProspCampaign,
} from "../api";

export function Campaigns() {
  const [campaigns, setCampaigns] = useState<ProspCampaign[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedCampaign, setSelectedCampaign] = useState<ProspCampaign | null>(null);
  const [leadsData, setLeadsData] = useState<CampaignLeadsResponse | null>(null);
  const [leadsLoading, setLeadsLoading] = useState(false);
  const [leadsError, setLeadsError] = useState<string | null>(null);
  const detailRef = useRef<HTMLDivElement>(null);
  const [expandedLeadUrl, setExpandedLeadUrl] = useState<string | null>(null);
  const [draftMessage, setDraftMessage] = useState("");
  const [sendingLead, setSendingLead] = useState(false);
  const [generateLoading, setGenerateLoading] = useState(false);
  const [bulkDescription, setBulkDescription] = useState("");
  const [bulkTemplate, setBulkTemplate] = useState("");
  const [bulkSending, setBulkSending] = useState(false);
  const [bulkGenerateLoading, setBulkGenerateLoading] = useState(false);
  const [bulkResult, setBulkResult] = useState<{ sent: number; failed: number; total: number } | null>(null);

  const loadCampaigns = useCallback(() => {
    api
      .campaigns()
      .then((c) => setCampaigns(Array.isArray(c) ? c : []))
      .catch((err) => setError(err instanceof Error ? err.message : String(err)))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    loadCampaigns();
  }, [loadCampaigns]);

  const onSelectCampaign = (c: ProspCampaign) => {
    const cid = c.campaign_id || "";
    if (!cid) return;
    setLeadsError(null);
    setLeadsData(null);
    setSelectedCampaign(c);
    setLeadsLoading(true);
    api
      .campaignLeads(cid)
      .then((data) => {
        setLeadsData(data);
        setLeadsLoading(false);
        requestAnimationFrame(() =>
          detailRef.current?.scrollIntoView({ behavior: "smooth", block: "start" })
        );
      })
      .catch((err) => {
        setLeadsError(err instanceof Error ? err.message : String(err));
        setLeadsLoading(false);
      });
  };

  const closeDetail = () => {
    setSelectedCampaign(null);
    setLeadsData(null);
    setLeadsError(null);
    setExpandedLeadUrl(null);
    setBulkResult(null);
    setBulkTemplate("");
  };

  const handleGenerateForLead = (lead: CampaignLeadWithMessages) => {
    setGenerateLoading(true);
    api
      .generateProspMessage(lead.name || "there", leadsData?.campaign_name || "")
      .then((r) => setDraftMessage(r.message || ""))
      .finally(() => setGenerateLoading(false));
  };

  const handleSendToLead = (lead: CampaignLeadWithMessages) => {
    if (!lead.linkedin_url || !draftMessage.trim()) return;
    setSendingLead(true);
    api
      .sendProspMessage(lead.linkedin_url, draftMessage.trim())
      .then(() => {
        setExpandedLeadUrl(null);
        setDraftMessage("");
      })
      .finally(() => setSendingLead(false));
  };

  const handleBulkGenerate = () => {
    if (!selectedCampaign?.campaign_id) return;
    setBulkGenerateLoading(true);
    setBulkResult(null);
    api
      .generateBulkMessage(selectedCampaign.campaign_id, bulkDescription)
      .then((r) => setBulkTemplate(r.message_template || ""))
      .finally(() => setBulkGenerateLoading(false));
  };

  const handleBulkSend = () => {
    if (!selectedCampaign?.campaign_id || !bulkTemplate.trim()) return;
    setBulkSending(true);
    setBulkResult(null);
    api
      .sendBulkMessage(selectedCampaign.campaign_id, bulkTemplate.trim())
      .then((r) => setBulkResult({ sent: r.sent, failed: r.failed, total: r.total }))
      .finally(() => setBulkSending(false));
  };

  if (loading) {
    return (
      <div className="loading-wrap">
        <div className="spinner" aria-hidden />
        <span>Loading campaigns…</span>
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
    <section className="campaigns">
      <h1 className="page-title">Campaigns</h1>
      <p className="page-subtitle">All Prosp campaigns (api/v1/campaigns/lists). Click a campaign to see leads and comments.</p>
      {campaigns.length === 0 ? (
        <div className="card wide">
          <p className="muted">No campaigns or PROSP_API_KEY not set.</p>
        </div>
      ) : (
        <>
          {(selectedCampaign || leadsLoading) && (
            <div
              ref={detailRef}
              className="card wide campaign-detail"
              role="region"
              aria-label="Campaign leads and comments"
            >
              <div className="lead-detail-header">
                <h3>
                  {selectedCampaign?.campaign_name || "Campaign"} — leads & comments
                </h3>
                <button
                  type="button"
                  className="btn secondary"
                  onClick={closeDetail}
                  aria-label="Close campaign detail"
                >
                  Close
                </button>
              </div>
              {leadsLoading ? (
                <div className="loading-wrap">
                  <div className="spinner" aria-hidden />
                  <span>Loading leads and conversations (parallel fetch)…</span>
                </div>
              ) : leadsError ? (
                <p className="error-msg">{leadsError}</p>
              ) : leadsData?.error ? (
                <p className="error-msg">{leadsData.error}</p>
              ) : leadsData?.leads && leadsData.leads.length > 0 ? (
                <>
                  {leadsData.leads_count > leadsData.leads.length && (
                    <p className="muted campaign-leads-hint">
                      Showing first {leadsData.leads.length} of {leadsData.leads_count} leads (faster load).
                    </p>
                  )}
                  <div className="campaign-bulk-send card">
                    <h4>Send message to all leads in this campaign</h4>
                    <p className="muted">Optional: add campaign description so AI can tailor the message.</p>
                    <textarea
                      className="campaign-compose-input"
                      placeholder="Campaign description (optional)"
                      value={bulkDescription}
                      onChange={(e) => setBulkDescription(e.target.value)}
                      rows={2}
                      aria-label="Campaign description for AI"
                    />
                    <div className="campaign-compose-actions">
                      <button
                        type="button"
                        className="btn secondary"
                        onClick={handleBulkGenerate}
                        disabled={bulkGenerateLoading || !selectedCampaign?.campaign_id}
                        aria-label="Generate message with AI"
                      >
                        {bulkGenerateLoading ? "Generating…" : "Generate with AI"}
                      </button>
                    </div>
                    <textarea
                      className="campaign-compose-input"
                      placeholder="Message template (use {name} for first name). Generate with AI above, then edit and Send to all."
                      value={bulkTemplate}
                      onChange={(e) => setBulkTemplate(e.target.value)}
                      rows={4}
                      aria-label="Bulk message template"
                    />
                    <div className="campaign-compose-actions">
                      <button
                        type="button"
                        className="btn primary"
                        onClick={handleBulkSend}
                        disabled={bulkSending || !bulkTemplate.trim()}
                        aria-label="Send to all leads"
                      >
                        {bulkSending ? "Sending…" : "Send to all leads"}
                      </button>
                      {bulkResult && (
                        <span className="muted" role="status">
                          Sent {bulkResult.sent} / {bulkResult.total}
                          {bulkResult.failed > 0 && `, ${bulkResult.failed} failed`}
                        </span>
                      )}
                    </div>
                  </div>
                <div className="campaign-leads-list">
                  {leadsData.leads.map((lead, idx) => (
                    <div key={lead.linkedin_url || idx} className="campaign-lead-block">
                      <div className="campaign-lead-head">
                        <strong>{lead.name || "—"}</strong>
                        {lead.company && (
                          <span className="muted"> · {lead.company}</span>
                        )}
                        {lead.linkedin_url && (
                          <a
                            href={lead.linkedin_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="campaign-lead-link"
                          >
                            LinkedIn
                          </a>
                        )}
                        <span className="muted"> · {lead.messages_count} message(s)</span>
                        {lead.linkedin_url && (
                          <button
                            type="button"
                            className="btn small"
                            onClick={(e) => {
                              e.stopPropagation();
                              setExpandedLeadUrl(expandedLeadUrl === lead.linkedin_url ? null : lead.linkedin_url);
                              if (expandedLeadUrl !== lead.linkedin_url) setDraftMessage("");
                            }}
                            aria-label={`Send message to ${lead.name}`}
                          >
                            Send message
                          </button>
                        )}
                      </div>
                      {expandedLeadUrl === lead.linkedin_url && (
                        <div className="campaign-lead-compose">
                          <button
                            type="button"
                            className="btn secondary"
                            onClick={() => handleGenerateForLead(lead)}
                            disabled={generateLoading}
                            aria-label="Generate with AI"
                          >
                            {generateLoading ? "Generating…" : "Generate with AI"}
                          </button>
                          <textarea
                            className="campaign-compose-input"
                            placeholder="Message (starts with Hello [name])"
                            value={draftMessage}
                            onChange={(e) => setDraftMessage(e.target.value)}
                            rows={4}
                            aria-label="Message to send"
                          />
                          <div className="campaign-compose-actions">
                            <button
                              type="button"
                              className="btn primary"
                              onClick={() => handleSendToLead(lead)}
                              disabled={sendingLead || !draftMessage.trim()}
                              aria-label="Send message"
                            >
                              {sendingLead ? "Sending…" : "Send"}
                            </button>
                          </div>
                        </div>
                      )}
                      <ul className="campaign-messages">
                        {lead.messages.length === 0 ? (
                          <li className="muted">No messages</li>
                        ) : (
                          lead.messages.map((msg, midx) => (
                            <li
                              key={midx}
                              className={msg.from_me ? "message-from-me" : "message-from-lead"}
                            >
                              <span className="message-meta">
                                {msg.from_me ? "You" : lead.name} · {msg.created_at || "—"}
                              </span>
                              <div className="message-content">{msg.content || "—"}</div>
                            </li>
                          ))
                        )}
                      </ul>
                    </div>
                  ))}
                </div>
                </>
              ) : (
                <p className="muted">No leads or no conversations for this campaign.</p>
              )}
            </div>
          )}
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Campaign name</th>
                  <th>Campaign ID</th>
                </tr>
              </thead>
              <tbody>
                {campaigns.map((c) => (
                  <tr
                    key={c.campaign_id || c.campaign_name}
                    onClick={() => onSelectCampaign(c)}
                    className={
                      selectedCampaign?.campaign_id === c.campaign_id ? "selected" : ""
                    }
                    role="button"
                    tabIndex={0}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" || e.key === " ") {
                        e.preventDefault();
                        onSelectCampaign(c);
                      }
                    }}
                    aria-label={`View leads and comments for ${c.campaign_name}`}
                  >
                    <td>{c.campaign_name || "—"}</td>
                    <td>
                      <code className="campaign-id">{c.campaign_id || "—"}</code>
                    </td>
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
