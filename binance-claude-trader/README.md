# binance-claude-trader

A Binance **spot** trading bot where Claude has full discretion over what to
trade, in which direction, and whether to trade at all — and where position
sizing and loss limits are enforced in code that the model cannot influence.

Runs on testnet with simulated orders by default. Two independent switches must
both be flipped before a single real order can be sent.

---

## How a cycle works

Once per closed candle (1h recommended; set via `CANDLE_INTERVAL`):

```
1. check exits      stops and targets on open positions are honoured first
2. read equity      total account value in USDT, priced through spot pairs
3. kill switch      if the day's realised loss breached the cap, stop here
4. build universe   top-N USDT pairs by 24h volume, liquidity-filtered
5. snapshot         reduce each pair to ~156 tokens of structure and indicators
6. decide           Claude picks a symbol and a side, or returns "none"
7. risk gate        deterministic approve/reject, and position sizing
8. execute          market order, or simulate it under DRY_RUN
9. journal          log the decision either way, approved or rejected
```

## What the model controls, and what it doesn't

| Claude decides | Code decides |
|---|---|
| Which symbol (from the liquid universe) | How much capital the position gets |
| Long or no trade | Whether the trade is permitted at all |
| Entry, stop and target levels | Max concurrent positions |
| Whether to close an open position | Daily loss cap and kill switch |
| Whether to trade at all this cycle | Which symbols are eligible |

`confidence` is used as a *filter* — below `MIN_CONFIDENCE` the trade is
discarded — but deliberately **not** as a sizing input. If confidence scaled
size, the model would have an incentive to inflate it.

---

## Setup

```bash
cd binance-claude-trader
pip install -r requirements.txt
cp .env.example .env
# fill in .env — see the comments in that file; it is loaded automatically
python main.py
```

Run the tests before trusting anything (no pytest needed):

```bash
python tests/test_risk.py         # 19 - the risk gate
python tests/test_config.py       # 15 - settings, .env loading, safe defaults
python tests/test_paper.py        #  9 - paper equity and simulated PnL
python tests/test_lessons.py      # 20 - lesson dedup, volume anomalies
python tests/test_quant.py        # 28 - expectancy, Kelly, ruin, leverage
python tests/test_integration.py  #  9 - the full cycle, stubbed exchange+model
```

The integration file matters most: it drives the real `run_cycle` through
open → stop exit → review → lesson → next decision, model-instructed close,
the kill switch, entry-drift skips, and a process restart — with a stub
exchange that raises if paper mode ever touches the real account balance.

### Getting testnet keys

Register at <https://testnet.binance.vision> with a GitHub account and generate
a key pair there. Testnet keys are separate from production keys; a production
key sent to the testnet host just returns 401. Testnet balances are fake and
periodically reset.

### Paper trading against live markets

The two switches are independent, which gives three modes:

| `BINANCE_TESTNET` | `DRY_RUN` | Order book | Fills | Use for |
|---|---|---|---|---|
| `true` | `true` | testnet (fake) | simulated | checking the plumbing works |
| `false` | `true` | **real** | simulated | **paper trading — start here** |
| `false` | `false` | real | **real money** | when the journal has earned it |

Paper mode needs **no Binance API key at all** — it only reads public
endpoints. Leave the key fields blank:

```bash
BINANCE_TESTNET=false
DRY_RUN=true
PAPER_EQUITY=10000
```

Testnet order books are thin and behave nothing like the real thing, so paper
trading against the live book is the honest test. Testnet is only worth a short
pass to confirm the plumbing.

Set `PAPER_EQUITY` to what you would actually deploy. Sizing is a percentage of
equity, so paper trading a 100k balance you don't have tells you nothing about
the position sizes you would really see.

Simulated PnL persists in `state.json` across restarts, so you can leave it
running for weeks and read the cumulative result. Raising `PAPER_EQUITY` later
takes effect while keeping accumulated PnL.

### Going live (later than you think)

```bash
BINANCE_TESTNET=false
DRY_RUN=false           # actually sends orders — now the keys are required
```

On the production API key: enable spot trading, **disable withdrawals**,
disable futures, and restrict to your server's IP. A key that cannot withdraw
cannot drain the account even if the server is compromised.

