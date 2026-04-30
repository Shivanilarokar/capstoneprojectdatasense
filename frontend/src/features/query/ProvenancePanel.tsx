import type { QueryResponse } from "../../lib/types";


type ProvenancePanelProps = {
  result: QueryResponse | null;
};


export function ProvenancePanel({ result }: ProvenancePanelProps) {
  return (
    <aside className="panel provenance-panel">
      <div className="panel__header">
        <div>
          <span className="eyebrow">Provenance</span>
          <h3>Route plan</h3>
        </div>
      </div>
      <pre>{JSON.stringify(result?.route_plan ?? { pipeline: "pending" }, null, 2)}</pre>
      <div className="provenance-panel__meta">
        <p>Graph stats</p>
        <pre>{JSON.stringify(result?.answer_graph?.stats ?? { node_count: 0, edge_count: 0, routes: [] }, null, 2)}</pre>
      </div>
      <div className="provenance-panel__meta">
        <p>Routes executed</p>
        <pre>{JSON.stringify(result?.routes_executed ?? [], null, 2)}</pre>
      </div>
      <div className="provenance-panel__meta">
        <p>Citations</p>
        <pre>{JSON.stringify(result?.citations ?? [], null, 2)}</pre>
      </div>
    </aside>
  );
}
