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
}

export interface CampaignLeadsResponse {
  campaign_id: string;
  campaign_name: string;
  leads_count: number;
  leads: CampaignLeadWithMessages[];
  error?: string;
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
  campaignLeads: (campaignId: string) =>
    request<CampaignLeadsResponse>(`/campaigns/${encodeURIComponent(campaignId)}/leads`),
  generateProspMessage: (name: string, context?: string) =>
    request<{ message: string }>("/prosp/generate-message", {
      method: "POST",
      body: JSON.stringify({ name, context }),
    }),
  sendProspMessage: (linkedinUrl: string, message: string) =>
    request<{ status: string }>("/prosp/send-message", {
      method: "POST",
      body: JSON.stringify({ linkedin_url: linkedinUrl, message }),
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
  inboxLinkedin: async (): Promise<Lead[]> => {
    const res = await request<LeadsResponse>("/inbox/linkedin");
    return Array.isArray(res.leads) ? res.leads : [];
  },
  lead: (id: string) => request<Lead>(`/leads/${encodeURIComponent(id)}`),
  sendReply: (id: string, body: string, subject?: string) =>
    request<{ status: string; message: string; channel: string }>(`/leads/${encodeURIComponent(id)}/send-reply`, {
      method: "POST",
      body: JSON.stringify({ body, subject }),
    }),
  runCycle: () => request<{ status: string; counts: RunCycleCounts }>("/run-cycle", { method: "POST" }),
};