---

## Things you should know before running this

**Stale decisions are skipped, not chased.** The model prices its decision
off the last closed candle; if the market has already run past half the stop
distance from the intended entry — or through the stop or target outright —
the executor refuses the trade and journals a `skip` instead of buying bad
slippage. This applies in paper and live mode alike.

**Thinking and protecting run on different clocks.** Decisions happen once
per closed candle (`CANDLE_INTERVAL`, recommended 1h). Stops and targets are
price levels, not candle events — while positions are open they are checked
every `POLL_SECONDS` (default 30s), so an exit fires within about half a
minute of its level being touched, whichever decision interval you use. This
is what makes the cheaper, calmer 1h interval safe to recommend.

**Stops are enforced by this process, not by the exchange.** There is no
resting stop order on Binance. If the bot is not running, your stops are not
active. Do not leave positions open with the process stopped. This is a real
tradeoff, taken because Binance spot OCO interacts badly with the
`quoteOrderQty` sizing used on entry — but it is the single biggest operational
risk in the design and you should be aware of it.

**Spot only, no shorts, no leverage.** The model is told this and the risk gate
enforces it. A bearish read produces "none", or "close" if a position is open.
This is also why the bot cannot profit from a falling market — it can only
avoid it.

**UK residency and the account details mismatch.** You mentioned the account was
registered on Pakistani details while you are in the UK. That is your call to
make, but it is a genuine engineering risk here, not just a compliance one: KYC
mismatches get accounts frozen, and a freeze that lands while positions are open
means you cannot exit them and the bot cannot either. Concretely, that is why
this is spot-only and why the design avoids leaving unmanaged positions open.
UK residents also face FCA restrictions on crypto derivatives, which is a second
reason futures are absent from the codebase entirely.

**The LLM is the weakest link in the loop.** It is non-deterministic, it cannot
be backtested honestly, and it will occasionally be confidently wrong. The risk
gate exists because of this. Read `journal.jsonl` before believing anything.

---

## Learning from its own trades

After every closed trade the bot reviews it and, when there is something worth
keeping, writes a lesson to `lessons.json`. Lessons are injected into later
decisions, with a count of how often each has recurred.

The review scores **process and outcome separately**, which is the part most
trade journals get wrong:

| | Profit | Loss |
|---|---|---|
| **Sound process** | repeat it | normal variance — usually *no lesson* |
| **Poor process** | dangerous; the result rewarded a bad decision | the real teaching case |

If you only journal losses you learn superstitions: you "fix" good decisions
that happened to lose, and keep bad decisions that happened to win. So a
well-reasoned trade that lost normally records nothing, and a reckless trade
that *won* still gets flagged.

Reviews judge only on data captured at entry time (`entry_snapshot` on the
position). Without that constraint the reviewer reasons from the exit and
produces hindsight rather than lessons.

Lessons are deduplicated by token similarity, so a repeated mistake increments
a counter rather than filling the file with restatements. The threshold is
tuned high (0.75 Jaccard) because trading lessons share heavy vocabulary —
"volume spike means enter" and "volume spike means wait" overlap on most words
while meaning opposite things, and merging those would silently discard one.

```bash
jq -r '.lessons[] | "\(.occurrences)x  \(.text)"' lessons.json | sort -rn
```

Turn it off with `ENABLE_REVIEW=false`.

## News and catalysts

Two independent signals, kept separate on purpose:

**Volume anomalies** are computed from Binance data alone — no API key, no
external service. Each pair gets `volume_ratio` and `range_expansion` measured
against *its own* recent baseline, so a small-cap waking up registers the same
as a large-cap doing so. Both must be elevated together to flag: volume without
range expansion is churn, usually one large print that moves no price.

**A news brief** is gathered by Claude with web search, hourly by default
(`NEWS_REFRESH_SECONDS`). Anomalous symbols are passed in as focus, so the
search asks about what is actually moving rather than for generic headlines.

The ordering is deliberate: volume moves *before* headlines. By the time a
story is widely reported, the move it describes has usually happened. So the
anomaly scan leads and the news explains — never the reverse. The prompt tells
the model to treat widely-reported news as priced in, and to avoid buying
verticals that are already extended.

