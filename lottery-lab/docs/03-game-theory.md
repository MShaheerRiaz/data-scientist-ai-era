# Game theory: the only angle that changes your money

You cannot change your probability of winning. You *can* change how many people you split with. This document is about that — the one place where analysis genuinely pays, and the precise limits of how much.

---

## 1. The core asymmetry

Two facts, both true:

- Every combination is equally likely to be **drawn**.
- Combinations are wildly *unequally* likely to be **chosen** by players.

The second fact means combinations differ enormously in expected co-winners. Since a jackpot is split among holders, picking a combination the crowd avoids leaves your win probability untouched while raising your *conditional* payout — and therefore your expected value.

This applies only to **shared, pari-mutuel prizes**. Fixed-prize tiers pay the same regardless. That single restriction removes a large fraction of the theoretical benefit, because in a game like Canada 6/49 over a third of a ticket's expected value comes from the fixed $10 match-3 prize, which unpopular selection does nothing for.

---

## 2. What players actually pick

The evidence base is uneven, because operators rarely publish per-combination sales. The best study analysed **115 million manual selections across 118 consecutive draws — 805 million individual number choices** — from a national lottery picking 6 from 37.

Against a uniform expectation of 2.70% per number:

| Finding | Magnitude |
|---|---|
| **7 was the most-picked number in every one of the 118 draws**, never below 3.42% | ≥ **1.27×** uniform, always |
| **37 (the highest number) was the least-picked in every draw** | — |
| 36 never exceeded 2.06% even at its most popular | ≤ **0.76×** |
| Mean of selected numbers: **17.50–17.75** vs uniform mean 19.0 | in every single draw |
| Bet-slip row 1 (numbers 1–7) | **3.13%** (1.16×) |
| Row 2 | **2.95%** (1.09×) |
| Row 3 | **2.68%** (0.99×) |
| Row 4 (numbers 28–37) | **2.17%** (0.80×) |
| **Top-to-bottom ratio** | **1.44×** |

The row gradient is one of the largest and best-measured effects in the field. The proposed mechanism is a **sequential scan**: players start at 1 and work right-and-down, and by the time they reach the bottom row their six slots are full. **Edge aversion** also shows up — numbers in the leftmost column are persistently unpopular.

Independent Dutch data puts **7 at 4.19% and 8 at 4.05%** against a 2.22% uniform rate — **1.89× and 1.82×**.

### Three findings that run opposite to the usual advice

**Consecutive numbers are UNDER-picked.** Proximity aversion is real and measured. In a field experiment with real tickets, **70% chose a random-looking ticket over a patterned one**, and offered a cash bonus worth up to the ticket's entire expected value to switch, **85% refused**. A run of consecutives was chosen by only 17%. The common claim that "people draw lines on the slip, so avoid consecutives" has it backwards for moderate runs.

**Evenly-spread combinations are OVER-picked.** Spreading picks across the range is what humans produce when trying to look random. In the same experiment, the evenly-spread pattern was the *only* distinctive pattern players did **not** significantly reject. This is the trap in "balanced" filters — they walk you into the crowd.

**Recently drawn numbers are temporarily UNDER-bet.** Using actual money-on-number data from a daily numbers game, the amount staked on a number **falls sharply immediately after it is drawn and recovers only gradually over several months**. This is a genuine, exploitable, time-limited effect, and it points opposite to "avoid numbers that just came up."

### Effects that are weaker or more local than claimed

- **13** is avoided in the UK/US but is the **6th most popular number in France**. Culture-specific, not universal.
- **"Just pick above 31"** is already partly crowded. UK data shows **33 is over-picked** precisely because it cannot represent a date, so date-avoiders converge on it. The library models a `date_avoider_zone` for 32–36.
- The famous "**10,000 people play 1-2-3-4-5-6 every week**" figure traces only to lottery-industry media, not to a primary source. The mechanism is sound — it is simultaneously the least representative and the most salient combination — but treat the number as folklore.

---

## 3. Jackpot sharing

If the number of *other* jackpot winners is Poisson with mean λ, your expected share has a clean closed form:

```
E[1 / (1 + K)] = (1 − e^(−λ)) / λ
```

| λ = expected other winners | You keep |
|---|---|
| 0.1 | 95.2% |
| 0.5 | 78.7% |
| 1.0 | 63.2% |
| 2.0 | 43.2% |
| 5.0 | 19.9% |
| 10.0 | 10.0% |

