"""
Migration des episode_keys Windows — remplacement des backslashes par des slashes.

Contexte
--------
Avant le correctif de portage Windows (Problème 4), les extracteurs de fichiers
locaux (office.py, meetings.py) utilisaient ``str(Path.resolve())`` pour
construire ``id_source``. Sur Windows, cela produisait des chemins avec
backslashes (``C:\\Users\\...``), rendant les episode_keys de la base SQLite
non portables.

Après le correctif, ``normalize_file_source_id`` utilise ``Path.as_posix()``
qui retourne des slashes (``C:/Users/...``).

Ce script met à jour toutes les episode_keys existantes qui contiennent des
backslashes en les remplaçant par des slashes POSIX.

Usage
-----
    # Affiche les clés qui seraient modifiées (dry-run)
    uv run python scripts/migrate_episode_keys.py

    # Applique réellement la migration
    uv run python scripts/migrate_episode_keys.py --apply

    # Chemin personnalisé vers la base SQLite
    uv run python scripts/migrate_episode_keys.py --db data/ingestion_tracking.db --apply
"""

import argparse
import logging
import sqlite3
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

DEFAULT_DB = Path("data") / "ingestion_tracking.db"


def _normalize_key(key: str) -> str:
    """Remplace les backslashes par des slashes dans une episode_key."""
    return key.replace("\\", "/")


def migrate(db_path: Path, apply: bool) -> None:
    """
    Parcourt la table ingested_episodes et corrige les clés contenant des backslashes.

    Args:
        db_path: Chemin vers la base SQLite.
        apply: Si True, applique les modifications. Si False, affiche seulement.
    """
    if not db_path.exists():
        logger.error("Base SQLite introuvable : %s", db_path)
        raise SystemExit(1)

    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(
            "SELECT episode_key, content_hash, ingested_at FROM ingested_episodes"
        ).fetchall()

    to_update: list[tuple[str, str, str, str]] = []
    for episode_key, content_hash, ingested_at in rows:
        if "\\" in episode_key:
            new_key = _normalize_key(episode_key)
            to_update.append((new_key, content_hash, ingested_at, episode_key))
            logger.info("  [à migrer] %r\n             → %r", episode_key, new_key)

    if not to_update:
        logger.info("Aucune clé avec backslash trouvée — base déjà à jour.")
        return

    logger.info("%d clé(s) à migrer.", len(to_update))

    if not apply:
        logger.info("Mode dry-run — aucune modification appliquée. Relancer avec --apply.")
        return

    with sqlite3.connect(db_path) as conn:
        for new_key, content_hash, ingested_at, old_key in to_update:
            # Vérifier qu'une entrée avec la nouvelle clé n'existe pas déjà
            existing = conn.execute(
                "SELECT 1 FROM ingested_episodes WHERE episode_key = ?",
                (new_key,),
            ).fetchone()
            if existing:
                logger.warning(
                    "Clé cible déjà présente, suppression de l'ancienne : %r", old_key
                )
                conn.execute(
                    "DELETE FROM ingested_episodes WHERE episode_key = ?",
                    (old_key,),
                )
            else:
                conn.execute(
                    """
                    INSERT INTO ingested_episodes (episode_key, content_hash, ingested_at)
                    VALUES (?, ?, ?)
                    """,
                    (new_key, content_hash, ingested_at),
                )
                conn.execute(
                    "DELETE FROM ingested_episodes WHERE episode_key = ?",
                    (old_key,),
                )
        conn.commit()

    logger.info("Migration terminée : %d clé(s) mise(s) à jour.", len(to_update))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Migre les episode_keys Windows (backslashes → slashes POSIX)."
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=DEFAULT_DB,
        help=f"Chemin vers la base SQLite (défaut : {DEFAULT_DB})",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Applique réellement les modifications (sans ce flag : dry-run).",
    )
    args = parser.parse_args()

    mode = "APPLY" if args.apply else "DRY-RUN"
    logger.info("Migration episode_keys — mode %s — base : %s", mode, args.db)
    migrate(db_path=args.db, apply=args.apply)


if __name__ == "__main__":
    main()
