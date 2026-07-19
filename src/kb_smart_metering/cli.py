"""
Interface en ligne de commande (CLI) — point d'entrée `kb`.

Commandes disponibles :
  kb version                              — version du package
  kb ingest --source jira --project XXX  — ingère les tickets Jira du projet XXX
  kb ingest --source confluence --space YYY — ingère les pages Confluence
  kb ingest --source git --path /repo    — ingère l'historique Git
  kb ingest --source file --path /doc    — ingère un fichier bureau (Word/PDF/Excel)
  kb ingest --source meeting --path /tx  — ingère une transcription de réunion
                                             (kb ingest ci-dessus nécessite un LLM réseau
                                             joignable — Ollama. Sans LLM : voir kb extract
                                             + kb ingest-extraction ci-dessous)
  kb extract --source jira --project XXX --out data/raw/
                                           — extrait une source en RawDocument JSON, SANS
                                             ingestion ni appel LLM ; l'agent Copilot lit
                                             ensuite ces fichiers et fait l'extraction lui-
                                             même en conversation (voir skill kb-ingest)
  kb ingest-extraction chemin.json        — écrit dans Neo4j une extraction JSON déjà
                                             produite par l'agent (voir skill kb-ingest) ;
                                             aucun appel LLM côté Python
  kb ask "question"                       — pose une question au graphe de connaissances
                                             (nécessite un LLM réseau joignable : Ollama)
  kb search "question"                    — retrieval + contexte, SANS appel LLM ;
                                             utilisé par l'agent Copilot en conversation
                                             (voir skill kb-chercheur) pour rédiger la
                                             réponse lui-même à partir du contexte
  kb reveng --repo ./chemin --lang java   — analyse + ingère (nécessite un LLM réseau ;
                                             sans LLM : kb reveng --out data/raw/ puis le
                                             flux kb-ingest, comme pour les autres sources)
  kb docgen --module Export --out docs/  — génère la doc Markdown d'un module (nécessite
                                             un LLM réseau ; sans LLM : kb docgen
                                             --extract-only --out … puis, après complétion
                                             par l'agent, kb docgen --from-extraction …)

Ajouter --dry-run pour simuler sans écriture (ingest, ingest-extraction, reveng).
"""

import asyncio
import logging
import sys
from pathlib import Path
from typing import Annotated, Optional

import typer

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Encodage console Windows (cp1252 → UTF-8)
# Reconfigure stdout/stderr en UTF-8 au démarrage du CLI.
# Sans effet sur Linux/macOS (guard sys.platform).
# ---------------------------------------------------------------------------
if sys.platform == "win32":
    for _stream in (sys.stdout, sys.stderr):
        try:
            _stream.reconfigure(encoding="utf-8", errors="replace")
        except AttributeError:
            pass  # stream sans .reconfigure() (ex : capsys de pytest)

app = typer.Typer(
    name="kb",
    help="Système de gestion des connaissances projet smart metering.",
)


@app.command()
def version() -> None:
    """Affiche la version du package."""
    from kb_smart_metering import __version__

    typer.echo(f"kb-smart-metering v{__version__}")


