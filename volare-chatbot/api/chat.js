import { SYSTEM_PROMPT, CAPTURE_LEAD_TOOL } from './_prompt.js';
import { notifyLead } from './_notify.js';

// OpenRouter (OpenAI-compatible). Set OPENROUTER_MODEL to any model on your
// OpenRouter account, e.g. anthropic/claude-sonnet-4.5, openai/gpt-4.1-mini,
// google/gemini-2.5-flash. Cheaper model = cheaper conversations, same code.
const OPENROUTER_URL = 'https://openrouter.ai/api/v1/chat/completions';
const MODEL = process.env.OPENROUTER_MODEL || 'anthropic/claude-sonnet-4.5';

const MAX_TURNS = 24; // messages kept from the client's history
const MAX_CHARS = 2000; // per message
const MAX_TOOL_ROUNDS = 3; // guard against a tool-call loop
const RATE_LIMIT = { max: 30, windowMs: 60 * 60 * 1000 }; // per IP per hour

// Best-effort, per-instance state. A serverless cold start resets both, so a rare
// duplicate lead or an extra allowed request is possible. Swap in Upstash/Vercel KV
// if you need this to be exact.
const rateLimits = new Map();
const capturedConversations = new Map();
const CAPTURE_TTL_MS = 6 * 60 * 60 * 1000;

// OpenAI-format tool definition, built from the neutral schema in _prompt.js.
const TOOLS = [
  {
    type: 'function',
    function: {
      name: CAPTURE_LEAD_TOOL.name,
      description: CAPTURE_LEAD_TOOL.description,
      parameters: CAPTURE_LEAD_TOOL.input_schema,
    },
  },
];

function sweep(map) {
  const now = Date.now();
  for (const [k, expiry] of map) if (expiry < now) map.delete(k);
}

function rateLimited(ip) {
  const now = Date.now();
  const entry = rateLimits.get(ip);
  if (!entry || entry.resetAt < now) {
    rateLimits.set(ip, { count: 1, resetAt: now + RATE_LIMIT.windowMs });
    return false;
  }
  entry.count += 1;
  return entry.count > RATE_LIMIT.max;
}

function applyCors(req, res) {
  const allowed = (process.env.ALLOWED_ORIGINS || '')
    .split(',')
    .map((s) => s.trim())
    .filter(Boolean);
  const origin = req.headers.origin;

  // With no allowlist configured we fall back to '*' so local testing works out of
  // the box. Always set ALLOWED_ORIGINS in production.
  if (allowed.length === 0) res.setHeader('Access-Control-Allow-Origin', '*');
  else if (origin && allowed.includes(origin)) res.setHeader('Access-Control-Allow-Origin', origin);
  else return false;

  res.setHeader('Vary', 'Origin');
  res.setHeader('Access-Control-Allow-Methods', 'POST, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');
  res.setHeader('Access-Control-Max-Age', '86400');
  return true;
}

/** Keep only well-formed, recent, length-capped turns. Never trust the client. */
function sanitizeHistory(raw) {
  if (!Array.isArray(raw)) return [];
  return raw
    .filter(
      (m) =>
        m &&
        (m.role === 'user' || m.role === 'assistant') &&
        typeof m.content === 'string' &&
        m.content.trim(),
    )
    .slice(-MAX_TURNS)
    .map((m) => ({ role: m.role, content: m.content.slice(0, MAX_CHARS) }));
}

const isEmail = (s) => typeof s === 'string' && /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(s.trim());

