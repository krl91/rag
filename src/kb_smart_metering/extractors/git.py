"""
Extracteur Git — collecte commits, branches et tags depuis un dépôt local cloné.

Utilise GitPython pour accéder aux métadonnées sans appel réseau.
"""

import logging
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Union

import git

from kb_smart_metering.normalize.models import RawDocument

logger = logging.getLogger(__name__)


def _check_git_available() -> None:
    """Vérifie que le binaire git est accessible avant tout appel GitPython.

    Si ``GIT_PYTHON_GIT_EXECUTABLE`` est défini dans l'environnement, GitPython
    l'utilisera directement — la détection via ``shutil.which`` est inutile.

    Raises:
        RuntimeError: Si git est introuvable et que la variable d'env n'est pas
            définie.
    """
    if os.environ.get("GIT_PYTHON_GIT_EXECUTABLE"):
        return
    if shutil.which("git") is None:
        raise RuntimeError(
            "git n'est pas trouvé dans le PATH. "
            "Sur Windows, installer Git for Windows : https://git-scm.com/download/win\n"
            "Alternative : définir GIT_PYTHON_GIT_EXECUTABLE dans .env "
            "pour pointer vers l'exécutable git (ex. C:\\Program Files\\Git\\bin\\git.exe)."
        )


class GitExtractor:
    """Extracteur de métadonnées Git via GitPython."""

    def __init__(self, repo_path: Union[str, Path]) -> None:
        """
        Initialise l'extracteur Git.

        Args:
            repo_path: Chemin vers le dépôt Git local cloné.

        Raises:
            RuntimeError: Si le binaire ``git`` est introuvable dans le PATH
                et que ``GIT_PYTHON_GIT_EXECUTABLE`` n'est pas défini.
        """
        _check_git_available()
        self._repo_path = Path(repo_path)

    def extract(self) -> list[RawDocument]:
        """Extrait les commits, branches et tags du dépôt."""
        try:
            repo = git.Repo(self._repo_path)
        except git.exc.InvalidGitRepositoryError as exc:
            logger.error("Dépôt Git invalide (%s) : %s", self._repo_path, exc)
            return []
        except git.exc.NoSuchPathError as exc:
            logger.error("Chemin introuvable (%s) : %s", self._repo_path, exc)
            return []

        documents: list[RawDocument] = []
        documents.extend(self._extract_commits(repo))
        documents.extend(self._extract_branches(repo))
        documents.extend(self._extract_tags(repo))

        logger.info(
            "Git : %d documents extraits depuis %s", len(documents), self._repo_path
        )
        return documents

    def _extract_commits(self, repo: git.Repo) -> list[RawDocument]:
        """Extrait les commits accessibles depuis HEAD."""
        documents: list[RawDocument] = []
        try:
            for commit in repo.iter_commits("HEAD"):
                sha = commit.hexsha
                fichiers = list(commit.stats.files.keys())
                fichiers_text = "\n".join(f"  - {f}" for f in fichiers)

                contenu = (
                    f"Message : {commit.message.strip()}\n"
                    f"Auteur : {commit.author.name} <{commit.author.email}>\n"
                    f"Fichiers modifiés ({len(fichiers)}) :\n{fichiers_text}"
                )

                authored_dt = datetime.fromtimestamp(commit.authored_date, tz=timezone.utc)

                documents.append(
                    RawDocument(
                        id_source=sha,
                        source_type="git",
                        titre=commit.message.splitlines()[0][:200],
                        contenu_texte=contenu,
                        auteur=f"{commit.author.name} <{commit.author.email}>",
                        date_creation=authored_dt,
                        date_modification=authored_dt,
                        url_ou_chemin=str(self._repo_path),
                        metadonnees={
                            "sha": sha,
                            "short_sha": sha[:8],
                            "nb_fichiers": len(fichiers),
                            "fichiers": fichiers[:50],
                        },
                    )
                )
        except git.exc.GitCommandError as exc:
            logger.warning("Impossible d'itérer les commits (dépôt vide ?) : %s", exc)
        except Exception as exc:
            logger.error("Erreur lors de l'extraction des commits : %s", exc)

        logger.debug("Git : %d commits extraits", len(documents))
        return documents

    def _extract_branches(self, repo: git.Repo) -> list[RawDocument]:
        """Extrait les métadonnées des branches locales."""
        documents: list[RawDocument] = []
        try:
            for branch in repo.branches:  # type: ignore[attr-defined]
                try:
                    tip = branch.commit
                    documents.append(
                        RawDocument(
                            id_source=f"branch:{branch.name}",
                            source_type="git",
                            titre=f"Branche : {branch.name}",
                            contenu_texte=(
                                f"Branche : {branch.name}\n"
                                f"Dernier commit : {tip.hexsha[:8]} — "
                                f"{tip.message.splitlines()[0]}\n"
                                f"Auteur : {tip.author.name}"
                            ),
                            auteur=tip.author.name,
                            date_modification=datetime.fromtimestamp(
                                tip.authored_date, tz=timezone.utc
                            ),
                            url_ou_chemin=str(self._repo_path),
                            metadonnees={
                                "branch_name": branch.name,
                                "tip_sha": tip.hexsha,
                            },
                        )
                    )
                except Exception as exc:
                    logger.warning("Branche %s ignorée : %s", branch.name, exc)
        except Exception as exc:
            logger.error("Erreur lors de l'extraction des branches : %s", exc)

        return documents

    def _extract_tags(self, repo: git.Repo) -> list[RawDocument]:
        """Extrait les tags et releases."""
        documents: list[RawDocument] = []
        try:
            for tag in repo.tags:
                try:
                    # Tag annoté vs tag léger
                    tag_obj = getattr(tag, "tag", None)
                    if tag_obj is not None:
                        message = tag_obj.message or ""
                        tagger = getattr(tag_obj, "tagger", None)
                        auteur = tagger.name if tagger else None
                        tagged_date = (
                            datetime.fromtimestamp(tag_obj.tagged_date, tz=timezone.utc)
                            if hasattr(tag_obj, "tagged_date")
                            else None
                        )
                    else:
                        commit = tag.commit
                        message = commit.message.strip()
                        auteur = commit.author.name
                        tagged_date = datetime.fromtimestamp(
                            commit.authored_date, tz=timezone.utc
                        )

                    documents.append(
                        RawDocument(
                            id_source=f"tag:{tag.name}",
                            source_type="git",
                            titre=f"Tag : {tag.name}",
                            contenu_texte=f"Tag : {tag.name}\nMessage : {message}",
                            auteur=auteur,
                            date_creation=tagged_date,
                            url_ou_chemin=str(self._repo_path),
                            metadonnees={
                                "tag_name": tag.name,
                                "commit_sha": tag.commit.hexsha,
                            },
                        )
                    )
                except Exception as exc:
                    logger.warning("Tag %s ignoré : %s", tag.name, exc)
        except Exception as exc:
            logger.error("Erreur lors de l'extraction des tags : %s", exc)

        return documents