@app.command()
def ingest(
    source: Annotated[
        str,
        typer.Option("--source", help="Source : jira | confluence | git | file | meeting"),
    ],
    project: Annotated[
        Optional[str],
        typer.Option("--project", help="Clé de projet Jira (ex: SMART)"),
    ] = None,
    space: Annotated[
        Optional[str],
        typer.Option("--space", help="Clé d'espace Confluence (ex: ARCH)"),
    ] = None,
    path: Annotated[
        Optional[str],
        typer.Option("--path", help="Chemin fichier ou répertoire (git, file, meeting)"),
    ] = None,
    group_id: Annotated[
        str,
        typer.Option("--group-id", help="Partition du graphe Graphiti"),
    ] = "smart_metering",
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Simulation sans écriture dans Neo4j"),
    ] = False,
) -> None:
    """Ingère une source de données dans le graphe de connaissances."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s — %(message)s",
    )

    valid_sources = {"jira", "confluence", "git", "file", "meeting"}
    if source not in valid_sources:
        typer.echo(f"[erreur] --source doit être parmi : {', '.join(sorted(valid_sources))}")
        raise typer.Exit(code=1)

    docs = _extract(source=source, project=project, space=space, path=path)
    if not docs:
        typer.echo("Aucun document extrait.")
        raise typer.Exit(code=0)

    typer.echo(
        f"{'[dry-run] ' if dry_run else ''}Ingestion de {len(docs)} document(s) "
        f"(source={source}, group={group_id})…"
    )

    asyncio.run(_run_ingestion(docs=docs, group_id=group_id, dry_run=dry_run))


@app.command()
def extract(
    source: Annotated[
        str,
        typer.Option("--source", help="Source : jira | confluence | git | file | meeting"),
    ],
    project: Annotated[
        Optional[str],
        typer.Option("--project", help="Clé de projet Jira (ex: SMART)"),
    ] = None,
    space: Annotated[
        Optional[str],
        typer.Option("--space", help="Clé d'espace Confluence (ex: ARCH)"),
    ] = None,
    path: Annotated[
        Optional[str],
        typer.Option("--path", help="Chemin fichier ou répertoire (git, file, meeting)"),
    ] = None,
    out: Annotated[
        str,
        typer.Option("--out", help="Répertoire de sortie pour les RawDocument JSON"),
    ] = "data/raw",
) -> None:
    """
    Extrait une source en RawDocument JSON — AUCUNE ingestion, AUCUN appel LLM.

    Destiné à l'agent Copilot en conversation (voir skill kb-ingest) : après
    cette commande, l'agent lit chaque fichier JSON produit, extrait lui-même
    les entités/relations, puis appelle `kb ingest-extraction` pour chacun.
    """
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s — %(message)s",
    )

    valid_sources = {"jira", "confluence", "git", "file", "meeting"}
    if source not in valid_sources:
        typer.echo(f"[erreur] --source doit être parmi : {', '.join(sorted(valid_sources))}")
        raise typer.Exit(code=1)

    docs = _extract(source=source, project=project, space=space, path=path)
    if not docs:
        typer.echo("Aucun document extrait.")
        raise typer.Exit(code=0)

    written = _write_raw_documents(docs, Path(out))
    typer.echo(f"{len(written)} document(s) extrait(s) dans '{out}/' :")
    for fpath in written:
        typer.echo(f"  {fpath}")
    typer.echo(
        "\nProchaine étape : pour chaque fichier, extraire entités/relations "
        "(voir skill kb-ingest) puis lancer :\n"
        "  kb ingest-extraction <fichier_extraction.json>"
    )


@app.command("ingest-extraction")
def ingest_extraction(
    extraction_file: Annotated[
        Path,
        typer.Argument(help="Fichier JSON produit par l'agent (schéma ExtractionResult)"),
    ],
    group_id: Annotated[
        str,
        typer.Option("--group-id", help="Partition du graphe"),
    ] = "smart_metering",
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Valide le JSON sans écrire dans Neo4j"),
    ] = False,
) -> None:
    """
    Écrit dans Neo4j une extraction JSON déjà produite par l'agent Copilot.

    Aucun appel LLM ici : Python valide et écrit ce que l'agent a extrait
    pendant la conversation (voir skill kb-ingest pour le format attendu et
    kb_smart_metering.ingestion.extraction_schema.ExtractionResult).
    L'idempotence est assurée par la clé métier (ExtractedEntity.key) — pas
    de résolution floue : deux extractions utilisant la même clé pour une
    entité sont fusionnées sur le même nœud.
    """
    import json as _json

    from kb_smart_metering.ingestion.extraction_schema import ExtractionResult

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s — %(message)s",
    )

    if not extraction_file.exists():
        typer.echo(f"[erreur] Fichier introuvable : {extraction_file}")
        raise typer.Exit(code=1)

    try:
        data = _json.loads(extraction_file.read_text(encoding="utf-8"))
        extraction = ExtractionResult.model_validate(data)
    except Exception as exc:
        typer.echo(f"[erreur] JSON invalide ou non conforme au schéma : {exc}")
        raise typer.Exit(code=1)

    typer.echo(
        f"{'[dry-run] ' if dry_run else ''}Écriture de '{extraction.source_ref}' "
        f"({len(extraction.entities)} entité(s), {len(extraction.relations)} relation(s))…"
    )

    if dry_run:
        typer.echo("[dry-run] Aucune écriture effectuée.")
        return

    asyncio.run(_run_ingest_extraction(extraction=extraction, group_id=group_id))


# ---------------------------------------------------------------------------
# Helpers privés
# ---------------------------------------------------------------------------


def _write_raw_documents(docs: list, out_dir: Path) -> list[Path]:
    """Écrit une liste de RawDocument en JSON (un fichier par document), sans appel LLM."""
    import re

    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for doc in docs:
        safe_id = re.sub(r"[^A-Za-z0-9_.-]", "_", doc.id_source)[:80]
        fpath = out_dir / f"{doc.source_type}_{safe_id}.json"
        fpath.write_text(doc.model_dump_json(indent=2), encoding="utf-8")
        written.append(fpath)
    return written


def _extract(
    source: str,
    project: Optional[str],
    space: Optional[str],
    path: Optional[str],
) -> list:
    """Délègue l'extraction à l'extracteur approprié et retourne des RawDocument."""
    from kb_smart_metering.config import settings

    if source == "jira":
        if not project:
            typer.echo("[erreur] --project est requis pour la source jira")
            raise typer.Exit(code=1)
        from kb_smart_metering.extractors.jira import JiraExtractor

        extractor = JiraExtractor(
            url=settings.jira_url,
            token=settings.jira_token,
        )
        return extractor.extract_project(project_key=project)

    if source == "confluence":
        if not space:
            typer.echo("[erreur] --space est requis pour la source confluence")
            raise typer.Exit(code=1)
        from kb_smart_metering.extractors.confluence import ConfluenceExtractor

        extractor = ConfluenceExtractor(
            url=settings.confluence_url,
            token=settings.confluence_token,
        )
        return extractor.extract_space(space_key=space)

    if source == "git":
        if not path:
            typer.echo("[erreur] --path est requis pour la source git")
            raise typer.Exit(code=1)
        from kb_smart_metering.extractors.git import GitExtractor

        extractor = GitExtractor(repo_path=path)
        return extractor.extract_commits()

    if source == "file":
        if not path:
            typer.echo("[erreur] --path est requis pour la source file")
            raise typer.Exit(code=1)
        return _extract_files(Path(path))

    if source == "meeting":
        if not path:
            typer.echo("[erreur] --path est requis pour la source meeting")
            raise typer.Exit(code=1)
        from kb_smart_metering.extractors.meetings import MeetingExtractor

        extractor = MeetingExtractor()
        target = Path(path)
        if target.is_file():
            return [extractor.extract(target)]
        return [extractor.extract(f) for f in sorted(target.iterdir()) if f.is_file()]

    return []


def _extract_files(target: Path) -> list:
    """Extrait un fichier ou tous les fichiers d'un répertoire."""
    from kb_smart_metering.extractors.office import ExcelExtractor, PdfExtractor, WordExtractor

    files = [target] if target.is_file() else sorted(target.iterdir())
    docs = []
    for f in files:
        suffix = f.suffix.lower()
        if suffix == ".docx":
            docs.append(WordExtractor().extract(f))
        elif suffix in {".xlsx", ".xls"}:
            docs.append(ExcelExtractor().extract(f))
        elif suffix == ".pdf":
            docs.append(PdfExtractor().extract(f))
        else:
            logger.warning("Format non supporté ignoré : %s", f)
    return docs


