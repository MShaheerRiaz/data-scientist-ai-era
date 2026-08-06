# The probability mathematics

Everything here is computed exactly by `lotterylab/combinatorics.py`. Nothing is estimated by simulation, because for these structures it doesn't need to be.

---

## 1. Counting tickets

A game picking `k` numbers from `n` has `C(n,k)` distinct tickets. With a bonus drawn from a *separate* pool, multiply by that pool's combinations.

| Game | Structure | Tickets |
|---|---|---|
| Canada 6/49 | 6 of 49 | 13,983,816 |
| UK Lotto | 6 of 59 | 45,057,474 |
| Lotto Max | 7 of 50 | 99,884,400 |
| EuroMillions | 5 of 50 + 2 of 12 | 139,838,160 |
| Mega Millions | 5 of 70 + 1 of 24 | 290,472,336 |
| Powerball | 5 of 69 + 1 of 26 | 292,201,338 |

Powerball's 292 million is worth making concrete. At one ticket per second it would take **9.3 years** to buy them all.

---

## 2. Prize-tier probabilities

The probability of matching exactly `m` of the main numbers is hypergeometric:

```
P(m) = C(k, m) · C(n−k, k−m) / C(n, k)
```

Choose which of your numbers hit, then fill the rest of your ticket from the balls that weren't drawn.

### The bonus ball, and a trap

There are three distinct bonus structures, and conflating them gives wrong odds.

**Separate pool** (Powerball, EuroMillions, Mega Millions). The bonus is independent, so probabilities multiply.

**Drawn from the remaining balls** (UK Lotto, Canada 6/49). The bonus comes from the `n−k` balls the main draw left behind, so hitting it is *conditional on how many main numbers you missed*:

```
P(hit bonus | m main matches) = (k − m) / (n − k)
```

**The trap.** In UK Lotto and Canada 6/49, the lower tiers pay on main matches **regardless of the bonus**. Insisting the bonus was missed gives 1 in 2,265 for UK "Match 4"; the published figure is **1 in 2,180**. The library marks these tiers `bonus_any` and sums over the bonus outcome. Getting this wrong also breaks the overall odds — Canada 6/49's published "1 in 6.6" only reproduces once the Match-2 free play is included as a tier.

### Verified against the operators

Every preset reproduces its operator's published figures:

```
powerball      jackpot 1 in 292,201,338   any prize 1 in 24.87
megamillions   jackpot 1 in 290,472,336   any prize 1 in 23.07
euromillions   jackpot 1 in 139,838,160   any prize 1 in 12.97
uk_lotto       jackpot 1 in  45,057,474   any prize 1 in  9.23
canada_649     jackpot 1 in  13,983,816   any prize 1 in  6.62
lotto_max      jackpot 1 in  99,884,400   any prize 1 in 20.94
```

Two figures need a note. Mega Millions reflects the **April 2025 revamp** ($5 ticket, Mega Ball pool cut to 24) — pre-2025 tables show 1 in 302,575,350. And Lotto Max's operator quotes ~1 in 7 for "any prize" because a **$5 ticket buys three selections**; per selection it is 1 in 20.94, and `1 − (1−p)³ = 1 in 7.3` reconciles them.

---

## 3. The scale problem

Odds this long defeat intuition, so anchor them:

| Event | Probability | vs a Powerball ticket |
|---|---|---|
| Powerball jackpot | 1 in 292,201,338 | — |
| Struck by lightning this year (US) | ~1 in 1,200,000 | **244× more likely** |
| Dealt a royal flush, first five cards | 1 in 649,740 | 450× more likely |
| Killed by a vending machine this year | ~1 in 112,000,000 | 2.6× more likely |

Buying one ticket twice a week, the expected wait for a Powerball jackpot exceeds **2.8 million years**. Over a 50-year playing lifetime the chance of hitting it once is about **1 in 56,000**.

Note the shape of the failure: buying 100 tickets makes you 100× more likely to win, and still leaves you at 1 in 2.9 million per draw. Multiplying a number this small by 100 does not produce a meaningful number.

---

## 4. Independence, and what "due" would require

Draws are independent. Ball 17 has no memory of the last draw, the last year, or the last century. For "due numbers" to work, some physical mechanism would have to make a ball's future appearance depend on its past — and that mechanism would have to be strong enough to survive random ball-set selection, weight screening, and test draws.

Three tests in `lotterylab/fairness.py` probe exactly this:

