const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: { "Content-Type": "application/json", ...options?.headers },
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ message: res.statusText }));
    throw new Error((err as { message?: string }).message || res.statusText);
  }
  return res.json() as Promise<T>;
}

export interface Health {
  status?: string;
}

export interface Endpoints {
  app?: string;
  endpoints?: Record<string, string>;
}

export interface Lead {
  id: string;
  channel: string;
  lead_name: string;
  company: string;
  campaign: string;
  classification: string;
  reply_text: string;
  suggested_response: string;
  notified_at: string;
  email?: string;
  linkedin_url?: string;
  reply_to_uuid?: string;
  from_email?: string;
  /** Email thread subject (Instantly) */
  subject?: string;
  /** Set when a reply was sent from the dashboard (UTC ISO from server). */
  replied_at?: string;
}

export interface SourcesResponse {
  instantly?: { count: number; signals?: unknown[] };
  prosp?: { count: number; signals?: unknown[] };
}

export interface ProspCampaign {
  campaign_id: string;
  campaign_name: string;
}

export interface CampaignsResponse {
  campaigns: ProspCampaign[];
  count?: number;
}

export interface CampaignLeadMessage {
  content: string;
  from_me: boolean;
  created_at: string;
}

export interface CampaignLeadWithMessages {
  name: string;
  linkedin_url: string;
  company: string;
  messages: CampaignLeadMessage[];
  messages_count: number;
  /** Prosp sender account URL used to fetch this conversation thread (so we can send replies from the same account). */
  prosp_sender_used?: string;
  /** Prosp campaign this thread belongs to (set by /linkedin/threads). */
  campaign_id?: string;
  campaign_name?: string;
}

export interface CampaignLeadsResponse {
  campaign_id: string;
  campaign_name: string;
  leads_count: number;
  leads: CampaignLeadWithMessages[];
  error?: string;
}

export interface LinkedinThreadsResponse {
  campaigns_loaded?: number;
  count?: number;
  leads: CampaignLeadWithMessages[];
}

export interface RunCycleCounts {
  fetched?: number;
  interested?: number;
  notified?: number;
  skipped_already_processed?: number;
}

export interface LeadsResponse {
  count?: number;
  leads?: Lead[];
}

export interface EmailMessage {
  id: string;
  channel: string;
  lead_name: string;
  email: string;
  company: string;
  campaign: string;
  reply_text: string;
  timestamp: string;
  reply_to_uuid?: string;
  from_email?: string;
  /** Our mailbox when Instantly lists From=mailbox / To=prospect */
  our_mailbox?: string;
}

export interface InboxEmailResponse {
  count?: number;
  emails?: EmailMessage[];
}

export const api = {
  health: () => request<Health>("/health"),
  index: () => request<Endpoints>("/"),
  leads: async (): Promise<Lead[]> => {
    const res = await request<LeadsResponse>("/leads");
    return Array.isArray(res.leads) ? res.leads : [];
  },
  sources: () => request<SourcesResponse>("/sources"),
  campaigns: async (): Promise<ProspCampaign[]> => {
    const res = await request<CampaignsResponse>("/campaigns");
    return Array.isArray(res.campaigns) ? res.campaigns : [];
  },
  /** Loads up to max_leads per campaign (server cap ~100) for dashboard. */
  campaignLeads: (campaignId: string, maxLeads = 100) =>
    request<CampaignLeadsResponse>(
      `/campaigns/${encodeURIComponent(campaignId)}/leads?max_leads=${maxLeads}`
    ),
  /** Active campaigns -> flattened list of lead conversations. */
  linkedinThreads: async (
    maxCampaigns?: number,
    maxLeadsPerCampaign?: number,
    includeNoMessages = false
  ): Promise<CampaignLeadWithMessages[]> => {
    const params = new URLSearchParams();
    if (maxCampaigns != null) params.set("max_campaigns", String(maxCampaigns));
    if (maxLeadsPerCampaign != null) {
      params.set("max_leads_per_campaign", String(maxLeadsPerCampaign));
    }
    if (includeNoMessages) params.set("include_no_messages", "1");
    const q = params.toString();
    const res = await request<LinkedinThreadsResponse>(
      `/linkedin/threads${q ? `?${q}` : ""}`
    );
    return Array.isArray(res.leads) ? res.leads : [];
  },
  generateProspMessage: (name: string, context?: string) =>
    request<{ message: string }>("/prosp/generate-message", {
      method: "POST",
      body: JSON.stringify({ name, context }),
    }),
  /** AI reply using LinkedIn thread (messages from Prosp); same idea as email suggested reply. */
  generateProspReply: (body: {
    name: string;
    campaign_name?: string;
    messages?: Array<{ content: string; from_me?: boolean }>;
    thread_context?: string;
  }) =>
    request<{ message: string }>("/prosp/generate-reply", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  sendProspMessage: (linkedinUrl: string, message: string, sender?: string) =>
    request<{ status: string }>("/prosp/send-message", {
      method: "POST",
      body: JSON.stringify({ linkedin_url: linkedinUrl, message, sender }),
    }),
  generateBulkMessage: (campaignId: string, campaignDescription?: string) =>
    request<{ message_template: string; campaign_name?: string }>(
      `/campaigns/${encodeURIComponent(campaignId)}/generate-bulk-message`,
      {
        method: "POST",
        body: JSON.stringify({ campaign_description: campaignDescription || "" }),
      }
    ),
  sendBulkMessage: (campaignId: string, messageTemplate: string) =>
    request<{ sent: number; failed: number; total: number; results: { name: string; status: string; reason?: string }[] }>(
      `/campaigns/${encodeURIComponent(campaignId)}/send-bulk`,
      {
        method: "POST",
        body: JSON.stringify({ message_template: messageTemplate }),
      }
    ),
  inboxEmail: async (limit?: number): Promise<EmailMessage[]> => {
    const q = limit != null ? `?limit=${limit}` : "";
    const res = await request<InboxEmailResponse>(`/inbox/email${q}`);
    return Array.isArray(res.emails) ? res.emails : [];
  },
  inboxLinkedin: async (): Promise<Lead[]> => {
    const res = await request<LeadsResponse>("/inbox/linkedin");
    return Array.isArray(res.leads) ? res.leads : [];
  },
  lead: (id: string) => request<Lead>(`/leads/${encodeURIComponent(id)}`),
  sendReply: (id: string, body: string, subject?: string) =>
    request<{ status: string; message: string; channel: string; replied_at?: string }>(
      `/leads/${encodeURIComponent(id)}/send-reply`,
      {
        method: "POST",
        body: JSON.stringify({ body, subject }),
      }
    ),
  runCycle: () => request<{ status: string; counts: RunCycleCounts }>("/run-cycle", { method: "POST" }),
};
