"""
Configuration centrale — chargement via Pydantic Settings.

Lit les variables d'environnement (ou .env) et expose un objet `settings`
importable depuis n'importe quel module du projet.

Usage :
    from kb_smart_metering.config import settings

    neo4j_uri = settings.neo4j_uri
"""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Paramètres de configuration du projet, chargés depuis l'environnement."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- Jira ---
    jira_url: str = Field(description="URL de l'instance Jira")
    jira_token: str = Field(description="Token d'API Jira (secret)")

    # --- Confluence ---
    confluence_url: str = Field(description="URL de l'instance Confluence")
    confluence_token: str = Field(description="Token d'API Confluence (secret)")

    # --- Neo4j ---
    neo4j_uri: str = Field(default="bolt://localhost:7687", description="URI Neo4j")
    neo4j_user: str = Field(default="neo4j", description="Utilisateur Neo4j")
    neo4j_password: str = Field(description="Mot de passe Neo4j (secret)")

    # --- LLM (endpoint OpenAI-compatible) — OPTIONNEL ---
    # Uniquement utilisé par `kb ingest`/`kb ask` (pipeline automatique).
    # `kb extract`/`kb search`/`kb ingest-extraction` n'en ont jamais besoin —
    # c'est l'agent Copilot, dans la conversation, qui fait ce travail (voir
    # skills kb-ingest/kb-ask). Valeurs par défaut ci-dessous = Ollama, si
    # disponible. Pont Copilot (option avancée, déconseillée : ouvre un
    # serveur HTTP local) : OLLAMA_BASE_URL=http://127.0.0.1:4141/v1,
    # OLLAMA_MODEL=gpt-4o, LLM_API_KEY vide — voir copilot-bridge/ et
    # .github/skills/kb-copilot-bridge/SKILL.md
    # (GitHub Models est retiré depuis le 30/07/2026, ne plus l'utiliser)
    ollama_base_url: str = Field(
        default="http://localhost:11434/v1",
        description="URL de base de l'endpoint OpenAI-compatible (Ollama ou pont Copilot local)",
    )
    ollama_model: str = Field(
        default="mistral:7b",
        description="Modèle LLM (ex: mistral:7b pour Ollama, gpt-4o pour le pont Copilot)",
    )
    llm_api_key: str = Field(
        default="",
        description="Clé API LLM — vide pour Ollama et pour le pont Copilot (aucun n'a d'auth)",
    )

    # --- Embeddings & reranking ---
    embedding_model: str = Field(
        default="BAAI/bge-m3",
        description="Modèle sentence-transformers pour les embeddings",
    )
    reranker_model: str = Field(
        default="BAAI/bge-reranker-v2-m3",
        description="Modèle sentence-transformers pour le reranking",
    )


settings = Settings()
