from __future__ import annotations


def test_backend_package_imports() -> None:
    from backend.config import load_app_config
    from backend.generation.generation import LLMConfig
    from backend.observability.logging import emit_trace_event

    assert callable(load_app_config)
    assert LLMConfig.__name__ == "LLMConfig"
    assert callable(emit_trace_event)



