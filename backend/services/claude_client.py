"""Claude via Microsoft AI Foundry.

The Foundry endpoint at ``…/anthropic/`` speaks the native Anthropic Messages
API, so the official ``anthropic`` SDK works out of the box with a base-URL
override. Every Claude-based agent in this MVP uses this thin wrapper.
"""

from __future__ import annotations

import logging
import time
from typing import Optional

from anthropic import AsyncAnthropic

log = logging.getLogger("claude")  # short logger name so it stands out in logs


class ClaudeClient:
    def __init__(self, base_url: str, api_key: str, model: str):
        self._client = AsyncAnthropic(base_url=base_url, api_key=api_key)
        self._model = model

    async def complete(
        self,
        system: str,
        user: str,
        max_tokens: int = 1024,
        temperature: float = 0.3,
        caller: Optional[str] = None,
    ) -> str:
        """Returns the assistant's text response."""
        tag = caller or "?"
        log.info("→ Claude call  [%s]  model=%s  sys=%d chars, user=%d chars",
                 tag, self._model, len(system), len(user))
        t0 = time.time()
        resp = await self._client.messages.create(
            model=self._model,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        elapsed = time.time() - t0
        usage = getattr(resp, "usage", None)
        if usage:
            log.info("← Claude reply [%s]  %.2fs  in=%d tok  out=%d tok",
                     tag, elapsed, usage.input_tokens, usage.output_tokens)
        else:
            log.info("← Claude reply [%s]  %.2fs", tag, elapsed)
        # Concatenate all text blocks (usually just one)
        parts = []
        for block in resp.content:
            text = getattr(block, "text", None)
            if text:
                parts.append(text)
        return "".join(parts)
