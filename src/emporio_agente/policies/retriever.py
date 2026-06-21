"""Policy retriever.

Lightweight RAG over the policy manual:

- Section-aware chunks (see ``chunker``).
- Local embeddings via sentence-transformers (BGE-M3 by default), computed once
  and cached to disk.
- Retrieval = cosine similarity in numpy. With ~9 chunks there is no need for a
  vector database; an in-memory matrix is faster, simpler, and fully
  reproducible. Rejecting a vector DB here is a deliberate scale-appropriate
  choice, mirroring the decision not to embed the structured data.
- A keyword fallback boosts exact-fact lookups (CNPJ, "sábado", "boleto") that
  pure semantic similarity can miss.

The embedding model is loaded lazily so importing the package (e.g. for the
data-layer tests) never pays the model-load cost.
"""

from __future__ import annotations

import pickle
import re
import warnings
from pathlib import Path

import numpy as np

_MINILM = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"

from ..config import EMBEDDING_CACHE, EMBEDDING_MODEL, POLICY_PDF, RETRIEVAL_TOP_K
from ..models import PolicyAnswer, PolicyChunk
from .chunker import load_policy_chunks

_WORD_RE = re.compile(r"[a-zà-ÿ0-9]+", re.IGNORECASE)


def _tokens(text: str) -> set[str]:
    return {t.lower() for t in _WORD_RE.findall(text) if len(t) > 2}


class PolicyRetriever:
    """Embeds policy chunks once and answers queries by hybrid similarity."""

    def __init__(
        self,
        pdf_path: Path | str = POLICY_PDF,
        model_name: str = EMBEDDING_MODEL,
        cache_path: Path | str = EMBEDDING_CACHE,
        top_k: int = RETRIEVAL_TOP_K,
    ) -> None:
        self.pdf_path = Path(pdf_path)
        self.model_name = model_name
        self.cache_path = Path(cache_path)
        self.top_k = top_k
        self._model = None
        self.chunks: list[PolicyChunk] = []
        self._matrix: np.ndarray | None = None

    # -- Lazy model load ----------------------------------------------------
    @property
    def model(self):
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
            except ImportError as exc:
                raise RuntimeError(
                    "O pacote 'sentence-transformers' não está instalado, mas é "
                    "necessário para o RAG de políticas. Instale com "
                    "`pip install -e .` (ou `pip install sentence-transformers`). "
                    f"Para um download mais leve, defina EMPORIO_EMBEDDING_MODEL={_MINILM}."
                ) from exc
            try:
                self._model = SentenceTransformer(self.model_name)
            except Exception as exc:
                raise RuntimeError(
                    f"Falha ao carregar o modelo de embeddings '{self.model_name}': "
                    f"{exc}. O modelo é baixado na primeira execução — verifique a "
                    f"conexão, ou use um modelo mais leve definindo "
                    f"EMPORIO_EMBEDDING_MODEL={_MINILM}."
                ) from exc
        return self._model

    def _embed(self, texts: list[str]) -> np.ndarray:
        vecs = self.model.encode(
            texts, normalize_embeddings=True, show_progress_bar=False
        )
        return np.asarray(vecs, dtype=np.float32)

    # -- Index build / load -------------------------------------------------
    def build(self, use_cache: bool = True) -> "PolicyRetriever":
        if use_cache and self.cache_path.exists() and self._load_cache():
            return self

        self.chunks = load_policy_chunks(self.pdf_path)
        self._matrix = self._embed([c.text for c in self.chunks])
        self._save_cache()
        return self

    def _load_cache(self) -> bool:
        """Load embeddings from the cache, returning ``False`` to trigger a
        rebuild when the cache is corrupt/unreadable or was built with a
        different embedding model (so a stale cache never crashes startup)."""
        try:
            with open(self.cache_path, "rb") as fh:
                payload = pickle.load(fh)
            if payload.get("model_name") != self.model_name:
                return False  # built with a different model -> rebuild
            self.chunks = [PolicyChunk(**c) for c in payload["chunks"]]
            self._matrix = payload["matrix"]
            return True
        except (
            pickle.UnpicklingError, EOFError, AttributeError, ImportError,
            ModuleNotFoundError, KeyError, TypeError, ValueError, OSError,
        ) as exc:
            warnings.warn(
                f"Cache de embeddings inválido em {self.cache_path} ({exc}); "
                "reconstruindo do zero.",
                RuntimeWarning,
                stacklevel=2,
            )
            return False

    def _save_cache(self) -> None:
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.cache_path, "wb") as fh:
            pickle.dump(
                {
                    "model_name": self.model_name,
                    "chunks": [c.model_dump() for c in self.chunks],
                    "matrix": self._matrix,
                },
                fh,
            )

    # -- Query --------------------------------------------------------------
    def search(self, query: str, top_k: int | None = None) -> PolicyAnswer:
        if self._matrix is None:
            self.build()
        k = top_k or self.top_k

        q_vec = self._embed([query])[0]
        semantic = self._matrix @ q_vec  # cosine (vectors are normalised)

        # Keyword overlap as a light boost for exact-fact lookups.
        q_tokens = _tokens(query)
        keyword = np.array(
            [
                len(q_tokens & _tokens(c.text)) / (len(q_tokens) or 1)
                for c in self.chunks
            ],
            dtype=np.float32,
        )

        scores = 0.85 * semantic + 0.15 * keyword
        order = np.argsort(-scores)[:k]

        results = [
            PolicyChunk(
                section_id=self.chunks[i].section_id,
                title=self.chunks[i].title,
                text=self.chunks[i].text,
                score=float(scores[i]),
            )
            for i in order
        ]
        return PolicyAnswer(query=query, chunks=results)
