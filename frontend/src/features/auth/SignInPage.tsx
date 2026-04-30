import { useLocation } from "react-router-dom";

import { useWorkspaceAuth } from "./useWorkspaceAuth";


function normalizeReturnTo(value: string | undefined) {
  const normalized = (value ?? "").trim();
  if (!normalized.startsWith("/") || normalized.startsWith("//")) {
    return "/query";
  }
  return normalized;
}


export function SignInPage() {
  const auth = useWorkspaceAuth();
  const location = useLocation();
  const returnTo = normalizeReturnTo(
    location.state && typeof location.state === "object" && "returnTo" in location.state
      ? String(location.state.returnTo ?? "")
      : "/query",
  );

  return (
    <section className="signin-page">
      <div className="signin-page__hero">
        <p className="eyebrow">Secure access</p>
        <h1>Sign in to the workspace.</h1>
        <p>
          Use your provisioned Google identity to open the query workspace or the admin dashboard.
        </p>
      </div>
      <div className="signin-card">
        <span className="signin-card__label">Sign in</span>
        <h2>Access is limited to Google identities provisioned for this workspace.</h2>
        <p>Admins assign roles in the control plane, then the app issues a tenant-scoped workspace token.</p>
        <button
          className="primary-button"
          onClick={() => void auth.signinRedirect({ state: { returnTo } })}
        >
          Continue with Google
        </button>
      </div>
    </section>
  );
}
