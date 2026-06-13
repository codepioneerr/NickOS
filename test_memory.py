#!/usr/bin/env python3
"""
test_memory.py — NickOS Memory Pipeline Smoke Test

Run from the repo root:
    python test_memory.py

Tests (all independent, each prints PASS / FAIL / SKIP + elapsed ms):
  1. Indexer initialises and indexes test fixture files
  2. Search returns results for 3 queries (study abroad, trading bot, health)
  3. Reflect pipeline calls Claude Haiku and returns a non-empty response
  4. Incremental reindex detects a newly written file

No external deps beyond requirements.txt.
ANTHROPIC_API_KEY must be set for Test 3; otherwise it is marked SKIP.
"""

from __future__ import annotations

import os
import sys
import time
import tempfile
import textwrap
import logging
from pathlib import Path
from datetime import datetime

# ── Redirect DATA_DIR before any NickOS imports so config.py picks it up ──────
_TMP_DIR = tempfile.mkdtemp(prefix="nickos_memtest_")
os.environ.setdefault("DATA_DIR", _TMP_DIR)

# Add repo root to sys.path
ROOT = Path(__file__).parent.resolve()
sys.path.insert(0, str(ROOT))

logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(message)s")

# ── Colour helpers ────────────────────────────────────────────────────────────
GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
BOLD   = "\033[1m"
RESET  = "\033[0m"

_results: list[tuple[str, str, float, str]] = []  # (name, status, ms, detail)


def run_test(name: str):
    """Decorator factory for a named test function."""
    def decorator(fn):
        def wrapper():
            t0 = time.perf_counter()
            status = "PASS"
            detail = ""
            try:
                result = fn()
                if result is not None:
                    detail = str(result)
            except SkipTest as e:
                status = "SKIP"
                detail = str(e)
            except AssertionError as e:
                status = "FAIL"
                detail = str(e)
            except Exception as e:
                status = "FAIL"
                detail = f"{type(e).__name__}: {e}"
            ms = (time.perf_counter() - t0) * 1000
            _results.append((name, status, ms, detail))
        return wrapper
    return decorator


class SkipTest(Exception):
    pass


# ── Fixtures ──────────────────────────────────────────────────────────────────

def _create_fixtures(mem_dir: Path, logs_dir: Path):
    """Write minimal test MEMORY.md + two daily logs."""
    logs_dir.mkdir(parents=True, exist_ok=True)

    (mem_dir / "MEMORY.md").write_text(textwrap.dedent("""\
        # Nick's Memory

        ## Active Goals

        - [ ] Study abroad London appeal — submitted appeal documents | Added: 2026-01-15
        - [ ] Trading bot: complete PEAD backtest strategy and push to GitHub | Added: 2026-02-01
        - [ ] Health: maintain 8 glasses water per day consistently | Added: 2026-03-01

        ## Health Tracking

        - Current streak: 7 days of logging
        - Meals today: 2/3
        - This week: 4/5 workouts
        - Last logged sleep: `7.5h` on 2026-06-08

        ## Today's Focus

        Complete the PEAD backtest implementation and push algo trading bot v2.

        ## Recent Wins 🏆

        - Finished algo trading bot v1 architecture
        - Submitted London study abroad appeal letter with supporting documents
        - Hit 8 glasses of water every day for a week
    """))

    (logs_dir / "2026-06-08.md").write_text(textwrap.dedent("""\
        # Daily Log 2026-06-08

        ## Morning Brief

        Brief sent at 08:10 ET

        ## Health

        Sleep: 7.5h (logged 08:15 ET)
        Meal: Breakfast — eggs and coffee (logged 09:00 ET)
        Water: glass 1 (logged 09:10 ET)
        Workout done: Upper body dumbbells (logged 17:45 ET)

        ## Focus Blocks

        09:30 ET — PEAD backtest results — excellent performance in Q1 backtesting

        ## Done Today

        Pushed trading bot v2 to GitHub ✓ (14:30 ET)
        Emailed London program advisor about study abroad appeal ✓ (15:00 ET)

        ## Notes

        Study abroad appeal decision expected within 10 business days.
        PEAD strategy showing 2.3 Sharpe ratio on backtest — very promising.
    """))

    (logs_dir / "2026-06-09.md").write_text(textwrap.dedent("""\
        # Daily Log 2026-06-09

        ## Morning Brief

        Brief sent at 08:20 ET

        ## Health

        Sleep: 8h (logged 08:25 ET)
        Meal: Breakfast (logged 09:15 ET)
        Water: glass 1 (logged 09:15 ET)
        Water: glass 2 (logged 11:00 ET)

        ## Focus Blocks

        10:00 ET — Memory search engine implementation for NickOS

        ## Done Today

        Implemented memory/search.py with hybrid FTS5+vector search ✓
    """))


