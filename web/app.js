const MAX_SELECTIONS = 3;

const state = {
  countries: [],
  countryDataByCode: new Map(),
  selectedChannelKeys: loadSelection(),
  search: "",
  mode: localStorage.getItem("whatsontv.channelMode") === "sports" ? "sports" : "all",
};

const els = {
  status: document.querySelector("#status"),
  showAll: document.querySelector("#show-all"),
  showSports: document.querySelector("#show-sports"),
  channelSearch: document.querySelector("#channel-search"),
  channelList: document.querySelector("#channel-list"),
  guide: document.querySelector("#guide"),
  selectedSummary: document.querySelector("#selected-summary"),
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

function isCurrent(program) {
  const now = Date.now();
  return new Date(program.startAt).getTime() <= now && now < new Date(program.endAt).getTime();
}

function progressPercent(program) {
  const now = Date.now();
  const start = new Date(program.startAt).getTime();
  const end = new Date(program.endAt).getTime();
  if (now <= start) {
    return 0;
  }
  if (now >= end) {
    return 100;
  }
  return Math.round(((now - start) / (end - start)) * 100);
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
    state.countries.map((country) => loadJson(state.mode === "sports" ? country.sportsDataUrl : country.dataUrl))
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
          const current = channel.currentProgram || channel.programs[0];
          return `
            <label class="channel-choice ${disabled ? "disabled" : ""}">
              <input type="checkbox" value="${escapeHtml(key)}" ${checked ? "checked" : ""} ${disabled ? "disabled" : ""} />
              <div>
                <div class="channel-name">${escapeHtml(channel.name)}</div>
                <div class="channel-meta">${escapeHtml(channel.provider)}</div>
                <div class="channel-now">${escapeHtml(current?.title || "No current program")}</div>
              </div>
              ${channel.logoUrl ? `<img class="logo" src="${escapeHtml(channel.logoUrl)}" alt="" loading="lazy" />` : ""}
            </label>
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

function programCell(program) {
  if (!program) {
    return `<div class="empty-program">No program in this slot</div>`;
  }
  const current = isCurrent(program);
  const progress = current ? `<div class="progress"><span style="width: ${progressPercent(program)}%"></span></div>` : "";
  return `
    <article class="program ${current ? "current" : ""}">
      <div class="program-time">${formatTime(program.startAt)} – ${formatTime(program.endAt)}</div>
      <div class="program-title">${escapeHtml(program.title)}</div>
      ${program.description ? `<p class="program-description">${escapeHtml(program.description)}</p>` : ""}
      ${progress}
    </article>
  `;
}

function renderGuide() {
  const channels = selectedChannels();

  els.selectedSummary.textContent = channels.length
    ? `${channels.length}/${MAX_SELECTIONS} selected · current and next 3 hours`
    : `No channels selected yet. Choose up to ${MAX_SELECTIONS}.`;

  if (!channels.length) {
    els.guide.innerHTML = `<div class="empty-state">Pick up to three channels on the left to build your guide table.</div>`;
    return;
  }

  const maxRows = Math.max(...channels.map((channel) => channel.programs.length));
  const rows = Array.from({ length: maxRows }, (_, index) => {
    const label = index === 0 ? "Now" : `Next ${index}`;
    const cells = channels.map((channel) => `<td>${programCell(channel.programs[index])}</td>`).join("");
    return `<tr><th scope="row">${label}</th>${cells}</tr>`;
  }).join("");

  const headers = channels
    .map(
      (channel) => `
        <th scope="col">
          <div class="guide-channel-heading">
            ${channel.logoUrl ? `<img class="logo" src="${escapeHtml(channel.logoUrl)}" alt="" loading="lazy" />` : ""}
            <div>
              <div>${escapeHtml(channel.name)}</div>
              <span>${escapeHtml(channel.countryName)} · ${escapeHtml(channel.provider)}</span>
            </div>
          </div>
        </th>
      `
    )
    .join("");

  els.guide.innerHTML = `
    <div class="guide-table-wrap">
      <table class="guide-table">
        <thead>
          <tr><th scope="col">Slot</th>${headers}</tr>
        </thead>
        <tbody>${rows}</tbody>
      </table>
    </div>
  `;
}

function render() {
  const totalChannels = state.countries.reduce(
    (sum, country) => sum + (state.mode === "sports" ? country.sportsChannelCount || 0 : country.channelCount || 0),
    0
  );
  els.status.textContent = `${state.countries.length} countries · ${totalChannels} ${state.mode === "sports" ? "sports " : ""}channels loaded`;
  els.showAll.classList.toggle("active", state.mode === "all");
  els.showSports.classList.toggle("active", state.mode === "sports");
  els.channelSearch.placeholder = state.mode === "sports" ? "Search sports channels" : "Search all channels";
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
els.showSports.addEventListener("click", () => setMode("sports"));

els.channelSearch.addEventListener("input", (event) => {
  state.search = event.target.value;
  renderChannelList();
});

els.channelList.addEventListener("change", (event) => {
  if (event.target.type !== "checkbox") {
    return;
  }

  const key = event.target.value;
  const selected = selectedSet();

  if (event.target.checked && state.selectedChannelKeys.length >= MAX_SELECTIONS) {
    event.target.checked = false;
    return;
  }

  if (event.target.checked) {
    selected.add(key);
  } else {
    selected.delete(key);
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
  } catch (error) {
    els.status.textContent = error.message;
    els.guide.innerHTML = `<div class="empty-state">Could not load guide data. Run <code>python3 scripts/build_web_data.py</code>, then serve the web directory.</div>`;
  }
}

start();
