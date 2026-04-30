import { formatRoleLabel } from "../../lib/auth";
import type { AdminUserAccessSummary } from "../../lib/types";


type AccessTableProps = {
  users: AdminUserAccessSummary[];
  onEdit: (user: AdminUserAccessSummary) => void;
};


export function AccessTable({ users, onEdit }: AccessTableProps) {
  return (
    <section className="panel">
      <div className="panel__header">
        <div>
          <span className="eyebrow">Access matrix</span>
          <h3>Users and roles</h3>
        </div>
      </div>
      <div className="access-table">
        <div className="access-table__row access-table__row--head">
          <span>User</span>
          <span>Tenant</span>
          <span>Roles</span>
          <span>Status</span>
          <span>Action</span>
        </div>
        {(users.length > 0
          ? users
          : [
              {
                email: "No users provisioned",
                display_name: "Create the first assignment from the panel on the right.",
                provider_subject: "",
                tenant_key: "default",
                roles: [],
                status: "pending",
                is_default: false,
                last_login_at: null,
              },
            ]).map((user) => (
          <div key={`${user.email}-${user.tenant_key}`} className="access-table__row">
            <div className="access-table__identity">
              <strong>{user.display_name}</strong>
              <small>{user.email}</small>
            </div>
            <div className="access-table__tenant">
              <span>{user.tenant_key}</span>
              {user.is_default ? <small>Default tenant</small> : null}
            </div>
            <div className="access-role-list">
              {user.roles.length > 0 ? (
                user.roles.map((role) => (
                  <span key={`${user.email}-${user.tenant_key}-${role}`} className="access-role-pill">
                    {formatRoleLabel(role)}
                  </span>
                ))
              ) : (
                <span className="access-role-pill access-role-pill--muted">No roles</span>
              )}
            </div>
            <span className={`status-pill status-pill--${user.status}`}>{user.status}</span>
            <div className="access-table__action">
              <button className="ghost-button" type="button" onClick={() => onEdit(user)}>
                Edit
              </button>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}
