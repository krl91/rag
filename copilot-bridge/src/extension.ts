/**
 * KB Copilot Bridge
 *
 * Expose les modèles de GitHub Copilot Chat (via l'API publique `vscode.lm`,
 * pas de reverse-engineering d'endpoint privé) sous forme d'un serveur HTTP
 * local OpenAI-compatible (`POST /v1/chat/completions`).
 *
 * Sert de remplacement à Ollama pour kb-smart-metering sur une machine
 * Windows où Ollama ne peut pas être installé : le pipeline Python pointe
 * simplement OLLAMA_BASE_URL sur ce serveur local au lieu d'un vrai Ollama.
 *
 * Contrainte à connaître : ce pont ne fonctionne que si VS Code est ouvert
 * et cette extension démarrée. Contrairement à Ollama, il n'y a pas de
 * service headless — pas d'ingestion planifiée sans session VS Code active.
 */
import * as http from "node:http";
import type { AddressInfo } from "node:net";
import * as vscode from "vscode";

let server: http.Server | undefined;
let statusBarItem: vscode.StatusBarItem;
let outputChannel: vscode.OutputChannel;

interface OpenAIChatMessage {
  role: "system" | "user" | "assistant";
  content: string;
}

interface OpenAIChatRequest {
  model?: string;
  messages: OpenAIChatMessage[];
  temperature?: number;
  // Accepté mais ignoré : vscode.lm n'a pas de mode JSON forcé natif.
  // Le prompt système du projet demande déjà explicitement du JSON,
  // et le client Python (kb_smart_metering) sait extraire un JSON
  // entouré de texte parasite ou de balises ```json.
  response_format?: unknown;
}

export function activate(context: vscode.ExtensionContext): void {
  outputChannel = vscode.window.createOutputChannel("KB Copilot Bridge");
  statusBarItem = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Right, 100);
  statusBarItem.command = "kbCopilotBridge.stop";
  setStatusBar(false);
  statusBarItem.show();

  context.subscriptions.push(
    outputChannel,
    statusBarItem,
    vscode.commands.registerCommand("kbCopilotBridge.start", () => startServer()),
    vscode.commands.registerCommand("kbCopilotBridge.stop", () => stopServer()),
  );
}

export function deactivate(): void {
  stopServer();
}

function setStatusBar(running: boolean, port?: number): void {
  if (running) {
    statusBarItem.text = `$(radio-tower) KB Bridge :${port}`;
    statusBarItem.tooltip = "Pont Copilot actif — cliquer pour arrêter";
    statusBarItem.command = "kbCopilotBridge.stop";
  } else {
    statusBarItem.text = "$(circle-slash) KB Bridge arrêté";
    statusBarItem.tooltip = "Cliquer pour démarrer le pont Copilot";
    statusBarItem.command = "kbCopilotBridge.start";
  }
}

async function startServer(): Promise<void> {
  if (server) {
    vscode.window.showInformationMessage("KB Bridge est déjà démarré.");
    return;
  }

  const config = vscode.workspace.getConfiguration("kbCopilotBridge");
  const port = config.get<number>("port", 4141);
  const defaultFamily = config.get<string>("modelFamily", "gpt-4o");

  // Appel initié explicitement par l'utilisateur (commande palette) —
  // conforme à la recommandation Microsoft d'appeler selectChatModels
  // suite à une action utilisateur, pas au démarrage silencieux de VS Code.
  const probe = await vscode.lm.selectChatModels({ vendor: "copilot", family: defaultFamily });
  if (probe.length === 0) {
    vscode.window.showErrorMessage(
      `Aucun modèle Copilot "${defaultFamily}" disponible. ` +
        "Vérifiez votre abonnement GitHub Copilot et que l'accès au modèle est autorisé.",
    );
    return;
  }

  server = http.createServer((req, res) => void handleRequest(req, res, defaultFamily));

  server.on("error", (err) => {
    outputChannel.appendLine(`Erreur serveur : ${err.message}`);
    vscode.window.showErrorMessage(`KB Bridge : erreur serveur — ${err.message}`);
    server = undefined;
    setStatusBar(false);
  });

  // 127.0.0.1 explicitement — jamais 0.0.0.0. Ce pont donne accès à Copilot
  // sur simple requête HTTP sans authentification : il ne doit être atteignable
  // que depuis la machine locale, jamais exposé sur le réseau.
  server.listen(port, "127.0.0.1", () => {
    const addr = server?.address() as AddressInfo;
    outputChannel.appendLine(`KB Bridge démarré sur http://127.0.0.1:${addr.port}`);
    outputChannel.appendLine(`Modèle par défaut : ${defaultFamily}`);
    setStatusBar(true, addr.port);
    vscode.window.showInformationMessage(`KB Bridge écoute sur http://127.0.0.1:${addr.port}`);
  });
}

