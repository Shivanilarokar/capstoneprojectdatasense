import { NavLink } from "react-router-dom";

import { formatRoleLabel, getRoleClaims } from "../../lib/auth";
import { useWorkspaceAuth } from "../../features/auth/useWorkspaceAuth";

const items = [
  { label: "Query", path: "/query", blurb: "Workspace", roles: ["admin", "analyst", "supplychain_manager", "vp"] },
  { label: "Admin", path: "/admin", blurb: "Access", roles: ["admin"] },
];


export function Sidebar() {
  const auth = useWorkspaceAuth();
  const roles = getRoleClaims(auth.user?.profile);
  const visibleItems = items.filter((item) => item.roles.some((role) => roles.includes(role)));

  return (
    <aside className="sidebar">
      <div className="sidebar__brand">
        <span className="sidebar__eyebrow">SupplyChainNexus</span>
        <h1>SupplyChainNexus</h1>
        <p>Routed queries and controlled access.</p>
      </div>
      <div className="sidebar__roles">
        {(roles.length > 0 ? roles : ["unassigned"]).map((role) => (
          <span key={role} className="sidebar__role-pill">
            {formatRoleLabel(role)}
          </span>
        ))}
      </div>
      <nav className="sidebar__nav" aria-label="Primary">
        {visibleItems.map((item) => (
          <NavLink
            key={item.path}
            to={item.path}
            className={({ isActive }) => (isActive ? "sidebar__link sidebar__link--active" : "sidebar__link")}
          >
            <span>{item.label}</span>
            <small>{item.blurb}</small>
          </NavLink>
        ))}
      </nav>
      <div className="sidebar__footer">
        <p>Google sign-in, tenant roles, app JWT.</p>
      </div>
    </aside>
  );
}
