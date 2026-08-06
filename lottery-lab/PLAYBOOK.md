# UK Lottery Playbook — the single source of truth

**This is the only file you need.** Everything in it is verified. If something isn't here, it isn't trusted.

> ### ⚠️ Which branch to use
>
> **USE:** branch `claude/bossman-hrljpk`, directory `lottery-lab/` — this file and the `lotterylab` package.
>
> **IGNORE:** branch `claude/uk-lottery-probability-CgSGE` (May 2026, `lottery/` directory). **Its odds are wrong.** It listed Thunderball Match 4 + Thunderball as 1 in 114,008; the true figure is 1 in 47,415. Every tier below the top two was similarly incorrect. Nothing in it should be used.
>
> When you ask me a lottery question, I read **this file only**.

---

## 1. Straight answer: which game should you play?

You said you don't care about £10 or £20, and you treat £1m as a fantasy. You want a **realistic shot at £1,000 – £20,000**. That makes the answer specific, and it is not one of the games you were thinking of.

### 🏆 For £1,000+ → **EuroMillions HotPicks, pick 3 numbers**

| | |
|---|---|
| Cost | **£1.50** per line |
| Prize | **£1,500** |
| Odds | **1 in 1,960** |
| £ staked per expected hit | **£2,940** |
| Return to player | **51.0%** |

**This is 98× better per pound than Lotto's Match 5** (£1,750 at 1 in 144,415, costing £288,830 per expected hit).

At £10/week for a year (£520 = 346 lines) you have a **16.2% chance — about 1 in 6 — of winning £1,500.**

### 🥈 For £10,000+ → **Lotto HotPicks, pick 4 numbers**

| | |
|---|---|
| Cost | **£1.00** per line |
| Prize | **£13,000** |
| Odds | **1 in 30,342** |
| Return to player | 42.8% |

At £10/week for a year (520 lines): **1.7% chance, about 1 in 59.**

### 🥉 For £20,000+ → **EuroMillions HotPicks, pick 4 numbers**

£1.50 for **£30,000** at **1 in 46,060**. At £520/year: 0.75%, about 1 in 134.

---

## 2. The full ranking

**Best route to each prize level**, by pounds staked per expected hit (lower is better):

| Target | Best option | Prize | Odds | £ per shot |
|---|---|---|---|---|
| **£1,000+** | **EuroMillions HotPicks pick-3** | £1,500 | 1 in 1,960 | **£2,940** |
| | Lotto HotPicks pick-4 | £13,000 | 1 in 30,342 | £30,342 |
| | EuroMillions HotPicks pick-4 | £30,000 | 1 in 46,060 | £69,090 |
| | Lotto Match 5 | £1,750 | 1 in 144,415 | £288,830 |
| **£10,000+** | **Lotto HotPicks pick-4** | £13,000 | 1 in 30,342 | **£30,342** |
| | EuroMillions HotPicks pick-4 | £30,000 | 1 in 46,060 | £69,090 |
| | Lotto HotPicks pick-5 | £350,000 | 1 in 834,398 | £834,398 |
| | Set For Life Match 5 | £120,000 | 1 in 1,704,377 | £2,556,565 |
| **£20,000+** | **EuroMillions HotPicks pick-4** | £30,000 | 1 in 46,060 | **£69,090** |
| | Lotto HotPicks pick-5 | £350,000 | 1 in 834,398 | £834,398 |

**Value ranking** — how fast the money drains (higher RTP is better):

| Option | Price | RTP | House edge |
|---|---|---|---|
| EuroMillions HotPicks pick-1 | £1.50 | **66.7%** | 33.3% |
| Lotto HotPicks pick-1 | £1.00 | 61.0% | 39.0% |
| EuroMillions HotPicks pick-2 | £1.50 | 54.4% | 45.6% |
| **Thunderball** (whole game) | £1.00 | **52.9%** | 47.1% |
| Lotto HotPicks pick-2 | £1.00 | 52.6% | 47.4% |
| **EuroMillions HotPicks pick-3** | £1.50 | **51.0%** | 49.0% |
| Lotto HotPicks pick-3 | £1.00 | 49.2% | 50.8% |
| Set For Life | £1.50 | 43.6% | 56.4% |
| EuroMillions HotPicks pick-4 | £1.50 | 43.4% | 56.6% |
| Lotto HotPicks pick-4 | £1.00 | 42.8% | 57.2% |
| Lotto HotPicks pick-5 | £1.00 | 41.9% | 58.1% |
| **UK Lotto** (whole game) | £2.00 | **40.3%** | 59.7% |
| **EuroMillions** (whole game) | £2.50 | **34.9%** | 65.1% |
| EuroMillions HotPicks pick-5 | £1.50 | 31.5% | 68.5% |

**The key finding:** EuroMillions HotPicks pick-3 is better on **both** counts than the two games you'd normally reach for. Better access to a four-figure prize (98× per pound) *and* better value (51.0% vs Lotto's 40.3% and EuroMillions' 34.9%).

That is rare. Usually access and value trade off. Here they point the same way.

---

## 3. What to avoid, and why

