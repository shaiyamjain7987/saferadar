// Offline-first report queueing.
// If a worker submits a report with no connection, we save the text fields
// (image uploads need connectivity and are skipped in offline mode — the
// worker is told this) to localStorage, then automatically POST them to
// /reports/new as soon as the browser is back online.

const OFFLINE_QUEUE_KEY = "sif_offline_report_queue";

function getQueue() {
  try {
    return JSON.parse(localStorage.getItem(OFFLINE_QUEUE_KEY)) || [];
  } catch (e) {
    return [];
  }
}

function saveQueue(queue) {
  localStorage.setItem(OFFLINE_QUEUE_KEY, JSON.stringify(queue));
}

function queueReportOffline(fields) {
  const queue = getQueue();
  queue.push({ ...fields, queued_at: new Date().toISOString() });
  saveQueue(queue);
  updateQueueBadge();
}

async function syncQueuedReports() {
  const queue = getQueue();
  if (!queue.length || !navigator.onLine) return;

  const remaining = [];
  for (const item of queue) {
    try {
      const body = new URLSearchParams();
      Object.entries(item).forEach(([k, v]) => {
        if (k !== "queued_at") body.append(k, v);
      });
      const res = await fetch("/worker/report/new", {
        method: "POST",
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
        body,
        credentials: "same-origin",
        redirect: "follow",
      });
      if (!res.ok) remaining.push(item);
    } catch (e) {
      remaining.push(item); // still offline / failed — keep it queued
    }
  }
  saveQueue(remaining);
  updateQueueBadge();
}

function updateQueueBadge() {
  const el = document.getElementById("offlineQueueBadge");
  if (!el) return;
  const count = getQueue().length;
  if (count > 0) {
    el.textContent = `${count} report${count > 1 ? "s" : ""} waiting to sync`;
    el.classList.remove("d-none");
  } else {
    el.classList.add("d-none");
  }
}

window.addEventListener("online", syncQueuedReports);
document.addEventListener("DOMContentLoaded", () => {
  updateQueueBadge();
  syncQueuedReports();
});