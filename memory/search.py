"""
memory/search.py — NickOS hybrid memory search engine.

Architecture
────────────
  Indexing:
    - Crawls memory/daily_logs/*.md, MEMORY.md, USER.md, SOUL.md
    - Chunks each file by markdown H2 section (≤600 chars, 60-char overlap)
    - Embeds chunks with the best available model (tried in order):
        1. fastembed  BAAI/bge-small-en-v1.5  (50 MB, semantic)
        2. sentence-transformers all-MiniLM-L6-v2 (22 MB, semantic)
        3. numpy hash-BOW fallback (zero extra deps, complementary to FTS5)
    - Stores text + float32 embedding blob in SQLite
    - Also inserts text into FTS5 virtual table for keyword (BM25) scoring

  Search:
    - Encodes query with same embedder
    - Loads all stored embeddings → numpy cosine similarity
    - FTS5 BM25 for keyword scoring
    - Hybrid: 0.70 × vector_score + 0.30 × bm25_score
    - Returns top-k [{text, source, date_str, section, score}]

  Auto-indexing:
    - index_all() on startup (skips unchanged files via mtime tracking)
    - reindex_changed() called hourly by APScheduler

Public API
──────────
    from memory.search import search, get_indexer

    results = search("PEAD backtest results", k=5)
    get_indexer().index_all()
    get_indexer().reindex_changed()
"""

from __future__ import annotations

import re
import sys
import struct
import sqlite3
import hashlib
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional

import numpy as np

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from config import DATA_DIR, DAILY_LOGS, MEMORY_FILE, MEMORY_DIR  # noqa: E402

logger = logging.getLogger(__name__)

# ── Constants ──────────────────────────────────────────────────────────────────
SEARCH_DB   = DATA_DIR / "db" / "memory_search.db"
EMBED_CACHE = DATA_DIR / "db" / "embed_cache"  # fastembed model cache
VOCAB_SIZE  = 512   # hash-BOW fallback dimension
CHUNK_CHARS = 600   # max chars per chunk
CHUNK_OVER  = 80    # overlap between chunks when splitting long sections
VECTOR_W    = 0.70  # weight for vector score in hybrid
KEYWORD_W   = 0.30  # weight for BM25 score in hybrid


# ── Embedding backend ──────────────────────────────────────────────────────────

_embedder_fn = None   # callable(texts: list[str]) → np.ndarray [N, dim]
_embed_dim   = VOCAB_SIZE
_embed_name  = "hash-bow"


def _init_embedder():
    """Try to load a real embedding model; fall back to hash-BOW."""
    global _embedder_fn, _embed_dim, _embed_name

    # 1. fastembed (BAAI/bge-small-en-v1.5 — 50 MB, fast, accurate)
    try:
        from fastembed import TextEmbedding
        EMBED_CACHE.mkdir(parents=True, exist_ok=True)
        _model = TextEmbedding(
            "BAAI/bge-small-en-v1.5",
            cache_dir=str(EMBED_CACHE),
        )

        def _fastembed(texts):
            return np.array(list(_model.embed(texts)), dtype=np.float32)

        _embedder_fn = _fastembed
        _embed_dim   = 384
        _embed_name  = "fastembed/bge-small-en-v1.5"
        logger.info("[search] embedder: fastembed/bge-small-en-v1.5")
        return
    except Exception:
        pass

    # 2. sentence-transformers (all-MiniLM-L6-v2 — 22 MB, decent)
    try:
        from sentence_transformers import SentenceTransformer
        _st = SentenceTransformer("all-MiniLM-L6-v2")

        def _sbert(texts):
            return _st.encode(texts, convert_to_numpy=True).astype(np.float32)

        _embedder_fn = _sbert
        _embed_dim   = 384
        _embed_name  = "sbert/all-MiniLM-L6-v2"
        logger.info("[search] embedder: sentence-transformers/all-MiniLM-L6-v2")
        return
    except Exception:
        pass

    # 3. Hash-BOW fallback — zero extra deps, complementary to FTS5
    def _hash_bow(texts):
        out = np.zeros((len(texts), VOCAB_SIZE), dtype=np.float32)
        for i, text in enumerate(texts):
            tokens = re.findall(r"[a-z0-9]+", text.lower())
            # Include bigrams for better phrase matching
            bigrams = [f"{a}_{b}" for a, b in zip(tokens, tokens[1:])]
            for tok in tokens + bigrams:
                out[i, hash(tok) % VOCAB_SIZE] += 1.0
            n = np.linalg.norm(out[i])
            if n > 0:
                out[i] /= n
        return out

    _embedder_fn = _hash_bow
    _embed_dim   = VOCAB_SIZE
    _embed_name  = "hash-bow"
    logger.info("[search] embedder: hash-bow fallback (install fastembed for semantic search)")


