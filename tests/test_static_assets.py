import subprocess
import unittest
from pathlib import Path


class StaticAssetsTest(unittest.TestCase):
    def test_editor_picks_render_all_events_and_distinct_channel_pills(self):
        script = r"""
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const app = fs.readFileSync('web/app.js', 'utf8');
const startAt = '2026-09-14T18:00:00Z', endAt = '2026-09-14T20:00:00Z';
const program = { title: 'Live event', startAt, endAt };
const channels = ['one', 'two'].map(id => ({ id, name: id, programs: [program] }));
const pick = { title: program.title, highlightType: 'liveSport', sportType: 'Tennis', startAt, channels: ['one', 'two', 'alias'].map(channelId => ({
  country: 'US', channelId, sourceTitle: program.title, startAt, endAt
})) };
const context = {
  state: { now: new Date('2026-09-14T19:00:00Z'), editorPicks: Array(20).fill(pick),
    countryDataByCode: new Map([['US', { country: 'US', channels, duplicateChannelAliases: { alias: 'one' } }]]) },
  els: { editorPicks: {}, editorPicksList: {} },
  normalizeSearchText: value => String(value || '').toLowerCase(),
  channelKey: (country, id) => `${country}:${id}`,
  isOverlappingDuplicate: () => false,
  isPreviewTheme: () => false,
  escapeHtml: value => value, formatTime: value => value, flagEmoji: value => value,
};
vm.createContext(context);
vm.runInContext(app.slice(app.indexOf('const SPORT_BUCKETS ='), app.indexOf('function isLiveSportsProgram(')), context);
vm.runInContext(app.slice(app.indexOf('function resolvedEditorPicks()'), app.indexOf('function setLiveSportsOpen(')), context);
assert.equal(vm.runInContext("detectSportBucket({ sportType: 'Football', competition: 'Premier League', categories: ['Cricket'] }).emoji", context), '🏏');
assert.equal(vm.runInContext("detectSportBucket({ title: 'UFC Fight Night', sportType: 'Combat sports' }).emoji", context), '🥊');
for (const [title, emoji] of [
  ['NFL: Detroit Lions at Buffalo Bills', '🏈'],
  ['AFL Preliminary Final: Sydney Swans vs Fremantle', '🏉'],
  ['Arena Football League', '🏈'],
  ['Premier League: Arsenal vs Chelsea', '⚽'],
]) {
  context.footballProgram = { title, sportType: 'Football', categories: ['Sport'] };
  assert.equal(vm.runInContext('detectSportBucket(footballProgram).emoji', context), emoji);
}
assert.equal(vm.runInContext("detectSportBucket({ title: 'NFL documentary', categories: ['Documentary'] })", context), null);
vm.runInContext('renderEditorPicks()', context);
const html = context.els.editorPicksList.innerHTML;
assert.equal((html.match(/class="editor-pick-result"/g) || []).length, 20);
assert.equal((html.match(/class="editor-pick-channel"/g) || []).length, 40);
assert.ok(html.includes('data-channel-key="US:two" data-program-index="0"'));
context.state.editorPicks = [
  { ...pick, title: 'Late tennis', startAt: '2026-09-14T21:00:00+02:00' },
  { ...pick, title: 'Series premiere', highlightType: 'freshProgramme', categories: ['Series'] },
  { ...pick, title: 'Early soccer', sportType: 'Soccer', startAt: '2026-09-14T18:30:00Z' },
];
vm.runInContext('renderEditorPicks()', context);
const sportsHtml = context.els.editorPicksList.innerHTML;
assert.equal((sportsHtml.match(/class="editor-pick-result"/g) || []).length, 2);
assert.ok(!sportsHtml.includes('Series premiere'));
assert.ok(sportsHtml.indexOf('Early soccer') < sportsHtml.indexOf('Late tennis'));
assert.ok(sportsHtml.includes('<span class="editor-pick-sport" aria-hidden="true">⚽</span>'));
assert.ok(sportsHtml.includes('>Early soccer</button>'));
context.state.editorPicks = ['Bundesliga', 'Ligue 1', 'Serie A', 'La Liga', 'Premier League', '2. Bundesliga', 'LaLiga Hypermotion', 'Ligue 2', 'Serie B', 'EFL Championship'].map(title => ({ ...pick, title, competition: title }));
assert.deepEqual(Array.from(vm.runInContext('resolvedEditorPicks().map(row => row.pick.title)', context)), ['Premier League', 'La Liga', 'Serie A', 'Ligue 1', 'Bundesliga']);
assert.equal(vm.runInContext("editorPickLeagueRank({ title: 'Caribbean Premier League', categories: ['Cricket'], competition: 'Premier League' })", context), 5);
assert.equal(vm.runInContext("editorPickLeagueRank({ title: 'Argentine Primera División', competition: 'Premier League', description: 'The premier league in Argentina' })", context), 5);
const many = ['US', 'FR', 'DE'].flatMap(country => Array.from({length: 4}, (_, i) => ({ country, channelId: country + i, sourceTitle: program.title, startAt, endAt })));
context.state.countryDataByCode = new Map(['US', 'FR', 'DE'].map(country => [country, {country, channels: many.filter(c => c.country === country).map(c => ({id: c.channelId, name: c.channelId, programs: [program]}))}]));
context.state.editorPicks = [{ ...pick, channels: many }];
vm.runInContext('renderEditorPicks()', context);
const manyHtml = context.els.editorPicksList.innerHTML;
assert.equal((manyHtml.match(/class="editor-pick-channel"/g) || []).length, 9);
assert.equal((manyHtml.split('<details')[0].match(/class="editor-pick-channel"/g) || []).length, 6);
assert.ok(manyHtml.includes('>more</summary>'));
for (const country of ['US', 'FR', 'DE']) assert.ok(!manyHtml.includes(`data-channel-key="${country}:${country}3"`));
assert.ok(sportsHtml.includes('<span class="editor-pick-sport" aria-hidden="true">🎾</span>'));
assert.ok(fs.readFileSync('web/index.html', 'utf8').includes("<h2 id=\"guide-title\" class=\"guide-title\">Today's Editors Picks in Sports</h2>"));
context.state.now = new Date(endAt);
vm.runInContext('renderEditorPicks()', context);
assert.equal(context.els.editorPicks.hidden, false);
assert.ok(context.els.editorPicksList.innerHTML.includes('No upcoming editor’s picks'));
"""
        subprocess.run(["node", "-e", script], cwd=Path(__file__).resolve().parents[1], check=True)

    def test_times_on_other_local_dates_include_the_date(self):
        subprocess.run(['node', '-e', r"""
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
process.env.TZ = 'America/Toronto';
const app = fs.readFileSync('web/app.js', 'utf8');
const context = {state: {now: new Date('2026-09-19T17:53:00Z')}};
vm.createContext(context);
vm.runInContext(app.slice(app.indexOf('function formatTime('), app.indexOf('function formatCurrentTime(')), context);
const format = value => { context.value = value; return vm.runInContext('formatTime(value)', context); };
const expected = (value, otherDay) => new Intl.DateTimeFormat(undefined, {
  ...(otherDay ? {month: 'short', day: 'numeric'} : {}), hour: 'numeric', minute: '2-digit',
}).format(new Date(value));
for (const [value, otherDay] of [
  ['2026-09-19T16:20:00Z', false],
  ['2026-09-20T12:50:00Z', true], // Live picks: tomorrow's 8:50 AM is below Now.
  ['2026-09-20T01:00:00Z', false], // UTC tomorrow is still today locally.
  ['2026-09-19T01:00:00Z', true],
]) assert.equal(format(value), expected(value, otherDay));
context.state.now = new Date('2026-09-20T04:00:00Z');
assert.equal(format('2026-09-20T12:50:00Z'), expected('2026-09-20T12:50:00Z', false));
assert.equal(format('2026-09-19T16:20:00Z'), expected('2026-09-19T16:20:00Z', true));
"""], cwd=Path(__file__).resolve().parents[1], check=True)

    def test_event_time_marker_tracks_now_and_handles_empty_lists(self):
        subprocess.run(['node', '-e', r"""
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const app = fs.readFileSync('web/app.js', 'utf8');
const context = {state: {now: new Date('2026-09-18T18:00:00Z')},
  formatTime: value => value.toISOString(), escapeHtml: value => value};
vm.createContext(context);
vm.runInContext(app.slice(app.indexOf('function renderTimedEvents('), app.indexOf('function renderEditorPicks(')), context);
const render = starts => {
  context.events = starts.map(hour => ({start: `2026-09-18T${hour}:00:00Z`, title: `Event ${hour}`}));
  return vm.runInContext('renderTimedEvents(events, e => e.start, e => `<article>${e.title}</article>`, "No events")', context);
};
let html = render(['17', '18', '19']);
assert.equal((html.match(/class="event-now-indicator"/g) || []).length, 1);
assert.ok(html.indexOf('Event 18') < html.indexOf('Now ·'));
assert.ok(html.indexOf('Now ·') < html.indexOf('Event 19'));
assert.ok(render(['19']).indexOf('Now ·') < render(['19']).indexOf('Event 19'));
html = render(['19', '17', '18']);
assert.ok(html.indexOf('Event 18') < html.indexOf('Now ·'));
assert.ok(html.indexOf('Now ·') < html.indexOf('Event 19'));
context.state.now = new Date('2026-09-18T19:01:00Z');
html = render(['17', '18', '19']);
assert.ok(html.indexOf('Now ·') > html.indexOf('Event 19'));
assert.ok(html.includes('datetime="2026-09-18T19:01:00.000Z"'));
html = render([]);
assert.ok(html.includes('Now ·'));
assert.ok(html.includes('No events'));
"""], cwd=Path(__file__).resolve().parents[1], check=True)

    def test_mobile_sidebar_dismisses_only_on_noninteractive_outside_clicks(self):
        script = r"""
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const app = fs.readFileSync('web/app.js', 'utf8');
let click, mobile = true, inside = false, interactive = false;
const context = {
  document: { addEventListener: (type, handler) => { click = handler; } },
  state: { mobileView: 'picker' },
  els: { channelPicker: { contains: () => inside } },
  isMobileLayout: () => mobile,
  setMobileView: view => { context.state.mobileView = view; },
};
vm.createContext(context);
vm.runInContext(app.slice(app.indexOf('document.addEventListener("click"'), app.indexOf('els.clearSelection.addEventListener("click"')), context);
assert.equal(typeof click, 'function');
const event = { target: { closest: () => interactive } };
for (const scenario of [
  [true, false, false, 'guide'],
  [true, true, false, 'picker'],
  [true, false, true, 'picker'],
  [false, false, false, 'picker'],
]) {
  [mobile, inside, interactive] = scenario;
  context.state.mobileView = 'picker';
  click(event);
  assert.equal(context.state.mobileView, scenario[3]);
}
"""
        subprocess.run(["node", "-e", script], cwd=Path(__file__).resolve().parents[1], check=True)

    def test_editor_picks_expire_without_reload(self):
        app = (Path(__file__).resolve().parents[1] / "web" / "app.js").read_text(encoding="utf-8")

        self.assertIn("new Date(channel.programs[index].endAt).getTime() > state.now.getTime()", app)
        self.assertIn("renderEditorPicks();", app[app.index("window.setInterval"):])


if __name__ == "__main__":
    unittest.main()