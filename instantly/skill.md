# Instantly API Skill

Direct API access to Instantly.ai for email campaign management, lead operations, and deliverability monitoring.

## Base URL

`https://api.instantly.ai/api/v2`

## Authentication

Bearer token in Authorization header:

```
Authorization: Bearer {API_KEY}
Content-Type: application/json
```

## Credentials (per workspace)

| Workspace | Env Var |
|-----------|---------|
| Virgil | `$INSTANTLY_API_KEY_VIRGIL` |
| RISE | `$INSTANTLY_API_KEY_RISE` |
| Eolas | `$INSTANTLY_API_KEY` |

Always confirm which workspace before making calls. Default to asking if ambiguous.

## Request Pattern

```bash
# GET request
curl -s "https://api.instantly.ai/api/v2/{endpoint}?{params}" \
  -H "Authorization: Bearer $API_KEY"

# POST/PATCH request
curl -s -X POST "https://api.instantly.ai/api/v2/{endpoint}" \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"key": "value"}'

# DELETE request
curl -s -X DELETE "https://api.instantly.ai/api/v2/{endpoint}" \
  -H "Authorization: Bearer $API_KEY"
```

## Pagination

Cursor-based. Use `starting_after` param with the last item's ID. Check if response has more items.

---

## Endpoints

### Campaigns

| Action | Method | Path | Body/Params |
|--------|--------|------|-------------|
| List | GET | `/campaigns` | `?limit=&status=&starting_after=` |
| Get | GET | `/campaigns/{id}` | — |
| Create | POST | `/campaigns` | `{name, sequences?, campaign_schedule?}` |
| Update | PATCH | `/campaigns/{id}` | `{name?, email_list?, daily_limit?, sequences?, campaign_schedule?, ...}` |
| Delete | DELETE | `/campaigns/{id}` | — |
| Activate | POST | `/campaigns/{id}/activate` | — |
| Pause | POST | `/campaigns/{id}/pause` | — |
| Add Variables | POST | `/campaigns/{id}/variables` | `{variables: string[]}` |

**Default schedule** (if not provided on create):
```json
{"schedules": [{"name": "Default", "timing": {"from": "09:00", "to": "17:00"}, "days": {"0": false, "1": true, "2": true, "3": true, "4": true, "5": true, "6": false}, "timezone": "America/Chicago"}]}
```

### Leads

| Action | Method | Path | Body/Params |
|--------|--------|------|-------------|
| List | **POST** | `/leads/list` | `{campaign_id?, limit?, starting_after?, email?, status?}` |
| Get | GET | `/leads/{id}` | — |
| Create | POST | `/leads` | `{email, first_name?, last_name?, company_name?, campaign_id?, custom_variables?}` |
| Update | PATCH | `/leads/{id}` | `{first_name?, last_name?, company_name?, custom_variables?, interest_status?}` |
| Delete | DELETE | `/leads/{id}` | — |
| Bulk Add | POST | `/leads/bulk` | `{campaign_id?, lead_list_id?, leads[], skip_if_in_campaign?, skip_if_in_workspace?}` |

**Gotcha**: Lead listing uses POST, not GET.

**Bulk lead format**:
```json
{"leads": [{"email": "j@co.com", "first_name": "J", "last_name": "D", "company_name": "Co", "custom_variables": {"key": "val"}}]}
```

### Lead Lists

| Action | Method | Path | Body |
|--------|--------|------|------|
| List | GET | `/lead-lists` | — |
| Get | GET | `/lead-lists/{id}` | — |
| Create | POST | `/lead-lists` | `{name}` |
| Delete | DELETE | `/lead-lists/{id}` | — |

### Accounts (Sending Mailboxes)