A failed news fetch never stops trading — the bot falls back to pure price
action. Turn it off with `ENABLE_NEWS=false`.

## The mathematics (quant.py / analyze.py)

The maths that decides trading outcomes is not calculus. It is a small set of
results from probability and repeated-betting theory, and `quant.py` implements
them with tests against hand-computable cases:

| Function | Answers |
|---|---|
| `expectancy_r` | is there an edge at all? |
| `breakeven_win_rate` | what win rate does this reward:risk require? |
| `kelly_fraction` | given an edge, how much may be risked? |
| `risk_of_ruin` | what is the chance of going broke before the edge pays? |
| `liquidation_distance_pct` | how far can price move before leverage closes you out? |
| `trades_needed_for_significance` | is the result real, or luck? |

After a paper run, `analyze.py` applies all of it to your actual journal:

```bash
python analyze.py journal.jsonl
```

It reports the edge, whether the sample is large enough to believe it, the
Kelly-implied position size, and the survival odds at several sizes.

### Two results worth internalising

**A high win rate does not mean profit.** `expectancy_r(0.70, 0.4)` is negative
— winning 70% of trades while losing money, because the losses are larger than
the wins. Win rate quoted without reward:risk is meaningless.

**Overbetting a real edge still destroys the account.** From the test suite,
with an identical 55% win rate at 1.5:1 across every row — only size changes:

| risk/trade | × Kelly | P(lose 50%) | median result |
|---|---|---|---|
| 0.5% | 0.02× | 0.0% | 2.5× |
| 5% | 0.20× | 0.1% | 4,218× |
| 25% | 1.00× | 44% | huge, via 92% drawdowns |
| 50% | 2.00× | **96%** | **0.48× — a loss** |
| 75% | 3.00× | **100%** | 0.25× |

At exactly twice Kelly the expected growth rate reaches zero; beyond it a
genuinely profitable strategy still goes to zero. Position sizing is not a
detail on top of a strategy — past a threshold it *is* the strategy.

## Reading the journal

Every decision is logged, including rejected ones. Rejections are the most
informative record you have — they tell you whether the model is producing
sane ideas the limits are trimming, or nonsense the limits are catching.

```bash
# What did it decide, and was it allowed through?
jq -r 'select(.event=="decision") | "\(.ts) \(.action) \(.symbol) conf=\(.confidence) -> \(.verdict)"' journal.jsonl

# Why did the risk gate reject things?
jq -r 'select(.event=="decision" and .approved==false) | .verdict' journal.jsonl | sort | uniq -c | sort -rn

# Is prompt caching actually working? cache_read should be non-zero after the
# first call. If it stays at 0, the system prompt is being invalidated.
jq -r 'select(.event=="decision") | .usage | "in=\(.input_tokens) cached=\(.cache_read_input_tokens) out=\(.output_tokens)"' journal.jsonl

# Realised PnL on closed trades
jq -r 'select(.event=="fill" and .order.pnl) | .order.pnl' journal.jsonl | paste -sd+ | bc
```

---

## Telegram notifications

Set `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` in `.env` (setup steps are in
`.env.example` and `notify.py` — about two minutes with @BotFather) and the bot
messages your phone on the events that matter:

