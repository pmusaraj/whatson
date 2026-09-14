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
const pick = { title: program.title, startAt, channels: ['one', 'two', 'alias'].map(channelId => ({
  country: 'US', channelId, sourceTitle: program.title, startAt, endAt
})) };
const context = {
  state: { now: new Date('2026-09-14T19:00:00Z'), editorPicks: Array(12).fill(pick),
    countryDataByCode: new Map([['US', { country: 'US', channels, duplicateChannelAliases: { alias: 'one' } }]]) },
  els: { editorPicks: {}, editorPicksList: {} },
  channelKey: (country, id) => `${country}:${id}`,
  isOverlappingDuplicate: () => false,
  escapeHtml: value => value, formatTime: value => value, flagEmoji: value => value,
};
vm.createContext(context);
vm.runInContext(app.slice(app.indexOf('function resolvedEditorPicks()'), app.indexOf('function setLiveSportsOpen(')), context);
vm.runInContext('renderEditorPicks()', context);
const html = context.els.editorPicksList.innerHTML;
assert.equal((html.match(/class="editor-pick-result"/g) || []).length, 12);
assert.equal((html.match(/class="editor-pick-channel"/g) || []).length, 24);
assert.ok(html.includes('data-channel-key="US:two" data-program-index="0"'));
context.state.now = new Date(endAt);
vm.runInContext('renderEditorPicks()', context);
assert.equal(context.els.editorPicks.hidden, true);
assert.equal(context.els.editorPicksList.innerHTML, '');
"""
        subprocess.run(["node", "-e", script], cwd=Path(__file__).resolve().parents[1], check=True)

    def test_editor_picks_expire_without_reload(self):
        app = (Path(__file__).resolve().parents[1] / "web" / "app.js").read_text(encoding="utf-8")

        self.assertIn("new Date(channel.programs[index].endAt).getTime() > state.now.getTime()", app)
        self.assertIn("renderEditorPicks();", app[app.index("window.setInterval"):])


if __name__ == "__main__":
    unittest.main()