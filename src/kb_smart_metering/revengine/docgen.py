"""
Génération de documentation fonctionnelle Markdown/Obsidian par module.

Chaque appel LLM est limité à 1 module : le contexte = éléments AST du module
uniquement (jamais le code source complet). La réponse est validée par Pydantic.

Usage :
    from kb_smart_metering.revengine.docgen import DocGenerator
    from kb_smart_metering.revengine.ast_extract import ASTExtractor, Language

    extractor = ASTExtractor(Language.JAVA)
    modules = extractor.extract_dir(Path("./src"))

    gen = DocGenerator()
    for module in modules:
        doc = gen.generate(module)
        output = Path("docs") / f"{module.module_name}.md"
        output.write_text(gen.render_markdown(doc))
"""

import json
import logging
from pathlib import Path
from typing import Optional

import httpx
from pydantic import BaseModel, Field, ValidationError

from kb_smart_metering.revengine.ast_extract import ClassInfo, ExtractedModule

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Schéma de réponse structurée du LLM
# ---------------------------------------------------------------------------

_JSON_SCHEMA_HINT = (
    "{\n"
    '  "description": "description fonctionnelle du module en 2-4 phrases",\n'
    '  "composants": ["nom du composant 1", "nom du composant 2"],\n'
    '  "flux": ["flux 1 : A → B via EventX", "flux 2"],\n'
    '  "regles_metier": ["règle 1 détectée", "règle 2"],\n'
    '  "risques": ["risque ou dette technique détecté"]\n'
    "}"
)

_SYSTEM_PROMPT = (
    "Tu es un architecte solution expert en smart metering. "
    "À partir des éléments structurels d'un module logiciel (classes, méthodes, "
    "événements, dépendances), génère une documentation fonctionnelle concise. "
    "Réponds UNIQUEMENT en JSON valide, sans texte avant ou après. "
    "Ne génère aucune information non fondée sur les éléments fournis."
)


class ModuleDocLLM(BaseModel):
    """Réponse structurée du LLM pour la documentation d'un module."""

    description: str = Field(
        description="Description fonctionnelle du module en 2-4 phrases"
    )
    composants: list[str] = Field(
        default_factory=list,
        description="Liste des composants identifiés dans le module",
    )
    flux: list[str] = Field(
        default_factory=list,
        description="Flux de données ou événements détectés",
    )
    regles_metier: list[str] = Field(
        default_factory=list,
        description="Règles métier détectées par analyse statique",
    )
    risques: list[str] = Field(
        default_factory=list,
        description="Risques ou dettes techniques détectés",
    )


# ---------------------------------------------------------------------------
# Résultat complet de la génération
# ---------------------------------------------------------------------------


class ModuleDoc(BaseModel):
    """Documentation complète d'un module, prête à être rendue en Markdown."""

    module_name: str
    language: str
    package: Optional[str]
    file_path: str
    classes: list[str] = Field(default_factory=list)
    events_published: list[str] = Field(default_factory=list)
    events_subscribed: list[str] = Field(default_factory=list)
    # Contenu généré par le LLM
    description: str = ""
    composants: list[str] = Field(default_factory=list)
    flux: list[str] = Field(default_factory=list)
    regles_metier: list[str] = Field(default_factory=list)
    risques: list[str] = Field(default_factory=list)
    # Sources (fichier + lignes)
    sources: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Rendu Markdown / Obsidian
# ---------------------------------------------------------------------------


def render_markdown(doc: ModuleDoc) -> str:
    """
    Génère la documentation Markdown/Obsidian d'un module.

    Le format est compatible Obsidian : frontmatter YAML + sections Markdown.
    """
    lines: list[str] = []

    # Frontmatter Obsidian
    lines.append("---")
    lines.append(f"module: {doc.module_name}")
    lines.append(f"language: {doc.language}")
    if doc.package:
        lines.append(f"package: {doc.package}")
    lines.append(f"tags: [code, {doc.language}, reverse-engineering]")
    lines.append("---")
    lines.append("")

    # Titre
    lines.append(f"# {doc.module_name}")
    lines.append("")

    # Description
    lines.append("## Description fonctionnelle")
    lines.append("")
    lines.append(doc.description or "_Aucune description générée._")
    lines.append("")

    # Composants
    if doc.composants or doc.classes:
        lines.append("## Composants")
        lines.append("")
        all_comps = list(dict.fromkeys(doc.composants + doc.classes))
        for comp in all_comps:
            lines.append(f"- `{comp}`")
        lines.append("")

    # Flux d'événements
    if doc.flux or doc.events_published or doc.events_subscribed:
        lines.append("## Flux")
        lines.append("")
        for flux in doc.flux:
            lines.append(f"- {flux}")
        if doc.events_published:
            lines.append(
                f"- **Événements publiés** : "
                + ", ".join(f"`{e}`" for e in doc.events_published)
            )
        if doc.events_subscribed:
            lines.append(
                f"- **Événements consommés** : "
                + ", ".join(f"`{e}`" for e in doc.events_subscribed)
            )
        lines.append("")

    # Règles métier
    if doc.regles_metier:
        lines.append("## Règles métier détectées")
        lines.append("")
        for regle in doc.regles_metier:
            lines.append(f"- {regle}")
        lines.append("")

    # Risques
    if doc.risques:
        lines.append("## Risques / dette technique")
        lines.append("")
        for risque in doc.risques:
            lines.append(f"- {risque}")
        lines.append("")

    # Sources
    if doc.sources:
        lines.append("## Sources")
        lines.append("")
        for src in doc.sources:
            lines.append(f"- `{src}`")
        lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Générateur principal
