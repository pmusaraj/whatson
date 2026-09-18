import subprocess
import unittest
from pathlib import Path


class ThemePreviewTest(unittest.TestCase):
    def test_preview_is_allowlisted_and_does_not_change_saved_theme(self):
        subprocess.run(['node', '-e', r'''
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const app = fs.readFileSync('web/app.js', 'utf8');
for (const query of ['', '?theme=paper', '?theme=pop', '?theme=broadcast', '?theme=constructor', '?theme=https://example.com']) {
  const saved = new Map([['whatsontv.theme', 'default'], ['whatsontv.themeDefault', 'editor-picks-pills']]);
  const before = JSON.stringify([...saved]);
  const context = { URLSearchParams, window: { location: { search: query } },
    localStorage: { getItem: k => saved.get(k), setItem: (k, v) => saved.set(k, v) },
    els: { themeLink: {} }, document: { documentElement: { dataset: {} } } };
  vm.createContext(context);
  vm.runInContext(app.slice(0, app.indexOf('const state =')), context);
  vm.runInContext(app.slice(app.indexOf('function loadTheme()'), app.indexOf('function channelKey(')), context);
  vm.runInContext('setTheme(loadTheme())', context);
  const expected = ['paper', 'pop', 'broadcast'].find(t => query === '?theme=' + t) || 'default';
  assert.equal(context.document.documentElement.dataset.theme, expected);
  assert.equal(JSON.stringify([...saved]), before);
  assert.ok(fs.existsSync('web/' + context.els.themeLink.href.split('?')[0]));
  if (query) {
    context.window.location.search = '';
    vm.runInContext('setTheme(loadTheme())', context);
    assert.equal(context.document.documentElement.dataset.theme, 'default');
  }
}
'''], cwd=Path(__file__).resolve().parents[1], check=True)


if __name__ == '__main__':
    unittest.main()
