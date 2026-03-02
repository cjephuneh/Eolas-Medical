# Eolas — Mailbox Tracker (updated 2026-01-29)

<!-- Source of truth for: Eolas mailbox inventory, domain status, and warmup state. For strategy: see context.md -->

## Active Mailboxes (as of 2026-01-29)

| Email | Domain | MI ID | Instantly | Warmup Score | Status |
|-------|--------|-------|-----------|--------------|--------|
| declan@m.eolasmedicalteam.com | m.eolasmedicalteam.com | 68548 | Yes | 100 | Active - highest volume |
| declankelly@m.eolasmedicalteam.com | m.eolasmedicalteam.com | 68552 | Yes | 100 | Active |
| declan.k@m.eolasmedicalteam.com | m.eolasmedicalteam.com | 68551 | Yes | 100 | Active |
| declan.kelly@m.eolasmedicalteam.com | m.eolasmedicalteam.com | 68549 | Yes | 100 | Active |
| declan.kelly@mail.eolas-medical.com | mail.eolas-medical.com | 68553 | Yes | 100 | Active |
| declan@mail.eolas-medical.com | mail.eolas-medical.com | 68554 | Yes | 100 | Active - low volume |
| declan@mail.eolasmedicalteam.com | mail.eolasmedicalteam.com | 75597 | Yes | 0 | New - just added 2026-01-29 |

## Bad/Deleted Mailboxes

| Email | Domain | MI ID | Deleted | Reason |
|-------|--------|-------|---------|--------|
| kelly@m.eolasmedicalteam.com | m.eolasmedicalteam.com | 68550 | 2026-01-29 | 0 warmup score, barely used |
| logan@eolasmedicalupdates.com | eolasmedicalupdates.com | - | 2026-01-29 | Inactive status in Instantly |

## Domains

| Domain | MI ID | Status | Mailboxes | Notes |
|--------|-------|--------|-----------|-------|
| m.eolasmedicalteam.com | 47134 | Verified | 5 | Primary sending domain |
| mail.eolas-medical.com | 47136 | Verified | 2 | Secondary - capacity available |
| mail.eolasmedicalteam.com | 47135 | Verified | 1 | Underutilized |
| mailbox.eolas-medical.com | 47137 | Verified | 0 | Empty - available for expansion |
| eolasmedicalupdates.com | 46903 | Unverified | 0 | Not in use |

## Notes
- All mailboxes use a shared password (see 1Password vault)
- First/Last name: Declan Kelly
- reply_to on mail.eolas-medical.com mailboxes: logan@eolasmedical.com
