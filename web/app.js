const MAX_SELECTIONS = 10;
const VISIBLE_HOURS = 9;
const PIXELS_PER_MINUTE = 2;
const SLOT_MINUTES = 30;
const TIMELINE_LOOKBACK_MINUTES = 60;
const SPORTS_NOW_UPCOMING_MINUTES = 60;
const THEME_VERSION = "quiet-guide-default-v1";
const DEFAULT_THEME = "quiet-guide";
const THEMES = {
  default: `quiet-guide-theme.css?v=${THEME_VERSION}`,
  "classic-v1": `sense-theme.css?v=${THEME_VERSION}`,
  sense: `sense-theme.css?v=${THEME_VERSION}`,
  "soft-studio": "soft-studio-theme.css?v=applied-1",
  "open-air": "open-air-theme.css?v=applied-1",
  "quiet-guide": "quiet-guide-theme.css?v=applied-1",
};

const state = {
  countries: [],
  generatedAt: null,
  countryDataByCode: new Map(),
  editorPicks: [],
  selectedChannelKeys: loadSelection(),
  search: "",
  now: new Date(),
  mobileView: "guide",
  searchOpen: false,
  liveSportsOpen: false,
  editorPicksOpen: true,
  expandedCountries: new Set(),
  selectedSportFilter: null,
};

const els = {
  status: document.querySelector("#status"),
  countryFlags: document.querySelector("#country-flags"),
  liveSportsToggle: document.querySelector("#live-sports-toggle"),
  editorPicksToggle: document.querySelector("#editor-picks-toggle"),
  channelSearch: document.querySelector("#channel-search"),
  channelList: document.querySelector("#channel-list"),
  channelPicker: document.querySelector("#channel-picker"),
  channelsView: document.querySelector("#channels-view"),
  searchResults: document.querySelector("#search-results"),
  guide: document.querySelector("#guide"),
  guideTitle: document.querySelector("#guide-title"),
  sportFilters: document.querySelector("#sport-filters"),
  dataUpdated: document.querySelector("#data-updated"),
  editorPicks: document.querySelector("#editor-picks"),
  editorPicksList: document.querySelector("#editor-picks-list"),
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
  const preview = new URLSearchParams(window.location.search).get("theme");
  if (Object.hasOwn(THEMES, preview)) return preview;
  const migratedToCurrentDefault =
    localStorage.getItem("whatsontv.themeDefault") === THEME_VERSION;
  const saved = localStorage.getItem("whatsontv.theme");
  if (!migratedToCurrentDefault) {
    return DEFAULT_THEME;
  }
  return Object.hasOwn(THEMES, saved) ? saved : DEFAULT_THEME;
}

function setTheme(themeName) {
  // Preserve old theme URLs while exposing the new names.
  const canonicalName = themeName === "default" ? DEFAULT_THEME
    : themeName === "sense" ? "classic-v1" : themeName;
  const theme = Object.hasOwn(THEMES, canonicalName) ? canonicalName : DEFAULT_THEME;
  els.themeLink.href = THEMES[theme];
  if (els.themeSelect) {
    els.themeSelect.value = theme;
  }
  document.documentElement.dataset.theme = theme;
  // URL previews never replace the user's saved theme or migration marker.
  if (!new URLSearchParams(window.location.search).has("theme")) {
    localStorage.setItem("whatsontv.theme", theme);
    localStorage.setItem("whatsontv.themeDefault", THEME_VERSION);
  }
}

