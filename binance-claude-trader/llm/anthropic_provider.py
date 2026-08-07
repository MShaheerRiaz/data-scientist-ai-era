"""Claude decision provider, via the official Anthropic SDK.

Three things this file does that a generic OpenAI-compatible shim cannot:

1. **Prompt caching with a 1h TTL — but only when the cadence can use it.**
   The system prompt is stable and large; the market payload changes every bar.
   The breakpoint sits on the last system block so the prefix is reused, with a
   1h TTL rather than the default 5m because a 15m loop wakes up *after* a 5m
   cache has already expired.

   The subtlety: a cache *write* costs 2x base at 1h TTL (1.25x at 5m), so a
   breakpoint that never gets read is strictly more expensive than not caching
   at all. On a 1h decision interval the entry expires at almost exactly the
   moment the next call arrives — you would pay the write premium every cycle
   and bank roughly no reads. So caching is enabled only when the bar is
   shorter than the TTL; at 1h and above the loop pays plain input price, which
   is the cheaper of the two. See `cache_system` below.
2. **Native structured outputs** (`output_config.format`), so the response is
   schema-valid JSON rather than prose we have to regex.
3. **Refusal handling.** A declined request returns HTTP 200 with
   `stop_reason == "refusal"` and empty content; reading `content[0]` blindly
   would raise IndexError mid-loop.
"""

from __future__ import annotations

import json
from typing import Any

import anthropic

from llm.base import ProviderRefusal


class AnthropicProvider:
    def __init__(
        self,
        api_key: str,
        model: str = "claude-opus-5",
        effort: str = "medium",
        cache_system: bool = True,
    ):
        # Explicit timeout: the SDK default is 10 minutes, most of a 15m bar.
        # A hung call should fail this cycle and let the next bar try again,
        # not silently consume the trading window. The SDK retries 429/5xx
        # twice on its own.
        self._client = anthropic.Anthropic(api_key=api_key, timeout=300.0)
        self._model = model
        self._effort = effort
        # False on slow bars, where a cache entry expires before it is read and
        # the write premium is pure loss. main.py decides from the interval.
        self._cache_system = cache_system

    def decide(
        self,
        system_prompt: str,
        market_payload: dict[str, Any],
        schema: dict[str, Any],
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        # Stable prefix. Nothing volatile (no timestamps, no symbol list) may be
        # interpolated here, or the cache is invalidated every call and the
        # breakpoint becomes pure cost.
        system_block: dict[str, Any] = {"type": "text", "text": system_prompt}
        if self._cache_system:
            system_block["cache_control"] = {"type": "ephemeral", "ttl": "1h"}

        response = self._client.messages.create(
            model=self._model,
            # Thinking is on by default on Claude Opus 5 and counts against
            # max_tokens alongside the response text. Too tight a cap truncates
            # the JSON mid-decision; 16000 leaves comfortable headroom.
            max_tokens=16000,
            system=[system_block],
            output_config={
                "effort": self._effort,
                "format": {"type": "json_schema", "schema": schema},
            },
            messages=[
                {
                    "role": "user",
                    # Volatile content sits after the cache breakpoint.
                    "content": json.dumps(market_payload, separators=(",", ":")),
                }
            ],
        )

        usage = {
            "input_tokens": response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens,
            "cache_read_input_tokens": getattr(
                response.usage, "cache_read_input_tokens", 0
            ),
            "cache_creation_input_tokens": getattr(
                response.usage, "cache_creation_input_tokens", 0
            ),
        }

        if response.stop_reason == "refusal":
            raise ProviderRefusal(
                f"model declined: {getattr(response.stop_details, 'category', None)}"
            )

        if response.stop_reason == "max_tokens":
            # Truncated output means incomplete JSON. Fail with a clear reason
            # instead of letting json.loads produce a confusing parse error.
            raise RuntimeError(
                "decision truncated at max_tokens — thinking plus response "
                "exceeded the cap; raise max_tokens in AnthropicProvider.decide"
            )

        text = next((b.text for b in response.content if b.type == "text"), None)
        if not text:
            raise ProviderRefusal("model returned no text block")

        return json.loads(text), usage


    def review(
        self,
        system_prompt: str,
        trade_payload: dict[str, Any],
        schema: dict[str, Any],
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """Review one closed trade.

        No cache_control here on purpose. Reviews fire a few times a day at
        most, so a cache entry would almost always expire unused and cost the
        write premium for nothing — the opposite of the trading loop, which
        fires often enough to amortise it.
        """
        response = self._client.messages.create(
            model=self._model,
            # Same headroom logic as decide(): thinking shares the cap, and
            # reviews run at high effort, which thinks more.
            max_tokens=16000,
            system=system_prompt,
            output_config={
                # Reviews are not latency-sensitive and their whole value is
                # judgement quality, so this runs a notch above the trading
                # loop's effort.
                "effort": "high",
                "format": {"type": "json_schema", "schema": schema},
            },
            messages=[
                {"role": "user", "content": json.dumps(trade_payload, separators=(",", ":"))}
            ],
        )

        usage = {
            "input_tokens": response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens,
        }

        if response.stop_reason == "refusal":
            raise ProviderRefusal("model declined to review the trade")

        if response.stop_reason == "max_tokens":
            raise RuntimeError("review truncated at max_tokens — incomplete JSON")

        text = next((b.text for b in response.content if b.type == "text"), None)
        if not text:
            raise ProviderRefusal("review returned no text block")

        return json.loads(text), usage


class OpenRouterProvider:
    """Placeholder showing where an OpenRouter swap would go.

    Left unimplemented on purpose. Routing Claude through OpenRouter gives up
    the two features the loop above depends on — `cache_control` breakpoints
    and `output_config.format` — so a working implementation would need to
    reintroduce both by hand: JSON-mode prompting plus response validation and
    a retry on malformed output, and it would pay full input price on every
    call with no cache reads. Implement this only if you need multi-provider
    failover badly enough to accept that.
    """

    def __init__(self, *_args, **_kwargs):
        raise NotImplementedError(
            "OpenRouter provider not implemented — see the class docstring for "
            "what you lose and what you would need to rebuild."
        )
