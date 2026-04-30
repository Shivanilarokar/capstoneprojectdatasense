import { startTransition, useEffect, useState } from "react";

import { apiFetch } from "../../lib/api";
import { useWorkspaceAuth } from "../auth/useWorkspaceAuth";
import type { QueryResponse } from "../../lib/types";
import { AnswerPanel } from "./AnswerPanel";
import { GraphPanel } from "./GraphPanel";
import { ProvenancePanel } from "./ProvenancePanel";
import { QueryForm } from "./QueryForm";


export function QueryPage() {
  const auth = useWorkspaceAuth();
  const [question, setQuestion] = useState("Which suppliers appear exposed to sanctions or regulatory action?");
  const [result, setResult] = useState<QueryResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    const raw = window.sessionStorage.getItem("scn:last-query");
    if (!raw) {
      return;
    }
    try {
      const parsed = JSON.parse(raw) as QueryResponse;
      setResult(parsed);
      if (parsed.question) {
        setQuestion(parsed.question);
      }
    } catch {
      window.sessionStorage.removeItem("scn:last-query");
    }
  }, []);

  async function submit() {
    if (!auth.user?.access_token) {
      setError("Missing access token.");
      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      const data = await apiFetch<QueryResponse>("/query/ask", auth.user.access_token, {
        method: "POST",
        body: JSON.stringify({ question }),
      });
      startTransition(() => {
        window.sessionStorage.setItem("scn:last-query", JSON.stringify(data));
        setResult(data);
      });
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unknown error");
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <section className="workspace-grid query-page">
      <div className="workspace-grid__main">
        <QueryForm
          question={question}
          onQuestionChange={setQuestion}
          onSubmit={() => void submit()}
          isLoading={isLoading}
        />
        <AnswerPanel result={result} error={error} />
        <GraphPanel result={result} />
      </div>
      <ProvenancePanel result={result} />
    </section>
  );
}
