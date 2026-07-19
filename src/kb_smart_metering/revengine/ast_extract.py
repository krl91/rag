"""
Extraction AST via tree-sitter — Java, Python, C#.

Produit pour chaque fichier un objet ExtractedModule contenant :
  - la liste des classes / interfaces
  - pour chaque classe : méthodes, appels sortants, événements publiés /
    consommés, modèles de données référencés
  - heuristiques événements : noms finissant par *Event, appels publish /
    subscribe / emit / dispatch / consume / listen

Usage :
    from kb_smart_metering.revengine.ast_extract import ASTExtractor, Language

    extractor = ASTExtractor(language=Language.JAVA)
    modules = extractor.extract_dir(Path("./src/main/java"))
"""

import logging
import re
from enum import Enum
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constantes heuristiques
# ---------------------------------------------------------------------------

# Noms de méthodes qui signalent une publication d'événement
_PUBLISH_VERBS: frozenset[str] = frozenset(
    {"publish", "emit", "dispatch", "fire", "raise", "send", "produce"}
)
# Noms de méthodes qui signalent une consommation d'événement
_SUBSCRIBE_VERBS: frozenset[str] = frozenset(
    {"subscribe", "consume", "listen", "on", "addlistener", "register", "handle"}
)
# Suffixe indiquant un type événement
_EVENT_SUFFIX_RE = re.compile(r"Event$")


# ---------------------------------------------------------------------------
# Langages supportés
# ---------------------------------------------------------------------------


class Language(str, Enum):
    """Langages supportés par l'extracteur AST."""

    JAVA = "java"
    PYTHON = "python"
    CSHARP = "csharp"


_LANG_EXTENSIONS: dict[Language, list[str]] = {
    Language.JAVA: [".java"],
    Language.PYTHON: [".py"],
    Language.CSHARP: [".cs"],
}


# ---------------------------------------------------------------------------
# Modèles de données (Pydantic v2)
# ---------------------------------------------------------------------------


class MethodInfo(BaseModel):
    """Informations extraites d'une méthode ou fonction."""

    name: str = Field(description="Nom de la méthode")
    line_start: int = Field(description="Ligne de début (1-based)")
    line_end: int = Field(description="Ligne de fin (1-based)")
    outgoing_calls: list[str] = Field(
        default_factory=list,
        description="Noms des méthodes / fonctions appelées depuis cette méthode",
    )
    events_published: list[str] = Field(
        default_factory=list,
        description="Types d'événements publiés détectés (heuristique)",
    )
    events_subscribed: list[str] = Field(
        default_factory=list,
        description="Types d'événements consommés détectés (heuristique)",
    )


class ClassInfo(BaseModel):
    """Informations extraites d'une classe, interface ou enum."""

    name: str = Field(description="Nom de la classe / interface")
    kind: str = Field(description="'class', 'interface', 'enum' ou 'record'")
    line_start: int = Field(description="Ligne de début (1-based)")
    line_end: int = Field(description="Ligne de fin (1-based)")
    methods: list[MethodInfo] = Field(default_factory=list)
    events_published: list[str] = Field(
        default_factory=list,
        description="Événements publiés agrégés de toutes les méthodes",
    )
    events_subscribed: list[str] = Field(
        default_factory=list,
        description="Événements consommés agrégés de toutes les méthodes",
    )
    data_models: list[str] = Field(
        default_factory=list,
        description="Types de données référencés (modèles détectés)",
    )
    outgoing_components: list[str] = Field(
        default_factory=list,
        description="Noms de composants appelés (heuristique sur les noms de champs)",
    )


class ExtractedModule(BaseModel):
    """Résultat de l'extraction AST d'un fichier source."""

    language: str = Field(description="Langage du fichier (java, python, csharp)")
    file_path: str = Field(description="Chemin absolu du fichier source")
    module_name: str = Field(description="Nom logique du module (stem du fichier)")
    package: Optional[str] = Field(
        default=None,
        description="Package / namespace (Java, C#) ou module Python",
    )
    classes: list[ClassInfo] = Field(default_factory=list)
    raw_source_excerpt: str = Field(
        default="",
        description="Les 500 premiers caractères du fichier (contexte pour le LLM)",
    )


