import { useEffect, useMemo, useState } from "react";
import { useLocation } from "react-router-dom";

import { formatRoleLabel, getRoleClaims } from "../../lib/auth";
import { publicFetch } from "../../lib/publicApi";
import { useWorkspaceAuth } from "../../features/auth/useWorkspaceAuth";


const titles: Record<string, { title: string; subtitle: string }> = {
  "/query": {
    title: "Query",
    subtitle: "Ask, review the answer, inspect the evidence.",
  },
  "/admin": {
    title: "Admin",
    subtitle: "Manage users, roles, and tenant access.",
  },
};


function claimText(value: unknown, fallback: string) {
  return typeof value === "string" && value.trim() ? value : fallback;
}


export function Header() {
  const auth = useWorkspaceAuth();
  const location = useLocation();
  const [healthStatus, setHealthStatus] = useState("checking");
  const copy = useMemo(
    () =>
      titles[location.pathname] ?? {
        title: "SupplyChainNexus",
        subtitle: "Role-based supply chain workspace.",
      },
    [location.pathname],
  );

  useEffect(() => {
    let cancelled = false;
    publicFetch<{ status: string }>("/health")
      .then((response) => {
        if (!cancelled) {
          setHealthStatus(response.status);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setHealthStatus("down");
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const email = claimText(auth.user?.profile.email, claimText(auth.user?.profile.preferred_username, "Signed in"));
  const subject = claimText(auth.user?.profile.sub, "External user");
  const tenantKey = claimText(auth.user?.profile.tenant_key, "default");
  const roles = getRoleClaims(auth.user?.profile);
  const roleSummary = roles.length > 0 ? roles.map(formatRoleLabel).join(", ") : subject;

  return (
    <header className="app-header">
      <div className="app-header__copy">
        <p className="app-header__eyebrow">Workspace</p>
        <h2>{copy.title}</h2>
        <p className="app-header__subtitle">{copy.subtitle}</p>
      </div>
      <div className="app-header__actions">
        <div className="app-header__meta">
          <span>{email}</span>
          <small>{roleSummary} · {tenantKey}</small>
        </div>
        <span className={`status-pill ${healthStatus === "ok" ? "status-pill--active" : "status-pill--pending"}`}>
          API {healthStatus}
        </span>
        <button className="ghost-button" onClick={() => void auth.signoutRedirect()}>
          Sign out
        </button>
      </div>
    </header>
  );
}
