# Volare AI — lead-capture chat widget

A coded replacement for the n8n chatbot, built so **the client sets up nothing**.
No accounts, no API keys, no OAuth screens. Volare pastes one `<script>` tag into
Webflow and is done. Every credential lives in your agency's Vercel project.

That's the whole point: "I don't have time to set up the APIs and accounts" stops
being a valid objection when there is nothing to set up.

---

## What it does

- Answers questions about Volare's advisory, the 6 value drivers, and how to start
- Qualifies the visitor conversationally — one question at a time, no forms
- Captures name, email, company, industry, revenue range and intent
- Emails the lead to Shamus with the full transcript the moment it has enough
- Optionally fires a WhatsApp alert at the same time
- Drops a "Book a founder call" button into the chat once the lead is captured

---

## Architecture

```
volare.ai (Webflow)                 Your Vercel project
┌─────────────────────┐             ┌──────────────────────────────┐
│  <script src=…>     │──POST──────▶│  /api/chat                   │
│  widget.js          │◀──JSON──────│    ├─ Claude (your key)      │
│  (shadow DOM)       │             │    └─ capture_lead tool      │
└─────────────────────┘             │         ├─ Resend  → email   │
                                    │         └─ Twilio  → WhatsApp│
                                    └──────────────────────────────┘
```

Four files matter:

| File | Purpose |
| --- | --- |
| `api/_prompt.js` | System prompt, tool schema, contact details. **Tune the bot here.** |
| `api/chat.js` | Request handling, the Claude tool loop, rate limiting, CORS |
| `api/_notify.js` | Resend email + optional Twilio WhatsApp |
| `public/widget.js` | The embeddable widget — zero dependencies, renders in a shadow root |

---

## Deploy

```bash
cd volare-chatbot
npm install
npx vercel                    # first deploy, creates the project
```

Then set the environment variables (see `.env.example` for the full annotated list):

```bash
npx vercel env add ANTHROPIC_API_KEY production
npx vercel env add RESEND_API_KEY production
npx vercel env add LEAD_EMAIL_FROM production
npx vercel env add LEAD_EMAIL_TO production
npx vercel env add ALLOWED_ORIGINS production
npx vercel --prod
```

**Before going live**, set `ALLOWED_ORIGINS` to `https://volare.ai,https://www.volare.ai`.
With it unset the API accepts requests from any origin — fine for local testing, not
for production, since anyone could point their own page at your endpoint and spend
your Claude credits.

### Local development

```bash
cp .env.example .env.local     # fill in the values
npx vercel dev                 # → http://localhost:3000/demo.html
```

---

## The embed snippet

This is the only thing Volare ever touches. In Webflow: **Site Settings → Custom Code
→ Footer Code**, paste, publish.

```html
<script
  src="https://YOUR-DEPLOYMENT.vercel.app/widget.js"
  data-api="https://YOUR-DEPLOYMENT.vercel.app/api/chat"
  data-accent="#111827"
  data-title="Volare AI"
  defer
></script>
```

Optional attributes: `data-subtitle`, `data-greeting`, `data-booking-url`,
`data-position="left"`.

You can also open the chat from any button on the page:

```html
<button onclick="window.VolareChat.open()">Talk to us</button>
```

---

## Cost per conversation

Measured against a realistic 8-exchange conversation. The system prompt and tool
schema (~1,150 tokens) sit behind a cache breakpoint, so every turn after the first
reads them at ~10% of input price instead of full freight.

| Model | Per conversation | 300/month | Notes |
| --- | --- | --- | --- |
| `claude-opus-5` (default) | ~$0.08 | ~$24 | Best judgement on qualifying and when to push for the email |
| `claude-sonnet-5` | ~$0.05 | ~$14 | **Drop-in** — change `CLAUDE_MODEL`, nothing else |
| `claude-haiku-4-5` | ~$0.02 | ~$5 | Needs a code change, see below |

Switching to Sonnet is a one-line env var change. Haiku 4.5 is on an older API
surface — it doesn't accept `output_config.effort` or adaptive thinking, so you must
also delete the `thinking` and `output_config` lines from `api/chat.js` or requests
will 400.

My recommendation: **start on Opus 5.** At Volare's traffic the difference is a few
dollars a month, and the qualifying conversation is the thing you're actually being
paid for. Drop to Sonnet if volume ever makes it matter.

---

## Design decisions worth knowing

**Non-streaming.** Responses are short (2–3 sentences) and run at low effort, so they
land in a couple of seconds behind a typing indicator. Streaming would add real
complexity to the tool loop for a barely perceptible gain here. If you want it later,
swap `messages.create` for `messages.stream` and pipe SSE through the handler.

**Thinking stays on, at low effort.** On Opus 5 thinking is enabled by default.
Disabling it is a known footgun when tools are in play — the model can write a tool
call into its visible text instead of emitting a real `tool_use` block, which means
the lead silently never gets captured. Low effort gets the cost saving without that
risk.

**Manual tool loop rather than the SDK tool runner.** The runner is still beta; this
is a client deliverable that has to keep running unattended for months, so the
stable `client.messages.create` path is the safer bet. The loop is ~30 lines.

**Shadow DOM.** Volare's site is Webflow, which ships aggressive global CSS. The
widget renders in a shadow root so neither side can break the other.

**Notification failures never surface to the visitor.** If Resend has a bad minute,
the model is still told the lead was recorded — nobody gets asked to retype their
email because of our infrastructure. The real error is logged for you to chase.

---

## Known limitations

- **Rate limiting and lead dedupe are per-instance.** Serverless cold starts reset
  both, so a rare duplicate lead email is possible. Add Vercel KV or Upstash if that
  ever becomes annoying.
- **No CRM write.** Leads go to email and WhatsApp only. Adding a HubSpot/Pipedrive
  push is a small addition to `_notify.js` — and a natural upsell.
- **No conversation storage.** Transcripts exist only in the notification email.
  Persisting them would give Volare a searchable record of what visitors actually ask,
  which is genuinely useful intelligence for their marketing.
