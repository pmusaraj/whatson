import subprocess
import unittest
from pathlib import Path


class LiveSportsGroupingTest(unittest.TestCase):
    def test_matching_broadcasts_group_without_merging_distinct_events(self):
        subprocess.run(['node', '-e', r'''
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const app = fs.readFileSync('web/app.js', 'utf8');
const context = {};
vm.createContext(context);
for (const [start, end] of [
  ['function normalizeSearchText(', 'function countryMatchesSearch('],
  ['function isOverlappingDuplicate(', 'function mergeDuplicateChannels('],
  ['function sportsEventText(', 'function availableSportFilters('],
]) vm.runInContext(app.slice(app.indexOf(start), app.indexOf(end)), context);
context.rows = [];
const row = (key, title = 'Arsenal vs. Chelsea', extra = {}) => ({
  key, index: 2, sport: {id: 'soccer', label: 'Soccer'},
  program: {title, startAt: '2026-09-18T18:00:00Z', endAt: '2026-09-18T20:00:00Z', ...extra},
});
const group = rows => {context.rows = rows; return vm.runInContext('groupLiveSportsResults(rows)', context)};
const a = row('GB:one');
const b = row('CA:two', 'Live: Arsenal v Chelsea', {startAt: '2026-09-18T18:15:00Z'});
let groups = group([a, b, b]);
assert.equal(groups.length, 1);
assert.equal(groups[0].airings.length, 2);
assert.equal(groups[0].airings[1].key, 'CA:two');
assert.equal(groups[0].airings[1].index, 2);
assert.equal(group([a, row('CA:two', 'Arsenal vs Liverpool')]).length, 2);
assert.equal(group([a, row('CA:two', a.program.title, {startAt: '2026-09-18T20:00:00Z', endAt: '2026-09-18T22:00:00Z'})]).length, 2);
assert.equal(group([row('GB:one', 'Tennis', {subtitle: 'Court 1'}), row('CA:two', 'Tennis', {subtitle: 'Court 2'})]).length, 2);
assert.equal(group([row('GB:one', 'Grand Slam Tennis', {subtitle: 'Court 1'}), row('CA:two', 'Grand Slam Tennis', {subtitle: 'Court 2'})]).length, 2);
assert.equal(group([a, {...b, sport: {id: 'rugby', label: 'Rugby'}}]).length, 2);
// Filtering operates on events while retaining all of their channel buttons.
context.state = {selectedSportFilter: 'soccer'};
vm.runInContext(app.slice(app.indexOf('function visibleLiveSportsResults('), app.indexOf('function renderSportFilters(')), context);
context.rows = groups;
assert.equal(vm.runInContext('visibleLiveSportsResults(rows).length', context), 1);
context.state.selectedSportFilter = 'tennis';
assert.equal(vm.runInContext('visibleLiveSportsResults(rows).length', context), 0);
context.state.selectedSportFilter = null;
assert.equal(vm.runInContext('visibleLiveSportsResults(rows).length', context), 1);
'''], cwd=Path(__file__).resolve().parents[1], check=True)

    def test_simultaneous_events_share_columns_and_keep_now_between_groups(self):
        subprocess.run(['node', '-e', r'''
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const app = fs.readFileSync('web/app.js', 'utf8');
const context = {state: {now: new Date('2026-09-18T18:30:00Z')},
  formatTime: value => value.toISOString(), escapeHtml: value => value};
vm.createContext(context);
for (const [start, end] of [
  ['function renderConcurrentEvents(', 'function renderLiveSportsResults('],
  ['function renderTimedEvents(', 'function renderEditorPicks('],
]) vm.runInContext(app.slice(app.indexOf(start), app.indexOf(end)), context);
context.events = [
  {title: 'Later', program: {startAt: '2026-09-18T19:00:00Z'}},
  {title: 'Soccer', program: {startAt: '2026-09-18T18:00:00Z'}},
  {title: 'Tennis', program: {startAt: '2026-09-18T20:00:00+02:00'}},
];
const render = () => vm.runInContext('renderConcurrentEvents(events, e => `<article>${e.title}</article>`, "No events")', context);
let html = render();
assert.ok(html.includes('<div class="event-time-group"><article>Soccer</article><article>Tennis</article></div>'));
assert.equal((html.match(/class="event-time-group"/g) || []).length, 2);
assert.equal((html.match(/class="event-time-heading"/g) || []).length, 2);
assert.equal((html.match(/datetime="2026-09-18T18:00:00.000Z"/g) || []).length, 1);
assert.ok(html.indexOf('Tennis') < html.indexOf('Now ·'));
assert.ok(html.indexOf('Now ·') < html.indexOf('Later'));
context.events = context.events.filter(e => e.title !== 'Tennis');
assert.ok(!render().includes('Tennis'));
context.events = [];
html = render();
assert.ok(html.includes('No events'));
assert.ok(html.includes('Now ·'));
'''], cwd=Path(__file__).resolve().parents[1], check=True)
