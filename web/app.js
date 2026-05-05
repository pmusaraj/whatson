const MAX_SELECTIONS = 10;
const VISIBLE_HOURS = 9;
const PIXELS_PER_MINUTE = 2;
const SLOT_MINUTES = 30;
const TIMELINE_LOOKBACK_MINUTES = 60;
const THEME_VERSION = "relative-update";
const DEFAULT_THEME = "sense";
const THEMES = {
  default: `theme.css?v=${THEME_VERSION}`,
  sense: `sense-theme.css?v=${THEME_VERSION}`,
};

const state = {
  countries: [],
  generatedAt: null,
  countryDataByCode: new Map(),
  selectedChannelKeys: loadSelection(),
  search: "",
  now: new Date(),
  mobileView: "guide",
  searchOpen: false,
};

const els = {
  status: document.querySelector("#status"),
  countryFlags: document.querySelector("#country-flags"),
  channelSearch: document.querySelector("#channel-search"),
  channelList: document.querySelector("#channel-list"),
  channelPicker: document.querySelector("#channel-picker"),
  searchResults: document.querySelector("#search-results"),
  guide: document.querySelector("#guide"),
  programDialog: document.querySelector("#program-dialog"),
  programDialogContent: document.querySelector("#program-dialog-content"),
  clearSelection: document.querySelector("#clear-selection"),
  mobileSearch: document.querySelector("#mobile-search"),
  mobileMenu: document.querySelector("#mobile-menu"),
  themeLink: document.querySelector("#theme-link"),
  themeSelect: document.querySelector("#theme-select"),
};

function loadSelection() {
  try {
    const saved = JSON.parse(
      localStorage.getItem("whatsontv.selectedChannels") || "[]",
    );
    if (Array.isArray(saved)) {
      return saved.slice(0, MAX_SELECTIONS);
    }
    if (saved && typeof saved === "object") {
      return Object.entries(saved)
        .flatMap(([countryCode, channelIds]) =>
          Array.isArray(channelIds)
            ? channelIds.map((channelId) => channelKey(countryCode, channelId))
            : [],
        )
        .slice(0, MAX_SELECTIONS);
    }
    return [];
  } catch {
    return [];
  }
}

function saveSelection() {
  localStorage.setItem(
    "whatsontv.selectedChannels",
    JSON.stringify(state.selectedChannelKeys),
  );
}

function loadTheme() {
  const migratedToSenseDefault =
    localStorage.getItem("whatsontv.themeDefault") === THEME_VERSION;
  const saved = localStorage.getItem("whatsontv.theme");
  if (!migratedToSenseDefault) {
    return DEFAULT_THEME;
  }
  return Object.hasOwn(THEMES, saved) ? saved : DEFAULT_THEME;
}

