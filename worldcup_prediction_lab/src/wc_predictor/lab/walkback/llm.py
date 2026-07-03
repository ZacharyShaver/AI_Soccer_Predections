"""Minimal LM Studio (OpenAI-compatible) chat client returning strict JSON.

No agentic tool use by design: 8-14B local models are unreliable tool callers,
and a single deterministic completion keeps the experiment reproducible.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

import requests

_JSON_RE = re.compile(r"\{.*\}", re.DOTALL)


def _extract_json(content: str) -> dict | None:
    match = _JSON_RE.search(content)
    if not match:
        return None
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return None


@dataclass
class LMClient:
    base_url: str = "http://localhost:1234/v1"
    model: str = ""
    temperature: float = 0.0
    timeout: int = 180

    def chat_json(self, system: str, user: str, *, max_retries: int = 2, session=None) -> dict:
        session = session or requests.Session()
        messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
        for attempt in range(max_retries + 1):
            resp = session.post(
                f"{self.base_url}/chat/completions",
                json={"model": self.model, "messages": messages,
                      "temperature": self.temperature},
                timeout=self.timeout,
            )
            content = resp.json()["choices"][0]["message"]["content"]
            parsed = _extract_json(content)
            if parsed is not None:
                return parsed
            messages.append({"role": "assistant", "content": content})
            messages.append({"role": "user",
                             "content": "Reply with ONLY a valid JSON object. No prose."})
        raise ValueError(f"no valid JSON after {max_retries + 1} attempts")
