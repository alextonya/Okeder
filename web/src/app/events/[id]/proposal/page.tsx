"use client";

import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { useAuth } from "@clerk/nextjs";

interface Proposal {
  id: string;
  title: string;
  venue_name?: string;
  venue_address?: string;
  date_time?: string;
  price_per_person?: number;
  category?: string;
  pct_budget_satisfied?: number;
  pct_time_satisfied?: number;
  pct_prefs_satisfied?: number;
  compromise_flagged?: boolean;
  compromise_explanation?: string;
  external_url?: string;
}

export default function ProposalPage() {
  const { id } = useParams<{ id: string }>();
  const { getToken } = useAuth();
  const [proposal, setProposal] = useState<Proposal | null>(null);

  useEffect(() => {
    async function load() {
      const token = await getToken();
      const res = await fetch(
        `${process.env.NEXT_PUBLIC_API_BASE_URL}/events/${id}/proposals/current`,
        { headers: { Authorization: `Bearer ${token}` } }
      );
      if (res.ok) setProposal(await res.json());
    }
    load();
  }, [id, getToken]);

  if (!proposal) return <div className="p-8 text-center text-slate-400">Loading proposal…</div>;

  return (
    <main className="mx-auto max-w-lg px-4 py-8 space-y-6">
      <h1 className="text-2xl font-bold">{proposal.title}</h1>

      {proposal.venue_name && (
        <p className="text-slate-300">📍 {proposal.venue_name}</p>
      )}
      {proposal.date_time && (
        <p className="text-slate-300">
          🕐 {new Date(proposal.date_time).toLocaleString("en-GB", {
            weekday: "long", day: "numeric", month: "short", hour: "2-digit", minute: "2-digit",
          })}
        </p>
      )}
      {proposal.price_per_person && (
        <p className="text-slate-300">
          💶 €{(proposal.price_per_person / 100).toFixed(0)}/person
        </p>
      )}

      {/* Legitimacy block L4 */}
      <div className="rounded-xl border border-slate-800 p-4 space-y-2">
        <h2 className="text-sm font-semibold text-slate-400 uppercase tracking-wide">Why this?</h2>
        {proposal.pct_budget_satisfied != null && (
          <p className="text-sm">✅ Budget: {(proposal.pct_budget_satisfied * 100).toFixed(0)}% of the group covered</p>
        )}
        {proposal.pct_time_satisfied != null && (
          <p className="text-sm">✅ Timing: {(proposal.pct_time_satisfied * 100).toFixed(0)}% availability match</p>
        )}
        {proposal.pct_prefs_satisfied != null && (
          <p className="text-sm">✅ Preferences: {(proposal.pct_prefs_satisfied * 100).toFixed(0)}% preference match</p>
        )}
        {proposal.compromise_flagged && proposal.compromise_explanation && (
          <p className="text-sm text-amber-400">⚠️ {proposal.compromise_explanation}</p>
        )}
      </div>

      <div className="flex flex-col gap-3">
        <a
          href={`/events/${id}/commit`}
          className="w-full rounded-xl bg-indigo-600 py-3 text-center font-semibold hover:bg-indigo-500 transition-colors"
        >
          I'm In — Confirm
        </a>
        {proposal.external_url && (
          <a
            href={proposal.external_url}
            target="_blank"
            rel="noopener noreferrer"
            className="w-full rounded-xl border border-slate-700 py-3 text-center text-sm text-slate-300 hover:border-slate-500 transition-colors"
          >
            View Details →
          </a>
        )}
      </div>
    </main>
  );
}
