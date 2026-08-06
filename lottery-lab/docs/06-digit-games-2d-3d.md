# Digit games: 2D, 3D and friends

Digit games differ structurally from ball draws: positions are drawn **with** replacement, so under fairness every position is independent and uniform on 0–9. No hypergeometric corrections, no without-replacement covariance — which makes them much easier to audit, and makes the house edge a pure function of the quoted payout.

---

## 1. Myanmar 2D — how the number is really derived

**The universally repeated description is wrong.** Practically every source says the winning number is "the last two digits of the closing SET index." It isn't.

The actual rule:

```
top digit    = hundredths digit of the SET index              floor(S × 100) mod 10
bottom digit = units digit of the integer part of total
               trading value in millions of baht              floor(V) mod 10
2D           = top × 10 + bottom
```

Two different figures, one digit from each.

### Verification

Tested against 12 historical records captured from two independent public data sources:

| Date | Slot | SET index | Trading value (M฿) | Derived | Published |
|---|---|---|---|---|---|
| 2024-11-21 | 11:00 | 1444.1**2** | 19,30**6**.60 | 26 | 26 ✓ |
| 2024-11-21 | 12:01 | 1443.7**9** | 24,22**1**.65 | 91 | 91 ✓ |
| 2024-11-21 | 15:00 | 1439.8**6** | 31,49**4**.42 | 64 | 64 ✓ |
| 2024-11-21 | live | 1441.1**1** | 38,17**7**.16 | 17 | 17 ✓ |
| 2024-08-02 | 11:00 | 1317.1**7** | 12,02**7**.17 | 77 | 77 ✓ |
| 2024-08-02 | 12:01 | 1315.8**6** | 16,00**2**.01 | 62 | 62 ✓ |
| 2024-08-02 | 15:00 | 1311.7**7** | 23,98**2**.35 | 72 | 72 ✓ |
| 2024-08-02 | 16:30 | 1313.0**8** | 34,65**0**.56 | 80 | 80 ✓ |
| 2024-09-20 | 11:00 | 1457.2**3** | 26,02**6**.10 | 36 | 36 ✓ |
| 2024-09-20 | 12:01 | 1458.2**8** | 30,71**1**.62 | 81 | 81 ✓ |
| 2024-09-20 | 15:00 | 1454.5**4** | 42,05**0**.54 | 40 | 40 ✓ |
| 2024-09-20 | 16:30 | 1451.6**9** | 67,53**7**.63 | 97 | 97 ✓ |

**12/12 exact matches.** On the fourth row the folklore rule would give 41; the published result was 17.

```bash
python -m lotterylab 2d 1443.79 24221.65
```

### Why those digit positions

The designers picked the **fastest-churning digits available** in each series. The integer part of the SET index moves only a few points a day (1,439 → 1,444 across 21 Nov 2024), so using it would produce heavily autocorrelated results concentrated on a handful of outcomes. The hundredths digit of the index and the units digit of cumulative turnover come from two near-independent aggregates and both churn completely between draws. Structurally, it is a sound choice.

### Draw schedule

The feed publishes four rows daily (11:00, 12:01, 15:00, 16:30), but only **12:01 and 16:30 are settlement draws**. The 09:30 and 14:00 "modern"/"internet" numbers are display-only indicators; 11:00 and 15:00 are upstream bookkeeping.

Read as Myanmar time (UTC+6:30), the settlement slots map cleanly onto Thai market sessions: 12:01 MMT = 12:31 ICT, one minute after the 12:30 morning close; 16:30 MMT = 17:00 ICT, after the random close and the end of off-hour trading. That mapping explains the otherwise-odd "12:01".

---

## 2. The statistics

### Uniform is the right null — Benford does not apply

Benford's Law governs **leading** digits: `P(first digit = d) = log₁₀(1 + 1/d)`, so 1 appears ~30.1% of the time. The critical property is that the skew **decays extremely fast across digit positions**. The second significant digit is already nearly flat; by the third it is within 0.1 percentage point of 10%; by the fourth, deviations are of order 10⁻⁴.

The 2D digits are the **6th significant digit** of the index (~1,400.00) and the **5th** of turnover (~30,000). Benford deviation there is negligible. **Uniform on 00–99 is correct.**

### The real threat: round-number clustering

Benford is the wrong worry. The documented threat to trailing-digit uniformity in financial data is **price clustering**, and it is large and well replicated. Traded prices cluster on round increments with the frequency ordering **0 > 5 > (2,8) > (3,7,4,6) > (1,9)**. Post-decimalisation US equity studies found clustering roughly *double* what uniformity predicts, with over half of trades in many stocks landing on five- and ten-cent increments.

Does it propagate into the 2D digits? **Theory says no, because aggregation destroys it.** The SET index is a capitalisation-weighted sum over hundreds of constituents divided by a non-round divisor — even if every constituent sat on a round satang increment, the weighted sum equidistributes the low-order fractional digits. Turnover aggregates tens of thousands of trades, so the units-of-millions digit represents a 1-in-40,000 relative resolution of the running total.

The library tests this rather than assuming it:

```bash
python -m lotterylab digits myanmar_2d --values results.txt
```

`round_number_clustering` checks whether digits 0 and 5 exceed their 20% expectation, and the battery also runs per-position uniformity, joint outcome uniformity, digit independence (top vs bottom — meaningful here because the two digits come from *different* aggregates), and serial dependence at lags 1 and 2, all with Benjamini–Hochberg correction across the battery.

