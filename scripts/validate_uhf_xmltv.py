#!/usr/bin/env python3
"""Validate and summarize the generated UHF XMLTV export."""

from __future__ import annotations

import argparse
import gzip
import importlib.util
import json
import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_XML = ROOT / "web" / "data" / "uhf" / "epg.xml"
DEFAULT_GZIP = ROOT / "web" / "data" / "uhf" / "epg.xml.gz"
DEFAULT_CHANNELS = ROOT / "web" / "data" / "uhf" / "channels.json"
DEFAULT_SUMMARY = ROOT / "web" / "data" / "uhf" / "summary.json"
DEFAULT_VALIDATION = ROOT / "web" / "data" / "uhf" / "validation.json"
DEFAULT_PREVIEW = ROOT / "web" / "data" / "uhf" / "preview.json"

try:
    from xmltv_utils import iso_z, parse_xmltv_time
except ModuleNotFoundError:  # pragma: no cover - used by direct test imports
    _UTILS_PATH = Path(__file__).resolve().parent / "xmltv_utils.py"
    _spec = importlib.util.spec_from_file_location("xmltv_utils", _UTILS_PATH)
    if _spec is None or _spec.loader is None:
        raise
    _module = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(_module)
    iso_z = _module.iso_z
    parse_xmltv_time = _module.parse_xmltv_time

PLACEHOLDER_TITLES = {
    "no events",
    "no upcoming events",
    "nessun evento",
    "nessun evento in programma",
    "sin eventos",
    "aucun événement",
    "aucun evenement",
    "no hay eventos",
}
CHANNEL_ID_RE = re.compile(r"^uhf:\d+$")
OVERLAP_WARNING_RATIO = 0.5
MAX_PREVIEW_DESCRIPTION_CHARS = 220


@dataclass
class ParsedProgramme:
    element: ET.Element
    channel_id: str
    title: str
    start: datetime
    stop: datetime


def parse_iso_datetime(value: str) -> datetime:
    if not value:
        raise ValueError("missing ISO datetime")
    normalized = value.strip().replace("Z", "+00:00")
    return datetime.fromisoformat(normalized).astimezone(timezone.utc)


def relative_path(path: Path | None) -> str | None:
    if path is None:
        return None
    try:
        return str(path.resolve().relative_to(ROOT))
    except ValueError:
        return str(path)


def finding(severity: str, code: str, message: str, **extra) -> dict:
    item = {"severity": severity, "code": code, "message": message}
    item.update({key: value for key, value in extra.items() if value not in (None, "", [])})
    return item


def load_json(path: Path | None, default):
    if path is None or not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def parse_xml_root(path: Path) -> ET.Element:
    return ET.parse(path).getroot()


def parse_gzip_root(path: Path | None) -> ET.Element | None:
    if path is None or not path.exists():
        return None
    with gzip.open(path, "rb") as infile:
        return ET.parse(infile).getroot()


def xmltv_fingerprint(root: ET.Element) -> dict[str, list[tuple[str, ...]]]:
    """Return a stable structural fingerprint for comparing plain and gzipped XMLTV."""
    channels = sorted(channel.attrib.get("id", "") for channel in root.findall("channel"))
    programmes = sorted(
        (
            programme.attrib.get("channel", ""),
            programme.attrib.get("start", ""),
            programme.attrib.get("stop", ""),
            programme_title(programme),
        )
        for programme in root.findall("programme")
    )
    return {"channels": [(channel_id,) for channel_id in channels], "programmes": programmes}


def child_text(element: ET.Element, tag: str) -> str | None:
    child = element.find(tag)
    if child is None or child.text is None:
        return None
    text = child.text.strip()
    return text or None


def child_texts(element: ET.Element, tag: str) -> list[str]:
    values = []
    for child in element.findall(tag):
        if child.text and child.text.strip():
            values.append(child.text.strip())
    return values


def channel_display_names(channel: ET.Element) -> list[str]:
    return child_texts(channel, "display-name")


def channel_name(channel_id: str, channel_by_id: dict[str, ET.Element], channels_meta: dict[str, dict]) -> str:
    meta_name = channels_meta.get(channel_id, {}).get("name")
    if meta_name:
        return meta_name
    channel = channel_by_id.get(channel_id)
    if channel is not None:
        names = channel_display_names(channel)
        if names:
            return names[0]
    return channel_id


def programme_title(programme: ET.Element) -> str:
    return child_text(programme, "title") or ""


def programme_subtitle(programme: ET.Element) -> str | None:
    return child_text(programme, "sub-title")


