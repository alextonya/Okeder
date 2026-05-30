"use client";

import { useParams } from "next/navigation";
import { useState } from "react";
import { useAuth } from "@clerk/nextjs";

export default function CommitPage() {
  const { id } = useParams<{ id: string }>();
  const { getToken } = useAuth();
  const [level, setLevel] = useState<"soft" | "confirmed" | "hard" | null>(null);
  const [loading, setLoading] = useState(false);
  const [done, setDone] = useState(false);

  async function commit(l: "soft" | "confirmed" | "hard") {
    setLoading(true);
    const token = await getToken();

    // Récupérer la proposal courante
    const propRes = await fetch(
      `${process.env.NEXT_PUBLIC_API_BASE_URL}/events/${id}/proposals/current`,
      { headers: { Authorization: `Bearer ${token}` } }
    );
    if (!propRes.ok) { setLoading(false); return; }
    const proposal = await propRes.json();

    await fetch(
      `${process.env.NEXT_PUBLIC_API_BASE_URL}/proposals/${proposal.id}/commitments`,
      {
        method: "POST",
        headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
        body: JSON.stringify({ level: l }),
      }
    );

    setLevel(l);
    setLoading(false);
    setDone(true);
  }

  if (done) {
    return (
      <main className="mx-auto max-w-lg px-4 py-16 text-center space-y-4">
        <div className="text-5xl">
          {level === "soft" ? "👍" : level === "confirmed" ? "✅" : "🔒"}
        </div>
        <h1 className="text-2xl font-bold">
          {level === "soft" ? "Noted!" : level === "confirmed" ? "You're in!" : "Locked in!"}
        </h1>
        <p className="text-slate-400">
          {level === "hard"
            ? "Payment confirmed. You'll receive booking confirmation shortly."
            : "We'll notify you when the booking is confirmed."}
        </p>
      </main>
    );
  }

  return (
    <main className="mx-auto max-w-lg px-4 py-8 space-y-6">
      <h1 className="text-2xl font-bold">Confirm your attendance</h1>
      <p className="text-slate-400">Choose your commitment level:</p>

      <div className="space-y-3">
        <button
          onClick={() => commit("soft")}
          disabled={loading}
          className="w-full rounded-xl border border-slate-700 p-4 text-left hover:border-indigo-500 transition-colors"
        >
          <div className="font-semibold">👍 Interested</div>
          <div className="text-sm text-slate-400">I might join — no commitment yet</div>
        </button>

        <button
          onClick={() => commit("confirmed")}
          disabled={loading}
          className="w-full rounded-xl border border-indigo-700 p-4 text-left hover:border-indigo-400 transition-colors"
        >
          <div className="font-semibold">✅ I'm In</div>
          <div className="text-sm text-slate-400">Count me in — I'll be there</div>
        </button>

        <button
          onClick={() => commit("hard")}
          disabled={loading}
          className="w-full rounded-xl bg-indigo-600 p-4 text-left hover:bg-indigo-500 transition-colors"
        >
          <div className="font-semibold">🔒 Lock In</div>
          <div className="text-sm text-indigo-200">Confirm with payment — highest priority spot</div>
        </button>
      </div>
    </main>
  );
}
