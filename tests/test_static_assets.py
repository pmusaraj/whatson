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
  state: { now: new Date('2026-09-14T19:00:00Z'), editorPicks: Array(12).fill(pick),
    countryDataByCode: new Map([['US', { country: 'US', channels, duplicateChannelAliases: { alias: 'one' } }]]) },
  els: { editorPicks: {}, editorPicksList: {} },
  normalizeSearchText: value => String(value || '').toLowerCase(),
  channelKey: (country, id) => `${country}:${id}`,
  isOverlappingDuplicate: () => false,
  escapeHtml: value => value, formatTime: value => value, flagEmoji: value => value,
};
vm.createContext(context);
vm.runInContext(app.slice(app.indexOf('const SPORT_BUCKETS ='), app.indexOf('function isLiveSportsProgram(')), context);
vm.runInContext(app.slice(app.indexOf('function resolvedEditorPicks()'), app.indexOf('function setLiveSportsOpen(')), context);
assert.equal(vm.runInContext("detectSportBucket({ sportType: 'Football', competition: 'Premier League', categories: ['Cricket'] }).emoji", context), '🏏');
assert.equal(vm.runInContext("detectSportBucket({ title: 'UFC Fight Night', sportType: 'Combat sports' }).emoji", context), '🥊');
vm.runInContext('renderEditorPicks()', context);
const html = context.els.editorPicksList.innerHTML;
assert.equal((html.match(/class="editor-pick-result"/g) || []).length, 12);
assert.equal((html.match(/class="editor-pick-channel"/g) || []).length, 24);
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
assert.ok(sportsHtml.includes('<span aria-hidden="true">⚽</span> Early soccer'));
assert.ok(sportsHtml.includes('<span aria-hidden="true">🎾</span> Late tennis'));
assert.ok(fs.readFileSync('web/index.html', 'utf8').includes("<summary>Today's editors picks for sports</summary>"));
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