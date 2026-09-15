// Keep the edition date honest if a scheduled refresh fails. The report itself
// is fully rendered HTML and remains readable with JavaScript disabled.
const edition = document.querySelector(".edition time");
if (edition) {
  const expiresAt = Date.parse(`${edition.dateTime}T00:00:00Z`) + 7 * 24 * 60 * 60 * 1000;
  if (Date.now() >= expiresAt) document.getElementById("stale-note").hidden = false;
}
