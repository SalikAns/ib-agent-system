"""
IB AI Agent System — AI Engine

3-tier AI cascade: Gemini → Groq → Ollama with LRU caching and quota tracking.
"""

from __future__ import annotations

import hashlib
import time
from typing import Any, Dict, Optional

import httpx
from cachetools import LRUCache
from tenacity import retry, stop_after_attempt, wait_exponential

from config import settings
from database import get_quota_today, increment_quota


class QuotaTracker:
    """Track daily API usage per provider against conservative limits."""

    gemini_limit: int = 950
    groq_limit: int = 95

    async def is_available(self, provider: str) -> bool:
        """Check whether a provider still has quota for today."""
        count = await get_quota_today(provider)
        if provider == "gemini":
            return count < self.gemini_limit
        if provider == "groq":
            return count < self.groq_limit
        return True

    async def log_usage(self, provider: str, tokens: int = 0) -> None:
        """Record one API call for a provider."""
        await increment_quota(provider, tokens)


class AIEngine:
    """3-tier AI engine with caching, quota management, and retries."""

    def __init__(self) -> None:
        self._cache: LRUCache = LRUCache(maxsize=100)
        self._quota = QuotaTracker()
        self._gemini_client: Any = None
        self._groq_client: Any = None
        self._ollama_client: Optional[httpx.AsyncClient] = None
        self._providers_ready: Dict[str, bool] = {
            "gemini": False,
            "groq": False,
            "ollama": False,
        }

    async def _init_gemini(self) -> bool:
        """Initialize the Gemini client."""
        try:
            import google.generativeai as genai

            genai.configure(api_key=settings.gemini_api_key)
            self._gemini_client = genai.GenerativeModel("gemini-1.5-flash")
            return True
        except Exception:
            return False

    async def _init_groq(self) -> bool:
        """Initialize the Groq client."""
        if not settings.groq_api_key:
            return False
        try:
            from groq import AsyncGroq

            self._groq_client = AsyncGroq(api_key=settings.groq_api_key)
            return True
        except Exception:
            return False

    async def _init_ollama(self) -> bool:
        """Initialize the Ollama httpx client."""
        if not settings.ollama_url:
            return False
        try:
            self._ollama_client = httpx.AsyncClient(
                base_url=settings.ollama_url, timeout=60.0
            )
            return True
        except Exception:
            return False

    async def warmup(self) -> Dict[str, bool]:
        """Ping each provider and report availability."""
        self._providers_ready["gemini"] = await self._init_gemini()
        self._providers_ready["groq"] = await self._init_groq()
        self._providers_ready["ollama"] = await self._init_ollama()

        results: Dict[str, bool] = {}
        for provider, ready in self._providers_ready.items():
            if not ready:
                results[provider] = False
                continue
            try:
                test = await self._call_provider(provider, "Reply with exactly: OK")
                results[provider] = "OK" in test or len(test.strip()) > 0
            except Exception:
                results[provider] = False

        return results

    def _cache_key(self, prompt: str, context: Optional[str] = None) -> str:
        """Generate a deterministic cache key from prompt + context."""
        raw = f"{prompt}|{context or ''}"
        return hashlib.sha256(raw.encode()).hexdigest()

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
    )
    async def _call_gemini(self, prompt: str, context: Optional[str] = None) -> str:
        """Call Gemini 1.5 Flash."""
        import google.generativeai as genai

        generation_config = genai.GenerationConfig(
            temperature=0.7,
            max_output_tokens=4096,
        )

        if context:
            model = genai.GenerativeModel(
                "gemini-1.5-flash",
                system_instruction=context,
                generation_config=generation_config,
            )
        else:
            model = genai.GenerativeModel(
                "gemini-1.5-flash",
                generation_config=generation_config,
            )

        response = await model.generate_content_async(prompt)
        return response.text

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
    )
    async def _call_groq(self, prompt: str, context: Optional[str] = None) -> str:
        """Call Groq Llama 3."""
        messages = []
        if context:
            messages.append({"role": "system", "content": context})
        messages.append({"role": "user", "content": prompt})

        response = await self._groq_client.chat.completions.create(
            model="llama3-8b-8192",
            messages=messages,
            temperature=0.7,
            max_tokens=4096,
        )
        return response.choices[0].message.content

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
    )
    async def _call_ollama(self, prompt: str, context: Optional[str] = None) -> str:
        """Call Ollama via httpx."""
        full_prompt = f"{context}\n\n{prompt}" if context else prompt
        response = await self._ollama_client.post(
            "/api/generate",
            json={
                "model": "llama3",
                "prompt": full_prompt,
                "stream": False,
                "options": {"temperature": 0.7},
            },
        )
        response.raise_for_status()
        data = response.json()
        return data.get("response", "")

    async def _call_provider(
        self, provider: str, prompt: str, context: Optional[str] = None
    ) -> str:
        """Route a call to the appropriate provider."""
        if provider == "gemini":
            return await self._call_gemini(prompt, context)
        if provider == "groq":
            return await self._call_groq(prompt, context)
        if provider == "ollama":
            return await self._call_ollama(prompt, context)
        raise ValueError(f"Unknown provider: {provider}")

    async def generate(
        self,
        prompt: str,
        context: Optional[str] = None,
        prefer_fast: bool = False,
    ) -> str:
        """
        Generate a response using the 3-tier cascade.

        Tier 1: Gemini 1.5 Flash (skip if prefer_fast or quota >= 950)
        Tier 2: Groq Llama 3 (skip if quota >= 95)
        Tier 3: Ollama (only if ollama_url is configured)
        Fallback: capacity message
        """
        key = self._cache_key(prompt, context)
        if key in self._cache:
            return self._cache[key]

        tiers = []
        if self._providers_ready.get("gemini") and not prefer_fast:
            tiers.append(("gemini", "gemini"))
        if self._providers_ready.get("groq"):
            tiers.append(("groq", "groq"))
        if self._providers_ready.get("ollama"):
            tiers.append(("ollama", "ollama"))

        for provider, quota_provider in tiers:
            if not await self._quota.is_available(quota_provider):
                continue
            try:
                start = time.monotonic()
                result = await self._call_provider(provider, prompt, context)
                elapsed_ms = int((time.monotonic() - start) * 1000)
                await self._quota.log_usage(quota_provider, tokens=len(result.split()))
                self._cache[key] = result
                return result
            except Exception:
                continue

        return "⏳ All AI providers at capacity. Resets at midnight UTC."

    async def health_status(self) -> Dict[str, Any]:
        """Return provider availability and today's quota counts."""
        quota_gemini = await get_quota_today("gemini")
        quota_groq = await get_quota_today("groq")
        quota_ollama = await get_quota_today("ollama")

        return {
            "providers": {
                "gemini": {
                    "online": self._providers_ready.get("gemini", False),
                    "quota_used": quota_gemini,
                    "quota_limit": QuotaTracker.gemini_limit,
                },
                "groq": {
                    "online": self._providers_ready.get("groq", False),
                    "quota_used": quota_groq,
                    "quota_limit": QuotaTracker.groq_limit,
                },
                "ollama": {
                    "online": self._providers_ready.get("ollama", False),
                    "quota_used": quota_ollama,
                    "quota_limit": None,
                },
            },
            "cache_size": len(self._cache),
            "cache_max": self._cache.maxsize,
        }


# Module-level singleton
ai_engine = AIEngine()