# ---------------------------------------------------------------------------
# Fonctions utilitaires internes
# ---------------------------------------------------------------------------


def _node_text(node: object, source: bytes) -> str:
    """Retourne le texte brut d'un nœud AST (décodage UTF-8 lenient)."""
    # tree-sitter Node : attributs start_byte, end_byte
    start: int = getattr(node, "start_byte", 0)
    end: int = getattr(node, "end_byte", 0)
    return source[start:end].decode("utf-8", errors="replace")


def _node_line(node: object) -> int:
    """Retourne la ligne de début d'un nœud (1-based)."""
    point = getattr(node, "start_point", (0, 0))
    return point[0] + 1


def _node_end_line(node: object) -> int:
    """Retourne la ligne de fin d'un nœud (1-based)."""
    point = getattr(node, "end_point", (0, 0))
    return point[0] + 1


def _is_event_type(name: str) -> bool:
    """Indique si un nom ressemble à un type événement (heuristique)."""
    return bool(_EVENT_SUFFIX_RE.search(name))


def _classify_call(method_name: str) -> Optional[str]:
    """
    Classifie un appel de méthode comme 'publish', 'subscribe' ou None.

    Comparaison insensible à la casse sur les verbes heuristiques.
    """
    lower = method_name.lower()
    if any(verb in lower for verb in _PUBLISH_VERBS):
        return "publish"
    if any(verb in lower for verb in _SUBSCRIBE_VERBS):
        return "subscribe"
    return None


def _iter_children(node: object):
    """Itère récursivement sur tous les nœuds descendants."""
    children = getattr(node, "children", [])
    for child in children:
        yield child
        yield from _iter_children(child)


def _direct_children_of_type(node: object, *types: str):
    """Retourne les enfants directs dont le type est dans `types`."""
    children = getattr(node, "children", [])
    return [c for c in children if getattr(c, "type", "") in types]


def _first_child_of_type(node: object, *types: str) -> Optional[object]:
    """Retourne le premier enfant direct dont le type est dans `types`."""
    children = getattr(node, "children", [])
    for c in children:
        if getattr(c, "type", "") in types:
            return c
    return None


# ---------------------------------------------------------------------------
# Extracteurs par langage
# ---------------------------------------------------------------------------


