import { RequireRoles } from "./RequireRoles";


export function RequireAdmin() {
  return <RequireRoles allowedRoles={["admin"]} redirectTo="/query" />;
}
