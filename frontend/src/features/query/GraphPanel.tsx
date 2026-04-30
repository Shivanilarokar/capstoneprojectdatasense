import { useEffect, useRef, useState } from "react";
import CytoscapeComponent from "react-cytoscapejs";

import type { QueryResponse } from "../../lib/types";


type GraphPanelProps = {
  result: QueryResponse | null;
};


const layouts = {
  hierarchy: {
    name: "breadthfirst",
    directed: true,
    padding: 36,
    spacingFactor: 1.15,
    animate: false,
  },
  force: {
    name: "cose",
    fit: true,
    padding: 36,
    animate: false,
  },
} as const;


const stylesheet = [
  {
    selector: "node",
    style: {
      label: "data(label)",
      "text-wrap": "wrap",
      "text-max-width": 120,
      "font-size": 11,
      color: "#e6eef8",
      "text-valign": "center",
      "text-halign": "center",
      width: 48,
      height: 48,
      "background-color": "#1d4ed8",
      "border-width": 2,
      "border-color": "#93c5fd",
    },
  },
  {
    selector: 'node[kind = "company"]',
    style: {
      shape: "round-rectangle",
      width: 78,
      height: 42,
      "background-color": "#0f766e",
      "border-color": "#5eead4",
    },
  },
  {
    selector: 'node[kind = "supplier"]',
    style: {
      shape: "round-rectangle",
      width: 72,
      height: 38,
      "background-color": "#1d4ed8",
      "border-color": "#93c5fd",
    },
  },
  {
    selector: 'node[kind = "component"]',
    style: {
      shape: "diamond",
      "background-color": "#7c3aed",
      "border-color": "#c4b5fd",
    },
  },
  {
    selector: 'node[kind = "material"]',
    style: {
      shape: "hexagon",
      "background-color": "#b45309",
      "border-color": "#fcd34d",
    },
  },
  {
    selector: 'node[kind = "country"]',
    style: {
      shape: "ellipse",
      "background-color": "#0f766e",
      "border-color": "#99f6e4",
    },
  },
  {
    selector: 'node[kind = "hazard"]',
    style: {
      shape: "vee",
      "background-color": "#be123c",
      "border-color": "#fda4af",
    },
  },
  {
    selector: 'node[kind = "sanction_entity"], node[kind = "status"], node[kind = "regulatory_action"], node[kind = "filing_section"], node[kind = "commodity"]',
    style: {
      shape: "round-tag",
      "background-color": "#334155",
      "border-color": "#cbd5e1",
    },
  },
  {
    selector: "edge",
    style: {
      width: 2,
      "line-color": "#64748b",
      "target-arrow-color": "#64748b",
      "target-arrow-shape": "triangle",
      "curve-style": "bezier",
      label: "data(label)",
      "font-size": 9,
      color: "#cbd5e1",
      "text-background-color": "#0f172a",
      "text-background-opacity": 0.8,
      "text-background-padding": 2,
    },
  },
  {
    selector: 'edge[kind = "hazard"]',
    style: {
      "line-color": "#fb7185",
      "target-arrow-color": "#fb7185",
    },
  },
  {
    selector: 'edge[kind = "trade"]',
    style: {
      "line-color": "#22c55e",
      "target-arrow-color": "#22c55e",
    },
  },
  {
    selector: ":selected",
    style: {
      "overlay-color": "#f8fafc",
      "overlay-opacity": 0.08,
    },
  },
];


export function GraphPanel({ result }: GraphPanelProps) {
  const [layoutMode, setLayoutMode] = useState<keyof typeof layouts>("hierarchy");
  const cyRef = useRef<any>(null);
  const graph = result?.answer_graph;
  const hasGraph = Boolean(graph?.nodes?.length);
  const elements = graph
    ? (CytoscapeComponent as any).normalizeElements({
        nodes: graph.nodes,
        edges: graph.edges,
      })
    : [];

  useEffect(() => {
    if (!cyRef.current || !hasGraph) {
      return;
    }
    cyRef.current.layout(layouts[layoutMode]).run();
    cyRef.current.fit(undefined, 36);
  }, [hasGraph, layoutMode, result?.query_id]);

  if (!result) {
    return (
      <section className="panel graph-empty">
        <div>
          <h3>Supply Chain Graph</h3>
          <p>Run a query to render supplier, sanctions, trade, hazard, and cascade relationships here.</p>
        </div>
      </section>
    );
  }

  if (!hasGraph) {
    return (
      <section className="panel graph-empty">
        <div>
          <span className="eyebrow">Supply Chain Graph</span>
          <h3>No graph structure in this answer.</h3>
          <p>
            Ask a graph-oriented question like <code>Show tier-2 cascade exposure for ACME suppliers</code> or
            combine sanctions, regulatory, and cascade risk in one query.
          </p>
        </div>
      </section>
    );
  }

  return (
    <section className="panel graph-panel">
      <div className="panel__header">
        <div>
          <span className="eyebrow">Supply Chain Graph</span>
          <h3>Interactive evidence view</h3>
        </div>
        <div className="graph-panel__toolbar">
          <span className="graph-panel__stat">{graph?.stats.node_count} nodes</span>
          <span className="graph-panel__stat">{graph?.stats.edge_count} edges</span>
          <button
            type="button"
            className={layoutMode === "hierarchy" ? "secondary-button" : "ghost-button"}
            onClick={() => setLayoutMode("hierarchy")}
          >
            Hierarchy
          </button>
          <button
            type="button"
            className={layoutMode === "force" ? "secondary-button" : "ghost-button"}
            onClick={() => setLayoutMode("force")}
          >
            Force
          </button>
        </div>
      </div>

      <div className="graph-panel__canvas">
        <CytoscapeComponent
          elements={elements}
          layout={layouts[layoutMode]}
          stylesheet={stylesheet}
          style={{ width: "100%", height: "100%" }}
          cy={(cy: any) => {
            cyRef.current = cy;
            cy.fit(undefined, 36);
          }}
        />
      </div>

      <div className="graph-panel__legend">
        <span className="graph-panel__legend-item graph-panel__legend-item--company">Company</span>
        <span className="graph-panel__legend-item graph-panel__legend-item--supplier">Supplier</span>
        <span className="graph-panel__legend-item graph-panel__legend-item--component">Component</span>
        <span className="graph-panel__legend-item graph-panel__legend-item--material">Material</span>
        <span className="graph-panel__legend-item graph-panel__legend-item--hazard">Hazard</span>
      </div>
    </section>
  );
}
