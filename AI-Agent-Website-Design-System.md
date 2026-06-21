# AI Orchestration Platform — Design System & Brief for Claude (Design)

> **How to use this document:** Paste this entire file into Claude Design. It is written as an instruction set, not a description. Follow it closely. The product is an **AI orchestration platform**: one primary "Orchestrator" agent that plans, delegates, and supervises **multiple specialized sub-agents** that execute work in parallel. The whole design must express *one mind directing many hands*.
>
> **Build target:** This will be built in **Framer**. Every layout decision must be **absolutely responsive across breakpoints** (Desktop, Tablet, Mobile-L, Mobile-S). See the **Responsive** section — treat it as mandatory, not optional. Use Framer-native Stacks/Auto-layout, relative units, min/max constraints, and breakpoint variants for every component. Nothing should be pixel-pinned in a way that breaks on resize.

---

## 1. Inspiration & References (what we're borrowing, and why)

I researched the current (2026) AI-product and SaaS design landscape. These are the reference points and the *specific* thing to steal from each:

| Reference | What to borrow |
|---|---|
| **Cognition / Devin** (autonomous engineer) | Calm confidence, "the agent is working for you" framing, sandboxed-environment visuals, restrained palette. |
| **Cursor** (agentic editor) | High-contrast dark UI, crisp product screenshots as hero, "it reads everything, then acts" narrative. |
| **Sierra / Decagon** (customer-experience agents) | Enterprise trust signals, named-customer proof, warmth inside a technical product. |
| **Lindy** (build-an-agent-in-minutes) | Friendly approachability, visual workflow/agent-builder canvas, "describe it in natural language" simplicity. |
| **n8n / LangGraph / CrewAII** (orchestration & graphs) | **The hero visual metaphor**: a node graph where one node delegates to others. This is *our* signature image. |

**The 2026 trends we will lean into** (from current SaaS/AI design research):
- **Dark-mode-first** — now an expectation, not a novelty. We design dark as primary, with a true light variant.
- **Oversized, assertive typography** — type is the headline act. Big, tight, confident headers.
- **Gradients + subtle glow + glassmorphism** — translucent layers for depth in dark UI without color noise.
- **Kinetic / variable type & motion-on-scroll** — restrained, purposeful, never decorative-for-its-own-sake.
- **Editorial serif accent in italic** — a serif italic mixed into a tight sans is the fastest way to look *designed*, not *templated*. We use it sparingly for emphasis words.
- **Bento grids & node-graph diagrams** — to explain the multi-agent architecture visually.

**Our signature idea:** Everywhere possible, visualize the **hub-and-spoke "constellation"**: a bright Orchestrator core connected by animated lines to a ring of sub-agent nodes, each lighting up as it works. This is the through-line of the brand.

---

## 2. Brand Concept & Personality

**Concept name (working / placeholder):** "The Orchestrator." Replace with the real product name; keep the metaphor.

**One-line positioning:** *One agent to command them all — describe the goal, and a coordinated team of AI agents gets it done.*

**Personality (pick the dial position):**
- Intelligent, not academic.
- Calm and in-control, not loud or hypey.
- Powerful but approachable — "mission control you can actually drive."
- Technical credibility *with* human warmth (the serif accent + warm micro-copy carry the warmth).

**Tone words:** Orchestrated · Effortless · Capable · Transparent · Premium.

**Avoid:** Generic "robot/cyberpunk neon," stocky AI-brain imagery, rainbow gradients, clutter.

---

## 3. Color System

Dark-first. All values are tokens — implement them as **Framer color styles / variables** with these exact names so they can be swapped globally.

### 3.1 Core Neutrals (Dark theme — primary)
A near-black base with a subtle blue-violet undertone (reads as "intelligent," not flat black).

| Token | Hex | Use |
|---|---|---|
| `bg/base` | `#07070B` | Page background (deepest). |
| `bg/raised` | `#0D0D14` | Section backgrounds, large blocks. |
| `surface/1` | `#121219` | Cards, panels. |
| `surface/2` | `#191922` | Elevated cards, popovers, hover surface. |
| `surface/3` | `#22222E` | Active/selected surface, inputs. |
| `border/subtle` | `#1E1E28` | Hairline dividers. |
| `border/default` | `#2A2A38` | Card borders. |
| `border/strong` | `#3A3A4D` | Focus rings, emphasized borders. |

### 3.2 Text
| Token | Hex | Use |
|---|---|---|
| `text/primary` | `#F4F4F8` | Headlines, primary copy. |
| `text/secondary` | `#A9A9BD` | Body, descriptions. |
| `text/tertiary` | `#6E6E85` | Captions, labels, metadata. |
| `text/disabled` | `#48485A` | Disabled states. |
| `text/on-accent` | `#0A0A0F` | Text on bright accent fills. |

