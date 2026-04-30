"""Load installed PageIndex SDK and provide a local adapter interface.

This project has a local package named `pageindex`, so importing the installed
PyPI package directly would shadow. We therefore load the installed SDK under
an alias via importlib.
"""

from __future__ import annotations

import hashlib
import importlib.metadata as metadata
import importlib.util
import json
import os
import re
import sys
import textwrap
import time
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional


def resolve_pageindex_key(explicit_pageindex_key: Optional[str] = None) -> str:
    """Resolve PageIndex API key for cloud SDK operations."""
    key = (explicit_pageindex_key or os.getenv("PAGEINDEX_API_KEY", "")).strip()
    if not key:
        raise RuntimeError(
            "PAGEINDEX_API_KEY is required for PageIndex SDK document indexing/retrieval. "
            "Create one at https://dash.pageindex.ai/api-keys"
        )
    return key


@lru_cache(maxsize=1)
def load_installed_pageindex_sdk() -> Any:
    """Load installed `pageindex` SDK package under alias `pageindex_sdk`."""
    try:
        dist = metadata.distribution("pageindex")
    except metadata.PackageNotFoundError as exc:
        raise RuntimeError(
            "Python package `pageindex` is not installed in this interpreter. "
            "Run: pip install -U pageindex"
        ) from exc

    init_file = Path(dist.locate_file("pageindex/__init__.py"))
    if not init_file.exists():
        raise RuntimeError(f"Installed pageindex package is invalid: {init_file} not found.")

    module_name = "pageindex_sdk"
    if module_name in sys.modules:
        return sys.modules[module_name]

    spec = importlib.util.spec_from_file_location(
        module_name,
        str(init_file),
        submodule_search_locations=[str(init_file.parent)],
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load installed pageindex SDK module spec.")

    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _parse_pages_selector(pages: str) -> List[int]:
    """Parse selector like `5-7`, `3,8`, or `12` into sorted unique ints."""
    result: List[int] = []
    for part in pages.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            start_s, end_s = part.split("-", 1)
            start = int(start_s.strip())
            end = int(end_s.strip())
            if start > end:
                raise ValueError(f"Invalid page range: {part}")
            result.extend(range(start, end + 1))
        else:
            result.append(int(part))
    return sorted(set(result))


def is_pageindex_limit_error(exc: Exception) -> bool:
    """Return true when the cloud SDK reports indexing quota exhaustion."""
    message = str(exc).lower()
    return "limitreached" in message or "limit reached" in message


def is_pageindex_cloud_unavailable_error(exc: Exception) -> bool:
    """Return true when cloud indexing is unavailable and local fallback should be used."""
    message = str(exc).lower()
    return any(
        token in message
        for token in (
            "limitreached",
            "limit reached",
            "api.pageindex.ai",
            "submit_document",
            "failed to establish a new connection",
            "max retries exceeded",
            "connectionerror",
            "httpsconnectionpool",
        )
    )


def describe_pageindex_cloud_error(exc: Exception) -> str:
    """Explain PageIndex cloud failures with likely cause and next step."""
    raw_message = str(exc).strip() or exc.__class__.__name__
    message = raw_message.lower()
    if "limitreached" in message or "usage_limit_reached" in message:
        return (
            "PageIndex cloud indexing failed because the account usage quota appears to be exhausted "
            f"(`{raw_message}`). This is usually an account/document-processing limit, not a local code bug. "
            "Use the PageIndex dashboard to check plan usage or switch to a key with available quota."
        )
    if "rate_limited" in message or "429" in message:
        return (
            "PageIndex cloud indexing was rate limited "
            f"(`{raw_message}`). Retry later or reduce submit frequency."
        )
    if is_pageindex_cloud_unavailable_error(exc):
        return (
            "PageIndex cloud indexing is currently unavailable "
            f"(`{raw_message}`). Verify the API key, service availability, and outbound network access."
        )
    return f"PageIndex cloud indexing failed: {raw_message}"


def _markdown_to_pdf(markdown_path: Path, pdf_path: Path) -> None:
    """Convert markdown/plain text to a simple text PDF for SDK submission."""
    try:
        import fitz  # PyMuPDF
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError("PyMuPDF (fitz) is required for markdown->pdf conversion.") from exc

    text = markdown_path.read_text(encoding="utf-8", errors="replace")
    pdf_path.parent.mkdir(parents=True, exist_ok=True)

    doc = fitz.open()
    page = doc.new_page()
    margin_x = 40
    margin_y = 40
    y = margin_y
    line_height = 12
    max_width_chars = 110

    for raw_line in text.splitlines():
        wrapped = textwrap.wrap(raw_line, width=max_width_chars) or [""]
        for line in wrapped:
            if y > page.rect.height - margin_y:
                page = doc.new_page()
                y = margin_y
            page.insert_text((margin_x, y), line, fontsize=9)
            y += line_height

    doc.save(str(pdf_path))
    doc.close()


class PageIndexCloudAdapter:
    """Adapter providing `index/get_document_structure/get_page_content` style APIs."""

    META_FILE = "_cloud_meta.json"

    def __init__(self, api_key: str, workspace: Path):
        sdk_module = load_installed_pageindex_sdk()
        client_cls = getattr(sdk_module, "PageIndexClient", None)
        if client_cls is None:
            raise RuntimeError("PageIndexClient missing in installed SDK.")

        self.client = client_cls(api_key=api_key)
        self.workspace = workspace
        self.workspace.mkdir(parents=True, exist_ok=True)
        self.documents: Dict[str, Dict[str, Any]] = {}
        self._load_meta()

    @property
    def _meta_path(self) -> Path:
        return self.workspace / self.META_FILE

    def _load_meta(self) -> None:
        if not self._meta_path.exists():
            return
        try:
            rows = json.loads(self._meta_path.read_text(encoding="utf-8"))
            if isinstance(rows, dict):
                self.documents = rows
        except Exception:  # noqa: BLE001
            self.documents = {}

    def _save_meta(self) -> None:
        self._meta_path.write_text(json.dumps(self.documents, indent=2), encoding="utf-8")

    def _find_remote_document_id(self, upload_file: Path) -> Optional[str]:
        """Reuse an already-uploaded remote document when the filename matches."""
        offset = 0
        while True:
            payload = self.client.list_documents(limit=100, offset=offset)
            rows = payload.get("documents", [])
            if not isinstance(rows, list):
                rows = []
            for row in rows:
                if not isinstance(row, dict):
                    continue
                if str(row.get("name", "")).strip() != upload_file.name:
                    continue
                doc_id = str(row.get("id", "") or row.get("doc_id", "")).strip()
                if doc_id:
                    return doc_id
            if len(rows) < 100:
                break
            offset += len(rows)
        return None

    def _prepare_upload_file(self, file_path: Path) -> Path:
        ext = file_path.suffix.lower()
        if ext == ".pdf":
            return file_path
        if ext not in {".md", ".markdown", ".txt"}:
            raise ValueError(f"Unsupported file for SDK submit_document: {file_path}")

        stat = file_path.stat()
        sig = hashlib.sha1(f"{file_path.resolve()}::{stat.st_mtime_ns}".encode("utf-8")).hexdigest()[:12]
        out_pdf = self.workspace / "_uploads" / f"{file_path.stem}_{sig}.pdf"
        if not out_pdf.exists():
            _markdown_to_pdf(file_path, out_pdf)
        return out_pdf

    def index(self, file_path: str, mode: str = "auto") -> str:
        """Submit document to PageIndex API and return `doc_id`."""
        src = Path(file_path).resolve()
        upload_file = self._prepare_upload_file(src)
        remote_doc_id = self._find_remote_document_id(upload_file)
        if remote_doc_id:
            self.documents[remote_doc_id] = {
                "id": remote_doc_id,
                "path": str(src),
                "upload_path": str(upload_file),
                "type": "pdf",
            }
            self._save_meta()
            return remote_doc_id
        result = self.client.submit_document(str(upload_file))
        doc_id = result.get("doc_id")
        if not doc_id:
            raise RuntimeError(f"PageIndex submit_document failed: {result}")

        self.documents[doc_id] = {
            "id": doc_id,
            "path": str(src),
            "upload_path": str(upload_file),
            "type": "pdf",
        }
        self._save_meta()
        return doc_id

    def chat_completions(
        self,
        messages: List[Dict[str, str]],
        *,
        stream: bool = False,
        doc_id: Optional[str | List[str]] = None,
        temperature: Optional[float] = None,
        stream_metadata: bool = False,
        enable_citations: bool = False,
    ) -> Any:
        """Proxy PageIndex Chat API calls through the installed SDK."""
        return self.client.chat_completions(
            messages=messages,
            stream=stream,
            doc_id=doc_id,
            temperature=temperature,
            stream_metadata=stream_metadata,
            enable_citations=enable_citations,
        )

    def get_document(self, doc_id: str) -> Dict[str, Any]:
        """Proxy document metadata lookup through the installed SDK."""
        return self.client.get_document(doc_id)

    def is_retrieval_ready(self, doc_id: str) -> bool:
        """Proxy retrieval readiness check through the installed SDK."""
        return self.client.is_retrieval_ready(doc_id)

    def _poll_until_ready(self, fetch_fn, *, max_wait_sec: int = 300, interval_sec: float = 2.0) -> Dict[str, Any]:
        """Poll API status until `status == completed` or timeout."""
        start = time.time()
        while True:
            payload = fetch_fn()
            status = str(payload.get("status", "")).lower()
            if status == "completed":
                return payload
            if status in {"failed", "error"}:
                return payload
            if (time.time() - start) >= max_wait_sec:
                return payload
            time.sleep(interval_sec)

    def get_document_structure(self, doc_id: str) -> str:
        """Return tree structure JSON string (like local client API)."""
        payload = self._poll_until_ready(lambda: self.client.get_tree(doc_id, node_summary=True))
        result = payload.get("result", [])
        if not isinstance(result, list):
            result = []
        return json.dumps(result, ensure_ascii=False)

    def get_page_content(self, doc_id: str, pages: str) -> str:
        """Return selected OCR pages as JSON list: [{'page': n, 'content': text}, ...]."""
        payload = self._poll_until_ready(lambda: self.client.get_ocr(doc_id, format="page"))
        rows = payload.get("result", [])
        if not isinstance(rows, list):
            rows = []

        wanted = _parse_pages_selector(pages)
        wanted_set = set(wanted)
        page_map: Dict[int, str] = {}

        for row in rows:
            if not isinstance(row, dict):
                continue
            # Support common field variants from SDK/API.
            page_num = row.get("page")
            if page_num is None:
                page_num = row.get("page_index")
            if page_num is None:
                page_num = row.get("page_num")
            try:
                page_int = int(page_num)
            except Exception:  # noqa: BLE001
                continue

            content = row.get("content")
            if content is None:
                content = row.get("markdown")
            if content is None:
                content = row.get("text", "")
            page_map[page_int] = str(content or "")

        out = [{"page": p, "content": page_map.get(p, "")} for p in wanted if p in wanted_set and p in page_map]
        return json.dumps(out, ensure_ascii=False)


class LocalMarkdownAdapter:
    """Local markdown-backed adapter for tree search when cloud indexing is unavailable."""

    META_FILE = "_meta.json"
    HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")

    def __init__(self, workspace: Path):
        self.workspace = workspace
        self.workspace.mkdir(parents=True, exist_ok=True)
        self.documents: Dict[str, Dict[str, Any]] = {}
        self._load_meta()

    @property
    def _meta_path(self) -> Path:
        return self.workspace / self.META_FILE

    def _load_meta(self) -> None:
        if not self._meta_path.exists():
            return
        try:
            rows = json.loads(self._meta_path.read_text(encoding="utf-8"))
            if isinstance(rows, dict):
                self.documents = rows
        except Exception:  # noqa: BLE001
            self.documents = {}

    def _save_meta(self) -> None:
        self._meta_path.write_text(json.dumps(self.documents, indent=2), encoding="utf-8")

    def _doc_id_for_path(self, path: Path) -> str:
        digest = hashlib.sha1(str(path.resolve()).encode("utf-8")).hexdigest()[:16]
        return f"local-{digest}"

    def _build_tree(self, path: Path) -> List[Dict[str, Any]]:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        heading_entries: List[Dict[str, Any]] = []
        for idx, line in enumerate(lines, start=1):
            match = self.HEADING_RE.match(line)
            if not match:
                continue
            level = len(match.group(1))
            title = match.group(2).strip()
            heading_entries.append(
                {
                    "level": level,
                    "title": title,
                    "start_index": idx,
                }
            )

        if not heading_entries:
            body = "\n".join(lines).strip()
            return [
                {
                    "node_id": "0001",
                    "title": path.stem,
                    "summary": body[:280],
                    "start_index": 1,
                    "end_index": max(1, len(lines)),
                    "nodes": [],
                }
            ]

        root: Dict[str, Any] = {"nodes": []}
        stack: List[tuple[int, Dict[str, Any]]] = [(0, root)]
        flat_nodes: List[Dict[str, Any]] = []

        for seq, entry in enumerate(heading_entries, start=1):
            node = {
                "node_id": f"{seq:04d}",
                "title": entry["title"],
                "summary": "",
                "start_index": entry["start_index"],
                "end_index": len(lines),
                "nodes": [],
            }
            flat_nodes.append(node)

            while stack and stack[-1][0] >= entry["level"]:
                stack.pop()
            parent = stack[-1][1]
            parent.setdefault("nodes", []).append(node)
            stack.append((entry["level"], node))

        starts = [node["start_index"] for node in flat_nodes]
        for idx, node in enumerate(flat_nodes):
            next_start = starts[idx + 1] if idx + 1 < len(starts) else len(lines) + 1
            node["end_index"] = max(node["start_index"], next_start - 1)
            section_lines = lines[node["start_index"] : node["end_index"]]
            summary_parts = [line.strip() for line in section_lines if line.strip() and not self.HEADING_RE.match(line)]
            node["summary"] = "\n".join(summary_parts)[:280]

        return root["nodes"]

    def index(self, file_path: str, mode: str = "auto") -> str:
        _ = mode
        src = Path(file_path).resolve()
        doc_id = self._doc_id_for_path(src)
        if doc_id not in self.documents:
            self.documents[doc_id] = {
                "id": doc_id,
                "path": str(src),
                "type": "md",
                "tree": self._build_tree(src),
            }
            self._save_meta()
        return doc_id

    def get_document_structure(self, doc_id: str) -> str:
        meta = self.documents.get(doc_id)
        if not meta:
            return "[]"
        return json.dumps(meta.get("tree", []), ensure_ascii=False)

    def get_page_content(self, doc_id: str, pages: str) -> str:
        meta = self.documents.get(doc_id)
        if not meta:
            return "[]"
        path = Path(str(meta.get("path", "")))
        if not path.exists():
            return "[]"
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        wanted = _parse_pages_selector(pages)
        rows = []
        for line_num in wanted:
            if 1 <= line_num <= len(lines):
                rows.append({"page": line_num, "content": lines[line_num - 1]})
        return json.dumps(rows, ensure_ascii=False)


def init_local_pageindex_client(workspace: Path) -> Any:
    """Create the markdown-backed local adapter."""
    workspace.mkdir(parents=True, exist_ok=True)
    return LocalMarkdownAdapter(workspace=workspace)


def init_pageindex_client(
    workspace: Path,
    pageindex_api_key: str,
    index_model: Optional[str],
    retrieve_model: Optional[str],
) -> Any:
    """Create PageIndex cloud adapter.

    `index_model` and `retrieve_model` are accepted for interface compatibility
    but not used by current cloud SDK endpoints.
    """
    _ = index_model
    _ = retrieve_model
    workspace.mkdir(parents=True, exist_ok=True)
    return PageIndexCloudAdapter(api_key=pageindex_api_key, workspace=workspace)


