# PageIndex SEC 10-K Pipeline

## Run

```powershell
python .\run_pageindex_pipeline.py --docs-only
python .\run_pageindex_pipeline.py --reindex --index-model gpt-4.1-mini
python .\run_pageindex_pipeline.py --question "What supply chain risk factors are disclosed in Apple's latest 10-K?"
```

Default artifact paths:
- `data/pageindex/docs`
- `data/pageindex/workspace`
- `data/pageindex/output`

## Keys

- `PAGEINDEX_API_KEY` is required for PageIndex SDK indexing/retrieval.
- `OPENAI_API_KEY` is required for LLM reasoning stages (routing + recursive tree search + answer generation).

## Module Layout

- `models.py`: SEC record dataclass
- `sec_markdown.py`: SEC item clipping + subsection shaping + markdown materialization
- `sdk_loader.py`: installed PageIndex SDK loader + cloud adapter
- `tree_search.py`: doc routing + recursive tree search + evidence extraction
- `pipeline.py`: orchestration
- `cli.py`: CLI
