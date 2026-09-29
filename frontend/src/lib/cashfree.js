function loadCashfreeCheckout() {
  if (window.Cashfree) return Promise.resolve();
  return new Promise((resolve, reject) => {
    const script = document.createElement("script");
    script.src = "https://sdk.cashfree.com/js/v3/cashfree.js";
    script.onload = resolve;
    script.onerror = () => reject(new Error("Couldn't load the payment page. Check your connection."));
    document.body.appendChild(script);
  });
}

// Opens Cashfree Checkout over the page. Resolves to an error message when the payment
// wasn't completed, or null; the college's server then checks with Cashfree itself.
export async function openCashfreeCheckout(order) {
  await loadCashfreeCheckout();
  const cashfree = window.Cashfree({ mode: order.environment });
  const result = await cashfree.checkout({ paymentSessionId: order.payment_session_id, redirectTarget: "_modal" });
  if (result?.error && !result?.paymentDetails) return result.error.message || "The payment wasn't completed.";
  return null;
}
