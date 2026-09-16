// Show the actual edition dates only when the weekly refresh is overdue.
const report = document.getElementById("report");
if (report) {
  const expiresAt = Date.parse(`${report.dataset.weekStart}T00:00:00Z`) + 7 * 24 * 60 * 60 * 1000;
  if (Date.now() >= expiresAt) document.getElementById("stale-note").hidden = false;
}
