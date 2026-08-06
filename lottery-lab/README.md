# lotterylab

A dependency-free Python toolkit for analysing lotteries honestly: probability, game theory, fairness auditing, covering designs, and digit games (2D/3D).

It is built around one uncomfortable fact, and does not try to talk you out of it:

> **For a fair lottery, past draws contain no information about future draws.**

Nothing here predicts winning numbers. What it does instead is attack the three angles where mathematics genuinely bites:

| Angle | What it does | Does it change your odds? | Does it change your money? |
|---|---|---|---|
| **Fairness auditing** | Tests whether a draw is *actually* fair, and tells you how small a bias your data could even detect | No | Only if the game is genuinely broken |
| **Payout game theory** | Picks combinations other players avoid, so a win is split fewer ways | **No** | **Yes** — measurably |
| **Positive-EV windows** | Finds roll-downs and structural quirks where tickets are worth more than they cost | No | **Yes** — this is how every documented legal win happened |

Everything is verified against external ground truth: published operator odds, known-optimal covering numbers, SciPy, and real historical draw records.

---

## Install

No dependencies. Python 3.9+.

```bash
git clone <repo> && cd lottery-lab
python -m lotterylab --help
```

SciPy and pytest are needed only to run the test suite.

---

## Quick start

```bash
# What games are built in, and what are the real odds?
python -m lotterylab games
python -m lotterylab odds powerball

# Is this draw history fair? And could I even tell if it weren't?
python -m lotterylab audit canada_649 --csv draws.csv
python -m lotterylab power canada_649 --draws 3000

# What is a ticket actually worth, once you account for splitting the jackpot?
python -m lotterylab ev powerball --jackpot 1500000000 \
    --cash-ratio 0.52 --tax 0.37 --sales-growth 0.39

# Generate tickets other players avoid
python -m lotterylab generate canada_649 -n 5 --salt "your-name-here"
python -m lotterylab explain canada_649 1 2 3 4 5 6

# Build a wheel with a mathematically verified guarantee
python -m lotterylab wheel canada_649 --pool 12 --coverage 4

# Do hot/cold/due systems work? (spoiler: no, and here's the proof)
python -m lotterylab backtest canada_649 --permutation

# Digit games
python -m lotterylab digits --compare
python -m lotterylab 2d 1443.79 24221.65
```

---

## The five results worth knowing

### 1. Your history almost certainly cannot detect bias

The single most useful calculation in the library. For a 6/49 game:

| History | Smallest detectable bias |
|---|---|
| 500 draws | 51% |
| 2,000 draws | 25% |
| 5,000 draws | 16% |
| 10,000 draws | 11% |

To detect a ball running **5% hot** at 80% power you would need **49,234 draws — 473 years** at two draws a week. Real physical ball bias is far below 5%. So a clean audit is not evidence of fairness; it is evidence that any bias is smaller than your data can resolve. Neither conclusion gives you anything to bet on.

### 2. A big jackpot never makes Powerball worth playing

The naive calculation — jackpot ÷ odds — says Powerball turns positive around a $1.6bn jackpot. That calculation is wrong because it ignores that **sales grow with the jackpot**, so the crowd you split with grows just as fast as the prize.

With sales calibrated to reality (~20M baseline + 0.39 tickets per dollar of jackpot, which reproduces the ~635M tickets sold at the record $1.586bn draw and its 3 winners against an expectation of 2.17):

| Jackpot | Tickets sold | Expected co-winners | You keep | EV | Net |
|---|---|---|---|---|---|
| $300M | 137M | 0.47 | 79.8% | $0.47 | −$1.53 |
| $1.586bn | 639M | 2.19 | 40.6% | $0.92 | −$1.08 |
| $5bn | 1.97bn | 6.74 | 14.8% | $1.03 | −$0.97 |
| → ∞ | — | — | → 0 | **$1.04** | **−$0.96** |

**Expected value converges to $1.04 against a $2.00 ticket. There is no jackpot size at which it becomes a good bet.**

### 3. Picking unpopular numbers is real, but smaller than advertised

Player choice is wildly non-uniform, and it is well measured. From 805 million real manual selections in one national lottery:

