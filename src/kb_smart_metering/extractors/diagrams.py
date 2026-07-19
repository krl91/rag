"""
Extracteur de diagrammes — drawio (diagrams.net), PlantUML, Mermaid.

- drawio (.drawio, .drawio.xml) : parse le XML mxGraphModel (compressé ou
  non — drawio compresse par défaut : base64 + deflate brut + URL-encodage)
  et produit une description textuelle des éléments et connexions.
- PlantUML (.puml, .plantuml) : le fichier est déjà une description
  textuelle (langage PlantUML) — lu tel quel.
- Mermaid (.mmd, .mermaid) : idem, syntaxe Mermaid déjà textuelle.

Dans les trois cas, le texte produit est une source comme une autre pour
`kb extract` : l'agent en fait ensuite l'extraction d'entités/relations en
conversation (voir skill kb-diagrams), exactement comme pour Word/PDF/Excel.
"""

import base64
import logging
import re
import zlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Union
from urllib.parse import unquote
from xml.etree import ElementTree as ET

from kb_smart_metering.normalize.models import RawDocument, normalize_file_source_id

logger = logging.getLogger(__name__)


class DrawioExtractor:
    """Extracteur de diagrammes drawio/diagrams.net (.drawio, .drawio.xml)."""

    def __init__(self, file_path: Union[str, Path]) -> None:
        self._file_path = Path(file_path)

    def extract(self) -> list[RawDocument]:
        """Extrait chaque page du diagramme en un RawDocument (nœuds + connexions)."""
        try:
            raw = self._file_path.read_text(encoding="utf-8")
        except OSError as exc:
            logger.error("Impossible de lire %s : %s", self._file_path, exc)
            return []

        try:
            root = ET.fromstring(raw)
        except ET.ParseError as exc:
            logger.error("XML drawio invalide dans %s : %s", self._file_path, exc)
            return []

        if root.tag == "mxGraphModel":
            diagram_elements: list[ET.Element] = [root]
        elif root.tag == "diagram":
            diagram_elements = [root]
        else:
            diagram_elements = root.findall(".//diagram")

        documents: list[RawDocument] = []
        stat = self._file_path.stat()
        mtime = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)

        for idx, diagram_el in enumerate(diagram_elements):
            page_name = diagram_el.get("name") or f"page{idx + 1}"
            graph_model = self._resolve_graph_model(diagram_el)
            if graph_model is None:
                logger.warning(
                    "Page '%s' ignorée dans %s : contenu illisible (ni XML direct, "
                    "ni compression drawio reconnue)",
                    page_name,
                    self._file_path,
                )
                continue

            contenu = self._graph_model_to_text(graph_model, page_name)
            if not contenu.strip():
                continue

            documents.append(
                RawDocument(
                    id_source=f"{normalize_file_source_id(self._file_path)}#{page_name}",
                    source_type="diagram",
                    titre=f"{self._file_path.stem} — {page_name}",
                    contenu_texte=contenu,
                    date_modification=mtime,
                    url_ou_chemin=self._file_path.resolve().as_uri(),
                    metadonnees={
                        "format": "drawio",
                        "page": page_name,
                        "taille_octets": stat.st_size,
                    },
                )
            )

        logger.info(
            "drawio : %d page(s) extraite(s) — %s", len(documents), self._file_path.name
        )
        return documents

    @staticmethod
    def _resolve_graph_model(diagram_el: ET.Element) -> Optional[ET.Element]:
        """
        Retourne l'élément <mxGraphModel>, en le décompressant si nécessaire.

        drawio compresse par défaut le contenu de <diagram> : le texte est
        base64(deflate_brut(encodeURIComponent(xml))). On tente d'abord le
        cas non compressé (XML direct en enfant), puis la décompression.
        """
        if diagram_el.tag == "mxGraphModel":
            return diagram_el

        direct = diagram_el.find("mxGraphModel")
        if direct is not None:
            return direct

        text = (diagram_el.text or "").strip()
        if not text:
            return None

        try:
            compressed = base64.b64decode(text)
            xml_bytes = zlib.decompress(compressed, -zlib.MAX_WBITS)
            xml_text = unquote(xml_bytes.decode("utf-8"))
            return ET.fromstring(xml_text)
        except Exception as exc:
            logger.debug("Décompression drawio échouée pour une page : %s", exc)
            return None

    @staticmethod
    def _graph_model_to_text(graph_model: ET.Element, page_name: str) -> str:
        """Convertit un mxGraphModel en description texte (éléments + connexions)."""
        cells = {cell.get("id"): cell for cell in graph_model.iter("mxCell")}
        # Les formes drawio "avec données métier" encapsulent parfois la
        # mxCell dans un <object label="..."> — le label prime alors.
        for obj in graph_model.iter("object"):
            inner = obj.find("mxCell")
            if inner is not None and inner.get("id"):
                if obj.get("label") or obj.get("value"):
                    inner.set("value", obj.get("label") or obj.get("value") or "")
                cells[inner.get("id")] = inner

        def label(cell_id: Optional[str]) -> str:
            cell = cells.get(cell_id) if cell_id else None
            if cell is None:
                return cell_id or "?"
            value = cell.get("value") or ""
            clean = re.sub(r"<[^>]+>", " ", value)
            clean = re.sub(r"\s+", " ", clean).strip()
            return clean or (cell.get("id") or "?")

        nodes: list[str] = []
        edges: list[str] = []
        for cell in cells.values():
            if cell.get("vertex") == "1":
                text = label(cell.get("id"))
                if text:
                    nodes.append(text)
            elif cell.get("edge") == "1":
                src = label(cell.get("source"))
                tgt = label(cell.get("target"))
                if not cell.get("source") or not cell.get("target"):
                    continue
                rel_label = label(cell.get("id")) if cell.get("value") else ""
                if rel_label and rel_label not in (src, tgt):
                    edges.append(f"{src} --{rel_label}--> {tgt}")
                else:
                    edges.append(f"{src} --> {tgt}")

        lines = [f"# Diagramme drawio : {page_name}", ""]
        if nodes:
            lines.append("## Éléments")
            lines.extend(f"- {n}" for n in dict.fromkeys(nodes))
            lines.append("")
        if edges:
            lines.append("## Connexions")
            lines.extend(f"- {e}" for e in dict.fromkeys(edges))
        return "\n".join(lines)


