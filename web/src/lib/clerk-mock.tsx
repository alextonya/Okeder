// Mock du package @clerk/nextjs pour le mode dev (auth bypassée).
// Aliasé dans next.config.ts -> aucun import de page à modifier.
import React from "react";

const DEV_USER_ID = "dev_user_okeder";
const DEV_TOKEN = "dev-token";

export function ClerkProvider({ children }: { children: React.ReactNode }) {
  return <>{children}</>;
}

export function useAuth() {
  return {
    isLoaded: true,
    isSignedIn: true,
    userId: DEV_USER_ID,
    sessionId: "dev_session",
    getToken: async () => DEV_TOKEN,
    signOut: async () => {},
  };
}

export function useUser() {
  return {
    isLoaded: true,
    isSignedIn: true,
    user: { id: DEV_USER_ID, firstName: "Dev", fullName: "Dev User", primaryEmailAddress: { emailAddress: "dev@okeder.test" } },
  };
}

export function SignIn() {
  return (
    <div style={{ padding: 24, textAlign: "center" }}>
      <p style={{ marginBottom: 12 }}>🔓 Dev mode — Clerk auth bypassed.</p>
      <a href="/dashboard" style={{ color: "#6366f1" }}>Go to dashboard →</a>
    </div>
  );
}

export function SignedIn({ children }: { children: React.ReactNode }) {
  return <>{children}</>;
}

export function SignedOut() {
  return null;
}

export function UserButton() {
  return null;
}
