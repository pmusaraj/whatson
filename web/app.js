const MAX_SELECTIONS = 5;
const VISIBLE_HOURS = 3;
const PIXELS_PER_MINUTE = 2;
const SLOT_MINUTES = 30;

const state = {
  countries: [],
  countryDataByCode: new Map(),
  selectedChannelKeys: loadSelection(),
  search: "",
  mode: localStorage.getItem("whatsontv.channelMode") === "premium" ? "premium" : "all",
  now: new Date(),
};

const els = {
  status: document.querySelector("#status"),
  showAll: document.querySelector("#show-all"),
  showSports: document.querySelector("#show-sports"),
  channelSearch: document.querySelector("#channel-search"),
  channelList: document.querySelector("#channel-list"),
  guide: document.querySelector("#guide"),
  clearSelection: document.querySelector("#clear-selection"),
};

function loadSelection() {
  try {
    const saved = JSON.parse(localStorage.getItem("whatsontv.selectedChannels") || "[]");
    if (Array.isArray(saved)) {
      return saved.slice(0, MAX_SELECTIONS);
    }
    if (saved && typeof saved === "object") {
      return Object.entries(saved)
        .flatMap(([countryCode, channelIds]) =>
          Array.isArray(channelIds) ? channelIds.map((channelId) => channelKey(countryCode, channelId)) : []
        )
        .slice(0, MAX_SELECTIONS);
    }
    return [];
  } catch {
    return [];
  }
}

function saveSelection() {
  localStorage.setItem("whatsontv.selectedChannels", JSON.stringify(state.selectedChannelKeys));
}

function channelKey(countryCode, channelId) {
  return `${countryCode}:${channelId}`;
}

function parseChannelKey(key) {
  const separator = key.indexOf(":");
  if (separator === -1) {
    return [null, null];
  }
  return [key.slice(0, separator), key.slice(separator + 1)];
}

function selectedSet() {
  return new Set(state.selectedChannelKeys);
}

function selectedChannels() {
  return state.selectedChannelKeys
    .map((key) => {
      const [countryCode, channelId] = parseChannelKey(key);
      const countryData = state.countryDataByCode.get(countryCode);
      const channel = countryData?.channels.find((item) => item.id === channelId);
      if (!countryData || !channel) {
        return null;
      }
      return { ...channel, countryCode, countryName: countryData.countryName, key };
    })
    .filter(Boolean);
}

function formatTime(value) {
  return new Intl.DateTimeFormat(undefined, {
    hour: "numeric",
    minute: "2-digit",
  }).format(new Date(value));
}

function formatCurrentTime(value) {
  return new Intl.DateTimeFormat(undefined, {
    hour: "numeric",
    minute: "2-digit",
    second: "2-digit",
  }).format(value);
}

function minutesBetween(start, end) {
  return (end.getTime() - start.getTime()) / 60000;
}

function roundDownToSlot(date) {
  const rounded = new Date(date);
  rounded.setSeconds(0, 0);
  rounded.setMinutes(Math.floor(rounded.getMinutes() / SLOT_MINUTES) * SLOT_MINUTES);
  return rounded;
}

function timelineBounds() {
  const start = roundDownToSlot(state.now);
  const end = new Date(start.getTime() + VISIBLE_HOURS * 60 * 60000);
  return { start, end };
}

function isCurrent(program) {
  const now = state.now.getTime();
  return new Date(program.startAt).getTime() <= now && now < new Date(program.endAt).getTime();
}

function escapeHtml(value) {
  return String(value || "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

async function loadJson(url) {
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`Could not load ${url}`);
  }
  return response.json();
}

async function loadGuideData() {
  const data = await loadJson("data/countries.json");
  state.countries = data.countries;
  await loadCountryPayloads();
}

async function loadCountryPayloads() {
  state.countryDataByCode.clear();
  const countryPayloads = await Promise.all(
    state.countries.map((country) => loadJson(state.mode === "premium" ? country.premiumDataUrl : country.dataUrl))
  );
  for (const payload of countryPayloads) {
    state.countryDataByCode.set(payload.country, payload);
  }
  state.selectedChannelKeys = state.selectedChannelKeys.filter((key) => {
    const [countryCode, channelId] = parseChannelKey(key);
    return state.countryDataByCode.get(countryCode)?.channels.some((channel) => channel.id === channelId);
  });
  saveSelection();
}

