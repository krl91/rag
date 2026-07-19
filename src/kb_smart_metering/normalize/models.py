"""
Modèle intermédiaire commun pour la normalisation des documents extraits.

Toutes les sources (Jira, Confluence, Git, fichiers, réunions) sont converties
en RawDocument avant ingestion dans le graphe de connaissances.
"""

from datetime import datetime
from pathlib import Path
from typing import Any, Literal, Optional, Union

from pydantic import BaseModel, Field

SourceType = Literal["jira", "confluence", "git", "docx", "xlsx", "pdf", "meeting", "obsidian"]


def normalize_file_source_id(path: Union[Path, str]) -> str:
    """Retourne le chemin résolu en format POSIX pour id_source.

    Élimine les backslashes Windows (``C:\\Users\\...`` → ``C:/Users/...``)
    sans modifier le comportement sur Linux/macOS. Utilise uniquement
    ``pathlib.Path.as_posix()`` de la stdlib, sans dépendance tierce.

    Args:
        path: Chemin vers le fichier (str ou Path).

    Returns:
        Chemin absolu normalisé avec des slashes POSIX.
    """
    return Path(path).resolve().as_posix()


class RawDocument(BaseModel):
    """Document brut normalisé, produit par chaque extracteur."""

    id_source: str = Field(
        description="Identifiant unique dans la source (clé Jira, ID page, SHA commit, chemin, etc.)"
    )
    source_type: SourceType = Field(description="Type de source du document")
    titre: str = Field(description="Titre du document ou résumé court")
    contenu_texte: str = Field(description="Contenu textuel brut du document")
    auteur: Optional[str] = Field(default=None, description="Auteur principal du document")
    date_creation: Optional[datetime] = Field(default=None, description="Date de création")
    date_modification: Optional[datetime] = Field(
        default=None, description="Date de dernière modification"
    )
    url_ou_chemin: Optional[str] = Field(
        default=None, description="URL de la source ou chemin absolu du fichier"
    )
    metadonnees: dict[str, Any] = Field(
        default_factory=dict, description="Métadonnées spécifiques à la source"
    )
    pieces_jointes: list[str] = Field(
        default_factory=list, description="Liste d'URLs ou chemins des pièces jointes"
    )
