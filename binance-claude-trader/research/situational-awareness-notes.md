# Situational Awareness: The Decade Ahead — Analysis Notes

**Source:** <https://situational-awareness.ai/> — Leopold Aschenbrenner, June 2024, ~165 pages
**Reviewed:** August 2026 (all 9 pages read in full)
**Question being answered:** is this useful for trading or market analysis, and does it help with crypto?

---

## 0. Who wrote it, and the conflict of interest

Aschenbrenner is a former member of OpenAI's Superalignment team, dismissed in April 2024.
He published this in June 2024 and then launched an AGI-focused investment firm
(reported ~$1.5B, backed by the Collison brothers among others).

**This matters for how you read it.** The essay is partly a fund thesis. He states in
Chapter V that he went "all-in leveraged long Nvidia in early 2023," and Chapter IIIa
closes with:

> "(What all of this means for NVDA/TSM/etc. I leave as an exercise for the reader.
> Hint: Those with situational awareness bought much lower than you, but it's still
> not even close to fully priced in.)"

He is talking his book. That doesn't make him wrong — as shown below, he was
substantially right — but read it as an argument from someone positioned, not as
neutral research.

---

## 1. The argument, chapter by chapter

### Introduction
Sets the frame: a few hundred people in SF have "situational awareness"; everyone
else is mispricing what's coming. Claims AGI race has begun, superintelligence by
end of decade, national security forces will be unleashed.

### I. From GPT-4 to AGI: Counting the OOMs
**The load-bearing chapter.** Everything else depends on it.

Method: count orders of magnitude (OOM = 10x) of "effective compute" along three axes.

| Driver | Rate | 2023→2027 |
|---|---|---|
| Physical compute | ~0.5 OOM/year | +2 OOMs (possibly +3) |
| Algorithmic efficiency | ~0.5 OOM/year | ~+2 OOMs (1–3 range) |
| "Unhobbling" (RLHF, chain-of-thought, scaffolding, tools, agents) | not quantified | step-changes |

- GPT-2 (2019) → GPT-4 (2023) was 4.5–6 OOMs, described as preschooler → smart high-schooler
- Expects another ~5 OOMs by end-2027 → another jump of the same size
- Conclusion: "AGI by 2027 is strikingly plausible"
- Defines AGI specifically as *"an AI system that could fully do the work of an AI
  researcher or engineer"* — not a chatbot benchmark

**Acknowledged risk — the data wall:** frontier models already trained on most of
the internet; repetition yields diminishing returns after ~16 epochs. He bets labs
crack it via synthetic data / self-play / RL (the "AlphaGo step 2" analogy) but
concedes "there's a very real chance things stall out."

**Addendum, "this decade or bust":** we are racing through OOMs *now* because of a
one-time scale-up in spending, hardware specialisation and algorithmic low-hanging
fruit. After the early 2030s, progress slows to a slog. So the modal AGI year is
this decade or it's far out.

### II. From AGI to Superintelligence: the Intelligence Explosion
- Don't need to automate everything — just AI research itself
- 100M+ automated researchers running at 10x human speed could compress a decade
  of algorithmic progress (5+ OOMs) into ≤1 year
- Considers bottlenecks honestly: limited compute for experiments, complementarities,
  diminishing returns, fundamental algorithmic limits
- Downstream: robotics solved, R&D explosion, economic growth possibly 30%/year,
  decisive military advantage

### IIIa. Racing to the Trillion-Dollar Cluster ← **THE MARKET CHAPTER**

Training cluster scaling:

| Year | Scale | Cost | Power | Reference |
|---|---|---|---|---|
| 2022 | GPT-4, ~10k H100e | ~$500M | ~10 MW | 10,000 homes |
| 2024 | +1 OOM, ~100k | $billions | ~100 MW | 100,000 homes |
| 2026 | +2 OOMs, ~1M | $10s of B | ~1 GW | Hoover Dam |
| 2028 | +3 OOMs, ~10M | $100s of B | ~10 GW | small US state |
| 2030 | +4 OOMs, ~100M | $1T+ | ~100 GW | >20% of US electricity |

Total annual AI investment:

| Year | Annual investment | Power as % US electricity |
|---|---|---|
| 2024 | ~$150B | 1–2% |
| 2026 | ~$500B | 5% |
| 2028 | ~$2T | 20% |
| 2030 | ~$8T | 100% |

Other claims:
- A big tech company hits **$100B AI revenue run rate ~mid-2026**
- "We might see our first $10T company soon thereafter"
- **Power is the binding constraint**, not chips. Not willingness to spend —
  "Where do I find 10GW?" US electricity generation grew only ~5% in a decade.
- Advocates natural gas (Marcellus shale could support 100GW); argues barriers are
  self-imposed (permitting, NEPA, FERC, climate commitments)
- Chips: AI is <10% of TSMC leading-edge; CoWoS packaging and HBM memory are the
  real near-term bottlenecks
