/**
 * Lead notifications. Both channels use plain fetch — no extra dependencies.
 *
 * Email (Resend) is required; WhatsApp (Twilio) is optional and silently skipped
 * unless all four TWILIO_* vars are set. Every account here belongs to the agency,
 * so the client never signs up for anything.
 */

const esc = (s) =>
  String(s ?? '').replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' })[c]);

/** Non-empty fields of the lead, in a stable display order. */
function leadFields(lead) {
  return [
    ['Name', lead.name],
    ['Email', lead.email],
    ['Phone', lead.phone],
    ['Company', lead.company],
    ['Industry', lead.industry],
    ['Revenue', lead.revenue_range],
    ['Urgency', lead.urgency?.replace(/_/g, ' ')],
  ].filter(([, v]) => v);
}

function buildEmail(lead, transcript) {
  const rows = leadFields(lead)
    .map(
      ([k, v]) =>
        `<tr><td style="padding:6px 16px 6px 0;color:#6b7280;white-space:nowrap">${esc(k)}</td>` +
        `<td style="padding:6px 0;color:#111827;font-weight:600">${esc(v)}</td></tr>`,
    )
    .join('');

  const chat = transcript
    .map(
      (m) =>
        `<p style="margin:0 0 10px"><strong style="color:#6b7280">` +
        `${m.role === 'user' ? 'Visitor' : 'Assistant'}:</strong> ${esc(m.content)}</p>`,
    )
    .join('');

  const html = `<div style="font-family:ui-sans-serif,system-ui,-apple-system,sans-serif;max-width:640px;margin:0 auto;padding:24px">
  <h2 style="margin:0 0 4px;font-size:20px;color:#111827">New lead from volare.ai</h2>
  <p style="margin:0 0 20px;color:#6b7280;font-size:14px">Captured by the website assistant</p>
  <table style="border-collapse:collapse;font-size:14px;margin-bottom:20px">${rows}</table>
  <div style="padding:14px 16px;background:#f9fafb;border-left:3px solid #111827;border-radius:4px;margin-bottom:24px">
    <p style="margin:0;font-size:14px;line-height:1.6;color:#111827">${esc(lead.summary)}</p>
  </div>
  <a href="mailto:${esc(lead.email)}" style="display:inline-block;padding:10px 18px;background:#111827;color:#fff;text-decoration:none;border-radius:6px;font-size:14px;font-weight:600">Reply to ${esc(lead.name)}</a>
  <h3 style="margin:28px 0 10px;font-size:14px;color:#6b7280;text-transform:uppercase;letter-spacing:.05em">Transcript</h3>
  <div style="font-size:13px;line-height:1.6;color:#374151">${chat}</div>
</div>`;

  const text = [
    'New lead from volare.ai',
    '',
    ...leadFields(lead).map(([k, v]) => `${k}: ${v}`),
    '',
    lead.summary,
    '',
    '--- Transcript ---',
    ...transcript.map((m) => `${m.role === 'user' ? 'Visitor' : 'Assistant'}: ${m.content}`),
  ].join('\n');

  return { html, text };
}

async function sendEmail(lead, transcript) {
  const { RESEND_API_KEY, LEAD_EMAIL_TO, LEAD_EMAIL_FROM } = process.env;
  if (!RESEND_API_KEY || !LEAD_EMAIL_TO || !LEAD_EMAIL_FROM) {
    throw new Error('Email not configured (RESEND_API_KEY / LEAD_EMAIL_TO / LEAD_EMAIL_FROM)');
  }

  const { html, text } = buildEmail(lead, transcript);
  const res = await fetch('https://api.resend.com/emails', {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${RESEND_API_KEY}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      from: LEAD_EMAIL_FROM,
      // Comma-separated list is supported, e.g. "shamus@volare.ai,team@volare.ai"
      to: LEAD_EMAIL_TO.split(',').map((s) => s.trim()),
      reply_to: lead.email,
      subject: `New lead: ${lead.name}${lead.company ? ` (${lead.company})` : ''}`,
      html,
      text,
    }),
  });

  if (!res.ok) throw new Error(`Resend ${res.status}: ${await res.text()}`);
}

async function sendWhatsApp(lead) {
  const { TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_WHATSAPP_FROM, WHATSAPP_TO } = process.env;
  if (!TWILIO_ACCOUNT_SID || !TWILIO_AUTH_TOKEN || !TWILIO_WHATSAPP_FROM || !WHATSAPP_TO) return;

  const body = [
    `*New lead from volare.ai*`,
    ...leadFields(lead).map(([k, v]) => `${k}: ${v}`),
    '',
    lead.summary,
  ].join('\n');

  const res = await fetch(
    `https://api.twilio.com/2010-04-01/Accounts/${TWILIO_ACCOUNT_SID}/Messages.json`,
    {
      method: 'POST',
      headers: {
        Authorization:
          'Basic ' + Buffer.from(`${TWILIO_ACCOUNT_SID}:${TWILIO_AUTH_TOKEN}`).toString('base64'),
        'Content-Type': 'application/x-www-form-urlencoded',
      },
      body: new URLSearchParams({
        From: `whatsapp:${TWILIO_WHATSAPP_FROM}`,
        To: `whatsapp:${WHATSAPP_TO}`,
        Body: body,
      }),
    },
  );

  if (!res.ok) throw new Error(`Twilio ${res.status}: ${await res.text()}`);
}

/**
 * Fan out to every configured channel. Never throws: a failed notification must not
 * break the visitor's conversation. Returns true if at least one channel delivered.
 */
export async function notifyLead(lead, transcript) {
  const results = await Promise.allSettled([sendEmail(lead, transcript), sendWhatsApp(lead)]);

  for (const r of results) {
    if (r.status === 'rejected') console.error('[lead-notify]', r.reason?.message ?? r.reason);
  }
  // sendWhatsApp resolves without sending when unconfigured, so email is the real signal.
  return results[0].status === 'fulfilled';
}
