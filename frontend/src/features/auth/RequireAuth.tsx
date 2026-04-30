import { Navigate, Outlet, useLocation } from "react-router-dom";

import { useWorkspaceAuth } from "./useWorkspaceAuth";

export function RequireAuth() {
  const auth = useWorkspaceAuth();
  const location = useLocation();

  if (auth.isLoading || auth.activeNavigator) {
    return <div className="panel panel--centered">Authenticating workspace...</div>;
  }

  if (!auth.isAuthenticated) {
    return (
      <Navigate
        to="/signin"
        replace
        state={{ returnTo: `${location.pathname}${location.search}` }}
      />
    );
  }

  return <Outlet />;
}