### 3.3 Brand & Accent
The **Orchestrator** owns **Iris/Violet** (the commanding primary). The **sub-agents** are differentiated by **Cyan** (the secondary). A warm **Amber** is a sparing tertiary highlight.

| Token | Hex | Use |
|---|---|---|
| `brand/primary` (Orchestrator) | `#6E56F7` | Primary buttons, key accents, the hub node. |
| `brand/primary-hover` | `#5A43E8` | Hover/pressed. |
| `brand/primary-soft` | `#1A1530` | Tinted backgrounds, badges. |
| `accent/cyan` (Sub-agents) | `#2DE3D0` | Sub-agent nodes, active/running glow, data viz. |
| `accent/cyan-soft` | `#0C2A2A` | Cyan tinted backgrounds. |
| `accent/amber` | `#FFB454` | Sparing highlight, "human-in-the-loop" moments. |

### 3.4 Agent State Colors (functional — used in the orchestration UI/diagrams)
These tell the story of agents working. Use consistently in product shots, diagrams, and the live "constellation."

| State | Token | Hex |
|---|---|---|
| Idle / queued | `state/idle` | `#6E6E85` |
| Thinking / planning | `state/thinking` | `#6E56F7` (violet pulse) |
| Running / executing | `state/running` | `#2DE3D0` (cyan pulse) |
| Success / done | `state/success` | `#3DD68C` |
| Needs input / warning | `state/warning` | `#FFB454` |
| Failed / error | `state/error` | `#FB6A6A` |

### 3.5 Gradients & Effects
- `gradient/aurora` — primary hero mesh: `#6E56F7` → `#7B5CF0` → `#2DE3D0`, soft radial, low saturation at edges. Use behind hero and section transitions at low opacity.
- `gradient/halo` — radial glow for the Orchestrator hub: center `#6E56F7` at ~40% opacity fading to transparent.
- `glow/node` — sub-agent node glow: `#2DE3D0` outer glow, tight radius.
- **Glassmorphism:** `surface/2` at 60–70% opacity + 16–24px backdrop blur + `border/default` 1px. Use for floating panels, nav-on-scroll, and stat cards over the gradient.

### 3.6 Light Theme (secondary — must exist for the toggle)
| Token | Hex |
|---|---|
| `bg/base` | `#FBFBFD` |
| `surface/1` | `#FFFFFF` |
| `surface/2` | `#F4F4F8` |
| `border/default` | `#E5E5EC` |
| `text/primary` | `#0E0E14` |
| `text/secondary` | `#54546A` |
| `brand/primary` | `#5A43E8` (slightly darker for AA contrast on light) |

> **Contrast rule:** All text must meet **WCAG AA** (4.5:1 body, 3:1 large). Verify `text/secondary` on every surface it sits on. Never put `brand/primary` text on `bg/base` for body copy — use it for large display or fills only.

---

## 4. Typography

**Pairing (all free + Framer/Google-Fonts native, so they load cleanly in Framer):**

- **Display & Headings → `Space Grotesk`** — geometric, technical, distinctive. Signals "AI/engineering" without being cold. Use for H1–H4, big numbers, nav.
- **Body & UI → `Inter`** — the legibility workhorse. All paragraphs, labels, buttons, inputs.
- **Editorial accent → `Instrument Serif` (italic)** — *one* emphasized word or short phrase per major section ("get it *done*", "*orchestrated*"). This is the "designed, not templated" touch. Use sparingly.
- **Mono / system → `JetBrains Mono`** — agent logs, code, status labels, tags, timestamps. Reinforces the "system/console" feel.

### 4.1 Type Scale (responsive — desktop → mobile)
Use a fluid `clamp()` mindset. Framer: set desktop sizes, then reduce per breakpoint as noted.

| Role | Font | Desktop | Mobile | Weight | Tracking | Line-height |
|---|---|---|---|---|---|---|
| Display / Hero | Space Grotesk | 72px | 40px | 600 | −2% | 1.02 |
| H1 | Space Grotesk | 56px | 34px | 600 | −1.5% | 1.05 |
| H2 | Space Grotesk | 40px | 28px | 600 | −1% | 1.1 |
| H3 | Space Grotesk | 28px | 22px | 500 | −0.5% | 1.2 |
| H4 / Eyebrow | Space Grotesk | 18px | 16px | 500 | +2% (uppercase) | 1.3 |
| Body L | Inter | 20px | 17px | 400 | 0 | 1.55 |
| Body M (default) | Inter | 17px | 16px | 400 | 0 | 1.6 |
| Body S / Caption | Inter | 14px | 13px | 400 | +1% | 1.5 |
| Label / Mono | JetBrains Mono | 13px | 12px | 500 | +3% (uppercase) | 1.4 |
| Serif accent | Instrument Serif | inherit (italic) | inherit | 400 | 0 | inherit |

