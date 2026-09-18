import re
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
for (const preference of ['default', 'sense', null]) {
for (const query of ['', '?theme=soft-studio', '?theme=open-air', '?theme=quiet-guide', '?theme=paper', '?theme=pop', '?theme=broadcast', '?theme=constructor', '?theme=__proto__', '?theme=', '?theme=https://example.com']) {
  const saved = new Map(preference ? [['whatsontv.theme', preference], ['whatsontv.themeDefault', 'editor-picks-pills']] : []);
  const before = JSON.stringify([...saved]);
  const context = { URLSearchParams, window: { location: { search: query } },
    localStorage: { getItem: k => saved.get(k), setItem: (k, v) => saved.set(k, v) },
    els: { themeLink: {} }, document: { documentElement: { dataset: {} } } };
  vm.createContext(context);
  vm.runInContext(app.slice(0, app.indexOf('const state =')), context);
  vm.runInContext(app.slice(app.indexOf('function loadTheme()'), app.indexOf('function channelKey(')), context);
  vm.runInContext('setTheme(loadTheme())', context);
  const expected = ['soft-studio', 'open-air', 'quiet-guide'].find(t => query === '?theme=' + t) || preference || 'sense';
  assert.equal(context.document.documentElement.dataset.theme, expected);
  if (query || preference) assert.equal(JSON.stringify([...saved]), before);
  assert.ok(fs.existsSync('web/' + context.els.themeLink.href.split('?')[0]));
  if (query) {
    context.window.location.search = '';
    vm.runInContext('setTheme(loadTheme())', context);
    assert.equal(context.document.documentElement.dataset.theme, preference || 'sense');
  }
}
}
'''], cwd=Path(__file__).resolve().parents[1], check=True)


    def test_preview_styles_preserve_logo_and_do_not_define_layout(self):
        web = Path(__file__).resolve().parents[1] / 'web'
        shared = (web / 'exploration-theme.css').read_text()
        sense = (web / 'sense-theme.css').read_text()

        def declaration(css, selector, name):
            rule = re.search(re.escape(selector) + r'\s*\{([^}]+)', css)[1]
            value = re.search(re.escape(name) + r':\s*([^;]+)', rule)[1]
            return ' '.join(value.split())

        self.assertEqual(declaration(shared, '.brand-logo', 'font-family'),
                         declaration(sense, 'body', 'font-family'))
        self.assertEqual(declaration(shared, '.brand-logo', 'line-height'),
                         declaration(sense, 'h1', 'line-height'))
        self.assertEqual(declaration(shared, '.brand-logo', 'color'),
                         declaration(sense, ':root', '--text'))
        html = (web / 'index.html').read_text()
        self.assertIn('<span class="brand-logo-part brand-logo-hey">hey</span>', html)
        self.assertIn('<span class="brand-logo-part brand-logo-main">whatson</span><span class="brand-logo-part brand-logo-domain">.tv</span>', html)
        allowed = {'color-scheme', 'color', 'background', 'border-color',
                   'border-bottom-color', 'border-radius', 'box-shadow',
                   'font-family', 'font-weight', 'font-variant-numeric',
                   'line-height', 'outline', 'outline-offset', 'opacity',
                   'backdrop-filter'}
        for name in ['exploration', 'soft-studio', 'open-air', 'quiet-guide']:
            css = (web / f'{name}-theme.css').read_text()
            properties = re.findall(r'(?:\{|;)\s*([\w-]+)\s*:', css)
            self.assertTrue(all(p.startswith('--') or p in allowed for p in properties), name)
            if name != 'exploration':
                self.assertNotIn('brand-logo', css)


if __name__ == '__main__':
    unittest.main()
