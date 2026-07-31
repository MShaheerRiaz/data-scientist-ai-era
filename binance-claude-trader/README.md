# binance-claude-trader

A Binance **spot** trading bot where Claude has full discretion over what to
trade, in which direction, and whether to trade at all — and where position
sizing and loss limits are enforced in code that the model cannot influence.

Runs on testnet with simulated orders by default. Two independent switches must
both be flipped before a single real order can be sent.

---

## How a cycle works

Once per closed candle (15m by default):

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
# fill in .env — see the comments in that file
python main.py
```

Run the tests before trusting anything (no pytest needed):

```bash
python tests/test_risk.py     # 19 - the risk gate
python tests/test_config.py   # 11 - settings coherence, safe defaults
python tests/test_paper.py    #  9 - paper equity and simulated PnL
```

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
binance_client.py       spot REST client, hand-rolled and auditable
indicators.py           EMA/RSI/ATR/swings, pure Python, no deps
universe.py             liquidity-filtered candidate selection
decision.py             system prompt + JSON schema contract
llm/base.py             provider interface
llm/anthropic_provider.py   Claude, with caching and refusal handling
risk.py                 the gate — deterministic, not promptable
executor.py             order placement and exit management
journal.py              JSONL log + crash-safe state
main.py                 the loop
tests/test_risk.py      19 tests covering the gate
```

## Status

Testnet-ready. Not backtested — an LLM in the loop cannot be backtested
honestly, which is the core argument for keeping a deterministic strategy as
the comparison baseline. Run it in dry-run alongside a rules-based strategy and
compare journals before concluding anything about edge.