class _JavaExtractor:
    """Extraction AST pour les fichiers Java."""

    def __init__(self, source: bytes) -> None:
        self._src = source

    def extract_package(self, root: object) -> Optional[str]:
        """Extrait la déclaration de package."""
        for child in getattr(root, "children", []):
            if getattr(child, "type", "") == "package_declaration":
                # package_declaration > scoped_identifier ou qualified_name
                for desc in _iter_children(child):
                    t = getattr(desc, "type", "")
                    if t in ("scoped_identifier", "identifier"):
                        return _node_text(desc, self._src)
        return None

    def extract_classes(self, root: object) -> list[ClassInfo]:
        """Extrait toutes les classes et interfaces du fichier."""
        results: list[ClassInfo] = []
        self._walk_classes(root, results)
        return results

    def _walk_classes(self, node: object, results: list[ClassInfo]) -> None:
        node_type = getattr(node, "type", "")
        if node_type == "class_declaration":
            results.append(self._parse_class(node, "class"))
        elif node_type == "interface_declaration":
            results.append(self._parse_class(node, "interface"))
        elif node_type == "enum_declaration":
            results.append(self._parse_class(node, "enum"))
        else:
            for child in getattr(node, "children", []):
                self._walk_classes(child, results)

    def _parse_class(self, node: object, kind: str) -> ClassInfo:
        name = ""
        for child in getattr(node, "children", []):
            if getattr(child, "type", "") == "identifier":
                name = _node_text(child, self._src)
                break

        methods: list[MethodInfo] = []
        data_models: set[str] = set()
        outgoing_components: set[str] = set()

        # Cherche le corps de la classe
        body = _first_child_of_type(node, "class_body", "interface_body", "enum_body")
        if body:
            for child in getattr(body, "children", []):
                ct = getattr(child, "type", "")
                if ct == "method_declaration":
                    m = self._parse_method(child)
                    methods.append(m)
                elif ct == "field_declaration":
                    # Heuristique : le type du champ → composant dépendant
                    type_node = _first_child_of_type(child, "type_identifier")
                    if type_node:
                        type_name = _node_text(type_node, self._src)
                        # Exclure les types primitifs et standards
                        if (
                            type_name
                            and type_name[0].isupper()
                            and not _is_event_type(type_name)
                        ):
                            outgoing_components.add(type_name)

        # Agréger les événements de toutes les méthodes
        published: list[str] = []
        subscribed: list[str] = []
        for m in methods:
            published.extend(m.events_published)
            subscribed.extend(m.events_subscribed)
            # Collecter les types de données depuis les appels sortants
            for call in m.outgoing_calls:
                if _is_event_type(call):
                    data_models.add(call)

        return ClassInfo(
            name=name,
            kind=kind,
            line_start=_node_line(node),
            line_end=_node_end_line(node),
            methods=methods,
            events_published=list(dict.fromkeys(published)),
            events_subscribed=list(dict.fromkeys(subscribed)),
            data_models=list(data_models),
            outgoing_components=list(outgoing_components),
        )

    def _parse_method(self, node: object) -> MethodInfo:
        name = ""
        for child in getattr(node, "children", []):
            if getattr(child, "type", "") == "identifier":
                name = _node_text(child, self._src)
                break

        outgoing: list[str] = []
        published: list[str] = []
        subscribed: list[str] = []

        for desc in _iter_children(node):
            dt = getattr(desc, "type", "")
            if dt == "method_invocation":
                # Structure Java : identifier [. identifier]* argument_list
                # Le nom de la méthode est le dernier identifier avant argument_list
                children = getattr(desc, "children", [])
                arg_list_idx = next(
                    (
                        i
                        for i, c in enumerate(children)
                        if getattr(c, "type", "") == "argument_list"
                    ),
                    len(children),
                )
                ids_before_args = [
                    c
                    for c in children[:arg_list_idx]
                    if getattr(c, "type", "") == "identifier"
                ]
                if not ids_before_args:
                    continue
                call_name = _node_text(ids_before_args[-1], self._src)
                outgoing.append(call_name)
                kind = _classify_call(call_name)
                if kind:
                    # Chercher les types *Event dans les arguments
                    for arg_desc in _iter_children(desc):
                        if getattr(arg_desc, "type", "") == "object_creation_expression":
                            type_node = _first_child_of_type(
                                arg_desc, "type_identifier"
                            )
                            if type_node:
                                evt = _node_text(type_node, self._src)
                                if _is_event_type(evt):
                                    if kind == "publish":
                                        published.append(evt)
                                    else:
                                        subscribed.append(evt)

        return MethodInfo(
            name=name,
            line_start=_node_line(node),
            line_end=_node_end_line(node),
            outgoing_calls=list(dict.fromkeys(outgoing)),
            events_published=list(dict.fromkeys(published)),
            events_subscribed=list(dict.fromkeys(subscribed)),
        )


