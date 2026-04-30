import { createBrowserRouter } from "react-router-dom";

import { AppFrame } from "../app/layout/AppFrame";
import { AdminPage } from "../features/admin/AdminPage";
import { AuthCallbackPage } from "../features/auth/AuthCallbackPage";
import { RequireAdmin } from "../features/auth/RequireAdmin";
import { RequireAuth } from "../features/auth/RequireAuth";
import { RequireRoles } from "../features/auth/RequireRoles";
import { SignInPage } from "../features/auth/SignInPage";
import { LandingPage } from "../features/landing/LandingPage";
import { QueryPage } from "../features/query/QueryPage";
import { WORKSPACE_ROLES } from "../lib/auth";


export const router = createBrowserRouter([
  {
    path: "/",
    element: <LandingPage />,
  },
  {
    path: "/signin",
    element: <SignInPage />,
  },
  {
    path: "/auth/callback",
    element: <AuthCallbackPage />,
  },
  {
    element: <RequireAuth />,
    children: [
      {
        element: <AppFrame />,
        children: [
          {
            path: "query",
            element: <RequireRoles allowedRoles={WORKSPACE_ROLES} redirectTo="/signin" />,
            children: [{ index: true, element: <QueryPage /> }],
          },
          {
            path: "admin",
            element: <RequireAdmin />,
            children: [{ index: true, element: <AdminPage /> }],
          },
        ],
      },
    ],
  },
]);
