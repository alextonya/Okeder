"use client";

import { useParams } from "next/navigation";
import { useAuth } from "@clerk/nextjs";
import { useState } from "react";

const STARS = [1, 2, 3, 4, 5];

export default function RatingPage() {
  const { id } = useParams<{ id: string }>();
  const { getToken } = useAuth();
  const [selected, setSelected] = useState<number | null>(null);
  const [done, setDone] = useState(false);

  async function submit(score: number) {
    setSelected(score);
    const token = await getToken();
    await fetch(`${process.env.NEXT_PUBLIC_API_BASE_URL}/events/${id}/ratings`, {
      method: "POST",
      headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
      body: JSON.stringify({ score }),
    });
    setDone(true);
  }

  if (done) {
    return (
      <main className="mx-auto max-w-lg px-4 py-16 text-center space-y-4">
        <div className="text-5xl">🙏</div>
        <h1 className="text-2xl font-bold">Thanks!</h1>
        <p className="text-slate-400">Your feedback will improve the next proposal.</p>
        <a href="/dashboard" className="block mt-4 text-indigo-400 hover:text-indigo-300">
          Back to dashboard →
        </a>
      </main>
    );
  }

  return (
    <main className="mx-auto max-w-lg px-4 py-16 space-y-8 text-center">
      <div>
        <h1 className="text-2xl font-bold">How was it?</h1>
        <p className="mt-2 text-slate-400">Your rating helps improve future suggestions for your group.</p>
      </div>

      <div className="flex justify-center gap-3">
        {STARS.map(s => (
          <button
            key={s}
            onClick={() => submit(s)}
            className={`text-4xl transition-transform hover:scale-125 ${
              selected === s ? "scale-125" : ""
            }`}
          >
            {s <= (selected ?? 0) ? "⭐" : "☆"}
          </button>
        ))}
      </div>
    </main>
  );
}
