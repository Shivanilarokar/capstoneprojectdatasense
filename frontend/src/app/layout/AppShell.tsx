import type { PropsWithChildren } from "react";

import { Header } from "./Header";
import { Sidebar } from "./Sidebar";


export function AppShell({ children }: PropsWithChildren) {
  return (
    <div className="app-shell">
      <Sidebar />
      <div className="app-shell__main">
        <Header />
        <main className="app-shell__content">{children}</main>
      </div>
    </div>
  );
}
