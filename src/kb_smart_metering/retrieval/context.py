"""
Assemblage du contexte final pour le LLM.

Regroupe les éléments de contexte par type (faits, décisions, actions,
réunions), respecte un budget de tokens configurable, et formate chaque
élément avec sa référence source en markdown compact.
"""

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)

DEFAULT_TOKEN_BUDGET = 3000

# Ratio mots → tokens (approximation pour fr/en, modèles ~4 car/token)
_WORDS_PER_TOKEN_RATIO = 1.3


class ContextType(str, Enum):
    """Types d'éléments de contexte acceptés par le LLM."""

    FACT = "fact"
    DECISION = "decision"
    ACTION = "action"
    MEETING = "meeting"
    RISK = "risk"


@dataclass
class ContextSource:
    """Référence à la source originale d'un élément de contexte."""

    type: str  # jira, confluence, git, file, meeting
    identifier: str  # URL, SHA commit, chemin fichier, ID ticket
    page: Optional[int] = None  # numéro de page (PDF/Word)

    def format(self) -> str:
        """Retourne une représentation compacte de la source."""
        if self.page is not None:
            return f"{self.identifier} (p.{self.page})"
        return self.identifier


@dataclass
class ContextItem:
    """Élément de contexte destiné à être inclus dans le prompt LLM."""

    type: ContextType
    content: str
    source: ContextSource
    valid_at: Optional[str] = None  # date ISO (ex : "2023-12-01")
    metadata: dict = field(default_factory=dict)


def estimate_tokens(text: str) -> int:
    """
    Estimation du nombre de tokens d'un texte.

    Approximation : 1 token ≈ 0.75 mot (ratio inverse : 1 mot ≈ 1.3 tokens).
    Suffisant pour le respect du budget sans appeler un tokenizer lourd.
    """
    return max(1, int(len(text.split()) * _WORDS_PER_TOKEN_RATIO))


_TYPE_ORDER = [
    ContextType.FACT,
    ContextType.DECISION,
    ContextType.ACTION,
    ContextType.MEETING,
    ContextType.RISK,
]

_TYPE_HEADERS: dict[ContextType, str] = {
    ContextType.FACT: "## Faits",
    ContextType.DECISION: "## Décisions",
    ContextType.ACTION: "## Actions",
    ContextType.MEETING: "## Réunions",
    ContextType.RISK: "## Risques",
}


def _format_item(item: ContextItem) -> str:
    """Formate un ContextItem en ligne markdown avec sa source."""
    meta_parts: list[str] = []
    if item.valid_at:
        meta_parts.append(f"date: {item.valid_at}")
    meta_parts.append(f"source: {item.source.format()}")
    meta_str = ", ".join(meta_parts)
    return f"- {item.content}\n  _({meta_str})_"


def assemble_context(
    items: list[ContextItem],
    question: str,
    token_budget: int = DEFAULT_TOKEN_BUDGET,
) -> str:
    """
    Assemble le contexte en markdown compact pour le LLM.

    Le contexte respecte le budget de tokens configuré. Les éléments sont
    regroupés par type dans l'ordre : Faits → Décisions → Actions →
    Réunions → Risques. L'assemblage s'arrête dès que le budget est atteint.

    Paramètres
    ----------
    items : list[ContextItem]
        Éléments de contexte à inclure (ordre de priorité conservé).
    question : str
        Question posée — incluse en en-tête du contexte pour ancrage.
    token_budget : int
        Budget de tokens maximum (défaut 3000).

    Retourne
    --------
    str
        Contexte en markdown compact prêt à être injecté dans le prompt LLM.
    """
    question_header = f"## Question\n{question}"
    used_tokens = estimate_tokens(question_header)

    # Regroupement par type
    by_type: dict[ContextType, list[ContextItem]] = {t: [] for t in ContextType}
    for item in items:
        by_type[item.type].append(item)

    sections: list[str] = []
    total_included = 0
    total_skipped = 0

    for ctx_type in _TYPE_ORDER:
        type_items = by_type[ctx_type]
        if not type_items:
            continue

        header = _TYPE_HEADERS[ctx_type]
        header_tokens = estimate_tokens(header)
        if used_tokens + header_tokens >= token_budget:
            total_skipped += len(type_items)
            logger.debug(
                "Budget atteint avant section %r (%d éléments ignorés)",
                ctx_type.value,
                len(type_items),
            )
            break

        entries: list[str] = []
        for item in type_items:
            entry = _format_item(item)
            entry_tokens = estimate_tokens(entry)
            if used_tokens + header_tokens + entry_tokens > token_budget:
                remaining = len(type_items) - len(entries)
                total_skipped += remaining
                logger.debug(
                    "Budget atteint dans section %r (%d éléments ignorés)",
                    ctx_type.value,
                    remaining,
                )
                break
            entries.append(entry)
            used_tokens += entry_tokens
            total_included += 1

        if entries:
            used_tokens += header_tokens
            sections.append(header + "\n" + "\n".join(entries))

    context = question_header
    if sections:
        context += "\n\n" + "\n\n".join(sections)

    logger.info(
        "Contexte assemblé : %d éléments inclus, %d ignorés (budget), ~%d tokens estimés",
        total_included,
        total_skipped,
        used_tokens,
    )
    return context