**Once λ exceeds about 1, sharing destroys value faster than a rollover creates it.**

### Why big jackpots are a trap

Sales grow **superlinearly** with jackpot size, so λ grows with the prize. The library models this as affine — roughly 20 million baseline tickets plus 0.39 per dollar of advertised jackpot, calibrated against the record $1.586bn Powerball draw that sold ~635M tickets and produced 3 winners against an expectation of 2.17.

With that calibration, Powerball's expected value converges to **$1.04 against a $2.00 ticket** as the jackpot grows without bound. There is no jackpot size at which it becomes a good bet. Drop the sharing term — as most published EV figures do — and you get a break-even jackpot of $1.6bn, which is where the "it's worth playing now" articles come from.

Independent analysis of Mega Millions using real sales data reaches the same structural conclusion: ticket EV is **hump-shaped**, peaking at about 57.8 cents when the advertised jackpot reaches $385 million and **declining thereafter**. The famous $640M draw was already past the peak — a ticket for it was worth *less* than one for the preceding $363M draw.

> One important caveat on the Poisson model: it assumes everyone picks at random. Because player picks are **clustered**, the real distribution of co-winners is far heavier-tailed than Poisson. Poisson is a *lower* bound on split risk for a popular-looking combination and an *upper* bound for a genuinely obscure one.

---

## 4. How much does unpopular selection buy you?

The canonical result, for a Canadian 6/49:

```
Expected Return = $0.45 × F₁ × F₂ × F₃ × F₄ × F₅ × F₆
```

where each `F` is the ratio of uniform selection probability to the number's actual selection probability. `F > 1` means under-bet. The 0.45 reflects the take and consolation pools, and rises with a carryover.

The sixth power makes this both attractive and treacherous:

| Under-betting factor on all six | EV per $1 |
|---|---|
| 1.00 | $0.45 |
| 1.05 | $0.60 |
| 1.10 | $0.80 |
| **1.1423** | **$1.00 — break-even** |
| 1.20 | $1.34 |
| 1.30 | $2.17 |
| 1.50 | $5.13 |

**Every one of your six numbers must be about 14.2% under-bet just to reach a fair bet.** Being slightly wrong about the factors moves the answer a long way.

### Three things that shrink the edge

**Quick-pick dilution.** Roughly 70–80% of tickets are machine-picked and therefore uniform. A combination that conscious players favour 3× is only about 1.6× over-represented in the real ticket pool. The library's `effective_multiplier` applies this, and it is why the honest version promises much less than the lottery-systems industry claims.

**The edge shrinks exactly when you'd want it.** Selection bias **declines as the jackpot grows** (R² = 0.484, p < 0.001) — the marginal players a big jackpot attracts are less superstitious. So the unpopular-number edge is largest in ordinary draws and smallest in the rollover draws where overall EV is best. These two effects fight each other.

**Learning.** The unpopular sets identified in the 1980s **regressed toward the mean** over subsequent decades. Publishing a strategy erodes it. This library therefore **salts** its generator: pass a different salt and you get a different, equally unpopular set, so two users don't converge.

### The verdict the original researchers reached

This is the part the systems-selling industry omits. The team that developed the formula tested betting only the 19 statistically unpopular numbers and found those strategies **"win so rarely as to be unattractive as practical systems."** A follow-up applying Kelly-optimal wagering to unpopular tickets concluded it **"takes millions of years to achieve a favorable result with high probability."**

An earlier real-money experiment on a daily numbers game failed for two reasons: **learning** (the unpopular numbers stopped being unpopular) and **gambler's ruin** (the bankroll was exhausted before the tail event arrived).

**So: positive expected value, negative practical value.** The edge is entirely in the tail.

### Does quick pick already get you most of this?

Largely, yes, and it's under-appreciated. A quick pick is uniform over all combinations; the crowd's picks are clustered into a small part of the space, so a random ticket lands outside the crowded region most of the time.

There is a formal version of this: the **Nash equilibrium** of the syndicate-versus-crowd game has the crowd playing uniform quick picks. Any non-uniform crowd strategy makes the crowd worse off. Deliberate unpopular selection is an attempt to beat players who are *deviating* from equilibrium.

