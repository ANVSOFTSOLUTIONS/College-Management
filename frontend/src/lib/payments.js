import { apiRequest } from "./apiClient";
import { openCashfreeCheckout } from "./cashfree";

// Opens the checkout of whichever gateway the college uses (the order says which).
// Resolves to an error message when the payment wasn't completed, or null; the
// school's server then checks with the gateway itself before recording anything.

const scripts = {};

function loadScript(src) {
  scripts[src] ??= new Promise((resolve, reject) => {
    const script = document.createElement("script");
    script.src = src;
    script.onload = resolve;
    script.onerror = () => {
      delete scripts[src];
      reject(new Error("Couldn't load the payment page. Check your connection."));
    };
    document.body.appendChild(script);
  });
  return scripts[src];
}

async function openRazorpayCheckout(order) {
  await loadScript("https://checkout.razorpay.com/v1/checkout.js");
  return new Promise((resolve) => {
    const checkout = new window.Razorpay({
      key: order.key_id,
      order_id: order.gateway_order_id,
      amount: Math.round(order.amount * 100),
      currency: "INR",
      name: order.school_name,
      description: order.description || "College fee",
      handler: () => resolve(null),
      modal: { ondismiss: () => resolve("The payment wasn't completed.") },
      theme: { color: "#059669" },
    });
    checkout.open();
  });
}

async function openPhonePeCheckout(order) {
  await loadScript("https://mercury.phonepe.com/web/bundle/checkout.js");
  return new Promise((resolve) => {
    window.PhonePeCheckout.transact({
      tokenUrl: order.checkout_url,
      type: "IFRAME",
      callback: (response) => resolve(response === "USER_CANCEL" ? "The payment wasn't completed." : null),
    });
  });
}

// The demo gateway's payment page: a small dialog over the app. No money moves.
function openDemoCheckout(order) {
  return new Promise((resolve) => {
    const rupees = new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR" }).format(order.amount);
    const overlay = document.createElement("div");
    overlay.className = "fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 p-4";
    overlay.innerHTML = `
      <div role="dialog" aria-modal="true" aria-labelledby="demo-pay-title" class="w-full max-w-sm space-y-4 rounded-2xl bg-white p-6 shadow-xl">
        <p class="w-fit rounded-full bg-amber-100 px-2 py-0.5 text-xs font-bold uppercase text-amber-800">Demo payment · no real money</p>
        <div>
          <h2 id="demo-pay-title" class="text-lg font-bold text-slate-900"></h2>
          <p class="text-sm text-slate-500" data-desc></p>
        </div>
        <p class="text-3xl font-bold text-slate-900" data-amount></p>
        <p class="text-xs text-slate-500">This is a test gateway for showing online payment. A real college connects Cashfree, Razorpay or PhonePe instead.</p>
        <p class="hidden text-sm font-medium text-rose-600" data-error></p>
        <div class="flex flex-col gap-2">
          <button type="button" data-pay class="rounded-lg bg-emerald-600 px-4 py-2.5 font-semibold text-white hover:bg-emerald-700 disabled:opacity-60"></button>
          <button type="button" data-fail class="rounded-lg px-4 py-2 text-sm font-semibold text-rose-600 ring-1 ring-inset ring-rose-200 hover:bg-rose-50">Make it fail</button>
          <button type="button" data-cancel class="rounded-lg px-4 py-2 text-sm font-semibold text-slate-600 hover:bg-slate-100">Cancel</button>
        </div>
      </div>`;
    overlay.querySelector("h2").textContent = order.school_name;
    overlay.querySelector("[data-desc]").textContent = order.description || "College fee";
    overlay.querySelector("[data-amount]").textContent = rupees;
    overlay.querySelector("[data-pay]").textContent = `Pay ${rupees}`;
    document.body.appendChild(overlay);

    const close = (result) => {
      overlay.remove();
      resolve(result);
    };
    const finish = async (outcome) => {
      overlay.querySelectorAll("button").forEach((b) => (b.disabled = true));
      try {
        await apiRequest(`/public/payments/demo/${encodeURIComponent(order.gateway_order_id)}/${outcome}`, { method: "POST" });
        close(outcome === "pay" ? null : "The payment failed (demo).");
      } catch {
        const error = overlay.querySelector("[data-error]");
        error.textContent = "Couldn't reach the college. Try again.";
        error.classList.remove("hidden");
        overlay.querySelectorAll("button").forEach((b) => (b.disabled = false));
      }
    };
    overlay.querySelector("[data-pay]").addEventListener("click", () => finish("pay"));
    overlay.querySelector("[data-fail]").addEventListener("click", () => finish("fail"));
    overlay.querySelector("[data-cancel]").addEventListener("click", () => close("The payment wasn't completed."));
    overlay.querySelector("[data-pay]").focus();
  });
}

export function openCheckout(order) {
  if (order.provider === "demo") return openDemoCheckout(order);
  if (order.provider === "razorpay") return openRazorpayCheckout(order);
  if (order.provider === "phonepe") return openPhonePeCheckout(order);
  return openCashfreeCheckout(order);
}
