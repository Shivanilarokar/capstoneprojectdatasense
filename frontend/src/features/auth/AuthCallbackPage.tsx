import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import { readLocalAuthSession, storeLocalAuthSession } from "../../lib/localAuth";


function normalizeReturnTo(value: string | null | undefined): string {
  const normalized = (value ?? "").trim();
  if (!normalized.startsWith("/") || normalized.startsWith("//")) {
    return "/query";
  }
  return normalized;
}

export function AuthCallbackPage() {
  const navigate = useNavigate();
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const accessToken = params.get("access_token");
    if (accessToken) {
      try {
        storeLocalAuthSession(accessToken);
        navigate(normalizeReturnTo(params.get("return_to")), { replace: true });
      } catch {
        setError("Google sign-in returned an invalid access token.");
      }
      return;
    }

    const authError = params.get("error");
    if (authError) {
      setError(params.get("error_description") ?? authError);
      return;
    }

    if (readLocalAuthSession()) {
      navigate("/query", { replace: true });
      return;
    }

    setError("Sign-in callback did not include an access token.");
  }, [navigate]);

  if (error) {
    return <div className="panel panel--critical">Sign-in failed: {error}</div>;
  }

  return <div className="panel panel--centered">Completing sign-in...</div>;
}
