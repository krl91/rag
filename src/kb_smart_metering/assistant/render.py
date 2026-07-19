"""
Rendu Markdown compatible Obsidian.

Format de sortie :
  # <question>
  ## Résumé
  ## Faits
  ## Décisions
  ## Actions
  ## Risques
  ## Sources (liens cliquables si URL détectée)
"""

import re

from kb_smart_metering.assistant.llm import ReponseStructuree

_URL_RE = re.compile(r"https?://\S+")


def _as_link(source: str) -> str:
    """Transforme une source contenant une URL en lien markdown cliquable."""
    match = _URL_RE.search(source)
    if match:
        url = match.group(0).rstrip(".,;)")
        label = source[: match.start()].strip(" —-:") or url
        return f"[{label}]({url})" if label and label != url else f"<{url}>"
    return source


def _bullet_list(items: list[str]) -> str:
    """Formate une liste d'items en liste à puces markdown."""
    if not items:
        return "_Aucun élément identifié._"
    return "\n".join(f"- {item}" for item in items)


def to_markdown(question: str, reponse: ReponseStructuree) -> str:
    """
    Rend une ReponseStructuree en markdown compatible Obsidian.

    Sections générées : # Sujet / ## Résumé / ## Faits / ## Décisions /
    ## Actions / ## Risques / ## Sources.

    Paramètres
    ----------
    question : str
        Question originale — utilisée comme titre H1.
    reponse : ReponseStructuree
        Réponse structurée validée par Pydantic.

    Retourne
    --------
    str
        Document markdown prêt à être copié dans un vault Obsidian.
    """
    sections: list[str] = []

    sections.append(f"# {question.strip()}")
    sections.append(f"## Résumé\n{reponse.resume}")

    if reponse.facts:
        sections.append(f"## Faits\n{_bullet_list(reponse.facts)}")

    if reponse.decisions:
        sections.append(f"## Décisions\n{_bullet_list(reponse.decisions)}")

    if reponse.actions:
        sections.append(f"## Actions\n{_bullet_list(reponse.actions)}")

    if reponse.risks:
        sections.append(f"## Risques\n{_bullet_list(reponse.risks)}")

    # Sources toujours affichées
    source_lines = [_as_link(s) for s in reponse.sources] if reponse.sources else []
    sources_content = _bullet_list(source_lines) if source_lines else "_Aucune source._"
    sections.append(f"## Sources\n{sources_content}")

    return "\n\n".join(sections)
