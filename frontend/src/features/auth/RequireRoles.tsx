import { Navigate, Outlet, useLocation } from "react-router-dom";

import { hasAnyRole } from "../../lib/auth";
import { useWorkspaceAuth } from "./useWorkspaceAuth";


type RequireRolesProps = {
  allowedRoles: readonly string[];
  redirectTo?: string;
};


export function RequireRoles({ allowedRoles, redirectTo = "/query" }: RequireRolesProps) {
  const auth = useWorkspaceAuth();
  const location = useLocation();

  if (!hasAnyRole(auth.user?.profile, allowedRoles)) {
    return <Navigate to={redirectTo} replace state={{ deniedFrom: location.pathname }} />;
  }

  return <Outlet />;
}
