# KB Copilot Bridge

Extension VS Code qui expose GitHub Copilot Chat comme un serveur HTTP local
compatible OpenAI (`POST /v1/chat/completions`), pour remplacer Ollama sur
une machine où il ne peut pas être installé.

Utilise uniquement l'API publique `vscode.lm` (aucun endpoint privé
Copilot, aucune rétro-ingénierie) — la même API que celle documentée par
Microsoft pour construire des extensions IA dans VS Code.

## Limite à connaître

Ce pont **n'est pas un service headless**. Il ne fonctionne que si :

- VS Code est ouvert,
- cette extension est activée,
- la commande **"KB Bridge: Démarrer le pont Copilot"** a été lancée.

Contrairement à Ollama, il n'y a pas d'ingestion planifiée (cron) possible
sans session VS Code active. Les appels en masse (ingestion Phase 2)
consomment le quota Copilot de l'utilisateur comme n'importe quel usage du
chat — à garder en tête pour dimensionner la fréquence d'ingestion.

## Installation (développement)

Prérequis : [Node.js](https://nodejs.org/) 20+.

```powershell
cd copilot-bridge
npm install
npm run compile
```

Puis ouvrir ce dossier dans VS Code et appuyer sur **F5** — une nouvelle
fenêtre "Extension Development Host" s'ouvre avec l'extension chargée.

## Installation (utilisation quotidienne, sans F5)

Empaqueter en `.vsix` et l'installer une fois pour toutes :

```powershell
cd copilot-bridge
npm install
npx vsce package
code --install-extension kb-copilot-bridge-0.1.0.vsix
```

## Utilisation

1. Palette de commandes (`Ctrl+Shift+P`) → **"KB Bridge: Démarrer le pont
   Copilot"**.
2. La barre de statut affiche `KB Bridge :4141` une fois démarré.
3. Configurer `kb-smart-metering` pour pointer dessus (voir
   `.github/skills/kb-copilot-bridge/SKILL.md` à la racine du dépôt) :

   ```dotenv
   OLLAMA_BASE_URL=http://127.0.0.1:4141/v1
   OLLAMA_MODEL=gpt-4o
   LLM_API_KEY=
   ```

4. Vérifier : `curl http://127.0.0.1:4141/health`

## Configuration

| Paramètre                        | Défaut    | Description                              |
|-----------------------------------|-----------|-------------------------------------------|
| `kbCopilotBridge.port`            | `4141`    | Port d'écoute local (127.0.0.1 uniquement) |
| `kbCopilotBridge.modelFamily`     | `gpt-4o`  | Modèle Copilot par défaut                  |

## Sécurité

Le serveur écoute exclusivement sur `127.0.0.1` — jamais sur `0.0.0.0`.
Il n'y a pas d'authentification par token : n'importe quel processus sur la
machine locale peut l'appeler. Ne jamais modifier `extension.ts` pour
écouter sur une interface réseau autre que loopback.