**Rules:**
- Headlines: tight tracking, generous size, max-width ~14 words. Let them breathe.
- Body: never exceed ~70ch line length. Use `text/secondary` for paragraphs, `text/primary` for leads.
- Eyebrows/labels: uppercase mono or Space Grotesk with positive tracking, in `accent/cyan` or `text/tertiary`.

---

## 5. Spacing, Grid & Layout

- **Base unit: 8px.** Spacing scale: 4, 8, 12, 16, 24, 32, 48, 64, 96, 128.
- **Max content width:** 1280px, centered, with 24px (mobile) → 80px (desktop) side gutters.
- **Grid:** 12-column desktop, 8-column tablet, 4-column mobile. Column gap 24px desktop / 16px mobile.
- **Section rhythm:** vertical padding 96–128px desktop, 64px tablet, 48px mobile.
- **Radii:** `sm` 8px (inputs, tags), `md` 12px (buttons), `lg` 16px (cards), `xl` 24px (large panels), `full` 999px (pills, avatars).
- **Elevation:** prefer borders + subtle inner glow over heavy shadows. When shadow is needed: `0 8px 40px rgba(0,0,0,0.5)` for floating elements only.

---

## 6. Core Components

Build each as a Framer component with breakpoint variants and interaction states (default / hover / active / focus / disabled).

**Buttons**
- *Primary:* `brand/primary` fill, `text/on-accent`, radius `md`, 12×24 padding; hover → `brand/primary-hover` + soft violet glow.
- *Secondary:* transparent fill, `border/default`, `text/primary`; hover → `surface/2`.
- *Ghost/Tertiary:* text-only with cyan underline-on-hover.
- Sizes: S / M / L. Always min 44px tap height on mobile.

**Navigation**
- Transparent at top → on scroll becomes a **glass bar** (`surface/2` blur). Logo left, links center, primary CTA + theme toggle right. Mobile: hamburger → full-screen overlay menu with large Space Grotesk links.

**Cards**
- `surface/1`, `border/default`, radius `lg`, 24–32px padding. Hover: border → `border/strong`, slight lift, faint violet/cyan glow.

**Agent Node (signature component)**
- Circular/rounded node with an icon, a name (mono label), and a **state ring** colored by `state/*`. Animated pulse when "running" (cyan) or "thinking" (violet). Orchestrator node is larger, violet, with a `gradient/halo`.

**Orchestration Diagram / Constellation (hero centerpiece)**
- One large Orchestrator hub center; 4–6 sub-agent nodes around it; animated connecting lines with traveling dots showing delegation/data flow. Nodes light up sequentially. Must gracefully reflow to a **vertical stack** on mobile (hub on top, agents listed below with a connecting spine).

**Other:** Bento feature grid, stat cards (glass over gradient), logo/customer marquee, pricing tiers (highlight the middle), testimonial cards, FAQ accordion, footer with sitemap + newsletter.

---

## 7. Motion (restrained & purposeful)

- **Easing:** custom ease-out `cubic-bezier(0.16, 1, 0.3, 1)` for entrances; 200–400ms.
- **Scroll reveals:** fade + 16px rise, staggered 60ms between siblings.
- **Constellation:** continuous low-energy ambient motion (lines pulse, dots travel) — slow, hypnotic, never frantic. Respect `prefers-reduced-motion`: drop to static states.
- **Hover:** micro-glow + 2–4px lift. **Buttons:** quick 120ms press.
- Motion should *explain* the product (delegation, flow, completion), not just decorate.

---

## 8. Iconography & Imagery

- **Icons:** thin-to-medium line icons, consistent 1.5px stroke, rounded joins (e.g., Lucide/Phosphor style). Tint with `text/secondary` default, `accent/cyan` when active.
- **Imagery:** real product UI screenshots in dark theme, framed in glass mockups with subtle gradient backdrops. Abstract node/constellation graphics for concept sections. **No cheesy robots or glowing-brain stock.**
- **Texture:** very subtle noise/grain over the base background and faint dotted grid in hero to add depth.

---

## 9. Page Structure (landing page)

