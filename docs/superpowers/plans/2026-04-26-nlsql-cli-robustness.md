# NL-SQL CLI Robustness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade the standalone NL-SQL route so it produces answer-first terminal output, uses stronger schema-grounded prompting, supports deterministic source classification, and handles simple FDA-to-OFAC cross-source joins safely.

**Architecture:** Keep the existing `question -> SQL generation -> validation -> execution -> answer synthesis` pipeline, but add deterministic classification, route-aware prompts, canonical join helpers, presentation formatting, and a text-first CLI. The LLM remains responsible for SQL generation and answer generation, while deterministic code constrains routing, joins, and rendering.

**Tech Stack:** Python, PostgreSQL, psycopg, OpenAI Responses API, unittest

---

## File Structure

- Modify: `src/nlsql/cli.py`
  - Switch default output from raw JSON to answer-first text and add `--debug`.
- Modify: `src/nlsql/query.py`
  - Orchestrate classification, helper-aware prompting, presentation formatting, and debug payload assembly.
- Modify: `src/nlsql/prompting.py`
  - Replace thin prompts with route-aware generation, repair, and answer prompts.
- Modify: `src/nlsql/openai_client.py`
  - Keep structured SQL generation and ensure answer generation returns text cleanly.
- Create: `src/nlsql/classifier.py`
  - Deterministic route classification and route metadata.
- Create: `src/nlsql/examples.py`
  - Few-shot SQL examples per route.
- Create: `src/nlsql/joins.py`
  - Canonical cross-source helper definitions and normalized-name expressions.
- Create: `src/nlsql/presentation.py`
  - Evidence formatting, number/date normalization, answer-first text rendering.
- Modify: `src/nlsql/schema_introspection.py`
  - Surface helper views or helper schemas in prompt-friendly order.
- Modify: `tests/nlsql/test_query.py`
  - Cover classifier-aware orchestration and cross-source helper usage.
- Create: `tests/nlsql/test_classifier.py`
  - Cover route selection.
- Create: `tests/nlsql/test_presentation.py`
  - Cover answer-first rendering and value formatting.
- Modify: `tests/nlsql/test_prompting.py`
  - Cover route-aware prompt examples and stronger answer prompt contract.
- Modify: `tests/nlsql/test_schema_introspection.py`
  - Cover helper-view/schema ordering if introduced.
- Modify: `tests/nlsql/test_validation.py`
  - Keep safety checks intact for helper-backed SQL.
- Modify: `README.md`
  - Update NL-SQL run command and debug mode documentation if needed.

### Task 1: Add Deterministic Classification

**Files:**
- Create: `src/nlsql/classifier.py`
- Test: `tests/nlsql/test_classifier.py`

- [ ] **Step 1: Write the failing tests**

```python
from unittest import TestCase

from nlsql.classifier import classify_question


class ClassifierTests(TestCase):
    def test_classifies_weather_question(self) -> None:
        result = classify_question("Which states had the highest storm damage?")
        self.assertEqual("weather", result.route)

    def test_classifies_trade_question(self) -> None:
        result = classify_question("Which countries had the highest export value in 2023?")
        self.assertEqual("trade", result.route)

    def test_classifies_cross_source_question(self) -> None:
        result = classify_question("Which companies appear in both FDA warning letters and the OFAC SDN list?")
        self.assertEqual("cross_source", result.route)
```

- [ ] **Step 2: Run test to verify it fails**

Run:
```powershell
.\.venv\Scripts\python.exe -m unittest tests.nlsql.test_classifier -v
```

Expected: FAIL because `nlsql.classifier` does not exist.

- [ ] **Step 3: Write minimal implementation**

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class ClassificationResult:
    route: str
    reason: str


def classify_question(question: str) -> ClassificationResult:
    text = question.lower()
    if "fda" in text and ("ofac" in text or "sdn" in text):
        return ClassificationResult(route="cross_source", reason="matched fda+sanctions keywords")
    if any(token in text for token in ("storm", "damage", "hurricane", "event")):
        return ClassificationResult(route="weather", reason="matched weather keywords")
    if any(token in text for token in ("export", "import", "trade", "reporter", "partner")):
        return ClassificationResult(route="trade", reason="matched trade keywords")
    if any(token in text for token in ("warning letter", "fda", "severity", "issuing office")):
        return ClassificationResult(route="fda", reason="matched fda keywords")
    if any(token in text for token in ("ofac", "sdn", "sanction", "sanctions program")):
        return ClassificationResult(route="sanctions", reason="matched sanctions keywords")
    return ClassificationResult(route="unsupported", reason="no route keywords matched")
```

- [ ] **Step 4: Run test to verify it passes**

Run:
```powershell
.\.venv\Scripts\python.exe -m unittest tests.nlsql.test_classifier -v
```

Expected: PASS

### Task 2: Add Prompt Examples and Stronger Prompt Builders

**Files:**
- Create: `src/nlsql/examples.py`
- Modify: `src/nlsql/prompting.py`
- Modify: `tests/nlsql/test_prompting.py`

- [ ] **Step 1: Write the failing tests**

```python
from unittest import TestCase

