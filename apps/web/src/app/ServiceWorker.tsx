"use client";

import { useEffect } from "react";

/** Registers the minimal service worker so the app is installable to the home
 * screen (PWA). Silent no-op where service workers are unavailable. */
export default function ServiceWorker() {
  useEffect(() => {
    if ("serviceWorker" in navigator) {
      navigator.serviceWorker.register("/sw.js").catch(() => {});
    }
  }, []);
  return null;
}