# ---------------------------------------------------------------------------


def _build_context(module: ExtractedModule) -> str:
    """Construit le contexte minimal envoyé au LLM (1 module, pas de code complet)."""
    summary: list[dict] = []
    for cls in module.classes:
        entry: dict = {
            "nom": cls.name,
            "type": cls.kind,
            "méthodes": [m.name for m in cls.methods],
        }
        if cls.events_published:
            entry["événements_publiés"] = cls.events_published
        if cls.events_subscribed:
            entry["événements_consommés"] = cls.events_subscribed
        if cls.outgoing_components:
            entry["dépendances"] = cls.outgoing_components
        if cls.data_models:
            entry["modèles_de_données"] = cls.data_models
        summary.append(entry)

    return (
        f"Module : {module.module_name}\n"
        f"Langage : {module.language}\n"
        f"Package : {module.package or 'N/A'}\n\n"
        f"Éléments structurels :\n"
        f"{json.dumps(summary, ensure_ascii=False, indent=2)}"
    )


def _extract_json(text: str) -> dict:
    """Extrait le JSON de la réponse brute (gère les blocs markdown)."""
    stripped = text.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        end = next(
            (i for i in range(len(lines) - 1, 0, -1) if lines[i].strip() == "```"),
            len(lines) - 1,
        )
        stripped = "\n".join(lines[1:end])
    return json.loads(stripped)


def _aggregate_module_events(
    classes: list[ClassInfo],
) -> tuple[list[str], list[str]]:
    """Agrège les événements publiés et consommés de toutes les classes."""
    published: list[str] = []
    subscribed: list[str] = []
    for cls in classes:
        published.extend(cls.events_published)
        subscribed.extend(cls.events_subscribed)
    return list(dict.fromkeys(published)), list(dict.fromkeys(subscribed))


def _build_sources(module: ExtractedModule) -> list[str]:
    """Construit la liste des sources (fichier + lignes des classes)."""
    return [
        f"{module.file_path}:{cls.line_start}-{cls.line_end} ({cls.name})"
        for cls in module.classes
    ]


def build_base_doc(module: ExtractedModule) -> ModuleDoc:
    """
    Construit un ModuleDoc à partir de l'AST seul — AUCUN appel LLM.

    Les champs de rédaction (description, composants, flux, regles_metier,
    risques) restent vides : à compléter soit par le LLM (generate()), soit
    par l'agent Copilot en conversation (voir build_extraction_payload()).
    """
    published, subscribed = _aggregate_module_events(module.classes)
    return ModuleDoc(
        module_name=module.module_name,
        language=module.language,
        package=module.package,
        file_path=module.file_path,
        classes=[cls.name for cls in module.classes],
        events_published=published,
        events_subscribed=subscribed,
        sources=_build_sources(module),
    )


def build_extraction_payload(module: ExtractedModule) -> dict:
    """
    JSON à écrire pour le flux sans LLM (`kb docgen --extract-only`).

    Contient le ModuleDoc de base (champs de rédaction vides) plus une clé
    ``contexte`` en lecture seule (les éléments structurels du module, le
    même contenu que celui normalement envoyé au LLM) — à l'agent Copilot de
    compléter description/composants/flux/regles_metier/risques à partir de
    ``contexte` uniquement, puis de sauvegarder le fichier tel quel (la clé
    ``contexte`` est ignorée à la relecture par load_module_doc_from_extraction).
    """
    payload = build_base_doc(module).model_dump(mode="json")
    payload["contexte"] = _build_context(module)
    return payload