from nlsql.prompting import build_sql_generation_prompt


class PromptingTests(TestCase):
    def test_generation_prompt_includes_route_and_examples(self) -> None:
        prompt = build_sql_generation_prompt(
            question="Which countries had the highest export value in 2023?",
            schema_text="Table: source_comtrade_flows\n- reporter_desc (text)",
            route="trade",
            helper_text="",
        )
        self.assertIn("Route: trade", prompt)
        self.assertIn("Example", prompt)
        self.assertIn("source_comtrade_flows", prompt)
```

- [ ] **Step 2: Run test to verify it fails**

Run:
```powershell
.\.venv\Scripts\python.exe -m unittest tests.nlsql.test_prompting -v
```

Expected: FAIL because prompt signature/content is still old.

- [ ] **Step 3: Write minimal implementation**

```python
ROUTE_EXAMPLES = {
    "trade": [
        {
            "question": "Which countries had the highest export value in 2023?",
            "sql": "SELECT reporter_desc, SUM(primary_value) AS total_value FROM source_comtrade_flows WHERE tenant_id = %(tenant_id)s AND ref_year = 2023 AND flow_code = 'X' GROUP BY reporter_desc ORDER BY total_value DESC LIMIT 5",
        }
    ]
}
```

Update `build_sql_generation_prompt(...)` to accept `route` and `helper_text`, then embed:

```python
parts = [
    "You are a PostgreSQL analytics SQL generator.",
    f"Route: {route}",
    schema_text,
    helper_text,
    "Examples:",
]
```

- [ ] **Step 4: Run test to verify it passes**

Run:
```powershell
.\.venv\Scripts\python.exe -m unittest tests.nlsql.test_prompting -v
```

Expected: PASS

### Task 3: Add Canonical Cross-Source Join Helpers

**Files:**
- Create: `src/nlsql/joins.py`
- Modify: `src/nlsql/query.py`
- Modify: `tests/nlsql/test_query.py`

- [ ] **Step 1: Write the failing tests**

```python
from unittest import TestCase

from nlsql.joins import normalized_company_expression, helper_text_for_route


class JoinHelperTests(TestCase):
    def test_cross_source_helper_mentions_normalized_company_match(self) -> None:
        helper = helper_text_for_route("cross_source")
        self.assertIn("source_fda_warning_letters", helper)
        self.assertIn("source_ofac_sdn_entities", helper)
        self.assertIn("normalized", helper.lower())
```

- [ ] **Step 2: Run test to verify it fails**

Run:
```powershell
.\.venv\Scripts\python.exe -m unittest tests.nlsql.test_query -v
```

Expected: FAIL because helper module does not exist or is not wired.

- [ ] **Step 3: Write minimal implementation**

```python
def normalized_company_expression(column_sql: str) -> str:
    return (
        "regexp_replace("
        "regexp_replace(lower(coalesce(" + column_sql + ", '')), '[^a-z0-9\\s]', '', 'g'),"
        "'\\b(inc|corp|corporation|ltd|limited|llc|co|company)\\b', '', 'g'"
        ")"
    )


