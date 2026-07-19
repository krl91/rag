"""
Génération de diagrammes Mermaid à partir des éléments déjà extraits par
ast_extract.py / graph_build.py — déterministe, AUCUN appel LLM.

Réutilisé par :
- docgen.py : diagramme par module (classes, événements, appels sortants)
- `kb reveng --diagram-out` : diagramme système, à partir de toutes les
  relations candidates détectées dans un dépôt.
"""

import re

from kb_smart_metering.revengine.ast_extract import ExtractedModule
from kb_smart_metering.revengine.graph_build import RelationCandidate


def _node_id(prefix: str, name: str) -> str:
    """Identifiant Mermaid valide et stable pour un nœud (alphanumérique + _)."""
    safe = re.sub(r"[^A-Za-z0-9_]", "_", name) or "x"
    return f"{prefix}_{safe}"


def _escape_label(name: str) -> str:
    return name.replace('"', "'")


def _ensure_node(
    lines: list[str], seen: set[str], prefix: str, name: str, open_c: str, close_c: str
) -> str:
    """Ajoute la déclaration du nœud à `lines` si nouveau, retourne son id."""
    nid = _node_id(prefix, name)
    if nid not in seen:
        lines.append(f'  {nid}{open_c}"{_escape_label(name)}"{close_c}')
        seen.add(nid)
    return nid


def mermaid_for_module(module: ExtractedModule) -> str:
    """
    Diagramme Mermaid d'un module : classes (rectangles), événements publiés/
    consommés (hexagones), composants appelés (stades). Chaîne vide si le
    module n'a rien à représenter (aucun événement ni dépendance détectée).
    """
    lines: list[str] = []
    seen: set[str] = set()
    edges: list[str] = []

    for cls in module.classes:
        cid = _ensure_node(lines, seen, "c", cls.name, "[", "]")
        for evt in cls.events_published:
            eid = _ensure_node(lines, seen, "e", evt, "{{", "}}")
            edges.append(f"  {cid} -->|publie| {eid}")
        for evt in cls.events_subscribed:
            eid = _ensure_node(lines, seen, "e", evt, "{{", "}}")
            edges.append(f"  {eid} -->|consommé par| {cid}")
        for dep in cls.outgoing_components:
            did = _ensure_node(lines, seen, "d", dep, "([", "])")
            edges.append(f"  {cid} -.->|appelle| {did}")

    if not edges:
        return ""
    return "\n".join(["flowchart LR", *lines, *edges])


_KIND_STYLE: dict[str, tuple[str, str]] = {
    "publie": ("-->", "publie"),
    "consomme": ("-->", "consomme"),
    "appelle": ("-.->", "appelle"),
}


def mermaid_for_relations(relations: list[RelationCandidate]) -> str:
    """
    Diagramme Mermaid système à partir de toutes les relations candidates
    d'un dépôt (voir GraphBuilder.build_relations). Chaîne vide si la liste
    est vide.
    """
    if not relations:
        return ""

    lines: list[str] = []
    seen: set[str] = set()
    edges: list[str] = []

    for rel in relations:
        src_id = _ensure_node(lines, seen, "c", rel.source_component, "[", "]")
        is_event = rel.kind in ("publie", "consomme")
        tgt_id = (
            _ensure_node(lines, seen, "e", rel.target, "{{", "}}")
            if is_event
            else _ensure_node(lines, seen, "c", rel.target, "[", "]")
        )
        arrow, label = _KIND_STYLE.get(rel.kind, ("-->", rel.kind))
        edges.append(f"  {src_id} {arrow}|{label}| {tgt_id}")

    return "\n".join(["flowchart LR", *lines, *edges])