| Action | Method | Path | Body |
|--------|--------|------|------|
| List | GET | `/accounts` | — |
| Get | GET | `/accounts/{email}` | — |
| Create | POST | `/accounts` | `{email, first_name?, last_name?, provider?, smtp_host/port/user/pass?, imap_host/port/user/pass?}` |
| Update | PATCH | `/accounts/{email}` | `{first_name?, last_name?, daily_limit?}` |
| Delete | DELETE | `/accounts/{email}` | — |
| Pause | POST | `/accounts/{email}/pause` | — |
| Resume | POST | `/accounts/{email}/resume` | — |
| Enable Warmup | POST | `/accounts/warmup/enable` | `{emails?, include_all_emails?, excluded_emails?}` |
| Disable Warmup | POST | `/accounts/warmup/disable` | `{emails?, include_all_emails?, excluded_emails?}` |
| Test Vitals | POST | `/accounts/test/vitals` | `{emails: string[]}` |

**Gotcha**: Email addresses in path params must be URI-encoded: `encodeURIComponent(email)`.

### Analytics

| Action | Method | Path | Params |
|--------|--------|------|--------|
| Campaign Analytics | GET | `/campaigns/analytics` | `?campaign_id=&start_date=&end_date=` |
| Campaign Overview | GET | `/campaigns/analytics/overview` | `?campaign_id=` |
| Campaign Daily | GET | `/campaigns/analytics/daily` | `?campaign_id=&start_date=&end_date=` |
| Campaign Steps | GET | `/campaigns/{id}/analytics/steps` | — |
| Account Daily | GET | `/accounts/analytics/daily` | `?emails=a@b.com,c@d.com&start_date=&end_date=` |
| Warmup Analytics | POST | `/accounts/warmup-analytics` | `{emails: string[]}` |

**Date format**: `YYYY-MM-DD`

### Emails / Unibox

| Action | Method | Path | Body/Params |
|--------|--------|------|-------------|
| List | GET | `/emails` | `?campaign_id=&lead_email=&search=&limit=&starting_after=&is_read=` |
| Get | GET | `/emails/{id}` | — |
| Delete | DELETE | `/emails/{id}` | — |
| Reply | POST | `/emails/reply` | `{reply_to_uuid, eaccount, subject, body: {text, html?}}` (see Instantly API v2) |
| Forward | POST | `/emails/forward` | `{forward_uuid, from_email, to_email, subject?, body?}` |
| Mark Read | POST | `/emails/threads/{thread_id}/mark-as-read` | — |
| Unread Count | GET | `/emails/unread/count` | — |

### Blocklist

| Action | Method | Path | Body/Params |
|--------|--------|------|-------------|
| List | GET | `/block-lists-entries` | `?limit=&domains_only=&search=&starting_after=` |
| Add | POST | `/block-lists-entries` | `{entry}` |
| Remove | DELETE | `/block-lists-entries/{id}` | — |

### Email Verification

| Action | Method | Path | Body |
|--------|--------|------|------|
| Verify | POST | `/email-verification` | `{email, webhook_url?}` |
| Check Status | GET | `/email-verification/{email}` | — |

### Tags

| Action | Method | Path | Body |
|--------|--------|------|------|
| List | GET | `/custom-tags` | `?limit=&starting_after=` |
| Create | POST | `/custom-tags` | `{name, color?}` |
| Delete | DELETE | `/custom-tags/{id}` | — |
| Assign | POST | `/custom-tag-mappings` | `{tag_id, resource_id, resource_type: "campaign"\|"account"}` |

### SuperSearch / Enrichment

| Action | Method | Path | Body | Credits |
|--------|--------|------|------|---------|
| Preview | POST | `/supersearch-enrichment/preview-leads-from-supersearch` | `{search_filters, skip_owned_leads?, show_one_lead_per_company?}` | Free |
| Count | POST | `/supersearch-enrichment/count-leads-from-supersearch` | `{search_filters}` | Free |
| Enrich | POST | `/supersearch-enrichment/enrich-leads-from-supersearch` | See below | ~1.5/email |
| Status | GET | `/supersearch-enrichment/{resource_id}` | — | Free |
| Run on Existing | POST | `/supersearch-enrichment/run` | `{resource_id, lead_ids?, limit?}` | ~1.5/email |
| AI Enrichment | POST | `/supersearch-enrichment/ai` | See below | Varies |

**Enrich body**:
```json
{
  "search_filters": {},
  "search_name": "string",
  "limit": 100,
  "work_email_enrichment": true,
  "fully_enriched_profile": true,
  "custom_flow": ["instantly", "findymail", "leadmagic"],
  "resource_id": "uuid",
  "resource_type": 1,
  "list_name": "string"
}
```
`resource_type`: 1 = campaign, 2 = list