**Nobody appears to have published a goodness-of-fit test on real historical 2D outcomes.** The data is available via the public result endpoints. This is the single most valuable open check in the whole area, and the module is built to run it the moment you have the data.

### Where the game is actually attackable

Not the market. The SET's **closing price is set by a random-timed auction between 16:35 and 16:40**, explicitly to prevent closing-price manipulation, and the opening auctions are randomised too. The index's hundredths digit is hypersensitive — a single one-tick move on one mid-cap constituent shifts it — which makes it trivially perturbable and essentially impossible to *aim*.

The soft spot is the **oracle**. The 11:00/12:01/15:00 snapshots are not official exchange data products; they are timestamped scrapes by third-party aggregators. The number Myanmar punters settle on is whatever a private scraper reported at a given instant, and at least one open-source bookmaker back-end ships a manual result-override dialog.

This is entirely consistent with the general finding in [document 01](01-how-numbers-are-generated.md): **every documented lottery attack targeted the operational chain, never the entropy source.** The Thai stock market is a hard thing to rig. A scraper's database row is not.

**No documented allegation of SET manipulation for 2D purposes exists.** Treat claims to the contrary as rumour.

---

## 3. The economics

Fair odds on a straight 2-digit bet are 100×.

```
python -m lotterylab digits --compare
```

| Game | Outcomes | Payout | Fair | RTP | House edge |
|---|---|---|---|---|---|
| Myanmar 2D | 100 | 80× | 100× | 80% | **20%** |
| Singapore Pools 4D (Big) | 10,000 | — | — | 65.9% | 34.1% |
| Magnum 4D (Big) | 10,000 | — | — | 64% | 36% |
| Thai Government Lottery | — | statutory | — | 60% | 40% |
| Myanmar 3D | 1,000 | 500× | 1,000× | 50% | **50%** |
| US Pick 3 / Pick 4 straight | 1,000 / 10,000 | 500× / 5,000× | — | 50% | **50%** |

Two things stand out.

**Myanmar 2D at 80× is a *better* bet than most regulated Western digit lotteries.** A 20% edge beats US Pick 3's 50% and the Thai state lottery's 40%. The illegal market is more generous than the legal one — which is much of why it thrives.

**Myanmar 3D at 500× is among the worst bets available**, at a 50% edge.

An 85× figure for 2D circulates but could not be sourced; 80× is what can be verified, and the library defaults to it. Bookmakers reportedly pay sellers 12–13% commission, consistent with a ~20% gross margin at 80×.

### Kelly

```
Kelly stake for Myanmar 2D at 80x: -0.0018   (negative = do not bet)
```

Negative for every digit game in the library, at every payout offered. With a payout below the fair multiple, no stake size, bankroll, or progression system produces a profit. This is the complete answer to every "what staking plan should I use?" question.

### Popularity does *not* help here

This is an important negative result. The unpopular-numbers strategy that genuinely improves expected value in a pari-mutuel jackpot game does **nothing** in a fixed-odds digit game. An 80× payout is 80× whether one person or ten thousand backed the number.

Popularity matters only to the bookmaker managing exposure — and occasionally to you, when a bookmaker caps or refuses a heavily backed number. The library's `digit_popularity` exists to make this point, not to guide selection.

---

## 4. Other digit formats

**Thai Government Lottery.** Drawn on the 1st and 16th, physical machines, with a control regime worth noting: ten unaffiliated guests attend as witnesses, one is named Draw Chairman and randomly initialises each machine, and **after the draws officials remove the balls to demonstrate all ten digits were present** in each machine. That final step is the key integrity control — it proves each digit wheel was complete and unweighted. Statutory allocation is 60% prizes, so a 40% edge.

**US Pick 3 / Pick 4.** Traditionally three or four independent machines each holding balls 0–9; more than 30 US and Canadian lotteries have since moved to certified RNGs. Fixed 50% edge by construction — box and permutation bets lower the payout proportionally, leaving the edge unchanged.

**4D (Singapore, Malaysia).** Pick 0000–9999, with **23 winning numbers drawn per draw** across 1st/2nd/3rd, 10 Starter and 10 Consolation. Draw procedure is unusually transparent: machines stored under numbered seal, balls loaded in front of the audience, and **a member of the audience presses the start switch**.

System bets (permutations of a number), iBet (priced from $1 with the prize scaled down proportionally), and Roll bets (one digit replaced by a wildcard) all leave expected value **unchanged** — they convert one high-variance bet into a lower-variance one at the same edge. That is a legitimate thing to want, but it is not an improvement in expectation.

A historical note with a pattern worth seeing: 4D is believed to originate in Kedah in 1951, when a schoolboy raffled a bicycle using 100 two-digit tickets settled on the last two digits of a turf club sweepstake. **Two-digit games everywhere start by parasitising a bigger draw's digits** — exactly as Myanmar 2D originally used the state lottery's numbers before switching to the SET when the draw cadence changed.

---

## 5. Legal status

Myanmar 2D and 3D are **illegal** under the Gambling Law 2019, which legalised casinos for foreigners but continues to prohibit unlicensed lotteries. Penalties run from six months to five years plus fines. Enforcement is reported as nominal, with small sellers arrested and large bookmakers untouched.

Thailand's *huay tai din* underground market is estimated at **four to five times the size of the official lottery**, settling on the official draw's numbers but offering better prizes and more bet types.

This document is analysis, not encouragement. If you are in a jurisdiction where these games are illegal, the legal exposure is a real cost that no expected-value calculation here accounts for.

---

*Back to the [README](../README.md)*