def programme_description(programme: ET.Element) -> str | None:
    description = child_text(programme, "desc")
    if description and len(description) > MAX_PREVIEW_DESCRIPTION_CHARS:
        return description[: MAX_PREVIEW_DESCRIPTION_CHARS - 1].rstrip() + "…"
    return description


def programme_categories(programme: ET.Element) -> list[str]:
    return child_texts(programme, "category")


def programme_to_preview(parsed: ParsedProgramme) -> dict:
    return {
        "title": parsed.title,
        "subtitle": programme_subtitle(parsed.element),
        "description": programme_description(parsed.element),
        "categories": programme_categories(parsed.element),
        "startAt": iso_z(parsed.start),
        "endAt": iso_z(parsed.stop),
    }


def load_channels_meta(channels_json: list[dict]) -> dict[str, dict]:
    metadata = {}
    for row in channels_json:
        channel_id = row.get("custom_xmltv_id") or row.get("id")
        if channel_id:
            metadata[channel_id] = row
    return metadata


def parse_programmes(
    root: ET.Element,
    channel_by_id: dict[str, ET.Element],
    channels_meta: dict[str, dict],
    findings: list[dict],
) -> tuple[list[ParsedProgramme], dict[str, list[ParsedProgramme]]]:
    parsed: list[ParsedProgramme] = []
    by_channel: dict[str, list[ParsedProgramme]] = defaultdict(list)
    seen_exact: set[tuple[str, str, str, str]] = set()

    for index, programme in enumerate(root.findall("programme")):
        channel_id = programme.attrib.get("channel", "")
        title = programme_title(programme)
        start_raw = programme.attrib.get("start", "")
        stop_raw = programme.attrib.get("stop", "")
        name = channel_name(channel_id, channel_by_id, channels_meta)

        if not channel_id:
            findings.append(finding("error", "programme.missing_channel", "Programme is missing channel attribute", programmeIndex=index, title=title))
            continue
        if channel_id not in channel_by_id:
            findings.append(
                finding(
                    "error",
                    "programme.unknown_channel",
                    "Programme references a channel not declared in XMLTV",
                    channelId=channel_id,
                    channelName=name,
                    title=title,
                )
            )
        if not title:
            findings.append(finding("warning", "programme.empty_title", "Programme has an empty title", channelId=channel_id, channelName=name))
        elif re.sub(r"\s+", " ", title).strip().casefold() in PLACEHOLDER_TITLES:
            findings.append(
                finding(
                    "warning",
                    "programme.placeholder_title",
                    "Programme appears to be an empty-event placeholder",
                    channelId=channel_id,
                    channelName=name,
                    title=title,
                )
            )

        try:
            start = parse_xmltv_time(start_raw)
            stop = parse_xmltv_time(stop_raw)
        except ValueError as error:
            findings.append(
                finding(
                    "error",
                    "programme.invalid_time",
                    f"Programme has an unparsable start/stop time: {error}",
                    channelId=channel_id,
                    channelName=name,
                    title=title,
                    start=start_raw,
                    stop=stop_raw,
                )
            )
            continue
        if start >= stop:
            findings.append(
                finding(
                    "error",
                    "programme.invalid_time_range",
                    "Programme start time must be before stop time",
                    channelId=channel_id,
                    channelName=name,
                    title=title,
                    startAt=iso_z(start),
                    endAt=iso_z(stop),
                )
            )
            continue

        exact_key = (channel_id, start_raw, stop_raw, title)
        if exact_key in seen_exact:
            findings.append(
                finding(
                    "warning",
                    "programme.duplicate_exact_slot",
                    "Programme duplicates an existing channel/start/stop/title slot",
                    channelId=channel_id,
                    channelName=name,
                    title=title,
                    startAt=iso_z(start),
                    endAt=iso_z(stop),
                )
            )
        seen_exact.add(exact_key)

        parsed_programme = ParsedProgramme(programme, channel_id, title, start, stop)
        parsed.append(parsed_programme)
        if channel_id in channel_by_id:
            by_channel[channel_id].append(parsed_programme)

    for programmes in by_channel.values():
        programmes.sort(key=lambda item: (item.start, item.stop, item.title))
    return parsed, dict(by_channel)


