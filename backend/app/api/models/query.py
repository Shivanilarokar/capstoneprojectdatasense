from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class QueryRequest(BaseModel):
    question: str


class QueryResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    status: str = "ok"
    question: str
    answer: str
    selected_pipeline: str
    route_plan: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    query_id: str = ""
    routes_executed: list[str] = Field(default_factory=list)
    route_results: dict[str, Any] = Field(default_factory=dict)
    filtered_route_results: dict[str, Any] = Field(default_factory=dict)
    citations: list[str] = Field(default_factory=list)
    answer_graph: dict[str, Any] = Field(default_factory=dict)