- Historical precedent: Manhattan/Apollo peaked at 0.4% GDP; $1T/yr AI ≈ 3% of GDP;
  British railway investment 1841–50 was ~40% of GDP cumulatively

**Footnote 26** (the explicitly falsifiable one): sell-side assumed 10–20% YoY Nvidia
growth, ~$120–130B CY25. He says "it's been pretty obvious for a while that Nvidia
is going to do over $200B of revenue in CY25."

### IIIb. Lock Down the Labs
Lab security is "swiss cheese"; algorithmic secrets and model weights are the assets.
Claims key AGI breakthroughs will leak to the CCP within 12–24 months. Notes quant
trading firms (Jane Street et al.) as the model for keeping valuable secrets — an
hour of conversation could zero out a firm's alpha, yet they manage it.

### IIIc. Superalignment
Technical AI safety: controlling systems much smarter than us is unsolved but solvable;
things could go off the rails during a fast intelligence explosion.
**No market content.**

### IIId. The Free World Must Prevail
- Superintelligence = decisive military advantage (Gulf War analogy: a 20–30 year tech
  lead annihilated the world's 4th-largest army in 100 hours)
- China can compete: SMIC 7nm is "enough" (A100-class); Huawei Ascend 910B only ~2–3x
  worse perf/$; and **China can outbuild the US on power** — it added roughly the entire
  US electricity capacity in a decade while the US stayed flat
- Notes convergence of AGI timelines (~2027) with Taiwan invasion timelines (~2027)

### IV. The Project
Predicts USG nationalises / consolidates the effort by 2027–28. Labs "voluntarily" merge,
Congress appropriates trillions, structured like the DoD relationship with Boeing or
Lockheed. Argues no startup can hold superintelligence.

### V. Parting Thoughts
"AGI Realism": national security matter, America must lead, don't screw it up.
Contains the leveraged-long-Nvidia disclosure.

---

## 2. Scorecard: what actually happened (checked Aug 2026)

### Capital-flow predictions — STRONG

| Prediction (June 2024) | Actual | Verdict |
|---|---|---|
| Nvidia >$200B revenue CY25 (vs sell-side $120–130B) | FY2026 revenue **$215.9B**, data centre $193.7B (+68%) | **Right; sell-side badly wrong** |
| ~$150B total AI investment 2024 | Broadly consistent | Right |
| ~$500B total AI investment 2026 | Big-4 hyperscaler capex alone **$725B** in 2026 (+77% YoY from $410B) | **Under-predicted** |
| ~$2T by 2028 | Analysts see >$1T in 2027 | On track |
| Power becomes the binding constraint | Confirmed — power/land/permitting is the industry's central problem | Right |
| Big tech AI revenue $100B run rate ~mid-2026 | Directionally tracking | Roughly right |

**He was right, and if anything conservative, on the money flows.**

### AGI timeline — UNRESOLVED

"AGI by 2027," defined as fully automating the work of an AI researcher. As of Aug 2026,
models are dramatically more capable and genuinely agentic, but not drop-in replacements
for cognitive workers at large. Roughly 17 months to his deadline. Not falsified, not
vindicated. The strong form looks unlikely on his schedule; the weak form (huge capability
gains, real automation of parts of software work) is happening.

### Structural predictions — MIXED / PENDING
- Lab security crackdown: partial
- USG "Project" by 27/28: not yet, though state involvement has grown
- Labs merging under government: no

**Pattern: the closer a prediction is to capital and physical constraints, the better it
did. The further into geopolitics and AGI-capability, the shakier.** That is exactly the
pattern you'd expect, and it tells you which parts to use.

---

## 3. Is it useful for trading?

### What it is
A **multi-year macro/thematic investment thesis**. Its correct use is asset allocation
and understanding what drives a sector — deciding *what* to own and *why*, over years.

### What it is not
- Not a trading system. Zero content on entries, exits, position sizing, risk, or timing.
- No falsifiable price targets or levels.
- No mechanism for being wrong gracefully. "It's not priced in" is unfalsifiable on any
  given day; it can be true for years while you get liquidated.

### Where the real value is
1. **The reference-class method.** Counting OOMs, checking against historical capital
   mobilisations, computing power requirements from first principles. That's transferable
   reasoning regardless of whether the conclusion holds.
2. **Constraint identification.** Calling power (not chips) as the binding constraint two
   years early was the single most useful analytical call in the document, and it was
   reached by arithmetic, not vision.
3. **The sell-side gap.** He beat professional analysts on Nvidia by a factor of ~1.7x
   using public information and trend extrapolation. Evidence that consensus systematically
   under-extrapolates exponentials.

### The trap
Being right about the technology is not the same as being right about the trade.
Telecoms invested ~$1T in internet infrastructure 1996–2001 — the internet thesis was
completely correct, and most of those investors were wiped out. He cites this precedent
himself without drawing the obvious warning from it.

---

## 4. Is it useful for crypto?

### Direct content: essentially none
Bitcoin is mentioned **once** in the entire 165 pages — as an illicit payment rail
("pay a human in bitcoin to synthesize it," re: bioweapons). There is no crypto thesis here.

### Indirect relevance: significant, via correlation

This is the real link, and it's not in the essay:

- BTC/Nasdaq-100 30-day rolling correlation reached ~**0.80** in early 2026, highest in
  ~4 years; broader BTC-equity correlation spiked to a record **0.96** by April 2026,
  against a pre-2025 average nearer 0.4
- Feb 2026: crypto sold off alongside Nasdaq futures on AI-disruption fears
- Late 2025: Bitcoin tracked the IGV software ETF "almost tick-for-tick" when AI began
  threatening SaaS business models
- Driver: institutional flows via spot ETFs have made BTC sensitive to the same macro
  forces as equities

**Implication:** the AI capex cycle is now a primary macro driver of crypto. Bitcoin is
trading as high-beta liquidity/tech exposure, not as an uncorrelated asset.

Concretely, these are now crypto-relevant events:
- Nvidia earnings and guidance
- Hyperscaler capex guidance (Microsoft, Alphabet, Amazon, Meta)
- Anything that challenges the AI capex narrative

If the AI trade breaks, crypto very likely breaks with it. That is a **risk-management**
insight, not an entry signal.

### Second-order: energy competition (inference, not in the essay)
The essay's core claim is that AI datacentres will consume an enormous and growing share
of electricity — plausibly >20% of US production by 2030 for a single cluster. Bitcoin
mining competes for exactly the same resource: cheap power, near generation, with
flexible interconnects. AI buyers can pay far more per kWh than miners.

Direction: structurally **negative for pure-play mining economics**, positive for miners
who convert sites to AI/HPC hosting. This is a real, mechanical link between the thesis
and a crypto sub-sector — and it's one the essay never mentions.

### Caveat on correlation
Sources noting the 0.96 figure also stress it is "historically new, not structurally
permanent." Correlation regimes break. Don't build anything that assumes it holds.

---

## 5. Relevance to this project (binance-claude-trader)

**Timeframe mismatch is total.** This thesis operates on a 2–10 year horizon. The bot
trades 15-minute bars. There is no path from "AGI by 2027" to a decision on this candle.

Where it *could* legitimately feed in — all via `catalyst.py`, as background context,
never as a trade trigger:

1. **Regime awareness.** With BTC-equity correlation this high, a US tech selloff is a
   crypto risk event. Worth having in the news brief.
2. **Scheduled catalysts.** Nvidia earnings and hyperscaler capex guidance are now
   crypto-relevant dates. The news layer should flag them the way it flags CPI.
3. **Miner-linked tokens.** If ever trading mining-exposed assets, the AI-power
   competition is a structural headwind.

**What would be wrong:** feeding "AGI is coming" into the decision prompt as a bullish
bias. That's an unfalsifiable, multi-year view contaminating a 15-minute decision — the
exact failure the risk gate and the lessons file exist to prevent.

---

## 6. Bottom line

| Question | Answer |
|---|---|
| Is the analysis serious? | Yes. Quantitative, sourced, states its own error bars, engages counterarguments. |
| Was he right? | On capital flows, yes and then some. On AGI timing, unresolved and the strong form looks late. |
| Useful for trading? | As a **thematic allocation framework** over years. Not as a trading method. |
| Useful for crypto? | Only indirectly — but the correlation channel is real and currently strong. Nothing crypto-specific in the document. |
| Useful for the 15m bot? | Only as regime/catalyst context. Never as directional bias. |
| Biggest caveat | The author was leveraged long the trade he was writing about, and launched a fund on this thesis. Right ≠ disinterested. |

**One line:** read it for how he reasons about constraints and capital, not for what to buy.
The method survives even if the AGI conclusion doesn't.

---

## Sources

- <https://situational-awareness.ai/> (all 9 pages)
- Nvidia FY2026 results — <https://nvidianews.nvidia.com/news/nvidia-announces-financial-results-for-fourth-quarter-and-fiscal-2026>
- Big Tech capex 2026 — <https://www.tomshardware.com/tech-industry/big-tech/big-techs-ai-spending-plans-reach-725-billion>, <https://www.cnbc.com/2026/02/06/google-microsoft-meta-amazon-ai-cash.html>
- BTC-equity correlation — <https://intellectia.ai/blog/bitcoin-stock-correlation-record-high-2026>, <https://www.coindesk.com/markets/2026/02/17/crypto-slides-as-tech-stocks-and-gold-retreat-bitcoin-nasdaq-correlation-turns-positive>
- Author background — <https://en.wikipedia.org/wiki/Leopold_Aschenbrenner>