def add_channel_overlap_findings(
    channel_id: str,
    programmes: list[ParsedProgramme],
    channel_by_id: dict[str, ET.Element],
    channels_meta: dict[str, dict],
    findings: list[dict],
) -> None:
    seen_slots: dict[tuple[datetime, datetime], str] = {}
    warned_overlaps = 0
    name = channel_name(channel_id, channel_by_id, channels_meta)
    for current in programmes:
        slot = (current.start, current.stop)
        prior_title = seen_slots.get(slot)
        if prior_title is not None and prior_title != current.title:
            findings.append(
                finding(
                    "warning",
                    "programme.same_slot_different_title",
                    "Channel has different programme titles for the same start/stop slot",
                    channelId=channel_id,
                    channelName=name,
                    title=current.title,
                    otherTitle=prior_title,
                    startAt=iso_z(current.start),
                    endAt=iso_z(current.stop),
                )
            )
        seen_slots.setdefault(slot, current.title)

    for previous, current in zip(programmes, programmes[1:]):
        if current.start < previous.stop:
            overlap = (min(previous.stop, current.stop) - current.start).total_seconds()
            shorter = min((previous.stop - previous.start).total_seconds(), (current.stop - current.start).total_seconds())
            if shorter > 0 and overlap / shorter >= OVERLAP_WARNING_RATIO and warned_overlaps < 5:
                warned_overlaps += 1
                findings.append(
                    finding(
                        "warning",
                        "programme.heavy_overlap",
                        "Channel has programmes whose times overlap substantially",
                        channelId=channel_id,
                        channelName=name,
                        title=current.title,
                        otherTitle=previous.title,
                        startAt=iso_z(current.start),
                        endAt=iso_z(current.stop),
                    )
                )


def build_channel_reports(
    channel_by_id: dict[str, ET.Element],
    programmes_by_channel: dict[str, list[ParsedProgramme]],
    channels_meta: dict[str, dict],
    findings: list[dict],
    now: datetime,
) -> list[dict]:
    reports = []
    next_24h_end = now + timedelta(hours=24)
    for channel_id in sorted(channel_by_id, key=lambda key: channel_name(key, channel_by_id, channels_meta).casefold()):
        channel = channel_by_id[channel_id]
        meta = channels_meta.get(channel_id, {})
        programmes = programmes_by_channel.get(channel_id, [])
        current = next((program for program in programmes if program.start <= now < program.stop), None)
        upcoming = [program for program in programmes if program.stop > now and program.start < next_24h_end]
        next_programme = next((program for program in programmes if program.start >= now), None)
        name = channel_name(channel_id, channel_by_id, channels_meta)

        if not programmes:
            findings.append(finding("warning", "channel.no_programmes", "Channel has no programmes", channelId=channel_id, channelName=name))
        else:
            if current is None:
                findings.append(
                    finding(
                        "warning",
                        "channel.no_current_programme",
                        "Channel has no programme covering validation time",
                        channelId=channel_id,
                        channelName=name,
                    )
                )
            if not upcoming:
                findings.append(
                    finding(
                        "warning",
                        "channel.no_next_24h",
                        "Channel has no programmes airing or starting in the next 24 hours",
                        channelId=channel_id,
                        channelName=name,
                    )
                )
            if programmes[-1].stop < now:
                findings.append(
                    finding(
                        "warning",
                        "channel.stale_last_programme",
                        "Channel's last programme ended before validation time",
                        channelId=channel_id,
                        channelName=name,
                        lastEndAt=iso_z(programmes[-1].stop),
                    )
                )
            if programmes[0].start > now + timedelta(hours=12):
                findings.append(
                    finding(
                        "warning",
                        "channel.first_programme_late",
                        "Channel's first programme starts more than 12 hours after validation time",
                        channelId=channel_id,
                        channelName=name,
                        firstStartAt=iso_z(programmes[0].start),
                    )
                )
        add_channel_overlap_findings(channel_id, programmes, channel_by_id, channels_meta, findings)

        icon = channel.find("icon")
        reports.append(
            {
                "id": channel_id,
                "name": name,
                "displayNames": channel_display_names(channel),
                "category": meta.get("category"),
                "targetXmltvId": meta.get("target_xmltv_id"),
                "targetName": meta.get("target_name"),
                "targetCountry": meta.get("target_country"),
                "targetGuideSites": meta.get("target_guide_sites"),
                "logoUrl": meta.get("logo_url") or (icon.attrib.get("src") if icon is not None else None),
                "programmeCount": len(programmes),
                "firstStartAt": iso_z(programmes[0].start) if programmes else None,
                "lastEndAt": iso_z(programmes[-1].stop) if programmes else None,
                "currentProgramTitle": current.title if current else None,
                "nextProgramTitle": next_programme.title if next_programme else None,
            }
        )
    return reports