function isPreviewTheme() {
  return ["soft-studio", "open-air", "quiet-guide"].includes(document.documentElement.dataset.theme);
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
  const date = new Date(value);
  return new Intl.DateTimeFormat(undefined, {
    ...(date.toDateString() !== state.now.toDateString() ? { month: "short", day: "numeric" } : {}),
    hour: "numeric",
    minute: "2-digit",
  }).format(date);
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

function startsWithinNextHour(program) {
  const now = state.now.getTime();
  const start = new Date(program.startAt).getTime();
  return start > now && start <= now + SPORTS_NOW_UPCOMING_MINUTES * 60000;
}

function isCurrentOrStartingSoon(program) {
  return isCurrent(program) || startsWithinNextHour(program);
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
  const [data, picks] = await Promise.all([
    loadJson("data/countries.json"),
    loadJson("data/editors-picks.json").catch(() => ({ picks: [] })),
  ]);
  state.countries = data.countries;
  state.generatedAt = data.generatedAt;
  state.editorPicks = Array.isArray(picks.picks)
    ? picks.picks.filter((pick) => pick && typeof pick.country === "string" && typeof pick.title === "string" && typeof pick.startAt === "string")
    : [];
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
  const eventFeedPrograms = programs.filter(isMlsAppleProgram);
  const dedupeCandidates = programs.filter((program) => !isMlsAppleProgram(program));
  const slots = new Map();
  for (const program of dedupeCandidates) {
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
  return [...deduped, ...eventFeedPrograms].sort((a, b) => a.startAt.localeCompare(b.startAt));
}

function isMlsAppleProgram(program) {
  const categories = new Set((program.categories || []).map((category) => String(category).toLowerCase()));
  return categories.has("mls") && categories.has("apple tv");
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

function normalizeSearchText(value) {
  return String(value || "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase();
}

function countryMatchesSearch(countryData, query) {
  return (
    normalizeSearchText(countryData.countryName).includes(query) ||
    normalizeSearchText(countryData.country).includes(query)
  );
}

function channelMatchesSearch(countryData, channel, query) {
  if (!query) {
    return true;
  }
  return (
    countryMatchesSearch(countryData, query) ||
    normalizeSearchText(channel.name).includes(query) ||
    normalizeSearchText(channel.provider).includes(query) ||
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
    .join(" ");
  return normalizeSearchText(haystack).includes(query);
}


const SPORT_BUCKETS = [
  {
    id: "major-events",
    label: "Major event",
    emoji: "🏅",
    terms: ["olympic", "olympics", "world cup", "commonwealth games", "pan american games"],
  },
  {
    id: "american-football",
    label: "American football",
    emoji: "🏈",
    terms: ["american football", "national football league", "arena football", "nfl", "ufl", "college football", "ncaa football", "ncaaf", "cfl"],
  },
  {
    id: "australian-football",
    label: "Australian football",
    emoji: "🏉",
    terms: ["australian football", "australian rules", "afl"],
  },
  {
    id: "cricket",
    label: "Cricket",
    emoji: "🏏",
    terms: ["cricket", "t20"],
  },
  {
    id: "combat-sports",
    label: "Combat sports",
    emoji: "🥊",
    terms: ["combat sports", "boxing", "mma", "ufc"],
  },
  {
    id: "soccer",
    label: "Soccer",
    emoji: "⚽",
    terms: ["soccer", "football", "fifa", "uefa", "champions league", "premier league", "la liga", "ligue 1", "serie a", "bundesliga", "copa libertadores", "mls"],
  },
  {
    id: "hockey",
    label: "Hockey",
    emoji: "🏒",
    terms: ["hockey", "nhl", "ice hockey", "iihf"],
  },
  {
    id: "basketball",
    label: "Basketball",
    emoji: "🏀",
    terms: ["basketball", "nba", "wnba", "euroleague", "lecb"],
  },
  {
    id: "baseball",
    label: "Baseball",
    emoji: "⚾",
    terms: ["baseball", "mlb"],
  },
  {
    id: "tennis",
    label: "Tennis",
    emoji: "🎾",
    terms: ["tennis", "atp", "wta", "roland garros", "wimbledon", "us open", "australian open"],
  },
  {
    id: "golf",
    label: "Golf",
    emoji: "⛳",
    terms: ["golf", "pga", "lpga", "masters", "ryder cup"],
  },
];

const SPORTS_CATEGORY_TERMS = new Set([
  "sport",
  "sports",
  "soccer",
  "football",
  "american football",
  "hockey",
  "basketball",
  "baseball",
  "tennis",
  "golf",
  "extreme",
  "motorsports",
  "watersports",
  "boxing",
  "mma",
  "rugby",
  "cricket",
  "cycling",
]);

const EMPTY_EVENT_LABEL_PATTERNS = [
  /^(no|not any)\s+(live\s+|upcoming\s+)?(event|events|game|games|match|matches|program|programs|programme|programmes)(\s+(scheduled|available|found|today|now|in programma))?$/,
  /^nothing\s+(scheduled|available|on|live)$/,
  /^no\s+hay\s+eventos?$/,
  /^sin\s+eventos?$/,
  /^nessun\s+event[io](\s+in\s+(programma|onda))?$/,
  /^nessuna\s+(partita|programmazione)$/,
  /^aucun\s+evenement$/,
  /^aucun\s+match$/,
  /^keine\s+(veranstaltung|veranstaltungen|ereignisse|spiele)$/,
  /^geen\s+(evenement|evenementen|wedstrijd|wedstrijden)$/,
  /^sem\s+eventos?$/,
  /^nenhum\s+evento$/,
];

const NON_SPORT_CATEGORY_TERMS = new Set([
  "sitcom",
  "comedy",
  "drama",
  "movie",
  "movies",
  "film",
  "documentary",
  "news",
  "children",
  "kids",
  "reality",
  "talk",
  "entertainment",
]);

function normalizedProgramParts(program) {
  const categories = program.categories || [];
  return {
    strong: normalizeSearchText([
      program.sportType,
      program.competition,
      ...categories,
    ].filter(Boolean).join(" ")),
    all: normalizeSearchText([
      program.title,
      program.subtitle,
      program.description,
      program.sportType,
      program.competition,
      ...categories,
    ].filter(Boolean).join(" ")),
    categories: categories.map((category) => normalizeSearchText(category)),
  };
}

function includesTerm(haystack, term) {
  const normalized = normalizeSearchText(term).replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  return new RegExp(`(^|[^a-z0-9])${normalized}([^a-z0-9]|$)`).test(haystack);
}

function hasSportsCategory(categories) {
  return categories.some((category) => SPORTS_CATEGORY_TERMS.has(category));
}

function hasNonSportCategory(categories) {
  return categories.some((category) => NON_SPORT_CATEGORY_TERMS.has(category));
}

function isEmptyEventPlaceholder(program) {
  const labels = [program.title, program.subtitle]
    .map((value) => normalizeSearchText(value).trim())
    .filter(Boolean);
  return labels.some((label) => EMPTY_EVENT_LABEL_PATTERNS.some((pattern) => pattern.test(label)));
}

function genericSportsBucket() {
  return {
    id: "other-sports",
    label: "Sports",
    emoji: "🏟️",
    terms: [],
  };
}

function detectSportBucket(program) {
  if (isEmptyEventPlaceholder(program)) {
    return null;
  }

  const parts = normalizedProgramParts(program);
  const sportsCategory = hasSportsCategory(parts.categories);
  const nonSportCategory = hasNonSportCategory(parts.categories);

  if (includesTerm(parts.all, "rugby")) {
    return genericSportsBucket();
  }

  // Specific football codes beat generic Football metadata from guide providers.
  for (const bucket of SPORT_BUCKETS.filter((bucket) => ["american-football", "australian-football"].includes(bucket.id))) {
    if ((!nonSportCategory || sportsCategory) && bucket.terms.some((term) => includesTerm(parts.all, term))) {
      return bucket;
    }
  }

  for (const bucket of SPORT_BUCKETS) {
    if (bucket.terms.some((term) => includesTerm(parts.strong, term))) {
      if (!nonSportCategory || sportsCategory) {
        return bucket;
      }
    }
  }

  for (const bucket of SPORT_BUCKETS) {
    if (bucket.terms.some((term) => includesTerm(parts.all, term))) {
      if (sportsCategory || !nonSportCategory) {
        return bucket;
      }
    }
  }

  if (sportsCategory && (program.sportType || program.competition)) {
    return {
      id: "other-sports",
      label: program.sportType || "Sports",
      emoji: "🏟️",
      terms: [],
    };
  }

  return null;
}

function isLiveSportsProgram(program) {
  if (!isCurrentOrStartingSoon(program)) {
    return false;
  }
  return Boolean(detectSportBucket(program));
}

function currentLiveSportsResults(limit = Infinity) {
  const results = [];
  const seen = new Set();
  for (const country of state.countries) {
    const countryData = state.countryDataByCode.get(country.code);
    if (!countryData) {
      continue;
    }
    for (const channel of countryData.channels) {
      const key = channelKey(countryData.country, channel.id);
      (channel.programs || []).forEach((program, index) => {
        const sport = detectSportBucket(program);
        if (!sport || !isCurrentOrStartingSoon(program)) {
          return;
        }
        const duplicateKey = [countryData.country, channel.id, program.title, program.startAt, program.endAt].join("|");
        if (seen.has(duplicateKey)) {
          return;
        }
        seen.add(duplicateKey);
        results.push({
          channel,
          countryData,
          key,
          program,
          index,
          sport,
          current: isCurrent(program),
        });
      });
    }
  }
  return results
    .sort((a, b) =>
      a.program.startAt.localeCompare(b.program.startAt) ||
      a.countryData.country.localeCompare(b.countryData.country) ||
      a.channel.name.localeCompare(b.channel.name) ||
      a.program.title.localeCompare(b.program.title),
    )
    .slice(0, limit);
}


function sportsEventText(value) {
  return normalizeSearchText(value)
    .replace(/^live\s*[:–-]?\s+/, "")
    .replace(/\b(vs?\.?|versus)\b/g, " ")
    .replace(/[^\p{L}\p{N}]+/gu, " ")
    .trim();
}

function groupLiveSportsResults(results) {
  const groups = [];
  for (const result of results) {
    const title = sportsEventText(result.program.title);
    const subtitle = sportsEventText(result.program.subtitle);
    // Generic sport labels alone cannot identify a shared event.
    const specific = title.split(" ").length > 1 && title !== sportsEventText(result.sport.label);
    const group = specific && groups.find((candidate) =>
      candidate.sport.id === result.sport.id &&
      sportsEventText(candidate.program.title) === title &&
      candidate.airings.every((airing) => {
        const otherSubtitle = sportsEventText(airing.program.subtitle);
        const competition = sportsEventText(result.program.competition);
        const otherCompetition = sportsEventText(airing.program.competition);
        return (!subtitle || !otherSubtitle || subtitle === otherSubtitle) &&
          (!competition || !otherCompetition || competition === otherCompetition) &&
          Math.abs(new Date(airing.program.startAt) - new Date(result.program.startAt)) <= 90 * 60000 &&
          isOverlappingDuplicate(airing.program, result.program);
      })
    );
    if (group) {
      if (!group.airings.some((airing) => airing.key === result.key && airing.index === result.index)) {
        group.airings.push(result);
      }
    } else {
      groups.push({ ...result, airings: [result] });
    }
  }
  return groups;
}

function availableSportFilters(results) {
  const filters = [];
  const seen = new Set();
  for (const result of results) {
    if (seen.has(result.sport.id)) {
      continue;
    }
    seen.add(result.sport.id);
    filters.push(result.sport);
  }
  return filters;
}

function visibleLiveSportsResults(results) {
  return results.filter((result) => !state.selectedSportFilter || result.sport.id === state.selectedSportFilter);
}

function renderSportFilters(filters) {
  if (!filters.length) {
    return "";
  }
  return `
    <div class="sport-filter-bar" aria-label="Filter sports">
      ${filters
        .map((sport) => {
          const selected = state.selectedSportFilter === sport.id;
          const enabled = !state.selectedSportFilter || selected;
          const action = selected ? "Show all sports" : `Show only ${sport.label}`;
          return `
            <button class="sport-filter-button ${enabled ? "enabled" : ""}" type="button" data-sport-filter="${escapeHtml(sport.id)}" aria-pressed="${selected}" title="${escapeHtml(action)}" aria-label="${escapeHtml(action)}">
              <span aria-hidden="true">${sport.emoji}</span>
            </button>
          `;
        })
        .join("")}
    </div>
  `;
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
  if (state.liveSportsOpen) {
    renderLiveSportsResults();
    return;
  }

  const query = normalizeSearchText(state.search.trim());
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

function renderConcurrentEvents(events, renderEvent, emptyMessage) {
  const byStart = new Map();
  for (const event of events) {
    // Match the minute shown in the UI, including equivalent time zones.
    const minute = Math.floor(new Date(event.program.startAt).getTime() / 60000);
    if (!byStart.has(minute)) byStart.set(minute, []);
    byStart.get(minute).push(event);
  }
  const groups = [...byStart.entries()].sort(([a], [b]) => a - b);
  return renderTimedEvents(groups, ([minute]) => minute * 60000,
    ([minute, simultaneous]) => `<section class="event-time-slot">
      <h3 class="event-time-heading"><time datetime="${new Date(minute * 60000).toISOString()}">${formatTime(new Date(minute * 60000))}</time><span class="event-time-sports" aria-hidden="true">${[...new Set(simultaneous.map((event) => event.sport?.emoji).filter(Boolean))].map(escapeHtml).join(" ")}</span></h3>
      <div class="event-time-group">${simultaneous.map(renderEvent).join("")}</div>
    </section>`,
    emptyMessage);
}

function onTodayChannelAirings(airings) {
  const counts = new Map();
  const seen = new Set();
  return airings.filter((airing) => {
    const country = airing.countryData.country;
    const count = counts.get(country) || 0;
    if (count >= 3 || seen.has(airing.key)) return false;
    counts.set(country, count + 1);
    seen.add(airing.key);
    return true;
  });
}

function renderLiveSportsResults() {
  const allResults = groupLiveSportsResults(currentLiveSportsResults());
  const filters = availableSportFilters(allResults);
  const results = visibleLiveSportsResults(allResults);
  els.sportFilters.innerHTML = renderSportFilters(filters);
  els.sportFilters.hidden = false;
  els.searchResults.hidden = false;
  els.searchResults.innerHTML = `
    <div class="show-results-list live-sports-list">
      ${renderConcurrentEvents(results,
            ({ program, sport, airings }) => `
              <article class="editor-pick-result">
                <div class="editor-pick-heading">
                  <button class="show-result-title event-title" type="button" data-channel-key="${escapeHtml(airings[0].key)}" data-program-index="${airings[0].index}"><span class="event-sport-icon" aria-hidden="true">${sport.emoji}</span> ${escapeHtml(program.title)}</button>
                </div>
                <div class="editor-pick-channels" aria-label="Available channels">
                  ${onTodayChannelAirings(airings).map(({ channel, countryData, key, index, program: airing }) => `
                    <button class="editor-pick-channel" type="button" data-channel-key="${escapeHtml(key)}" data-program-index="${index}" title="Open ${escapeHtml(channel.name)} · ${formatTime(airing.startAt)} – ${formatTime(airing.endAt)}">
                      <span aria-hidden="true">${flagEmoji(countryData.country)}</span> ${escapeHtml(channel.name)}
                    </button>
                  `).join("")}
                </div>
              </article>
            `,
        "No sports match the active filters.")}
    </div>
  `;
}

function resolvedEditorPicks() {
  return state.editorPicks.filter((pick) => pick.highlightType === "liveSport" && editorPickLeagueRank(pick) >= 0).map((pick) => {
    const airings = (Array.isArray(pick.channels) ? pick.channels : [pick])
      .map((airing) => {
        const countryData = state.countryDataByCode.get(airing.country);
        const channelId = countryData?.duplicateChannelAliases?.[airing.channelId] || airing.channelId;
        const channel = countryData?.channels.find((item) => item.id === channelId)
          || countryData?.channels.find((item) => item.name === airing.channelName);
        const exactIndex = channel?.programs.findIndex((program) =>
          program.title === (airing.sourceTitle || pick.title) && program.startAt === airing.startAt
        );
        const matchingSlots = channel?.programs
          .map((program, index) => ({ program, index }))
          .filter(({ program }) =>
            (program.startAt === airing.startAt && program.endAt === airing.endAt)
            || isOverlappingDuplicate(program, airing)
          ) || [];
        const index = exactIndex >= 0 ? exactIndex : matchingSlots.length === 1 ? matchingSlots[0].index : -1;
        return countryData && channel && index >= 0
          && new Date(channel.programs[index].endAt).getTime() > state.now.getTime()
          ? { countryData, channel, index, key: channelKey(airing.country, channel.id) }
          : null;
      }).filter(Boolean).filter((airing, index, all) =>
        all.findIndex((item) => item.key === airing.key) === index
      );
    const countries = new Map();
    const limited = airings.filter(({ countryData }) => {
      const count = (countries.get(countryData.country) || 0) + 1;
      countries.set(countryData.country, count);
      return count <= 3;
    });
    return limited.length ? { pick, airings: limited } : null;
  }).filter(Boolean).sort((a, b) => editorPickLeagueRank(a.pick) - editorPickLeagueRank(b.pick)
    || new Date(a.pick.startAt) - new Date(b.pick.startAt));
}

function editorPickLeagueRank(pick) {
  const text = [pick.title, pick.subtitle, pick.competition, pick.description].filter(Boolean).join(" ")
    .normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase().replace(/[^a-z0-9]+/g, " ");
  if (/\b(?:2\s*bundesliga|bundesliga\s*2|ligue\s*2|serie\s*b|la\s*liga\s*2|segunda\s*(?:division|divisao|liga)|liga\s*(?:portugal\s*)?2|(?:la\s*)?liga\s*hypermotion|(?:efl|sky\s*bet|english)\s*championship|tff\s*1|1\s*lig|eerste\s*divisie|challenger\s*pro\s*league|usl\s*championship|second\s*(?:tier|division))\b/.test(text)) return -1;
  const heading = [pick.title, pick.subtitle].filter(Boolean).join(" ").toLowerCase();
  if (/cricket|\bt20\b/i.test([heading, pick.sportType, ...(pick.categories || [])].join(" "))) return 5;
  const rank = [/\bpremier league\b/, /\bla\s*liga\b/, /\bserie a\b/, /\bligue 1\b/, /\bbundesliga\b/].findIndex(pattern => pattern.test(heading));
  return rank < 0 ? 5 : rank;
}

function editorPickChannel({ countryData, channel, index, key }) {
  return `<button class="editor-pick-channel" type="button" data-channel-key="${escapeHtml(key)}" data-program-index="${index}" title="Open ${escapeHtml(channel.name)}">
    <span aria-hidden="true">${flagEmoji(countryData.country)}</span> ${escapeHtml(channel.name)}
  </button>`;
}

function renderTimedEvents(events, startAt, renderEvent, emptyMessage) {
  const marker = `<div class="event-now-indicator"><time datetime="${state.now.toISOString()}">Now · ${formatTime(state.now)}</time></div>`;
  if (!events.length) {
    return marker + `<p class="empty-program">${escapeHtml(emptyMessage)}</p>`;
  }
  // Preserve editorial ranking within each side of the current-time marker.
  const started = [];
  const upcoming = [];
  for (const event of events) {
    (new Date(startAt(event)) > state.now ? upcoming : started).push(event);
  }
  return started.map(renderEvent).join("") + marker + upcoming.map(renderEvent).join("");
}

function renderEditorPicks() {
  const picks = resolvedEditorPicks();
  els.editorPicks.hidden = false;
  els.editorPicksList.innerHTML = renderTimedEvents(picks, ({ pick }) => pick.startAt, ({ pick, airings }) => `
    <article class="editor-pick-result">
      <div class="editor-pick-heading">
        <span class="show-result-time">${formatTime(pick.startAt)}</span>
        <span class="editor-pick-sport" aria-hidden="true">${(detectSportBucket(pick) || genericSportsBucket()).emoji}</span>
        <button class="show-result-title event-title" type="button" data-channel-key="${escapeHtml(airings[0].key)}" data-program-index="${airings[0].index}">${escapeHtml(pick.title)}</button>
      </div>
      <div class="editor-pick-channels" aria-label="Available channels">
        ${airings.slice(0, 6).map(editorPickChannel).join("")}
        ${airings.length > 6 ? `<details class="editor-pick-more"><summary aria-label="More channels for ${escapeHtml(pick.title)}">more</summary>
          <div class="editor-pick-channels">${airings.slice(6).map(editorPickChannel).join("")}</div>
        </details>` : ""}
      </div>
    </article>
  `, "No upcoming editor’s picks in the current data.");
}

function setLiveSportsOpen(open) {
  state.liveSportsOpen = open;
  if (open) {
    state.editorPicksOpen = false;
    state.search = "";
    els.channelSearch.value = "";
    setMobileSearchOpen(false);
    if (isMobileLayout()) {
      setMobileView("guide");
    }
  }
  document.body.dataset.liveSportsOpen = String(open);
  document.body.dataset.guideEmpty = String(selectedChannels().length === 0);
  els.liveSportsToggle?.setAttribute("aria-pressed", String(open));
  renderCountryFlags();
  renderChannelList();
  renderSearchResults();
  renderGuide();
}

function renderChannelList() {
  // Country disclosures use native keyboard and screen-reader behavior.
  // Expansion is independent of channel selection and survives rerenders.
  const selected = selectedSet();
  const query = normalizeSearchText(state.search.trim());

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

      if (isPreviewTheme()) {
        return `
          <details class="country-group" name="countries" data-country-code="${escapeHtml(countryData.country)}"${state.expandedCountries.has(countryData.country) ? " open" : ""}>
            <summary><span class="country-flag-pill" aria-hidden="true">${flagEmoji(countryData.country)}</span> ${escapeHtml(countryData.countryName)}</summary>
            <div class="country-channels">${choices}</div>
          </details>`;
      }
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
  const query = normalizeSearchText(state.search.trim());
  if (query || isPreviewTheme()) {
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

function layoutProgramColumns(programEntries) {
  const entries = programEntries.map((entry) => ({ ...entry, laneIndex: 0, laneCount: 1 }));
  const active = [];
  for (const entry of entries) {
    const start = new Date(entry.program.startAt).getTime();
    const end = new Date(entry.program.endAt).getTime();
    for (let index = active.length - 1; index >= 0; index -= 1) {
      if (active[index].end <= start) {
        active.splice(index, 1);
      }
    }
    const usedLanes = new Set(active.map((item) => item.entry.laneIndex));
    let laneIndex = 0;
    while (usedLanes.has(laneIndex)) {
      laneIndex += 1;
    }
    entry.laneIndex = laneIndex;
    active.push({ entry, end });
    const laneCount = Math.max(...active.map((item) => item.entry.laneIndex)) + 1;
    for (const item of active) {
      item.entry.laneCount = Math.max(item.entry.laneCount, laneCount);
    }
  }
  return entries;
}

function programmeBlock(program, start, end, channelKeyValue, programIndex, laneIndex = 0, laneCount = 1) {
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

  const laneGap = 0.16;
  const laneWidth = laneCount > 1 ? 100 / laneCount : 100;
  const laneLeft = laneIndex * laneWidth;
  const laneStyle =
    laneCount > 1
      ? `left: calc(${laneLeft}% + 0.25rem); right: auto; width: calc(${laneWidth}% - ${laneGap + 0.5}rem);`
      : "";

  return `
    <article class="program-block ${current ? "current" : ""}" role="button" tabindex="0" data-channel-key="${escapeHtml(channelKeyValue)}" data-program-index="${programIndex}" aria-label="Show details for ${escapeHtml(program.title)}" style="top: ${top}px; height: ${height}px; ${laneStyle}">
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
  document.body.dataset.guideEmpty = String(!channels.length);
  document.body.dataset.editorPicksOpen = String(state.editorPicksOpen);
  els.editorPicksToggle?.setAttribute("aria-pressed", String(state.editorPicksOpen && !state.liveSportsOpen && !state.search.trim()));

  els.guideTitle.textContent = state.search.trim() ? "Search Results"
    : state.liveSportsOpen ? "On Today"
    : state.editorPicksOpen ? "Today's Editors Picks in Sports" : "Channels";
  els.sportFilters.hidden = !state.liveSportsOpen;
  els.dataUpdated.textContent = `Data last updated ${formatRelativeTime(state.generatedAt)}`;

  const picksWereInGuide = els.guide.contains(els.editorPicks);
  if (state.editorPicksOpen) {
    const scrollTop = els.guide.querySelector(".empty-state")?.scrollTop || 0;
    els.guide.innerHTML = '<div class="empty-state"></div>';
    els.guide.querySelector(".empty-state").append(els.editorPicks);
    els.guide.querySelector(".empty-state").scrollTop = scrollTop;
    return;
  }

  if (picksWereInGuide) {
    els.guide.parentElement.prepend(els.editorPicks);
  }
  if (!channels.length) {
    els.guide.innerHTML = '<div class="empty-state"><p>Choose a channel from the sidebar to see its schedule.</p></div>';
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
          <div class="guide-channel-logo" aria-hidden="true">
            ${channel.logoUrl ? `<img class="logo" src="${escapeHtml(channel.logoUrl)}" alt="" loading="lazy" />` : ""}
          </div>
          <div class="guide-channel-label">
            <span class="guide-channel-flag" aria-hidden="true">${flagEmoji(channel.countryCode)}</span>
            <div class="guide-channel-name">${escapeHtml(channel.name)}</div>
            <button class="remove-channel-button" type="button" data-channel-key="${escapeHtml(channel.key)}" aria-label="Remove ${escapeHtml(channel.name)} from guide">×</button>
          </div>
        </div>
      `,
    )
    .join("");

  const columns = channels
    .map((channel) => {
      const programs = layoutProgramColumns(overlappingPrograms(channel, start, end));
      return `
        <div class="schedule-column" style="height: ${totalHeight}px">
          ${programs.length ? programs.map(({ program, index, laneIndex, laneCount }) => programmeBlock(program, start, end, channel.key, index, laneIndex, laneCount)).join("") : `<div class="empty-program">No program in this window</div>`}
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
  document.body.dataset.guideEmpty = String(selectedChannels().length === 0);
  renderCountryFlags();
  renderChannelList();
  renderEditorPicks();
  renderSearchResults();
  renderGuide();
  setMobileView(state.mobileView);
  setMobileSearchOpen(state.searchOpen);
  document.body.dataset.liveSportsOpen = String(state.liveSportsOpen);
  els.liveSportsToggle?.setAttribute("aria-pressed", String(state.liveSportsOpen));
  if (els.clearSelection) {
    els.clearSelection.hidden = state.selectedChannelKeys.length === 0;
  }
}

els.channelSearch.addEventListener("input", (event) => {
  state.editorPicksOpen = false;
  state.liveSportsOpen = false;
  document.body.dataset.liveSportsOpen = "false";
  els.liveSportsToggle?.setAttribute("aria-pressed", "false");
  state.search = event.target.value;
  document.body.dataset.searching = String(Boolean(state.search.trim()));
  renderCountryFlags();
  renderChannelList();
  renderSearchResults();
  renderGuide();
});

els.liveSportsToggle?.addEventListener("click", () => {
  setLiveSportsOpen(true);
});

els.editorPicksToggle?.addEventListener("click", () => {
  state.editorPicksOpen = true;
  state.search = "";
  els.channelSearch.value = "";
  setMobileSearchOpen(false);
  setLiveSportsOpen(false);
  setMobileView("guide");
  render();
});

els.channelList.addEventListener("toggle", (event) => {
  const group = event.target;
  if (!group.matches("details.country-group") || !group.isConnected) return;
  if (group.open) {
    state.expandedCountries.clear();
    state.expandedCountries.add(group.dataset.countryCode);
    for (const other of els.channelList.querySelectorAll("details.country-group[open]")) {
      if (other !== group) other.open = false;
    }
  } else {
    state.expandedCountries.delete(group.dataset.countryCode);
  }
}, true);

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

function activateChannelView() {
  state.editorPicksOpen = false;
  state.liveSportsOpen = false;
  state.search = "";
  els.channelSearch.value = "";
  setMobileSearchOpen(false);
  setMobileView("guide");
}

els.channelsView.addEventListener("click", () => {
  activateChannelView();
  render();
});

function showChannel(key) {
  if (!getChannelByKey(key)) return;
  if (!state.selectedChannelKeys.includes(key)) {
    state.selectedChannelKeys = [...state.selectedChannelKeys.slice(0, MAX_SELECTIONS - 1), key];
    saveSelection();
  }
  activateChannelView();
  render();
}

els.channelList.addEventListener("click", (event) => {
  const choice = event.target.closest(".channel-choice");
  if (!choice || choice.disabled) {
    return;
  }

  const key = choice.dataset.channelKey;
  const switchingView = state.editorPicksOpen || state.liveSportsOpen || Boolean(state.search.trim());
  const selected = selectedSet();
  const isSelected = selected.has(key);

  if (!isSelected && state.selectedChannelKeys.length >= MAX_SELECTIONS) {
    return;
  }

  if (isSelected && !switchingView) {
    selected.delete(key);
  } else {
    selected.add(key);
  }

  activateChannelView();
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

document.addEventListener("click", (event) => {
  if (
    isMobileLayout() && state.mobileView === "picker" &&
    !els.channelPicker.contains(event.target) &&
    !event.target.closest('a, button, input, select, textarea, label, summary, dialog, [role="button"], [contenteditable="true"]')
  ) {
    setMobileView("guide");
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
    setLiveSportsOpen(false);
    setMobileSearchOpen(false);
  }
});

if (els.themeSelect) {
  els.themeSelect.addEventListener("change", (event) => {
    setTheme(event.target.value);
  });
}

els.sportFilters.addEventListener("click", (event) => {
  const filterButton = event.target.closest("[data-sport-filter]");
  if (filterButton) {
    const sportId = filterButton.dataset.sportFilter;
    state.selectedSportFilter = state.selectedSportFilter === sportId ? null : sportId;
    renderLiveSportsResults();
  }
});

els.searchResults.addEventListener("click", (event) => {
  const result = event.target.closest(".show-result, .editor-pick-channel, .event-title");
  if (!result) {
    return;
  }
  if (result.matches(".editor-pick-channel")) {
    showChannel(result.dataset.channelKey);
  } else {
    openProgramDetails(result.dataset.channelKey, result.dataset.programIndex);
  }
});

els.editorPicksList.addEventListener("click", (event) => {
  const title = event.target.closest(".event-title");
  if (title) {
    openProgramDetails(title.dataset.channelKey, title.dataset.programIndex);
    return;
  }
  const result = event.target.closest(".editor-pick-channel");
  if (result) {
    showChannel(result.dataset.channelKey);
  }
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
      renderEditorPicks();
      if (state.liveSportsOpen) {
        renderLiveSportsResults();
      }
    }, 60000);
  } catch (error) {
    els.status.textContent = error.message;
    els.guide.innerHTML = `<div class="empty-state">Could not load guide data. Run <code>python3 scripts/build_web_data.py</code>, then serve the web directory.</div>`;
  }
}

setTheme(loadTheme());
start();
