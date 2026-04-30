from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ClassificationResult:
    route: str
    reason: str
    preferred_tables: list[str]


def classify_question(question: str) -> ClassificationResult:
    text = question.lower()

    has_fda = any(token in text for token in ("fda", "warning letter", "warning letters", "issuing office"))
    has_sanctions = any(token in text for token in ("ofac", "sdn", "sanction", "sanctions program"))
    has_weather = any(token in text for token in ("storm", "damage", "hurricane", "weather", "event"))
    has_trade = any(token in text for token in ("trade", "export", "import", "reporter", "partner", "hs code"))

    if has_fda and has_sanctions:
        return ClassificationResult(
            route="cross_source",
            reason="matched cross-source FDA and sanctions keywords",
            preferred_tables=["source_fda_warning_letters", "source_ofac_sdn_entities"],
        )
    if has_weather:
        return ClassificationResult(
            route="weather",
            reason="matched weather keywords",
            preferred_tables=["source_noaa_storm_events"],
        )
    if has_trade:
        return ClassificationResult(
            route="trade",
            reason="matched trade keywords",
            preferred_tables=["source_comtrade_flows"],
        )
    if has_fda:
        return ClassificationResult(
            route="fda",
            reason="matched FDA keywords",
            preferred_tables=["source_fda_warning_letters"],
        )
    if has_sanctions:
        return ClassificationResult(
            route="sanctions",
            reason="matched sanctions keywords",
            preferred_tables=["source_ofac_sdn_entities"],
        )
    return ClassificationResult(
        route="unsupported",
        reason="no strong route keywords matched",
        preferred_tables=[],
    )


