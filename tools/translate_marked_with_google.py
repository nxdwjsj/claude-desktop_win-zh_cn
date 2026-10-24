#!/usr/bin/env python3
"""Translate marked non-ICU frontend strings through Google Translate.

This is an explicit, opt-in helper for Claude version upgrades. It protects
placeholders, tags, code spans, and URLs before requesting a translation and
restores them only when every protected token survives the response.
"""
from __future__ import annotations

import argparse
import html
import json
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "resources" / "frontend-zh-CN.json"
MARKERS = ("\u5f85\u7ffb\u8bd1\uff1a", "\u5f85\u8865\u5145\u7ffb\u8bd1\uff1a")
ICU_RE = re.compile(r"\b(?:plural|select|selectordinal)\s*,", re.IGNORECASE)
PROTECTED_RE = re.compile(
    r"`[^`]*`|https?://\S+|</?[A-Za-z][^>]*>|\{[^{}]+\}",
    re.DOTALL,
)
RESULT_RE = re.compile(r'class="result-container">(.*?)</div>', re.DOTALL)


def strip_marker(value: str) -> str:
    for marker in MARKERS:
        if value.startswith(marker):
            return value[len(marker):]
    return value


def protect(value: str, prefix: str) -> tuple[str, dict[str, str]]:
    protected: dict[str, str] = {}

    def replace(match: re.Match[str]) -> str:
        token = f"{prefix}{len(protected)}END"
        protected[token] = match.group(0)
        return token

    return PROTECTED_RE.sub(replace, value), protected


def translate(value: str) -> str:
    url = "https://translate.google.com/m?sl=en&tl=zh-CN&q=" + urllib.parse.quote(value)
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(request, timeout=25) as response:
        body = response.read().decode("utf-8", errors="replace")
    match = RESULT_RE.search(body)
    if not match:
        raise ValueError("translation response did not include a result")
    return html.unescape(match.group(1).strip())


def polish(value: str) -> str:
    for source, target in {
        "克劳德": "Claude",
        "选项卡": "标签页",
        "您的": "你的",
        "您": "你",
        "使用量": "用量",
        "继续前进": "继续使用",
    }.items():
        value = value.replace(source, target)
    return value


def restore(value: str, protected: dict[str, str]) -> str | None:
    restored = value
    for token, original in protected.items():
        if token not in restored:
            return None
        restored = restored.replace(token, original)
    return polish(restored)


def translate_batch(items: list[tuple[str, dict[str, str]]]) -> list[str | None]:
    parts = []
    for index, (protected_source, _) in enumerate(items):
        parts.append(protected_source)
        if index < len(items) - 1:
            parts.append(f"[[[{index}]]]")
    translated = translate("\n".join(parts))
    parts = re.split(r"\s*\[\[\[\d+\]\]\]\s*", translated)
    if len(parts) != len(items):
        return [None] * len(items)
    return [restore(part, protected) for part, (_, protected) in zip(parts, items)]


def main() -> int:
    parser = argparse.ArgumentParser(description="Translate marked non-ICU frontend strings")
    parser.add_argument("--limit", type=int, default=200)
    parser.add_argument("--delay", type=float, default=0.4)
    parser.add_argument("--batch-size", type=int, default=10)
    args = parser.parse_args()

    data = json.loads(FRONTEND.read_text(encoding="utf-8"))
    candidates = [
        (key, value)
        for key, value in data.items()
        if isinstance(value, str) and value.startswith(MARKERS) and not ICU_RE.search(strip_marker(value))
    ]
    changed = 0
    skipped = 0
    failed = 0
    selected = candidates[:args.limit]
    index = 0
    while index < len(selected):
        key, current = selected[index]
        source = strip_marker(current)
        protected_source, protected = protect(source, "ZXPROTECT0_")
        if protected:
            group = [(key, current)]
            protected_group = [(protected_source, protected)]
        else:
            group = []
            protected_group = []
            while index < len(selected) and len(group) < args.batch_size:
                next_key, next_current = selected[index]
                next_source = strip_marker(next_current)
                next_protected_source, next_protected = protect(next_source, f"ZXPROTECT{len(group)}_")
                if next_protected:
                    break
                group.append((next_key, next_current))
                protected_group.append((next_protected_source, next_protected))
                index += 1
            if not group:
                continue
        try:
            translated_group = translate_batch(protected_group)
        except Exception as error:
            print(f"failed batch at {key}: {error}")
            failed += len(group)
            index += 1
            continue
        for (current_key, current_value), translated in zip(group, translated_group):
            current_source = strip_marker(current_value)
            if not translated or translated == current_source:
                print(f"skipped {current_key}: protected token mismatch or unchanged result")
                skipped += 1
                continue
            data[current_key] = translated
            changed += 1
        if protected:
            index += 1
        time.sleep(args.delay)

    if changed:
        FRONTEND.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"candidates={len(candidates)} changed={changed} skipped={skipped} failed={failed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
