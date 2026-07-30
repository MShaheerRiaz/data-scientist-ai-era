/**
 * Volare AI chat widget.
 *
 * Embed with a single tag — nothing else to install or configure:
 *
 *   <script src="https://YOUR-DEPLOYMENT/widget.js"
 *           data-api="https://YOUR-DEPLOYMENT/api/chat"
 *           defer></script>
 *
 * Content attributes:
 *   data-title, data-subtitle, data-greeting, data-placeholder, data-legal,
 *   data-booking-url, data-position="left|right"
 *
 * Appearance attributes — all optional, all fall back to the theme preset:
 *   data-theme="light|dark"   preset surfaces (default light)
 *   data-accent               buttons, launcher, visitor bubble
 *   data-accent-text          text on the accent (default #fff)
 *   data-header               header bar background (default: the accent)
 *   data-header-text          header text; defaults to the accent when
 *                             data-header is set, so a white bar gets a
 *                             brand-coloured wordmark
 *   data-header-align="left|center"
 *   data-surface, data-log-bg, data-bubble-bg, data-fg, data-muted,
 *   data-line, data-field     individual surface overrides
 *   data-radius, data-font
 *
 * Renders inside a shadow root, so the host page's CSS can't touch it and vice
 * versa — important when dropping into a Webflow site with global resets.
 */
