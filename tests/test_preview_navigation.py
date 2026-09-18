import subprocess
import unittest
from pathlib import Path


class PreviewNavigationTest(unittest.TestCase):
    def test_collapsed_countries_and_top_actions_preserve_selection(self):
        subprocess.run(['node', '-e', r'''
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const nodes = new Map();
function node(id) {
  if (!nodes.has(id)) nodes.set(id, {innerHTML: '', dataset: {}, value: '',
    addEventListener(type, fn) { this[type] = fn; }, setAttribute() {},
    contains() { return false; }, prepend() {}, append() {}, focus() {}});
  return nodes.get(id);
}
const document = {querySelector: node, documentElement: {dataset: {theme: 'soft-studio'}},
  body: {dataset: {}}, addEventListener() {}};
const context = {document, URLSearchParams, console,
  localStorage: {getItem() {return null}, setItem() {}},
  window: {addEventListener() {}, matchMedia() {return {matches: false}}}};
vm.createContext(context);
let app = fs.readFileSync('web/app.js', 'utf8');
vm.runInContext(app.slice(0, app.lastIndexOf('setTheme(loadTheme());')), context);
vm.runInContext(`
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
node('#channel-list').toggle({target: {matches: () => true, isConnected: true, dataset: {countryCode: 'CA'}, open: false}});
vm.runInContext('renderChannelList(); render = () => {}; renderGuide = () => {};', context);
assert.doesNotMatch(node('#channel-list').innerHTML, / open/);
node('#editor-picks-toggle').click();
assert.equal(vm.runInContext('state.editorPicksOpen', context), true);
assert.equal(JSON.stringify(vm.runInContext('state.selectedChannelKeys', context)), '["CA:one"]');
node('#live-sports-toggle').click();
assert.equal(vm.runInContext('state.liveSportsOpen', context), true);
assert.equal(vm.runInContext('state.editorPicksOpen', context), false);
assert.equal(JSON.stringify(vm.runInContext('state.selectedChannelKeys', context)), '["CA:one"]');
// Non-preview themes retain the existing expanded country groups.
document.documentElement.dataset.theme = 'sense';
vm.runInContext('renderChannelList()', context);
assert.match(node('#channel-list').innerHTML, /<section class="country-group"/);
'''], cwd=Path(__file__).resolve().parents[1], check=True)


if __name__ == '__main__':
    unittest.main()
