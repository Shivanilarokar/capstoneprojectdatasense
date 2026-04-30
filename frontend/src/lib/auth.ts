type OidcProfile = Record<string, unknown> | undefined;

export const WORKSPACE_ROLES = ["admin", "analyst", "supplychain_manager", "vp"] as const;

export type WorkspaceRole = (typeof WORKSPACE_ROLES)[number];


export function getRoleClaims(profile: OidcProfile): string[] {
  const raw = profile?.roles;
  if (Array.isArray(raw)) {
    const roles = raw.map((role) => String(role).trim()).filter(Boolean);
    return Array.from(new Set(roles));
  }
  if (typeof raw === "string" && raw.trim()) {
    return [raw];
  }
  return [];
}


export function hasAnyRole(profile: OidcProfile, allowedRoles: readonly string[]): boolean {
  const roles = getRoleClaims(profile);
  return allowedRoles.some((role) => roles.includes(role));
}


export function formatRoleLabel(role: string): string {
  switch (role) {
    case "supplychain_manager":
      return "Supplychain Manager";
    case "vp":
      return "VP";
    case "admin":
      return "Admin";
    case "analyst":
      return "Analyst";
    default:
      return role.replaceAll("_", " ");
  }
}