| Avoid | Reason |
|---|---|
| **EuroMillions main game** | Worst value of any main UK game at 34.9% RTP. You're paying £2.50 for jackpot odds of 1 in 139,838,160 that you will never hit. |
| **EuroMillions HotPicks pick-5** | Worst value of all, 31.5% RTP. The £1m prize is bait. |
| **Chasing big rollover jackpots** | Sales rise with the jackpot, so you split it more ways. EV *falls* past a peak. |
| **Powerball** | US game. Not sold in the UK. |
| **Lotto HotPicks pick-5 / Set For Life top prize** | £834k–£2.5m per expected hit. Same fantasy as the jackpot, dressed differently. |

---

## 4. Which numbers should I pick?

**For HotPicks: it does not matter at all. Use any numbers.**

HotPicks prizes are **fixed and never shared**. £1,500 is £1,500 whether one person or ten thousand hold your numbers. There is no advantage to unusual numbers, no disadvantage to 1-2-3, none whatsoever. Pick birthdays if you like them.

```bash
python -m lotterylab dip uk_lotto -n 5          # take any 3 or 4 of these for HotPicks
```

**For Lotto and EuroMillions main games: numbers matter slightly**, because jackpots are shared. Avoiding popular combinations doesn't change your odds — it changes how many people you split with.

```bash
python -m lotterylab dip euromillions -n 3 --mode unpopular --salt "shaheer"
```

Use your own `--salt`. If everyone used the same one, the "unpopular" numbers would become popular.

**For Thunderball and Set For Life: also fixed prizes.** Numbers are irrelevant. The tool will tell you so if you ask for unpopular mode.

---

## 5. Are past winning numbers useful? No.

I tested this properly rather than asserting it.

- **Your history cannot detect bias worth having.** With 3,000 draws you could only spot a ball running **20%+ hot**. Detecting a 5% bias would take **49,234 draws — 473 years**.
- **Hot/cold/due strategies fail against a proper null.** Measured against the theoretical rate, a hot-numbers strategy scores z = +6.7 on data *generated to be perfectly fair* — because within any fixed history the "hot" balls appear more often by construction. Against a permutation test that scrambles the order, the effect vanishes completely.
- **No one in history has ever beaten a lottery by finding a statistical bias.** Every documented case — the 1980 Pennsylvania weighted-ball fix, the Hot Lotto rootkit, Cash WinFall — was an insider attack or a game-design flaw. Never statistics.

**You do not need to send me winning numbers.** They cannot improve a pick. If you want to audit a game for fairness, the official history is free:

```bash
python -m lotterylab fetch          # downloads all four games
python -m lotterylab audit uk_lotto --uk-csv uk-data/uk_lotto.csv
```

---

## 6. Why someone wins a million every week at your till

Correct observation, and it's **designed**:

| Source | UK millionaires/week |
|---|---|
| EuroMillions UK Millionaire Maker | **2.00** — guaranteed, no matching needed |
| Lotto Match 5 + Bonus (flat £1m) | 4.66 |
| EuroMillions jackpot, UK share | 0.06 |
| **Total** | **~6.7 per week** |

The Millionaire Maker code is drawn from codes **actually sold**, so a winner exists before the draw happens.

Your side: one line in both weekly Lotto draws gives a **1 in 1,238** chance of £1m+ across **50 years**, costing £10,400. Both facts are true at once. The winners come from the crowd's size — 30+ million lines — not from the odds, which never move.

---

## 7. Commands you'll actually use

```bash
# Which game for the prize I want?
python -m lotterylab compare --target 1000 --weekly 10
python -m lotterylab compare --value

# Generate numbers
python -m lotterylab dip uk_lotto -n 5
python -m lotterylab dip euromillions -n 3 --mode unpopular --salt "shaheer"

# Real odds for any game
python -m lotterylab odds thunderball

# Why someone wins every week
python -m lotterylab winners

# Get and audit the official draw history
python -m lotterylab fetch
python -m lotterylab audit uk_lotto --uk-csv uk-data/uk_lotto.csv
```

---

## 8. Honest bottom line

Every option above loses money on average. The best value here still hands the operator **33p in every pound**, and the option I'm recommending for your goal takes **49p**.

What the analysis can do is stop you paying £288,830 per expected £1,750 win when £2,940 per expected £1,500 win is sitting on the same counter. That's a real, verified difference, and it's the whole value of this exercise.

If you play, treat it as entertainment with a set budget. **£10/week gives you roughly a 1-in-6 shot at £1,500 within the year** on EuroMillions HotPicks pick-3 — which is, genuinely, the best realistic offer on the shelf.

---

## Verification status

| Claim | How verified |
|---|---|
| All UK game odds | Exact combinatorics + 6M-ticket simulation; top tiers match operator figures exactly |
| HotPicks odds | Formula `C(drawn,k)/C(pool,k)`; EuroMillions HotPicks matches published on **all 5 tiers** |
| Thunderball sub-tiers | Corrected from the old branch's wrong values; simulation-confirmed |
| RTP figures | Computed from full prize tables |
| Hot/cold has no edge | Permutation test against scrambled-chronology null |
| Power analysis | Bonferroni-corrected two-proportion sample size |
| 2D derivation | 12/12 historical records |

**204 automated tests pass.** Run `python -m pytest tests/ -q`.

*Prize values and ticket prices change. Confirm current figures with the operator before betting.*
