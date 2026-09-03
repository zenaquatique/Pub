// AquaRappel — Supabase Edge Function "chat"
//
// Pont entre l'appli et l'API Gemini (Google AI, gratuite). Reçoit un message
// utilisateur + le contexte des tâches, appelle Gemini avec des "function calls"
// pour ajouter/cocher/décocher/supprimer des tâches, exécute ces actions dans
// Supabase (avec le jeton de l'utilisateur, donc soumis aux règles RLS), et
// renvoie une réponse en français.
//
// Déploiement : voir docs/README.md ("Mise en place").
// Secret requis : GEMINI_API_KEY (Dashboard Supabase > Edge Functions > chat > Secrets,
// ou `supabase secrets set GEMINI_API_KEY=...`).

import { createClient, type SupabaseClient } from "https://esm.sh/@supabase/supabase-js@2";

const GEMINI_API_KEY = Deno.env.get("GEMINI_API_KEY") ?? "";
const GEMINI_MODEL = Deno.env.get("GEMINI_MODEL") ?? "gemini-flash-latest";
const SUPABASE_URL = Deno.env.get("SUPABASE_URL") ?? "";
const SUPABASE_ANON_KEY = Deno.env.get("SUPABASE_ANON_KEY") ?? "";

const CORS_HEADERS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
};

type Task = { id: string; text: string; done: boolean };
type HistoryTurn = { role: "user" | "assistant"; text: string };

const FUNCTION_DECLARATIONS = [
  {
    name: "add_task",
    description: "Ajoute une nouvelle tâche à la liste de l'utilisateur.",
    parameters: {
      type: "object",
      properties: { text: { type: "string", description: "Le texte de la tâche à ajouter." } },
      required: ["text"],
    },
  },
  {
    name: "complete_task",
    description: "Marque une tâche existante comme faite (cochée).",
    parameters: {
      type: "object",
      properties: { task_id: { type: "string", description: "L'identifiant (id) de la tâche à cocher." } },
      required: ["task_id"],
    },
  },
  {
    name: "uncomplete_task",
    description: "Décoche une tâche déjà marquée comme faite.",
    parameters: {
      type: "object",
      properties: { task_id: { type: "string" } },
      required: ["task_id"],
    },
  },
  {
    name: "delete_task",
    description: "Supprime définitivement une tâche de la liste.",
    parameters: {
      type: "object",
      properties: { task_id: { type: "string" } },
      required: ["task_id"],
    },
  },
];

function buildSystemPrompt(tasks: Task[]): string {
  const pending = tasks.filter((t) => !t.done);
  const done = tasks.filter((t) => t.done);
  const fmt = (arr: Task[]) => (arr.length ? arr.map((t) => `- [${t.id}] ${t.text}`).join("\n") : "(aucune)");

  return `Tu es AquaRappel, un assistant personnel francophone, chaleureux et direct, qui aide l'utilisateur à gérer sa liste de tâches. Tutoie-le toujours.

Voici l'état actuel de sa liste (identifiant entre crochets) :

Tâches à faire :
${fmt(pending)}

Tâches déjà faites :
${fmt(done)}

Quand l'utilisateur te demande d'ajouter, cocher, décocher ou supprimer une tâche, utilise obligatoirement les fonctions disponibles (add_task, complete_task, uncomplete_task, delete_task) avec le bon task_id tiré de la liste ci-dessus — ne devine jamais un id. Après avoir utilisé une fonction, confirme brièvement ce que tu as fait. Réponds toujours en français, de façon naturelle et concise (1 à 3 phrases), jamais sous forme de liste à puces ni de markdown.`;
}