def load_module_doc_from_extraction(data: dict) -> ModuleDoc:
    """Reconstruit un ModuleDoc depuis le JSON complété par l'agent (ignore 'contexte')."""
    return ModuleDoc.model_validate(data)


class DocGenerator:
    """
    Génère la documentation Markdown d'un module via LLM local (Ollama).

    Paramètres
    ----------
    base_url : str | None
        URL de l'endpoint OpenAI-compatible. Par défaut : settings.ollama_base_url.
    model : str | None
        Modèle LLM. Par défaut : settings.ollama_model.
    timeout : float
        Timeout HTTP en secondes. Défaut : 120.
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        timeout: float = 120.0,
    ) -> None:
        if base_url is None or model is None:
            from kb_smart_metering.config import settings as _settings

            base_url = base_url if base_url is not None else _settings.ollama_base_url
            model = model if model is not None else _settings.ollama_model
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._timeout = timeout

    def generate(self, module: ExtractedModule) -> ModuleDoc:
        """
        Génère la documentation d'un module.

        Appelle le LLM avec le contexte minimal du module (pas de code complet).
        Valide la réponse avec Pydantic. En cas d'échec, retourne une doc partielle
        sans section LLM.
        """
        base_doc = build_base_doc(module)

        try:
            llm_result = self._call_llm(module)
            base_doc.description = llm_result.description
            base_doc.composants = llm_result.composants
            base_doc.flux = llm_result.flux
            base_doc.regles_metier = llm_result.regles_metier
            base_doc.risques = llm_result.risques
        except Exception as exc:
            logger.warning(
                "LLM indisponible pour le module '%s' : %s — documentation partielle.",
                module.module_name,
                exc,
            )

        return base_doc

    def generate_dir(
        self,
        modules: list[ExtractedModule],
        out_dir: Path,
        module_filter: Optional[str] = None,
    ) -> list[Path]:
        """
        Génère la documentation de tous les modules dans `out_dir`.

        Paramètres
        ----------
        modules : list[ExtractedModule]
            Modules à documenter.
        out_dir : Path
            Répertoire de sortie (créé si inexistant).
        module_filter : str | None
            Si fourni, traite uniquement le module dont le nom correspond.

        Retourne la liste des fichiers Markdown générés.
        """
        out_dir.mkdir(parents=True, exist_ok=True)
        generated: list[Path] = []

        for module in modules:
            if module_filter and module.module_name != module_filter:
                continue
            doc = self.generate(module)
            content = render_markdown(doc)
            out_file = out_dir / f"{module.module_name}.md"
            out_file.write_text(content, encoding="utf-8")
            generated.append(out_file)
            logger.info("Documentation générée : %s", out_file)

        return generated

    # ------------------------------------------------------------------
    # Privé
    # ------------------------------------------------------------------

    def _call_llm(self, module: ExtractedModule) -> ModuleDocLLM:
        """Appelle le LLM et valide la réponse. Retry unique en cas d'échec JSON."""
        context = _build_context(module)
        user_msg = (
            f"Voici les éléments structurels du module '{module.module_name}' :\n\n"
            f"{context}\n\n"
            f"Génère la documentation fonctionnelle en JSON selon ce schéma :\n"
            f"{_JSON_SCHEMA_HINT}"
        )
        return self._call_with_retry(user_msg)

    def _call_with_retry(
        self, user_msg: str, *, attempt: int = 1
    ) -> ModuleDocLLM:
        """Appel LLM avec 1 retry en cas de réponse JSON invalide."""
        raw = self._call_api(user_msg)
        try:
            data = _extract_json(raw)
            return ModuleDocLLM.model_validate(data)
        except (json.JSONDecodeError, ValidationError, ValueError) as exc:
            if attempt >= 2:
                raise ValueError(
                    f"Réponse LLM non parseable après {attempt} tentatives : {exc}"
                ) from exc
            logger.warning(
                "Module doc — tentative %d JSON invalide, retry : %s", attempt, exc
            )
            return self._call_with_retry(user_msg, attempt=attempt + 1)

    def _call_api(self, user_msg: str) -> str:
        """Effectue l'appel HTTP vers l'endpoint /v1/chat/completions."""
        url = f"{self._base_url}/chat/completions"
        payload: dict = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": user_msg},
            ],
            "temperature": 0.1,
            "response_format": {"type": "json_object"},
        }
        logger.info(
            "Appel LLM docgen : model=%s, url=%s", self._model, url
        )
        try:
            response = httpx.post(url, json=payload, timeout=self._timeout)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise ConnectionError(
                f"Erreur HTTP vers {url} : {exc}"
            ) from exc

        body = response.json()
        return body["choices"][0]["message"]["content"]
