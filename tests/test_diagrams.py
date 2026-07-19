"""
Tests de l'extracteur de diagrammes (drawio, PlantUML, Mermaid).

Aucun appel réseau : tout est basé sur des fichiers écrits dans tmp_path.
"""

import base64
import zlib
from pathlib import Path
from urllib.parse import quote

import pytest

from kb_smart_metering.extractors.diagrams import (
    DrawioExtractor,
    MermaidExtractor,
    PlantUMLExtractor,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _compress_drawio_xml(xml: str) -> str:
    """Reproduit la compression drawio : base64(deflate_brut(encodeURIComponent(xml)))."""
    encoded = quote(xml, safe="")
    compressor = zlib.compressobj(9, zlib.DEFLATED, -15)
    compressed = compressor.compress(encoded.encode("utf-8")) + compressor.flush()
    return base64.b64encode(compressed).decode("ascii")


_UNCOMPRESSED_DRAWIO = """<mxfile>
  <diagram name="Architecture">
    <mxGraphModel>
      <root>
        <mxCell id="0" />
        <mxCell id="1" parent="0" />
        <mxCell id="2" value="Compteur" vertex="1" parent="1"><mxGeometry/></mxCell>
        <mxCell id="3" value="Concentrateur" vertex="1" parent="1"><mxGeometry/></mxCell>
        <mxCell id="4" value="publie releve" edge="1" source="2" target="3" parent="1"><mxGeometry/></mxCell>
      </root>
    </mxGraphModel>
  </diagram>
</mxfile>
"""

_INNER_XML_FOR_COMPRESSION = (
    '<mxGraphModel><root>'
    '<mxCell id="0"/><mxCell id="1" parent="0"/>'
    '<mxCell id="2" value="MDM" vertex="1" parent="1"><mxGeometry/></mxCell>'
    '<mxCell id="3" value="Facturation" vertex="1" parent="1"><mxGeometry/></mxCell>'
    '<mxCell id="4" value="envoie donnees" edge="1" source="2" target="3" parent="1"><mxGeometry/></mxCell>'
    '</root></mxGraphModel>'
)


# ---------------------------------------------------------------------------
# DrawioExtractor
# ---------------------------------------------------------------------------


class TestDrawioExtractor:
    def test_xml_non_compresse(self, tmp_path: Path) -> None:
        f = tmp_path / "archi.drawio"
        f.write_text(_UNCOMPRESSED_DRAWIO, encoding="utf-8")

        docs = DrawioExtractor(f).extract()

        assert len(docs) == 1
        assert docs[0].source_type == "diagram"
        assert docs[0].metadonnees["format"] == "drawio"
        assert "Compteur" in docs[0].contenu_texte
        assert "Concentrateur" in docs[0].contenu_texte
        assert "Compteur --publie releve--> Concentrateur" in docs[0].contenu_texte

    def test_xml_compresse_round_trip(self, tmp_path: Path) -> None:
        """Vérifie la décompression drawio (base64 + deflate brut + URL-encodage)."""
        b64 = _compress_drawio_xml(_INNER_XML_FOR_COMPRESSION)
        f = tmp_path / "flux.drawio"
        f.write_text(f'<mxfile><diagram name="Flux MDM">{b64}</diagram></mxfile>', encoding="utf-8")

        docs = DrawioExtractor(f).extract()

        assert len(docs) == 1
        assert "MDM" in docs[0].contenu_texte
        assert "Facturation" in docs[0].contenu_texte
        assert "MDM --envoie donnees--> Facturation" in docs[0].contenu_texte

    def test_plusieurs_pages(self, tmp_path: Path) -> None:
        xml = """<mxfile>
          <diagram name="Page1"><mxGraphModel><root>
            <mxCell id="0"/><mxCell id="1" parent="0"/>
            <mxCell id="2" value="A" vertex="1" parent="1"><mxGeometry/></mxCell>
          </root></mxGraphModel></diagram>
          <diagram name="Page2"><mxGraphModel><root>
            <mxCell id="0"/><mxCell id="1" parent="0"/>
            <mxCell id="2" value="B" vertex="1" parent="1"><mxGeometry/></mxCell>
          </root></mxGraphModel></diagram>
        </mxfile>"""
        f = tmp_path / "multi.drawio"
        f.write_text(xml, encoding="utf-8")

        docs = DrawioExtractor(f).extract()

        assert len(docs) == 2
        titres = {d.titre for d in docs}
        assert any("Page1" in t for t in titres)
        assert any("Page2" in t for t in titres)

    def test_xml_invalide_retourne_liste_vide(self, tmp_path: Path) -> None:
        f = tmp_path / "casse.drawio"
        f.write_text("<mxfile><diagram>pas du xml valide <<<", encoding="utf-8")

        assert DrawioExtractor(f).extract() == []

    def test_fichier_inexistant_retourne_liste_vide(self, tmp_path: Path) -> None:
        assert DrawioExtractor(tmp_path / "absent.drawio").extract() == []

    def test_labels_html_nettoyes(self, tmp_path: Path) -> None:
        xml = """<mxfile><diagram name="P"><mxGraphModel><root>
          <mxCell id="0"/><mxCell id="1" parent="0"/>
          <mxCell id="2" value="&lt;b&gt;Service&lt;/b&gt; Export" vertex="1" parent="1"><mxGeometry/></mxCell>
        </root></mxGraphModel></diagram></mxfile>"""
        f = tmp_path / "html.drawio"
        f.write_text(xml, encoding="utf-8")

        docs = DrawioExtractor(f).extract()

        assert "Service Export" in docs[0].contenu_texte
        assert "<b>" not in docs[0].contenu_texte


# ---------------------------------------------------------------------------
# PlantUMLExtractor
# ---------------------------------------------------------------------------


class TestPlantUMLExtractor:
    def test_lit_le_contenu_tel_quel(self, tmp_path: Path) -> None:
        contenu = "@startuml\nCompteur -> Concentrateur : releve\n@enduml"
        f = tmp_path / "sequence.puml"
        f.write_text(contenu, encoding="utf-8")

        docs = PlantUMLExtractor(f).extract()

        assert len(docs) == 1
        assert docs[0].contenu_texte == contenu
        assert docs[0].source_type == "diagram"
        assert docs[0].metadonnees["format"] == "plantuml"

    def test_fichier_inexistant_retourne_liste_vide(self, tmp_path: Path) -> None:
        assert PlantUMLExtractor(tmp_path / "absent.puml").extract() == []


# ---------------------------------------------------------------------------
# MermaidExtractor
# ---------------------------------------------------------------------------


class TestMermaidExtractor:
    def test_lit_le_contenu_tel_quel(self, tmp_path: Path) -> None:
        contenu = "flowchart LR\n  Compteur --> Concentrateur --> MDM"
        f = tmp_path / "flux.mmd"
        f.write_text(contenu, encoding="utf-8")

        docs = MermaidExtractor(f).extract()

        assert len(docs) == 1
        assert docs[0].contenu_texte == contenu
        assert docs[0].source_type == "diagram"
        assert docs[0].metadonnees["format"] == "mermaid"

    def test_fichier_inexistant_retourne_liste_vide(self, tmp_path: Path) -> None:
        assert MermaidExtractor(tmp_path / "absent.mmd").extract() == []


@pytest.mark.parametrize(
    "extractor_cls,suffix,contenu",
    [
        (PlantUMLExtractor, ".puml", "@startuml\nA -> B\n@enduml"),
        (MermaidExtractor, ".mmd", "flowchart LR\n  A --> B"),
    ],
)
def test_id_source_normalise_sans_backslash(
    tmp_path: Path, extractor_cls: type, suffix: str, contenu: str
) -> None:
    """id_source doit toujours utiliser des slashes POSIX (cf. episode_key Windows)."""
    f = tmp_path / f"diagramme{suffix}"
    f.write_text(contenu, encoding="utf-8")

    docs = extractor_cls(f).extract()

    assert "\\" not in docs[0].id_source