Deno.serve(async (req: Request) => {
  if (req.method === "OPTIONS") return new Response(null, { headers: CORS_HEADERS });

  if (!GEMINI_API_KEY) {
    return jsonResponse({ error: "GEMINI_API_KEY non configurée côté serveur." }, 500);
  }

  try {
    const authHeader = req.headers.get("Authorization");
    if (!authHeader) return jsonResponse({ error: "Non authentifié." }, 401);

    const body = await req.json();
    const message: string = body?.message;
    const tasks: Task[] = Array.isArray(body?.tasks) ? body.tasks : [];
    const history: HistoryTurn[] = Array.isArray(body?.history) ? body.history : [];

    if (!message || typeof message !== "string") {
      return jsonResponse({ error: "Message manquant." }, 400);
    }

    const supabase = createClient(SUPABASE_URL, SUPABASE_ANON_KEY, {
      global: { headers: { Authorization: authHeader } },
    });

    const { data: userData, error: userErr } = await supabase.auth.getUser();
    if (userErr || !userData?.user) return jsonResponse({ error: "Session invalide." }, 401);
    const userId = userData.user.id;

    const contents: Array<{ role: string; parts: unknown[] }> = [
      ...history.map((h) => ({
        role: h.role === "assistant" ? "model" : "user",
        parts: [{ text: h.text }],
      })),
      { role: "user", parts: [{ text: message }] },
    ];

    const actionsPerformed: Array<{ name: string; args: Record<string, unknown> }> = [];
    let reply = await callGemini(contents, tasks);

    for (let round = 0; round < 4 && reply.functionCalls.length > 0; round++) {
      const functionResponseParts = [];
      for (const call of reply.functionCalls) {
        const result = await executeAction(supabase, userId, call.name, call.args);
        actionsPerformed.push({ name: call.name, args: call.args });
        functionResponseParts.push({
          functionResponse: { name: call.name, response: result },
        });
      }
      contents.push({ role: "model", parts: reply.rawParts });
      contents.push({ role: "function", parts: functionResponseParts });
      reply = await callGemini(contents, tasks);
    }

    return jsonResponse({ reply: reply.text || "D'accord, c'est fait.", actionsPerformed });
  } catch (err) {
    console.error(err);
    return jsonResponse({ error: err instanceof Error ? err.message : "Erreur serveur." }, 500);
  }
});

async function callGemini(contents: Array<{ role: string; parts: unknown[] }>, tasks: Task[]) {
  const res = await fetch(
    `https://generativelanguage.googleapis.com/v1beta/models/${GEMINI_MODEL}:generateContent`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json", "x-goog-api-key": GEMINI_API_KEY },
      body: JSON.stringify({
        system_instruction: { parts: [{ text: buildSystemPrompt(tasks) }] },
        contents,
        tools: [{ function_declarations: FUNCTION_DECLARATIONS }],
      }),
    }
  );

  if (!res.ok) {
    throw new Error(`Gemini a répondu une erreur (${res.status}) : ${await res.text()}`);
  }

  const data = await res.json();
  const parts: any[] = data?.candidates?.[0]?.content?.parts ?? [];
  const text = parts.filter((p) => p.text).map((p) => p.text).join(" ").trim();
  const functionCalls = parts
    .filter((p) => p.functionCall)
    .map((p) => ({ name: p.functionCall.name as string, args: (p.functionCall.args ?? {}) as Record<string, unknown> }));

  return { text, functionCalls, rawParts: parts };
}

async function executeAction(
  supabase: SupabaseClient,
  userId: string,
  name: string,
  args: Record<string, unknown>
) {
  switch (name) {
    case "add_task": {
      const text = String(args.text ?? "").trim();
      if (!text) return { ok: false, error: "Texte de tâche vide." };
      const { data, error } = await supabase
        .from("tasks")
        .insert({ text, user_id: userId })
        .select()
        .single();
      return error ? { ok: false, error: error.message } : { ok: true, task: data };
    }
    case "complete_task":
      return updateDone(supabase, String(args.task_id ?? ""), true);
    case "uncomplete_task":
      return updateDone(supabase, String(args.task_id ?? ""), false);
    case "delete_task": {
      const { error } = await supabase.from("tasks").delete().eq("id", String(args.task_id ?? ""));
      return error ? { ok: false, error: error.message } : { ok: true };
    }
    default:
      return { ok: false, error: "Fonction inconnue : " + name };
  }
}

async function updateDone(supabase: SupabaseClient, taskId: string, done: boolean) {
  if (!taskId) return { ok: false, error: "task_id manquant." };
  const { data, error } = await supabase.from("tasks").update({ done }).eq("id", taskId).select().single();
  return error ? { ok: false, error: error.message } : { ok: true, task: data };
}

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json", ...CORS_HEADERS },
  });
}