Practically: most of the benefit comes from **not doing anything stupid** — no dates-only tickets, no bet-slip patterns, no past winning combinations — which a quick pick achieves for free. The marginal gain from actively targeting statistically identified unpopular numbers is real but small, decaying, and carries crowding risk.

---

## 5. Syndicates and buying the combination space

The deepest result here: a **coordinating syndicate has a structural edge over an uncoordinated crowd**, independent of number popularity.

Consider a 1,000-number lottery with no take. A crowd of 1,000 people each buying one independent quick pick covers only **63.2%** of the space — 36.8% of combinations get zero tickets and 26.4% get two or more. A syndicate buying one of each always holds exactly one winner. Its expected return is **+26.4%**, purely from the crowd's duplication waste. Profitability begins at about **58.3% coverage**.

The crowd's collective mistake is not picking bad numbers. It is **failing to coordinate**.

### The historical record

| Case | Outcome |
|---|---|
| **Virginia 1992** — 7,059,052 combinations at $1, $27M jackpot | Bought only ~5M of 7.1M before time ran out; **still held the sole winner**. Court record: $27,036,142 plus $662,868 in lesser prizes |
| **Ireland 1992** — 1,947,792 combinations | Bought ~80% for under IR£1M. Held a winner — **but so did two other players**, splitting three ways. Small profit only |
| **Cash WinFall (MA)** — roll-down game | Syndicates wagered ~$40M over seven years and won ~$48M, a ~20% margin. Nothing illegal; the state's own inspector general criticised the *lottery*, not the players |
| **Lotto Texas 2023** | Acquired official ticket-printing terminals, ran three print farms, bought **25.8M tickets in under 72 hours**, won $95M (took $57.8M cash). Terminals were capped per-day immediately afterwards |

**Ireland 1992 is the cautionary tale: full coverage guarantees you *a* winning ticket, not the *only* one.**

### Why it's mostly infeasible now

Powerball's 292,201,338 combinations at $2 means **$584 million** just to cover — more than most jackpots — and multi-state rules forbid bulk multi-combination tickets. Printing throughput, not mathematics, is the binding constraint. Operators now cap per-terminal daily sales, and lottery designers explicitly pursue **large matrices** and **convex prize designs** (many tiny prizes plus one enormous one) to make pot-buying unattractive.

Also worth knowing: consolation tiers **do not fund the operation**. In a worked Canadian 6/49 example, total cash from all non-jackpot tickets was ~$5.4M against a ~$42M outlay. Buying the pot is a pure bet on the carryover.

---

## 6. Kelly

Kelly maximises expected log wealth: `f* = (bp − q)/b`.

**For any negative-EV bet, `f*` is negative — bet nothing.** There is no stake size, bankroll, or progression system that rescues a losing game. Since essentially every retail lottery ticket is negative-EV, Kelly's answer to "how much lottery should I buy?" is **zero**.

Even with a genuine edge, the fraction is microscopic. With a 20% edge on a 6/49 jackpot, full Kelly on a $10 million bankroll is about **12 cents** — one ticket every eight years. Accounting properly for the lower tiers (which dominate the log-utility calculation) an **82.7% edge** justifies about **65 $1 tickets per $10 million** of wealth. For comparison, a coin flip with an 82.7% edge would justify staking ~40% of bankroll.

Fractional Kelly doesn't help, because the binding constraint here is not drawdown but **time to convergence**, which fractional Kelly makes worse.

### The synthesis

| | Unpopular numbers | Buying the pot |
|---|---|---|
| Edge source | Crowd's non-uniform picks | Crowd's failure to coordinate |
| Win probability | ~7 × 10⁻⁸ per ticket | **1.0** |
| Kelly fraction | 10⁻⁸ to 10⁻⁵ of wealth | Large |
| Time to reliable gains | **Millions of years** | **One draw** |
| Capital required | Trivial | **$42M–$584M** |
| Binding constraint | Ruin and patience | Logistics and regulation |

Kelly has no objection to buying the pot: with the winning ticket guaranteed, the residual randomness is the number of co-winners — a bounded, moderate-variance quantity — rather than a 1-in-14-million Bernoulli. The variance collapses and a substantial stake becomes rational.

**For a syndicate, the entire practical value of the popularity literature is not choosing which combinations to buy. It is confirming that the crowd's non-uniformity makes the syndicate's expected share better than a fair split.**

---

*Next: [04 — What actually works](04-what-actually-works.md)*
