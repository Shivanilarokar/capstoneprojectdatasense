type QueryFormProps = {
  question: string;
  onQuestionChange: (value: string) => void;
  onSubmit: () => void;
  isLoading: boolean;
};


export function QueryForm({ question, onQuestionChange, onSubmit, isLoading }: QueryFormProps) {
  return (
    <section className="panel query-form">
      <div className="query-form__intro">
        <div>
          <span className="eyebrow">Query</span>
          <h3>Ask one question.</h3>
          <p className="query-form__copy">The workspace routes it, answers it, and keeps the evidence beside it.</p>
        </div>
      </div>
      <div className="query-form__composer">
        <textarea
          className="query-form__input"
          value={question}
          onChange={(event) => onQuestionChange(event.target.value)}
          placeholder="Which suppliers appear exposed to sanctions or regulatory action?"
        />
        <div className="query-form__actions">
          <span className="query-form__hint">Role-aware routed answer</span>
          <button className="primary-button" onClick={onSubmit} disabled={isLoading || !question.trim()}>
            {isLoading ? "Thinking..." : "Send"}
          </button>
        </div>
      </div>
    </section>
  );
}