**Search filters**:
```json
{
  "locations": [{"country": "US", "state": "California", "city": "San Francisco"}],
  "title": {"include": ["CEO"], "exclude": ["Consultant"]},
  "level": ["Executive", "Director", "Senior", "Manager", "Owner", "Partner"],
  "department": ["Engineering", "Sales", "Marketing", "Finance & Administration"],
  "employee_count": ["0 - 25", "25 - 100", "100 - 250", "250 - 1000", "1K - 10K"],
  "revenue": ["$0 - 1M", "$1 - 10M", "$10 - 50M", "$50 - 100M"],
  "industry": {"include": ["Financial Services"], "exclude": ["Government"]},
  "company_name": {"include": ["Acme"], "exclude": []},
  "domains": ["acme.com"],
  "funding_type": ["seed", "series_a", "series_b", "private_equity"],
  "news": ["launches", "receives_financing", "hires", "goes_ipo"]
}
```

**CRITICAL filter gotchas** (see `~/.claude/skills/campaign-builder/skill.md` for full reference):
- **Locations**: Use ISO 2-letter country codes (`"GB"` not `"United Kingdom"`)
- **Level**: Use single words (`"Director"`, `"Executive"`) — NOT `"Director-Level"` or `"C-Level"` (those fail validation)
- **Employee count**: Must have spaces around dash (`"250 - 1000"`) — without spaces silently returns unfiltered results

### Workspace & API Keys

| Action | Method | Path | Body |
|--------|--------|------|------|
| Get Workspace | GET | `/workspace` | — |
| Update Workspace | PATCH | `/workspace` | `{name?}` |
| List API Keys | GET | `/api-keys` | — |
| Create API Key | POST | `/api-keys` | `{name, scopes: string[]}` |
| Delete API Key | DELETE | `/api-keys/{api_key_id}` | — |

### Background Jobs

| Action | Method | Path |
|--------|--------|------|
| Get Job Status | GET | `/background-jobs/{job_id}` |

Used for async operations (bulk warmup enable/disable).

---

## Common Workflows

### Assign mailboxes to a campaign
Use `email_list` field on campaign PATCH (or POST for new campaigns):
```
PATCH /campaigns/{id}
{"email_list": ["mailbox1@domain.com", "mailbox2@domain.com"]}
```
- Each email must be a connected account in the workspace
- Replaces existing assignments (not additive) — include all desired mailboxes
- Best practice: 1 unique mailbox per campaign for clean deliverability tracking
- Verify via: `GET /account-campaign-mappings/{email}` (read-only, shows which campaigns an account is linked to)

### Launch a campaign
1. Create lead list: `POST /lead-lists`
2. Bulk add leads: `POST /leads/bulk` with `lead_list_id`
3. Create campaign: `POST /campaigns` with sequences, schedule, and `email_list`
4. Activate: `POST /campaigns/{id}/activate`

### Health check (email infra)
1. List accounts: `GET /accounts`
2. Test vitals: `POST /accounts/test/vitals` with all emails
3. Get warmup analytics: `POST /accounts/warmup-analytics` with all emails
4. Check campaign analytics: `GET /campaigns/analytics`

### Find and enrich prospects
1. Preview (free): `POST /supersearch-enrichment/preview-leads-from-supersearch`
2. Count (free): `POST /supersearch-enrichment/count-leads-from-supersearch`
3. **Confirm with user before enriching** — costs ~1.5 credits per email
4. Enrich: `POST /supersearch-enrichment/enrich-leads-from-supersearch`

---

## Gotchas

- Lead listing is POST, not GET
- Email addresses in URL paths must be URI-encoded
- Warmup enable/disable returns a background job ID — poll via `/background-jobs/{id}`
- SuperSearch preview/count are free; enrich costs credits — always confirm before enriching
- Pagination is cursor-based (`starting_after`), not offset-based
- Date format for analytics: `YYYY-MM-DD`
- Empty API responses are valid (treated as success)
