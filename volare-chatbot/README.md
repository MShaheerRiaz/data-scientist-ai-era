# Volare AI — lead-capture chat widget

A coded replacement for the n8n chatbot, built so **the client sets up nothing**.
No accounts, no API keys, no OAuth screens. Volare pastes one `<script>` tag into
Framer (or Webflow) and is done. Every credential lives in your agency's Vercel
project. The model runs through **OpenRouter**, so you manage one balance and can
switch models with a single env var.

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
| `api/chat.js` | Request handling, the OpenRouter tool loop, rate limiting, CORS |
| `api/_notify.js` | Resend email + optional Twilio WhatsApp |
| `public/widget.js` | The embeddable widget — zero dependencies, renders in a shadow root |

There are **no npm dependencies** — everything uses built-in `fetch`, so `npm install`
is a no-op and deploys are instant.

---

## Deploy

Easiest path — **no laptop, no CLI, all from the browser**:

1. Go to [vercel.com/new](https://vercel.com/new) and import this GitHub repo.
2. Set **Root Directory** to `volare-chatbot`.
3. Add the environment variables below under **Settings → Environment Variables**.
4. Deploy. Vercel gives you a URL like `volare-chatbot.vercel.app`.

Environment variables (see `.env.example` for the annotated list):

```
OPENROUTER_API_KEY   sk-or-...
OPENROUTER_MODEL     anthropic/claude-sonnet-4.5   (or any model on your account)
RESEND_API_KEY       re_...
LEAD_EMAIL_FROM      Volare Assistant <leads@yourdomain.com>
LEAD_EMAIL_TO        shamus@volare.ai
ALLOWED_ORIGINS      https://volare.framer.website,https://volare.ai,https://www.volare.ai
```

CLI alternative, if you prefer:

```bash
cd volare-chatbot
npx vercel                    # first deploy, creates the project
# add the same vars with: npx vercel env add NAME production
npx vercel --prod
```

**Before going live**, set `ALLOWED_ORIGINS` to the domains the widget loads on —
your Framer preview URL plus the live site, e.g.
`https://volare.framer.website,https://volare.ai,https://www.volare.ai`. With it unset
the API accepts requests from any origin — fine for local testing, not for production,
since anyone could point their own page at your endpoint and spend your OpenRouter
credits.

### Local development

```bash
cp .env.example .env.local     # fill in the values
npx vercel dev                 # → http://localhost:3000/demo.html
```

---

## The embed snippet

This is the only thing Volare ever touches. In **Framer**: Project Settings → General
→ Custom Code → **End of `<body>` tag**, paste, publish. (Webflow: Site Settings →
Custom Code → Footer Code.)

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

Rough figures for a realistic 8-exchange conversation, through OpenRouter. You pick
the model by setting `OPENROUTER_MODEL` — no code change either way. Check live prices
on your OpenRouter dashboard; these are ballpark.

| `OPENROUTER_MODEL` | Per conversation | 300/month | Notes |
| --- | --- | --- | --- |
| `anthropic/claude-sonnet-4.5` (default) | ~$0.05 | ~$15 | Strong judgement on qualifying and when to ask for the email |
| `openai/gpt-4.1-mini` | ~$0.02 | ~$6 | Cheaper, still good enough for this task |
| `google/gemini-2.5-flash` | ~$0.01 | ~$3 | Cheapest; test the qualifying quality first |

Switching model is one env var — the tool loop is standard OpenAI format, so any
tool-calling model on OpenRouter works. Start on Sonnet 4.5; drop to a cheaper model
if volume ever makes it matter.

---

## Design decisions worth knowing

**OpenRouter, OpenAI-format.** One balance, one key, any model. The request is a
plain `chat/completions` call with `tools` in function format — nothing model-specific,
so swapping providers is just the `OPENROUTER_MODEL` string.

**Non-streaming.** Responses are short (2–3 sentences), so they land in a couple of
seconds behind a typing indicator. Streaming would add real complexity to the tool
loop for a barely perceptible gain here.

**Manual tool loop.** ~40 lines: call the model, if it asks for `capture_lead` run it
(email + WhatsApp), feed the result back, repeat up to 3 rounds. Capped so a
misbehaving model can't loop forever.

**No npm dependencies.** Everything is built-in `fetch`, so there's nothing to install
and nothing to keep patched.

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
