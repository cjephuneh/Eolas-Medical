import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  api,
  type CampaignLeadWithMessages,
  type CampaignLeadsResponse,
  type ProspCampaign,
} from "../api";

type CampaignMessageFilterTab = "all" | "with_messages" | "no_messages";

export function Campaigns() {
  const [campaigns, setCampaigns] = useState<ProspCampaign[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedCampaign, setSelectedCampaign] = useState<ProspCampaign | null>(null);
  const [leadsData, setLeadsData] = useState<CampaignLeadsResponse | null>(null);
  const [leadsLoading, setLeadsLoading] = useState(false);
  const [leadsError, setLeadsError] = useState<string | null>(null);
  const detailRef = useRef<HTMLDivElement>(null);
  const [expandedLeadKey, setExpandedLeadKey] = useState<string | null>(null);
  const [draftByLead, setDraftByLead] = useState<Record<string, string>>({});
  const [sendingKey, setSendingKey] = useState<string | null>(null);
  const [generateKey, setGenerateKey] = useState<string | null>(null);
  const [bulkDescription, setBulkDescription] = useState("");
  const [bulkTemplate, setBulkTemplate] = useState("");
  const [bulkSending, setBulkSending] = useState(false);
  const [bulkGenerateLoading, setBulkGenerateLoading] = useState(false);
  const [bulkResult, setBulkResult] = useState<{ sent: number; failed: number; total: number } | null>(null);
  const [leadSearch, setLeadSearch] = useState("");
  const [leadMessageTab, setLeadMessageTab] = useState<CampaignMessageFilterTab>("all");

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
    setLeadSearch("");
    setLeadMessageTab("all");
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
    setExpandedLeadKey(null);
    setDraftByLead({});
    setBulkResult(null);
    setBulkTemplate("");
    setLeadSearch("");
    setLeadMessageTab("all");
  };

  const showCampaignDetail = Boolean(selectedCampaign || leadsLoading);

  const leadMessageStats = useMemo(() => {
    const rows = leadsData?.leads;
    if (!rows || !Array.isArray(rows)) {
      return { total: 0, withMessages: 0, noMessages: 0 };
    }
    let withMessages = 0;
    for (const l of rows) {
      if (Array.isArray(l.messages) && l.messages.length > 0) withMessages += 1;
    }
    return {
      total: rows.length,
      withMessages,
      noMessages: rows.length - withMessages,
    };
  }, [leadsData?.leads]);

  const filteredCampaignLeads = useMemo(() => {
    const rows = leadsData?.leads;
    if (!rows || !Array.isArray(rows)) return [];
    let out = rows;
    if (leadMessageTab === "with_messages") {
      out = out.filter((l) => (l.messages?.length ?? 0) > 0);
    } else if (leadMessageTab === "no_messages") {
      out = out.filter((l) => (l.messages?.length ?? 0) === 0);
    }
    const q = leadSearch.trim().toLowerCase();
    if (!q) return out;
    return out.filter((l) => {
      const name = (l.name || "").toLowerCase();
      const company = (l.company || "").toLowerCase();
      const url = (l.linkedin_url || "").toLowerCase();
      return name.includes(q) || company.includes(q) || url.includes(q);
    });
  }, [leadsData?.leads, leadSearch, leadMessageTab]);

  const leadRowKey = (lead: CampaignLeadWithMessages, idx: number): string => {
    const u = (lead.linkedin_url || "").trim();
    return u || `lead-${idx}-${lead.name || "unknown"}`;
  };

  const handleGenerateForLead = (lead: CampaignLeadWithMessages, idx: number) => {
    const key = leadRowKey(lead, idx);
    setGenerateKey(key);
    const name = lead.name || "there";
    const campaignName = leadsData?.campaign_name || "";
    const hasThread = Array.isArray(lead.messages) && lead.messages.length > 0;
    const gen = hasThread
      ? api.generateProspReply({
          name,
          campaign_name: campaignName,
          messages: lead.messages.map((m) => ({
            content: m.content || "",
            from_me: m.from_me,
          })),
        })
      : api.generateProspMessage(name, campaignName);
    gen
      .then((r) => {
        setDraftByLead((prev) => ({ ...prev, [key]: r.message || "" }));
      })
      .finally(() => setGenerateKey(null));
  };

  const handleSendToLead = (lead: CampaignLeadWithMessages, idx: number) => {
    const key = leadRowKey(lead, idx);
    const text = (draftByLead[key] || "").trim();
    if (!lead.linkedin_url || !text) return;
    setSendingKey(key);
    api
      .sendProspMessage(lead.linkedin_url, text)
      .then(() => {
        setExpandedLeadKey(null);
        setDraftByLead((prev) => {
          const next = { ...prev };
          delete next[key];
          return next;
        });
      })
      .finally(() => setSendingKey(null));
  };

  const setDraftForLead = (key: string, value: string) => {
    setDraftByLead((prev) => ({ ...prev, [key]: value }));
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
      {!showCampaignDetail && (
        <>
          <h1 className="page-title">LinkedIn</h1>
          <p className="page-subtitle">
            Choose a campaign to open it only on this page — leads, threads, and reply in one place.
          </p>
        </>
      )}
      {campaigns.length === 0 ? (
        <div className="card wide">
          <p className="muted">No campaigns or PROSP_API_KEY not set.</p>
        </div>
      ) : (
        <>
          {showCampaignDetail && (
            <div
              ref={detailRef}
              className="card wide campaign-detail campaign-detail-focused"
              role="region"
              aria-label="Campaign leads and LinkedIn messages"
            >
              <div className="focused-view-nav">
                <button
                  type="button"
                  className="btn secondary focused-view-back"
                  onClick={closeDetail}
                  aria-label="Back to all campaigns"
                >
                  ← All campaigns
                </button>
              </div>
              <div className="lead-detail-header">
                <h3>
                  {selectedCampaign?.campaign_name || "Campaign"} — leads &amp; messages
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
                  <div className="campaign-metrics" role="region" aria-label="Campaign lead and message counts">
                    <div className="campaign-metric-card">
                      <span className="campaign-metric-value">{leadMessageStats.total}</span>
                      <span className="campaign-metric-label">Leads loaded</span>
                    </div>
                    <div className="campaign-metric-card">
                      <span className="campaign-metric-value">{leadMessageStats.withMessages}</span>
                      <span className="campaign-metric-label">With conversation</span>
                    </div>
                    <div className="campaign-metric-card">
                      <span className="campaign-metric-value">{leadMessageStats.noMessages}</span>
                      <span className="campaign-metric-label">No thread yet</span>
                    </div>
                  </div>
                  <div className="campaign-lead-toolbar">
                    <div className="lead-filter-tabs campaign-message-tabs" role="tablist" aria-label="Filter by messages">
                      {(
                        [
                          { id: "all" as const, label: "All leads", count: leadMessageStats.total },
                          { id: "with_messages" as const, label: "With messages", count: leadMessageStats.withMessages },
                          { id: "no_messages" as const, label: "No messages", count: leadMessageStats.noMessages },
                        ] as const
                      ).map(({ id, label, count }) => (
                        <button
                          key={id}
                          type="button"
                          role="tab"
                          aria-selected={leadMessageTab === id}
                          className={`btn filter-tab ${leadMessageTab === id ? "active" : "secondary"}`}
                          onClick={() => setLeadMessageTab(id)}
                        >
                          {label} ({count})
                        </button>
                      ))}
                    </div>
                    <div className="campaign-lead-filter">
                      <label htmlFor="campaign-lead-search" className="sr-only">
                        Filter leads by name or company
                      </label>
                      <input
                        id="campaign-lead-search"
                        type="search"
                        className="campaign-lead-search-input"
                        placeholder="Search name, company, LinkedIn URL…"
                        value={leadSearch}
                        onChange={(e) => setLeadSearch(e.target.value)}
                        aria-label="Search leads in this campaign"
                      />
                    </div>
                  </div>
                <div className="campaign-leads-list">
                  {filteredCampaignLeads.length === 0 ? (
                    <p className="muted" role="status">
                      {leadSearch.trim() || leadMessageTab !== "all"
                        ? "No leads match these filters. Clear search, choose All leads, or try another tab."
                        : null}
                    </p>
                  ) : null}
                  {filteredCampaignLeads.map((lead, idx) => {
                    const rowKey = leadRowKey(lead, idx);
                    const isOpen = expandedLeadKey === rowKey;
                    const draft = draftByLead[rowKey] ?? "";
                    const isGen = generateKey === rowKey;
                    const isSend = sendingKey === rowKey;
                    const hasThread = lead.messages.length > 0;
                    return (
                    <div key={rowKey} className="campaign-lead-block">
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
                              setExpandedLeadKey(isOpen ? null : rowKey);
                            }}
                            aria-expanded={isOpen}
                            aria-label={isOpen ? `Close reply composer for ${lead.name}` : `Reply to ${lead.name}`}
                          >
                            {isOpen ? "Hide reply" : "Reply"}
                          </button>
                        )}
                      </div>
                      <ul className="campaign-messages" aria-label={`Conversation with ${lead.name}`}>
                        {lead.messages.length === 0 ? (
                          <li className="campaign-messages-empty">
                            <p>
                              <strong>No conversation history</strong> — Prosp returned no messages for this lead
                              (new lead, no DMs yet, or the API couldn’t read the thread).
                            </p>
                            <p className="muted small">
                              If you expected messages: set <code>PROSP_SENDER</code> in <code>.env</code> to the
                              LinkedIn profile URL of the account that is <strong>active</strong> in Prosp (not
                              parked). It must match the connected account exactly. Restart the API and reload this
                              campaign.
                            </p>
                            <p className="muted small">
                              You can still use <strong>Reply</strong> below — type manually or use{" "}
                              <strong>Generate with AI</strong> for an intro-style message.
                            </p>
                          </li>
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
                      {lead.linkedin_url && isOpen && (
                        <div className="campaign-lead-compose">
                          <p className="muted small campaign-compose-hint">
                            {hasThread
                              ? "Generate with AI uses the conversation above for a contextual reply."
                              : "No thread loaded — Generate with AI writes a short intro (like a cold outreach). Edit before sending."}
                          </p>
                          <div className="campaign-compose-actions">
                            <button
                              type="button"
                              className="btn secondary"
                              onClick={() => handleGenerateForLead(lead, idx)}
                              disabled={isGen}
                              aria-label={
                                hasThread
                                  ? "Generate reply with AI using conversation thread"
                                  : "Generate intro message with AI"
                              }
                            >
                              {isGen ? "Generating…" : "Generate with AI"}
                            </button>
                          </div>
                          <textarea
                            className="campaign-compose-input"
                            placeholder="Your LinkedIn message — edit after generating"
                            value={draft}
                            onChange={(e) => setDraftForLead(rowKey, e.target.value)}
                            rows={8}
                            aria-label={`Message to ${lead.name}`}
                          />
                          <div className="campaign-compose-actions">
                            <button
                              type="button"
                              className="btn primary"
                              onClick={() => handleSendToLead(lead, idx)}
                              disabled={isSend || !draft.trim()}
                              aria-label={`Send LinkedIn message to ${lead.name}`}
                            >
                              {isSend ? "Sending…" : "Send"}
                            </button>
                          </div>
                        </div>
                      )}
                    </div>
                    );
                  })}
                </div>
                </>
              ) : (
                <p className="muted">No leads or no conversations for this campaign.</p>
              )}
            </div>
          )}
          {!showCampaignDetail && (
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
                      aria-label={`Open campaign ${c.campaign_name}`}
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
          )}
        </>
      )}
    </section>
  );
}
