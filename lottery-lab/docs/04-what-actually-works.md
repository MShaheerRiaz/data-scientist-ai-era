# What actually works

A short document, because the list is short. Everything here has either a mathematical proof or a documented real-world payday behind it. Everything *not* here — see [document 05](05-fallacies.md).

---

## The ranking

| # | Method | Edge | Realistically available to you? |
|---|---|---|---|
| 1 | Don't play | Saves 100% of the house edge | **Yes** |
| 2 | Play the least-bad game | Cuts the edge 2–3× | **Yes** |
| 3 | Avoid popular combinations | Raises conditional payout | **Yes, modestly** |
| 4 | Wheels for guaranteed floors | Zero EV change; variance only | Yes, if you understand what you're buying |
| 5 | Positive-EV windows (roll-downs) | +15–25%, *proven* | Rarely — these get closed |
| 6 | Buy the combination space | +10–25%, *proven* | Needs $40M+ and terminal access |
| 7 | Find a genuinely biased draw | Would be large | **Effectively never** |

---

## 1. Not playing

The only strategy with a guaranteed positive return. Worth stating first because every line below is a way of losing more slowly.

## 2. Choosing the game

House edges vary enormously, and the differences dwarf anything you can achieve through number selection:

| Game | House edge |
|---|---|
| Myanmar 2D (at 80×) | **20%** |
| Singapore/Malaysia 4D | 34–36% |
| Thai Government Lottery | 40% |
| Typical national 6/49 | ~50% |
| US Pick 3 / Pick 4 straight | **50%** |
| Myanmar 3D (at 500×) | **50%** |

Moving from Pick 3 to a 20%-edge game more than halves your expected loss. No amount of clever number-picking comes close to that.

For comparison: roulette carries 5.26%, blackjack under 1%. Lotteries are the most expensive legal gambling available, by a wide margin.

## 3. Avoiding popular combinations

**The only number-selection method with a real basis.** It does not change your odds — it changes how many people you split with.

Concretely, avoid: all numbers ≤31 (birthdays); 7 and 8; evenly-spread "random-looking" spreads; arithmetic sequences; bet-slip columns and diagonals; anything in the top rows of the slip; previous winning combinations; and 1-2-3-4-5-6.

Counter-intuitively, and per the measured evidence, **do not avoid**: moderate consecutive runs (proximity aversion means the crowd already avoids them) or numbers drawn in the last few draws (temporarily under-bet).

```bash
python -m lotterylab generate canada_649 -n 5 --salt "something-personal"
python -m lotterylab explain canada_649 1 2 3 4 5 6
```

**Use your own salt.** If everyone ran this tool with the default, the "unpopular" combinations would become popular — the strategy is self-defeating under adoption. Salting keeps users apart.

**The honest ceiling.** Every one of your six numbers must be ~14.2% under-bet just to reach break-even, quick-pick dilution cuts the effect by ~70%, the edge shrinks precisely on the big-jackpot draws, and the researchers who developed the method found it "wins so rarely as to be unattractive as a practical system." It narrows the loss. It does not reverse it.

## 4. Wheels

Genuine mathematics with provable guarantees. A `(v,k,t)` covering design guarantees that if `t` of the drawn numbers fall inside your chosen pool of `v`, at least one ticket matches `t`.

```bash
python -m lotterylab wheel canada_649 --pool 12 --coverage 4
```

```
covering wheel C(12,6,4): 55 tickets from 12 numbers.
Guarantee (verified): if at least 4 of the drawn numbers are among your 12,
at least one ticket matches 4 or more.

full wheel would cost C(12,6) = 924 tickets; this uses 55
```

Every wheel this library produces is **verified exhaustively** against its own claim before being returned.

**What a wheel does not do.** It does not improve your jackpot odds. Buying `n` distinct tickets multiplies your jackpot chance by exactly `n`, however you choose them. A wheel converts a random scatter of small prizes into a guaranteed floor — variance traded for certainty, at a price.