def _embed(texts: list[str]) -> Optional[np.ndarray]:
    """Embed a list of texts → float32 array [N, dim]. Returns None on error."""
    if _embedder_fn is None:
        _init_embedder()
    try:
        return _embedder_fn(texts)  # type: ignore[misc]
    except Exception as e:
        logger.warning(f"[search] embed failed: {e}")
        return None


# ── Markdown chunker ───────────────────────────────────────────────────────────

def _date_from_path(path: Path) -> str:
    """Extract YYYY-MM-DD from filename like 2026-06-09.md."""
    m = re.match(r"(\d{4}-\d{2}-\d{2})", path.stem)
    return m.group(1) if m else ""


def chunk_file(path: Path) -> list[dict]:
    """
    Split a markdown file into chunks for indexing.

    Strategy:
      - Split on H2 (##) headings — each section is one or more chunks
      - Long sections (> CHUNK_CHARS) are split further with overlap
      - Returns list of:
        {chunk_id, text, source, date_str, section}
    """
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return []

    date_str = _date_from_path(path)
    try:
        source = str(path.resolve().relative_to(ROOT.resolve()))
    except ValueError:
        source = str(path)
    chunks   = []

    # Split on H2 headings (keeping the heading in the chunk)
    parts = re.split(r"\n(## .+)", text)
    # parts alternates: [preamble, heading1, body1, heading2, body2, ...]

    # First part is preamble (title + intro)
    preamble = parts[0].strip()
    if preamble and len(preamble) > 20:
        # Extract H1 title if present
        h1_m = re.match(r"# (.+)", preamble)
        section = h1_m.group(1).strip() if h1_m else "Intro"
        for sub in _split_text(preamble, source, date_str, section):
            chunks.append(sub)

    # Process heading + body pairs
    for i in range(1, len(parts), 2):
        heading = parts[i].lstrip("#").strip() if i < len(parts) else ""
        body    = parts[i + 1].strip()         if i + 1 < len(parts) else ""
        combined = f"{heading}\n{body}".strip()
        if len(combined) < 15:
            continue
        for sub in _split_text(combined, source, date_str, heading):
            chunks.append(sub)

    return chunks


def _split_text(text: str, source: str, date_str: str, section: str) -> list[dict]:
    """Split text into CHUNK_CHARS-size pieces with CHUNK_OVER overlap."""
    text = text.strip()
    if not text:
        return []

    pieces = []
    if len(text) <= CHUNK_CHARS:
        pieces = [text]
    else:
        start = 0
        while start < len(text):
            end = start + CHUNK_CHARS
            pieces.append(text[start:end])
            start += CHUNK_CHARS - CHUNK_OVER

    result = []
    for idx, piece in enumerate(pieces):
        piece = piece.strip()
        if not piece or len(piece) < 10:
            continue
        # Stable chunk_id: source + section + piece index + hash of text
        raw_id = f"{source}|{section}|{idx}|{piece[:40]}"
        chunk_id = hashlib.sha1(raw_id.encode()).hexdigest()[:16]
        result.append({
            "chunk_id": chunk_id,
            "text":     piece,
            "source":   source,
            "date_str": date_str,
            "section":  section,
        })
    return result


# ── SQLite schema ──────────────────────────────────────────────────────────────

_SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA synchronous=NORMAL;

