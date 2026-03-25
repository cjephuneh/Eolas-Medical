import { useCallback, useEffect, useMemo, useState } from "react";
import { api, type CampaignLeadWithMessages } from "../api";

type MessageFilterTab = "all" | "with_messages" | "no_messages";

type FocusedThread = {
  key: string;
  lead: CampaignLeadWithMessages;
};

function leadThreadKey(lead: CampaignLeadWithMessages, idx: number): string {
  const campaign = (lead.campaign_id || lead.campaign_name || "").trim();
  const url = (lead.linkedin_url || "").trim();
  if (campaign && url) return `${campaign}::${url}`;
  if (url) return url;
  return `${idx}::${(lead.name || "unknown").trim()}`;
}

export function Campaigns() {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [threads, setThreads] = useState<CampaignLeadWithMessages[]>([]);

  const [filterTab, setFilterTab] = useState<MessageFilterTab>("with_messages");
  const [search, setSearch] = useState("");

  const [focused, setFocused] = useState<FocusedThread | null>(null);
  const [draftByLead, setDraftByLead] = useState<Record<string, string>>({});
  const [generateKey, setGenerateKey] = useState<string | null>(null);
  const [sendingKey, setSendingKey] = useState<string | null>(null);
  const [sendResult, setSendResult] = useState<{ ok: boolean; message: string } | null>(null);

  const loadThreads = useCallback(() => {
    setError(null);
    setLoading(true);
    setSendResult(null);

    // Keep the initial load responsive by limiting campaigns/leads.
    // If the user switches to "No thread", we refetch with include_no_messages=1.
    api
      .linkedinThreads(3, 25, filterTab === "no_messages")
      .then((leads) => setThreads(leads))
      .catch((err) => setError(err instanceof Error ? err.message : String(err)))
      .finally(() => setLoading(false));
  }, [filterTab]);

  useEffect(() => {
    loadThreads();
  }, [loadThreads]);

  useEffect(() => {
    // When the list is refetched for a different tab/search, drop any focused thread
    // to avoid stale keys.
    setFocused(null);
    setGenerateKey(null);
    setSendingKey(null);
    setSendResult(null);
  }, [filterTab, search]);

  const stats = useMemo(() => {
    let withMessages = 0;
    for (const l of threads) {
      if ((l.messages?.length ?? 0) > 0) withMessages += 1;
    }
    return {
      total: threads.length,
      withMessages,
      noMessages: threads.length - withMessages,
    };
  }, [threads]);

  const filteredThreads = useMemo(() => {
    let rows = threads;
    if (filterTab === "with_messages") rows = rows.filter((l) => (l.messages?.length ?? 0) > 0);
    if (filterTab === "no_messages") rows = rows.filter((l) => (l.messages?.length ?? 0) === 0);

    const q = search.trim().toLowerCase();
    if (!q) return rows;

    return rows.filter((l) => {
      const name = (l.name || "").toLowerCase();
      const company = (l.company || "").toLowerCase();
      const campaign = (l.campaign_name || "").toLowerCase();
      const url = (l.linkedin_url || "").toLowerCase();
      const body = (l.messages || []).map((m) => m.content || "").join(" ").toLowerCase();
      return name.includes(q) || company.includes(q) || campaign.includes(q) || url.includes(q) || body.includes(q);
    });
  }, [threads, filterTab, search]);

  const openThread = (lead: CampaignLeadWithMessages, idx: number) => {
    const key = leadThreadKey(lead, idx);
    setFocused({ key, lead });
    setSendResult(null);
  };

  const handleGenerate = async (lead: CampaignLeadWithMessages, key: string) => {
    setGenerateKey(key);
    setSendResult(null);

    try {
      const name = lead.name || "there";
      const campaignName = lead.campaign_name || "";
      const hasThread = (lead.messages?.length ?? 0) > 0;

      const gen = hasThread
        ? api.generateProspReply({
            name,
            campaign_name: campaignName,
            messages: (lead.messages || []).map((m) => ({ content: m.content || "", from_me: m.from_me })),
          })
        : api.generateProspMessage(name, campaignName);

      const r = await gen;
      setDraftByLead((prev) => ({ ...prev, [key]: r.message || "" }));
    } finally {
      setGenerateKey(null);
    }
  };

  const handleSend = async (lead: CampaignLeadWithMessages, key: string) => {
    const draft = (draftByLead[key] || "").trim();
    if (!lead.linkedin_url || !draft) return;

    setSendingKey(key);
    setSendResult(null);

    try {
      await api.sendProspMessage(lead.linkedin_url, draft, lead.prosp_sender_used);
      setSendResult({ ok: true, message: "Message sent." });
      setFocused(null);
      setDraftByLead((prev) => {
        const next = { ...prev };
        delete next[key];
        return next;
      });
    } catch (err) {
      setSendResult({
        ok: false,
        message: err instanceof Error ? err.message : String(err),
      });
    } finally {
      setSendingKey(null);
    }
  };

  if (loading) {
    return (
      <div className="loading-wrap">
        <div className="spinner" aria-hidden />
        <span>Loading LinkedIn threads…</span>
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
      <h1 className="page-title">LinkedIn</h1>
      <p className="page-subtitle">
        Active Prosp campaigns flattened into one list of connections and their message threads.
      </p>

      {!focused && (
        <>
          <div className="campaign-metrics leads-metrics" role="region" aria-label="LinkedIn thread counts">
            <div className="campaign-metric-card">
              <span className="campaign-metric-value">{stats.total}</span>
              <span className="campaign-metric-label">Connections</span>
            </div>
            <div className="campaign-metric-card">
              <span className="campaign-metric-value">{stats.withMessages}</span>
              <span className="campaign-metric-label">With messages</span>
            </div>
            <div className="campaign-metric-card">
              <span className="campaign-metric-value">{stats.noMessages}</span>
              <span className="campaign-metric-label">No thread</span>
            </div>
          </div>

          <div className="leads-email-filters">
            <div className="lead-filter-tabs email-message-tabs" role="tablist" aria-label="Filter by messages">
              {(
                [
                  { id: "all" as const, label: "All", count: stats.total },
                  { id: "with_messages" as const, label: "With messages", count: stats.withMessages },
                  { id: "no_messages" as const, label: "No thread", count: stats.noMessages },
                ] as const
              ).map(({ id, label, count }) => (
                <button
                  key={id}
                  type="button"
                  role="tab"
                  aria-selected={filterTab === id}
                  className={`btn filter-tab ${filterTab === id ? "active" : "secondary"}`}
                  onClick={() => {
                    setFilterTab(id);
                    setSendResult(null);
                  }}
                  aria-controls="linkedin-thread-list"
                >
                  {label} ({count})
                </button>
              ))}
            </div>

            <div className="leads-inbox-search" style={{ marginBottom: 0 }}>
              <label htmlFor="linkedin-search" className="sr-only">
                Search LinkedIn threads
              </label>
              <input
                id="linkedin-search"
                type="search"
                className="leads-inbox-search-input"
                placeholder="Search name, company, campaign, or message…"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                aria-label="Search LinkedIn threads"
              />
            </div>
          </div>

          {filteredThreads.length === 0 ? (
            <div className="table-wrap">
              <div className="empty-state">No LinkedIn threads match your filters.</div>
            </div>
          ) : (
            <div className="campaign-leads-list" id="linkedin-thread-list" aria-label="LinkedIn thread list">
              {filteredThreads.map((lead, idx) => {
                const key = leadThreadKey(lead, idx);
                const hasThread = (lead.messages?.length ?? 0) > 0;

                return (
                  <div key={key} className="campaign-lead-block">
                    <div className="campaign-lead-head">
                      <strong>{lead.name || "—"}</strong>
                      {lead.company && <span className="muted"> · {lead.company}</span>}
                      {lead.campaign_name && <code className="campaign-id">{lead.campaign_name}</code>}
                      <span className="muted"> · {(lead.messages?.length ?? 0)} message(s)</span>

                      {lead.linkedin_url && (
                        <a
                          href={lead.linkedin_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="campaign-lead-link"
                          aria-label={`Open LinkedIn profile for ${lead.name}`}
                        >
                          LinkedIn
                        </a>
                      )}

                      <button
                        type="button"
                        className="btn small"
                        onClick={() => openThread(lead, idx)}
                        aria-label={`Open messages for ${lead.name}`}
                      >
                        {hasThread ? "Open" : "Open"}
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </>
      )}

      {focused && (
        <div className="card wide campaign-detail campaign-detail-focused" role="region" aria-label="Focused LinkedIn thread">
          <div className="focused-view-nav">
            <button
              type="button"
              className="btn secondary focused-view-back"
              onClick={() => setFocused(null)}
              aria-label="Back to thread list"
            >
              ← Back
            </button>
          </div>

          <div className="lead-detail-header">
            <h3>
              {focused.lead.name || "—"} {focused.lead.company ? `· ${focused.lead.company}` : ""}
            </h3>
            {focused.lead.campaign_name ? <code className="campaign-id">{focused.lead.campaign_name}</code> : null}
          </div>

          {focused.lead.linkedin_url && (
            <p className="muted">
              <a
                href={focused.lead.linkedin_url}
                target="_blank"
                rel="noopener noreferrer"
                className="campaign-lead-link"
              >
                LinkedIn profile
              </a>
            </p>
          )}

          <p className="muted small campaign-compose-hint">
            {(focused.lead.messages?.length ?? 0) > 0
              ? "Messages loaded — Generate with AI will write a contextual follow-up."
              : "No messages loaded — Generate with AI will write an intro-style message."}
          </p>

          <div className="campaign-compose-actions">
            <button
              type="button"
              className="btn secondary"
              onClick={() => handleGenerate(focused.lead, focused.key)}
              disabled={generateKey === focused.key}
              aria-label="Generate LinkedIn message with AI"
            >
              {generateKey === focused.key ? "Generating…" : "Generate with AI"}
            </button>
          </div>

          <textarea
            className="campaign-compose-input"
            placeholder="Your LinkedIn message — edit before sending"
            value={draftByLead[focused.key] ?? ""}
            onChange={(e) =>
              setDraftByLead((prev) => ({ ...prev, [focused.key]: e.target.value }))
            }
            rows={6}
            aria-label={`Message to ${focused.lead.name}`}
            disabled={sendingKey === focused.key}
          />

          <div className="campaign-compose-actions">
            <button
              type="button"
              className="btn primary"
              onClick={() => handleSend(focused.lead, focused.key)}
              disabled={sendingKey === focused.key || !(draftByLead[focused.key] || "").trim()}
              aria-label={`Send LinkedIn message to ${focused.lead.name}`}
            >
              {sendingKey === focused.key ? "Sending…" : "Send"}
            </button>
          </div>

          {sendResult && (
            <span className={sendResult.ok ? "send-ok" : "send-error"} role="status">
              {sendResult.message}
            </span>
          )}

          <div className="lead-detail-header" style={{ marginTop: "1rem" }}>
            <h3>Conversation</h3>
          </div>

          <ul className="campaign-messages" aria-label={`Conversation with ${focused.lead.name}`}>
            {focused.lead.messages?.length ? (
              focused.lead.messages.map((msg, midx) => (
                <li key={midx} className={msg.from_me ? "message-from-me" : "message-from-lead"}>
                  <span className="message-meta">
                    {msg.from_me ? "You" : focused.lead.name} · {msg.created_at || "—"}
                  </span>
                  <div className="message-content">{msg.content || "—"}</div>
                </li>
              ))
            ) : (
              <li className="muted">No messages loaded.</li>
            )}
          </ul>
        </div>
      )}
    </section>
  );
}
