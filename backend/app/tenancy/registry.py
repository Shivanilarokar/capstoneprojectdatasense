from __future__ import annotations

from backend.app.tenancy.context import TenantRuntimeContext


class TenantRuntimeRegistry:
    def __init__(self) -> None:
        self._contexts: dict[str, TenantRuntimeContext] = {}

    def register(self, context: TenantRuntimeContext) -> TenantRuntimeContext:
        self._contexts[context.tenant_key] = context
        return context

    def get(self, tenant_key: str) -> TenantRuntimeContext | None:
        return self._contexts.get(tenant_key)


tenant_runtime_registry = TenantRuntimeRegistry()
