"use client";

import { useAuth } from "@clerk/nextjs";
import { useEffect, useState } from "react";

interface WizardEvent {
  id: string;
  title?: string;
  status: string;
  wizard_mode: boolean;
}

interface WizardEventDetail {
  id: string;
  title?: string;
  status: string;
  wizard_mode: boolean;
  constraint_deadline?: string;
  members: Array<{
    id: string;
    display_name: string;
    telegram_id?: number;
    role: string;
    preference_status: "pending" | "submitted" | "declined";
    preference?: {
      budget_min?: number;
      budget_max?: number;
      category_prefs?: string[];
      hard_constraints?: string[];
      soft_preferences?: string[];
    } | null;
  }>;
  submitted_count: number;
  total_members: number;
  proposal?: {
    id: string;
    version: number;
    title: string;
    venue_name?: string;
    venue_address?: string;
    date_time?: string;
    price_per_person?: number;
    category?: string;
    external_url?: string;
    pct_budget_satisfied?: number;
    pct_time_satisfied?: number;
    pct_prefs_satisfied?: number;
    compromise_flagged?: boolean;
    compromise_explanation?: string;
    generated_by: string;
    published: boolean;
    commitments: { soft: number; confirmed: number; hard: number };
  } | null;
}

const STATUS_NEXT: Record<string, string> = {
  collecting: "deciding",
  deciding: "proposed",
  proposed: "committing",
  committing: "booking",
  booking: "confirmed",
  confirmed: "completed",
};

const STATUS_COLOR: Record<string, string> = {
  collecting: "text-amber-400",
  deciding: "text-blue-400",
  proposed: "text-indigo-400",
  committing: "text-purple-400",
  booking: "text-cyan-400",
  confirmed: "text-green-400",
  completed: "text-slate-500",
  expired: "text-red-400",
};

