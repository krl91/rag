"""
Client LLM OpenAI-compatible (Ollama).

Fonction principale :
    assistant.ask(question, contexte) -> ReponseStructuree

Le LLM reçoit uniquement le contexte assemblé, jamais un document complet.
Parsing JSON robuste avec 1 retry en cas de réponse invalide.
"""

import json
import logging
from typing import Optional

import httpx
from pydantic import BaseModel, Field, ValidationError

logger = logging.getLogger(__name__)

# Prompt système imposé — ne pas modifier
_SYSTEM_PROMPT = (
    "Tu es un assistant expert en smart metering. "
    "Réponds UNIQUEMENT à partir du contexte fourni ; "
    "si l'information est absente, dis-le explicitement. "
    "Réponds en JSON valide avec exactement les clés : "
    "resume, facts, decisions, actions, risks, sources. "
    "Ne génère aucun texte en dehors du JSON."
)

_JSON_SCHEMA_HINT = (
    "{\n"
    '  "resume": "résumé de la réponse",\n'
    '  "facts": ["fait 1", "fait 2"],\n'
    '  "decisions": ["décision 1"],\n'
    '  "actions": ["action 1"],\n'
    '  "risks": ["risque 1"],\n'
    '  "sources": ["source 1"]\n'
    "}"
)


class ReponseStructuree(BaseModel):
    """Réponse structurée du LLM, validée par Pydantic."""

    resume: str = Field(description="Résumé de la réponse à la question posée")
    facts: list[str] = Field(default_factory=list, description="Faits extraits du contexte")
    decisions: list[str] = Field(default_factory=list, description="Décisions identifiées")
    actions: list[str] = Field(default_factory=list, description="Actions à réaliser")
    risks: list[str] = Field(default_factory=list, description="Risques identifiés")
    sources: list[str] = Field(default_factory=list, description="Sources utilisées")


def _build_user_message(question: str, contexte: str) -> str:
    """Construit le message utilisateur avec la question et le contexte."""
    return (
        f"Contexte :\n{contexte}\n\n"
        f"Question : {question}\n\n"
        f"Réponds en JSON selon ce schéma :\n{_JSON_SCHEMA_HINT}"
    )


def _extract_json(text: str) -> dict:
    """
    Extrait le JSON de la réponse brute du LLM.

    Gère les cas : JSON brut, bloc ```json ... ```, texte parasite avant/après.
    """
    stripped = text.strip()

    # Bloc fenced markdown ```json ... ``` ou ``` ... ```
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        end = next(
            (i for i in range(len(lines) - 1, 0, -1) if lines[i].strip() == "```"),
            len(lines) - 1,
        )
        inner = "\n".join(lines[1:end])
        return json.loads(inner)

    # JSON brut (cas normal avec response_format json_object)
    return json.loads(stripped)


class LLMAssistant:
    """
    Client LLM OpenAI-compatible pointant sur OLLAMA_BASE_URL.

    Compatible Ollama et pont Copilot (aucun n'exige d'auth ; LLM_API_KEY
    reste disponible pour tout futur endpoint OpenAI-compatible nécessitant
    un Bearer token).
    Ne transmet jamais un document complet au LLM, uniquement le contexte
    assemblé par le retriever.
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        timeout: float = 120.0,
    ) -> None:
        from kb_smart_metering.config import settings as _settings
        self._base_url = (base_url or _settings.ollama_base_url).rstrip("/")
        self._model = model or _settings.ollama_model
        self._api_key = api_key if api_key is not None else _settings.llm_api_key
        self._timeout = timeout

    def ask(self, question: str, contexte: str) -> ReponseStructuree:
        """
        Envoie la question et le contexte au LLM, retourne une ReponseStructuree.

        Retry unique en cas de JSON invalide ou de validation Pydantic échouée.
        """
        user_msg = _build_user_message(question, contexte)
        return self._call_with_retry(user_msg)

    def _call_with_retry(self, user_msg: str, *, attempt: int = 1) -> ReponseStructuree:
        """Appel LLM avec 1 retry en cas d'échec de parsing/validation."""
        raw = self._call_api(user_msg)
        try:
            data = _extract_json(raw)
            return ReponseStructuree.model_validate(data)
        except (json.JSONDecodeError, ValidationError, ValueError, KeyError) as exc:
            if attempt >= 2:
                logger.error(
                    "Parsing JSON échoué après %d tentatives : %s | Réponse brute : %r",
                    attempt,
                    exc,
                    raw[:500],
                )
                raise ValueError(
                    f"Réponse LLM non parseable après {attempt} tentatives : {exc}"
                ) from exc
            logger.warning("Tentative %d — JSON invalide, retry : %s", attempt, exc)
            return self._call_with_retry(user_msg, attempt=attempt + 1)

    def _call_api(self, user_msg: str) -> str:
        """Effectue l'appel HTTP à l'endpoint /v1/chat/completions."""
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
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        logger.info("Appel LLM : model=%s, url=%s", self._model, url)
        try:
            response = httpx.post(url, json=payload, headers=headers, timeout=self._timeout)
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            logger.error("Erreur HTTP LLM : %s", exc)
            raise
        data = response.json()
        content: str = data["choices"][0]["message"]["content"]
        logger.debug("Réponse LLM brute (%d chars)", len(content))
        return content
