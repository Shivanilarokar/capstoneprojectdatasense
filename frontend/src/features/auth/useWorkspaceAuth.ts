import { useEffect, useState } from "react";

import {
  clearLocalAuthSession,
  readLocalAuthSession,
  subscribeLocalAuthSession,
  type LocalAuthProfile,
} from "../../lib/localAuth";
import { resolveApiBaseUrl } from "../../lib/apiBase";

type WorkspaceUser = {
  access_token: string;
  profile: LocalAuthProfile;
};

type WorkspaceSigninArgs = {
  state?: unknown;
};

function normalizeReturnTo(value: string | undefined): string {
  const normalized = (value ?? "").trim();
  if (!normalized.startsWith("/") || normalized.startsWith("//")) {
    return "/query";
  }
  return normalized;
}


function resolveReturnTo(state: unknown): string {
  if (state && typeof state === "object" && "returnTo" in state) {
    return normalizeReturnTo(String(state.returnTo ?? ""));
  }
  return "/query";
}


function buildGoogleLoginUrl(returnTo: string): string {
  const url = new URL("/google/login", resolveApiBaseUrl());
  url.searchParams.set("return_to", returnTo);
  return url.toString();
}


export function useWorkspaceAuth() {
  const [localSession, setLocalSession] = useState(() => readLocalAuthSession());

  useEffect(() => subscribeLocalAuthSession(() => setLocalSession(readLocalAuthSession())), []);

  const user = localSession
    ? ({
        access_token: localSession.accessToken,
        profile: localSession.profile,
      } satisfies WorkspaceUser)
    : null;

  async function signinRedirect(args?: WorkspaceSigninArgs) {
    window.location.assign(buildGoogleLoginUrl(resolveReturnTo(args?.state)));
  }

  async function signoutRedirect() {
    if (localSession) {
      clearLocalAuthSession();
    }
    window.location.assign("/signin");
  }

  return {
    isAuthenticated: Boolean(localSession),
    isLoading: false,
    activeNavigator: undefined,
    user,
    signinRedirect,
    signoutRedirect,
  };
}
