/**
 * Split LLM email suggestions into body + sign-off so we don't show "[Your name]" inline.
 */
export function splitSuggestedEmailReply(text: string): { body: string; signOff: string } {
  const s = text ?? "";
  const defaultSignOff =
    (import.meta.env.VITE_SENDER_NAME as string | undefined)?.trim() || "Eolas";

  const idx = s.search(/\[Your name\]/i);
  if (idx === -1) {
    return { body: s.trimEnd(), signOff: "" };
  }

  let body = s.slice(0, idx).trimEnd();
  body = body.replace(/\n+(Best regards|Best|Regards|Thanks|Thank you|Kind regards)[,\s]*\s*$/i, "").trimEnd();

  return { body, signOff: defaultSignOff };
}

export function composeEmailReplyForSend(body: string, signOff: string): string {
  const b = (body || "").trim();
  const s = (signOff || "").trim();
  if (!b && !s) return "";
  if (!s) return b;
  if (!b) return `Best,\n${s}`;
  return `${b}\n\nBest,\n${s}`;
}

/** Full reply text for display/edit before send (body + sign-off from LLM). */
export function buildEditableReplyFromLead(lead: { suggested_response?: string }): string {
  const raw = (lead.suggested_response || "").trim();
  if (!raw) return "";
  const parts = splitSuggestedEmailReply(raw);
  return composeEmailReplyForSend(parts.body, parts.signOff);
}
