// AquaRappel — Supabase Edge Function "send-reminders"
//
// Appelée toutes les 15 minutes par un job pg_cron (voir
// supabase/migration_002_reminders_calendar.sql). Pour chaque utilisateur :
//   - envoie une fois par jour, au début de sa plage horaire, un récapitulatif
//     des tâches dont l'échéance est aujourd'hui ;
//   - envoie ensuite, à l'intervalle qu'il a choisi et tant qu'on est dans sa
//     plage horaire, un rappel des tâches non cochées en général.
// Les notifications sont de vraies notifications push (Web Push / VAPID),
// donc reçues même si l'appli est fermée.
//
// Secrets requis (Dashboard Supabase > Edge Functions > send-reminders > Secrets) :
//   VAPID_PUBLIC_KEY, VAPID_PRIVATE_KEY, VAPID_SUBJECT (ex: mailto:toi@example.com)
// SUPABASE_URL et SUPABASE_SERVICE_ROLE_KEY sont fournis automatiquement par
// Supabase à toutes les Edge Functions, pas besoin de les configurer.

import { createClient } from "https://esm.sh/@supabase/supabase-js@2";
import webpush from "npm:web-push@3.6.7";

const SUPABASE_URL = Deno.env.get("SUPABASE_URL") ?? "";
const SERVICE_ROLE_KEY = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") ?? "";
const VAPID_PUBLIC_KEY = Deno.env.get("VAPID_PUBLIC_KEY") ?? "";
const VAPID_PRIVATE_KEY = Deno.env.get("VAPID_PRIVATE_KEY") ?? "";
const VAPID_SUBJECT = Deno.env.get("VAPID_SUBJECT") ?? "mailto:contact@example.com";

const PARIS_TZ = "Europe/Paris";

type ReminderSettings = {
  user_id: string;
  window_start_hour: number;
  window_end_hour: number;
  interval_minutes: number;
  last_reminder_at: string | null;
  last_digest_date: string | null;
};

type Task = { id: string; text: string; done: boolean; due_date: string | null };
type PushSub = { id: string; endpoint: string; p256dh: string; auth_key: string };

const LEAD_INS = [
  "Petit rappel : il te reste",
  "N'oublie pas, il te reste encore",
  "Pense à finir",
];

function parisNow() {
  const now = new Date();
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone: PARIS_TZ,
    hour: "2-digit",
    hour12: false,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(now);
  const get = (type: string) => parts.find((p) => p.type === type)?.value ?? "";
  const hour = Number(get("hour")) % 24;
  const dateStr = `${get("year")}-${get("month")}-${get("day")}`;
  return { hour, dateStr, now };
}

Deno.serve(async (req: Request) => {
  if (req.method === "OPTIONS") return new Response(null, { status: 204 });

  if (!VAPID_PUBLIC_KEY || !VAPID_PRIVATE_KEY) {
    return new Response(JSON.stringify({ error: "VAPID keys non configurées." }), { status: 500 });
  }

  webpush.setVapidDetails(VAPID_SUBJECT, VAPID_PUBLIC_KEY, VAPID_PRIVATE_KEY);

  const supabase = createClient(SUPABASE_URL, SERVICE_ROLE_KEY);
  const { hour: parisHour, dateStr: parisDate, now } = parisNow();

  const { data: settingsRows, error: settingsErr } = await supabase
    .from("reminder_settings")
    .select("*");
  if (settingsErr) {
    return new Response(JSON.stringify({ error: settingsErr.message }), { status: 500 });
  }

  const results: Array<{ user_id: string; sent: boolean; reason?: string }> = [];

  for (const settings of (settingsRows ?? []) as ReminderSettings[]) {
    const { window_start_hour, window_end_hour, interval_minutes, last_reminder_at, last_digest_date } = settings;

    const inWindow = parisHour >= window_start_hour && parisHour < window_end_hour;
    if (!inWindow) {
      results.push({ user_id: settings.user_id, sent: false, reason: "hors plage horaire" });
      continue;
    }

    const digestDue = last_digest_date !== parisDate;
    const reminderDue =
      !last_reminder_at || now.getTime() - new Date(last_reminder_at).getTime() >= interval_minutes * 60 * 1000;

    if (!digestDue && !reminderDue) {
      results.push({ user_id: settings.user_id, sent: false, reason: "rien à envoyer" });
      continue;
    }

    const { data: tasks } = await supabase
      .from("tasks")
      .select("id, text, done, due_date")
      .eq("user_id", settings.user_id);
    const allTasks = (tasks ?? []) as Task[];
    const pending = allTasks.filter((t) => !t.done);
    const dueToday = pending.filter((t) => t.due_date === parisDate);

    const messageParts: string[] = [];
    let digestHandled = false;
    let reminderHandled = false;

    if (digestDue) {
      digestHandled = true;
      if (dueToday.length > 0) {
        const list = dueToday.map((t) => t.text).join(", ");
        messageParts.push(`Aujourd'hui : ${list}.`);
      }
    }

    if (reminderDue && pending.length > 0) {
      reminderHandled = true;
      const leadIn = LEAD_INS[Math.floor(Math.random() * LEAD_INS.length)];
      const shown = pending.slice(0, 4).map((t) => t.text);
      let list = shown.join(", ");
      if (pending.length > shown.length) list += `, et ${pending.length - shown.length} autre(s)`;
      const suffix = pending.length === 1 ? "à faire." : "tâche(s) à faire.";
      messageParts.push(`${leadIn} : ${list} — ${pending.length} ${suffix}`);
    }

    if (digestHandled) {
      await supabase.from("reminder_settings").update({ last_digest_date: parisDate }).eq("user_id", settings.user_id);
    }
    if (reminderHandled) {
      await supabase
        .from("reminder_settings")
        .update({ last_reminder_at: now.toISOString() })
        .eq("user_id", settings.user_id);
    }

    if (messageParts.length === 0) {
      results.push({ user_id: settings.user_id, sent: false, reason: "rien à faire aujourd'hui" });
      continue;
    }

    const body = messageParts.join(" ");

    const { data: subs } = await supabase
      .from("push_subscriptions")
      .select("id, endpoint, p256dh, auth_key")
      .eq("user_id", settings.user_id);

    let sentAny = false;
    for (const sub of (subs ?? []) as PushSub[]) {
      try {
        await webpush.sendNotification(
          {
            endpoint: sub.endpoint,
            keys: { p256dh: sub.p256dh, auth: sub.auth_key },
          },
          JSON.stringify({ title: "AquaRappel", body }),
        );
        sentAny = true;
      } catch (err) {
        const statusCode = (err as { statusCode?: number })?.statusCode;
        if (statusCode === 404 || statusCode === 410) {
          await supabase.from("push_subscriptions").delete().eq("id", sub.id);
        } else {
          console.error("Échec envoi push", settings.user_id, err);
        }
      }
    }

    results.push({ user_id: settings.user_id, sent: sentAny });
  }

  return new Response(JSON.stringify({ ok: true, results }), {
    headers: { "Content-Type": "application/json" },
  });
});