- **7 is the most over-picked number worldwide** (~1.9× uniform), with 8 close behind
- Pick rates decline monotonically down the bet slip: **3.13% → 2.95% → 2.68% → 2.17%** by row against a 2.70% uniform rate
- The **highest number in the pool was the least-picked in all 118 draws** studied
- Bias **shrinks as the jackpot grows** — so the edge is largest in ordinary draws and smallest in exactly the rollover draws where overall EV is best

Three findings here run *opposite* to the usual advice, and the model encodes them:

- **Consecutive numbers are under-picked, not over-picked** — proximity aversion is real; 70% of people in a field experiment preferred a random-looking ticket, and 85% refused a cash bribe worth the ticket's entire EV to switch.
- **Evenly-spread combinations are over-picked** — that is what humans produce when trying to look random. "Balanced" filters walk you straight into the crowd.
- **Recently drawn numbers are temporarily under-bet** — money on a number drops sharply right after it appears and recovers only over months. This is genuinely exploitable and time-limited.

The honest ceiling: under Ziemba's formula `EV = 0.45 × F₁…F₆`, every one of your six numbers must be **14.2% under-bet just to break even**. And with ~70% of tickets sold as quick picks, conscious-selection effects are diluted by that factor before they reach your payout.

### 4. Wheels are real mathematics, and they don't do what's implied

Covering designs give genuine, provable guarantees, and every wheel this library builds is **verified exhaustively** rather than asserted. A 12-number, 4-if-4 wheel needs 55 tickets instead of the full wheel's 924.

But: **a wheel does not improve your jackpot odds.** Buying *n* distinct tickets multiplies your jackpot chance by exactly *n*, however you choose them. A wheel converts a random scatter of small prizes into a guaranteed floor — it trades variance for certainty, and you pay for it.

### 5. Nobody has ever beaten a lottery by finding a statistical bias

Across every documented case — the 1980 Pennsylvania "Triple Six Fix" (weighted balls), the Hot Lotto rootkit, Ronald Harris at the Nevada Gaming Control Board, Cash WinFall, Stefan Mandel, Lotto Texas 2023 — **not one attacker profited by exploiting an undetected statistical bias in the draw itself.** Every success was either an *operational* attack (insider access to the number-producing system) or a *structural* one (game design that created positive EV with a perfectly fair draw).

The roll-down structure is the only mechanism that ever produced a durable legal edge, because the money lands in tiers that are hit *often and predictably* — so the law of large numbers works for you instead of against you:

```
Cash WinFall roll-down, $2M pool, ~1M tickets sold
  match-5: $4,000 -> $24,236  (x6.06)
  match-4:   $150 ->    $909  (x6.06)
  match-3:     $5 ->     $30  (x6.06)
  return: 1.198 on a $2 ticket  (+20%)
```
Matching the historical record (×5.75, ×5.33, ×5.20) and the syndicates' reported 15–20% returns.

---

## Myanmar 2D

The game is not a ball draw — the number is derived from published Thai stock market figures. The universally repeated description is **wrong**.

```
top digit    = hundredths digit of the SET index          floor(S*100) mod 10
bottom digit = units digit of integer millions of turnover floor(V) mod 10
2D           = top*10 + bottom
```

Verified against **12 historical records from two independent sources — 12/12 exact matches.** On 21 Nov 2024 the SET index was 1441.11 with turnover 38,177.16M฿ and the published result was **17**; the folklore "last two digits of the index" rule gives 41.

Two consequences:

- **Uniform is the correct null.** These are the 5th and 6th significant digits of their quantities, where Benford deviation is negligible. Benford governs *leading* digits only.
- **The exploitable weakness is not the market.** The SET closes via a random-timed auction specifically to frustrate closing-price manipulation. The soft spot is that settlement depends on a *private scraper's* timestamped capture rather than an audited exchange publication — consistent with the general rule that lottery attacks target the operational chain, never the entropy source.

House edge at the verifiable 80× payout: **20%**. Better than US Pick 3 (50%) or the Thai state lottery (40%), worse than almost any casino game.

---

## Library use