def build_preview(
    generated_at: str | None,
    channel_reports: list[dict],
    programmes_by_channel: dict[str, list[ParsedProgramme]],
    findings: list[dict],
    now: datetime,
    preview_hours_before: int,
    preview_hours_after: int,
) -> dict:
    window_start = now - timedelta(hours=preview_hours_before)
    window_end = now + timedelta(hours=preview_hours_after)
    finding_codes_by_channel: dict[str, list[str]] = defaultdict(list)
    for item in findings:
        channel_id = item.get("channelId")
        if channel_id:
            finding_codes_by_channel[channel_id].append(item["code"])

    channels = []
    for report in channel_reports:
        channel_id = report["id"]
        programmes = [
            programme_to_preview(program)
            for program in programmes_by_channel.get(channel_id, [])
            if program.stop > window_start and program.start < window_end
        ]
        channels.append(
            {
                "id": channel_id,
                "name": report.get("name"),
                "displayNames": report.get("displayNames") or [],
                "category": report.get("category"),
                "targetCountry": report.get("targetCountry"),
                "targetXmltvId": report.get("targetXmltvId"),
                "targetName": report.get("targetName"),
                "targetGuideSites": report.get("targetGuideSites"),
                "logoUrl": report.get("logoUrl"),
                "warnings": sorted({code for code in finding_codes_by_channel.get(channel_id, []) if not code.startswith("mapping.")}),
                "programs": programmes,
            }
        )
    return {
        "generatedAt": generated_at,
        "validatedAt": iso_z(now),
        "previewWindow": {"startAt": iso_z(window_start), "endAt": iso_z(window_end)},
        "channels": channels,
    }


