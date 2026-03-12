"""
LLM abstraction layer — supports Groq (cloud) and Ollama (local).

Every call goes through `llm_complete(prompt, system)` which returns a string.
Provider switching is transparent to the rest of the application.
"""

from __future__ import annotations

import json
import logging
import ssl
from typing import Any

from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

from config import LLMProvider, get_settings

logger = logging.getLogger(__name__)


# ── SSL helper ────────────────────────────────────────────────────────────────

def _build_ssl_context() -> ssl.SSLContext:
    """
    Build an SSL context that trusts the system/corporate CA certificates.

    Corporate proxies (e.g. Zscaler, Netskope) often inject certificates that
    lack the Authority Key Identifier extension.  Python 3.13 rejects these by
    default.  We load certs with VERIFY_X509_PARTIAL_CHAIN so intermediate-only
    chains are accepted, and we suppress the strict AKI check.
    """
    settings = get_settings()
    ctx = ssl.create_default_context()

    # Allow partial chains — the proxy cert may not chain back to a root
    # that Python recognises in the normal way.
    ctx.verify_flags |= ssl.VERIFY_X509_PARTIAL_CHAIN  # type: ignore[attr-defined]

    ca_bundle = settings.ca_bundle_path
    if ca_bundle:
        logger.info("Loading custom CA bundle into SSL context: %s", ca_bundle)
        ctx.load_verify_locations(ca_bundle)

    return ctx


# ── Provider-specific clients (lazy-initialised) ─────────────────────────────

_groq_client: Any = None
_ollama_client: Any = None


def _get_groq_client() -> Any:
    global _groq_client
    if _groq_client is None:
        from groq import Groq  # type: ignore[import-untyped]
        import httpx

        settings = get_settings()
        if not settings.groq_api_key:
            raise ValueError(
                "GROQ_API_KEY is not set. "
                "Get a free key at https://console.groq.com and add it to .env"
            )

        # Build an SSL-aware httpx client for corporate proxy environments
        ssl_ctx = _build_ssl_context()
        http_client = httpx.Client(verify=ssl_ctx)
        _groq_client = Groq(api_key=settings.groq_api_key, http_client=http_client)
    return _groq_client


def _get_ollama_client() -> Any:
    global _ollama_client
    if _ollama_client is None:
        import ollama  # type: ignore[import-untyped]

        _ollama_client = ollama.Client(host=get_settings().ollama_base_url)
    return _ollama_client


# ── Public API ────────────────────────────────────────────────────────────────

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    retry=retry_if_exception_type(Exception),
    reraise=True,
)
async def llm_complete(
    prompt: str,
    system: str = "",
    *,
    temperature: float = 0.2,
    max_tokens: int = 2048,
    json_mode: bool = False,
) -> str:
    """
    Send a prompt to the configured LLM and return the text response.

    When *json_mode* is True the LLM is instructed to return valid JSON only.
    """
    settings = get_settings()

    if settings.llm_provider == LLMProvider.GROQ:
        return await _groq_complete(
            prompt, system, temperature=temperature,
            max_tokens=max_tokens, json_mode=json_mode,
        )
    elif settings.llm_provider == LLMProvider.OLLAMA:
        return await _ollama_complete(
            prompt, system, temperature=temperature,
            max_tokens=max_tokens, json_mode=json_mode,
        )
    else:
        raise ValueError(f"Unknown LLM provider: {settings.llm_provider}")


async def _groq_complete(
    prompt: str,
    system: str,
    *,
    temperature: float,
    max_tokens: int,
    json_mode: bool,
) -> str:
    """Call Groq cloud API (synchronous SDK, wrapped for async callers)."""
    import asyncio

    client = _get_groq_client()
    settings = get_settings()

    messages: list[dict[str, str]] = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    kwargs: dict[str, Any] = {
        "model": settings.groq_model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}

    # Groq SDK is synchronous — run in executor to avoid blocking the loop
    loop = asyncio.get_event_loop()
    response = await loop.run_in_executor(
        None, lambda: client.chat.completions.create(**kwargs)
    )

    text: str = response.choices[0].message.content or ""
    logger.debug("Groq response length: %d chars", len(text))
    return text.strip()


async def _ollama_complete(
    prompt: str,
    system: str,
    *,
    temperature: float,
    max_tokens: int,
    json_mode: bool,
) -> str:
    """Call local Ollama instance."""
    import asyncio

    client = _get_ollama_client()
    settings = get_settings()

    messages: list[dict[str, str]] = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    kwargs: dict[str, Any] = {
        "model": settings.ollama_model,
        "messages": messages,
        "options": {
            "temperature": temperature,
            "num_predict": max_tokens,
        },
    }
    if json_mode:
        kwargs["format"] = "json"

    loop = asyncio.get_event_loop()
    response = await loop.run_in_executor(
        None, lambda: client.chat(**kwargs)
    )

    text: str = response["message"]["content"] or ""
    logger.debug("Ollama response length: %d chars", len(text))
    return text.strip()


# ── JSON helper ───────────────────────────────────────────────────────────────

async def llm_json(
    prompt: str,
    system: str = "",
    *,
    temperature: float = 0.1,
    max_tokens: int = 2048,
) -> dict[str, Any]:
    """
    Convenience wrapper: calls the LLM in JSON mode and parses the result.
    Falls back to extracting JSON from fenced code blocks if needed.
    """
    raw = await llm_complete(
        prompt, system, temperature=temperature,
        max_tokens=max_tokens, json_mode=True,
    )

    # Try direct parse first
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    # Try extracting from ```json ... ``` blocks
    if "```" in raw:
        start = raw.find("```")
        end = raw.rfind("```")
        if start != end:
            inner = raw[start:end]
            # Remove the opening ``` line
            first_newline = inner.find("\n")
            if first_newline != -1:
                inner = inner[first_newline + 1:]
            try:
                return json.loads(inner.strip())
            except json.JSONDecodeError:
                pass

    # Last resort: find first { and last }
    brace_start = raw.find("{")
    brace_end = raw.rfind("}")
    if brace_start != -1 and brace_end != -1 and brace_end > brace_start:
        try:
            return json.loads(raw[brace_start : brace_end + 1])
        except json.JSONDecodeError:
            pass

    logger.error("Failed to parse LLM JSON response: %s", raw[:200])
    raise ValueError("LLM did not return valid JSON. Raw response logged.")

