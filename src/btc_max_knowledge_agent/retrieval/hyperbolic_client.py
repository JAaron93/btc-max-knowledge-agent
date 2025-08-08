import logging
from typing import Any, Dict, List, Optional

import aiohttp

from btc_max_knowledge_agent.utils.config import Config

logger = logging.getLogger(__name__)


class HyperbolicClient:
    """Minimal client for Hyperbolic AI GPT-OSS 120B.

    Provides:
    - generate(): chat completion using a simple OpenAI-like schema
    - search(): placeholder for future retrieval integration
    """

    def __init__(
        self, api_key: Optional[str] = None, base_url: Optional[str] = None
    ) -> None:
        Config.validate()
        self.api_key = api_key or Config.HYPERBOLIC_API_KEY
        default_base = "https://api.hyperbolic-ai.xyz"
        # Prefer provided base_url, then .env override, else default
        self.base_url = base_url or Config.HYPERBOLIC_API_BASE or default_base
        self.model = Config.HYPERBOLIC_MODEL

    async def _post_json(self, path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        base = self.base_url.rstrip("/")
        sub = path.lstrip("/")
        url = f"{base}/{sub}"
        auth_header = f"Bearer {self.api_key}"
        headers = {
            "Authorization": auth_header,
            "Content-Type": "application/json",
        }
        timeout = aiohttp.ClientTimeout(total=60)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(url, json=payload, headers=headers) as resp:
                if resp.status >= 400:
                    text = await resp.text()
                    logger.error(
                        "Hyperbolic API error %s: %s",
                        resp.status,
                        text,
                    )
                    raise RuntimeError(
                        f"Hyperbolic API error {resp.status}: {text}"
                    )
                return await resp.json()

    async def generate(
        self,
        prompt: str,
        *,
        max_tokens: int = 512,
        temperature: float = 0.3,
        system_prompt: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Generate a completion from GPT-OSS 120B.

        Returns: { response: str, model: str, usage: dict }
        """
        messages: List[Dict[str, str]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        data = await self._post_json("v1/chat/completions", payload)

        text = ""
        try:
            # OpenAI-like schema compatibility
            text = data["choices"][0]["message"]["content"]
        except Exception:  # noqa: BLE001
            text = str(data)

        return {
            "response": text,
            "model": data.get("model", self.model),
            "usage": data.get("usage", {}),
        }

    async def search(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """Placeholder for RAG search with Hyperbolic components.

        For now, returns an empty list.
        """
        logger.info(
            "Hyperbolic search placeholder called: %s (top_k=%d)", query, top_k
        )
        return []


