import subprocess
import unittest
from pathlib import Path


class PreviewNavigationTest(unittest.TestCase):
    def test_collapsed_countries_and_program_actions_preserve_selection(self):
        subprocess.run(['node', '-e', r'''
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const nodes = new Map();
function node(id) {
  if (!nodes.has(id)) nodes.set(id, {innerHTML: '', dataset: {}, value: '',
    addEventListener(type, fn) { this[type] = fn; }, setAttribute() {},
    querySelectorAll() { return []; }, contains() { return false; }, prepend() {}, append() {}, focus() {}});
  return nodes.get(id);
}
const document = {querySelector: node, documentElement: {dataset: {theme: 'soft-studio'}},
  body: {dataset: {}}, addEventListener() {}};
const context = {document, URLSearchParams, console, assert,
  localStorage: {getItem() {return null}, setItem() {}},
  window: {addEventListener() {}, matchMedia() {return {matches: false}}}};
vm.createContext(context);
let app = fs.readFileSync('web/app.js', 'utf8');
vm.runInContext(app.slice(0, app.lastIndexOf('setTheme(loadTheme());')), context);
vm.runInContext(`
assert.equal(state.editorPicksOpen, true);
state.countries = [{code: 'CA'}, {code: 'UK'}];
for (const code of ['CA', 'UK']) state.countryDataByCode.set(code,
  {country: code, countryName: code === 'CA' ? 'Canada' : 'United Kingdom', channels: [{id: 'one', name: 'One', programs: []}]});
state.selectedChannelKeys = ['CA:one'];
renderChannelList();
`, context);
assert.match(node('#channel-list').innerHTML, /<details class="country-group"/);
assert.doesNotMatch(node('#channel-list').innerHTML, / open/);
assert.match(node('#channel-list').innerHTML, /<summary><span class="country-flag-pill" aria-hidden="true">🇨🇦<\/span> Canada<\/summary>/);
node('#channel-list').toggle({target: {matches: () => true, isConnected: true, dataset: {countryCode: 'CA'}, open: true}});
vm.runInContext('renderChannelList()', context);
assert.match(node('#channel-list').innerHTML, /data-country-code="CA" open/);
assert.doesNotMatch(node('#channel-list').innerHTML, /data-country-code="UK" open/);
const canada = {matches: () => true, isConnected: true, dataset: {countryCode: 'CA'}, open: true};
const uk = {matches: () => true, isConnected: true, dataset: {countryCode: 'UK'}, open: true};
node('#channel-list').querySelectorAll = () => [canada, uk].filter(group => group.open);
node('#channel-list').toggle({target: uk});
assert.equal(canada.open, false);
vm.runInContext('renderChannelList()', context);
assert.doesNotMatch(node('#channel-list').innerHTML, /data-country-code="CA" open/);
assert.match(node('#channel-list').innerHTML, /data-country-code="UK" open/);
uk.open = false;
node('#channel-list').toggle({target: uk});
vm.runInContext('renderChannelList(); render = () => {}; renderGuide = () => {};', context);
assert.doesNotMatch(node('#channel-list').innerHTML, / open/);
node('#editor-picks-toggle').click();
assert.equal(vm.runInContext('state.editorPicksOpen', context), true);
assert.equal(JSON.stringify(vm.runInContext('state.selectedChannelKeys', context)), '["CA:one"]');
node('#live-sports-toggle').click();
assert.equal(vm.runInContext('state.liveSportsOpen', context), true);
assert.equal(vm.runInContext('state.editorPicksOpen', context), false);
assert.equal(JSON.stringify(vm.runInContext('state.selectedChannelKeys', context)), '["CA:one"]');
node('#editor-picks-toggle').click();
assert.equal(vm.runInContext('state.editorPicksOpen', context), true);
assert.equal(vm.runInContext('state.liveSportsOpen', context), false);
assert.equal(JSON.stringify(vm.runInContext('state.selectedChannelKeys', context)), '["CA:one"]');
// Program controls stay active when invoked again.
node('#live-sports-toggle').click();
node('#live-sports-toggle').click();
assert.equal(vm.runInContext('state.liveSportsOpen', context), true);
const selectedChannel = {dataset: {channelKey: 'CA:one'}, disabled: false};
node('#channel-list').click({target: {closest: () => selectedChannel}});
assert.equal(vm.runInContext('state.liveSportsOpen', context), false);
assert.equal(vm.runInContext('state.editorPicksOpen', context), false);
assert.equal(JSON.stringify(vm.runInContext('state.selectedChannelKeys', context)), '["CA:one"]');
node('#editor-picks-toggle').click();
node('#editor-picks-toggle').click();
assert.equal(vm.runInContext('state.editorPicksOpen', context), true);
node('#editor-picks-list').click({target: {closest: selector => selector === '.event-title' ? null : ({dataset: {channelKey: 'UK:one'}})}});
assert.equal(vm.runInContext('state.editorPicksOpen', context), false);
assert.equal(JSON.stringify(vm.runInContext('state.selectedChannelKeys', context)), '["CA:one","UK:one"]');
node('#live-sports-toggle').click();
const channelPill = {dataset: {channelKey: 'CA:one'}, matches: () => true};
node('#search-results').click({target: {closest: selector => selector === '[data-sport-filter]' ? null : channelPill}});
assert.equal(vm.runInContext('state.liveSportsOpen', context), false);
assert.equal(vm.runInContext('state.mobileView', context), 'guide');
// Event titles open the modal without switching views or changing channels.
vm.runInContext('openProgramDetails = (key, index) => { globalThis.openedEvent = {key, index}; };', context);
const eventTitle = {dataset: {channelKey: 'CA:one', programIndex: '2'}, matches: () => false};
node('#editor-picks-toggle').click();
node('#editor-picks-list').click({target: {closest: () => eventTitle}});
assert.equal(context.openedEvent.key, 'CA:one');
assert.equal(context.openedEvent.index, '2');
assert.equal(vm.runInContext('state.editorPicksOpen', context), true);
node('#live-sports-toggle').click();
node('#search-results').click({target: {closest: selector => selector === '[data-sport-filter]' ? null : eventTitle}});
assert.equal(context.openedEvent.key, 'CA:one');
assert.equal(vm.runInContext('state.liveSportsOpen', context), true);
// Filters remain interactive in the heading, independently of event clicks.
node('#sport-filters').click({target: {closest: () => ({dataset: {sportFilter: 'soccer'}})}});
assert.equal(vm.runInContext("state.selectedSportFilter", context), "soccer");
node('#sport-filters').click({target: {closest: () => ({dataset: {sportFilter: 'soccer'}})}});
assert.equal(vm.runInContext("state.selectedSportFilter", context), null);
// Channels heading returns to the saved channel view without changing selection.
node('#editor-picks-toggle').click();
const beforeChannelsClick = JSON.stringify(vm.runInContext('state.selectedChannelKeys', context));
node('#channels-view').click();
assert.equal(vm.runInContext('state.editorPicksOpen', context), false);
assert.equal(vm.runInContext('state.liveSportsOpen', context), false);
assert.equal(JSON.stringify(vm.runInContext('state.selectedChannelKeys', context)), beforeChannelsClick);
// Non-preview themes retain the existing expanded country groups.
document.documentElement.dataset.theme = 'sense';
vm.runInContext('renderChannelList()', context);
assert.match(node('#channel-list').innerHTML, /<section class="country-group"/);
'''], cwd=Path(__file__).resolve().parents[1], check=True)


if __name__ == '__main__':
    unittest.main()
