import type { AdminMetricCard, AdminTenantSummary } from "../../lib/types";


type OverviewCardsProps = {
  status: string;
  cards: AdminMetricCard[];
  tenants: AdminTenantSummary[];
};


const defaults = (status: string, tenants: AdminTenantSummary[]) => [
  { label: "System", value: status.toUpperCase() },
  { label: "Tenants", value: String(tenants.length) },
  { label: "Queries", value: "0" },
];


export function OverviewCards({ status, cards, tenants }: OverviewCardsProps) {
  const rendered = cards.length > 0 ? cards : defaults(status, tenants);

  return (
    <section className="admin-cards">
      {rendered.map((card, index) => (
        <article key={`${String(card.label ?? "card")}-${index}`} className="panel admin-card">
          <span className="eyebrow">{String(card.label ?? "Metric")}</span>
          <h3>{String(card.value ?? "0")}</h3>
        </article>
      ))}
    </section>
  );
}