(function () {
  'use strict';

  // currentScript is null when the tag is injected dynamically (Framer and some
  // tag managers do this), so fall back to locating our own tag by attribute.
  var script =
    document.currentScript ||
    document.querySelector('script[data-api][src*="widget.js"]') ||
    document.querySelector('script[data-api]');

  if (!script) {
    console.error('[volare-widget] Could not locate the widget script tag.');
    return;
  }

  var DARK = script.dataset.theme === 'dark';

  // Surface palette. Every value is overridable per-attribute so the widget can be
  // matched to a host site without editing this file.
  var THEME = DARK
    ? {
        surface: '#0C1512', // panel, header strip, composer
        log: '#0A120F', // message list behind the bubbles
        bubble: '#16211D', // assistant bubble
        fg: '#E9F1ED',
        muted: '#8FA39A',
        line: 'rgba(255,255,255,.10)',
        field: '#111C18',
        shadow: '0 18px 56px rgba(0,0,0,.55)',
      }
    : {
        surface: '#ffffff',
        log: '#fafafa',
        bubble: '#ffffff',
        fg: '#111827',
        muted: '#9aa0a8',
        line: '#eceef1',
        field: '#ffffff',
        shadow: '0 12px 48px rgba(0,0,0,.2)',
      };

  var cfg = {
    api: script.dataset.api,
    accent: script.dataset.accent || (DARK ? '#1FA97A' : '#111827'),
    onAccent: script.dataset.accentText || '#ffffff',
    title: script.dataset.title || 'Volare AI',
    // An explicit data-subtitle="" means "no subtitle", so only default when absent.
    subtitle:
      'subtitle' in script.dataset ? script.dataset.subtitle : 'Typically replies instantly',
    booking: script.dataset.bookingUrl || 'https://volare.ai/booking-survey',
    position: script.dataset.position === 'left' ? 'left' : 'right',
    greeting:
      script.dataset.greeting ||
      "Hi — I'm Volare's assistant. I can explain how the advisory works, what drives your company's value, or get you booked with a founder. What brings you in?",
    placeholder: script.dataset.placeholder || 'Ask about growth, valuation, exit…',
    legal: script.dataset.legal || 'AI assistant — an advisor will follow up personally.',
    // A font-family list may not contain the `inherit` keyword — mixing them voids
    // the whole declaration and the browser silently falls back to serif. Pass
    // data-font="inherit" on its own to pick up the host page's typeface instead.
    font:
      script.dataset.font ||
      'ui-sans-serif,system-ui,-apple-system,"Segoe UI",Roboto,Inter,sans-serif',
    radius: script.dataset.radius || '16px',
    surface: script.dataset.surface || THEME.surface,
    logBg: script.dataset.logBg || THEME.log,
    bubbleBg: script.dataset.bubbleBg || THEME.bubble,
    fg: script.dataset.fg || THEME.fg,
    muted: script.dataset.muted || THEME.muted,
    line: script.dataset.line || THEME.line,
    field: script.dataset.field || THEME.field,
    shadow: THEME.shadow,
    // Header bar: defaults to the accent colour, but set data-header="#fff" with
    // data-header-text="<brand colour>" for a white bar with a coloured wordmark.
    header: script.dataset.header || '',
    headerText: script.dataset.headerText || '',
    headerAlign: script.dataset.headerAlign === 'center' ? 'center' : 'left',
  };
  if (!cfg.header) cfg.header = cfg.accent;
  if (!cfg.headerText) cfg.headerText = script.dataset.header ? cfg.accent : '#ffffff';

  if (!cfg.api) {
    console.error('[volare-widget] Missing data-api attribute on the script tag.');
    return;
  }

  if (/YOUR-DEPLOYMENT/.test(cfg.api)) {
    console.error(
      '[volare-widget] data-api still contains the YOUR-DEPLOYMENT placeholder. ' +
        'Replace it with your deployment domain, e.g. https://your-project.vercel.app/api/chat',
    );
    return;
  }

  // Framer and other SPAs can re-run injected code on client-side navigation.
  if (document.querySelector('[data-volare-widget]')) return;

  var STORE_KEY = 'volare_chat_v1';
  var MAX_LEN = 2000;

  // ---------------------------------------------------------------- state

  var state = { open: false, sending: false, history: [], conversationId: null };

  try {
    var saved = JSON.parse(sessionStorage.getItem(STORE_KEY) || 'null');
    if (saved && Array.isArray(saved.history)) {
      state.history = saved.history;
      state.conversationId = saved.conversationId;
    }
  } catch (e) {
    /* private mode, corrupt payload — start fresh */
  }

  if (!state.conversationId) {
    state.conversationId =
      (crypto.randomUUID && crypto.randomUUID()) || String(Date.now()) + Math.random().toString(36).slice(2);
  }

  function persist() {
    try {
      sessionStorage.setItem(
        STORE_KEY,
        JSON.stringify({ history: state.history.slice(-24), conversationId: state.conversationId }),
      );
    } catch (e) {
      /* over quota or blocked — the chat still works, it just won't survive reload */
    }
  }

  // ---------------------------------------------------------------- markup

  var host = document.createElement('div');
  host.setAttribute('data-volare-widget', '');
  var root = host.attachShadow({ mode: 'open' });

  root.innerHTML = [
    '<style>',
    ':host{all:initial}',
    '*{box-sizing:border-box;margin:0;padding:0;font-family:var(--font)}',
    '.wrap{position:fixed;bottom:20px;' + cfg.position + ':20px;z-index:2147483000;display:flex;flex-direction:column;align-items:flex-end;gap:12px}',
    '.launcher{width:56px;height:56px;border:0;border-radius:50%;background:var(--accent);color:var(--on-accent);cursor:pointer;box-shadow:0 4px 20px rgba(0,0,0,.22);display:flex;align-items:center;justify-content:center;transition:transform .18s ease,box-shadow .18s ease;align-self:flex-end}',
    '.launcher:hover{transform:scale(1.06);box-shadow:0 6px 26px rgba(0,0,0,.3)}',
    '.launcher:focus-visible{outline:3px solid var(--accent);outline-offset:3px}',
    '.launcher svg{width:26px;height:26px;fill:none;stroke:currentColor;stroke-width:2;stroke-linecap:round;stroke-linejoin:round}',
    // dvh excludes the mobile browser's address bar; vh (declared first) is the
    // fallback for browsers that don't support dvh. Without this the panel is taller
    // than the visible viewport on mobile Safari and the header scrolls off-screen.
    '.panel{width:380px;max-width:calc(100vw - 32px);height:560px;max-height:calc(100vh - 120px);max-height:calc(100dvh - 120px);background:var(--surface);border-radius:var(--radius);box-shadow:var(--shadow);display:none;flex-direction:column;overflow:hidden;border:1px solid var(--line)}',
    '.panel.open{display:flex;animation:rise .22s cubic-bezier(.2,.8,.3,1)}',
    '@keyframes rise{from{opacity:0;transform:translateY(12px)}to{opacity:1;transform:none}}',
    '@media (prefers-reduced-motion:reduce){.panel.open{animation:none}.launcher{transition:none}}',
    '.head{background:var(--header);color:var(--header-fg);padding:16px 18px;display:flex;align-items:center;gap:12px;flex-shrink:0;border-bottom:1px solid var(--line)}',
    '.head .id{flex:1;text-align:var(--head-align)}',
    '.head h3{font-size:15px;font-weight:700;line-height:1.3;letter-spacing:-.01em}',
    '.head p{font-size:12px;opacity:.7;margin-top:2px;color:var(--header-fg)}',
    '.close{margin-left:auto;background:transparent;border:0;color:var(--header-fg);cursor:pointer;opacity:.6;padding:4px;border-radius:6px;line-height:0}',
    '.close:hover{opacity:1}.close:focus-visible{outline:2px solid var(--header-fg);outline-offset:2px}',
    '.close svg{width:18px;height:18px;fill:none;stroke:currentColor;stroke-width:2;stroke-linecap:round}',
    '.log{flex:1;overflow-y:auto;padding:18px;display:flex;flex-direction:column;gap:12px;background:var(--log-bg);scroll-behavior:smooth}',
    '.msg{max-width:84%;padding:10px 14px;border-radius:14px;font-size:14px;line-height:1.55;white-space:pre-wrap;overflow-wrap:anywhere}',
    '.msg.bot{background:var(--bubble);color:var(--fg);border:1px solid var(--line);border-bottom-left-radius:4px;align-self:flex-start}',
    '.msg.user{background:var(--accent);color:var(--on-accent);border-bottom-right-radius:4px;align-self:flex-end}',
    '.msg.err{background:#fef2f2;color:#991b1b;border:1px solid #fecaca;align-self:flex-start;font-size:13px}',
    '.msg a{color:inherit;text-decoration:underline;text-underline-offset:2px}',
    '.dots{display:flex;gap:4px;padding:14px;align-self:flex-start;background:var(--bubble);border:1px solid var(--line);border-radius:14px;border-bottom-left-radius:4px}',
    '.dots i{width:7px;height:7px;border-radius:50%;background:var(--muted);animation:blink 1.3s infinite}',
    '.dots i:nth-child(2){animation-delay:.18s}.dots i:nth-child(3){animation-delay:.36s}',
    '@keyframes blink{0%,60%,100%{opacity:.35;transform:translateY(0)}30%{opacity:1;transform:translateY(-3px)}}',
    '.cta{align-self:flex-start;display:inline-block;padding:9px 15px;background:var(--accent);color:var(--on-accent);text-decoration:none;border-radius:9px;font-size:13px;font-weight:600}',
    '.foot{padding:12px;border-top:1px solid var(--line);background:var(--surface);flex-shrink:0}',
    '.row{display:flex;gap:8px;align-items:flex-end}',
    'textarea{flex:1;resize:none;border:1px solid var(--line);border-radius:10px;padding:10px 12px;font-size:14px;line-height:1.45;max-height:110px;color:var(--fg);background:var(--field)}',
    'textarea::placeholder{color:var(--muted)}',
    'textarea:focus{outline:none;border-color:var(--accent);box-shadow:0 0 0 3px color-mix(in srgb,var(--accent) 22%,transparent)}',
    '.send{width:40px;height:40px;flex-shrink:0;border:0;border-radius:10px;background:var(--accent);color:var(--on-accent);cursor:pointer;display:flex;align-items:center;justify-content:center}',
    '.send:disabled{opacity:.4;cursor:not-allowed}',
    '.send:focus-visible{outline:2px solid var(--accent);outline-offset:2px}',
    '.send svg{width:17px;height:17px;fill:none;stroke:currentColor;stroke-width:2;stroke-linecap:round;stroke-linejoin:round}',
    '.legal{text-align:center;font-size:10.5px;color:var(--muted);margin-top:8px}',
    '@media (max-width:440px){.wrap{bottom:12px;left:12px;right:12px;align-items:stretch}.panel{width:100%;height:calc(100vh - 88px);height:calc(100dvh - 88px)}.launcher{align-self:flex-end}}',
    '</style>',
    '<div class="wrap">',
    '  <div class="panel" role="dialog" aria-modal="false" aria-label="Chat with Volare AI">',
    '    <div class="head">',
    '      <div class="id"><h3></h3><p></p></div>',
    '      <button class="close" aria-label="Close chat"><svg viewBox="0 0 24 24"><path d="M18 6 6 18M6 6l12 12"/></svg></button>',
    '    </div>',
    '    <div class="log" role="log" aria-live="polite" aria-atomic="false"></div>',
    '    <div class="foot">',
    '      <div class="row">',
    '        <textarea rows="1" aria-label="Message"></textarea>',
    '        <button class="send" aria-label="Send message"><svg viewBox="0 0 24 24"><path d="m22 2-7 20-4-9-9-4 20-7Z"/></svg></button>',
    '      </div>',
    '      <p class="legal"></p>',
    '    </div>',
    '  </div>',
    '  <button class="launcher" aria-label="Open chat" aria-expanded="false">',
    '    <svg class="ico-chat" viewBox="0 0 24 24"><path d="M21 11.5a8.4 8.4 0 0 1-9 8.4 8.9 8.9 0 0 1-4-.9L3 21l1.9-4.6A8.4 8.4 0 0 1 12 3.1a8.4 8.4 0 0 1 9 8.4Z"/></svg>',
    '  </button>',
    '</div>',
  ].join('');

  // Custom properties are assigned here rather than in an inline style attribute:
  // font stacks contain double quotes ("Segoe UI"), which would terminate the
  // attribute early and silently void every declaration after it.
  var VARS = {
    accent: cfg.accent,
    'on-accent': cfg.onAccent,
    header: cfg.header,
    'header-fg': cfg.headerText,
    'head-align': cfg.headerAlign,
    surface: cfg.surface,
    'log-bg': cfg.logBg,
    bubble: cfg.bubbleBg,
    fg: cfg.fg,
    muted: cfg.muted,
    line: cfg.line,
    field: cfg.field,
    radius: cfg.radius,
    shadow: cfg.shadow,
    font: cfg.font,
  };

  var wrap = root.querySelector('.wrap');
  for (var key in VARS) {
    if (VARS[key]) wrap.style.setProperty('--' + key, VARS[key]);
  }

  var $ = function (sel) {
    return root.querySelector(sel);
  };
  var panel = $('.panel'),
    launcher = $('.launcher'),
    log = $('.log'),
    input = $('textarea'),
    sendBtn = $('.send');

  $('.head h3').textContent = cfg.title;
  $('.head p').textContent = cfg.subtitle;
  $('.legal').textContent = cfg.legal;
  $('textarea').placeholder = cfg.placeholder;
  if (!cfg.subtitle) $('.head p').style.display = 'none';

  // ---------------------------------------------------------------- render

  function scrollDown() {
    log.scrollTop = log.scrollHeight;
  }

  /** Renders text safely, linkifying bare URLs. Never uses innerHTML on model output. */
  function addMessage(role, text) {
    var el = document.createElement('div');
    el.className = 'msg ' + role;

    var parts = String(text).split(/(https?:\/\/[^\s<>"')]+)/g);
    parts.forEach(function (part, i) {
      if (i % 2 === 1) {
        var a = document.createElement('a');
        a.href = part;
        a.target = '_blank';
        a.rel = 'noopener noreferrer';
        a.textContent = part;
        el.appendChild(a);
      } else if (part) {
        el.appendChild(document.createTextNode(part));
      }
    });

    log.appendChild(el);
    scrollDown();
    return el;
  }

  function addBookingCta() {
    var a = document.createElement('a');
    a.className = 'cta';
    a.href = cfg.booking;
    a.target = '_blank';
    a.rel = 'noopener noreferrer';
    a.textContent = 'Book a founder call →';
    log.appendChild(a);
    scrollDown();
  }

  function showTyping() {
    var d = document.createElement('div');
    d.className = 'dots';
    d.innerHTML = '<i></i><i></i><i></i>';
    log.appendChild(d);
    scrollDown();
    return d;
  }

  function paintHistory() {
    log.textContent = '';
    if (state.history.length === 0) {
      addMessage('bot', cfg.greeting);
      return;
    }
    state.history.forEach(function (m) {
      addMessage(m.role === 'user' ? 'user' : 'bot', m.content);
    });
  }

  // ---------------------------------------------------------------- actions

  function setOpen(open) {
    state.open = open;
    panel.classList.toggle('open', open);
    launcher.setAttribute('aria-expanded', String(open));
    launcher.setAttribute('aria-label', open ? 'Close chat' : 'Open chat');
    if (open) setTimeout(function () { input.focus(); }, 60);
  }

  function send() {
    var text = input.value.trim();
    if (!text || state.sending) return;

    state.sending = true;
    sendBtn.disabled = true;
    input.value = '';
    input.style.height = 'auto';

    addMessage('user', text);
    var typing = showTyping();

    fetch(cfg.api, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        message: text.slice(0, MAX_LEN),
        history: state.history.slice(-24),
        conversationId: state.conversationId,
      }),
    })
      .then(function (r) {
        return r.json().then(function (data) {
          return { ok: r.ok, data: data };
        });
      })
      .then(function (res) {
        typing.remove();
        if (!res.ok) {
          addMessage('err', res.data.error || 'Something went wrong. Please try again.');
          return;
        }
        addMessage('bot', res.data.reply);
        state.history.push({ role: 'user', content: text });
        state.history.push({ role: 'assistant', content: res.data.reply });
        persist();
        if (res.data.leadCaptured) addBookingCta();
      })
      .catch(function () {
        typing.remove();
        addMessage(
          'err',
          "Couldn't reach the assistant. Please try again, or email " +
            'shamus@volare.ai.',
        );
      })
      .finally(function () {
        state.sending = false;
        sendBtn.disabled = false;
        input.focus();
      });
  }

  // ---------------------------------------------------------------- wiring

  launcher.addEventListener('click', function () {
    setOpen(!state.open);
  });
  $('.close').addEventListener('click', function () {
    setOpen(false);
    launcher.focus();
  });
  sendBtn.addEventListener('click', send);

  input.addEventListener('keydown', function (e) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      send();
    }
  });
  input.addEventListener('input', function () {
    input.style.height = 'auto';
    input.style.height = Math.min(input.scrollHeight, 110) + 'px';
  });

  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape' && state.open) {
      setOpen(false);
      launcher.focus();
    }
  });

  paintHistory();
  document.body.appendChild(host);

  // Small public API for the host page: window.VolareChat.open()
  window.VolareChat = {
    open: function () { setOpen(true); },
    close: function () { setOpen(false); },
    reset: function () {
      state.history = [];
      persist();
      paintHistory();
    },
  };
})();