function stopServer(): void {
  if (!server) {
    return;
  }
  server.close();
  server = undefined;
  setStatusBar(false);
  outputChannel.appendLine("KB Bridge arrêté.");
}

async function handleRequest(
  req: http.IncomingMessage,
  res: http.ServerResponse,
  defaultFamily: string,
): Promise<void> {
  try {
    if (req.method === "GET" && req.url === "/health") {
      sendJson(res, 200, { status: "ok" });
      return;
    }

    if (req.method === "GET" && req.url === "/v1/models") {
      const models = await vscode.lm.selectChatModels({ vendor: "copilot" });
      sendJson(res, 200, {
        object: "list",
        data: models.map((m) => ({ id: m.family, object: "model", owned_by: "github-copilot" })),
      });
      return;
    }

    if (req.method === "POST" && req.url === "/v1/chat/completions") {
      const body = await readJsonBody<OpenAIChatRequest>(req);
      const content = await runChatCompletion(body, defaultFamily);
      sendJson(res, 200, {
        id: `kbbridge-${Date.now()}`,
        object: "chat.completion",
        created: Math.floor(Date.now() / 1000),
        model: body.model || defaultFamily,
        choices: [
          {
            index: 0,
            message: { role: "assistant", content },
            finish_reason: "stop",
          },
        ],
      });
      return;
    }

    sendJson(res, 404, { error: { message: `Route inconnue : ${req.method} ${req.url}` } });
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err);
    outputChannel.appendLine(`Erreur requête : ${message}`);
    sendJson(res, 502, { error: { message } });
  }
}

async function runChatCompletion(body: OpenAIChatRequest, defaultFamily: string): Promise<string> {
  if (!body.messages || body.messages.length === 0) {
    throw new Error("Requête invalide : champ 'messages' manquant ou vide.");
  }

  const family = body.model || defaultFamily;
  const models = await vscode.lm.selectChatModels({ vendor: "copilot", family });
  if (models.length === 0) {
    throw new Error(`Aucun modèle Copilot "${family}" disponible.`);
  }
  const model = models[0];

  // L'API vscode.lm stable ne propose pas de rôle "system" dédié pour tous
  // les fournisseurs : le contenu système est préfixé au premier message
  // utilisateur, technique standard pour ce cas.
  const systemParts = body.messages.filter((m) => m.role === "system").map((m) => m.content);
  const conversational = body.messages.filter((m) => m.role !== "system");

  const lmMessages: vscode.LanguageModelChatMessage[] = conversational.map((m, i) => {
    const text = i === 0 && systemParts.length > 0 ? `${systemParts.join("\n\n")}\n\n${m.content}` : m.content;
    return m.role === "assistant"
      ? vscode.LanguageModelChatMessage.Assistant(text)
      : vscode.LanguageModelChatMessage.User(text);
  });

  const cts = new vscode.CancellationTokenSource();
  const timeout = setTimeout(() => cts.cancel(), 120_000);
  try {
    const response = await model.sendRequest(lmMessages, {}, cts.token);
    let full = "";
    for await (const fragment of response.text) {
      full += fragment;
    }
    return full;
  } finally {
    clearTimeout(timeout);
    cts.dispose();
  }
}

function readJsonBody<T>(req: http.IncomingMessage): Promise<T> {
  return new Promise((resolve, reject) => {
    let raw = "";
    req.on("data", (chunk) => (raw += chunk));
    req.on("end", () => {
      try {
        resolve(JSON.parse(raw) as T);
      } catch {
        reject(new Error("Corps de requête JSON invalide."));
      }
    });
    req.on("error", reject);
  });
}

function sendJson(res: http.ServerResponse, status: number, payload: unknown): void {
  const data = JSON.stringify(payload);
  res.writeHead(status, { "Content-Type": "application/json; charset=utf-8" });
  res.end(data);
}