- **Consecutive-draw overlap** — how many numbers carry over between draws. Under independence this is hypergeometric with mean `k²/n` (0.73 for a 6/49 game).
- **Serial persistence** — a pooled 2×2 table of "appeared last draw" against "appears this draw". If hot numbers existed in any usable sense, this fires.
- **Gap distribution** — waiting times between a ball's appearances must be geometric with `p = k/n`. Memoryless means memoryless.

On fair data none of them fire. On synthetic data with injected serial dependence, all three fire at 100%.

---

## 5. The distributions people misread

### Draw sums

For 6/49, sums run 21 to 279 with a sharp mode at **150**. Because sums concentrate, a "balanced" sum near 150 feels meaningful — it isn't. Most combinations have a sum near 150 precisely because that's where the mass is; conditioning on it tells you nothing about the draw and, worse, moves you *toward* the region other players occupy.

The library computes this distribution exactly by dynamic programming (verified against brute force) and tests observed sums against it with a binned chi-square.

> **Why not a KS test?** Draw sums are heavily tied — 2,000 draws of a 6/49 game land on only ~175 distinct sums, with the modal sum occurring 28 times. KS assumes a continuous distribution; scoring every tied observation against the inclusive CDF inflates the statistic by each atom's mass. In calibration this drove the false-positive rate to **20.7%**. The binned chi-square runs at 4.2%.

### Repeated combinations

Bulgaria's 6/49 drew the same six numbers four days apart in September 2009, triggering a ministerial investigation that found nothing. It shouldn't have surprised anyone: with `D` draws there are `D(D−1)/2` chances to collide, so repeats are governed by the birthday problem. The library's `duplicate_combination_test` compares the observed count against a Poisson expectation of `D(D−1)/2 / C(n,k)`.

Repeats are only suspicious if there are *more* than chance predicts.

---

## 6. What your history can actually detect

This is the calculation that dissolves most "I found a pattern" claims, and the most useful function in the library.

Testing every ball in the pool means correcting for multiple comparisons. Under Bonferroni-adjusted α and 80% power, for a 6/49 game:

| History | Smallest detectable bias |
|---|---|
| 500 draws | 51.3% |
| 2,000 draws | 25.2% |
| 5,000 draws | 15.8% |
| 10,000 draws | 11.2% |

Inverted — draws needed to detect a given bias:

| Bias | Draws required | Years at 2 draws/week |
|---|---|---|
| 5% | 49,234 | **473** |
| 10% | 12,410 | **119** |
| 20% | 3,151 | 30 |
| 50% | 525 | 5 |
| 100% | 138 | 1 |

Two conclusions follow, and they cut in opposite directions from the ones people want:

1. **A clean audit is weak evidence of fairness.** It says the bias is smaller than your data can resolve, not that it's zero.
2. **A bias you *could* detect would have to be enormous** — far larger than any documented physical ball bias — and would have had to survive the whole control regime described in [document 01](01-how-numbers-are-generated.md).

Either way, there is nothing to bet on.

---

## 7. Multiple testing

Run 49 per-ball tests at α = 0.05 on a perfectly fair lottery and you should **expect about 2.5 "significant" balls**. This is the engine behind every hot-number website: run enough tests, publish the ones that fire.

Every multi-test routine here reports **Benjamini–Hochberg adjusted q-values**, and `audit()` corrects across the battery as a whole. Calibration on 400 fair histories:

```
ball frequency (chi-square)              5.0%
gap distribution (chi-square)            5.2%
serial persistence (2x2)                 4.8%
runs test (sum vs median)                4.8%
odd/even split (chi-square)              4.5%
draw-sum distribution (chi-square)       4.2%
consecutive-draw overlap                 3.2%
duplicate combinations (Poisson)         0.8%   (discrete, inherently conservative)

>=1 ball flagged after FDR:              4.8%   (target ~5%)
```

And on known-rigged data, detection rates:

| Injected flaw | Ball-level detection | Battery detection |
|---|---|---|
| One ball +20% | 48% | 8% |
| One ball +50% | 100% | 93% |
| One ball ×2 | 100% | 100% |
| Low half +15% | 52% | 100% |
| 20% serial dependence | 80% | 100% |

The +20% row is the honest one: it sits right at the power limit for 2,000 draws, exactly as the power analysis predicts.

---

*Next: [03 — Game theory and player behaviour](03-game-theory.md)*
