export type GraphNode = {
  data: {
    id: string;
    label: string;
    kind?: string;
    route?: string;
    subtitle?: string;
  };
};

export type GraphEdge = {
  data: {
    id: string;
    source: string;
    target: string;
    label?: string;
    kind?: string;
    route?: string;
  };
};

export type AnswerGraph = {
  query_id: string;
  mode: string;
  nodes: GraphNode[];
  edges: GraphEdge[];
  stats: {
    node_count: number;
    edge_count: number;
    routes: string[];
  };
};

export type QueryResponse = {
  status: string;
  question: string;
  answer: string;
  selected_pipeline: string;
  route_plan: Record<string, unknown>;
  warnings: string[];
  query_id?: string;
  routes_executed?: string[];
  route_results?: Record<string, unknown>;
  filtered_route_results?: Record<string, unknown>;
  provenance?: Record<string, unknown>;
  citations?: string[];
  answer_graph?: AnswerGraph;
};

export type AdminMetricCard = {
  label: string;
  value: string;
};

export type AdminTenantSummary = {
  tenant_key: string;
  display_name: string;
  status: string;
  member_count: number;
  pg_database?: string | null;
  neo4j_database?: string | null;
};

export type AdminUserAccessSummary = {
  email: string;
  display_name: string;
  provider_subject: string;
  tenant_key: string;
  roles: string[];
  status: string;
  is_default: boolean;
  last_login_at?: string | null;
};

export type AdminAccessUpsertRequest = {
  display_name: string;
  tenant_key: string;
  roles: string[];
  status: string;
  is_default: boolean;
};

export type AdminOverviewResponse = {
  status: string;
  cards: AdminMetricCard[];
  tenants: AdminTenantSummary[];
  users: AdminUserAccessSummary[];
  available_roles: string[];
};