def validate(
    *,
    xml_path: Path = DEFAULT_XML,
    gzip_path: Path | None = DEFAULT_GZIP,
    channels_path: Path | None = DEFAULT_CHANNELS,
    summary_path: Path | None = DEFAULT_SUMMARY,
    now: datetime | None = None,
    max_age_hours: int = 72,
    preview_hours_before: int = 4,
    preview_hours_after: int = 20,
) -> tuple[dict, dict]:
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    findings: list[dict] = []
    root = parse_xml_root(xml_path)
    gzip_root = parse_gzip_root(gzip_path)
    channels_json = load_json(channels_path, [])
    summary_json = load_json(summary_path, {})
    channels_meta = load_channels_meta(channels_json if isinstance(channels_json, list) else [])

    channels = root.findall("channel")
    programmes = root.findall("programme")
    channel_by_id: dict[str, ET.Element] = {}
    channel_id_counts = Counter(channel.attrib.get("id", "") for channel in channels)

    if not channels:
        findings.append(finding("error", "xmltv.no_channels", "XMLTV export contains no channels"))
    if not programmes:
        findings.append(finding("error", "xmltv.no_programmes", "XMLTV export contains no programmes"))

    for channel in channels:
        channel_id = channel.attrib.get("id", "")
        if not channel_id:
            findings.append(finding("error", "channel.missing_id", "Channel is missing id attribute"))
            continue
        if channel_id_counts[channel_id] > 1:
            findings.append(finding("error", "channel.duplicate_id", "Channel id is duplicated", channelId=channel_id))
        if not CHANNEL_ID_RE.match(channel_id):
            findings.append(finding("warning", "channel.non_uhf_id", "Channel id does not use expected uhf:<number> format", channelId=channel_id))
        channel_by_id.setdefault(channel_id, channel)

    if gzip_root is not None:
        gzip_channel_count = len(gzip_root.findall("channel"))
        gzip_programme_count = len(gzip_root.findall("programme"))
        if gzip_channel_count != len(channels) or gzip_programme_count != len(programmes):
            findings.append(
                finding(
                    "error",
                    "gzip.count_mismatch",
                    "Gzipped XMLTV counts do not match plain XMLTV counts",
                    gzipChannels=gzip_channel_count,
                    gzipProgrammes=gzip_programme_count,
                    xmlChannels=len(channels),
                    xmlProgrammes=len(programmes),
                )
            )
        elif xmltv_fingerprint(gzip_root) != xmltv_fingerprint(root):
            findings.append(
                finding(
                    "error",
                    "gzip.content_mismatch",
                    "Gzipped XMLTV content does not match plain XMLTV content",
                )
            )

    xml_ids = set(channel_by_id)
    json_ids = set(channels_meta)
    for missing_id in sorted(json_ids - xml_ids)[:100]:
        meta = channels_meta.get(missing_id, {})
        findings.append(
            finding(
                "warning",
                "mapping.channel_missing_from_xml",
                "Channel exists in channels.json but not in XMLTV export",
                channelId=missing_id,
                channelName=meta.get("name"),
            )
        )
    for extra_id in sorted(xml_ids - json_ids)[:100]:
        findings.append(
            finding(
                "warning",
                "mapping.xml_channel_missing_from_channels_json",
                "Channel exists in XMLTV export but not in channels.json",
                channelId=extra_id,
                channelName=channel_name(extra_id, channel_by_id, channels_meta),
            )
        )

    generated_at = summary_json.get("generatedAt") if isinstance(summary_json, dict) else None
    generated_dt = None
    tv_date = root.attrib.get("date")
    for source_name, value in (("summary.generatedAt", generated_at), ("tv.date", tv_date)):
        if not value:
            continue
        try:
            parsed = parse_iso_datetime(value)
        except ValueError:
            findings.append(finding("warning", "export.invalid_generated_at", f"{source_name} is not parseable", value=value))
            continue
        if source_name == "summary.generatedAt":
            generated_dt = parsed
    if generated_dt is not None and now - generated_dt > timedelta(hours=max_age_hours):
        findings.append(
            finding(
                "warning",
                "export.stale",
                f"UHF XMLTV export is older than {max_age_hours} hours",
                generatedAt=iso_z(generated_dt),
                validatedAt=iso_z(now),
            )
        )

    parsed_programmes, programmes_by_channel = parse_programmes(root, channel_by_id, channels_meta, findings)
    channel_reports = build_channel_reports(channel_by_id, programmes_by_channel, channels_meta, findings, now)

    severity_counts = Counter(item["severity"] for item in findings)
    findings_by_channel = defaultdict(Counter)
    for item in findings:
        channel_id = item.get("channelId")
        if channel_id:
            findings_by_channel[channel_id][item["severity"]] += 1
    for report in channel_reports:
        counts = findings_by_channel.get(report["id"], Counter())
        report["errorCount"] = counts.get("error", 0)
        report["warningCount"] = counts.get("warning", 0)

    starts = [programme.start for programme in parsed_programmes]
    stops = [programme.stop for programme in parsed_programmes]
    report = {
        "generatedAt": generated_at,
        "validatedAt": iso_z(now),
        "source": {
            "xml": relative_path(xml_path),
            "gzip": relative_path(gzip_path),
            "channelsJson": relative_path(channels_path),
            "summaryJson": relative_path(summary_path),
        },
        "counts": {
            "channels": len(channels),
            "programmes": len(programmes),
            "channelsWithCurrent": sum(1 for channel_id in channel_by_id if any(p.start <= now < p.stop for p in programmes_by_channel.get(channel_id, []))),
            "channelsWithNext24h": sum(1 for channel_id in channel_by_id if any(p.stop > now and p.start < now + timedelta(hours=24) for p in programmes_by_channel.get(channel_id, []))),
            "errors": severity_counts.get("error", 0),
            "warnings": severity_counts.get("warning", 0),
            "info": severity_counts.get("info", 0),
        },
        "coverage": {
            "firstProgrammeStartAt": iso_z(min(starts)) if starts else None,
            "lastProgrammeEndAt": iso_z(max(stops)) if stops else None,
            "now": iso_z(now),
        },
        "findings": findings,
        "channels": channel_reports,
    }
    preview = build_preview(generated_at, channel_reports, programmes_by_channel, findings, now, preview_hours_before, preview_hours_after)
    return report, preview


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_XML)
    parser.add_argument("--gzip", type=Path, default=DEFAULT_GZIP)
    parser.add_argument("--channels", type=Path, default=DEFAULT_CHANNELS)
    parser.add_argument("--summary", type=Path, default=DEFAULT_SUMMARY)
    parser.add_argument("--out-validation", type=Path, default=DEFAULT_VALIDATION)
    parser.add_argument("--out-preview", type=Path, default=DEFAULT_PREVIEW)
    parser.add_argument("--max-age-hours", type=int, default=72)
    parser.add_argument("--preview-hours-before", type=int, default=4)
    parser.add_argument("--preview-hours-after", type=int, default=20)
    parser.add_argument("--strict-warnings", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    try:
        report, preview = validate(
            xml_path=args.input,
            gzip_path=args.gzip,
            channels_path=args.channels,
            summary_path=args.summary,
            max_age_hours=args.max_age_hours,
            preview_hours_before=args.preview_hours_before,
            preview_hours_after=args.preview_hours_after,
        )
    except (ET.ParseError, OSError, json.JSONDecodeError, gzip.BadGzipFile) as error:
        print(f"UHF XMLTV validation failed before report generation: {error}", file=sys.stderr)
        return 1

    write_json(args.out_validation, report)
    write_json(args.out_preview, preview)
    print(json.dumps({"counts": report["counts"], "coverage": report["coverage"]}, ensure_ascii=False, indent=2))

    if report["counts"]["errors"]:
        return 1
    if args.strict_warnings and report["counts"]["warnings"]:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
