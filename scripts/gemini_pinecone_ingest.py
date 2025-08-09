"""
Gemini + Pinecone Ingestion and Search Script

This script provides a production-ready CLI for:
- Generating text embeddings using Google Gemini's text-embedding-004 model.
- Creating/using a Pinecone serverless index and upserting vectors with rich metadata.
- Ingesting content from files/directories and/or inline strings, plus query-only mode.

Design notes:
- Chunking defaults (chunk_size=1000, chunk_overlap=200) balance retrieval recall and cost.
  Tune as needed for your corpus. Embedding cost scales with total characters processed.
- Robust retries with exponential backoff + jitter are implemented for embedding and upserts.
  This reduces flakiness from transient 429/5xx/network issues.
- Deterministic vector IDs use sha256(source_id:chunk_index:chunk_text) to enable stable
  re-ingestion without duplication.

Setup & Run
-----------
Install dependencies (pypdf optional for PDFs; python-dotenv optional for .env loading):
  pip install google-generativeai pinecone pypdf python-dotenv

Required environment variables:
  export GOOGLE_API_KEY="YOUR_GOOGLE_API_KEY"
  export PINECONE_API_KEY="YOUR_PINECONE_API_KEY"

Optional environment variables:
  export PINECONE_CLOUD="aws"            # or "gcp"
  export PINECONE_REGION="us-east-1"     # e.g., "us-east-1"
  export INDEX_NAME="gemini-rag"
  export NAMESPACE=""

Example commands:
- Ingest a directory:
  python scripts/gemini_pinecone_ingest.py --input-path ./docs --index-name my-index --namespace default

- Query only (assuming indexed):
  python scripts/gemini_pinecone_ingest.py --index-name my-index --namespace default --query "What is Bitcoin?" --top-k 5

- Mixed inline texts + directory:
  python scripts/gemini_pinecone_ingest.py --input-path ./notes --text "Extra inline text A" --text "Another string"
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import random
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

# Optional dotenv support for local development
try:
    from dotenv import load_dotenv  # type: ignore
except Exception:
    load_dotenv = None  # type: ignore

# Google Generative AI (Gemini) embeddings
try:
    import google.generativeai as genai  # type: ignore
except Exception as e:
    genai = None  # type: ignore

# Pinecone SDK v5+
try:
    from pinecone import Pinecone, ServerlessSpec  # type: ignore
except Exception as e:
    Pinecone = None  # type: ignore
    ServerlessSpec = None  # type: ignore


@dataclass
class Document:
    source_id: str      # absolute path or "inline:N"
    content_type: str   # "txt" | "md" | "pdf" | "inline"
    filename: str       # filename for files; "inline:N" for inline
    text: str


def setup_logger() -> logging.Logger:
    """
    Configure structured logging. Avoid printing sensitive data.
    """
    logger = logging.getLogger("gemini_pinecone_ingest")
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    return logger


def normalize_text(text: str) -> str:
    """
    Normalize line endings and trim excessive surrounding whitespace.
    """
    if not text:
        return ""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    # Collapse trailing spaces on each line
    lines = [ln.rstrip() for ln in text.split("\n")]
    normalized = "\n".join(lines).strip()
    return normalized


def chunk_text(text: str, chunk_size: int, chunk_overlap: int) -> List[str]:
    """
    Chunk text into overlapping windows.

    Rationale:
      chunk_size=1000 and chunk_overlap=200 usually balance recall and cost for many corpora,
      but tune per dataset. Overlap preserves context across chunk boundaries.
    """
    chunks: List[str] = []
    if chunk_size <= 0:
        raise ValueError("chunk_size must be > 0")
    if chunk_overlap < 0:
        raise ValueError("chunk_overlap must be >= 0")
    if chunk_overlap >= chunk_size:
        # Ensure forward progress
        chunk_overlap = max(0, chunk_size // 4)

    text = normalize_text(text)
    if not text:
        return chunks

    n = len(text)
    start = 0
    while start < n:
        end = min(start + chunk_size, n)
        window = text[start:end]
        # Try to end at whitespace to avoid breaking words
        if end < n:
            last_space = window.rfind(" ")
            if last_space > 0 and last_space >= int(0.6 * len(window)):
                window = window[:last_space]
                end = start + last_space
        w = window.strip()
        if w:
            chunks.append(w)
        if end >= n:
            break
        start = max(0, end - chunk_overlap)
    return chunks


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def deterministic_vector_id(source_id: str, chunk_index: int, chunk_text: str) -> str:
    raw = f"{source_id}:{chunk_index}:{chunk_text}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def read_txt_or_md(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        # Fallback to binary decode
        try:
            return path.read_bytes().decode("utf-8", errors="ignore")
        except Exception:
            return ""


def read_pdf(path: Path, logger: logging.Logger) -> str:
    """
    Best-effort PDF extraction using pypdf. If unavailable or extraction fails, return empty string.
    """
    try:
        from pypdf import PdfReader  # type: ignore
    except Exception:
        logger.warning(json.dumps({
            "event": "pdf_skip",
            "reason": "pypdf_not_installed",
            "path": str(path)
        }))
        return ""
    try:
        reader = PdfReader(str(path))
        out = []
        for page in reader.pages:
            try:
                out.append(page.extract_text() or "")
            except Exception:
                continue
        return "\n".join(out)
    except Exception as e:
        logger.warning(json.dumps({
            "event": "pdf_skip",
            "reason": "read_error",
            "path": str(path)
        }))
        return ""


def enumerate_files(input_path: Path) -> List[Path]:
    if input_path.is_dir():
        # Recurse and include .txt, .md, .pdf
        return [
            p for p in input_path.rglob("*")
            if p.is_file() and p.suffix.lower() in {".txt", ".md", ".pdf"}
        ]
    else:
        return [input_path]


def collect_documents(input_path: Optional[str], inline_texts: Sequence[str], logger: logging.Logger) -> List[Document]:
    docs: List[Document] = []
    # Files/directories
    if input_path:
        p = Path(input_path).expanduser().resolve()
        if not p.exists():
            raise FileNotFoundError(f"Input path not found: {p}")
        for fp in enumerate_files(p):
            ext = fp.suffix.lower()
            if ext == ".txt":
                content_type = "txt"
                text = read_txt_or_md(fp)
            elif ext == ".md":
                content_type = "md"
                text = read_txt_or_md(fp)
            elif ext == ".pdf":
                content_type = "pdf"
                text = read_pdf(fp, logger)
            else:
                continue
            text = normalize_text(text)
            source_id = str(fp.resolve())
            docs.append(Document(
                source_id=source_id,
                content_type=content_type,
                filename=fp.name,
                text=text
            ))
    # Inline texts
    for i, t in enumerate(inline_texts):
        source_id = f"inline:{i+1}"
        docs.append(Document(
            source_id=source_id,
            content_type="inline",
            filename=source_id,
            text=normalize_text(t or "")
        ))
    return docs


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def backoff_sleep(attempt: int, base: float = 0.5, cap: float = 10.0) -> None:
    """
    Exponential backoff with jitter. attempt starts at 1.
    """
    exp = min(cap, base * (2 ** (attempt - 1)))
    jitter = random.uniform(0, exp / 2.0)
    time.sleep(exp + jitter)


def extract_embedding(result: object) -> Optional[List[float]]:
    """
    Defensive extraction of embedding vector from google-generativeai response.
    """
    if result is None:
        return None
    # Typical shapes observed:
    # - {"embedding": {"values": [...]}}
    # - {"embedding": [...]}
    try:
        if isinstance(result, dict):
            emb = result.get("embedding")
            if emb is None:
                return None
            if isinstance(emb, dict) and "values" in emb:
                v = emb.get("values")
                if isinstance(v, list) and v and isinstance(v[0], (int, float)):
                    return [float(x) for x in v]
            if isinstance(emb, list):
                if emb and isinstance(emb[0], (int, float)):
                    return [float(x) for x in emb]
        # Some versions may return an object with .embedding attribute
        emb = getattr(result, "embedding", None)
        if emb is not None:
            if isinstance(emb, dict) and "values" in emb:
                v = emb.get("values")
                if isinstance(v, list) and v and isinstance(v[0], (int, float)):
                    return [float(x) for x in v]
            if isinstance(emb, list):
                if emb and isinstance(emb[0], (int, float)):
                    return [float(x) for x in emb]
    except Exception:
        return None
    return None


def embed_text(
    text: str,
    task_type: str,
    logger: logging.Logger,
    max_retries: int = 5,
    per_request_delay: float = 0.05,
) -> List[float]:
    """
    Get embedding from Gemini with retries. task_type in {"retrieval_document", "retrieval_query"}.
    """
    if genai is None:
        raise RuntimeError("google-generativeai is not installed.")
    last_err: Optional[Exception] = None
    for attempt in range(1, max_retries + 1):
        try:
            # Respect a small client-side delay to smooth QPS
            if per_request_delay > 0:
                time.sleep(per_request_delay)
            res = genai.embed_content(
                model="models/text-embedding-004",
                content=text,
                task_type=task_type,
            )
            vec = extract_embedding(res)
            if not vec:
                raise RuntimeError("Empty embedding received")
            return vec
        except Exception as e:
            last_err = e
            logger.warning(json.dumps({
                "event": "embed_retry",
                "attempt": attempt,
                "task_type": task_type,
                "error": repr(e)
            }))
            if attempt < max_retries:
                backoff_sleep(attempt)
    # After retries exhausted
    raise RuntimeError(f"Embedding failed after {max_retries} retries: {last_err}")


def ensure_index(
    pc: "Pinecone",
    index_name: str,
    dimension: int,
    cloud: str,
    region: str,
    logger: logging.Logger,
) -> None:
    """
    Create Pinecone serverless index if it doesn't exist, then wait for readiness.
    """
    names = set(pc.list_indexes().names())
    if index_name not in names:
        logger.info(json.dumps({
            "event": "create_index",
            "index_name": index_name,
            "dimension": dimension,
            "metric": "cosine",
            "cloud": cloud,
            "region": region
        }))
        pc.create_index(
            name=index_name,
            dimension=dimension,
            metric="cosine",
            spec=ServerlessSpec(cloud=cloud, region=region),
        )
    # Wait readiness
    while True:
        try:
            desc = pc.describe_index(index_name)
            ready = bool(getattr(desc, "status", {}).get("ready", False))
            if ready:
                break
        except Exception as e:
            logger.warning(json.dumps({
                "event": "wait_index_error",
                "index_name": index_name,
                "error": repr(e)
            }))
        backoff_sleep(1)
    logger.info(json.dumps({
        "event": "index_ready",
        "index_name": index_name
    }))


def upsert_batch_with_retry(
    index,
    vectors: List[Dict],
    namespace: str,
    logger: logging.Logger,
    max_retries: int = 5,
) -> bool:
    """
    Upsert a single batch with retries. Returns True if success, False if failed after retries.
    """
    last_err: Optional[Exception] = None
    for attempt in range(1, max_retries + 1):
        try:
            index.upsert(vectors=vectors, namespace=namespace)
            return True
        except Exception as e:
            last_err = e
            logger.warning(json.dumps({
                "event": "upsert_retry",
                "attempt": attempt,
                "batch_size": len(vectors),
                "error": repr(e)
            }))
            if attempt < max_retries:
                backoff_sleep(attempt)
    logger.error(json.dumps({
        "event": "upsert_failed",
        "batch_size": len(vectors),
        "error": repr(last_err)
    }))
    return False


def build_metadata(
    doc: Document,
    chunk_index: int,
    total_chunks: int,
    chunk_text: str,
) -> Dict:
    return {
        "source": doc.source_id,
        "chunk_index": chunk_index,
        "total_chunks": total_chunks,
        "sha256": sha256_text(chunk_text),
        "timestamp": utc_timestamp(),
        "size_chars": len(chunk_text),
        "filename": doc.filename,
        "content_type": doc.content_type,
        # A short snippet for operator validation without logging entire content
        "snippet": chunk_text[:200],
    }


def query_and_print(
    pc: "Pinecone",
    index_name: str,
    namespace: str,
    query_text: str,
    top_k: int,
    logger: logging.Logger,
) -> None:
    index = pc.Index(index_name)
    qvec = embed_text(query_text, task_type="retrieval_query", logger=logger)
    res = index.query(
        vector=qvec,
        top_k=top_k,
        include_metadata=True,
        namespace=namespace,
    )
    matches = getattr(res, "matches", []) or res.get("matches", []) if isinstance(res, dict) else []
    print("\nTop matches:")
    for i, m in enumerate(matches, 1):
        mid = m.get("id") if isinstance(m, dict) else getattr(m, "id", "")
        score = m.get("score") if isinstance(m, dict) else getattr(m, "score", 0.0)
        md = m.get("metadata") if isinstance(m, dict) else getattr(m, "metadata", {}) or {}
        src = md.get("source", "")
        cidx = md.get("chunk_index", "")
        tchunks = md.get("total_chunks", "")
        snippet = md.get("snippet", "")
        print(f"{i:>2}. id={mid} score={score:.4f} source={src} [{cidx}/{tchunks}]")
        if snippet:
            print(f"    snippet: {snippet[:160].replace('\\n', ' ')}")


def parse_args() -> argparse.Namespace:
    env = os.environ
    parser = argparse.ArgumentParser(description="Gemini embeddings -> Pinecone ingestion & search")
    parser.add_argument("--input-path", type=str, default=None, help="Path to a file or directory to ingest")
    parser.add_argument("--text", action="append", default=[], help="Inline text to ingest (repeatable)")
    parser.add_argument("--index-name", type=str, default=env.get("INDEX_NAME", "gemini-rag"))
    parser.add_argument("--namespace", type=str, default=env.get("NAMESPACE", ""))
    parser.add_argument("--batch-size", type=int, default=100, help="Upsert batch size (max 100)")
    parser.add_argument("--chunk-size", type=int, default=1000, help="Chunk size in characters")
    parser.add_argument("--chunk-overlap", type=int, default=200, help="Chunk overlap in characters")
    parser.add_argument("--cloud", type=str, default=env.get("PINECONE_CLOUD", "aws"), help="Pinecone serverless cloud (aws/gcp)")
    parser.add_argument("--region", type=str, default=env.get("PINECONE_REGION", "us-east-1"), help="Pinecone serverless region (e.g., us-east-1)")
    parser.add_argument("--top-k", type=int, default=5, help="Top-K for semantic search")
    parser.add_argument("--query", type=str, default=None, help="Optional query string for semantic search after ingestion")
    parser.add_argument("--log-level", type=str, default="INFO", help="Logging level (DEBUG, INFO, WARNING, ERROR)")
    return parser.parse_args()


def main() -> None:
    if load_dotenv:
        try:
            load_dotenv()
        except Exception:
            pass
    logger = setup_logger()
    args = parse_args()
    logger.setLevel(getattr(logging, args.log_level.upper(), logging.INFO))

    start_time = time.time()
    env = os.environ

    input_path = args.input_path
    inline_texts: List[str] = args.text or []
    index_name = args.index_name
    namespace = args.namespace
    batch_size = max(1, min(100, int(args.batch_size)))  # hard cap 100
    chunk_size = max(1, int(args.chunk_size))
    chunk_overlap = max(0, int(args.chunk_overlap))
    
    # Validate chunk parameters
    if chunk_overlap >= chunk_size:
        logger.error(json.dumps({
            "event": "invalid_args",
            "reason": "chunk_overlap_must_be_less_than_chunk_size",
            "chunk_overlap": chunk_overlap,
            "chunk_size": chunk_size
        }))
        sys.exit(2)
    
    cloud = args.cloud
    region = args.region
    top_k = max(1, int(args.top_k))
    query_text = args.query

    # Determine operational mode
    ingest_mode = bool(input_path or inline_texts)
    query_mode = bool(query_text)
    if not ingest_mode and not query_mode:
        logger.error(json.dumps({
            "event": "invalid_args",
            "reason": "no_input_and_no_query"
        }))
        sys.exit(2)

    # Validate API keys depending on actions
    google_api_key = env.get("GOOGLE_API_KEY")
    pinecone_api_key = env.get("PINECONE_API_KEY")

    if ( ingest_mode or query_mode ):
        # Query embeds require Gemini; ingestion requires both Gemini + Pinecone
        if not google_api_key:
            logger.error(json.dumps({"event": "missing_env", "var": "GOOGLE_API_KEY"}))
            sys.exit(2)
    if ( ingest_mode or query_mode ):
        if not pinecone_api_key:
            logger.error(json.dumps({"event": "missing_env", "var": "PINECONE_API_KEY"}))
            sys.exit(2)

    # Configure Gemini
    if genai is None:
        logger.error(json.dumps({"event": "missing_dependency", "package": "google-generativeai"}))
        sys.exit(2)
    try:
        genai.configure(api_key=google_api_key)
    except Exception as e:
        logger.error(json.dumps({"event": "genai_config_error", "error": repr(e)}))
        sys.exit(2)

    # Pinecone client
    if Pinecone is None or ServerlessSpec is None:
        logger.error(json.dumps({"event": "missing_dependency", "package": "pinecone"}))
        sys.exit(2)
    try:
        pc = Pinecone(api_key=pinecone_api_key)
    except Exception as e:
        logger.error(json.dumps({"event": "pinecone_init_error", "error": repr(e)}))
        sys.exit(2)

    # Prepare documents
    docs: List[Document] = []
    if ingest_mode:
        try:
            docs = collect_documents(input_path, inline_texts, logger)
        except Exception as e:
            logger.error(json.dumps({"event": "collect_documents_error", "error": repr(e)}))
            sys.exit(2)

    files_processed = 0
    total_chunks = 0
    total_chunks_skipped_empty = 0
    total_chunks_dedup_skipped = 0
    vectors_upserted = 0
    vectors_failed = 0
    embedding_dimension: Optional[int] = None

    dedup_hashes: set[str] = set()

    # Early validation: generate test embedding to get dimension and ensure index
    if ingest_mode and docs:
        try:
            test_embedding = embed_text(
                "Test embedding for dimension detection",
                task_type="retrieval_document",
                logger=logger
            )
            embedding_dimension = len(test_embedding)
            
            # Ensure index exists and is ready
            ensure_index(pc, index_name, embedding_dimension, cloud, region, logger)
            
            # Get index handle once upfront
            index = pc.Index(index_name)
            
            logger.info(json.dumps({
                "event": "ingest_start",
                "doc_count": len(docs),
                "index_name": index_name,
                "namespace": namespace,
                "cloud": cloud,
                "region": region,
                "dimension": embedding_dimension
            }))
            
        except Exception as e:
            logger.error(json.dumps({
                "event": "initialization_error",
                "error": repr(e)
            }))
            sys.exit(2)

    # Process documents -> chunk -> embed -> upsert
    batch: List[Dict] = []
    if ingest_mode:
        for doc in docs:
            if doc.content_type != "inline":
                files_processed += 1
            chunks = chunk_text(doc.text, chunk_size=chunk_size, chunk_overlap=chunk_overlap)
            doc_total = len(chunks)
            total_chunks += doc_total
            if doc_total == 0:
                total_chunks_skipped_empty += 1  # count as one empty doc
            for cidx, chunk in enumerate(chunks):
                if not chunk.strip():
                    total_chunks_skipped_empty += 1
                    continue
                c_hash = sha256_text(chunk)
                if c_hash in dedup_hashes:
                    total_chunks_dedup_skipped += 1
                    continue
                dedup_hashes.add(c_hash)

                # Embed
                try:
                    vec = embed_text(chunk, task_type="retrieval_document", logger=logger)
                except Exception as e:
                    logger.error(json.dumps({
                        "event": "embed_error",
                        "source": doc.source_id,
                        "chunk_index": cidx,
                        "error": repr(e)
                    }))
                    vectors_failed += 1
                    continue

                # Build vector payload
                vec_id = deterministic_vector_id(doc.source_id, cidx, chunk)
                metadata = build_metadata(doc, cidx, doc_total, chunk)
                batch.append({"id": vec_id, "values": vec, "metadata": metadata})

                # Upsert if batch full
                if len(batch) >= batch_size:
                    ok = upsert_batch_with_retry(index, batch, namespace, logger)
                    if ok:
                        vectors_upserted += len(batch)
                    else:
                        vectors_failed += len(batch)
                    batch = []

        # Flush remainder
        if batch:
            ok = upsert_batch_with_retry(index, batch, namespace, logger)
            if ok:
                vectors_upserted += len(batch)
            else:
                vectors_failed += len(batch)
            batch = []

    # Query
    if query_mode:
        try:
            # Ensure index handle (in case of query-only mode)
            if not ingest_mode:
                # For query-only we don't know dimension; just ensure index exists logically
                # This will not create index; it assumes the index is already present
                try:
                    names = set(pc.list_indexes().names())
                except Exception:
                    names = set()
                if index_name not in names:
                    logger.error(json.dumps({
                        "event": "query_index_missing",
                        "index_name": index_name,
                        "message": f"Index '{index_name}' not found. Please run the ingestion process first to create the index before attempting to query."
                    }))
                    sys.exit(2)
                index = pc.Index(index_name)
            query_and_print(pc, index_name, namespace, query_text, top_k, logger)
        except Exception as e:
            logger.error(json.dumps({
                "event": "query_error",
                "error": repr(e)
            }))
            sys.exit(2)

    elapsed = time.time() - start_time
    # Final summary
    summary = {
        "event": "summary",
        "vectors_upserted": vectors_upserted,
        "vectors_failed": vectors_failed,
        "index_name": index_name,
        "namespace": namespace,
        "dimension": embedding_dimension,
        "cloud": cloud,
        "region": region,
        "files_processed": files_processed,
        "chunks_total": total_chunks,
        "chunks_skipped_empty": total_chunks_skipped_empty,
        "chunks_skipped_dedup": total_chunks_dedup_skipped,
        "elapsed_sec": round(elapsed, 2),
    }
    logger.info(json.dumps(summary))


if __name__ == "__main__":
    main()