function countryMatchesSearch(countryData, query) {
  return countryData.countryName.toLowerCase().includes(query) || countryData.country.toLowerCase().includes(query);
}

function channelMatchesSearch(countryData, channel, query) {
  if (!query) {
    return true;
  }
  return countryMatchesSearch(countryData, query) || channel.name.toLowerCase().includes(query) || channel.provider.toLowerCase().includes(query);
}

function renderChannelList() {
  const selected = selectedSet();
  const query = state.search.trim().toLowerCase();

  els.channelList.innerHTML = state.countries
    .map((country) => {
      const countryData = state.countryDataByCode.get(country.code);
      const channels = countryData.channels.filter((channel) => channelMatchesSearch(countryData, channel, query));
      if (!channels.length) {
        return "";
      }

      const choices = channels
        .map((channel) => {
          const key = channelKey(countryData.country, channel.id);
          const checked = selected.has(key);
          const disabled = !checked && state.selectedChannelKeys.length >= MAX_SELECTIONS;
          return `
            <button class="channel-choice ${checked ? "selected" : ""}" type="button" data-channel-key="${escapeHtml(key)}" aria-pressed="${checked}" ${disabled ? "disabled" : ""}>
              <span class="channel-name">${escapeHtml(channel.name)}</span>
            </button>
          `;
        })
        .join("");

      return `
        <section class="country-group">
          <h3>${escapeHtml(countryData.countryName)} <span>${channels.length}</span></h3>
          <div class="country-channels">${choices}</div>
        </section>
      `;
    })
    .join("");
}

function programTags(program) {
  const tags = [program.sportType, program.competition, ...(program.categories || [])].filter(Boolean);
  return [...new Set(tags)].slice(0, 4);
}

function overlappingPrograms(channel, start, end) {
  return channel.programs.filter((program) => {
    const programStart = new Date(program.startAt);
    const programEnd = new Date(program.endAt);
    return programEnd > start && programStart < end;
  });
}

function programmeBlock(program, start, end) {
  const programStart = new Date(program.startAt);
  const programEnd = new Date(program.endAt);
  const clippedStart = programStart < start ? start : programStart;
  const clippedEnd = programEnd > end ? end : programEnd;
  const top = Math.max(0, minutesBetween(start, clippedStart) * PIXELS_PER_MINUTE);
  const height = Math.max(34, minutesBetween(clippedStart, clippedEnd) * PIXELS_PER_MINUTE - 4);
  const current = isCurrent(program);
  const tags = programTags(program);

  return `
    <article class="program-block ${current ? "current" : ""}" style="top: ${top}px; height: ${height}px">
      <div class="program-time">${formatTime(program.startAt)} – ${formatTime(program.endAt)}</div>
      <div class="program-title">${escapeHtml(program.title)}</div>
      ${program.subtitle ? `<div class="program-subtitle">${escapeHtml(program.subtitle)}</div>` : ""}
      ${tags.length ? `<div class="program-tags">${tags.map((tag) => `<span>${escapeHtml(tag)}</span>`).join("")}</div>` : ""}
      ${program.description ? `<details class="program-description"><summary>Description</summary><p>${escapeHtml(program.description)}</p></details>` : ""}
    </article>
  `;
}

function timelineLabels(start, totalMinutes) {
  const labels = [];
  for (let offset = 0; offset <= totalMinutes; offset += SLOT_MINUTES) {
    labels.push(`
      <div class="time-label" style="top: ${offset * PIXELS_PER_MINUTE}px">
        ${formatTime(new Date(start.getTime() + offset * 60000))}
      </div>
    `);
  }
  return labels.join("");
}

