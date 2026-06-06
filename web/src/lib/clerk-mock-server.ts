// Mock du package @clerk/nextjs/server pour le mode dev (auth bypassée).
// Aliasé dans next.config.ts.
const DEV_USER_ID = "dev_user_okeder";
const DEV_TOKEN = "dev-token";

export async function auth() {
  return {
    userId: DEV_USER_ID,
    sessionId: "dev_session",
    getToken: async () => DEV_TOKEN,
  };
}

export async function currentUser() {
  return {
    id: DEV_USER_ID,
    firstName: "Dev",
    lastName: "User",
    fullName: "Dev User",
  };
}