CREATE TABLE IF NOT EXISTS memory_chunks (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    chunk_id   TEXT    UNIQUE NOT NULL,
    text       TEXT    NOT NULL,
    source     TEXT    NOT NULL,
    date_str   TEXT    DEFAULT '',
    section    TEXT    DEFAULT '',
    embedding  BLOB,                 -- float32 raw bytes
    embed_dim  INTEGER DEFAULT 0,
    indexed_at TEXT    NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_chunks_source  ON memory_chunks(source);
CREATE INDEX IF NOT EXISTS idx_chunks_date    ON memory_chunks(date_str);

CREATE VIRTUAL TABLE IF NOT EXISTS memory_fts USING fts5(
    chunk_id  UNINDEXED,
    text,
    source    UNINDEXED,
    date_str  UNINDEXED,
    section   UNINDEXED,
    tokenize  = 'porter ascii'
);

-- Track which files have been indexed and when
CREATE TABLE IF NOT EXISTS indexed_files (
    path        TEXT PRIMARY KEY,
    mtime       REAL NOT NULL,
    chunk_count INTEGER DEFAULT 0,
    indexed_at  TEXT NOT NULL
);
"""


# ── MemoryIndexer ──────────────────────────────────────────────────────────────

class MemoryIndexer:
    """
    Manages the memory search index.
    Call index_all() on startup, reindex_changed() hourly.
    """

    def __init__(self):
        SEARCH_DB.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(SEARCH_DB), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_schema()
        _init_embedder()  # warm up the embedding model
        logger.info(f"[search] MemoryIndexer ready (embedder={_embed_name}, db={SEARCH_DB})")

    def _init_schema(self):
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    # ── File discovery ─────────────────────────────────────────────────────────

    def _files_to_index(self) -> list[Path]:
        """All memory files that should be indexed."""
        files: list[Path] = []

        # Daily logs
        if DAILY_LOGS.exists():
            files.extend(sorted(DAILY_LOGS.glob("*.md")))

        # Core memory files
        for name in ("MEMORY.md", "USER.md", "SOUL.md"):
            p = MEMORY_DIR / name
            if p.exists():
                files.append(p)

        return files

    # ── Index operations ───────────────────────────────────────────────────────

    def index_all(self, force: bool = False) -> dict:
        """
        Index all memory files. Skips unchanged files unless force=True.
        Returns summary: {indexed, skipped, chunks_added}
        """
        files   = self._files_to_index()
        indexed = 0
        skipped = 0
        added   = 0

        for path in files:
            try:
                mtime = path.stat().st_mtime
            except OSError:
                continue

            if not force:
                row = self._conn.execute(
                    "SELECT mtime FROM indexed_files WHERE path = ?",
                    (str(path),),
                ).fetchone()
                if row and abs(row["mtime"] - mtime) < 0.5:
                    skipped += 1
                    continue

            n = self._index_file(path, mtime)
            added   += n
            indexed += 1

        self._conn.commit()
        logger.info(f"[search] index_all: indexed={indexed}, skipped={skipped}, chunks_added={added}")
        return {"indexed": indexed, "skipped": skipped, "chunks_added": added}

    def reindex_changed(self) -> dict:
        """
        Called hourly. Re-indexes files modified since last index run.
        Also indexes new daily log files automatically.
        """
        return self.index_all(force=False)

    def _index_file(self, path: Path, mtime: float) -> int:
        """
        Index one file: chunk it, embed, upsert into DB.
        Returns number of chunks added/updated.
        """
        chunks = chunk_file(path)
        if not chunks:
            return 0

        texts      = [c["text"] for c in chunks]
        embeddings = _embed(texts)          # shape [N, dim] or None

        now_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

        # Delete old chunks from this source before re-inserting
        old_ids = [
            row["chunk_id"]
            for row in self._conn.execute(
                "SELECT chunk_id FROM memory_chunks WHERE source = ?",
                (str(path.relative_to(ROOT)),),
            )
        ]
        if old_ids:
            self._conn.executemany(
                "DELETE FROM memory_fts WHERE chunk_id = ?",
                [(cid,) for cid in old_ids],
            )
            self._conn.execute(
                f"DELETE FROM memory_chunks WHERE source = ?",
                (str(path.relative_to(ROOT)),),
            )

        for i, chunk in enumerate(chunks):
            emb_blob  = None
            emb_dim   = 0

            if embeddings is not None and i < len(embeddings):
                vec      = embeddings[i].astype(np.float32)
                emb_blob = vec.tobytes()
                emb_dim  = len(vec)

            self._conn.execute(
                """INSERT OR REPLACE INTO memory_chunks
                   (chunk_id, text, source, date_str, section, embedding, embed_dim, indexed_at)
                   VALUES (?,?,?,?,?,?,?,?)""",
                (
                    chunk["chunk_id"],
                    chunk["text"],
                    chunk["source"],
                    chunk["date_str"],
                    chunk["section"],
                    emb_blob,
                    emb_dim,
                    now_str,
                ),
            )

            # FTS5 upsert — delete old row first
            self._conn.execute(
                "INSERT INTO memory_fts(chunk_id, text, source, date_str, section) VALUES(?,?,?,?,?)",
                (
                    chunk["chunk_id"],
                    chunk["text"],
                    chunk["source"],
                    chunk["date_str"],
                    chunk["section"],
                ),
            )

        # Update file tracking
        self._conn.execute(
            """INSERT OR REPLACE INTO indexed_files(path, mtime, chunk_count, indexed_at)
               VALUES(?,?,?,?)""",
            (str(path), mtime, len(chunks), now_str),
        )

        logger.debug(f"[search] indexed {path.name}: {len(chunks)} chunks")
        return len(chunks)

    # ── Search ─────────────────────────────────────────────────────────────────

    def search(self, query: str, k: int = 5) -> list[dict]:
        """
        Hybrid search: 70% vector cosine similarity + 30% FTS5 BM25.

        Returns top-k results:
          [{text, source, date_str, section, score, match_type}]
        """
        query = query.strip()
        if not query:
            return []

        # ── FTS5 keyword search ────────────────────────────────────────────────
        # Escape special FTS5 chars
        safe_q = re.sub(r'[^\w\s]', ' ', query).strip()
        fts_rows: dict[str, float] = {}

        if safe_q:
            try:
                rows = self._conn.execute(
                    """SELECT mc.chunk_id, mc.text, mc.source, mc.date_str, mc.section,
                              mc.embedding, mc.embed_dim, -bm25(memory_fts) AS bm25_raw
                       FROM memory_fts
                       JOIN memory_chunks mc ON mc.chunk_id = memory_fts.chunk_id
                       WHERE memory_fts MATCH ?
                       ORDER BY bm25_raw DESC
                       LIMIT 40""",
                    (safe_q,),
                ).fetchall()

                # Normalize BM25 scores to [0, 1]
                raw_scores = [r["bm25_raw"] for r in rows]
                max_bm25   = max(raw_scores, default=1.0) or 1.0

                for r in rows:
                    fts_rows[r["chunk_id"]] = {
                        "text":     r["text"],
                        "source":   r["source"],
                        "date_str": r["date_str"],
                        "section":  r["section"],
                        "embedding": r["embedding"],
                        "embed_dim": r["embed_dim"],
                        "bm25":      r["bm25_raw"] / max_bm25,
                    }
            except sqlite3.OperationalError as e:
                logger.warning(f"[search] FTS5 error: {e}")

        # ── Vector search ──────────────────────────────────────────────────────
        q_emb = _embed([query])
        vec_rows: dict[str, float] = {}

        if q_emb is not None:
            qvec = q_emb[0]  # shape [dim]

            # Load all stored embeddings — for small corpora (<10k chunks) this is fast
            stored = self._conn.execute(
                "SELECT chunk_id, text, source, date_str, section, embedding, embed_dim FROM memory_chunks WHERE embedding IS NOT NULL"
            ).fetchall()

            for row in stored:
                if row["embed_dim"] != _embed_dim:
                    continue  # embedder changed — skip stale embeddings
                vec = np.frombuffer(row["embedding"], dtype=np.float32)
                score = float(np.dot(qvec, vec))  # both are unit-normed by _embed
                if score > 0.1:  # ignore near-zero matches
                    vec_rows[row["chunk_id"]] = {
                        "text":     row["text"],
                        "source":   row["source"],
                        "date_str": row["date_str"],
                        "section":  row["section"],
                        "vscore":   score,
                    }

        # Normalize vector scores
        v_scores = [v["vscore"] for v in vec_rows.values()] if vec_rows else [1.0]
        max_v    = max(v_scores, default=1.0) or 1.0
        for v in vec_rows.values():
            v["vscore"] = v["vscore"] / max_v

        # ── Merge + hybrid score ───────────────────────────────────────────────
        all_ids = set(fts_rows) | set(vec_rows)
        results = []

        for cid in all_ids:
            fts = fts_rows.get(cid, {})
            vec = vec_rows.get(cid, {})

            vscore   = vec.get("vscore", 0.0)
            bm25     = fts.get("bm25",   0.0)
            hybrid   = VECTOR_W * vscore + KEYWORD_W * bm25

            info = fts or vec
            results.append({
                "text":       info.get("text",     ""),
                "source":     info.get("source",   ""),
                "date_str":   info.get("date_str", ""),
                "section":    info.get("section",  ""),
                "score":      round(hybrid, 4),
                "vscore":     round(vscore, 4),
                "bm25":       round(bm25, 4),
                "match_type": (
                    "hybrid"  if cid in fts_rows and cid in vec_rows else
                    "vector"  if cid in vec_rows else
                    "keyword"
                ),
            })

        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:k]

    # ── Stats ──────────────────────────────────────────────────────────────────

    def stats(self) -> dict:
        """Return index statistics for /reflect or debug use."""
        total = self._conn.execute("SELECT COUNT(*) FROM memory_chunks").fetchone()[0]
        files = self._conn.execute("SELECT COUNT(*) FROM indexed_files").fetchone()[0]
        dates = self._conn.execute(
            "SELECT COUNT(DISTINCT date_str) FROM memory_chunks WHERE date_str != ''"
        ).fetchone()[0]
        return {
            "total_chunks": total,
            "indexed_files": files,
            "daily_logs_indexed": dates,
            "embedder": _embed_name,
            "db_path": str(SEARCH_DB),
        }

    def close(self):
        self._conn.close()


# ── Singleton + public API ─────────────────────────────────────────────────────

_indexer: Optional[MemoryIndexer] = None


def get_indexer() -> MemoryIndexer:
    """Get or create the singleton MemoryIndexer."""
    global _indexer
    if _indexer is None:
        _indexer = MemoryIndexer()
    return _indexer


def search(query: str, k: int = 5) -> list[dict]:
    """
    Hybrid memory search. Returns top-k relevant chunks.

    Example:
        results = search("PEAD backtest results", k=5)
        for r in results:
            print(r["date_str"], r["section"], r["text"][:100])
    """
    return get_indexer().search(query, k)


def format_results(results: list[dict], max_chars: int = 1200) -> str:
    """
    Format search results as a readable Telegram-safe string.
    Truncates to max_chars total.
    """
    if not results:
        return "No relevant memory found."

    lines: list[str] = []
    total = 0

    for i, r in enumerate(results, 1):
        source = Path(r["source"]).name
        date   = r["date_str"] or "—"
        sec    = r["section"] or "—"
        snippet = r["text"].replace("\n", " ").strip()[:200]

        entry = f"[{i}] {date} › {sec} ({source})\n{snippet}"
        if total + len(entry) > max_chars:
            break
        lines.append(entry)
        total += len(entry)

    return "\n\n".join(lines)


# ── CLI test ───────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    idx = MemoryIndexer()
    print("\n▶ Indexing all memory files...")
    summary = idx.index_all(force=True)
    print(f"  {summary}")
    print(f"  Stats: {idx.stats()}")

    queries = sys.argv[1:] or [
        "PEAD backtest results",
        "study abroad London appeal",
        "what workouts did I do",
        "focus for today",
    ]

    for q in queries:
        print(f"\n▶ Search: '{q}'")
        results = idx.search(q, k=3)
        for r in results:
            print(f"  score={r['score']:.3f} [{r['match_type']}]  {r['date_str']} › {r['section']}")
            print(f"    {r['text'][:120].replace(chr(10), ' ')}")