```python
from lotterylab import PRESETS, load_csv
from lotterylab.fairness import audit, power_analysis
from lotterylab.ev import EVAssumptions, ticket_ev, break_even_jackpot
from lotterylab.generate import generate_unpopular
from lotterylab.wheels import covering_design

cfg = PRESETS["canada_649"]

history = load_csv("draws.csv", cfg)
print(audit(history).to_text())
print(power_analysis(cfg, history.n_draws)["note"])

print(ticket_ev(cfg, EVAssumptions(jackpot=20e6, tickets_sold=3_000_000)).to_text())
print(generate_unpopular(cfg, 5, salt="your-name").to_text())

wheel = covering_design(range(1, 13), 6, 4)
print(wheel.describe())   # guarantee is verified exhaustively, not asserted
```

CSV loading is deliberately forgiving about layout, and reports every row it could not parse rather than dropping it silently — silently dropping draws is how people "discover" biases that are really broken imports.

---

## Documentation

| Document | Contents |
|---|---|
| [`docs/01-how-numbers-are-generated.md`](docs/01-how-numbers-are-generated.md) | Ball machines, certified RNGs, and every documented fraud |
| [`docs/02-probability.md`](docs/02-probability.md) | The exact mathematics, and the corrections people get wrong |
| [`docs/03-game-theory.md`](docs/03-game-theory.md) | Player popularity, jackpot sharing, syndicates, Nash equilibrium |
| [`docs/04-what-actually-works.md`](docs/04-what-actually-works.md) | The short list of things with a real edge |
| [`docs/05-fallacies.md`](docs/05-fallacies.md) | Hot/cold/due, and why the backtest says no |
| [`docs/06-digit-games-2d-3d.md`](docs/06-digit-games-2d-3d.md) | 2D/3D mechanics, derivation, and economics |

---

## Verification

Run `python -m pytest tests/ -q` — 158 tests.

The library has **no runtime dependencies**; SciPy is used in tests purely as an independent oracle.

| Component | Checked against | Result |
|---|---|---|
| Special functions | SciPy | max relative error 5×10⁻¹⁴ |
| `binom_test` | `scipy.stats.binomtest` | 4×10⁻¹³ absolute |
| Prize-tier odds | Operators' published figures | exact on all 7 games |
| Outcome matrix | Must sum to 1 | exact to 10⁻¹⁵ |
| Covering designs | Exhaustive verifier + known optima | valid; hits the optimum where checked |
| Schönheim bound | Known-optimal C(49,6,2)=82, C(49,6,5)=325,205 | exact |
| 2D derivation | 12 historical records | 12/12 |
| Audit calibration | 400 fair histories | 4.2–5.2% false-positive rate |
| Audit power | Known-biased histories | 93–100% detection at ≥1.5× bias |

Three real bugs were found and fixed by this process, and each is documented in the source where it occurred:

1. **Haigh's correction was missing.** Balls are drawn *without replacement*, so the Pearson statistic is distributed as `[(pool−k)/(pool−1)]·χ²(pool−1)`, not `χ²(pool−1)`. Uncorrected, the headline fairness test fired at 1.3% instead of 5% — badly conservative, and it would miss real bias.
2. **A KS test on draw sums was anti-conservative.** Sums are heavily tied (2,000 draws land on ~175 distinct values) and KS assumes continuity; scoring tied observations against the inclusive CDF drove the false-positive rate to **20.7%**. Replaced with a binned chi-square.
3. **The Schönheim bound nested its ceilings backwards.** Ceilings don't commute; evaluated outermost-first it claimed C(49,6,2) ≥ 87 when the true covering number is 82 — not a lower bound at all.

---

## What this toolkit will not do

It will not tell you which numbers are due, hot, cold, or lucky. Those concepts have no referent in a memoryless process, and the backtester is included specifically so you can watch them fail against a properly calibrated null.

Every game in this library is negative expected value at retail. Picking unpopular combinations narrows the loss; it does not reverse it. The Kelly criterion's answer to "how much lottery should I buy?" is, for essentially every real ticket, **zero** — and for a genuinely positive-EV jackpot play it is still under a millionth of a bankroll per draw, which is why the syndicates that actually made money played roll-downs and bought combination space rather than chasing jackpots.

If you play, play for entertainment, with money you are content to lose.
