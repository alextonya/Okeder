"use client";

import { useParams, useRouter } from "next/navigation";
import { useAuth } from "@clerk/nextjs";
import { useEffect, useState } from "react";

interface EventSummary {
  event_id: string;
  status: string;
  wizard_mode: boolean;
  member_count: number;
  preferences_submitted: number;
  proposal: { id: string; title: string; published: boolean } | null;
  commitments: { soft: number; confirmed: number; hard: number };
}

const STATUS_LABELS: Record<string, { label: string; color: string }> = {
  collecting:  { label: "Collecting preferences", color: "text-amber-400" },
  deciding:    { label: "Deciding",               color: "text-blue-400"  },
  proposed:    { label: "Proposal ready",          color: "text-indigo-400"},
  committing:  { label: "Confirming attendance",   color: "text-purple-400"},
  booking:     { label: "Booking in progress",     color: "text-cyan-400"  },
  confirmed:   { label: "Confirmed!",              color: "text-green-400" },
  completed:   { label: "Completed",               color: "text-slate-400" },
  expired:     { label: "Expired",                 color: "text-red-400"   },
};

export default function EventPage() {
  const { id } = useParams<{ id: string }>();
  const { getToken } = useAuth();
  const router = useRouter();
  const [summary, setSummary] = useState<EventSummary | null>(null);

  useEffect(() => {
    async function load() {
      const token = await getToken();
      const res = await fetch(
        `${process.env.NEXT_PUBLIC_API_BASE_URL}/events/${id}/summary`,
        { headers: { Authorization: `Bearer ${token}` } }
      );
      if (res.ok) setSummary(await res.json());
    }
    load();
  }, [id, getToken]);

  if (!summary) {
    return <div className="p-8 text-center text-slate-400">Loading…</div>;
  }

  const statusInfo = STATUS_LABELS[summary.status] ?? { label: summary.status, color: "text-slate-400" };
  const prefPct = summary.member_count > 0
    ? Math.round((summary.preferences_submitted / summary.member_count) * 100)
    : 0;

  return (
    <main className="mx-auto max-w-lg px-4 py-8 space-y-6">
      {/* Header */}
      <div className="space-y-1">
        <div className="flex items-center gap-2">
          <a href="/dashboard" className="text-slate-500 hover:text-slate-300 text-sm">← Events</a>
        </div>
        <h1 className="text-2xl font-bold">Group Event</h1>
        <p className={`text-sm font-medium ${statusInfo.color}`}>{statusInfo.label}</p>
      </div>

      {/* Preference collection progress */}
      {["collecting", "deciding"].includes(summary.status) && (
        <div className="rounded-xl border border-slate-800 p-4 space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-sm font-medium">Preferences collected</span>
            <span className="text-sm text-slate-400">
              {summary.preferences_submitted} / {summary.member_count}
            </span>
          </div>
          <div className="h-2 rounded-full bg-slate-800 overflow-hidden">
            <div
              className="h-full rounded-full bg-indigo-500 transition-all"
              style={{ width: `${prefPct}%` }}
            />
          </div>
          {summary.preferences_submitted === 0 && (
            <p className="text-xs text-slate-500">
              Waiting for group members to respond to the Telegram DM.
            </p>
          )}
        </div>
      )}

      {/* Proposal card */}
      {summary.proposal && (
        <div className="rounded-xl border border-indigo-800 bg-indigo-950/30 p-4 space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-sm font-semibold text-indigo-300">Proposal ready</span>
            {summary.proposal.published && (
              <span className="rounded-full bg-green-900/40 px-2 py-0.5 text-xs text-green-400">
                Published
              </span>
            )}
          </div>
          <p className="font-medium">{summary.proposal.title}</p>

          {/* Commitments */}
          <div className="flex gap-4 text-sm">
            <span className="text-slate-400">👍 {summary.commitments.soft} interested</span>
            <span className="text-indigo-300">✅ {summary.commitments.confirmed} confirmed</span>
            <span className="text-green-400">🔒 {summary.commitments.hard} locked</span>
          </div>

          <a
            href={`/events/${id}/proposal`}
            className="block w-full rounded-lg bg-indigo-600 py-2 text-center text-sm font-medium hover:bg-indigo-500 transition-colors"
          >
            View Proposal →
          </a>
        </div>
      )}

      {/* Own constraints form if still collecting */}
      {summary.status === "collecting" && (
        <a
          href={`/events/${id}/constraints`}
          className="block w-full rounded-xl border border-slate-700 py-3 text-center text-sm text-slate-300 hover:border-slate-500 transition-colors"
        >
          Submit my preferences →
        </a>
      )}
    </main>
  );
}
