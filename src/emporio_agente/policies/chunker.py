"""Policy chunking.

The policy manual has clean numbered headers (1 Sobre, 2 Horário, 3 Pagamento,
...). We chunk on those section boundaries so each chunk is a coherent policy
unit, rather than blind fixed-size windowing that could split a rule (e.g. the
7-day return window) in half. At ~20 sections this yields a handful of chunks —
small enough that an in-memory cosine search needs no vector database.

Implementation note: pypdf extracts this PDF with doubled spaces and frequently
glues a section header onto the first sentence of its body on the same line
(e.g. "4.1 Direito de Arrependimento (Compras Online) • O cliente pode ..."). So
we detect the leading "N" / "N.M" section number at the start of a line and
split there, regardless of line length, then normalise whitespace.
"""

from __future__ import annotations

import re
from pathlib import Path

from ..models import PolicyChunk

# A section header is a line that STARTS with a number like "4" or "4.1",
# optionally followed by a dot, then whitespace, then a capitalised word.
_SECTION_RE = re.compile(r"^(\d+(?:\.\d+)?)\.?\s+([A-ZÀ-Ý].*)$")

# Page-number / furniture lines to ignore when they stand alone.
_NOISE_RE = re.compile(r"^(página\s*\d+|\d{1,3})$", re.IGNORECASE)


def extract_pdf_text(pdf_path: Path | str) -> str:
    """Extract raw text from the policy PDF using pypdf."""
    from pypdf import PdfReader

    reader = PdfReader(str(pdf_path))
    pages = [page.extract_text() or "" for page in reader.pages]
    return "\n".join(pages)


def _norm(text: str) -> str:
    """Collapse pypdf's doubled spaces and stray whitespace."""
    text = text.replace("\xa0", " ")
    text = re.sub(r"[ \t]{2,}", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _split_header(line: str) -> tuple[str, str, str] | None:
    """If ``line`` starts a section, return (id, title, inline_body).

    The title is taken up to the first sentence/bullet boundary; anything after
    that on the same line is returned as inline body so no content is lost.
    """
    line = re.sub(r"[ \t]{2,}", " ", line.strip())
    m = _SECTION_RE.match(line)
    if not m:
        return None
    section_id, rest = m.group(1), m.group(2).strip()

    # Split the title from a body that pypdf glued on. Title ends at the first
    # bullet, or after a short capitalised phrase before a lowercase run.
    for sep in ("•", " - "):
        if sep in rest:
            title, body = rest.split(sep, 1)
            return section_id, title.strip(), body.strip()

    # Otherwise: keep up to ~8 words as the title, rest as body.
    words = rest.split()
    if len(words) <= 8:
        return section_id, rest, ""
    title = " ".join(words[:8])
    body = " ".join(words[8:])
    return section_id, title, body


def chunk_policy_text(raw_text: str) -> list[PolicyChunk]:
    """Split policy text into section chunks (without embeddings/scores yet)."""
    lines = _norm(raw_text).splitlines()
    chunks: list[PolicyChunk] = []
    current_id = "0"
    current_title = "Apresentação"
    buffer: list[str] = []

    def flush() -> None:
        body = _norm("\n".join(buffer))
        if body:
            chunks.append(
                PolicyChunk(
                    section_id=current_id,
                    title=current_title,
                    text=f"{current_id} {current_title}\n{body}",
                    score=0.0,
                )
            )

    for line in lines:
        stripped = line.strip()
        if not stripped or _NOISE_RE.match(stripped):
            continue
        header = _split_header(stripped)
        if header:
            flush()
            current_id, current_title, inline = header
            buffer = [inline] if inline else []
        else:
            buffer.append(stripped)
    flush()

    return [c for c in chunks if len(c.text) > 40]


def load_policy_chunks(pdf_path: Path | str) -> list[PolicyChunk]:
    return chunk_policy_text(extract_pdf_text(pdf_path))