def helper_text_for_route(route: str) -> str:
    if route != "cross_source":
        return ""
    return (
        "Cross-source helper: join source_fda_warning_letters and source_ofac_sdn_entities "
        "using normalized company-name expressions rather than raw equality."
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run:
```powershell
.\.venv\Scripts\python.exe -m unittest tests.nlsql.test_query -v
```

Expected: PASS

### Task 4: Add Presentation Formatting and Answer-First Rendering

**Files:**
- Create: `src/nlsql/presentation.py`
- Modify: `src/nlsql/cli.py`
- Create: `tests/nlsql/test_presentation.py`

- [ ] **Step 1: Write the failing tests**

```python
from unittest import TestCase

from nlsql.presentation import render_answer_first


class PresentationTests(TestCase):
    def test_render_answer_first_outputs_expected_sections(self) -> None:
        text = render_answer_first(
            question="Which states had the highest storm damage?",
            answer="Texas had the highest damage.",
            methodology="Summed damage_property_usd by state.",
            evidence_lines=["1. Texas | $1,200,000"],
        )
        self.assertIn("Question", text)
        self.assertIn("Answer", text)
        self.assertIn("How It Was Computed", text)
        self.assertIn("Evidence", text)
```

- [ ] **Step 2: Run test to verify it fails**

Run:
```powershell
.\.venv\Scripts\python.exe -m unittest tests.nlsql.test_presentation -v
```

Expected: FAIL because module/function does not exist.

- [ ] **Step 3: Write minimal implementation**

```python
def render_answer_first(*, question: str, answer: str, methodology: str, evidence_lines: list[str]) -> str:
    blocks = [
        "Question",
        question,
        "",
        "Answer",
        answer,
        "",
        "How It Was Computed",
        methodology,
        "",
        "Evidence",
        *evidence_lines,
    ]
    return "\n".join(blocks).strip()
```

Update `cli.py` to:

```python
parser.add_argument("--debug", action="store_true")
```

and print answer-first text unless `--debug`.

- [ ] **Step 4: Run test to verify it passes**

Run:
```powershell
.\.venv\Scripts\python.exe -m unittest tests.nlsql.test_presentation -v
```

Expected: PASS

### Task 5: Wire Classification, Prompting, and Presentation into Query Orchestration

**Files:**
- Modify: `src/nlsql/query.py`
- Modify: `src/nlsql/openai_client.py`
- Modify: `tests/nlsql/test_query.py`

- [ ] **Step 1: Write the failing tests**

```python
@patch("nlsql.query.classify_question")
def test_run_nlsql_query_returns_answer_first_payload(...):
    classify_mock.return_value = ClassificationResult(route="weather", reason="matched weather keywords")
    ...
    result = run_nlsql_query(settings, "Which states had the highest property damage?")
    self.assertEqual("weather", result["classification"]["route"])
    self.assertIn("How It Was Computed", result["rendered_output"])
```

- [ ] **Step 2: Run test to verify it fails**

Run:
```powershell
.\.venv\Scripts\python.exe -m unittest tests.nlsql.test_query -v
```

Expected: FAIL because classification/rendered output are not returned yet.

- [ ] **Step 3: Write minimal implementation**

Implement in `run_nlsql_query(...)`:

```python
classification = classify_question(question)
helper_text = helper_text_for_route(classification.route)
generation = generate_sql(
    settings,
    build_sql_generation_prompt(
        question=question,
        schema_text=schema_text,
        route=classification.route,
        helper_text=helper_text,
    ),
)
```

After execution:

```python
formatted_rows = format_rows_for_display(execution.rows)
methodology = summarize_methodology(question=question, sql=execution.sql, row_count=len(execution.rows))
answer = synthesize_answer(
    settings,
    build_answer_prompt(
        question=question,
        sql=execution.sql,
        rows=formatted_rows,
        route=classification.route,
        methodology=methodology,
    ),
)
rendered_output = render_answer_first(
    question=question,
    answer=answer,
    methodology=methodology,
    evidence_lines=build_evidence_lines(formatted_rows),
)
```

- [ ] **Step 4: Run test to verify it passes**

Run:
```powershell
.\.venv\Scripts\python.exe -m unittest tests.nlsql.test_query -v
```

Expected: PASS

### Task 6: Add CLI Debug Mode and Human-Friendly Terminal Output

**Files:**
- Modify: `src/nlsql/cli.py`
- Test: `tests/nlsql/test_query.py`

- [ ] **Step 1: Write the failing test**

```python
@patch("nlsql.cli.run_nlsql_query")
def test_cli_prints_rendered_output_by_default(run_query_mock):
    run_query_mock.return_value = {
        "rendered_output": "Question\nQ\n\nAnswer\nA",
        "debug_payload": {"question": "Q"},
    }
```

- [ ] **Step 2: Run test to verify it fails**

Run:
```powershell
.\.venv\Scripts\python.exe -m unittest tests.nlsql.test_query -v
```

Expected: FAIL because CLI still prints raw JSON.

- [ ] **Step 3: Write minimal implementation**

Default path:

```python
if args.debug:
    print(json.dumps(result["debug_payload"], indent=2, ensure_ascii=False, default=str))
else:
    print(result["rendered_output"])
```

- [ ] **Step 4: Run test to verify it passes**

Run:
```powershell
.\.venv\Scripts\python.exe -m unittest tests.nlsql.test_query -v
```

Expected: PASS

### Task 7: Verify the Whole NL-SQL Slice

**Files:**
- Modify: `README.md` if behavior changed enough to warrant docs
- Test: `tests/nlsql/test_classifier.py`
- Test: `tests/nlsql/test_presentation.py`
- Test: `tests/nlsql/test_prompting.py`
- Test: `tests/nlsql/test_query.py`
- Test: `tests/nlsql/test_validation.py`
- Test: `tests/nlsql/test_executor.py`

- [ ] **Step 1: Run the full NL-SQL unit suite**

Run:
```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests\nlsql -p "test*.py"
```

Expected: PASS

- [ ] **Step 2: Run representative CLI queries**

Run:
```powershell
.\.venv\Scripts\python.exe .\run_nlsql_query.py --question "Which states had the highest total property damage?" --tenant-id capstone
.\.venv\Scripts\python.exe .\run_nlsql_query.py --question "Which countries had the highest export value in 2023?" --tenant-id capstone
.\.venv\Scripts\python.exe .\run_nlsql_query.py --question "Which companies appear in both FDA warning letters and the OFAC SDN list?" --tenant-id capstone --debug
```

Expected:
- default runs print answer-first sections
- debug run prints classifier, SQL, validation, execution, and rows

- [ ] **Step 3: Update README if the CLI contract changed**

Add example commands and mention `--debug`.
