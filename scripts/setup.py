"""Script de configuration initiale cross-platform.

Équivalent de : cp -n .env.example .env || true
Sémantique : copie .env.example vers .env uniquement si .env n'existe pas encore.
Usage : uv run python scripts/setup.py
"""

import shutil
import sys
from pathlib import Path


def copy_env_if_missing() -> None:
    """Copie .env.example vers .env si .env est absent."""
    root = Path(__file__).resolve().parent.parent
    src = root / ".env.example"
    dst = root / ".env"

    if not src.exists():
        print(f"AVERTISSEMENT : {src} introuvable — .env non créé.", file=sys.stderr)
        return

    if dst.exists():
        print(f".env déjà présent ({dst}) — aucune modification.")
        return

    shutil.copy2(src, dst)
    print(f".env créé depuis .env.example ({dst}).")
    print("Pensez à renseigner les variables dans .env avant de démarrer les services.")


if __name__ == "__main__":
    copy_env_if_missing()