class _PythonExtractor:
    """Extraction AST pour les fichiers Python."""

    def __init__(self, source: bytes) -> None:
        self._src = source

    def extract_package(self, root: object, file_path: Path) -> Optional[str]:
        """Retourne le chemin de module Python (relatif au repo)."""
        return file_path.stem

    def extract_classes(self, root: object) -> list[ClassInfo]:
        """Extrait toutes les classes du fichier."""
        results: list[ClassInfo] = []
        for child in getattr(root, "children", []):
            if getattr(child, "type", "") == "class_definition":
                results.append(self._parse_class(child))
        return results

    def _parse_class(self, node: object) -> ClassInfo:
        name = ""
        for child in getattr(node, "children", []):
            if getattr(child, "type", "") == "identifier":
                name = _node_text(child, self._src)
                break

        methods: list[MethodInfo] = []
        data_models: set[str] = set()

        body = _first_child_of_type(node, "block")
        if body:
            for child in getattr(body, "children", []):
                if getattr(child, "type", "") == "function_definition":
                    methods.append(self._parse_method(child))

        published: list[str] = []
        subscribed: list[str] = []
        for m in methods:
            published.extend(m.events_published)
            subscribed.extend(m.events_subscribed)

        return ClassInfo(
            name=name,
            kind="class",
            line_start=_node_line(node),
            line_end=_node_end_line(node),
            methods=methods,
            events_published=list(dict.fromkeys(published)),
            events_subscribed=list(dict.fromkeys(subscribed)),
            data_models=list(data_models),
        )

    def _parse_method(self, node: object) -> MethodInfo:
        name = ""
        for child in getattr(node, "children", []):
            if getattr(child, "type", "") == "identifier":
                name = _node_text(child, self._src)
                break

        outgoing: list[str] = []
        published: list[str] = []
        subscribed: list[str] = []

        for desc in _iter_children(node):
            dt = getattr(desc, "type", "")
            if dt == "call":
                func_node = _first_child_of_type(desc, "identifier", "attribute")
                if func_node:
                    fn_type = getattr(func_node, "type", "")
                    if fn_type == "attribute":
                        # obj.method — récupère le nom de méthode (dernier identifier)
                        ids = _direct_children_of_type(func_node, "identifier")
                        call_name = _node_text(ids[-1], self._src) if ids else ""
                    else:
                        call_name = _node_text(func_node, self._src)

                    if call_name:
                        outgoing.append(call_name)
                        kind = _classify_call(call_name)
                        if kind:
                            # Chercher des *Event dans les arguments
                            args_node = _first_child_of_type(desc, "argument_list")
                            if args_node:
                                for arg in _iter_children(args_node):
                                    arg_type = getattr(arg, "type", "")
                                    if arg_type == "call":
                                        # SomeEvent() ou SomeEvent(...)
                                        arg_func = _first_child_of_type(
                                            arg, "identifier", "attribute"
                                        )
                                        if arg_func:
                                            evt_name = _node_text(arg_func, self._src)
                                            if _is_event_type(evt_name):
                                                if kind == "publish":
                                                    published.append(evt_name)
                                                else:
                                                    subscribed.append(evt_name)
                                    elif arg_type == "identifier":
                                        evt_name = _node_text(arg, self._src)
                                        if _is_event_type(evt_name):
                                            if kind == "publish":
                                                published.append(evt_name)
                                            else:
                                                subscribed.append(evt_name)

        return MethodInfo(
            name=name,
            line_start=_node_line(node),
            line_end=_node_end_line(node),
            outgoing_calls=list(dict.fromkeys(outgoing)),
            events_published=list(dict.fromkeys(published)),
            events_subscribed=list(dict.fromkeys(subscribed)),
        )


