"use client";

// Patch global de fetch : ajoute l'en-tête anti-avertissement ngrok à toutes les
// requêtes du PWA (sinon ngrok-free renvoie sa page d'alerte au lieu du JSON).
// Exécuté au chargement du bundle client, avant les effets des pages.
if (typeof window !== "undefined" && !(window as { __ngrokPatched?: boolean }).__ngrokPatched) {
  (window as { __ngrokPatched?: boolean }).__ngrokPatched = true;
  const orig = window.fetch.bind(window);
  window.fetch = (input: RequestInfo | URL, init: RequestInit = {}) => {
    const headers = new Headers(init.headers || undefined);
    headers.set("ngrok-skip-browser-warning", "true");
    return orig(input, { ...init, headers });
  };
}

export default function ClientInit() {
  return null;
}
