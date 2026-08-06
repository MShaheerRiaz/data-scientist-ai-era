# Fallacies, and the proof they fail

Every system in this document is sold commercially. Every one is tested in `lotterylab/backtest.py`, and every one fails.

---

## How to test a lottery strategy properly

Naive backtesting is worthless here. Outcomes are dominated by whether you happened to hit something — one lucky match-5 swamps thousands of draws of signal. Rank strategies by realised profit and the ranking reshuffles every time you change the seed.

Two things fix this:

**1. Measure mean matches, not money.** The average number of main-number matches per ticket has a tiny variance compared with payout, and it is what any genuine edge would move first. If a strategy cannot shift mean matches, it has no edge, full stop.

**2. Compare against a permutation null.** Shuffle the *order* of the historical draws. This destroys any real time-structure while preserving the exact same multiset of draws. A strategy that genuinely exploits history should perform **worse** on scrambled chronology. One that performs identically was never using chronology at all.

```bash
python -m lotterylab backtest canada_649 --permutation
```

---

## 1. Hot numbers

*"Number 23 has come up eight times in the last twenty draws. It's running hot."*

Balls have no memory and no momentum. The observed variation in frequencies is exactly what independence predicts — that is the whole content of `ball_frequency_test`, which on fair data fires at 5%, precisely its nominal rate.

**Test result:** the `hot` strategy lands on the theoretical mean-match rate and sits comfortably inside its scrambled-chronology null. Scrambling the order changes nothing, because the strategy was never extracting anything.

There is one twist worth knowing: because recently drawn numbers are *temporarily under-bet by other players*, a hot-numbers ticket may actually be marginally better than average — **not** because it is likelier to win, but because you would split a win fewer ways. Right conclusion, entirely wrong reason.

## 2. Cold numbers / due numbers

*"Ball 17 hasn't appeared in 40 draws. It's due."*

The purest form of the gambler's fallacy, and the most widely sold system in the world. A memoryless process has no notion of "due". The gap between appearances is geometric, and the geometric distribution's defining property is that it forgets — the expected wait from *now* is the same whether the ball appeared last draw or forty draws ago.

The famous case: ball 17 in UK Lotto once went **72 draws** without appearing. The naive probability of that specific gap is 0.000082 — but across 7,440 observed gaps, the chance that *some* gap reaches 72 is about **0.46**, and simulation puts the mean largest gap at exactly 72.

**Test result:** the `due` strategy is indistinguishable from random, on real chronology and scrambled alike.

## 3. Overdue combinations

*"This combination has never come up in the history of the game."*

Almost no combination has. A 6/49 game drawing twice a week for 50 years produces 5,200 draws against 13,983,816 combinations — **99.96% of all combinations have never appeared.** "Never drawn before" describes essentially every ticket you could buy.

## 4. Sum ranges and "balanced" filters

*"Winning combinations usually sum to between 120 and 180, so filter to that range."*

True and useless. Sums concentrate near 150 because that is where the combinatorial mass sits — most *combinations* have a sum near 150, so most *winning* combinations do too. Conditioning on it selects nothing.

It is also actively harmful. Sum filters, odd/even balance, and "spread across the range" are precisely the heuristics other players use. In a field experiment the evenly-spread pattern was the **only** distinctive pattern players did not reject. Filtering toward "balanced-looking" combinations moves you into the crowd and **raises** your expected number of co-winners.

## 5. Wheeling as an odds improver

Wheels are real (see [document 04](04-what-actually-works.md)) but routinely mis-sold. **A wheel does not improve your jackpot odds.** Buying `n` distinct tickets multiplies your jackpot chance by exactly `n`, however chosen. What a wheel buys is a guaranteed *floor* on lower tiers — variance traded for certainty, at a price.

## 6. Pattern and delta systems

*"Track the differences between consecutive numbers."*

A bijective relabelling of the combination space. Any statistic computed in delta-space carries exactly the information the original numbers carried — which is none. Rearranging a random variable does not create signal.

## 7. Astrology, numerology, dream books, lucky-number apps

No mechanism, no evidence. Worth one practical note: these are **popularity concentrators**. Shared "lucky numbers", dream-book mappings, and app-generated picks push many players onto the same combinations, so a win is split more ways. They are worse than random for reasons that have nothing to do with luck.

## 8. "Systems" sold with testimonials

Selection effects. With millions of players, some will win having used any given method. The seller shows you the winners. The test is whether the method beats a properly calibrated null across all draws — which is what this library does, and which no such system has ever passed.

If a system genuinely worked, selling it would be irrational: publishing it would destroy the edge (see the documented decay of unpopular-number sets once they became known).

---

## The empirical result — and a trap worth studying

Running every strategy over the same **fair synthetic** history (1,500 draws, 4 tickets each, 10 repeats):

```
  strategy        mean matches       sd      ROI   z vs theory
  hot                  0.75113  0.00775   0.2090         6.70
  unpopular            0.73941  0.01294   0.1994         1.15
  due                  0.73843  0.00708   0.1986         1.67
  cold                 0.73532  0.00628   0.1979         0.32
  random               0.72893  0.00670   0.1950        -2.72

  theoretical mean matches per ticket: 0.73469   (= k²/n = 36/49)
```

**`hot` scores z = +6.70 against the theoretical rate — on data generated to be perfectly fair.** If you stopped here you would conclude hot numbers work. This is very likely how most published "our system beats random" results are produced.

### Why the apparent edge is an artifact

Comparing a history-dependent strategy against the *theoretical* rate is the wrong null.

Within any **fixed finite history**, the empirically hot balls appear more often than average *by definition* — that is what made them hot. Walk-forward testing then correlates "hot as of draw *t*" with "appears at draw *t*", because both are driven by the same underlying quantity: the ball's total realised count across that particular history. The strategy is not predicting anything; it is picking up its own selection criterion.

### The correct null

Permutation testing fixes it. Shuffling the draw order **preserves the multiset of draws** — so exactly the same balls remain hot overall — while destroying any genuine time-structure. Same data, same finite-sample quirks, no chronology.

```
  strategy     observed  null mean  null sd      z      p
  hot           0.75875    0.74806  0.01084   0.99  0.129
  cold          0.73643    0.72846  0.00814   0.98  0.194
  due           0.74036    0.73413  0.01584   0.39  0.452
  random        0.71893    0.73633  0.01080  -1.61  0.935
```

Note the null mean for `hot`: **0.74806**, already far above the theoretical 0.73469. The entire apparent advantage is present in the scrambled data. Against the correct null, `hot` gives **z = 0.99, p = 0.129** — nothing at all.

Every strategy sits inside its own permutation null. None extracts information from history, because there is none to extract.

**The general lesson:** if a lottery system is validated against a theoretical baseline rather than against a resampled null built from the same data, the validation is worthless — and it will reliably produce a positive result on data known to be random.

---

## The one real cognitive trap

The strongest argument against all of this is not statistical, it is psychological: **near-misses feel like progress.** Matching 3 of 6 feels like being halfway to 6 of 6. It isn't. The conditional probability of the remaining three given three matches is not meaningfully different from the unconditional probability of any three specific numbers.

Lottery prize structures are designed around this. Frequent small prizes exist to produce the sensation of almost-winning. That is the product being sold.

---

*Next: [06 — Digit games: 2D, 3D and friends](06-digit-games-2d-3d.md)*
