/* Order tracking poller */
(function () {
  "use strict";

  const token = document.body.dataset.trackingToken;
  if (!token) return;

  const statusEl = document.getElementById("order-status");
  const timeline = document.getElementById("status-timeline");
  const STATUS_ORDER = ["placed", "accepted", "preparing", "ready", "served", "completed"];
  const LABELS = {
    placed: "Order Placed",
    accepted: "Order Accepted",
    preparing: "Preparing",
    ready: "Ready to Serve",
    served: "Served",
    completed: "Completed",
    rejected: "Rejected",
    cancelled: "Cancelled",
  };

  function updateUI(data) {
    if (statusEl) statusEl.textContent = LABELS[data.status] || data.status;
    if (timeline) {
      const items = timeline.querySelectorAll("li");
      const idx = STATUS_ORDER.indexOf(data.status);
      items.forEach((li, i) => {
        li.classList.remove("done", "current");
        if (i < idx) li.classList.add("done");
        else if (i === idx) li.classList.add("current", "done");
      });
    }
  }

  async function poll() {
    try {
      const res = await fetch("/api/track/" + token);
      if (!res.ok) return;
      const data = await res.json();
      updateUI(data);
      if (["completed", "rejected", "cancelled"].includes(data.status)) return; // stop
    } catch (_) {}
    setTimeout(poll, 5000);
  }

  setTimeout(poll, 5000);
})();