class PlantUMLExtractor:
    """Extracteur de diagrammes PlantUML (.puml, .plantuml) — texte déjà lisible."""

    def __init__(self, file_path: Union[str, Path]) -> None:
        self._file_path = Path(file_path)

    def extract(self) -> list[RawDocument]:
        contenu = self._read_text()
        if contenu is None:
            return []

        stat = self._file_path.stat()
        logger.info("PlantUML : 1 diagramme extrait — %s", self._file_path.name)
        return [
            RawDocument(
                id_source=normalize_file_source_id(self._file_path),
                source_type="diagram",
                titre=self._file_path.stem,
                contenu_texte=contenu,
                date_modification=datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc),
                url_ou_chemin=self._file_path.resolve().as_uri(),
                metadonnees={"format": "plantuml", "taille_octets": stat.st_size},
            )
        ]

    def _read_text(self) -> Optional[str]:
        try:
            return self._file_path.read_text(encoding="utf-8")
        except OSError as exc:
            logger.error("Impossible de lire %s : %s", self._file_path, exc)
            return None


class MermaidExtractor:
    """Extracteur de diagrammes Mermaid (.mmd, .mermaid) — texte déjà lisible."""

    def __init__(self, file_path: Union[str, Path]) -> None:
        self._file_path = Path(file_path)

    def extract(self) -> list[RawDocument]:
        contenu = self._read_text()
        if contenu is None:
            return []

        stat = self._file_path.stat()
        logger.info("Mermaid : 1 diagramme extrait — %s", self._file_path.name)
        return [
            RawDocument(
                id_source=normalize_file_source_id(self._file_path),
                source_type="diagram",
                titre=self._file_path.stem,
                contenu_texte=contenu,
                date_modification=datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc),
                url_ou_chemin=self._file_path.resolve().as_uri(),
                metadonnees={"format": "mermaid", "taille_octets": stat.st_size},
            )
        ]

    def _read_text(self) -> Optional[str]:
        try:
            return self._file_path.read_text(encoding="utf-8")
        except OSError as exc:
            logger.error("Impossible de lire %s : %s", self._file_path, exc)
            return None
