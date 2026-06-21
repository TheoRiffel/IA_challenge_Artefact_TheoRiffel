"""Small search layer for the product catalogue.

Scope is deliberately tight (65 products): accent/case-insensitive matching, a
category-synonym map, conservative fuzzy matching for product *names*, and an
explicit classifier for the dataset's trap term — "cordas".

The trap: the store does NOT sell accessory strings ("cordas avulsas"), but
"Cordas Orquestrais" is a valid product category. Bare "cordas" is therefore
ambiguous; the data layer must expose that signal instead of silently routing to
the orchestral-strings category. See ``classify_term``.

No ranking beyond "best price" lives here — that stays in ``StoreData``.
"""

from __future__ import annotations

import unicodedata
from enum import Enum
from typing import Iterable

from rapidfuzz import fuzz, process


def normalize(text: str | None) -> str:
    """Lowercase, strip accents (NFKD), and collapse whitespace.

    So "violao" matches "Violão" and "sax" matches "Saxofone".
    """
    if not text:
        return ""
    decomposed = unicodedata.normalize("NFKD", str(text))
    no_accents = "".join(c for c in decomposed if not unicodedata.combining(c))
    return " ".join(no_accents.lower().split())


# Canonical category names — must match data/categories.csv exactly.
CATEGORY_SYNONYMS: dict[str, str] = {
    "guitarra": "Guitarras", "guitarras": "Guitarras",
    "baixo": "Baixos", "baixos": "Baixos", "contrabaixo eletrico": "Baixos",
    "bateria": "Baterias e Percussão", "baterias": "Baterias e Percussão",
    "percussao": "Baterias e Percussão",
    "teclado": "Teclados e Pianos", "teclados": "Teclados e Pianos",
    "piano": "Teclados e Pianos", "pianos": "Teclados e Pianos",
    "sintetizador": "Teclados e Pianos",
    "violao": "Violões", "violoes": "Violões",
    "sopro": "Instrumentos de Sopro (Madeiras)",
    "madeira": "Instrumentos de Sopro (Madeiras)",
    "madeiras": "Instrumentos de Sopro (Madeiras)",
    "sax": "Instrumentos de Sopro (Madeiras)",
    "saxofone": "Instrumentos de Sopro (Madeiras)",
    "flauta": "Instrumentos de Sopro (Madeiras)",
    "clarinete": "Instrumentos de Sopro (Madeiras)",
    "metal": "Instrumentos de Sopro (Metais)",
    "metais": "Instrumentos de Sopro (Metais)",
    "trompete": "Instrumentos de Sopro (Metais)",
    "trombone": "Instrumentos de Sopro (Metais)",
    "ukulele": "Ukuleles", "ukuleles": "Ukuleles",
    "violino": "Cordas Orquestrais", "violinos": "Cordas Orquestrais",
    "viola": "Cordas Orquestrais", "violas": "Cordas Orquestrais",
    "violoncelo": "Cordas Orquestrais", "cello": "Cordas Orquestrais",
}

# Accessories the store does NOT sell (ARCHITECTURE.md §3.5).
# NOTE: bare "corda(s)" is intentionally absent — it is ambiguous (see below).
ACCESSORY_TERMS: set[str] = {
    "palheta", "palhetas", "cabo", "cabos", "case", "cases", "pedal", "pedais",
    "amplificador", "amplificadores", "capa", "capas", "afinador", "afinadores",
    "encordoamento", "encordoamentos",
}

# Cues that disambiguate a "cordas" query.
_ORCHESTRAL_CUES = {
    "orquestrais", "orquestral", "violino", "violinos", "viola", "violas",
    "violoncelo", "cello", "contrabaixo", "contrabaixos",
}
_AVULSA_CUES = {"avulsa", "avulsas", "avulso", "avulsos", "reposicao", "sobressalente"}


class TermClass(str, Enum):
    CATEGORY = "category"
    ACCESSORY_OUT_OF_SCOPE = "accessory_out_of_scope"
    AMBIGUOUS = "ambiguous"
    UNKNOWN = "unknown"


def classify_term(term: str) -> tuple[TermClass, str | None]:
    """Classify a search term.

    Returns ``(class, canonical_category_or_None)``. The canonical category is
    only set for :data:`TermClass.CATEGORY`.
    """
    tokens = set(normalize(term).split())
    has_cordas = bool(tokens & {"corda", "cordas"})

    # "cordas" with an orchestral cue -> the valid product category.
    if has_cordas and (tokens & _ORCHESTRAL_CUES):
        return TermClass.CATEGORY, "Cordas Orquestrais"
    # "cordas avulsas" and friends -> accessory, out of scope.
    if has_cordas and (tokens & _AVULSA_CUES):
        return TermClass.ACCESSORY_OUT_OF_SCOPE, None
    # bare "cordas" -> ambiguous: the data layer must not guess.
    if has_cordas:
        return TermClass.AMBIGUOUS, None

    # Unambiguous accessory term.
    if tokens & ACCESSORY_TERMS:
        return TermClass.ACCESSORY_OUT_OF_SCOPE, None

    # Category synonym (any token).
    for tok in tokens:
        if tok in CATEGORY_SYNONYMS:
            return TermClass.CATEGORY, CATEGORY_SYNONYMS[tok]

    return TermClass.UNKNOWN, None


def resolve_category(term: str, category_names: Iterable[str]) -> str | None:
    """Map a (possibly accented / synonym / partial) term to a canonical
    category name from ``category_names``, or ``None``."""
    klass, canonical = classify_term(term)
    if klass is TermClass.CATEGORY:
        return canonical
    n = normalize(term)
    if not n:
        return None
    for cname in category_names:
        cn = normalize(cname)
        if n == cn or n in cn or cn in n:
            return cname
    return None


# Conservative cutoff: near-misses match, garbage does not.
FUZZY_THRESHOLD = 80


def _name_index(names: Iterable[str]) -> dict[str, str]:
    """Map normalized name -> first original name with that normalization."""
    index: dict[str, str] = {}
    for name in names:
        index.setdefault(normalize(name), name)
    return index


def fuzzy_name_matches(
    query: str, names: Iterable[str], *, limit: int = 8, threshold: int = FUZZY_THRESHOLD
) -> list[str]:
    """Original product names whose normalized form fuzzily matches ``query``."""
    index = _name_index(names)
    hits = process.extract(
        normalize(query),
        list(index),
        scorer=fuzz.WRatio,
        limit=limit,
        score_cutoff=threshold,
    )
    return [index[match] for match, _score, _i in hits]


def fuzzy_best_name(
    query: str, names: Iterable[str], *, threshold: int = FUZZY_THRESHOLD
) -> str | None:
    """Single best fuzzy name match for ``query``, or ``None`` below threshold."""
    index = _name_index(names)
    best = process.extractOne(
        normalize(query), list(index), scorer=fuzz.WRatio, score_cutoff=threshold
    )
    return index[best[0]] if best else None


# Human-readable signals returned to the agent (it phrases / acts on them).
AMBIGUOUS_CORDAS_NOTE = (
    "O termo 'cordas' é ambíguo: pode ser a categoria de produtos 'Cordas "
    "Orquestrais' (violinos, violas, violoncelos) ou cordas avulsas de reposição "
    "(acessório que a loja NÃO vende). Peça esclarecimento ao cliente antes de "
    "assumir qualquer uma das opções."
)
ACCESSORY_OUT_OF_SCOPE_NOTE = (
    "Este termo corresponde a um acessório que a loja não comercializa (a loja "
    "trabalha apenas com instrumentos). Nenhum produto retornado."
)
