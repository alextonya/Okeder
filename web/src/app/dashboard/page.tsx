import { auth } from "@clerk/nextjs/server";
import { redirect } from "next/navigation";

async function getEvents(token: string) {
  try {
    const base = process.env.BACKEND_INTERNAL_URL
      ? `${process.env.BACKEND_INTERNAL_URL}/v1`
      : process.env.NEXT_PUBLIC_API_BASE_URL;
    const res = await fetch(`${base}/events`, {
      headers: { Authorization: `Bearer ${token}` },
      cache: "no-store",
    });
    if (!res.ok) return [];
    return res.json();
  } catch {
    return [];
  }
}

export default async function Dashboard() {
  const { userId, getToken } = await auth();
  if (!userId) redirect("/sign-in");

  const token = await getToken();
  const events = token ? await getEvents(token) : [];

  return (
    <main className="mx-auto max-w-lg px-4 py-8">
      <h1 className="mb-6 text-2xl font-bold">Your Events</h1>
      {events.length === 0 ? (
        <div className="rounded-xl border border-slate-800 p-8 text-center text-slate-400">
          <p>No active events yet.</p>
          <p className="mt-2 text-sm">Add @Okeder to a Telegram group to get started.</p>
        </div>
      ) : (
        <ul className="space-y-3">
          {events.map((e: { id: string; title?: string; status: string }) => (
            <li key={e.id}>
              <a
                href={`/events/${e.id}`}
                className="flex items-center justify-between rounded-xl border border-slate-800 p-4 hover:border-slate-600 transition-colors"
              >
                <span className="font-medium">{e.title || "Group Event"}</span>
                <span className="text-xs text-slate-400 uppercase tracking-wide">{e.status}</span>
              </a>
            </li>
          ))}
        </ul>
      )}
    </main>
  );
}