/** One call to OpenRouter. Throws on non-2xx so the handler can map the status. */
async function callModel(messages) {
  const res = await fetch(OPENROUTER_URL, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${process.env.OPENROUTER_API_KEY}`,
      'Content-Type': 'application/json',
      // Optional attribution shown on your OpenRouter dashboard.
      'HTTP-Referer': process.env.SITE_URL || 'https://volare.ai',
      'X-Title': 'Volare AI Assistant',
    },
    body: JSON.stringify({
      model: MODEL,
      max_tokens: 1024,
      tools: TOOLS,
      tool_choice: 'auto',
      messages,
    }),
  });

  if (!res.ok) {
    const body = await res.text();
    const err = new Error(`OpenRouter ${res.status}: ${body}`);
    err.status = res.status;
    throw err;
  }
  return res.json();
}

export default async function handler(req, res) {
  if (!applyCors(req, res)) return res.status(403).json({ error: 'Origin not allowed' });
  if (req.method === 'OPTIONS') return res.status(204).end();
  if (req.method !== 'POST') return res.status(405).json({ error: 'Method not allowed' });

  if (!process.env.OPENROUTER_API_KEY) {
    console.error('[chat] OPENROUTER_API_KEY is not set');
    return res.status(500).json({ error: 'Assistant is not configured yet.' });
  }

  const ip =
    (req.headers['x-forwarded-for'] || '').split(',')[0].trim() ||
    req.socket?.remoteAddress ||
    'unknown';

  sweep(rateLimits);
  if (rateLimited(ip)) {
    return res.status(429).json({ error: 'Too many messages. Please try again later.' });
  }

  const { message, history, conversationId } = req.body ?? {};
  if (typeof message !== 'string' || !message.trim()) {
    return res.status(400).json({ error: 'message is required' });
  }

  // Plain-text transcript for the notification email (no tool plumbing).
  const transcript = [
    ...sanitizeHistory(history),
    { role: 'user', content: message.slice(0, MAX_CHARS) },
  ];
  // Full message list sent to the model — grows with assistant/tool turns below.
  const messages = [{ role: 'system', content: SYSTEM_PROMPT }, ...transcript];
  let leadCaptured = false;

  try {
    for (let round = 0; round <= MAX_TOOL_ROUNDS; round++) {
      const data = await callModel(messages);
      const choice = data.choices?.[0];
      const msg = choice?.message ?? {};
      const toolCalls = msg.tool_calls ?? [];

      if (toolCalls.length === 0) {
        return res.status(200).json({
          reply: (msg.content || '').trim() || "Sorry — I didn't catch that. Could you rephrase?",
          leadCaptured,
        });
      }

      // Echo the assistant turn (with its tool_calls) back before answering them.
      messages.push(msg);

      for (const call of toolCalls) {
        const push = (content) =>
          messages.push({ role: 'tool', tool_call_id: call.id, content });

        if (call.function?.name !== 'capture_lead') {
          push(`Unknown tool: ${call.function?.name}`);
          continue;
        }

        let lead;
        try {
          lead = JSON.parse(call.function.arguments || '{}');
        } catch {
          push('Could not parse the arguments. Ask the visitor to confirm their details.');
          continue;
        }

        if (!isEmail(lead.email)) {
          push("That email doesn't look valid. Ask the visitor to confirm it, then try again.");
          continue;
        }

        sweep(capturedConversations);
        const key = conversationId || `${ip}:${lead.email.toLowerCase()}`;
        if (capturedConversations.has(key)) {
          leadCaptured = true;
          push('Already recorded earlier in this conversation. No action taken.');
          continue;
        }

        const delivered = await notifyLead(lead, transcript);
        if (delivered) {
          capturedConversations.set(key, Date.now() + CAPTURE_TTL_MS);
          leadCaptured = true;
        }
        // Tell the model it succeeded even if delivery failed: the visitor must not
        // be asked to retype details because our mail provider had a bad minute. The
        // real failure is logged in notifyLead for us to chase.
        push('Lead recorded. The Volare team has been notified.');
      }
    }

    // Ran out of tool rounds without a plain text answer.
    return res.status(200).json({
      reply: `Got it — someone from the team will be in touch. If you'd like to move faster, you can book a call at ${process.env.BOOKING_URL || 'https://volare.ai/booking-survey'}.`,
      leadCaptured,
    });
  } catch (err) {
    console.error('[chat]', err.message);
    if (err.status === 429) {
      return res.status(429).json({ error: 'Busy right now — please try again in a moment.' });
    }
    return res
      .status(500)
      .json({ error: 'Something went wrong on our end. Please try again shortly.' });
  }
}
