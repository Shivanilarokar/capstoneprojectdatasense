import { formatRoleLabel } from "../../lib/auth";
import type { AdminTenantSummary } from "../../lib/types";


export type AccessEditorDraft = {
  email: string;
  display_name: string;
  tenant_key: string;
  roles: string[];
  status: string;
  is_default: boolean;
};

type AccessEditorProps = {
  draft: AccessEditorDraft;
  availableRoles: string[];
  tenants: AdminTenantSummary[];
  saving: boolean;
  error: string | null;
  onChange: (draft: AccessEditorDraft) => void;
  onSubmit: () => void;
  onReset: () => void;
};


export function AccessEditor({
  draft,
  availableRoles,
  tenants,
  saving,
  error,
  onChange,
  onSubmit,
  onReset,
}: AccessEditorProps) {
  function toggleRole(role: string) {
    const nextRoles = draft.roles.includes(role)
      ? draft.roles.filter((value) => value !== role)
      : [...draft.roles, role];
    onChange({ ...draft, roles: nextRoles });
  }

  return (
    <aside className="panel">
      <div className="panel__header">
        <div>
          <span className="eyebrow">Access editor</span>
          <h3>Assign roles</h3>
        </div>
      </div>

      <div className="admin-form">
        <label className="admin-field">
          <span>Email</span>
          <input
            className="admin-input"
            type="email"
            value={draft.email}
            onChange={(event) => onChange({ ...draft, email: event.target.value })}
            placeholder="name@company.com"
          />
        </label>

        <label className="admin-field">
          <span>Display name</span>
          <input
            className="admin-input"
            type="text"
            value={draft.display_name}
            onChange={(event) => onChange({ ...draft, display_name: event.target.value })}
            placeholder="Team member name"
          />
        </label>

        <label className="admin-field">
          <span>Tenant key</span>
          <input
            className="admin-input"
            type="text"
            list="tenant-suggestions"
            value={draft.tenant_key}
            onChange={(event) => onChange({ ...draft, tenant_key: event.target.value })}
            placeholder="tenant-acme"
          />
          <datalist id="tenant-suggestions">
            {tenants.map((tenant) => (
              <option key={tenant.tenant_key} value={tenant.tenant_key} />
            ))}
          </datalist>
        </label>

        <label className="admin-field">
          <span>Status</span>
          <select
            className="admin-input"
            value={draft.status}
            onChange={(event) => onChange({ ...draft, status: event.target.value })}
          >
            <option value="active">Active</option>
            <option value="suspended">Suspended</option>
          </select>
        </label>

        <div className="admin-field">
          <span>Roles</span>
          <div className="role-toggle-grid">
            {availableRoles.map((role) => (
              <label key={role} className="role-toggle">
                <input
                  type="checkbox"
                  checked={draft.roles.includes(role)}
                  onChange={() => toggleRole(role)}
                />
                <div>
                  <strong>{formatRoleLabel(role)}</strong>
                  <small>{role}</small>
                </div>
              </label>
            ))}
          </div>
        </div>

        <label className="admin-checkbox">
          <input
            type="checkbox"
            checked={draft.is_default}
            onChange={(event) => onChange({ ...draft, is_default: event.target.checked })}
          />
          <span>Set as default tenant for this user</span>
        </label>

        {error ? <div className="admin-inline-error">{error}</div> : null}

        <div className="admin-form__actions">
          <button className="primary-button" type="button" onClick={onSubmit} disabled={saving}>
            {saving ? "Saving..." : "Save access"}
          </button>
          <button className="secondary-button" type="button" onClick={onReset}>
            Reset
          </button>
        </div>
      </div>
    </aside>
  );
}
