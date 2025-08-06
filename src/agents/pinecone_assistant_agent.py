from dataclasses import dataclass
from typing import Any, Dict, List, Optional

@dataclass
class PineconeAssistantAgent:
    api_key: Optional[str] = None
    index: Optional[str] = None

    def query(self, text: str, top_k: int = 5) -> List[Dict[str, Any]]:
        return [{"text": text, "score": 1.0, "id": "stub"}]

    def upsert(self, items: List[Dict[str, Any]]) -> int:
        return len(items)