function setTheme(themeName) {
  const theme = Object.hasOwn(THEMES, themeName) ? themeName : DEFAULT_THEME;
  els.themeLink.href = THEMES[theme];
  if (els.themeSelect) {
    els.themeSelect.value = theme;
  }
  document.documentElement.dataset.theme = theme;
  localStorage.setItem("whatsontv.theme", theme);
  localStorage.setItem("whatsontv.themeDefault", THEME_VERSION);
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

function getChannelByKey(key) {
  const [countryCode, channelId] = parseChannelKey(key);
  const countryData = state.countryDataByCode.get(countryCode);
  const channel = countryData?.channels.find((item) => item.id === channelId);
  if (!countryData || !channel) {
    return null;
  }
  return {
    ...channel,
    countryCode,
    countryName: countryData.countryName,
    key,
  };
}

function selectedChannels() {
  return state.selectedChannelKeys.map(getChannelByKey).filter(Boolean);
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

function formatRelativeTime(value) {
  if (!value) {
    return "unknown";
  }

  const elapsedSeconds = Math.max(
    0,
    Math.round((state.now.getTime() - new Date(value).getTime()) / 1000),
  );
  const units = [
    ["day", 86400],
    ["hour", 3600],
    ["minute", 60],
  ];

  for (const [unit, seconds] of units) {
    if (elapsedSeconds >= seconds) {
      const amount = Math.floor(elapsedSeconds / seconds);
      return `${amount} ${unit}${amount === 1 ? "" : "s"} ago`;
    }
  }

  return "just now";
}

function minutesBetween(start, end) {
  return (end.getTime() - start.getTime()) / 60000;
}

function roundDownToSlot(date) {
  const rounded = new Date(date);
  rounded.setSeconds(0, 0);
  rounded.setMinutes(
    Math.floor(rounded.getMinutes() / SLOT_MINUTES) * SLOT_MINUTES,
  );
  return rounded;
}

function timelineBounds() {
  const start = new Date(
    state.now.getTime() - TIMELINE_LOOKBACK_MINUTES * 60000,
  );
  start.setSeconds(0, 0);
  const end = new Date(start.getTime() + VISIBLE_HOURS * 60 * 60000);
  return { start, end };
}

function isCurrent(program) {
  const now = state.now.getTime();
  return (
    new Date(program.startAt).getTime() <= now &&
    now < new Date(program.endAt).getTime()
  );
}

function escapeHtml(value) {
  return String(value || "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function flagEmoji(countryCode) {
  const flagCode = countryCode.toUpperCase() === "UK" ? "GB" : countryCode;
  return flagCode
    .toUpperCase()
    .replace(/./g, (char) => String.fromCodePoint(127397 + char.charCodeAt(0)));
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
  state.generatedAt = data.generatedAt;
  await loadCountryPayloads();
}

async function loadCountryPayloads() {
  state.countryDataByCode.clear();
  const countryPayloads = await Promise.all(
    state.countries.map(async (country) => {
      const payloads = await Promise.all([
        loadJson(country.dataUrl),
        loadJson(country.premiumDataUrl),
      ]);
      return mergeCountryPayloads(payloads);
    }),
  );
  for (const payload of countryPayloads) {
    state.countryDataByCode.set(payload.country, payload);
  }
  state.selectedChannelKeys = [
    ...new Set(
      state.selectedChannelKeys.map((key) => {
        const [countryCode, channelId] = parseChannelKey(key);
        const aliases =
          state.countryDataByCode.get(countryCode)?.duplicateChannelAliases ||
          {};
        return channelKey(countryCode, aliases[channelId] || channelId);
      }),
    ),
  ].filter((key) => {
    const [countryCode, channelId] = parseChannelKey(key);
    return state.countryDataByCode
      .get(countryCode)
      ?.channels.some((channel) => channel.id === channelId);
  });
  state.mobileView = "guide";
  saveSelection();
}

function mergeCountryPayloads(payloads) {
  const [basePayload] = payloads;
  const channelMap = new Map();
  const channelNameMap = new Map();
  const duplicateChannelAliases = {};

  for (const payload of payloads) {
    for (const channel of payload.channels || []) {
      const existingById = channelMap.get(channel.id);
      if (existingById) {
        channelMap.set(
          channel.id,
          mergeDuplicateChannels(existingById, channel),
        );
        continue;
      }

      const displayKey = normalizeChannelName(channel.name);
      const existingId = channelNameMap.get(displayKey);
      if (!existingId) {
        channelMap.set(channel.id, channel);
        channelNameMap.set(displayKey, channel.id);
        continue;
      }

      const existing = channelMap.get(existingId);
      const merged = mergeDuplicateChannels(existing, channel);
      const keptId =
        betterChannel(channel, existing) === channel ? channel.id : existingId;
      const droppedId = keptId === channel.id ? existingId : channel.id;
      channelMap.delete(droppedId);
      channelMap.set(keptId, { ...merged, id: keptId });
      channelNameMap.set(displayKey, keptId);
      duplicateChannelAliases[droppedId] = keptId;
      if (existingId !== keptId) {
        for (const [alias, target] of Object.entries(duplicateChannelAliases)) {
          if (target === existingId) {
            duplicateChannelAliases[alias] = keptId;
          }
        }
      }
    }
  }

  const channels = [...channelMap.values()]
    .map((channel) => ({
      ...channel,
      programs: mergePrograms(channel.programs || []),
    }))
    .sort((a, b) => a.name.localeCompare(b.name));

  return {
    ...basePayload,
    sourceGuides: [
      ...new Set(payloads.flatMap((payload) => payload.sourceGuides || [])),
    ],
    channelCount: channels.length,
    duplicateChannelAliases,
    premiumSportsOnly: false,
    channels,
  };
}

function normalizeChannelName(name) {
  return String(name || "")
    .toLowerCase()
    .replace(/&/g, " and ")
    .replace(/\b(hd|sd)\b$/g, "")
    .replace(/[^a-z0-9]+/g, " ")
    .trim();
}

function channelScore(channel) {
  const programs = channel.programs || [];
  const metadataScore = programs.reduce(
    (total, program) =>
      total +
      [
        "subtitle",
        "description",
        "imageUrl",
        "sportType",
        "competition",
      ].filter((key) => program[key]).length +
      (program.categories || []).length,
    0,
  );
  return programs.length * 10 + metadataScore + (channel.logoUrl ? 4 : 0);
}

function betterChannel(a, b) {
  return channelScore(a) > channelScore(b) ? a : b;
}

function mergePrograms(programs) {
  const slots = new Map();
  for (const program of programs) {
    const key = `${program.startAt}|${program.endAt}`;
    const existing = slots.get(key);
    if (!existing) {
      slots.set(key, program);
      continue;
    }
    if (programMetadataScore(program) > programMetadataScore(existing)) {
      slots.set(key, program);
    }
  }

  const deduped = [];
  for (const program of [...slots.values()].sort((a, b) =>
    a.startAt.localeCompare(b.startAt),
  )) {
    const overlapIndex = deduped.findIndex((existing) =>
      isOverlappingDuplicate(existing, program),
    );
    if (overlapIndex === -1) {
      deduped.push(program);
      continue;
    }
    if (
      programMetadataScore(program) >
      programMetadataScore(deduped[overlapIndex])
    ) {
      deduped[overlapIndex] = program;
    }
  }
  return deduped.sort((a, b) => a.startAt.localeCompare(b.startAt));
}

function programMetadataScore(program) {
  return (
    ["subtitle", "description", "imageUrl", "sportType", "competition"].filter(
      (field) => program[field],
    ).length + (program.categories || []).length
  );
}

function isOverlappingDuplicate(a, b) {
  const startA = new Date(a.startAt).getTime();
  const endA = new Date(a.endAt).getTime();
  const startB = new Date(b.startAt).getTime();
  const endB = new Date(b.endAt).getTime();
  const overlap = Math.min(endA, endB) - Math.max(startA, startB);
  if (overlap <= 0) {
    return false;
  }
  const shorterDuration = Math.min(endA - startA, endB - startB);
  return overlap / shorterDuration >= 0.5;
}

function mergeDuplicateChannels(a, b) {
  const preferred = betterChannel(a, b);
  const fallback = preferred === a ? b : a;
  return {
    ...fallback,
    ...preferred,
    logoUrl: preferred.logoUrl || fallback.logoUrl,
    sources: [
      ...new Set([...(fallback.sources || []), ...(preferred.sources || [])]),
    ],
    programs: mergePrograms([
      ...(fallback.programs || []),
      ...(preferred.programs || []),
    ]),
  };
}

function countryMatchesSearch(countryData, query) {
  return (
    countryData.countryName.toLowerCase().includes(query) ||
    countryData.country.toLowerCase().includes(query)
  );
}

function channelMatchesSearch(countryData, channel, query) {
  if (!query) {
    return true;
  }
  return (
    countryMatchesSearch(countryData, query) ||
    channel.name.toLowerCase().includes(query) ||
    channel.provider.toLowerCase().includes(query) ||
    (channel.programs || []).some((program) =>
      programMatchesSearch(countryData, channel, program, query),
    )
  );
}

function programMatchesSearch(countryData, channel, program, query) {
  if (!query) {
    return false;
  }
  const haystack = [
    program.title,
    program.subtitle,
    program.description,
    program.sportType,
    program.competition,
    ...(program.categories || []),
    channel.name,
    countryData.countryName,
    countryData.country,
  ]
    .filter(Boolean)
    .join(" ")
    .toLowerCase();
  return haystack.includes(query);
}

function searchProgramResults(query, limit = 60) {
  if (!query) {
    return [];
  }
  const results = [];
  for (const country of state.countries) {
    const countryData = state.countryDataByCode.get(country.code);
    if (!countryData) {
      continue;
    }
    for (const channel of countryData.channels) {
      const key = channelKey(countryData.country, channel.id);
      (channel.programs || []).forEach((program, index) => {
        if (!programMatchesSearch(countryData, channel, program, query)) {
          return;
        }
        results.push({
          channel,
          countryData,
          key,
          program,
          index,
          current: isCurrent(program),
        });
      });
    }
  }
  return results
    .sort((a, b) => {
      if (a.current !== b.current) {
        return a.current ? -1 : 1;
      }
      return a.program.startAt.localeCompare(b.program.startAt);
    })
    .slice(0, limit);
}

function renderSearchResults() {
  const query = state.search.trim().toLowerCase();
  if (!query) {
    els.searchResults.hidden = true;
    els.searchResults.innerHTML = "";
    return;
  }

  const results = searchProgramResults(query);
  els.searchResults.hidden = false;
  els.searchResults.innerHTML = `
    <div class="search-results-heading">
      <h2>Shows matching “${escapeHtml(state.search.trim())}”</h2>
      <span>${results.length ? `${results.length} result${results.length === 1 ? "" : "s"}` : "No matching shows"}</span>
    </div>
    ${
      results.length
        ? `
      <div class="show-results-list">
        ${results
          .map(
            ({ channel, countryData, key, program, index, current }) => `
              <button class="show-result ${current ? "current" : ""}" type="button" data-channel-key="${escapeHtml(key)}" data-program-index="${index}">
                <span class="show-result-time">${formatTime(program.startAt)} – ${formatTime(program.endAt)}</span>
                <span class="show-result-title">${escapeHtml(program.title)}</span>
                <span class="show-result-meta">${flagEmoji(countryData.country)} ${escapeHtml(channel.name)}</span>
              </button>
            `,
          )
          .join("")}
      </div>
    `
        : `<div class="empty-program">Try a channel, sport, team, league, or programme title.</div>`
    }
  `;
}

function renderChannelList() {
  const selected = selectedSet();
  const query = state.search.trim().toLowerCase();

  if (query) {
    const matchingChannels = state.countries.flatMap((country) => {
      const countryData = state.countryDataByCode.get(country.code);
      if (!countryData) {
        return [];
      }
      return countryData.channels
        .filter((channel) => channelMatchesSearch(countryData, channel, query))
        .map((channel) => ({ countryData, channel }));
    });

    els.channelList.innerHTML =
      matchingChannels
        .map(({ countryData, channel }) => {
          const key = channelKey(countryData.country, channel.id);
          const checked = selected.has(key);
          const disabled =
            !checked && state.selectedChannelKeys.length >= MAX_SELECTIONS;
          return `
          <button class="channel-choice search-channel-choice ${checked ? "selected" : ""}" type="button" data-channel-key="${escapeHtml(key)}" aria-pressed="${checked}" ${disabled ? "disabled" : ""}>
            <span class="channel-flag" aria-hidden="true">${flagEmoji(countryData.country)}</span>
            <span class="channel-name">${escapeHtml(channel.name)}</span>
          </button>
        `;
        })
        .join("") || `<div class="empty-program">No matching channels.</div>`;
    return;
  }

  els.channelList.innerHTML = state.countries
    .map((country) => {
      const countryData = state.countryDataByCode.get(country.code);
      const channels = countryData.channels.filter((channel) =>
        channelMatchesSearch(countryData, channel, query),
      );
      if (!channels.length) {
        return "";
      }

      const choices = channels
        .map((channel) => {
          const key = channelKey(countryData.country, channel.id);
          const checked = selected.has(key);
          const disabled =
            !checked && state.selectedChannelKeys.length >= MAX_SELECTIONS;
          return `
            <button class="channel-choice ${checked ? "selected" : ""}" type="button" data-channel-key="${escapeHtml(key)}" aria-pressed="${checked}" ${disabled ? "disabled" : ""}>
              <span class="channel-name">${escapeHtml(channel.name)}</span>
            </button>
          `;
        })
        .join("");

      return `
        <section class="country-group" data-country-code="${escapeHtml(countryData.country)}">
          <h3>${escapeHtml(countryData.countryName)}</h3>
          <div class="country-channels">${choices}</div>
        </section>
      `;
    })
    .join("");
}

function renderCountryFlags() {
  const query = state.search.trim().toLowerCase();
  if (query) {
    els.countryFlags.innerHTML = "";
    els.countryFlags.hidden = true;
    return;
  }
  els.countryFlags.hidden = false;
  els.countryFlags.innerHTML = state.countries
    .map((country) => {
      const countryData = state.countryDataByCode.get(country.code);
      const hasVisibleChannels = countryData?.channels.some((channel) =>
        channelMatchesSearch(countryData, channel, query),
      );
      if (!countryData || !hasVisibleChannels) {
        return "";
      }
      return `
        <button class="flag-button" type="button" data-country-code="${escapeHtml(countryData.country)}" title="${escapeHtml(countryData.countryName)}" aria-label="Jump to ${escapeHtml(countryData.countryName)}">
          <span aria-hidden="true">${flagEmoji(countryData.country)}</span>
        </button>
      `;
    })
    .join("");
}

function programTags(program) {
  const tags = [
    program.sportType,
    program.competition,
    ...(program.categories || []),
  ].filter(Boolean);
  return [...new Set(tags)].slice(0, 4);
}

function overlappingPrograms(channel, start, end) {
  return channel.programs
    .map((program, index) => ({ program, index }))
    .filter(({ program }) => {
      const programStart = new Date(program.startAt);
      const programEnd = new Date(program.endAt);
      return programEnd > start && programStart < end;
    });
}

function programmeBlock(program, start, end, channelKeyValue, programIndex) {
  const programStart = new Date(program.startAt);
  const programEnd = new Date(program.endAt);
  const clippedStart = programStart < start ? start : programStart;
  const clippedEnd = programEnd > end ? end : programEnd;
  const top = Math.max(
    0,
    minutesBetween(start, clippedStart) * PIXELS_PER_MINUTE,
  );
  const height = Math.max(
    34,
    minutesBetween(clippedStart, clippedEnd) * PIXELS_PER_MINUTE - 4,
  );
  const current = isCurrent(program);
  const tags = programTags(program);

  return `
    <article class="program-block ${current ? "current" : ""}" role="button" tabindex="0" data-channel-key="${escapeHtml(channelKeyValue)}" data-program-index="${programIndex}" aria-label="Show details for ${escapeHtml(program.title)}" style="top: ${top}px; height: ${height}px">
      <div class="program-time">${formatTime(program.startAt)} – ${formatTime(program.endAt)}</div>
      <div class="program-title">${escapeHtml(program.title)}</div>
      ${program.subtitle ? `<div class="program-subtitle">${escapeHtml(program.subtitle)}</div>` : ""}
      ${tags.length ? `<div class="program-tags">${tags.map((tag) => `<span>${escapeHtml(tag)}</span>`).join("")}</div>` : ""}
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
    els.guide.innerHTML = `
      <div class="empty-state">
        <p>This is a simple app to find what's on TV. Pick channels from the left column, or search above for a show, channel, or live event.</p>
        <p class="empty-state-notes">Data last updated ${escapeHtml(formatRelativeTime(state.generatedAt))} · <a href="https://github.com/pmusaraj/whatson" target="_blank" rel="noreferrer">GitHub</a> for questions, issues, and requests.</p>
      </div>`;
    return;
  }

  const { start, end } = timelineBounds();
  const totalMinutes = VISIBLE_HOURS * 60;
  const totalHeight = totalMinutes * PIXELS_PER_MINUTE;
  const currentOffset =
    Math.max(0, Math.min(totalMinutes, minutesBetween(start, state.now))) *
    PIXELS_PER_MINUTE;

  const headers = channels
    .map(
      (channel) => `
        <div class="guide-channel-heading">
          ${channel.logoUrl ? `<img class="logo" src="${escapeHtml(channel.logoUrl)}" alt="" loading="lazy" />` : ""}
          <span class="guide-channel-flag" aria-hidden="true">${flagEmoji(channel.countryCode)}</span>
          <div class="guide-channel-name">${escapeHtml(channel.name)}</div>
          <button class="remove-channel-button" type="button" data-channel-key="${escapeHtml(channel.key)}" aria-label="Remove ${escapeHtml(channel.name)} from guide">×</button>
        </div>
      `,
    )
    .join("");

  const columns = channels
    .map((channel) => {
      const programs = overlappingPrograms(channel, start, end);
      return `
        <div class="schedule-column" style="height: ${totalHeight}px">
          ${programs.length ? programs.map(({ program, index }) => programmeBlock(program, start, end, channel.key, index)).join("") : `<div class="empty-program">No program in this window</div>`}
        </div>
      `;
    })
    .join("");

  els.guide.innerHTML = `
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

function programDetailRows(program, channel) {
  const rows = [["Channel", `${channel.name} (${channel.countryName})`]];

  if (program.competition) {
    rows.push(["Competition", program.competition]);
  }
  if (program.sportType) {
    rows.push(["Sport", program.sportType]);
  }
  if (program.categories?.length) {
    rows.push(["Categories", program.categories.join(", ")]);
  }

  return rows
    .map(
      ([label, value]) => `
        <div class="program-detail-row">
          <dt>${escapeHtml(label)}</dt>
          <dd>${escapeHtml(value)}</dd>
        </div>
      `,
    )
    .join("");
}

function openProgramDetails(channelKeyValue, programIndex) {
  const channel = getChannelByKey(channelKeyValue);
  const program = channel?.programs[Number(programIndex)];
  if (!channel || !program) {
    return;
  }

  const tags = programTags(program);
  els.programDialogContent.innerHTML = `
    ${program.imageUrl ? `<img class="program-dialog-image" src="${escapeHtml(program.imageUrl)}" alt="" loading="lazy" />` : ""}
    <div class="program-dialog-kicker">${escapeHtml(channel.name)} · ${formatTime(program.startAt)} – ${formatTime(program.endAt)}</div>
    <h2 id="program-dialog-title">${escapeHtml(program.title)}</h2>
    ${program.subtitle ? `<p class="program-dialog-subtitle">${escapeHtml(program.subtitle)}</p>` : ""}
    ${tags.length ? `<div class="program-tags program-dialog-tags">${tags.map((tag) => `<span>${escapeHtml(tag)}</span>`).join("")}</div>` : ""}
    <dl class="program-detail-list">${programDetailRows(program, channel)}</dl>
    <p class="program-dialog-description">${program.description ? escapeHtml(program.description) : "No description available."}</p>
  `;

  if (typeof els.programDialog.showModal === "function") {
    els.programDialog.showModal();
  } else {
    els.programDialog.setAttribute("open", "");
  }
}

function handleProgramBlockOpen(event) {
  if (event.target.closest(".remove-channel-button")) {
    return;
  }
  const programBlock = event.target.closest(".program-block");
  if (!programBlock) {
    return;
  }
  openProgramDetails(
    programBlock.dataset.channelKey,
    programBlock.dataset.programIndex,
  );
}

function setMobileView(view) {
  state.mobileView = view;
  document.body.dataset.mobileView = view;
  if (els.mobileMenu) {
    const pickerOpen = view === "picker";
    els.mobileMenu.setAttribute("aria-expanded", String(pickerOpen));
    els.mobileMenu.setAttribute(
      "aria-label",
      pickerOpen ? "Hide channels" : "Show channels",
    );
  }
}

function setMobileSearchOpen(open, options = {}) {
  state.searchOpen = open;
  if (!open && options.clearSearch) {
    state.search = "";
    els.channelSearch.value = "";
    renderCountryFlags();
    renderChannelList();
    renderSearchResults();
  }
  if (!open && isMobileLayout()) {
    setMobileView("guide");
  }
  document.body.dataset.searchOpen = String(open);
  document.body.dataset.searching = String(Boolean(state.search.trim()));
  if (els.mobileSearch) {
    els.mobileSearch.setAttribute("aria-expanded", String(open));
    els.mobileSearch.setAttribute(
      "aria-label",
      open ? "Hide search" : "Search",
    );
  }
  if (open) {
    els.channelSearch.focus();
  }
}

function isMobileLayout() {
  return window.matchMedia("(max-width: 860px)").matches;
}

function render() {
  els.status.textContent = "";
  renderCountryFlags();
  renderChannelList();
  renderSearchResults();
  renderGuide();
  setMobileView(state.mobileView);
  setMobileSearchOpen(state.searchOpen);
}

els.channelSearch.addEventListener("input", (event) => {
  state.search = event.target.value;
  document.body.dataset.searching = String(Boolean(state.search.trim()));
  renderCountryFlags();
  renderChannelList();
  renderSearchResults();
});

els.countryFlags.addEventListener("click", (event) => {
  const button = event.target.closest(".flag-button");
  if (!button) {
    return;
  }

  const countryGroup = els.channelList.querySelector(
    `[data-country-code="${CSS.escape(button.dataset.countryCode)}"]`,
  );
  countryGroup?.scrollIntoView({ block: "start", behavior: "smooth" });
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
  if (isMobileLayout()) {
    setMobileView("guide");
  }
});

els.channelPicker.addEventListener("click", (event) => {
  if (
    isMobileLayout() &&
    state.mobileView === "guide" &&
    !state.search.trim() &&
    !event.target.closest("button")
  ) {
    setMobileView("picker");
  }
});

els.clearSelection.addEventListener("click", () => {
  state.selectedChannelKeys = [];
  saveSelection();
  render();
});

els.mobileMenu.addEventListener("click", () => {
  setMobileView(state.mobileView === "picker" ? "guide" : "picker");
});

els.mobileSearch?.addEventListener("click", () => {
  const nextOpen = !state.searchOpen;
  setMobileSearchOpen(nextOpen, { clearSearch: !nextOpen });
});

els.channelSearch.addEventListener("keydown", (event) => {
  if (event.key === "Escape" && isMobileLayout()) {
    event.preventDefault();
    setMobileSearchOpen(false);
  }
});

if (els.themeSelect) {
  els.themeSelect.addEventListener("change", (event) => {
    setTheme(event.target.value);
  });
}

els.searchResults.addEventListener("click", (event) => {
  const result = event.target.closest(".show-result");
  if (!result) {
    return;
  }
  openProgramDetails(result.dataset.channelKey, result.dataset.programIndex);
});

els.guide.addEventListener("click", (event) => {
  const removeButton = event.target.closest(".remove-channel-button");
  if (removeButton) {
    state.selectedChannelKeys = state.selectedChannelKeys.filter(
      (key) => key !== removeButton.dataset.channelKey,
    );
    saveSelection();
    render();
    return;
  }
  handleProgramBlockOpen(event);
});

els.guide.addEventListener("keydown", (event) => {
  if (event.key !== "Enter" && event.key !== " ") {
    return;
  }
  const programBlock = event.target.closest(".program-block");
  if (!programBlock) {
    return;
  }
  event.preventDefault();
  openProgramDetails(
    programBlock.dataset.channelKey,
    programBlock.dataset.programIndex,
  );
});

els.programDialog.addEventListener("click", (event) => {
  if (event.target === els.programDialog) {
    els.programDialog.close();
  }
});

window.addEventListener("resize", () => setMobileView(state.mobileView));

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

setTheme(loadTheme());
start();
