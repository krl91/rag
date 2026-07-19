# Portage Windows — Problème 2 : Podman rootless et conteneurisation

## Contexte du projet

`kb-smart-metering` utilise Neo4j 5.x (avec le plugin APOC) comme base de
données graphe. Neo4j est démarré via un fichier `compose.yml` avec Podman.
La contrainte du projet est : **Podman exclusivement, jamais Docker**.

---

## Principe directeur

**Privilégier systématiquement ce qui est déjà disponible** sur la machine
cible avant de recommander l'installation d'outils supplémentaires :
- Si Podman Desktop est déjà installé, s'appuyer dessus sans demander d'autre
  outil de conteneurisation.
- Si WSL2 est déjà activé sur le système, l'exploiter plutôt que d'installer
  une couche supplémentaire.
- Si aucune solution conteneur n'est disponible, évaluer l'installation directe
  de Neo4j (sans conteneur) comme alternative viable.
- Proposer les solutions du moins intrusif au plus intrusif.

---

## Description du problème

Podman rootless, tel qu'il est utilisé sur macOS et Linux, **n'existe pas sous
Windows natif**. Les options disponibles sous Windows sont :

| Option | Disponibilité | Contrainte |
|--------|--------------|------------|
| Podman Desktop pour Windows | Oui | Nécessite WSL2 ou une VM HyperV |
| Docker Desktop | Oui | Interdit par la contrainte projet |
| WSL2 + Podman dans WSL | Oui | Transparence partielle depuis Windows |
| `podman machine` (comme sur macOS) | Partiel | Support expérimental |

La commande `podman compose up -d` du Makefile ne fonctionnera pas si Podman
n'est pas correctement installé et démarré.

### Fichier `compose.yml` actuel

```yaml
services:
  neo4j:
    image: docker.io/library/neo4j:5
    container_name: kb_neo4j
    restart: unless-stopped
    environment:
      NEO4J_AUTH: "${NEO4J_USER:-neo4j}/${NEO4J_PASSWORD:-changeme}"
      NEO4J_PLUGINS: '["apoc"]'
      NEO4J_dbms_security_procedures_unrestricted: "apoc.*"
      NEO4J_dbms_security_procedures_allowlist: "apoc.*"
      NEO4J_server_memory_heap_initial__size: "512m"
      NEO4J_server_memory_heap_max__size: "1G"
    ports:
      - "7474:7474"
      - "7687:7687"
    volumes:
      - neo4j_data:/data
      - neo4j_logs:/logs
      - neo4j_plugins:/plugins
    healthcheck:
      test: ["CMD", "neo4j", "status"]
      interval: 30s
      timeout: 10s
      retries: 5
      start_period: 60s

volumes:
  neo4j_data:
    driver: local
  neo4j_logs:
    driver: local
  neo4j_plugins:
    driver: local
```

---

## Ce que tu dois analyser

### Option A — Podman Desktop pour Windows (recommandée si disponible)

1. Documenter la procédure d'installation complète de Podman Desktop sur
   Windows 10/11 (via winget, Chocolatey, ou installeur direct).
2. Vérifier si `podman compose` est disponible dans Podman Desktop sous Windows
   et quelle version est nécessaire.
3. Déterminer si `podman machine init` / `podman machine start` sont nécessaires
   sur Windows comme sur macOS, ou si Podman Desktop les gère automatiquement.
4. Identifier les prérequis système (WSL2, Hyper-V, virtualisation activée dans
   le BIOS).

### Option B — Neo4j standalone sans conteneur

Si Podman n'est pas disponible, Neo4j peut être installé directement :

1. Évaluer l'installation de **Neo4j Desktop** (interface graphique) ou de
   **Neo4j Community Server** (service Windows) en remplacement du conteneur.
2. Le plugin APOC doit être installé manuellement : quelle est la procédure
   exacte sous Windows ?
3. Les variables d'environnement `NEO4J_AUTH`, `NEO4J_PLUGINS`, etc. du
   `compose.yml` doivent être traduites en configuration `neo4j.conf` : fournir
   le mapping complet.

### Option C — `podman machine` en mode WSL2

1. Décrire la configuration `podman machine init --provider wsl` sur Windows.
2. Cette option conserve la commande `podman compose` inchangée : confirmer
   la compatibilité complète avec le `compose.yml` existant.

### Comparatif et recommandation

- Classer les options A, B, C par simplicité d'installation et de maintenance.
- La solution retenue doit permettre à un développeur Windows sans droits
  d'administrateur d'utiliser Neo4j (si possible).
- Documenter les ports exposés (7474, 7687) et la vérification de connectivité
  depuis Python (`neo4j` driver, `bolt://localhost:7687`).

---

## Contraintes du projet

- Podman **préféré** mais tolérance si Podman Desktop nécessite une exception.
- Le `compose.yml` ne doit pas être modifié pour la version Linux/macOS.
- `CONTAINER_ENGINE` est une variable surchargeable dans le Makefile (voir
  Problème 1) : `CONTAINER_ENGINE=docker make up` doit rester possible comme
  ultime recours documenté.
- Neo4j version 5.x avec plugin APOC est obligatoire (utilisé par graphiti-core).

---

## Livrable attendu

- Procédure d'installation pas à pas pour Windows (avec les commandes exactes).
- Un `compose.override.yml` si des ajustements sont nécessaires pour Windows.
- Section à ajouter dans le `README.md` : "Installation sous Windows".
- Script de vérification PowerShell qui teste la connectivité Neo4j sur les ports
  7474 et 7687.
