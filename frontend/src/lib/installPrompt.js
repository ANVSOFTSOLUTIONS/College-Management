import { useEffect, useState } from "react";

// Chrome/Android fire `beforeinstallprompt` once, early; keep it for the Install button.
let deferredPrompt = null;
const listeners = new Set();

if (typeof window !== "undefined") {
  window.addEventListener("beforeinstallprompt", (event) => {
    event.preventDefault();
    deferredPrompt = event;
    listeners.forEach((notify) => notify());
  });
  window.addEventListener("appinstalled", () => {
    deferredPrompt = null;
    listeners.forEach((notify) => notify());
  });
}

export function isStandalone() {
  return window.matchMedia?.("(display-mode: standalone)").matches || window.navigator.standalone === true;
}

export function isIOS() {
  return /iphone|ipad|ipod/i.test(window.navigator.userAgent);
}

export function useInstallPrompt() {
  const [, setVersion] = useState(0);
  useEffect(() => {
    const notify = () => setVersion((v) => v + 1);
    listeners.add(notify);
    return () => listeners.delete(notify);
  }, []);

  return {
    installed: isStandalone(),
    canInstall: Boolean(deferredPrompt),
    ios: isIOS(),
    async install() {
      if (!deferredPrompt) return false;
      deferredPrompt.prompt();
      const choice = await deferredPrompt.userChoice;
      deferredPrompt = null;
      listeners.forEach((notify) => notify());
      return choice.outcome === "accepted";
    },
  };
}