async def _run_ingestion(docs: list, group_id: str, dry_run: bool) -> None:
    """Lance l'ingestion asynchrone et affiche le résumé."""
    from kb_smart_metering.ingestion.graphiti import build_graphiti
    from kb_smart_metering.ingestion.pipeline import IngestionPipeline

    graphiti = build_graphiti()
    await graphiti.build_indices_and_constraints()
    try:
        pipeline = IngestionPipeline(graphiti=graphiti, group_id=group_id)
        results = await pipeline.ingest_batch(docs=docs, dry_run=dry_run)
    finally:
        await graphiti.close()

    total_nodes = sum(r.nodes_created for r in results)
    total_edges = sum(r.edges_created for r in results)
    skipped = sum(1 for r in results if r.skipped)

    typer.echo(
        f"\nRésumé : {len(results)} épisodes "
        f"({len(results) - skipped} ingérés, {skipped} ignorés), "
        f"{total_nodes} entités, {total_edges} relations."
    )


async def _run_ingest_extraction(extraction, group_id: str) -> None:
    """Construit un Graphiti (driver + embedder, sans dépendre du LLM) et écrit l'extraction."""
    from kb_smart_metering.ingestion.graph_writer import GraphWriter
    from kb_smart_metering.ingestion.graphiti import build_graphiti

    graphiti = build_graphiti()
    await graphiti.build_indices_and_constraints()
    try:
        writer = GraphWriter(driver=graphiti.driver, embedder=graphiti.embedder, group_id=group_id)
        result = await writer.write(extraction)
    finally:
        await graphiti.close()

    typer.echo(
        f"\nRésumé : {result.nodes_created} entité(s) créée(s), "
        f"{result.nodes_reused} réutilisée(s), {result.edges_created} relation(s)."
    )


