import { useEffect, useState } from "react";

import { apiFetch } from "../../lib/api";
import { useWorkspaceAuth } from "../auth/useWorkspaceAuth";
import type {
  AdminAccessUpsertRequest,
  AdminOverviewResponse,
  AdminUserAccessSummary,
} from "../../lib/types";
import { AccessEditor, type AccessEditorDraft } from "./AccessEditor";
import { AccessTable } from "./AccessTable";
import { OverviewCards } from "./OverviewCards";
import { TenantTable } from "./TenantTable";

const emptyDraft: AccessEditorDraft = {
  email: "",
  display_name: "",
  tenant_key: "default",
  roles: [],
  status: "active",
  is_default: true,
};


export function AdminPage() {
  const auth = useWorkspaceAuth();
  const [overview, setOverview] = useState<AdminOverviewResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [draft, setDraft] = useState<AccessEditorDraft>(emptyDraft);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!auth.user?.access_token) {
      return;
    }

    async function loadOverview() {
      try {
        const response = await apiFetch<AdminOverviewResponse>("/admin/overview", auth.user!.access_token);
        setOverview(response);
        setDraft((current) =>
          current.email
            ? current
            : {
                ...emptyDraft,
                tenant_key:
                  response.tenants[0]?.tenant_key ??
                  String(auth.user?.profile.tenant_key ?? "default"),
              },
        );
      } catch (caught) {
        setError(caught instanceof Error ? caught.message : "Unknown admin error");
      }
    }

    void loadOverview();
  }, [auth.user]);

  if (error) {
    return <section className="panel panel--critical">Admin overview failed: {error}</section>;
  }

  function selectUser(user: AdminUserAccessSummary) {
    setDraft({
      email: user.email,
      display_name: user.display_name,
      tenant_key: user.tenant_key,
      roles: [...user.roles],
      status: user.status,
      is_default: user.is_default,
    });
  }

  function resetDraft() {
    setDraft({
      ...emptyDraft,
      tenant_key:
        overview?.tenants[0]?.tenant_key ??
        String(auth.user?.profile.tenant_key ?? "default"),
    });
    setError(null);
  }

  async function saveDraft() {
    if (!auth.user?.access_token) {
      return;
    }
    if (!draft.email.trim()) {
      setError("An email address is required.");
      return;
    }
    if (draft.roles.length === 0) {
      setError("Select at least one role.");
      return;
    }

    setSaving(true);
    setError(null);
    try {
      const payload: AdminAccessUpsertRequest = {
        display_name: draft.display_name,
        tenant_key: draft.tenant_key,
        roles: draft.roles,
        status: draft.status,
        is_default: draft.is_default,
      };
      const saved = await apiFetch<AdminUserAccessSummary>(
        `/admin/access/${encodeURIComponent(draft.email.trim().toLowerCase())}`,
        auth.user.access_token,
        {
          method: "PUT",
          body: JSON.stringify(payload),
        },
      );
      selectUser(saved);
      const refreshed = await apiFetch<AdminOverviewResponse>("/admin/overview", auth.user.access_token);
      setOverview(refreshed);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Failed to save access.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <section className="workspace-grid admin-page">
      <div className="workspace-grid__main">
        <OverviewCards
          status={overview?.status ?? "loading"}
          cards={overview?.cards ?? []}
          tenants={overview?.tenants ?? []}
        />
        <AccessTable users={overview?.users ?? []} onEdit={selectUser} />
        <TenantTable tenants={overview?.tenants ?? []} />
      </div>
      <AccessEditor
        draft={draft}
        availableRoles={overview?.available_roles ?? []}
        tenants={overview?.tenants ?? []}
        saving={saving}
        error={error}
        onChange={setDraft}
        onSubmit={() => void saveDraft()}
        onReset={resetDraft}
      />
    </section>
  );
}