function renderGuide() {
  const channels = selectedChannels();

  if (!channels.length) {
    els.guide.innerHTML = `<div class="empty-state">Pick up to ${MAX_SELECTIONS} channels on the left to build your guide.</div>`;
    return;
  }

  const { start, end } = timelineBounds();
  const totalMinutes = VISIBLE_HOURS * 60;
  const totalHeight = totalMinutes * PIXELS_PER_MINUTE;
  const currentOffset = Math.max(0, Math.min(totalMinutes, minutesBetween(start, state.now))) * PIXELS_PER_MINUTE;

  const headers = channels
    .map(
      (channel) => `
        <div class="guide-channel-heading">
          ${channel.logoUrl ? `<img class="logo" src="${escapeHtml(channel.logoUrl)}" alt="" loading="lazy" />` : ""}
          <div>
            <div>${escapeHtml(channel.name)}</div>
            <span>${escapeHtml(channel.countryName)} · ${escapeHtml(channel.provider)}</span>
          </div>
        </div>
      `
    )
    .join("");

  const columns = channels
    .map((channel) => {
      const programs = overlappingPrograms(channel, start, end);
      return `
        <div class="schedule-column" style="height: ${totalHeight}px">
          ${programs.length ? programs.map((program) => programmeBlock(program, start, end)).join("") : `<div class="empty-program">No program in this window</div>`}
        </div>
      `;
    })
    .join("");

  els.guide.innerHTML = `
    <div class="guide-meta">Showing ${formatTime(start)} – ${formatTime(end)} · current time ${formatCurrentTime(state.now)}</div>
    <div class="schedule-wrap" style="--guide-columns: ${channels.length}; --guide-height: ${totalHeight}px">
      <div class="schedule-header">
        <div class="time-header"></div>
        ${headers}
      </div>
      <div class="schedule-body" style="height: ${totalHeight}px">
        <div class="time-axis">${timelineLabels(start, totalMinutes)}</div>
        <div class="time-grid" aria-hidden="true">
          ${Array.from({ length: totalMinutes / SLOT_MINUTES + 1 }, (_, index) => `<span style="top: ${index * SLOT_MINUTES * PIXELS_PER_MINUTE}px"></span>`).join("")}
        </div>
        <div class="current-time-line" style="top: ${currentOffset}px"><span>${formatTime(state.now)}</span></div>
        <div class="schedule-columns">${columns}</div>
      </div>
    </div>
  `;
}

function render() {
  const totalChannels = state.countries.reduce(
    (sum, country) => sum + (state.mode === "premium" ? country.premiumChannelCount || 0 : country.channelCount || 0),
    0
  );
  els.status.textContent = `${state.countries.length} countries · ${totalChannels} ${state.mode === "premium" ? "premium " : ""}channels loaded`;
  els.showAll.classList.toggle("active", state.mode === "all");
  els.showSports.classList.toggle("active", state.mode === "premium");
  els.channelSearch.placeholder = state.mode === "premium" ? "Search premium channels" : "Search all channels";
  renderChannelList();
  renderGuide();
}

async function setMode(mode) {
  if (state.mode === mode) {
    return;
  }
  state.mode = mode;
  localStorage.setItem("whatsontv.channelMode", mode);
  els.status.textContent = "Loading guide data…";
  await loadCountryPayloads();
  render();
}

els.showAll.addEventListener("click", () => setMode("all"));
els.showSports.addEventListener("click", () => setMode("premium"));

els.channelSearch.addEventListener("input", (event) => {
  state.search = event.target.value;
  renderChannelList();
});

els.channelList.addEventListener("click", (event) => {
  const choice = event.target.closest(".channel-choice");
  if (!choice || choice.disabled) {
    return;
  }

  const key = choice.dataset.channelKey;
  const selected = selectedSet();
  const isSelected = selected.has(key);

  if (!isSelected && state.selectedChannelKeys.length >= MAX_SELECTIONS) {
    return;
  }

  if (isSelected) {
    selected.delete(key);
  } else {
    selected.add(key);
  }

  state.selectedChannelKeys = Array.from(selected).slice(0, MAX_SELECTIONS);
  saveSelection();
  render();
});

els.clearSelection.addEventListener("click", () => {
  state.selectedChannelKeys = [];
  saveSelection();
  render();
});

async function start() {
  try {
    await loadGuideData();
    render();
    window.setInterval(() => {
      state.now = new Date();
      renderGuide();
    }, 60000);
  } catch (error) {
    els.status.textContent = error.message;
    els.guide.innerHTML = `<div class="empty-state">Could not load guide data. Run <code>python3 scripts/build_web_data.py</code>, then serve the web directory.</div>`;
  }
}

start();
