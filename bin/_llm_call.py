#!/usr/bin/env python3
"""Anthropic API call wrapper for the 心魔 prompt.

Zero external deps (urllib only). Prompt caching enabled on the system block —
the system prompt is static, so repeat calls hit the cache.

Inputs (stdin JSON):
    {"system": str, "user": str}

Outputs (stdout JSON):
    {"text": str|null, "ok": bool, "attempts": int, "reason": str}

Behavior:
    1. If JIANGHU_LLM_MOCK is set, the call is short-circuited:
         - JIANGHU_LLM_MOCK="<text>"  → returns that text on first attempt
         - JIANGHU_LLM_MOCK="@FAIL"   → exhausts retries, returns ok=false
         - JIANGHU_LLM_MOCK="@FILE:/path" → returns the file's contents
       This is for tests + offline development. No network call is made.
    2. Otherwise calls Anthropic Messages API with prompt caching on system.
    3. Validates output through deterministic quality gates (no "?", no
       advice-words, non-empty, both ZH and EN content).
    4. Up to JIANGHU_LLM_RETRIES (default 3) attempts.
    5. On final failure, returns ok=false; caller renders silence.

Env:
    ANTHROPIC_API_KEY        required for real calls
    ANTHROPIC_BASE_URL       default https://api.anthropic.com
    JIANGHU_LLM_MODEL        default claude-sonnet-4-5-20250929
    JIANGHU_LLM_MAX_TOKENS   default 600
    JIANGHU_LLM_RETRIES      default 3
    JIANGHU_LLM_MOCK         see above
"""
from __future__ import annotations

import json
import os
import re
import sys
import urllib.error
import urllib.request

DEFAULT_MODEL = "claude-sonnet-4-5-20250929"
DEFAULT_BASE_URL = "https://api.anthropic.com"
DEFAULT_MAX_TOKENS = 600
DEFAULT_RETRIES = 3

ADVICE_PATTERNS = [
    r"\b建议\b",
    r"\b也许\b",
    r"\b似乎\b",
    r"\b不妨\b",
    r"\bshould\b",
    r"\bcould\b",
    r"\bmaybe\b",
    r"\bperhaps\b",
    r"\bit seems\b",
    r"\byou might\b",
]
ADVICE_RE = re.compile("|".join(ADVICE_PATTERNS), re.IGNORECASE)
HAN_RE = re.compile(r"[\u4e00-\u9fff]")
LATIN_RE = re.compile(r"[A-Za-z]")


def quality_gates(text: str) -> tuple[bool, str]:
    """Returns (passed, reason). Lighter than the 5-gate spec — gates that can
    be checked deterministically without parsing each pattern's structure.
    """
    if not text or not text.strip():
        return False, "empty output"
    if "?" in text or "？" in text:
        return False, "contains question mark"
    m = ADVICE_RE.search(text)
    if m:
        return False, f"advice token: {m.group(0)}"
    if not HAN_RE.search(text):
        return False, "no Chinese content"
    if not LATIN_RE.search(text):
        return False, "no English mirror"
    return True, "ok"


def call_anthropic(system: str, user: str) -> tuple[str | None, str]:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return None, "ANTHROPIC_API_KEY not set"
    base = os.environ.get("ANTHROPIC_BASE_URL", DEFAULT_BASE_URL).rstrip("/")
    model = os.environ.get("JIANGHU_LLM_MODEL", DEFAULT_MODEL)
    max_tokens = int(os.environ.get("JIANGHU_LLM_MAX_TOKENS", str(DEFAULT_MAX_TOKENS)))

    body = {
        "model": model,
        "max_tokens": max_tokens,
        "system": [{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
        "messages": [{"role": "user", "content": user}],
    }
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        f"{base}/v1/messages",
        data=data,
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            err_body = e.read().decode("utf-8")
        except Exception:
            err_body = ""
        return None, f"http {e.code}: {err_body[:200]}"
    except (urllib.error.URLError, OSError, ValueError) as e:
        return None, f"network error: {e}"

    blocks = payload.get("content") or []
    for b in blocks:
        if b.get("type") == "text":
            return b.get("text", ""), "ok"
    return None, "no text block in response"


def call_mock(spec: str) -> tuple[str | None, str]:
    if spec == "@FAIL":
        return None, "mock: forced failure"
    if spec.startswith("@FILE:"):
        path = spec[len("@FILE:"):]
        try:
            with open(path, "r", encoding="utf-8") as f:
                return f.read(), "ok"
        except OSError as e:
            return None, f"mock file read failed: {e}"
    return spec, "ok"


def main(_argv: list[str]) -> int:
    try:
        body = json.load(sys.stdin)
    except ValueError as e:
        sys.stdout.write(json.dumps({"text": None, "ok": False, "attempts": 0, "reason": f"bad input json: {e}"}) + "\n")
        return 0

    system = body.get("system", "")
    user = body.get("user", "")
    mock = os.environ.get("JIANGHU_LLM_MOCK")
    retries = max(1, int(os.environ.get("JIANGHU_LLM_RETRIES", str(DEFAULT_RETRIES))))

    last_reason = ""
    for attempt in range(1, retries + 1):
        if mock is not None:
            text, reason = call_mock(mock)
        else:
            text, reason = call_anthropic(system, user)
        if text is None:
            last_reason = reason
            continue
        passed, gate_reason = quality_gates(text)
        if passed:
            sys.stdout.write(
                json.dumps(
                    {"text": text, "ok": True, "attempts": attempt, "reason": "ok"},
                    ensure_ascii=False,
                )
                + "\n"
            )
            return 0
        last_reason = f"gate failed: {gate_reason}"

    sys.stdout.write(
        json.dumps(
            {"text": None, "ok": False, "attempts": retries, "reason": last_reason},
            ensure_ascii=False,
        )
        + "\n"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
