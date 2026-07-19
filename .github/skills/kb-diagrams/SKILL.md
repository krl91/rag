---
name: kb-diagrams
description: "Lire et écrire des diagrammes (drawio/diagrams.net, PlantUML, Mermaid) dans kb-smart-metering. Utiliser pour : ingérer un diagramme d'architecture existant comme source de connaissance, générer un diagramme Mermaid à partir du code analysé (kb reveng/kb docgen), créer ou éditer un diagramme drawio/PlantUML plus élaboré via les serveurs MCP optionnels."
argument-hint: "Action (lire|générer|créer) + chemin ou description du diagramme"
---

# Skill — Diagrammes (lecture, génération, édition)

## Trois cas d'usage distincts

| Besoin | Comment | Appel LLM ? |
|---|---|---|
| **Lire** un diagramme existant (.drawio, .puml, .mmd) comme source de connaissance | `kb extract --source file --path diagramme.drawio` | Non — extraction texte pure, puis flux `kb-ingest` habituel |
| **Générer** un diagramme à partir du code analysé (revengine) | `kb reveng --diagram-out` / intégré à `kb docgen` | Non — déterministe depuis l'AST |
| **Créer/éditer** un diagramme drawio ou PlantUML élaboré (formes AWS/Azure, mise en page précise) | Serveurs MCP optionnels (`drawio`, `plantuml`) | Non (les MCP ne sont pas des LLM) — mais nécessite de démarrer un serveur MCP local |

---

## 1 — Lire un diagramme comme source de connaissance

`kb extract --source file` reconnaît automatiquement (voir
`src/kb_smart_metering/extractors/diagrams.py`) :

- **`.drawio`, `.drawio.xml`** : parse le XML `mxGraphModel` (compressé ou
  non — la décompression drawio standard est gérée automatiquement),
  produit une liste d'éléments et de connexions par page.
- **`.puml`, `.plantuml`** : lu tel quel (déjà un texte structuré).
- **`.mmd`, `.mermaid`** : lu tel quel (déjà un texte structuré).

```bash
kb extract --source file --path architecture.drawio --out data/raw/
kb extract --source file --path sequence_export.puml --out data/raw/
kb extract --source file --path flux_donnees.mmd --out data/raw/
```

Ensuite, flux identique à toute autre source (voir skill `kb-ingest`) :
tu lis le RawDocument produit, extrais les entités/relations qu'il décrit,
puis `kb ingest-extraction`. Un diagramme d'architecture devient ainsi une
source de connaissance au même titre qu'un ticket Jira ou une page
Confluence — utile notamment pour ingérer des schémas déjà réalisés par
l'équipe avant que le code ou la documentation n'existent.

---

## 2 — Générer un diagramme depuis le code (revengine)

Entièrement déterministe (aucun LLM) — voir
`src/kb_smart_metering/revengine/diagram_export.py`.

**Diagramme système** (toutes les relations `publie`/`consomme`/`appelle`
d'un dépôt) :

```bash
kb reveng --repo /repos/compteur-service --lang java --diagram-out docs/architecture.mmd
```

Compatible avec toutes les autres options de `kb reveng` (`--out`,
`--dry-run`, ingestion directe si Ollama disponible).

**Diagramme par module** : `kb docgen` (avec ou sans `--extract-only`,
voir skill `kb-reveng`) inclut automatiquement une section "## Diagramme"
dans chaque documentation générée, avec le flowchart Mermaid du module
(classes, événements publiés/consommés, appels sortants).

Les fichiers `.mmd`/le contenu Mermaid dans le Markdown généré s'affichent
nativement dans GitHub, Obsidian et l'aperçu Markdown de VS Code — rien à
installer pour les visualiser.

---

## 3 — Créer/éditer un diagramme drawio ou PlantUML élaboré

Pour des besoins dépassant un simple flowchart Mermaid (formes AWS/Azure/
GCP/Kubernetes/BPMN, mise en page précise dans l'éditeur drawio, diagrammes
UML détaillés type séquence/classes en PlantUML) : deux serveurs MCP
optionnels sont préconfigurés dans `.vscode/mcp.json.example`.

### Activer les serveurs MCP (une fois)

```bash
cp .vscode/mcp.json.example .vscode/mcp.json
```

Puis dans VS Code : palette de commandes → "MCP: List Servers" → démarrer
`drawio` et/ou `plantuml`. Prérequis : Node.js (comme pour l'extension
`copilot-bridge/` optionnelle — voir skill `kb-copilot-bridge`).

- **`drawio`** ([@drawio/mcp](https://www.npmjs.com/package/@drawio/mcp),
  officiel diagrams.net) : recherche parmi 10 000+ formes, crée/modifie des
  fichiers `.drawio`, convertit du CSV ou du Mermaid en diagramme drawio.
- **`plantuml`** ([plantuml-mcp-server](https://github.com/infobip/plantuml-mcp-server)) :
  génère et corrige du PlantUML, retourne des URLs SVG/PNG.
  > **Confidentialité** : par défaut, le rendu passe par le serveur public
  > `plantuml.com` — le contenu du diagramme y est envoyé. Pour des
  > schémas sensibles, changer `PLANTUML_SERVER_URL` dans
  > `.vscode/mcp.json` vers un serveur PlantUML interne, ou se limiter à
  > générer le texte `.puml` sans passer par le rendu distant.

### Mermaid : pas de serveur nécessaire

Mermaid ne nécessite aucun MCP : c'est du texte simple, déjà géré nativement
par ce projet (§2 ci-dessus) et rendu directement par GitHub/Obsidian/VS
Code. N'active un serveur MCP Mermaid que si tu as besoin d'un aperçu live
avec rechargement automatique pendant l'édition manuelle d'un `.mmd`.

---

## Résumé des formats supportés

| Format | Lire (source) | Écrire (déterministe) | Écrire (élaboré, via MCP) |
|---|---|---|---|
| drawio | ✅ `kb extract --source file` | — | ✅ serveur `drawio` |
| PlantUML | ✅ `kb extract --source file` | — | ✅ serveur `plantuml` |
| Mermaid | ✅ `kb extract --source file` | ✅ `kb reveng`/`kb docgen` | non nécessaire |
