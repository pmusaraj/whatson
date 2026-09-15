# France, Italy and Germany guide repairs

Verified against public sources on 2026-09-15. UHF was not opened or modified.

## France

- Prefer SFR for supported Estv channels and download its shared daily guide
  once per day. Both the UHF and country-feed refreshers use the same fetcher.
- Give the remaining large French batches time proportional to their channel
  count, capped at 15 minutes, instead of killing them after two minutes.
- Keep Canal+ Sport separate from Canal+ Sport 360.
- Ignore obsolete French UHF source snapshots according to the active grab
  plan, while preserving the files for diagnosis.
- The generated Estv export grew from 29 to 118 French rows with schedules.
  All 118 have programmes in the next 24 hours. This is export validation,
  not confirmation of UHF's local channel matching.

## Italy

- Update Sky Sport Uno, Arena and Basket to the current Sky Italia provider
  IDs. Correct LA7's XMLTV identity (it was incorrectly labelled LA7d).
- Request Sky Italia from today: its API rejects the previous day's request.
- Parse Super Guida TV's current HTML layout, using its published durations
  or the next programme start. Never invent the last programme's end time.
- Request only today, tomorrow and the following day, which the source supports.
- Omit a channel if any requested day fails; write the remaining complete
  channels atomically. Preserve the old snapshot if all channels fail.
- Remove the unidentified, generic DAZN entry from the sports list.
- Live validation returned 991 programmes for 12 general channels and 617
  programmes for eight sports channels. The two Italian Eurosport pages had
  no usable schedules and were omitted. The combined sports payload now has
  11 channels with schedules, up from six.

## Germany

- Assign the missing XMLTV ID to Sky Sport Premier League.
- Add MagentaTV schedules for Sky Sport Top Event, Sport 1/2, Bundesliga 1,
  F1, Premier League, Golf and News. Use the actual named channels rather than
  upstream's mismatched historical numbering (Top Event is not Sport 1).
- Sky Germany's endpoint returned HTTP 403; MagentaTV's public guide worked.
  Its sports snapshot grew from 174 programmes across three channels to 549
  across 11 channels.

## Repeat the checks

```sh
python3 scripts/refresh_uhf_epg.py --countries FR
python3 scripts/refresh_epg.py --countries FR IT DE --skip-editor-picks
python3 -m unittest discover -s tests
```

Italy and Germany are country/browser feeds; the saved Estv channel export
contains no Italian or German rows. These changes do not invent playlist
assignments for those countries. Publishing the fixes requires a commit and
deployment; subsequent scheduled country refreshes use the repaired fetchers.
