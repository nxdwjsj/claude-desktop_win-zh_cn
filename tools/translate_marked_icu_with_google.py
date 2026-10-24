#!/usr/bin/env python3
"""Translate marked ICU frontend strings without changing their structure."""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import check_i18n_coverage as coverage
from tools import sync_i18n_from_installed as sync
from tools import translate_marked_with_google as google

FRONTEND = ROOT / "resources" / "frontend-zh-CN.json"
MARKERS = ("\u5f85\u7ffb\u8bd1\uff1a", "\u5f85\u8865\u5145\u7ffb\u8bd1\uff1a")
ICU_KIND_RE = re.compile(r"\b(?:plural|select|selectordinal)\s*,", re.IGNORECASE)
BRANCH_EXACT = {
    "# minute": "# \u5206\u949f",
    "# minutes": "# \u5206\u949f",
    "# second": "# \u79d2",
    "# seconds": "# \u79d2",
    "# channel": "# \u4e2a\u9891\u9053",
    "# channels": "# \u4e2a\u9891\u9053",
    "# project": "# \u4e2a\u9879\u76ee",
    "all # projects": "\u6240\u6709 # \u4e2a\u9879\u76ee",
    "# character": "# \u4e2a\u5b57\u7b26",
    "# characters": "# \u4e2a\u5b57\u7b26",
    "member": "\u6210\u5458",
    "group": "\u7ec4",
}


def strip_marker(value: str) -> str:
    for marker in MARKERS:
        if value.startswith(marker):
            return value[len(marker):]
    return value


def matching_brace(value: str, start: int) -> int:
    depth = 0
    for index in range(start, len(value)):
        char = value[index]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return index
    return -1


def split_top_level(value: str, limit: int) -> list[str]:
    parts = []
    start = 0
    depth = 0
    for index, char in enumerate(value):
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
        elif char == "," and depth == 0 and len(parts) < limit:
            parts.append(value[start:index])
            start = index + 1
    parts.append(value[start:])
    return parts


def translate_plain(value: str) -> str:
    if not value.strip():
        return value
    protected, mapping = google.protect(value, "ZXICU_")
    translated = google.translate(protected)
    restored = google.restore(translated, mapping)
    return restored.replace("\uff03", "#") if restored else value


def translate_branch(content: str) -> str:
    leading = content[:len(content) - len(content.lstrip())]
    trailing = content[len(content.rstrip()):]
    translated = BRANCH_EXACT.get(content.strip())
    if translated is not None:
        return leading + translated + trailing
    return translate_with_icu(content)


def translate_icu_block(block: str) -> str:
    inner = block[1:-1]
    parts = split_top_level(inner, 2)
    if len(parts) != 3 or parts[1].strip().lower() not in {"plural", "select", "selectordinal"}:
        return block
    variable, kind, option_text = parts[0].strip(), parts[1].strip(), parts[2]
    result = []
    index = 0
    while index < len(option_text):
        while index < len(option_text) and option_text[index].isspace():
            index += 1
        if index >= len(option_text):
            break
        label_start = index
        while index < len(option_text) and not option_text[index].isspace() and option_text[index] != "{":
            index += 1
        label = option_text[label_start:index]
        while index < len(option_text) and option_text[index].isspace():
            index += 1
        if not label or index >= len(option_text) or option_text[index] != "{":
            return block
        end = matching_brace(option_text, index)
        if end == -1:
            return block
        content = option_text[index + 1:end]
        result.append(f"{label} {{{translate_branch(content)}}}")
        index = end + 1
    return "{" + f"{variable}, {kind}, " + " ".join(result) + "}"


def translate_with_icu(value: str) -> str:
    blocks: list[str] = []
    output = []
    index = 0
    while index < len(value):
        if value[index] != "{":
            output.append(value[index])
            index += 1
            continue
        end = matching_brace(value, index)
        if end == -1:
            output.append(value[index])
            index += 1
            continue
        block = value[index:end + 1]
        if ICU_KIND_RE.search(block):
            token = f"ZXICUBLOCK{len(blocks)}END"
            blocks.append(translate_icu_block(block))
            output.append(token)
        else:
            output.append(block)
        index = end + 1
    skeleton = "".join(output)
    if re.fullmatch(r"(?:ZXICUBLOCK\d+END)+", skeleton):
        translated = skeleton
    else:
        translated = translate_plain(skeleton)
    for index, block in enumerate(blocks):
        translated = translated.replace(f"ZXICUBLOCK{index}END", block)
    return translated


def main() -> int:
    parser = argparse.ArgumentParser(description="Translate marked ICU frontend strings")
    parser.add_argument("--limit", type=int, default=10)
    args = parser.parse_args()

    data = json.loads(FRONTEND.read_text(encoding="utf-8"))
    changed = 0
    technical = 0
    translated = 0
    for key, current in list(data.items()):
        if not isinstance(current, str) or not current.startswith(MARKERS):
            continue
        source = strip_marker(current)
        if not ICU_KIND_RE.search(source):
            if sync.looks_technical_or_placeholder(source) or coverage.classify_value(source) is None:
                data[key] = source
                changed += 1
                technical += 1
            continue
        if translated >= args.limit:
            continue
        try:
            next_value = translate_with_icu(source)
        except Exception as error:
            print(f"skipped {key}: {error}")
            continue
        if next_value != source:
            data[key] = next_value
            changed += 1
            translated += 1
    if changed:
        FRONTEND.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"changed={changed} technical={technical} icu_translated={translated}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