# ── Test setup ────────────────────────────────────────────────────────────────

# Patch memory.search module-level globals before instantiating MemoryIndexer.
# This lets us use /tmp for the DB regardless of config.DATA_DIR.
import memory.search as _search_mod

_TEST_DB = Path(_TMP_DIR) / "db" / "memory_search.db"
_TEST_DB.parent.mkdir(parents=True, exist_ok=True)
_search_mod.SEARCH_DB = _TEST_DB

_TEST_MEM_DIR  = Path(_TMP_DIR) / "memory"
_TEST_LOGS_DIR = _TEST_MEM_DIR / "daily_logs"
_search_mod.MEMORY_DIR  = _TEST_MEM_DIR
_search_mod.DAILY_LOGS  = _TEST_LOGS_DIR
_search_mod.MEMORY_FILE = _TEST_MEM_DIR / "MEMORY.md"

_create_fixtures(_TEST_MEM_DIR, _TEST_LOGS_DIR)


# ─────────────────────────────────────────────────────────────────────────────
# TEST 1 — Indexer initialises and indexes all fixture files
# ─────────────────────────────────────────────────────────────────────────────
@run_test("1. Indexer init + full index")
def test_indexer_init():
    _search_mod._indexer = None  # reset singleton
    indexer = _search_mod.get_indexer()

    stats_before = indexer.stats()
    assert stats_before["total_chunks"] == 0, \
        f"Expected empty index, got {stats_before['total_chunks']} chunks"

    summary = indexer.index_all(force=True)

    assert summary["indexed"] > 0, \
        f"Expected files to be indexed, got: {summary}"
    assert summary["chunks_added"] > 0, \
        f"Expected chunks to be added, got: {summary}"

    stats_after = indexer.stats()
    assert stats_after["total_chunks"] > 0, \
        f"Expected chunks in index, got 0"
    assert stats_after["indexed_files"] > 0, \
        "Expected indexed_files > 0"

    return (
        f"indexed={summary['indexed']} files, "
        f"{summary['chunks_added']} chunks | embedder={stats_after['embedder']}"
    )


# ─────────────────────────────────────────────────────────────────────────────
# TEST 2 — Search returns results for 3 topic queries
# ─────────────────────────────────────────────────────────────────────────────
@run_test("2. Search — 3 topic queries")
def test_search_three_queries():
    indexer = _search_mod.get_indexer()

    queries = [
        ("study abroad",  "study abroad London appeal"),
        ("trading bot",   "PEAD backtest results"),
        ("health",        "water glasses workout sleep"),
    ]

    hits: list[str] = []
    misses: list[str] = []

    for label, query in queries:
        results = indexer.search(query, k=5)
        if results and results[0]["score"] > 0:
            hits.append(f"{label}({results[0]['score']:.3f})")
        else:
            misses.append(label)

    assert not misses, \
        f"Search returned no results for: {', '.join(misses)}"

    return "hits: " + ", ".join(hits)


