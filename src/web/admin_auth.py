from dataclasses import dataclass
from typing import Optional

@dataclass
class AdminAuthenticator:
    secret: Optional[str] = None

    def verify(self, token: str) -> bool:
        return bool(token) and (self.secret is None or token == self.secret)

def get_admin_authenticator(secret: Optional[str] = None) -> AdminAuthenticator:
    return AdminAuthenticator(secret=secret)

def verify_admin_access(token: str, secret: Optional[str] = None) -> bool:
    return get_admin_authenticator(secret).verify(token)
