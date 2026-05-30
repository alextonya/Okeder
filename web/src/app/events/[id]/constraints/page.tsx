"use client";

import { useParams, useRouter } from "next/navigation";
import { useAuth } from "@clerk/nextjs";
import { useState } from "react";

const CATEGORIES = ["Restaurant", "Bar / Cocktails", "Concert / Show", "Sport / Activity", "Escape Room", "Cinema", "Other"];

export default function ConstraintsPage() {
  const { id } = useParams<{ id: string }>();
  const { getToken } = useAuth();
  const router = useRouter();

  const [budgetMin, setBudgetMin] = useState("");
  const [budgetMax, setBudgetMax] = useState("");
  const [selectedCats, setSelectedCats] = useState<string[]>([]);
  const [hardNos, setHardNos] = useState("");
  const [softPrefs, setSoftPrefs] = useState("");
  const [loading, setLoading] = useState(false);
  const [done, setDone] = useState(false);

  function toggleCat(cat: string) {
    setSelectedCats(prev =>
      prev.includes(cat) ? prev.filter(c => c !== cat) : [...prev, cat]
    );
  }

  async function submit() {
    setLoading(true);
    const token = await getToken();

    const body: Record<string, unknown> = {
      category_prefs: selectedCats.map(c => c.toLowerCase()),
    };
    if (budgetMin) body.budget_min = Math.round(parseFloat(budgetMin) * 100);
    if (budgetMax) body.budget_max = Math.round(parseFloat(budgetMax) * 100);
    if (hardNos) {
      body.hard_constraints = hardNos.split(",").map(s => s.trim()).filter(Boolean);
    }
    if (softPrefs) {
      body.soft_preferences = softPrefs.split(",").map(s => s.trim()).filter(Boolean);
    }

    await fetch(
      `${process.env.NEXT_PUBLIC_API_BASE_URL}/events/${id}/preferences`,
      {
        method: "POST",
        headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
        body: JSON.stringify(body),
      }
    );

    setLoading(false);
    setDone(true);
  }

  if (done) {
    return (
      <main className="mx-auto max-w-lg px-4 py-16 text-center space-y-4">
        <div className="text-5xl">✅</div>
        <h1 className="text-2xl font-bold">Done!</h1>
        <p className="text-slate-400">Your preferences have been saved. I'll notify you when a plan is ready.</p>
        <a href={`/events/${id}`} className="block mt-4 text-indigo-400 hover:text-indigo-300">
          Back to event →
        </a>
      </main>
    );
  }

  return (
    <main className="mx-auto max-w-lg px-4 py-8 space-y-6">
      <div>
        <a href={`/events/${id}`} className="text-slate-500 hover:text-slate-300 text-sm">← Back</a>
        <h1 className="mt-2 text-2xl font-bold">Your preferences</h1>
        <p className="text-slate-400 text-sm">Private — only used to find the best option for everyone.</p>
      </div>

      {/* Budget */}
      <div className="space-y-2">
        <label className="text-sm font-medium text-slate-300">Budget per person (€)</label>
        <div className="flex gap-3">
          <div className="flex-1">
            <input
              type="number"
              placeholder="Min (e.g. 20)"
              value={budgetMin}
              onChange={e => setBudgetMin(e.target.value)}
              className="w-full rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-sm focus:border-indigo-500 focus:outline-none"
            />
          </div>
          <span className="self-center text-slate-500">—</span>
          <div className="flex-1">
            <input
              type="number"
              placeholder="Max (e.g. 60)"
              value={budgetMax}
              onChange={e => setBudgetMax(e.target.value)}
              className="w-full rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-sm focus:border-indigo-500 focus:outline-none"
            />
          </div>
        </div>
      </div>

      {/* Category preferences */}
      <div className="space-y-2">
        <label className="text-sm font-medium text-slate-300">What kind of outing?</label>
        <div className="flex flex-wrap gap-2">
          {CATEGORIES.map(cat => (
            <button
              key={cat}
              onClick={() => toggleCat(cat)}
              className={`rounded-full px-3 py-1.5 text-sm border transition-colors ${
                selectedCats.includes(cat)
                  ? "border-indigo-500 bg-indigo-950 text-indigo-300"
                  : "border-slate-700 text-slate-400 hover:border-slate-500"
              }`}
            >
              {cat}
            </button>
          ))}
        </div>
      </div>

      {/* Hard constraints */}
      <div className="space-y-2">
        <label className="text-sm font-medium text-slate-300">Hard nos <span className="text-slate-500">(optional)</span></label>
        <input
          type="text"
          placeholder="e.g. no sushi, wheelchair access needed, halal only"
          value={hardNos}
          onChange={e => setHardNos(e.target.value)}
          className="w-full rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-sm focus:border-indigo-500 focus:outline-none"
        />
        <p className="text-xs text-slate-500">Separate with commas. These will be strictly respected.</p>
      </div>

      {/* Soft preferences */}
      <div className="space-y-2">
        <label className="text-sm font-medium text-slate-300">Nice to have <span className="text-slate-500">(optional)</span></label>
        <input
          type="text"
          placeholder="e.g. rooftop, jazz, outdoor terrace"
          value={softPrefs}
          onChange={e => setSoftPrefs(e.target.value)}
          className="w-full rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-sm focus:border-indigo-500 focus:outline-none"
        />
      </div>

      <button
        onClick={submit}
        disabled={loading}
        className="w-full rounded-xl bg-indigo-600 py-3 font-semibold hover:bg-indigo-500 disabled:opacity-50 transition-colors"
      >
        {loading ? "Saving…" : "Submit preferences"}
      </button>
    </main>
  );
}
