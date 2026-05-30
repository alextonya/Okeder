"use client";

import { useAuth } from "@clerk/nextjs";
import { useEffect, useState } from "react";

interface WizardEvent {
  id: string;
  title?: string;
  status: string;
}

const STATUS_NEXT: Record<string, string> = {
  collecting: "deciding",
  deciding: "proposed",
  proposed: "committing",
  committing: "booking",
  booking: "confirmed",
  confirmed: "completed",
};

export default function WizardPage() {
  const { getToken } = useAuth();
  const [events, setEvents] = useState<WizardEvent[]>([]);
  const [loading, setLoading] = useState<string | null>(null);

  async function fetchEvents() {
    const token = await getToken();
    const res = await fetch(`${process.env.NEXT_PUBLIC_API_BASE_URL}/wizard/events`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (res.ok) setEvents(await res.json());
  }

  useEffect(() => { fetchEvents(); }, []);

  async function advance(eventId: string, nextStatus: string) {
    setLoading(eventId);
    const token = await getToken();
    await fetch(`${process.env.NEXT_PUBLIC_API_BASE_URL}/wizard/events/${eventId}/advance-status`, {
      method: "POST",
      headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
      body: JSON.stringify({ status: nextStatus }),
    });
    await fetchEvents();
    setLoading(null);
  }

  async function triggerEngine(eventId: string) {
    setLoading(eventId);
    const token = await getToken();
    await fetch(`${process.env.NEXT_PUBLIC_API_BASE_URL}/wizard/events/${eventId}/trigger-engine`, {
      method: "POST",
      headers: { Authorization: `Bearer ${token}` },
    });
    setLoading(null);
  }

  async function sendProposal(eventId: string) {
    setLoading(eventId);
    const token = await getToken();
    await fetch(`${process.env.NEXT_PUBLIC_API_BASE_URL}/wizard/events/${eventId}/send-proposal`, {
      method: "POST",
      headers: { Authorization: `Bearer ${token}` },
    });
    setLoading(null);
  }

  return (
    <main className="mx-auto max-w-2xl px-4 py-8 space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">🧙 Wizard Panel</h1>
        <span className="rounded-full bg-amber-900/40 px-3 py-1 text-xs text-amber-400">
          Wizard of Oz Mode
        </span>
      </div>

      {events.length === 0 && (
        <p className="text-slate-400">No events yet. Add @Okeder to a Telegram group.</p>
      )}

      <div className="space-y-4">
        {events.map((e) => (
          <div key={e.id} className="rounded-xl border border-slate-800 p-4 space-y-3">
            <div className="flex items-center justify-between">
              <span className="font-semibold">{e.title || "Group Event"}</span>
              <span className="rounded-full border border-slate-700 px-2 py-0.5 text-xs text-slate-400 uppercase">
                {e.status}
              </span>
            </div>

            <div className="flex flex-wrap gap-2">
              {STATUS_NEXT[e.status] && (
                <button
                  onClick={() => advance(e.id, STATUS_NEXT[e.status])}
                  disabled={loading === e.id}
                  className="rounded-lg bg-slate-800 px-3 py-1.5 text-sm hover:bg-slate-700 transition-colors"
                >
                  → {STATUS_NEXT[e.status]}
                </button>
              )}
              {["collecting", "deciding"].includes(e.status) && (
                <button
                  onClick={() => triggerEngine(e.id)}
                  disabled={loading === e.id}
                  className="rounded-lg border border-indigo-800 px-3 py-1.5 text-sm text-indigo-400 hover:border-indigo-600 transition-colors"
                >
                  ⚡ Run Engine
                </button>
              )}
              {e.status === "proposed" && (
                <button
                  onClick={() => sendProposal(e.id)}
                  disabled={loading === e.id}
                  className="rounded-lg bg-indigo-600 px-3 py-1.5 text-sm hover:bg-indigo-500 transition-colors"
                >
                  📤 Send to Group
                </button>
              )}
              <a
                href={`/events/${e.id}`}
                className="rounded-lg border border-slate-700 px-3 py-1.5 text-sm text-slate-400 hover:border-slate-500 transition-colors"
              >
                View →
              </a>
            </div>
          </div>
        ))}
      </div>
    </main>
  );
}
