"""
api/routers/obsidian.py
GET /api/obsidian/search?q=... — search Nick's Obsidian vault.

Vault path comes from OBSIDIAN_VAULT_PATH (default: ~/Obsidian).
If the vault doesn't exist yet, the endpoint returns an empty result with
vaultFound=false — the dashboard shows a graceful empty state.
"""

import os
import re
import urllib.parse
from pathlib import Path

from fastapi import APIRouter, Query

router = APIRouter(prefix="/api/obsidian", tags=["obsidian"])

MAX_RESULTS    = 20
PREVIEW_CHARS  = 200
MAX_FILE_BYTES = 1_000_000  # skip pathological files


def vault_path() -> Path:
    return Path(os.environ.get("OBSIDIAN_VAULT_PATH", "~/Obsidian")).expanduser()


def _preview(content: str, query: str) -> str:
    """Return ~200 chars around the first match (or the start of the note)."""
    idx = content.lower().find(query.lower())
    if idx == -1:
        snippet = content[:PREVIEW_CHARS]
    else:
        start   = max(0, idx - 60)
        snippet = ("…" if start else "") + content[start:start + PREVIEW_CHARS]
    snippet = re.sub(r"[#>*`\[\]]", "", snippet)        # strip md syntax
    snippet = re.sub(r"\s+", " ", snippet).strip()
    return snippet + ("…" if len(content) > PREVIEW_CHARS else "")


@router.get("/search")
def search_vault(q: str = Query("", max_length=100)):
    vault = vault_path()
    if not vault.is_dir():
        return {"vaultFound": False, "vaultPath": str(vault), "results": []}

    q = q.strip()
    if not q:
        return {"vaultFound": True, "vaultPath": str(vault), "results": []}

    vault_name   = vault.name
    title_hits   = []
    content_hits = []

    for md in sorted(vault.rglob("*.md")):
        if md.is_symlink() or any(p.startswith(".") for p in md.relative_to(vault).parts):
            continue
        try:
            if md.stat().st_size > MAX_FILE_BYTES:
                continue
            content = md.read_text(errors="ignore")
        except OSError:
            continue

        rel        = md.relative_to(vault)
        title      = md.stem
        title_match   = q.lower() in title.lower()
        content_match = q.lower() in content.lower()
        if not (title_match or content_match):
            continue

        result = {
            "title":   title,
            "path":    str(rel),
            "preview": _preview(content, q),
            "obsidianUrl": (
                "obsidian://open?vault=" + urllib.parse.quote(vault_name)
                + "&file=" + urllib.parse.quote(str(rel.with_suffix("")))
            ),
        }
        (title_hits if title_match else content_hits).append(result)
        if len(title_hits) + len(content_hits) >= MAX_RESULTS * 2:
            break

    results = (title_hits + content_hits)[:MAX_RESULTS]
    return {"vaultFound": True, "vaultPath": str(vault), "query": q, "results": results}
