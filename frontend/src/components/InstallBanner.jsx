import { useState } from "react";

import { useInstallPrompt } from "../lib/installPrompt";

// "Install the app" call to action. Android/Chrome gets a real Install button;
// iPhone gets the Add to Home Screen steps (Safari has no install prompt).
function InstallBanner({ compact = false }) {
  const { installed, canInstall, ios, install } = useInstallPrompt();
  const [dismissed, setDismissed] = useState(false);

  if (installed || dismissed || (!canInstall && !ios)) return null;

  if (compact) {
    return canInstall ? (
      <button
        type="button"
        onClick={install}
        className="rounded-lg bg-emerald-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-emerald-700"
      >
        Install app
      </button>
    ) : null;
  }

  return (
    <div className="flex items-start gap-3 rounded-xl border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-900">
      <img src="/icons/icon-192.png" alt="" className="h-10 w-10 rounded-lg" />
      <div className="flex-1">
        <p className="font-semibold">Install the app on your phone</p>
        {canInstall ? (
          <p className="text-xs text-emerald-800">Opens straight from your home screen, like any other app.</p>
        ) : (
          <p className="text-xs text-emerald-800">
            In Safari, tap <span className="font-semibold">Share</span> (the square with an arrow), then{" "}
            <span className="font-semibold">Add to Home Screen</span>.
          </p>
        )}
        {canInstall && (
          <button type="button" onClick={install} className="mt-2 rounded-lg bg-emerald-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-emerald-700">
            Install app
          </button>
        )}
      </div>
      <button type="button" onClick={() => setDismissed(true)} aria-label="Dismiss" className="px-1 text-emerald-700 hover:text-emerald-900">
        ×
      </button>
    </div>
  );
}

export default InstallBanner;
