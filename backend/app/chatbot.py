from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np
import requests
import faiss


# =========================
# Config
# =========================
BASE_DIR = Path(__file__).resolve().parents[1]
STORE_DIR = BASE_DIR / "data" / "rag_store_chunks"
FAISS_PATH = STORE_DIR / "index.faiss"
META_PATH  = STORE_DIR / "meta.jsonl"
TEXT_PATH  = STORE_DIR / "texts.jsonl"

OLLAMA_URL  = os.getenv("OLLAMA_URL", "http://localhost:11434")
CHAT_MODEL  = os.getenv("CHAT_MODEL", "llama3.1:8b")
EMBED_MODEL = os.getenv("EMBED_MODEL", "nomic-embed-text")

TOP_K = 5
MIN_SIM_FOR_RAG = 0.28  # ajusta: 0.22 más permisivo, 0.33 más estricto
MAX_CONTEXT_CHARS = 6500
TIMEOUT_S = int(os.getenv("OLLAMA_TIMEOUT_S", "240"))


# =========================
# Ollama
# =========================
def ollama_embedding(text: str, model: str = EMBED_MODEL) -> np.ndarray:
    r = requests.post(
        f"{OLLAMA_URL}/api/embeddings",
        json={"model": model, "prompt": text},
        timeout=TIMEOUT_S,
    )
    r.raise_for_status()
    return np.array(r.json()["embedding"], dtype=np.float32)


def ollama_chat(messages: List[Dict[str, str]], model: str = CHAT_MODEL) -> str:
    r = requests.post(
        f"{OLLAMA_URL}/api/chat",
        json={"model": model, "messages": messages, "stream": False},
        timeout=TIMEOUT_S,
    )
    r.raise_for_status()
    return r.json()["message"]["content"]


# =========================
# Helpers
# =========================
def l2_normalize_vec(x: np.ndarray, eps: float = 1e-12) -> np.ndarray:
    n = float(np.linalg.norm(x))
    return x / (n + eps)


def es_saludo(text: str) -> bool:
    t = text.strip().lower()
    return t in {"hola", "holaa", "hello", "buenas", "buenos dias", "buenas tardes", "buenas noches"}


def limpiar_texto(s: str) -> str:
    s = (s or "").replace("\x00", " ")
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()


def title_is_generic(title: str) -> bool:
    """
    Detecta títulos genéricos que NO quieres mostrar: "Chunk" o "Chunk 12".
    """
    t = (title or "").strip()
    if not t:
        return True
    if t.lower() == "chunk":
        return True
    if re.fullmatch(r"chunk\s*\d+", t.strip(), flags=re.IGNORECASE):
        return True
    return False


# =========================
# Load store
# =========================
def load_jsonl(path: Path) -> List[Dict[str, Any]]:
    out = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            out.append(json.loads(line))
    return out


def load_store() -> Tuple[faiss.Index, List[Dict[str, Any]], List[str]]:
    if not FAISS_PATH.exists():
        raise FileNotFoundError(f"No existe: {FAISS_PATH.resolve()}")
    if not META_PATH.exists():
        raise FileNotFoundError(f"No existe: {META_PATH.resolve()}")
    if not TEXT_PATH.exists():
        raise FileNotFoundError(f"No existe: {TEXT_PATH.resolve()}")

    index = faiss.read_index(str(FAISS_PATH))
    meta = load_jsonl(META_PATH)

    texts_json = load_jsonl(TEXT_PATH)
    texts = [r["text"] for r in texts_json]

    if len(meta) != len(texts):
        raise ValueError(f"Inconsistencia: meta={len(meta)} vs texts={len(texts)}")

    return index, meta, texts


# =========================
# Retrieval + context
# =========================
def retrieve(index: faiss.Index, meta: List[Dict[str, Any]], texts: List[str], query: str, topk: int = TOP_K):
    q = ollama_embedding(query)
    qn = l2_normalize_vec(q).astype(np.float32)

    D, I = index.search(qn.reshape(1, -1), topk)
    scores = D[0].tolist()
    idxs = I[0].tolist()

    results = []
    for score, idx in zip(scores, idxs):
        if idx < 0:
            continue
        m = meta[idx]
        t = texts[idx]
        results.append({
            "score": float(score),
            "pdf": m.get("pdf", ""),
            "chunk_id": m.get("chunk_id", None),
            "title": m.get("title", "") or "",
            "text": t,
        })
    return results


def build_context(results: List[Dict[str, Any]], max_chars: int = MAX_CONTEXT_CHARS) -> str:
    """
    Construye contexto con trazabilidad, omitiendo títulos genéricos (Chunk/Chunk N).
    """
    parts = []
    used = 0
    for r in results:
        pdf = r["pdf"]
        cid = r["chunk_id"]
        score = r["score"]
        title = r.get("title", "")

        # Header: sin "Chunk"
        if title_is_generic(title):
            header = f"[Fuente: {pdf} | id: {cid} | score={score:.3f}]"
        else:
            header = f"[Fuente: {pdf} | {title} | id: {cid} | score={score:.3f}]"

        body = limpiar_texto(r["text"])
        block = header + "\n" + body + "\n"

        if used + len(block) > max_chars:
            break
        parts.append(block)
        used += len(block)

    return "\n".join(parts).strip()


# =========================
# Chat
# =========================
def answer(user_msg: str, history: List[Dict[str, str]], index, meta, texts) -> str:
    if es_saludo(user_msg):
        return "hola"

    results = retrieve(index, meta, texts, user_msg, topk=TOP_K)
    best = results[0]["score"] if results else 0.0
    use_rag = best >= MIN_SIM_FOR_RAG

    system = (
        "Eres un asistente útil y conversacional.\n"
        "Reglas:\n"
        "- Si el usuario saluda, responde el saludo.\n"
        "- Si se entrega contexto documental, úsalo para responder con precisión.\n"
        "- No inventes datos; si el contexto no trae la respuesta, puedes dar una respuesta basada en lo que sabes.\n"
        "- Prioriza responder de forma clara y directa."
    )

    if use_rag:
        context = build_context(results)
        user_payload = (
            "CONTEXTO (fragmentos recuperados de documentos):\n"
            f"{context}\n\n"
            "PREGUNTA DEL USUARIO:\n"
            f"{user_msg}"
        )
    else:
        user_payload = user_msg

    messages = [{"role": "system", "content": system}]
    messages.extend(history[-12:])
    messages.append({"role": "user", "content": user_payload})
    return ollama_chat(messages, model=CHAT_MODEL)


def main():
    index, meta, texts = load_store()
    print("Store cargado:")
    print("- chunks:", len(texts))
    print("- dim:", index.d)
    print("\nChat listo. Escribe 'exit' para salir.\n")

    history: List[Dict[str, str]] = []

    while True:
        user_msg = input("Tú: ").strip()
        if not user_msg:
            continue
        if user_msg.lower() in {"exit", "quit", "salir"}:
            break

        try:
            ans = answer(user_msg, history, index, meta, texts)
        except Exception as e:
            ans = f"Ocurrió un error: {e}"

        print(f"Asistente: {ans}\n")

        history.append({"role": "user", "content": user_msg})
        history.append({"role": "assistant", "content": ans})


if __name__ == "__main__":
    main()
