import { Outlet } from "react-router-dom";

import { AppShell } from "./AppShell";

export function AppFrame() {
  return (
    <AppShell>
      <Outlet />
    </AppShell>
  );
}
