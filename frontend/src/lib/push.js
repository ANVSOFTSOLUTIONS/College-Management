// Phone/browser push notifications: they arrive even when the app is closed.
import { apiRequest } from "./apiClient";
import { isIOS, isStandalone } from "./installPrompt";

function urlBase64ToUint8Array(base64) {
  const padded = (base64 + "=".repeat((4 - (base64.length % 4)) % 4)).replace(/-/g, "+").replace(/_/g, "/");
  const raw = atob(padded);
  return Uint8Array.from(raw, (c) => c.charCodeAt(0));
}

// "unsupported" | "needs-install" (iPhone: only an installed app can get push) | "denied" | "off" | "on"
export async function pushStatus() {
  if (!("serviceWorker" in navigator) || !("PushManager" in window) || !("Notification" in window)) {
    return isIOS() && !isStandalone() ? "needs-install" : "unsupported";
  }
  if (Notification.permission === "denied") return "denied";
  const registration = await navigator.serviceWorker.getRegistration();
  if (!registration) return "unsupported";
  const subscription = await registration.pushManager.getSubscription();
  return subscription ? "on" : "off";
}

export async function enablePush(token) {
  const permission = await Notification.requestPermission();
  if (permission !== "granted") return permission === "denied" ? "denied" : "off";
  const registration = await navigator.serviceWorker.ready;
  const { public_key: publicKey } = await apiRequest("/push/public-key", { token });
  const subscription =
    (await registration.pushManager.getSubscription()) ??
    (await registration.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: urlBase64ToUint8Array(publicKey) }));
  const { endpoint, keys } = subscription.toJSON();
  await apiRequest("/push/subscribe", { method: "POST", token, body: { endpoint, keys } });
  return "on";
}

export async function disablePush(token) {
  const registration = await navigator.serviceWorker.getRegistration();
  const subscription = await registration?.pushManager.getSubscription();
  if (subscription) {
    await apiRequest("/push/unsubscribe", { method: "POST", token, body: { endpoint: subscription.endpoint } }).catch(() => {});
    await subscription.unsubscribe();
  }
  return "off";
}