# ---------------------------------------------------------------------------
# Commandes de rétro-ingénierie
# ---------------------------------------------------------------------------


@app.command()
def reveng(
    repo: Annotated[
        str,
        typer.Option("--repo", help="Chemin du dépôt de code source à analyser"),
    ],
    lang: Annotated[
        str,
        typer.Option(
            "--lang",
            help="Langage à analyser : java | python | csharp",
        ),
    ] = "java",
    group_id: Annotated[
        str,
        typer.Option("--group-id", help="Partition du graphe Graphiti"),
    ] = "smart_metering",
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Simulation sans écriture dans Neo4j"),
    ] = False,
    out: Annotated[
        Optional[str],
        typer.Option(
            "--out",
            help="Si fourni, extrait en RawDocument JSON dans ce répertoire au lieu "
            "d'ingérer directement — AUCUN appel LLM (flux sans LLM, voir skill kb-reveng). "
            "Incompatible avec l'ingestion directe : --dry-run/ingestion ignorés si --out est fourni.",
        ),
    ] = None,
) -> None:
    """Analyse le code source d'un dépôt et ingère les entités dans le graphe."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s — %(message)s",
    )

    from kb_smart_metering.revengine.ast_extract import ASTExtractor, Language
    from kb_smart_metering.revengine.graph_build import GraphBuilder

    lang_map = {"java": Language.JAVA, "python": Language.PYTHON, "csharp": Language.CSHARP}
    if lang not in lang_map:
        typer.echo(f"[erreur] --lang doit être parmi : {', '.join(sorted(lang_map))}")
        raise typer.Exit(code=1)

    repo_path = Path(repo)
    if not repo_path.is_dir():
        typer.echo(f"[erreur] Le répertoire '{repo}' n'existe pas.")
        raise typer.Exit(code=1)

    typer.echo(f"Analyse du dépôt : {repo_path} (langage={lang})…")
    extractor = ASTExtractor(language=lang_map[lang])
    modules = extractor.extract_dir(repo_path)

    if not modules:
        typer.echo("Aucun fichier source trouvé.")
        raise typer.Exit(code=0)

    builder = GraphBuilder()
    relations = builder.build_relations(modules)
    docs = builder.build_documents(modules)

    typer.echo(
        f"Extrait : {len(modules)} module(s), "
        f"{len(relations)} relation(s) candidate(s), "
        f"{len(docs)} document(s)."
    )

    # Afficher les relations détectées
    for rel in relations:
        typer.echo(
            f"  [{rel.kind}] {rel.source_component} → {rel.target} "
            f"(confiance={rel.confidence:.0%})"
        )

    if out:
        written = _write_raw_documents(docs, Path(out))
        typer.echo(f"\n{len(written)} document(s) extrait(s) dans '{out}/' :")
        for fpath in written:
            typer.echo(f"  {fpath}")
        typer.echo(
            "\nProchaine étape : pour chaque fichier, extraire entités/relations "
            "(voir skill kb-ingest — les relations candidates ci-dessus sont un point "
            "de départ fiable, à transcrire dans le JSON d'extraction) puis lancer :\n"
            "  kb ingest-extraction <fichier_extraction.json>"
        )
        return

    if dry_run:
        typer.echo("[dry-run] Aucune écriture effectuée.")
        return

    asyncio.run(_run_ingestion(docs=docs, group_id=group_id, dry_run=False))


@app.command()
def docgen(
    repo: Annotated[
        str,
        typer.Option("--repo", help="Chemin du dépôt de code source à analyser"),
    ],
    lang: Annotated[
        str,
        typer.Option("--lang", help="Langage : java | python | csharp"),
    ] = "java",
    module: Annotated[
        Optional[str],
        typer.Option("--module", help="Filtre sur le nom du module (ex: ExportService)"),
    ] = None,
    out: Annotated[
        str,
        typer.Option("--out", help="Répertoire de sortie (Markdown, ou JSON si --extract-only)"),
    ] = "docs",
    extract_only: Annotated[
        bool,
        typer.Option(
            "--extract-only",
            help="Extrait le contexte structurel par module en JSON dans --out, "
            "SANS appel LLM — à compléter par l'agent Copilot (voir skill kb-reveng), "
            "puis assembler avec --from-extraction.",
        ),
    ] = False,
    from_extraction: Annotated[
        Optional[str],
        typer.Option(
            "--from-extraction",
            help="Assemble et écrit le Markdown depuis un JSON déjà complété par "
            "l'agent (produit par --extract-only) — AUCUN appel LLM.",
        ),
    ] = None,
) -> None:
    """Génère la documentation Markdown/Obsidian des modules d'un dépôt."""
    import json as _json

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s — %(message)s",
    )

    if from_extraction:
        from kb_smart_metering.revengine.docgen import (
            load_module_doc_from_extraction,
            render_markdown,
        )

        extraction_path = Path(from_extraction)
        if not extraction_path.exists():
            typer.echo(f"[erreur] Fichier introuvable : {extraction_path}")
            raise typer.Exit(code=1)

        try:
            data = _json.loads(extraction_path.read_text(encoding="utf-8"))
            doc = load_module_doc_from_extraction(data)
        except Exception as exc:
            typer.echo(f"[erreur] JSON invalide ou non conforme : {exc}")
            raise typer.Exit(code=1) from exc

        out_dir = Path(out)
        out_dir.mkdir(parents=True, exist_ok=True)
        out_file = out_dir / f"{doc.module_name}.md"
        out_file.write_text(render_markdown(doc), encoding="utf-8")
        typer.echo(f"Documentation écrite : {out_file}")
        return

    from kb_smart_metering.revengine.ast_extract import ASTExtractor, Language

    lang_map = {"java": Language.JAVA, "python": Language.PYTHON, "csharp": Language.CSHARP}
    if lang not in lang_map:
        typer.echo(f"[erreur] --lang doit être parmi : {', '.join(sorted(lang_map))}")
        raise typer.Exit(code=1)

    repo_path = Path(repo)
    if not repo_path.is_dir():
        typer.echo(f"[erreur] Le répertoire '{repo}' n'existe pas.")
        raise typer.Exit(code=1)

    out_dir = Path(out)
    typer.echo(f"Analyse du dépôt : {repo_path} (langage={lang})…")

    extractor = ASTExtractor(language=lang_map[lang])
    modules = extractor.extract_dir(repo_path)

    if not modules:
        typer.echo("Aucun fichier source trouvé.")
        raise typer.Exit(code=0)

    if module:
        matching = [m for m in modules if m.module_name == module]
        if not matching:
            names = ", ".join(m.module_name for m in modules)
            typer.echo(f"[erreur] Module '{module}' introuvable. Disponibles : {names}")
            raise typer.Exit(code=1)
        modules = matching

    if extract_only:
        from kb_smart_metering.revengine.docgen import build_extraction_payload

        out_dir.mkdir(parents=True, exist_ok=True)
        written: list[Path] = []
        for m in modules:
            payload = build_extraction_payload(m)
            fpath = out_dir / f"{m.module_name}.extraction.json"
            fpath.write_text(
                _json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            written.append(fpath)

        typer.echo(f"{len(written)} contexte(s) extrait(s) dans '{out_dir}/' :")
        for fpath in written:
            typer.echo(f"  {fpath}")
        typer.echo(
            "\nProchaine étape : compléter description/composants/flux/regles_metier/"
            "risques dans chaque fichier à partir de sa clé 'contexte' (voir skill "
            "kb-reveng), puis pour chacun :\n"
            "  kb docgen --from-extraction <fichier>.extraction.json --out docs/"
        )
        return

    typer.echo(f"Génération de la doc pour {len(modules)} module(s)…")

    from kb_smart_metering.revengine.docgen import DocGenerator

    generator = DocGenerator()
    generated = generator.generate_dir(modules=modules, out_dir=out_dir)

    typer.echo(f"\n{len(generated)} fichier(s) généré(s) dans '{out_dir}/':")
    for fpath in generated:
        typer.echo(f"  {fpath}")


@app.command()
def ask(
    question: Annotated[str, typer.Argument(help="Question à poser au graphe de connaissances")],
    as_of: Annotated[
        Optional[str],
        typer.Option("--as-of", help="Date de référence ISO (ex: 2023-12-01)"),
    ] = None,
    entity_type: Annotated[
        Optional[str],
        typer.Option("--type", help="Type(s) d'entité à restreindre (ex: Decision,Action)"),
    ] = None,
    output_json: Annotated[
        bool,
        typer.Option("--json/--no-json", help="Sortie en JSON brut"),
    ] = False,
    output_markdown: Annotated[
        bool,
        typer.Option("--markdown/--no-markdown", help="Sortie en Markdown Obsidian (défaut)"),
    ] = True,
) -> None:
    """Pose une question au graphe de connaissances et affiche la réponse structurée."""
    import json as _json
    from datetime import datetime

    logging.basicConfig(
        level=logging.WARNING,
        format="%(asctime)s %(levelname)s %(name)s — %(message)s",
    )

    # Parsing de la date optionnelle
    as_of_date: Optional[datetime] = None
    if as_of:
        try:
            as_of_date = datetime.fromisoformat(as_of)
        except ValueError:
            typer.echo(f"[erreur] --as-of doit être une date ISO valide (ex: 2023-12-01), reçu : {as_of!r}")
            raise typer.Exit(code=1)

    # Parsing des types d'entité optionnels
    entity_types: Optional[list[str]] = None
    if entity_type:
        entity_types = [t.strip() for t in entity_type.split(",") if t.strip()]

    from kb_smart_metering.assistant.chain import AssistantChain

    chain = AssistantChain()
    try:
        reponse = asyncio.run(
            chain.run(question=question, as_of_date=as_of_date, entity_types=entity_types)
        )
    except Exception as exc:
        typer.echo(f"[erreur] {exc}")
        raise typer.Exit(code=1)

    if output_json:
        typer.echo(_json.dumps(reponse.model_dump(), ensure_ascii=False, indent=2))
    else:
        typer.echo(chain.render_markdown(question=question, reponse=reponse))


@app.command()
def search(
    question: Annotated[str, typer.Argument(help="Question à poser au graphe de connaissances")],
    as_of: Annotated[
        Optional[str],
        typer.Option("--as-of", help="Date de référence ISO (ex: 2023-12-01)"),
    ] = None,
    entity_type: Annotated[
        Optional[str],
        typer.Option("--type", help="Type(s) d'entité à restreindre (ex: Decision,Action)"),
    ] = None,
) -> None:
    """
    Retrieval + reranking + contexte assemblé — AUCUN appel LLM.

    Destiné à l'agent Copilot en conversation (voir skill kb-chercheur) :
    lisez le contexte affiché ci-dessous et rédigez vous-même la réponse
    structurée finale (JSON {resume, facts, decisions, actions, risks,
    sources}), en vous limitant STRICTEMENT à ce contexte. Si l'information
    n'y figure pas, dites-le explicitement plutôt que d'inventer.
    """
    from datetime import datetime

    logging.basicConfig(
        level=logging.WARNING,
        format="%(asctime)s %(levelname)s %(name)s — %(message)s",
    )

    as_of_date: Optional[datetime] = None
    if as_of:
        try:
            as_of_date = datetime.fromisoformat(as_of)
        except ValueError:
            typer.echo(f"[erreur] --as-of doit être une date ISO valide (ex: 2023-12-01), reçu : {as_of!r}")
            raise typer.Exit(code=1)

    entity_types: Optional[list[str]] = None
    if entity_type:
        entity_types = [t.strip() for t in entity_type.split(",") if t.strip()]

    from kb_smart_metering.assistant.chain import AssistantChain

    chain = AssistantChain()
    try:
        contexte = asyncio.run(
            chain.build_context(question=question, as_of_date=as_of_date, entity_types=entity_types)
        )
    except Exception as exc:
        typer.echo(f"[erreur] {exc}")
        raise typer.Exit(code=1)

    typer.echo(contexte)


if __name__ == "__main__":
    app()
