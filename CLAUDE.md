# Repository memory

This repo holds several unrelated projects. Load the memory for whichever one
you are working in.

## Crypto trading bot — `binance-claude-trader/`

@CRYPTO-BOT.md

Read that file **before** changing anything under `binance-claude-trader/`. It
carries the constraints, the risk maths, and the list of bugs already fixed —
several of which look like reasonable code until you know why they were wrong.

Two things that are easy to get wrong and expensive to relearn:

- **Spot only. No futures, no leverage, no shorting.** This is a legal and
  account-safety constraint, not a preference. See §1 of the memory file.
- **The risk gate is deterministic and must stay that way.** The model chooses
  what to trade; code alone decides how much. Never let a model-supplied field
  (confidence especially) influence position size.

Tests are plain Python, no pytest:

```bash
cd binance-claude-trader && for f in tests/test_*.py; do python3 "$f"; done
```

137 tests. Every one of them pins a specific past bug or invariant — if you
break one, read why it exists before you edit it.
