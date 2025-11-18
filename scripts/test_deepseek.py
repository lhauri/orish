"""Quick DeepSeek connectivity test.

Run with: `python scripts/test_deepseek.py`

Ensures the DEEPSEEK_API_KEY/.env is configured correctly before launching the app.
"""

from __future__ import annotations

import os
import sys

from openai import OpenAI


def main() -> int:
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        print("DEEPSEEK_API_KEY missing. Export it or place it in your .env file.", file=sys.stderr)
        return 1

    base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
    if not base_url.rstrip("/").endswith("/v1"):
        base_url = base_url.rstrip("/") + "/v1"

    client = OpenAI(api_key=api_key, base_url=base_url)
    print("Calling DeepSeek chat completions...")
    try:
        response = client.chat.completions.create(
            model=os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
            messages=[
                {"role": "system", "content": "You are a connectivity test bot."},
                {"role": "user", "content": "Reply with a short confirmation that the API works."},
            ],
            stream=False,
        )
    except Exception as exc:  # pragma: no cover - manual diagnostic
        print(f"DeepSeek call failed: {exc}", file=sys.stderr)
        return 2

    choice = response.choices[0]
    print("DeepSeek responded:", choice.message.content)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