export default function WizardPage() {
  const { getToken } = useAuth();
  const [events, setEvents] = useState<WizardEvent[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [detail, setDetail] = useState<WizardEventDetail | null>(null);
  const [loading, setLoading] = useState<string | null>(null);
  const [showProposalForm, setShowProposalForm] = useState(false);

  // Champs du formulaire de proposal
  const [pTitle, setPTitle] = useState("");
  const [pVenue, setPVenue] = useState("");
  const [pAddress, setPAddress] = useState("");
  const [pDate, setPDate] = useState("");
  const [pPrice, setPPrice] = useState("");
  const [pCategory, setPCategory] = useState("");
  const [pUrl, setPUrl] = useState("");
  const [pBudgetPct, setPBudgetPct] = useState("80");
  const [pTimePct, setPTimePct] = useState("80");
  const [pPrefsPct, setPPrefsPct] = useState("80");
  const [pCompromise, setPCompromise] = useState(false);
  const [pCompromiseNote, setPCompromiseNote] = useState("");

  async function api<T = unknown>(path: string, opts?: RequestInit): Promise<T> {
    const token = await getToken();
    const res = await fetch(`${process.env.NEXT_PUBLIC_API_BASE_URL}${path}`, {
      ...opts,
      headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json", ...(opts?.headers ?? {}) },
    });
    if (!res.ok) throw new Error(`${res.status} ${path}`);
    return res.json();
  }

  async function loadEvents() {
    try {
      const data = await api<WizardEvent[]>("/wizard/events");
      setEvents(data);
    } catch {}
  }

  async function loadDetail(eventId: string) {
    try {
      const data = await api<WizardEventDetail>(`/wizard/events/${eventId}`);
      setDetail(data);
      // Préremplir le formulaire si une proposal existe
      if (data.proposal && !data.proposal.published) {
        setPTitle(data.proposal.title ?? "");
        setPVenue(data.proposal.venue_name ?? "");
        setPAddress(data.proposal.venue_address ?? "");
        setPDate(data.proposal.date_time ? data.proposal.date_time.slice(0, 16) : "");
        setPPrice(data.proposal.price_per_person ? String(data.proposal.price_per_person / 100) : "");
        setPCategory(data.proposal.category ?? "");
        setPUrl(data.proposal.external_url ?? "");
        if (data.proposal.pct_budget_satisfied != null) setPBudgetPct(String(Math.round(data.proposal.pct_budget_satisfied * 100)));
        if (data.proposal.pct_time_satisfied != null) setPTimePct(String(Math.round(data.proposal.pct_time_satisfied * 100)));
        if (data.proposal.pct_prefs_satisfied != null) setPPrefsPct(String(Math.round(data.proposal.pct_prefs_satisfied * 100)));
        setPCompromise(data.proposal.compromise_flagged ?? false);
        setPCompromiseNote(data.proposal.compromise_explanation ?? "");
      }
    } catch {}
  }

  useEffect(() => { loadEvents(); }, []);
  useEffect(() => {
    if (selectedId) loadDetail(selectedId);
  }, [selectedId]);

  async function doAction(action: () => Promise<unknown>) {
    setLoading("action");
    try { await action(); } catch {}
    if (selectedId) await loadDetail(selectedId);
    await loadEvents();
    setLoading(null);
  }

  async function saveProposal() {
    if (!selectedId) return;
    const body: Record<string, unknown> = {
      title: pTitle || "Group outing",
      venue_name: pVenue || undefined,
      venue_address: pAddress || undefined,
      date_time: pDate || undefined,
      price_per_person: pPrice ? Math.round(parseFloat(pPrice) * 100) : undefined,
      category: pCategory || undefined,
      external_url: pUrl || undefined,
      pct_budget_satisfied: parseFloat(pBudgetPct) / 100,
      pct_time_satisfied: parseFloat(pTimePct) / 100,
      pct_prefs_satisfied: parseFloat(pPrefsPct) / 100,
      compromise_flagged: pCompromise,
      compromise_explanation: pCompromise ? pCompromiseNote : undefined,
    };

    await doAction(() => api(`/wizard/events/${selectedId}/proposals`, { method: "POST", body: JSON.stringify(body) }));
    setShowProposalForm(false);
  }

  const evt = events.find(e => e.id === selectedId);

  return (
    <div className="flex h-screen overflow-hidden">
      {/* Sidebar — liste des events */}
      <aside className="w-64 shrink-0 border-r border-slate-800 flex flex-col">
        <div className="p-4 border-b border-slate-800">
          <div className="flex items-center gap-2">
            <span className="text-lg font-bold">🧙 Wizard</span>
            <span className="rounded-full bg-amber-900/40 px-2 py-0.5 text-xs text-amber-400">OZ</span>
          </div>
        </div>
        <div className="flex-1 overflow-y-auto p-3 space-y-1">
          {events.length === 0 && (
            <p className="text-xs text-slate-500 px-2 py-4">No events yet. Add @Okeder to a Telegram group.</p>
          )}
          {events.map(e => (
            <button
              key={e.id}
              onClick={() => setSelectedId(e.id)}
              className={`w-full text-left rounded-lg px-3 py-2.5 transition-colors ${
                e.id === selectedId ? "bg-slate-800 text-white" : "text-slate-400 hover:bg-slate-900 hover:text-white"
              }`}
            >
              <div className="text-sm font-medium truncate">{e.title || "Group Event"}</div>
              <div className={`text-xs ${STATUS_COLOR[e.status] ?? "text-slate-500"}`}>{e.status}</div>
            </button>
          ))}
        </div>
      </aside>

      {/* Main panel */}
      <main className="flex-1 overflow-y-auto">
        {!selectedId ? (
          <div className="flex h-full items-center justify-center text-slate-500">
            Select an event to manage it
          </div>
        ) : !detail ? (
          <div className="flex h-full items-center justify-center text-slate-500">Loading…</div>
        ) : (
          <div className="p-6 max-w-3xl space-y-6">
            {/* Header */}
            <div className="flex items-start justify-between">
              <div>
                <h1 className="text-xl font-bold">{detail.title || "Group Event"}</h1>
                <p className={`text-sm font-medium ${STATUS_COLOR[detail.status] ?? "text-slate-400"}`}>
                  {detail.status}
                </p>
              </div>
              <div className="flex gap-2">
                {STATUS_NEXT[detail.status] && (
                  <button
                    onClick={() => doAction(() => api(`/wizard/events/${detail.id}/advance-status`, { method: "POST", body: JSON.stringify({ status: STATUS_NEXT[detail.status] }) }))}
                    disabled={loading === "action"}
                    className="rounded-lg bg-slate-800 px-3 py-1.5 text-sm hover:bg-slate-700 transition-colors disabled:opacity-50"
                  >
                    → {STATUS_NEXT[detail.status]}
                  </button>
                )}
              </div>
            </div>

            {/* Members & preferences */}
            <section className="rounded-xl border border-slate-800 overflow-hidden">
              <div className="flex items-center justify-between px-4 py-3 bg-slate-900/50 border-b border-slate-800">
                <span className="text-sm font-medium">Preferences</span>
                <span className="text-sm text-slate-400">{detail.submitted_count} / {detail.total_members} submitted</span>
              </div>
              <div className="divide-y divide-slate-800">
                {detail.members.map(m => (
                  <div key={m.id} className="px-4 py-3 flex items-start gap-3">
                    <div className="mt-0.5">
                      {m.preference_status === "submitted" && <span className="text-green-400 text-sm">✅</span>}
                      {m.preference_status === "declined"  && <span className="text-red-400 text-sm">❌</span>}
                      {m.preference_status === "pending"   && <span className="text-slate-500 text-sm">⏳</span>}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-medium">{m.display_name}</span>
                        {m.role === "initiator" && (
                          <span className="rounded-full border border-indigo-800 px-1.5 py-0.5 text-xs text-indigo-400">initiator</span>
                        )}
                      </div>
                      {m.preference && (
                        <div className="mt-1 text-xs text-slate-400 space-y-0.5">
                          {(m.preference.budget_min != null || m.preference.budget_max != null) && (
                            <div>💶 {m.preference.budget_min != null ? `€${m.preference.budget_min/100}` : "?"} — {m.preference.budget_max != null ? `€${m.preference.budget_max/100}` : "any"}</div>
                          )}
                          {m.preference.category_prefs?.length ? (
                            <div>🎯 {m.preference.category_prefs.join(", ")}</div>
                          ) : null}
                          {m.preference.hard_constraints?.length ? (
                            <div className="text-red-400">🚫 {m.preference.hard_constraints.join(", ")}</div>
                          ) : null}
                          {m.preference.soft_preferences?.length ? (
                            <div>✨ {m.preference.soft_preferences.join(", ")}</div>
                          ) : null}
                        </div>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </section>

            {/* Engine + Proposal actions */}
            <section className="flex flex-wrap gap-3">
              {["collecting", "deciding"].includes(detail.status) && (
                <button
                  onClick={() => doAction(() => api(`/wizard/events/${detail.id}/trigger-engine`, { method: "POST" }))}
                  disabled={loading === "action"}
                  className="rounded-lg border border-indigo-800 px-4 py-2 text-sm text-indigo-400 hover:border-indigo-600 transition-colors disabled:opacity-50"
                >
                  ⚡ Run Engine (auto-generate proposal)
                </button>
              )}
              <button
                onClick={() => setShowProposalForm(v => !v)}
                className="rounded-lg border border-slate-700 px-4 py-2 text-sm text-slate-300 hover:border-slate-500 transition-colors"
              >
                {showProposalForm ? "Hide form" : "✏️ Write proposal manually"}
              </button>
            </section>

            {/* Proposal creation form */}
            {showProposalForm && (
              <section className="rounded-xl border border-slate-700 p-4 space-y-4">
                <h2 className="font-semibold text-sm text-slate-300">New proposal</h2>
                <div className="grid grid-cols-2 gap-3">
                  <Field label="Title" value={pTitle} onChange={setPTitle} placeholder="Dinner at Dishoom" colSpan />
                  <Field label="Venue name" value={pVenue} onChange={setPVenue} placeholder="Dishoom King's Cross" />
                  <Field label="Address" value={pAddress} onChange={setPAddress} placeholder="5 Stable St, London" />
                  <Field label="Date & time" value={pDate} onChange={setPDate} type="datetime-local" />
                  <Field label="Price/person (€)" value={pPrice} onChange={setPPrice} type="number" placeholder="35" />
                  <Field label="Category" value={pCategory} onChange={setPCategory} placeholder="restaurant" />
                  <Field label="Booking URL" value={pUrl} onChange={setPUrl} placeholder="https://..." colSpan />
                </div>

                {/* Legitimacy sliders */}
                <div className="space-y-3 pt-2 border-t border-slate-800">
                  <h3 className="text-xs font-medium text-slate-400 uppercase tracking-wide">Legitimacy block (L4)</h3>
                  <Slider label="Budget satisfied" value={pBudgetPct} onChange={setPBudgetPct} />
                  <Slider label="Timing satisfied" value={pTimePct} onChange={setPTimePct} />
                  <Slider label="Preferences satisfied" value={pPrefsPct} onChange={setPPrefsPct} />
                  <div className="flex items-center gap-3">
                    <input type="checkbox" id="compromise" checked={pCompromise} onChange={e => setPCompromise(e.target.checked)} className="rounded" />
                    <label htmlFor="compromise" className="text-sm text-slate-300">Flag compromise</label>
                  </div>
                  {pCompromise && (
                    <Field label="Compromise explanation" value={pCompromiseNote} onChange={setPCompromiseNote} placeholder="Venue is 20min further than preferred" colSpan />
                  )}
                </div>

                <button
                  onClick={saveProposal}
                  disabled={loading === "action"}
                  className="w-full rounded-lg bg-indigo-600 py-2.5 text-sm font-semibold hover:bg-indigo-500 transition-colors disabled:opacity-50"
                >
                  Save proposal
                </button>
              </section>
            )}

            {/* Current proposal */}
            {detail.proposal && (
              <section className="rounded-xl border border-slate-800 overflow-hidden">
                <div className="flex items-center justify-between px-4 py-3 bg-slate-900/50 border-b border-slate-800">
                  <span className="text-sm font-medium">
                    Proposal v{detail.proposal.version}
                    <span className="ml-2 text-xs text-slate-500">({detail.proposal.generated_by})</span>
                  </span>
                  <div className="flex items-center gap-2">
                    {detail.proposal.published ? (
                      <span className="rounded-full bg-green-900/40 px-2 py-0.5 text-xs text-green-400">Published</span>
                    ) : (
                      <button
                        onClick={() => doAction(() => api(`/wizard/events/${detail.id}/send-proposal`, { method: "POST" }))}
                        disabled={loading === "action"}
                        className="rounded-lg bg-indigo-600 px-3 py-1.5 text-xs font-medium hover:bg-indigo-500 transition-colors disabled:opacity-50"
                      >
                        📤 Publish to group
                      </button>
                    )}
                  </div>
                </div>
                <div className="p-4 space-y-2 text-sm">
                  <p className="font-semibold text-base">{detail.proposal.title}</p>
                  {detail.proposal.venue_name && <p className="text-slate-400">📍 {detail.proposal.venue_name}</p>}
                  {detail.proposal.date_time && (
                    <p className="text-slate-400">
                      🕐 {new Date(detail.proposal.date_time).toLocaleString("en-GB", { weekday: "short", day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" })}
                    </p>
                  )}
                  {detail.proposal.price_per_person && (
                    <p className="text-slate-400">💶 €{detail.proposal.price_per_person / 100}/person</p>
                  )}
                  {/* Legitimacy */}
                  <div className="mt-3 space-y-1 border-t border-slate-800 pt-3">
                    {detail.proposal.pct_budget_satisfied != null && (
                      <LegRow label="Budget" pct={detail.proposal.pct_budget_satisfied} />
                    )}
                    {detail.proposal.pct_time_satisfied != null && (
                      <LegRow label="Timing" pct={detail.proposal.pct_time_satisfied} />
                    )}
                    {detail.proposal.pct_prefs_satisfied != null && (
                      <LegRow label="Preferences" pct={detail.proposal.pct_prefs_satisfied} />
                    )}
                    {detail.proposal.compromise_flagged && detail.proposal.compromise_explanation && (
                      <p className="text-amber-400 text-xs">⚠️ {detail.proposal.compromise_explanation}</p>
                    )}
                  </div>
                  {/* Commitments */}
                  <div className="mt-3 flex gap-4 border-t border-slate-800 pt-3">
                    <span className="text-slate-400">👍 {detail.proposal.commitments.soft}</span>
                    <span className="text-indigo-300">✅ {detail.proposal.commitments.confirmed}</span>
                    <span className="text-green-400">🔒 {detail.proposal.commitments.hard}</span>
                  </div>
                </div>
              </section>
            )}
          </div>
        )}
      </main>
    </div>
  );
}

// ─── Composants utilitaires ───────────────────────────────────────────────────

function Field({ label, value, onChange, placeholder, type = "text", colSpan }: {
  label: string; value: string; onChange: (v: string) => void;
  placeholder?: string; type?: string; colSpan?: boolean;
}) {
  return (
    <div className={colSpan ? "col-span-2" : ""}>
      <label className="block text-xs text-slate-400 mb-1">{label}</label>
      <input
        type={type}
        value={value}
        onChange={e => onChange(e.target.value)}
        placeholder={placeholder}
        className="w-full rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-sm focus:border-indigo-500 focus:outline-none"
      />
    </div>
  );
}

function Slider({ label, value, onChange }: { label: string; value: string; onChange: (v: string) => void }) {
  const pct = parseInt(value) || 0;
  return (
    <div className="flex items-center gap-3">
      <span className="text-xs text-slate-400 w-36 shrink-0">{label}</span>
      <input
        type="range" min={0} max={100} step={5}
        value={value}
        onChange={e => onChange(e.target.value)}
        className="flex-1 accent-indigo-500"
      />
      <span className={`text-xs font-medium w-8 text-right ${pct >= 70 ? "text-green-400" : "text-amber-400"}`}>
        {pct}%
      </span>
    </div>
  );
}

function LegRow({ label, pct }: { label: string; pct: number }) {
  const pctInt = Math.round(pct * 100);
  return (
    <div className="flex items-center gap-3">
      <span className={`text-xs ${pctInt >= 70 ? "text-green-400" : "text-amber-400"}`}>
        {pctInt >= 70 ? "✅" : "⚠️"}
      </span>
      <span className="text-xs text-slate-400 w-24">{label}</span>
      <div className="flex-1 h-1.5 rounded-full bg-slate-800">
        <div className={`h-full rounded-full ${pctInt >= 70 ? "bg-green-500" : "bg-amber-500"}`} style={{ width: `${pctInt}%` }} />
      </div>
      <span className="text-xs text-slate-500 w-8 text-right">{pctInt}%</span>
    </div>
  );
}
