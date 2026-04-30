import type { AdminTenantSummary } from "../../lib/types";


type TenantTableProps = {
  tenants: AdminTenantSummary[];
};


export function TenantTable({ tenants }: TenantTableProps) {
  return (
    <section className="panel">
      <div className="panel__header">
        <div>
          <span className="eyebrow">Tenant overview</span>
          <h3>Provisioned organizations</h3>
        </div>
      </div>
      <div className="tenant-table">
        <div className="tenant-table__row tenant-table__row--head">
          <span>Tenant</span>
          <span>Name</span>
          <span>Status</span>
          <span>Members</span>
          <span>Stores</span>
        </div>
        {(tenants.length > 0
          ? tenants
          : [{ tenant_key: "No tenants yet", display_name: "Awaiting provisioning", status: "pending", member_count: 0 }]).map((tenant, index) => (
          <div key={`${String(tenant.tenant_key ?? "tenant")}-${index}`} className="tenant-table__row">
            <span>{String(tenant.tenant_key ?? "n/a")}</span>
            <span>{String(tenant.display_name ?? "n/a")}</span>
            <span>{String(tenant.status ?? "unknown")}</span>
            <span>{String(tenant.member_count ?? 0)}</span>
            <span>{`${String(tenant.pg_database ?? "pg:n/a")} · ${String(tenant.neo4j_database ?? "neo4j:n/a")}`}</span>
          </div>
        ))}
      </div>
    </section>
  );
}
