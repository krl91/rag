# Portage Windows — Problème 8 : `GitPython` et dépendance à `git` dans le PATH

## Contexte du projet

`kb-smart-metering` inclut un extracteur Git qui analyse l'historique des
dépôts de code source (commits, branches, tags). Il utilise la bibliothèque
`GitPython>=3.1.43`.

---

## Principe directeur

**Privilégier systématiquement ce qui est déjà disponible** sur la machine :
- Si `git` est déjà installé (Git for Windows très répandu chez les
  développeurs), utiliser `shutil.which("git")` pour le détecter et produire
  un message d'erreur clair plutôt que de changer de bibliothèque.
- Ne migrer vers `pygit2` que si `GitPython` présente des problèmes
  structurels sur Windows au-delà de la simple absence du binaire `git`.
- `shutil` est dans la stdlib — pas de dépendance supplémentaire pour la
  détection.

---

## Description du problème

`GitPython` est une bibliothèque Python qui **encapsule des appels au
binaire `git`** via des sous-processus (`subprocess`). Elle ne réimplémente
pas le protocole Git : elle a besoin que `git` soit installé et accessible
dans le `PATH` du processus Python.

Sur **Windows**, `git` n'est pas installé par défaut. Il doit être installé
manuellement, par exemple via :
- [Git for Windows](https://git-scm.com/download/win)
- `winget install Git.Git`
- `choco install git`

### Symptôme si `git` est absent

```
git.exc.GitCommandNotFound: Cmd('git') not found due to: FileNotFoundError('[WinError 2]
Le fichier spécifié est introuvable')
```

### Extracteur concerné

`src/kb_smart_metering/extractors/git.py` :

```python
import git

class GitExtractor:
    def __init__(self, repo_path: Union[str, Path]) -> None:
        self._repo_path = Path(repo_path)

    def extract(self) -> list[RawDocument]:
        try:
            repo = git.Repo(self._repo_path)
        except git.exc.InvalidGitRepositoryError as exc:
            logger.error("Dépôt Git invalide (%s) : %s", self._repo_path, exc)
            return []
        except git.exc.NoSuchPathError as exc:
            logger.error("Chemin introuvable (%s) : %s", self._repo_path, exc)
            return []
        ...
```

### Cas supplémentaire : chemins Windows dans GitPython

Sur Windows, les chemins retournés par `commit.stats.files.keys()` utilisent
des slashes Unix (`/`) car c'est la convention Git. Ce comportement est
généralement correct, mais vérifier qu'aucun code ne suppose des backslashes.

---

## Ce que tu dois analyser

### 1. Détection de `git` au démarrage

Ajouter une vérification explicite dans `GitExtractor.__init__` ou dans la
commande CLI `kb ingest --source git` :

```python
import shutil

if shutil.which("git") is None:
    raise RuntimeError(
        "git n'est pas trouvé dans le PATH. "
        "Installer Git for Windows : https://git-scm.com/download/win"
    )
```

- Où placer cette vérification (dans `__init__` ? dans `extract()` ?) pour
  un message d'erreur clair sans crash `FileNotFoundError` ?
- Faut-il un niveau de log `ERROR` ou une exception levée ?

### 2. Configuration du chemin `git` dans GitPython

GitPython permet de configurer le chemin vers l'exécutable git :

```python
import git
git.GIT_PYTHON_GIT_EXECUTABLE = r"C:\Program Files\Git\bin\git.exe"
```

Ou via la variable d'environnement `GIT_PYTHON_GIT_EXECUTABLE`.

- Est-ce une meilleure approche que la détection via `shutil.which` ?
- Comment exposer cette configuration dans le fichier `.env.example` du projet ?

### 3. Chemins dans `commit.stats.files`

`commit.stats.files.keys()` retourne des chemins au format Git (slashes Unix).
Dans le code actuel :

```python
fichiers = list(commit.stats.files.keys())
fichiers_text = "\n".join(f"  - {f}" for f in fichiers)
```

Ce code est-il correct sous Windows ? Y a-t-il des cas où GitPython retourne
des backslashes sous Windows (sous-modules, dépôts avec configuration
`core.autocrlf` ou `core.symlinks`) ?

### 4. Alternative : `pygit2`

`pygit2` est une alternative à GitPython qui utilise `libgit2` (bibliothèque C).
Elle ne dépend pas du binaire `git` dans le PATH et a des wheels Windows sur
PyPI. Est-elle une alternative viable ?

Comparer :
- Disponibilité des wheels Windows : `pygit2` vs `GitPython`
- API pour extraire commits, branches, tags
- Volume de changements dans `git.py` si migration vers `pygit2`

---

## Contraintes du projet

- `GitPython>=3.1.43` est spécifié dans `pyproject.toml`.
- L'extracteur Git est optionnel (la source `git` est une option CLI).
- Les tests dans `tests/test_extractors.py` mockent les appels GitPython
  (pas d'appel réseau ni de dépôt réel requis dans les tests).

---

## Livrable attendu

- Recommandation : ajouter la vérification `shutil.which` ou passer à `pygit2` ?
- Le diff dans `src/kb_smart_metering/extractors/git.py` (message d'erreur clair).
- Si `pygit2` est recommandé : diff complet de `git.py` + mise à jour de
  `pyproject.toml`.
- Ligne à ajouter dans `.env.example` si la variable `GIT_PYTHON_GIT_EXECUTABLE`
  est recommandée.
- Note dans le `README.md` sur l'installation de Git for Windows.
