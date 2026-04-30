from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from typing import Iterable


@dataclass(frozen=True)
class CurrentPrincipal:
    subject: str
    email: str
    roles: tuple[str, ...]
    tenant_key: str
    token_claims: dict[str, Any]

    def has_role(self, role: str) -> bool:
        return role in self.roles

    def has_any_role(self, roles: Iterable[str]) -> bool:
        return any(role in self.roles for role in roles)