class _CSharpExtractor:
    """Extraction AST pour les fichiers C# (.cs)."""

    def __init__(self, source: bytes) -> None:
        self._src = source

    def extract_namespace(self, root: object) -> Optional[str]:
        """Extrait le namespace C#."""
        for desc in _iter_children(root):
            if getattr(desc, "type", "") in (
                "namespace_declaration",
                "file_scoped_namespace_declaration",
            ):
                name_node = _first_child_of_type(
                    desc, "identifier", "qualified_name"
                )
                if name_node:
                    return _node_text(name_node, self._src)
        return None

    def extract_classes(self, root: object) -> list[ClassInfo]:
        """Extrait toutes les classes et interfaces du fichier."""
        results: list[ClassInfo] = []
        self._walk(root, results)
        return results

    def _walk(self, node: object, results: list[ClassInfo]) -> None:
        nt = getattr(node, "type", "")
        if nt == "class_declaration":
            results.append(self._parse_class(node, "class"))
        elif nt == "interface_declaration":
            results.append(self._parse_class(node, "interface"))
        elif nt == "record_declaration":
            results.append(self._parse_class(node, "record"))
        else:
            for child in getattr(node, "children", []):
                self._walk(child, results)

    def _parse_class(self, node: object, kind: str) -> ClassInfo:
        name = ""
        for child in getattr(node, "children", []):
            if getattr(child, "type", "") == "identifier":
                name = _node_text(child, self._src)
                break

        methods: list[MethodInfo] = []
        data_models: set[str] = set()
        outgoing: set[str] = set()
        events_decl: list[str] = []

        body = _first_child_of_type(node, "declaration_list")
        if body:
            for child in getattr(body, "children", []):
                ct = getattr(child, "type", "")
                if ct == "method_declaration":
                    methods.append(self._parse_method(child))
                elif ct == "event_field_declaration":
                    # C# : public event EventHandler SomethingHappened;
                    vd = _first_child_of_type(child, "variable_declaration")
                    if vd:
                        for vdesc in getattr(vd, "children", []):
                            if getattr(vdesc, "type", "") == "variable_declarator":
                                eid = _first_child_of_type(vdesc, "identifier")
                                if eid:
                                    events_decl.append(_node_text(eid, self._src))
                elif ct == "field_declaration":
                    # Champs → composants dépendants
                    vd = _first_child_of_type(child, "variable_declaration")
                    if vd:
                        type_node = _first_child_of_type(vd, "identifier")
                        if type_node:
                            type_name = _node_text(type_node, self._src)
                            if (
                                type_name
                                and type_name[0].isupper()
                                and not _is_event_type(type_name)
                            ):
                                outgoing.add(type_name)

        published: list[str] = []
        subscribed: list[str] = []
        for m in methods:
            published.extend(m.events_published)
            subscribed.extend(m.events_subscribed)
        # Les événements C# déclarés dans la classe sont comptés comme publiés
        published.extend(events_decl)

        return ClassInfo(
            name=name,
            kind=kind,
            line_start=_node_line(node),
            line_end=_node_end_line(node),
            methods=methods,
            events_published=list(dict.fromkeys(published)),
            events_subscribed=list(dict.fromkeys(subscribed)),
            data_models=list(data_models),
            outgoing_components=list(outgoing),
        )

    def _parse_method(self, node: object) -> MethodInfo:
        name = ""
        for child in getattr(node, "children", []):
            if getattr(child, "type", "") == "identifier":
                name = _node_text(child, self._src)
                break

        outgoing: list[str] = []
        published: list[str] = []
        subscribed: list[str] = []

        for desc in _iter_children(node):
            dt = getattr(desc, "type", "")
            if dt == "invocation_expression":
                # C# : obj.Method(args)
                fn = _first_child_of_type(desc, "member_access_expression", "identifier")
                if fn:
                    fn_type = getattr(fn, "type", "")
                    if fn_type == "member_access_expression":
                        ids = _direct_children_of_type(fn, "identifier")
                        call_name = _node_text(ids[-1], self._src) if ids else ""
                    else:
                        call_name = _node_text(fn, self._src)

                    if call_name:
                        outgoing.append(call_name)
                        kind = _classify_call(call_name)
                        if kind:
                            # Chercher *Event dans les arguments
                            args = _first_child_of_type(desc, "argument_list")
                            if args:
                                for arg_desc in _iter_children(args):
                                    adt = getattr(arg_desc, "type", "")
                                    if adt == "object_creation_expression":
                                        t = _first_child_of_type(
                                            arg_desc, "identifier"
                                        )
                                        if t:
                                            evt = _node_text(t, self._src)
                                            if _is_event_type(evt):
                                                if kind == "publish":
                                                    published.append(evt)
                                                else:
                                                    subscribed.append(evt)
                                    elif adt == "identifier":
                                        evt = _node_text(arg_desc, self._src)
                                        if _is_event_type(evt):
                                            if kind == "publish":
                                                published.append(evt)
                                            else:
                                                subscribed.append(evt)

        return MethodInfo(
            name=name,
            line_start=_node_line(node),
            line_end=_node_end_line(node),
            outgoing_calls=list(dict.fromkeys(outgoing)),
            events_published=list(dict.fromkeys(published)),
            events_subscribed=list(dict.fromkeys(subscribed)),
        )


