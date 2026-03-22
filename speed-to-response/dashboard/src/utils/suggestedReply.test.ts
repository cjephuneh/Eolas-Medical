import { describe, expect, it } from "vitest";
import {
  buildEditableReplyFromLead,
  composeEmailReplyForSend,
  splitSuggestedEmailReply,
} from "./suggestedReply";

describe("buildEditableReplyFromLead", () => {
  it("happy path: composes body and sign-off", () => {
    const text = "Hello\n\n[Your name]";
    const full = buildEditableReplyFromLead({ suggested_response: text });
    expect(full).toContain("Hello");
    expect(full).toMatch(/Best,\s*\n/);
  });

  it("edge: empty suggested_response", () => {
    expect(buildEditableReplyFromLead({ suggested_response: "" })).toBe("");
    expect(buildEditableReplyFromLead({})).toBe("");
  });

  it("failure: whitespace-only becomes empty", () => {
    expect(buildEditableReplyFromLead({ suggested_response: "   \n  " })).toBe("");
  });
});

describe("splitSuggestedEmailReply", () => {
  it("no placeholder returns full as body", () => {
    const { body, signOff } = splitSuggestedEmailReply("Plain text only");
    expect(body).toBe("Plain text only");
    expect(signOff).toBe("");
  });
});

describe("composeEmailReplyForSend", () => {
  it("combines body and sign-off", () => {
    expect(composeEmailReplyForSend("Hi", "Alex")).toBe("Hi\n\nBest,\nAlex");
  });
});
