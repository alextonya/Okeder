import type { Metadata, Viewport } from "next";
import { ClerkProvider } from "@clerk/nextjs";
import "./globals.css";
import ClientInit from "./ClientInit";

export const metadata: Metadata = {
  title: "Okeder — Ok, Ordered!",
  description: "Group coordination made effortless.",
  manifest: "/manifest.json",
  appleWebApp: { capable: true, statusBarStyle: "black-translucent", title: "Okeder" },
};

export const viewport: Viewport = {
  themeColor: "#0F172A",
  width: "device-width",
  initialScale: 1,
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <ClerkProvider>
      <html lang="en">
        <body className="bg-slate-950 text-slate-100 min-h-screen"><ClientInit />{children}</body>
      </html>
    </ClerkProvider>
  );
}
