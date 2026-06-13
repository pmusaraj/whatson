const state = {
  validation: null,
  preview: null,
  channels: [],
  selectedId: null,
  query: '',
  severity: 'all',
};

const els = {
  status: document.querySelector('#status'),
  summary: document.querySelector('#summary'),
  search: document.querySelector('#search'),
  severity: document.querySelector('#severity-filter'),
  list: document.querySelector('#channel-list'),
  detail: document.querySelector('#channel-detail'),
};

function escapeHtml(value) {
  return String(value ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function formatDate(value) {
  if (!value) return '—';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString([], { dateStyle: 'medium', timeStyle: 'short' });
}

function formatUtc(value) {
  if (!value) return '—';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toISOString().replace('.000Z', 'Z');
}

function relativeAge(value) {
  if (!value) return 'unknown age';
  const then = new Date(value).getTime();
  if (Number.isNaN(then)) return 'unknown age';
  const minutes = Math.max(0, Math.round((Date.now() - then) / 60000));
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 48) return `${hours}h ago`;
  return `${Math.round(hours / 24)}d ago`;
}

async function loadJson(url) {
  const response = await fetch(url, { cache: 'no-cache' });
  if (!response.ok) throw new Error(`${url}: HTTP ${response.status}`);
  return response.json();
}

function mergeData(validation, preview) {
  const validationByChannel = new Map((validation.channels || []).map((channel) => [channel.id, channel]));
  const findingsByChannel = new Map();
  for (const finding of validation.findings || []) {
    if (!finding.channelId) continue;
    if (!findingsByChannel.has(finding.channelId)) findingsByChannel.set(finding.channelId, []);
    findingsByChannel.get(finding.channelId).push(finding);
  }
  return (preview.channels || []).map((channel) => {
    const validationChannel = validationByChannel.get(channel.id) || {};
    const findings = findingsByChannel.get(channel.id) || [];
    return {
      ...channel,
      ...validationChannel,
      displayNames: channel.displayNames || validationChannel.displayNames || [],
      programs: channel.programs || [],
      findings,
      errorCount: validationChannel.errorCount || findings.filter((item) => item.severity === 'error').length,
      warningCount: validationChannel.warningCount || findings.filter((item) => item.severity === 'warning').length,
    };
  });
}

function renderSummary() {
  const counts = state.validation.counts || {};
  const coverage = state.validation.coverage || {};
  const cards = [
    ['Channels', counts.channels, 'total UHF XMLTV channels', ''],
    ['Programmes', counts.programmes, 'total programme entries', ''],
    ['Current', counts.channelsWithCurrent, 'channels with current programme', counts.channelsWithCurrent === counts.channels ? 'ok' : 'warning'],
    ['Next 24h', counts.channelsWithNext24h, 'channels with upcoming data', counts.channelsWithNext24h === counts.channels ? 'ok' : 'warning'],
    ['Errors', counts.errors, 'structural validation issues', counts.errors ? 'error' : 'ok'],
    ['Warnings', counts.warnings, 'coverage or quality findings', counts.warnings ? 'warning' : 'ok'],
  ];
  els.summary.innerHTML = cards.map(([label, value, hint, klass]) => `
    <div class="summary-card ${klass}">
      <strong>${escapeHtml(value ?? '—')}</strong>
      <span>${escapeHtml(label)} · ${escapeHtml(hint)}</span>
    </div>
  `).join('');
  els.status.textContent = `Generated ${relativeAge(state.validation.generatedAt)} · coverage ${formatDate(coverage.firstProgrammeStartAt)} → ${formatDate(coverage.lastProgrammeEndAt)}`;
}

function searchableText(channel) {
  return [
    channel.name,
    channel.id,
    channel.category,
    channel.targetCountry,
    channel.targetXmltvId,
    channel.targetName,
    channel.targetGuideSites,
    ...(channel.displayNames || []),
    ...(channel.programs || []).map((program) => program.title),
  ].filter(Boolean).join(' ').toLowerCase();
}

function filteredChannels() {
  const query = state.query.trim().toLowerCase();
  return state.channels.filter((channel) => {
    if (state.severity === 'errors' && !channel.errorCount) return false;
    if (state.severity === 'warnings' && channel.warningCount === 0) return false;
    if (state.severity === 'clean' && (channel.errorCount || channel.warningCount)) return false;
    if (query && !searchableText(channel).includes(query)) return false;
    return true;
  });
}

function renderList() {
  const channels = filteredChannels();
  if (!channels.length) {
    els.list.innerHTML = '<div class="empty">No channels match the current filters.</div>';
    els.detail.innerHTML = '<div class="empty">Select a channel to inspect its schedule.</div>';
    return;
  }
  if (!state.selectedId || !channels.some((channel) => channel.id === state.selectedId)) {
    state.selectedId = channels[0].id;
  }
  els.list.innerHTML = channels.map((channel) => {
    const current = channel.currentProgramTitle || 'No current programme';
    const badges = [
      channel.errorCount ? `<span class="badge error">${channel.errorCount} errors</span>` : '',
      channel.warningCount ? `<span class="badge warning">${channel.warningCount} warnings</span>` : '<span class="badge ok">clean</span>',
      `<span class="badge">${channel.programmeCount || channel.programs.length} programmes</span>`,
    ].join('');
    return `
      <button class="channel-row ${channel.id === state.selectedId ? 'active' : ''}" type="button" data-id="${escapeHtml(channel.id)}">
        <span class="channel-row-title">${escapeHtml(channel.name || channel.id)}</span>
        <span class="channel-row-meta">${escapeHtml(channel.id)} · ${escapeHtml(channel.targetXmltvId || 'no target')} · ${escapeHtml(channel.targetCountry || '—')}</span>
        <span class="channel-row-program">${escapeHtml(current)}</span>
        <span class="badges">${badges}</span>
      </button>
    `;
  }).join('');
  renderDetail();
}

function keyValueRows(channel) {
  const rows = [
    ['Custom XMLTV id', channel.id],
    ['Target XMLTV id', channel.targetXmltvId],
    ['Target name', channel.targetName],
    ['Country', channel.targetCountry],
    ['Category', channel.category],
    ['Guide sites', channel.targetGuideSites],
    ['Display names', (channel.displayNames || []).join(' · ')],
    ['First programme', formatUtc(channel.firstStartAt)],
    ['Last programme', formatUtc(channel.lastEndAt)],
    ['Current', channel.currentProgramTitle],
    ['Next', channel.nextProgramTitle],
  ];
  return `<dl class="kv">${rows.map(([key, value]) => `<dt>${escapeHtml(key)}</dt><dd>${escapeHtml(value || '—')}</dd>`).join('')}</dl>`;
}

function renderFindings(channel) {
  if (!channel.findings.length) return '<div class="finding"><strong>No channel-specific findings.</strong></div>';
  return channel.findings.map((finding) => `
    <div class="finding ${escapeHtml(finding.severity)}">
      <strong>${escapeHtml(finding.severity.toUpperCase())}</strong>
      <span class="finding-code">${escapeHtml(finding.code)}</span>
      <div>${escapeHtml(finding.message)}</div>
      ${finding.title ? `<div>Title: ${escapeHtml(finding.title)}</div>` : ''}
      ${finding.startAt ? `<div>Slot: ${escapeHtml(finding.startAt)} → ${escapeHtml(finding.endAt)}</div>` : ''}
    </div>
  `).join('');
}

function renderPrograms(channel) {
  if (!channel.programs.length) return '<div class="empty">No programmes in the preview window.</div>';
  return channel.programs.map((program) => `
    <article class="program-card">
      <h3>${escapeHtml(program.title || 'Untitled')}</h3>
      <div class="program-time">${escapeHtml(formatDate(program.startAt))} → ${escapeHtml(formatDate(program.endAt))} <span title="UTC">(${escapeHtml(formatUtc(program.startAt))} → ${escapeHtml(formatUtc(program.endAt))})</span></div>
      ${program.subtitle ? `<div>${escapeHtml(program.subtitle)}</div>` : ''}
      ${(program.categories || []).length ? `<div class="badges">${program.categories.map((category) => `<span class="badge">${escapeHtml(category)}</span>`).join('')}</div>` : ''}
      ${program.description ? `<p class="program-description">${escapeHtml(program.description)}</p>` : ''}
    </article>
  `).join('');
}

function renderDetail() {
  const channel = state.channels.find((item) => item.id === state.selectedId);
  if (!channel) {
    els.detail.innerHTML = '<div class="empty">Select a channel to inspect its schedule.</div>';
    return;
  }
  els.detail.innerHTML = `
    <div class="detail-header">
      ${channel.logoUrl ? `<img class="detail-logo" src="${escapeHtml(channel.logoUrl)}" alt="" loading="lazy" />` : '<div class="detail-logo" aria-hidden="true"></div>'}
      <div>
        <h2>${escapeHtml(channel.name || channel.id)}</h2>
        <div class="channel-row-meta">${escapeHtml(channel.id)} · ${escapeHtml(channel.targetXmltvId || 'no target')}</div>
      </div>
    </div>
    <section class="detail-meta">
      <h3>Mapping and coverage</h3>
      ${keyValueRows(channel)}
    </section>
    <section>
      <h3>Validation findings</h3>
      ${renderFindings(channel)}
    </section>
    <section>
      <h3>Preview window programmes</h3>
      ${renderPrograms(channel)}
    </section>
  `;
}

async function init() {
  try {
    const [validation, preview] = await Promise.all([
      loadJson('data/uhf/validation.json'),
      loadJson('data/uhf/preview.json'),
    ]);
    state.validation = validation;
    state.preview = preview;
    state.channels = mergeData(validation, preview);
    renderSummary();
    renderList();
  } catch (error) {
    els.status.textContent = `Failed to load UHF validation data: ${error.message}`;
    els.detail.innerHTML = `<div class="empty">${escapeHtml(error.message)}</div>`;
  }
}

els.search.addEventListener('input', (event) => {
  state.query = event.target.value;
  renderList();
});
els.severity.addEventListener('change', (event) => {
  state.severity = event.target.value;
  renderList();
});
els.list.addEventListener('click', (event) => {
  const row = event.target.closest('.channel-row');
  if (!row) return;
  state.selectedId = row.dataset.id;
  renderList();
});

init();
