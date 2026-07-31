"""Provider interface for the decision model.

Everything the bot needs from an LLM goes through `DecisionProvider.decide`.
Swapping providers (OpenRouter, a self-hosted gateway) means adding one file
that implements this protocol — no other module imports an SDK directly.
"""

from __future__ import annotations

from typing import Any, Protocol


class ProviderRefusal(RuntimeError):
    """The model declined to answer. Treated as 'no trade', never as an error."""


class DecisionProvider(Protocol):
    def decide(
        self,
        system_prompt: str,
        market_payload: dict[str, Any],
        schema: dict[str, Any],
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """Return (decision, usage).

        `decision` must validate against `schema`. `usage` carries token counts
        for cost tracking; an empty dict is acceptable if the provider does not
        report them.
        """
        ...
