import Anthropic from '@anthropic-ai/sdk';
import { SYSTEM_PROMPT, CAPTURE_LEAD_TOOL } from './_prompt.js';
import { notifyLead } from './_notify.js';

const client = new Anthropic(); // reads ANTHROPIC_API_KEY

// Single knob for the cost/quality tradeoff. See README for per-conversation numbers.
const MODEL = process.env.CLAUDE_MODEL || 'claude-opus-5';

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

const textOf = (content) =>
  content
    .filter((b) => b.type === 'text')
    .map((b) => b.text)
    .join('')
    .trim();

export default async function handler(req, res) {
  if (!applyCors(req, res)) return res.status(403).json({ error: 'Origin not allowed' });
  if (req.method === 'OPTIONS') return res.status(204).end();
  if (req.method !== 'POST') return res.status(405).json({ error: 'Method not allowed' });

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

  const transcript = [
    ...sanitizeHistory(history),
    { role: 'user', content: message.slice(0, MAX_CHARS) },
  ];
  // Grows with tool_use / tool_result blocks during the loop below; `transcript` stays
  // plain text for the notification email.
  const messages = [...transcript];
  let leadCaptured = false;

  try {
    for (let round = 0; round <= MAX_TOOL_ROUNDS; round++) {
      const response = await client.messages.create({
        model: MODEL,
        max_tokens: 2048, // thinking shares this budget — leave headroom
        system: [
          // The prompt is well over the 512-token cache minimum, so every turn after
          // the first reads it at ~10% of input price instead of paying full freight.
          { type: 'text', text: SYSTEM_PROMPT, cache_control: { type: 'ephemeral' } },
        ],
        thinking: { type: 'adaptive' },
        output_config: { effort: 'low' },
        tools: [CAPTURE_LEAD_TOOL],
        messages,
      });

      // Check before touching content: a refusal can arrive with content empty.
      if (response.stop_reason === 'refusal') {
        return res.status(200).json({
          reply: `I can't help with that one. If you'd like to talk to an advisor directly, you can reach the team at ${process.env.LEAD_EMAIL_TO || 'volare.ai'}.`,
          leadCaptured: false,
        });
      }

      const toolUses = response.content.filter((b) => b.type === 'tool_use');
      if (toolUses.length === 0) {
        return res.status(200).json({
          reply: textOf(response.content) || "Sorry — I didn't catch that. Could you rephrase?",
          leadCaptured,
        });
      }

      // Echo the full content back, thinking blocks included — required by the API.
      messages.push({ role: 'assistant', content: response.content });

      const toolResults = [];
      for (const call of toolUses) {
        if (call.name !== 'capture_lead') {
          toolResults.push({
            type: 'tool_result',
            tool_use_id: call.id,
            content: `Unknown tool: ${call.name}`,
            is_error: true,
          });
          continue;
        }

        const lead = call.input ?? {};
        if (!isEmail(lead.email)) {
          toolResults.push({
            type: 'tool_result',
            tool_use_id: call.id,
            content:
              "That email address doesn't look valid. Ask the visitor to confirm it, then try again.",
            is_error: true,
          });
          continue;
        }

        sweep(capturedConversations);
        const key = conversationId || `${ip}:${lead.email.toLowerCase()}`;
        if (capturedConversations.has(key)) {
          leadCaptured = true;
          toolResults.push({
            type: 'tool_result',
            tool_use_id: call.id,
            content: 'Already recorded earlier in this conversation. No action taken.',
          });
          continue;
        }

        const delivered = await notifyLead(lead, transcript);
        if (delivered) {
          capturedConversations.set(key, Date.now() + CAPTURE_TTL_MS);
          leadCaptured = true;
        }
        // Even on failure we tell the model it succeeded: the visitor shouldn't be
        // asked to re-enter details because our mail provider had a bad minute. The
        // real failure is logged in notifyLead for us to chase.
        toolResults.push({
          type: 'tool_result',
          tool_use_id: call.id,
          content: 'Lead recorded. The Volare team has been notified.',
        });
      }

      messages.push({ role: 'user', content: toolResults });
    }

    // Ran out of tool rounds without a final text answer.
    return res.status(200).json({
      reply: `Got it — someone from the team will be in touch. If you'd like to move faster, you can book a call at ${process.env.BOOKING_URL || 'https://volare.ai/booking-survey'}.`,
      leadCaptured,
    });
  } catch (err) {
    console.error('[chat]', err);
    if (err instanceof Anthropic.RateLimitError) {
      return res.status(429).json({ error: 'Busy right now — please try again in a moment.' });
    }
    return res
      .status(500)
      .json({ error: 'Something went wrong on our end. Please try again shortly.' });
  }
}
