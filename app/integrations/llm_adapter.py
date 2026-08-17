from __future__ import annotations

import os
import httpx

OPENAI_API_BASE = os.getenv("OPENAI_API_BASE", "https://api.openai.com/v1").rstrip("/")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")


async def generate_text(
    prompt: str,
    system: str | None = None,
    model: str | None = None,
    temperature: float = 0.4,
    max_tokens: int = 800,
    debug: bool = False,
) -> str:
    """Call OpenAI's chat completions API and return the generated text."""
    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY is not set — add it to your .env")

    if debug:
        print(f"[llm] prompt:\n{prompt}", flush=True)

    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    payload = {
        "model": model or OPENAI_MODEL,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            f"{OPENAI_API_BASE}/chat/completions",
            headers=headers,
            json=payload,
        )
        response.raise_for_status()
        data = response.json()

    response_text = data["choices"][0]["message"]["content"].strip()
    if debug:
        print(f"[llm] response:\n{response_text}", flush=True)
    return response_text