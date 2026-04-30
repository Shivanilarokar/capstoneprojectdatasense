import type { QueryResponse } from "../../lib/types";


type AnswerPanelProps = {
  result: QueryResponse | null;
  error: string | null;
};


export function AnswerPanel({ result, error }: AnswerPanelProps) {
  if (error) {
    return <section className="panel panel--critical">Query failed: {error}</section>;
  }

  if (!result) {
    return (
      <section className="panel panel--empty">
        <h3>No answer yet.</h3>
        <p>Start with a question in the composer above.</p>
      </section>
    );
  }

  return (
    <section className="panel answer-panel">
      <div className="panel__header">
        <div>
          <span className="eyebrow">Response</span>
          <h3>{result.question}</h3>
        </div>
        <div className="answer-panel__chips">
          {(result.routes_executed ?? []).map((route) => (
            <span key={route} className="chip">
              {route}
            </span>
          ))}
        </div>
      </div>
      <p className="answer-panel__body">{result.answer}</p>
      {result.warnings.length > 0 ? (
        <div className="answer-panel__warnings">
          {result.warnings.map((warning) => (
            <p key={warning}>{warning}</p>
          ))}
        </div>
      ) : null}
      <footer className="answer-panel__footer">
        <span>Pipeline: {result.selected_pipeline}</span>
        <span>Query ID: {result.query_id ?? "pending"}</span>
      </footer>
    </section>
  );
}
