"use client";

import { useRouter } from "next/navigation";
import { useAuth } from "@clerk/nextjs";
import { useState } from "react";

export default function OnboardingPage() {
  const { getToken } = useAuth();
  const router = useRouter();
  const [displayName, setDisplayName] = useState("");
  const [consent1, setConsent1] = useState(false); // functional (required)
  const [consent2, setConsent2] = useState(false); // behavioral memory
  const [consent3, setConsent3] = useState(false); // aggregated insights
  const [loading, setLoading] = useState(false);

  async function submit() {
    if (!consent1) return; // level 1 required
    setLoading(true);
    const token = await getToken();

    // Enregistrer le consentement
    const consents = [
      { level: 1, granted: consent1 },
      { level: 2, granted: consent2 },
      { level: 3, granted: consent3 },
    ].filter(c => c.granted);

    await fetch(`${process.env.NEXT_PUBLIC_API_BASE_URL}/auth/consent`, {
      method: "POST",
      headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
      body: JSON.stringify({ display_name: displayName, consents, source: "pwa_onboarding" }),
    });

    router.push("/dashboard");
  }

  return (
    <main className="mx-auto max-w-lg px-4 py-12 space-y-8">
      <div className="text-center">
        <h1 className="text-3xl font-bold">Welcome to Okeder</h1>
        <p className="mt-2 text-slate-400">Let's set up your profile in 30 seconds.</p>
      </div>

      {/* Display name */}
      <div className="space-y-2">
        <label className="text-sm font-medium text-slate-300">Your name</label>
        <input
          type="text"
          placeholder="How should your group see you?"
          value={displayName}
          onChange={e => setDisplayName(e.target.value)}
          className="w-full rounded-xl border border-slate-700 bg-slate-900 px-4 py-3 focus:border-indigo-500 focus:outline-none"
        />
      </div>

      {/* GDPR consent */}
      <div className="rounded-xl border border-slate-800 overflow-hidden">
        <div className="px-4 py-3 bg-slate-900/50 border-b border-slate-800">
          <h2 className="text-sm font-semibold">Data & privacy</h2>
          <p className="text-xs text-slate-500 mt-0.5">We only collect what we need. You control everything.</p>
        </div>

        <div className="divide-y divide-slate-800">
          <ConsentRow
            required
            checked={consent1}
            onChange={setConsent1}
            title="Service data (required)"
            description="Availability, budget, event type — needed to coordinate. Without this, Okeder can't work."
          />
          <ConsentRow
            checked={consent2}
            onChange={setConsent2}
            title="Behavioural memory"
            description="Remember your preferences across events to improve future proposals. You can withdraw anytime."
          />
          <ConsentRow
            checked={consent3}
            onChange={setConsent3}
            title="Aggregated insights"
            description="Strictly anonymous group statistics shared with venue partners. Never individual data. Optional."
          />
        </div>
      </div>

      <button
        onClick={submit}
        disabled={!consent1 || loading}
        className="w-full rounded-xl bg-indigo-600 py-3.5 font-semibold hover:bg-indigo-500 disabled:opacity-40 transition-colors"
      >
        {loading ? "Saving…" : "Get started →"}
      </button>

      <p className="text-center text-xs text-slate-500">
        By continuing you accept our{" "}
        <a href="/terms" className="underline hover:text-slate-300">Terms of Service</a>
        {" "}and{" "}
        <a href="/privacy" className="underline hover:text-slate-300">Privacy Policy</a>.
      </p>
    </main>
  );
}

function ConsentRow({ title, description, checked, onChange, required }: {
  title: string; description: string;
  checked: boolean; onChange: (v: boolean) => void; required?: boolean;
}) {
  return (
    <label className="flex items-start gap-4 px-4 py-4 cursor-pointer hover:bg-slate-900/30 transition-colors">
      <div className="mt-0.5 shrink-0">
        <input
          type="checkbox"
          checked={checked}
          onChange={e => onChange(e.target.checked)}
          disabled={required && checked}
          className="w-4 h-4 rounded accent-indigo-500"
        />
      </div>
      <div>
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium">{title}</span>
          {required && (
            <span className="rounded-full border border-slate-700 px-1.5 py-0.5 text-xs text-slate-500">required</span>
          )}
        </div>
        <p className="text-xs text-slate-400 mt-0.5">{description}</p>
      </div>
    </label>
  );
}