1. **Nav** (transparent → glass on scroll).
2. **Hero** — oversized headline with one Instrument Serif italic accent word; subhead; primary + secondary CTA; **the constellation diagram** as the visual; aurora gradient + grain behind.
3. **Logo marquee** — "trusted by / works with."
4. **The Problem → The Shift** — short editorial section (serif accents) on why single agents aren't enough.
5. **How it works** — 3 steps: *Describe the goal → Orchestrator plans & delegates → Agents execute in parallel, you watch live.* Use animated node states.
6. **Capabilities bento grid** — parallel execution, transparency/observability, human-in-the-loop, integrations, memory, guardrails.
7. **Live orchestration showcase** — product screenshot / interactive constellation with state colors.
8. **Use cases** — tabbed (research, ops, engineering, support).
9. **Trust & security** — enterprise signals, badges.
10. **Pricing** — 3 tiers, middle highlighted in violet.
11. **Testimonials / proof.**
12. **Big CTA** — gradient panel, "Command your first agent team."
13. **Footer.**

---

## 10. RESPONSIVE — MANDATORY (read this twice)

**The design must be absolutely responsive across every breakpoint.** This is a hard requirement because it's being built in Framer. Apply these rules to *every* frame and component:

**Breakpoints (Framer):**
- **Desktop:** 1280px (design baseline) — and ensure graceful behaviour up to 1920px (max content width caps at 1280, gutters grow).
- **Tablet:** 810px.
- **Mobile-L:** 390px.
- **Mobile-S:** 320px (must not break or clip).

**Rules:**
1. **Use Framer Stacks / Auto-layout for everything.** No absolute-positioned elements that can't reflow. Set fill/fixed/relative sizing deliberately.
2. **Fluid type:** headlines scale down per the type scale (Section 4). Use clamp-style behaviour so text never overflows or gets tiny.
3. **Reflow multi-column → single-column** on tablet/mobile. The bento grid: 3-col → 2-col → 1-col. Pricing: 3 across → stacked.
4. **The constellation/orchestration diagram must reflow** from a radial hub-and-spoke (desktop) to a **vertical stacked spine** (mobile) — never let it overflow or shrink into an unreadable blob.
5. **Tap targets ≥ 44×44px** on mobile. Nav collapses to hamburger + full-screen menu.
6. **Spacing scales down** per Section 5 (section padding 128 → 64 → 48).
7. **Images/mockups** use relative widths with max-width caps; never fixed pixel widths that overflow small screens.
8. **Test mentally at 320px**: nothing clipped, no horizontal scroll, all CTAs reachable, all text legible.
9. **Sticky nav + CTA** remain accessible on scroll across breakpoints.
10. Honor `prefers-reduced-motion` and `prefers-color-scheme` (default to dark).

> If any layout decision can't be expressed responsively in Framer with Stacks + constraints + breakpoint variants, choose a different layout. Responsiveness is non-negotiable.

---

## 11. Quick-Reference Token Sheet (for fast setup)

```
FONTS
  Display/Headings : Space Grotesk (600/500)
  Body/UI          : Inter (400/500/600)
  Accent (italic)  : Instrument Serif (400)
  Mono/System      : JetBrains Mono (500)

COLOR (DARK — primary)
  bg/base       #07070B    surface/1   #121219
  bg/raised     #0D0D14    surface/2   #191922
  surface/3     #22222E
  border/subtle #1E1E28    border/default #2A2A38   border/strong #3A3A4D
  text/primary  #F4F4F8    text/secondary #A9A9BD   text/tertiary #6E6E85
  brand/primary #6E56F7    primary-hover #5A43E8     primary-soft  #1A1530
  accent/cyan   #2DE3D0    accent/amber  #FFB454

STATES
  idle #6E6E85  thinking #6E56F7  running #2DE3D0
  success #3DD68C  warning #FFB454  error #FB6A6A

GRADIENT/aurora  #6E56F7 → #7B5CF0 → #2DE3D0 (soft radial mesh)

SPACING  4/8/12/16/24/32/48/64/96/128 (8px base)
RADII    sm 8 · md 12 · lg 16 · xl 24 · full 999
GRID     12 / 8 / 4 cols · max 1280 · gutters 24→80
BREAKPTS 1280 · 810 · 390 · 320   (RESPONSIVE = MANDATORY)
```

---

### Final instruction to Claude (Design)
Design the landing page (and reusable component library) for this AI orchestration platform using the system above. Dark-first, premium, calm-but-powerful. Make the **Orchestrator-commands-sub-agents constellation** the signature visual. Use Space Grotesk + Inter + Instrument Serif accent + JetBrains Mono. Apply the exact color tokens. **Every screen must be absolutely responsive across the 1280 / 810 / 390 / 320 breakpoints, built with Framer Stacks/auto-layout so it reflows cleanly — this is a hard requirement.** Prioritize clarity, hierarchy, and the story of *one mind directing many agents.*