- position opened (entry, stop, target, size, risk)
- position closed (reason and P&L, plus the day's running total)
- daily kill switch tripped (once, on the transition — not every cycle)
- bot started, and bot stopped while positions are still open (important:
  stops are enforced by the process, so a stopped bot means unprotected
  positions)

No-trade cycles stay silent by design. Notifications are fire-and-forget: a
Telegram outage is logged and ignored, it can never affect trading. Leave the
two variables blank and the feature is off.

### Asking it questions

Telegram is two-way, but **read-only**. Send the bot a command and it answers
from live state and its journal, so you can watch what it is doing without
SSHing into the VPS:

| Command | What you get |
|---|---|
| `/status` | mode, equity, day P&L, open positions, halted? |
| `/positions` | each position with live P&L and progress in R |
| `/why` | the last decision, its reasoning, and what it passed on |
| `/rejected` | recent entries the risk gate blocked, with reasons |
| `/journal` | the last dozen journal events |
| `/pnl` | closed trades, win rate, total realised |
| `/lessons` | everything it has learned, with repeat counts |

Replies land within ~`POLL_SECONDS`, because commands are polled on the same
clock as the exit watcher — you get an answer in seconds even mid-way through
an hourly candle.

**Nothing sent over chat can act on the account.** There is no command to
open, close, pause, or resize a position, and `test_no_command_can_act_on_the_account`
exists to keep it that way. The reasoning: chat is the only part of this system
reachable from the open internet, so the worst case for a compromised token is
that someone reads a P&L figure. Trading decisions come from the model and the
risk gate and nothing else can reach them. To halt trading, stop the service on
the VPS.

`/pnl` deliberately warns you when there are fewer than 50 closed trades —
a three-trade winning streak is not an edge, and the bot says so.

### Keeping it private

Telegram bots cannot be made unlisted, so privacy is enforced at the bot rather
than by hiding it:

- **Only your chat id gets answers.** Every other chat is refused and gets no
  reply at all — not an error, not a "not authorised" message, nothing. A
  stranger cannot even confirm the bot is running.
- **You are told if it happens.** The first message from an unknown chat sends
  you a warning, capped at `MAX_REFUSAL_ALERTS` per run so it cannot itself
  become a spam channel.
- **Harden it in BotFather** (30 seconds, recommended): send `/setjoingroups`
  → *Disable* so nobody can add it to a group, and `/setprivacy` → *Enable*.
- **If the token ever leaks**, `/revoke` in BotFather invalidates it instantly;
  put the new one in `.env` and restart. The token is the only secret here —
  it grants chat access, never account access.

---

## Cost

~1,880 tokens of market payload plus a ~700-token system prompt, and ~400
tokens out per decision. At 96 decisions/day on 15m bars:

| Model | Per decision | Per day | Per month |
|---|---|---|---|
| `claude-opus-5` | ~$0.023 | ~$2.20 | ~$66 |
| `claude-sonnet-5` | ~$0.009 | ~$0.86 | ~$26 |

Prompt caching cuts the input side substantially once warm. The system prompt is
cached with a **1-hour TTL** rather than the 5-minute default, because a 15m
loop wakes up after a 5-minute cache has already expired — with the default you
would pay the write premium on every bar and never record a single cache read.
Check `cache_read_input_tokens` in the journal to confirm it is working.

---

## Why the official Anthropic SDK and not OpenRouter

You asked about OpenRouter. It works, but this loop depends on three things
that an OpenAI-compatible shim does not expose cleanly:

- `cache_control` breakpoints with an explicit TTL — the caching above
- `output_config.format` — schema-guaranteed JSON, so a decision cannot arrive
  as prose that needs regex-parsing into a price level
- reliable `usage` fields including cache hits, for cost tracking

Provider access is isolated behind `llm/base.py`, so swapping is one file. See
`OpenRouterProvider` in `llm/anthropic_provider.py` for what you would need to
rebuild by hand.

---

## Layout

```
config.py               settings + risk limits, with the coupling documented
lessons.py              trade review + deduplicated lesson book
quant.py                expectancy, Kelly, risk of ruin, leverage maths
analyze.py              applies quant.py to your journal
catalyst.py             volume anomalies + hourly news brief
binance_client.py       spot REST client, hand-rolled and auditable
indicators.py           EMA/RSI/ATR/swings, pure Python, no deps
universe.py             liquidity-filtered candidate selection
decision.py             system prompt + JSON schema contract
llm/base.py             provider interface
llm/anthropic_provider.py   Claude, with caching and refusal handling
risk.py                 the gate — deterministic, not promptable
executor.py             order placement and exit management
journal.py              JSONL log + crash-safe state
notify.py               Telegram alerts + command polling, fire-and-forget
telegram_control.py     answers /status, /why, /journal … from live state
main.py                 the loop
tests/test_risk.py      19 tests covering the gate
```

## Status

Testnet-ready. Not backtested — an LLM in the loop cannot be backtested
honestly, which is the core argument for keeping a deterministic strategy as
the comparison baseline. Run it in dry-run alongside a rules-based strategy and
compare journals before concluding anything about edge.
