const els = {
  title: document.querySelector('#page-title'),
  status: document.querySelector('#status'),
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
  return `
    <div class="program-table" role="table" aria-label="Programme preview">
      <div class="program-table-row program-table-head" role="row">
        <div role="columnheader">Time</div>
        <div role="columnheader">Title</div>
        <div role="columnheader">Details</div>
      </div>
      ${channel.programs.map((program) => `
        <article class="program-table-row" role="row">
          <div class="program-time" role="cell">
            <strong>${escapeHtml(formatDate(program.startAt))}</strong>
            <span>${escapeHtml(formatDate(program.endAt))}</span>
            <small>${escapeHtml(formatUtc(program.startAt))} → ${escapeHtml(formatUtc(program.endAt))}</small>
          </div>
          <div role="cell">
            <h3>${escapeHtml(program.title || 'Untitled')}</h3>
            ${program.subtitle ? `<div>${escapeHtml(program.subtitle)}</div>` : ''}
            ${(program.categories || []).length ? `<div class="badges">${program.categories.map((category) => `<span class="badge">${escapeHtml(category)}</span>`).join('')}</div>` : ''}
          </div>
          <div role="cell" class="program-description">${escapeHtml(program.description || '—')}</div>
        </article>
      `).join('')}
    </div>
  `;
}

function renderChannel(channel, validation) {
  const statusBadges = [
    channel.errorCount ? `<span class="badge error">${channel.errorCount} errors</span>` : '',
    channel.warningCount ? `<span class="badge warning">${channel.warningCount} warnings</span>` : '<span class="badge ok">clean</span>',
    `<span class="badge">${channel.programmeCount || channel.programs.length} programmes</span>`,
  ].join('');

  els.title.textContent = channel.name || channel.id;
  els.status.textContent = `Generated ${relativeAge(validation.generatedAt)} · ${channel.id}`;
  document.title = `${channel.name || channel.id} -- UHF channel detail`;
  els.detail.innerHTML = `
    <div class="detail-header detail-header-page">
      ${channel.logoUrl ? `<img class="detail-logo" src="${escapeHtml(channel.logoUrl)}" alt="" loading="lazy" />` : '<div class="detail-logo" aria-hidden="true"></div>'}
      <div>
        <h2>${escapeHtml(channel.name || channel.id)}</h2>
        <div class="channel-row-meta">${escapeHtml(channel.id)} · ${escapeHtml(channel.targetXmltvId || 'no target')}</div>
        <div class="badges">${statusBadges}</div>
      </div>
    </div>

    <section class="detail-meta">
      <h3>Mapping and coverage</h3>
      ${keyValueRows(channel)}
    </section>

    <section class="detail-section">
      <h3>Validation findings</h3>
      ${renderFindings(channel)}
    </section>

    <section class="detail-section">
      <h3>Preview window programmes</h3>
      ${renderPrograms(channel)}
    </section>
  `;
}

async function init() {
  try {
    const id = new URLSearchParams(window.location.search).get('id');
    if (!id) throw new Error('Missing channel id in the URL.');
    const [validation, preview] = await Promise.all([
      loadJson('data/uhf/validation.json'),
      loadJson('data/uhf/preview.json'),
    ]);
    const channel = mergeData(validation, preview).find((item) => item.id === id);
    if (!channel) throw new Error(`Channel not found: ${id}`);
    renderChannel(channel, validation);
  } catch (error) {
    els.status.textContent = `Failed to load channel detail: ${error.message}`;
    els.detail.innerHTML = `<div class="empty">${escapeHtml(error.message)}</div>`;
  }
}

init();
