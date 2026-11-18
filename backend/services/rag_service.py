import math
import re
from collections import Counter
from pathlib import Path
from typing import Dict, List, Optional

from backend.config.settings import ROOT_DIR
from backend.schemas.workflow_state import RetrievedDocument

KNOWLEDGE_BASE_DIR = ROOT_DIR / "backend" / "knowledge_base"


class RAGService:
    def __init__(
        self,
        kb_dir: Optional[Path] = None,
        model_name: str = "all-MiniLM-L6-v2",
        use_embeddings: bool = True,
    ) -> None:
        self.kb_dir = kb_dir or KNOWLEDGE_BASE_DIR
        self.model_name = model_name
        self.chunks: List[Dict[str, str]] = []
        self._model = None
        self._faiss_index = None
        self._np = None
        self._idf: Dict[str, float] = {}
        self._tfidf_vectors: List[Dict[str, float]] = []

        self._load_and_chunk_documents()
        self._build_tfidf_index()
        if use_embeddings and self.chunks:
            self._try_build_faiss_index()

    def _load_and_chunk_documents(self) -> None:
        if not self.kb_dir.exists():
            return

        for md_file in sorted(self.kb_dir.glob("*.md")):
            text = md_file.read_text(encoding="utf-8")
            department_id = self._extract_department_id(md_file, text)
            sections = self._chunk_markdown_by_section(text)
            for section in sections:
                self.chunks.append(
                    {
                        "source_file": md_file.name,
                        "department_id": department_id,
                        "content_snippet": section,
                    }
                )

    @staticmethod
    def _extract_department_id(md_file: Path, text: str) -> str:
        match = re.search(r"department_id:\s*([A-Z0-9_]+)", text)
        if match:
            return match.group(1).strip()
        return md_file.stem.upper()

    @staticmethod
    def _chunk_markdown_by_section(text: str) -> List[str]:
        raw_sections = re.split(r"\n(?=##\s+)", text.strip())
        chunks: List[str] = []
        for sec in raw_sections:
            cleaned = sec.strip()
            if not cleaned:
                continue
            # Skip top-level title-only metadata block if no substantive content
            if cleaned.startswith("# ") and "\n## " not in cleaned and len(cleaned.splitlines()) <= 3:
                continue
            chunks.append(cleaned)
        return chunks

    def _try_build_faiss_index(self) -> None:
        try:
            import faiss
            import numpy as np
            from sentence_transformers import SentenceTransformer

            model = SentenceTransformer(self.model_name)
            texts = [c["content_snippet"] for c in self.chunks]
            embeddings = model.encode(texts, normalize_embeddings=True)
            vectors = np.asarray(embeddings, dtype="float32")
            index = faiss.IndexFlatIP(vectors.shape[1])
            index.add(vectors)

            self._np = np
            self._model = model
            self._faiss_index = index
        except Exception:
            # Deterministic TF-IDF fallback remains active
            self._model = None
            self._faiss_index = None

    @staticmethod
    def _tokenize(text: str) -> List[str]:
        return re.findall(r"[a-z0-9]+", text.lower())

    def _build_tfidf_index(self) -> None:
        if not self.chunks:
            return

        doc_tokens = [self._tokenize(c["content_snippet"]) for c in self.chunks]
        num_docs = len(doc_tokens)
        df: Counter = Counter()
        for tokens in doc_tokens:
            df.update(set(tokens))

        self._idf = {
            term: math.log((num_docs + 1) / (freq + 1)) + 1.0
            for term, freq in df.items()
        }

        self._tfidf_vectors = []
        for tokens in doc_tokens:
            tf = Counter(tokens)
            total = max(len(tokens), 1)
            vec = {
                term: (count / total) * self._idf.get(term, 1.0)
                for term, count in tf.items()
            }
            norm = math.sqrt(sum(v * v for v in vec.values())) or 1.0
            self._tfidf_vectors.append({k: v / norm for k, v in vec.items()})

    def _tfidf_scores(self, query: str) -> List[float]:
        tokens = self._tokenize(query)
        if not tokens:
            return [0.0] * len(self.chunks)
        tf = Counter(tokens)
        total = len(tokens)
        q_vec = {
            term: (count / total) * self._idf.get(term, 1.0)
            for term, count in tf.items()
        }
        q_norm = math.sqrt(sum(v * v for v in q_vec.values())) or 1.0
        q_vec = {k: v / q_norm for k, v in q_vec.items()}

        scores: List[float] = []
        for d_vec in self._tfidf_vectors:
            score = sum(q_val * d_vec.get(term, 0.0) for term, q_val in q_vec.items())
            scores.append(score)
        return scores

    def retrieve_department_docs(
        self, department_id: str, query: str, top_k: int = 3
    ) -> List[RetrievedDocument]:
        dept_indices = [
            idx
            for idx, chunk in enumerate(self.chunks)
            if chunk["department_id"] == department_id
        ]
        if not dept_indices:
            return []

        if self._faiss_index is not None and self._model is not None and self._np is not None:
            q_emb = self._model.encode([query], normalize_embeddings=True)
            q_vec = self._np.asarray(q_emb, dtype="float32")
            scores, indices = self._faiss_index.search(q_vec, len(self.chunks))
            ranked_indices = [
                int(idx)
                for idx in indices[0]
                if idx >= 0 and self.chunks[int(idx)]["department_id"] == department_id
            ]
        else:
            tfidf_scores = self._tfidf_scores(query)
            ranked_indices = sorted(
                dept_indices, key=lambda idx: tfidf_scores[idx], reverse=True
            )

        selected = ranked_indices[:top_k]
        return [
            RetrievedDocument(
                source_file=self.chunks[idx]["source_file"],
                department_id=self.chunks[idx]["department_id"],
                content_snippet=self.chunks[idx]["content_snippet"],
            )
            for idx in selected
        ]