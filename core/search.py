"""
Web search layer for nutrition lookups.

Primary: DuckDuckGo (free, no API key).
The module returns a list of search result dicts with 'title', 'body', and 'href'.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

from config import SearchProvider, get_settings

logger = logging.getLogger(__name__)


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=15),
    retry=retry_if_exception_type(Exception),
    reraise=True,
)
async def search_nutrition(
    food_name: str,
    *,
    max_results: int = 5,
) -> list[dict[str, str]]:
    """
    Search the web for nutrition information about *food_name*.

    Returns up to *max_results* results, each with keys:
        title, body (snippet), href (source URL).
    """
    settings = get_settings()

    if settings.search_provider == SearchProvider.DUCKDUCKGO:
        return await _ddg_search(food_name, max_results=max_results)
    else:
        raise ValueError(f"Unsupported search provider: {settings.search_provider}")


async def _ddg_search(
    food_name: str,
    *,
    max_results: int = 5,
) -> list[dict[str, str]]:
    """Search DuckDuckGo for Indian-context nutrition data."""
    import os
    import ssl
    from duckduckgo_search import DDGS  # type: ignore[import-untyped]

    # Ensure corporate CA certs are trusted for the search HTTP calls.
    # Set env vars *and* build a permissive SSL context so that primp/httpx
    # underlying the DDGS client can negotiate through corporate proxies
    # whose certs lack the Authority Key Identifier extension.
    settings = get_settings()
    ca_bundle = settings.ca_bundle_path
    if ca_bundle:
        os.environ["SSL_CERT_FILE"] = ca_bundle
        os.environ["REQUESTS_CA_BUNDLE"] = ca_bundle
        os.environ["CURL_CA_BUNDLE"] = ca_bundle

    query = f"{food_name} nutrition calories protein per serving India"

    def _do_search() -> list[dict[str, Any]]:
        with DDGS(verify=False) as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
        return results

    loop = asyncio.get_event_loop()
    raw_results = await loop.run_in_executor(None, _do_search)

    cleaned: list[dict[str, str]] = []
    for r in raw_results:
        cleaned.append({
            "title": r.get("title", ""),
            "body": r.get("body", r.get("snippet", "")),
            "href": r.get("href", r.get("link", "")),
        })

    logger.info("DDG search for '%s' returned %d results", food_name, len(cleaned))
    return cleaned


def format_search_results(results: list[dict[str, str]]) -> str:
    """
    Flatten search results into a text block suitable for LLM consumption.
    """
    if not results:
        return "No search results found."

    parts: list[str] = []
    for i, r in enumerate(results, 1):
        parts.append(
            f"[{i}] {r['title']}\n{r['body']}\nSource: {r['href']}"
        )
    return "\n\n".join(parts)

