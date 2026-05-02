const state = {
  countries: [],
  countryCode: null,
  countryData: null,
  selectedByCountry: loadSelection(),
  search: "",
};

const els = {
  status: document.querySelector("#status"),
  countrySelect: document.querySelector("#country-select"),
  channelSearch: document.querySelector("#channel-search"),
  channelList: document.querySelector("#channel-list"),
  guide: document.querySelector("#guide"),
  selectedSummary: document.querySelector("#selected-summary"),
  clearSelection: document.querySelector("#clear-selection"),
};

function loadSelection() {
  try {
    return JSON.parse(localStorage.getItem("whatsontv.selectedChannels") || "{}");
  } catch {
    return {};
  }
}

function saveSelection() {
  localStorage.setItem("whatsontv.selectedChannels", JSON.stringify(state.selectedByCountry));
}

function selectedSet() {
  const ids = state.selectedByCountry[state.countryCode] || [];
  return new Set(ids);
}

function setSelectedSet(ids) {
  state.selectedByCountry[state.countryCode] = Array.from(ids);
  saveSelection();
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

async function loadCountries() {
  const response = await fetch("data/countries.json");
  if (!response.ok) {
    throw new Error("Could not load countries.json");
  }
  const data = await response.json();
  state.countries = data.countries;
  state.countryCode = state.countries[0]?.code;
}

async function loadCountry(code) {
  const country = state.countries.find((item) => item.code === code);
  const response = await fetch(country.dataUrl);
  if (!response.ok) {
    throw new Error(`Could not load ${country.dataUrl}`);
  }
  state.countryCode = code;
  state.countryData = await response.json();
  state.search = "";
  els.channelSearch.value = "";
}

function renderCountrySelect() {
  els.countrySelect.innerHTML = state.countries
    .map((country) => `<option value="${country.code}">${country.name} (${country.channelCount})</option>`)
    .join("");
  els.countrySelect.value = state.countryCode;
}

function renderChannelList() {
  const selected = selectedSet();
  const query = state.search.trim().toLowerCase();
  const channels = state.countryData.channels.filter((channel) => channel.name.toLowerCase().includes(query));

  els.channelList.innerHTML = channels
    .map((channel) => {
      const current = channel.currentProgram || channel.programs[0];
      return `
        <label class="channel-choice">
          <input type="checkbox" value="${escapeHtml(channel.id)}" ${selected.has(channel.id) ? "checked" : ""} />
          <div>
            <div class="channel-name">${escapeHtml(channel.name)}</div>
            <div class="channel-now">${escapeHtml(current?.title || "No current program")}</div>
          </div>
          ${channel.logoUrl ? `<img class="logo" src="${escapeHtml(channel.logoUrl)}" alt="" loading="lazy" />` : ""}
        </label>
      `;
    })
    .join("");
}

function renderGuide() {
  const selected = selectedSet();
  const selectedChannels = state.countryData.channels.filter((channel) => selected.has(channel.id));

  els.selectedSummary.textContent = selectedChannels.length
    ? `${selectedChannels.length} selected · showing current and next ${state.countryData.windowHours} hours`
    : "No channels selected yet.";

  if (!selectedChannels.length) {
    els.guide.innerHTML = `<div class="empty-state">Pick a few channels on the left to build your personal guide.</div>`;
    return;
  }

  els.guide.innerHTML = selectedChannels
    .map((channel) => {
      const programs = channel.programs
        .map((program) => {
          const current = isCurrent(program);
          const progress = current ? `<div class="progress"><span style="width: ${progressPercent(program)}%"></span></div>` : "";
          return `
            <article class="program ${current ? "current" : ""}">
              <div class="program-time">${formatTime(program.startAt)} – ${formatTime(program.endAt)}</div>
              <div>
                <div class="program-title">${escapeHtml(program.title)}</div>
                ${program.description ? `<p class="program-description">${escapeHtml(program.description)}</p>` : ""}
                ${progress}
              </div>
            </article>
          `;
        })
        .join("");

      return `
        <section class="channel-card">
          <header class="channel-card-header">
            ${channel.logoUrl ? `<img class="logo" src="${escapeHtml(channel.logoUrl)}" alt="" loading="lazy" />` : ""}
            <div>
              <h3>${escapeHtml(channel.name)}</h3>
              <div class="status">${channel.currentProgram ? "On now" : "Upcoming"}</div>
            </div>
          </header>
          <div class="program-list">${programs}</div>
        </section>
      `;
    })
    .join("");
}

function render() {
  if (!state.countryData) {
    return;
  }
  els.status.textContent = `${state.countryData.countryName} · generated ${new Date(state.countryData.generatedAt).toLocaleString()}`;
  renderCountrySelect();
  renderChannelList();
  renderGuide();
}

els.countrySelect.addEventListener("change", async (event) => {
  els.status.textContent = "Loading guide data…";
  await loadCountry(event.target.value);
  render();
});

els.channelSearch.addEventListener("input", (event) => {
  state.search = event.target.value;
  renderChannelList();
});

els.channelList.addEventListener("change", (event) => {
  if (event.target.type !== "checkbox") {
    return;
  }
  const selected = selectedSet();
  if (event.target.checked) {
    selected.add(event.target.value);
  } else {
    selected.delete(event.target.value);
  }
  setSelectedSet(selected);
  renderGuide();
});

els.clearSelection.addEventListener("click", () => {
  setSelectedSet(new Set());
  render();
});

async function start() {
  try {
    await loadCountries();
    await loadCountry(state.countryCode);
    render();
  } catch (error) {
    els.status.textContent = error.message;
    els.guide.innerHTML = `<div class="empty-state">Could not load guide data. Run <code>python3 scripts/build_web_data.py</code>, then serve the web directory.</div>`;
  }
}

start();