Two warnings:

- **Key-number wheels concentrate risk.** Putting the same numbers on every ticket means that if they miss, *every* ticket is damaged simultaneously. In a fair lottery you have no reason to believe a key will be drawn.
- **Filters destroy guarantees.** Removing combinations by odd/even balance or sum range breaks the covering property. Worse, the popular filters — "balanced" parity, spread across the range — are exactly the heuristics the crowd uses, so filtering moves you *into* the crowded region and *raises* your expected co-winners. If you filter, filter the other way.

## 5. Positive-EV windows

**This is how every legal lottery fortune was actually made.**

The mechanism is a **roll-down**: when a jackpot goes unhit at a cap, the money flows into lower tiers instead of rolling over. Those tiers are hit *often and predictably*, so a large buyer converts them into a near-certain average by the law of large numbers. A jackpot play stays a lottery no matter how many tickets you buy; a roll-down does not.

Cash WinFall (Massachusetts 6/46) is the documented case. Modelled by this library:

```
roll-down $2M pool, ~1M tickets sold
  match-5: $4,000 -> $24,236  (x6.06)
  match-4:   $150 ->    $909  (x6.06)
  match-3:     $5 ->     $30  (x6.06)
  return: 1.198 on a $2 ticket  (+20%)
```

Matching the historical record (×5.75, ×5.33, ×5.20 — near-identical multipliers, because the pool was allocated so every tier scaled together) and the syndicates' reported 15–20% returns. Over seven years, high-volume players wagered ~$40M and won ~$48M.

Nothing about it was illegal. The state's inspector general criticised the *lottery* for letting it run, and found no evidence small players or taxpayers were harmed.

**These windows close.** Michigan killed Winfall in 2005; Massachusetts killed Cash WinFall in 2012.

Other structural windows worth knowing: **capped rollovers** (where the prize cannot grow but keeps accumulating), **promotional multiplier draws**, and **guaranteed-minimum jackpots on low-sales games**. The tool to evaluate any of them:

```bash
python -m lotterylab ev <game> --jackpot X --sales-growth 0.39 --cash-ratio 0.52 --tax 0.37
```

## 6. Buying the combination space

Proven, and mostly closed. See [document 03 §5](03-game-theory.md). Requires $40M–$584M, retailer terminal access at scale, and tolerance of the Ireland-1992 outcome where you hold a winner and so do two other people.

## 7. Finding a biased draw

**Effectively unavailable, and this is the finding people least expect.**

Your history almost certainly cannot detect a bias worth exploiting — 473 years of draws to detect a 5% biased ball. And even if a bias existed at a detectable size, it would have had to survive random ball-set selection, weight screening with a 1-gram trigger, and scripted test draws.

Most decisively: **in no documented case in lottery history did anyone profit by exploiting an undetected statistical bias in a draw.** Every real attack was operational (insider access to the number-producing system) or structural (game design). Not one was statistical.

Run the audit anyway if you have the data — it is the responsible thing to do with a draw history, and it is what the module is for:

```bash
python -m lotterylab audit canada_649 --csv draws.csv
python -m lotterylab power canada_649 --draws 3000
```

Just read the power analysis alongside the result.

---

## If you play anyway

1. Pick the lowest house edge available to you.
2. Buy one ticket, not many — the odds are so long that buying more changes nothing meaningful, while the cost scales linearly.
3. Use a salted unpopular-combination pick, or a quick pick. Both are fine; the quick pick is free.
4. Skip the big-jackpot frenzy draws. That is when sharing is worst and the selection edge is smallest.
5. Budget it as entertainment, and set the amount in advance.

The expected loss is 20–50% of everything you stake. That is the product. Enjoy it as one if you enjoy it at all.

---

*Next: [05 — Fallacies, and the proof they fail](05-fallacies.md)*
