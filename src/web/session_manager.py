from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Optional

@dataclass
class SessionData:
    user_id: str
    is_admin: bool = False

class SessionManager:
    def __init__(self) -> None:
        self._sessions: Dict[str, SessionData] = {}

    def create(self, session_id: str, user_id: str, is_admin: bool = False) -> SessionData:
        data = SessionData(user_id=user_id, is_admin=is_admin)
        self._sessions[session_id] = data
        return data

    def get(self, session_id: str) -> Optional[SessionData]:
        return self._sessions.get(session_id)

_GLOBAL_SM: Optional[SessionManager] = None
def get_session_manager() -> SessionManager:
    global _GLOBAL_SM
    if _GLOBAL_SM is None:
        _GLOBAL_SM = SessionManager()
    return _GLOBAL_SM
