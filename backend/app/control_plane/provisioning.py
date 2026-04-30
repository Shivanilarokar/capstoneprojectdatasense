from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class TenantProvisioningPlan:
    tenant_key: str
    postgres_database: str
    neo4j_database: str


def build_tenant_provisioning_plan(tenant_key: str) -> TenantProvisioningPlan:
    slug = re.sub(r"[^a-z0-9]+", "_", tenant_key.strip().lower()).strip("_") or "tenant"
    return TenantProvisioningPlan(
        tenant_key=tenant_key,
        postgres_database=f"tenant_{slug}",
        neo4j_database=f"tenant-{slug}",
    )