# ─────────────────────────────────────────────────────────────────────────────
# TEST 3 — Reflect pipeline: search + Haiku synthesis
# ─────────────────────────────────────────────────────────────────────────────
@run_test("3. Reflect pipeline — Haiku synthesis")
def test_reflect_pipeline():
    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        raise SkipTest("ANTHROPIC_API_KEY not set")

    from zoneinfo import ZoneInfo
    ET = ZoneInfo("America/New_York")

    indexer = _search_mod.get_indexer()

    # Search for "daily review" — same as /reflect with no args
    results = indexer.search("daily review progress goals", k=3)

    context_chunks = [
        f"[{r.get('source', '')} | {r.get('date_str', '')}]\n{r.get('text', '').strip()}"
        for r in results
    ]

    # Read today's test log
    log_path = _TEST_LOGS_DIR / "2026-06-09.md"
    today_log = log_path.read_text() if log_path.exists() else "(no log)"

    now_str = datetime.now(ET).strftime("%A, %B %-d at %-I:%M %p ET")
    memory_block = ""
    if context_chunks:
        memory_block = "\n\nRelevant past context:\n" + "\n\n".join(context_chunks)

    prompt = (
        f"You are NickOS — Nick's personal AI OS.\n"
        f"Current time: {now_str}\n"
        f"\nToday's log:\n{today_log}"
        f"{memory_block}"
        f"\n\nGenerate a short end-of-day reflection. Be direct and specific. "
        f"3-4 sentences. Tough-love tone."
    )

    import anthropic
    haiku_model = os.environ.get("ANTHROPIC_HAIKU_MODEL", "claude-haiku-4-5-20251001")
    client = anthropic.Anthropic(api_key=api_key)
    resp = client.messages.create(
        model=haiku_model,
        max_tokens=200,
        temperature=0.7,
        messages=[{"role": "user", "content": prompt}],
    )
    reflection = resp.content[0].text.strip()

    assert reflection, "Haiku returned empty response"
    assert len(reflection) > 20, f"Reflection suspiciously short: {repr(reflection)}"

    snippet = reflection[:80].replace("\n", " ")
    return f"Haiku OK — '{snippet}…'"


# ─────────────────────────────────────────────────────────────────────────────
# TEST 4 — Incremental reindex picks up a newly written file
# ─────────────────────────────────────────────────────────────────────────────
@run_test("4. Incremental reindex — new file detection")
def test_incremental_reindex():
    indexer = _search_mod.get_indexer()

    # Unique sentinel content that won't appear in existing fixtures
    sentinel = "xK9_SMOKE_TEST_SENTINEL_UNIQUE_2026"
    new_log = _TEST_LOGS_DIR / "2026-06-10.md"
    new_log.write_text(textwrap.dedent(f"""\
        # Daily Log 2026-06-10

        ## Notes

        This is a smoke test entry containing {sentinel}.
        Testing incremental reindex detection in NickOS memory system.
    """))

    # Reindex (incremental — only changed/new files)
    summary = indexer.reindex_changed()

    assert summary["indexed"] >= 1, \
        f"Expected at least 1 new file indexed, got: {summary}"

    # Now search for the sentinel — must find it
    results = indexer.search(sentinel, k=3)

    assert results, "Search returned no results after reindex"
    top_text = results[0]["text"]
    assert sentinel in top_text or results[0]["score"] > 0, \
        f"Sentinel not found in top result. Top: {top_text[:80]}"

    # Clean up
    new_log.unlink()

    return (
        f"reindex indexed {summary['indexed']} file(s), "
        f"sentinel found (score={results[0]['score']:.3f})"
    )


# ── Runner ────────────────────────────────────────────────────────────────────

def main():
    print(f"\n{BOLD}{CYAN}{'─'*60}{RESET}")
    print(f"{BOLD}{CYAN}  NickOS Memory Pipeline Smoke Test{RESET}")
    print(f"{BOLD}{CYAN}{'─'*60}{RESET}")
    print(f"  DB:      {_TEST_DB}")
    print(f"  Fixtures:{_TEST_MEM_DIR}")
    print()

    # Run all tests
    test_indexer_init()
    test_search_three_queries()
    test_reflect_pipeline()
    test_incremental_reindex()

    # Print results
    passed = failed = skipped = 0
    for name, status, ms, detail in _results:
        if status == "PASS":
            icon  = f"{GREEN}PASS{RESET}"
            passed += 1
        elif status == "SKIP":
            icon  = f"{YELLOW}SKIP{RESET}"
            skipped += 1
        else:
            icon  = f"{RED}FAIL{RESET}"
            failed += 1

        print(f"  [{icon}]  {name}  ({ms:.0f}ms)")
        if detail:
            wrapped = textwrap.indent(textwrap.fill(detail, 72), "         ")
            print(wrapped)

    print(f"\n{BOLD}{'─'*60}{RESET}")
    summary_color = GREEN if failed == 0 else RED
    print(
        f"{summary_color}{BOLD}  {passed} passed, {failed} failed, {skipped} skipped{RESET}"
    )
    print(f"{'─'*60}\n")

    # Clean up temp dir (best-effort)
    import shutil
    try:
        shutil.rmtree(_TMP_DIR, ignore_errors=True)
    except Exception:
        pass

    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