# ---------------------------------------------------------------------------
# Classe principale
# ---------------------------------------------------------------------------


class ASTExtractor:
    """
    Extracteur AST multi-langages (Java, Python, C#).

    Paramètres
    ----------
    language : Language
        Langage cible.
    """

    def __init__(self, language: Language) -> None:
        self._language = language
        self._parser = self._build_parser(language)

    @staticmethod
    def _build_parser(language: Language) -> object:
        """Construit et retourne un parser tree-sitter pour le langage donné."""
        try:
            import tree_sitter_language_pack as tlp
        except ImportError as exc:
            raise ImportError(
                "Le module revengine nécessite tree-sitter-language-pack. "
                "Installer avec : uv sync --extra revengine"
            ) from exc

        lang_id = language.value
        if not tlp.has_language(lang_id):
            logger.info("Téléchargement du support tree-sitter pour '%s'…", lang_id)
            tlp.download([lang_id])
        return tlp.get_parser(lang_id)

    def extract_file(self, file_path: Path) -> Optional[ExtractedModule]:
        """
        Extrait les informations AST d'un fichier source.

        Retourne None si le fichier ne peut pas être parsé.
        """
        try:
            source = file_path.read_bytes()
        except OSError as exc:
            logger.warning("Impossible de lire %s : %s", file_path, exc)
            return None

        try:
            tree = self._parser.parse(source)  # type: ignore[union-attr]
        except Exception as exc:
            logger.warning("Parsing échoué pour %s : %s", file_path, exc)
            return None

        root = tree.root_node
        return self._build_module(root, source, file_path)

    def extract_dir(self, repo_path: Path) -> list[ExtractedModule]:
        """
        Extrait récursivement tous les fichiers du langage dans `repo_path`.

        Ignore les répertoires cachés (.git, __pycache__, .venv, node_modules).
        """
        _IGNORED_DIRS = {".git", "__pycache__", ".venv", "node_modules", "target", "build"}
        extensions = _LANG_EXTENSIONS[self._language]
        modules: list[ExtractedModule] = []

        for ext in extensions:
            for fpath in sorted(repo_path.rglob(f"*{ext}")):
                if any(part in _IGNORED_DIRS for part in fpath.parts):
                    continue
                m = self.extract_file(fpath)
                if m:
                    modules.append(m)
                    logger.info("Extrait : %s (%d classes)", fpath, len(m.classes))

        return modules

    def _build_module(
        self, root: object, source: bytes, file_path: Path
    ) -> ExtractedModule:
        """Construit un ExtractedModule à partir de l'AST."""
        lang = self._language.value
        excerpt = source[:500].decode("utf-8", errors="replace")

        if self._language == Language.JAVA:
            extractor = _JavaExtractor(source)
            classes = extractor.extract_classes(root)
            package = extractor.extract_package(root)
        elif self._language == Language.PYTHON:
            extractor_py = _PythonExtractor(source)
            classes = extractor_py.extract_classes(root)
            package = extractor_py.extract_package(root, file_path)
        else:
            extractor_cs = _CSharpExtractor(source)
            classes = extractor_cs.extract_classes(root)
            package = extractor_cs.extract_namespace(root)

        return ExtractedModule(
            language=lang,
            file_path=str(file_path.resolve()),
            module_name=file_path.stem,
            package=package,
            classes=classes,
            raw_source_excerpt=excerpt,
        )
