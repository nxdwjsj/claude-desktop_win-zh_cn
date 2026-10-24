#!/usr/bin/env python3
r"""结构级校验器：比对英文原文与中文译文的关键结构。

判据（只比结构，不比自然语言——规范要求翻译 ICU 分支内的文字）：
  1. key 集合 + 顺序完全一致
  2. 具名占位符集合一致（只取真正的变量名，含 ICU 选择器变量）
  3. ICU 块结构一致（类型词 + 变量名 + 分支键，按语法位置解析）
  4. `#` 数量一致（ICU 里代表计数的特殊 token）
  5. printf 占位符数量一致
  6. HTML/XML 标签名多重集一致
  7. 值均为 str、UTF-8 无 BOM、不出现字面 \uXXXX 转义

用法:
  python validate_structure.py <batch-name> [...]        # 校验 <name>.done.json
  python validate_structure.py --out <name>              # 校验 <name>.json + <name>.out.txt
"""
from __future__ import annotations

import argparse
import io
import json
import os
import re
import sys

WORK = r"D:\Project\DeepSeek\out\zh-work"

# 只解析真正的 ICU 块：{var, kind, ...}。类型词仅在这些块内有效，
# 避免把正文里的 "vendor, date, amount" 误判成 ICU date 类型。
ICU_KINDS = "plural|select|selectordinal|number|date|time|duration|list"
ICU_HEAD_RE = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*,\s*(" + ICU_KINDS + r")\s*(?:,|$)")
TAG_RE = re.compile(r"</?([A-Za-z][A-Za-z0-9]*)")
PRINTF_RE = re.compile(r"%[sdif]")


def _match_brace(text: str, start: int) -> int:
    """返回与 text[start]=='{' 配对的 '}' 的下标；找不到返回 -1。"""
    depth = 0
    for j in range(start, len(text)):
        if text[j] == "{":
            depth += 1
        elif text[j] == "}":
            depth -= 1
            if depth == 0:
                return j
    return -1


def parse_icu(text: str) -> list[dict]:
    """只解析真正的 ICU 块，返回结构描述列表。

    识别规则：只有当 `{` 后紧跟 `名字 , 类型词 ,` 时才算 ICU 块
    （如 `{count, plural, ...}`、`{action, select, ...}`）。
    这彻底避免了在普通文案里误判——`Pre-clone {repo}`、`clone {x}`、
    `vendor, date, amount` 都不会被当成 ICU。

    严格按语法位置提取分支键：分支键 = 紧跟块起始 `{` 或上一分支体 `}`
    之后的标识符/`=数字`，且其后紧跟 `{`。
    这样既能识别 select 的自定义分支键（both/author/web/phone/…），
    也不会把正文里的英文单词当成结构。
    """
    blocks: list[dict] = []
    i, n = 0, len(text)
    while i < n:
        if text[i] != "{":
            i += 1
            continue
        end = _match_brace(text, i)
        if end < 0:
            i += 1
            continue
        body = text[i + 1 : end]
        head = ICU_HEAD_RE.match(body)
        if not head:
            # 不是 ICU 块；但仍要进入其内部继续找嵌套的 ICU 块
            i += 1
            continue

        var, kind = head.group(1), head.group(2)
        rest = body[head.end() :]
        branches: list[str] = []
        hashes = 0
        pos = 0
        m = re.match(r"\s*", rest)
        pos = m.end() if m else 0
        while pos < len(rest):
            key_m = re.match(r"\s*(=\d+|[A-Za-z_][A-Za-z0-9_]*|\S+?)\s*\{", rest[pos:])
            if not key_m:
                break
            branches.append(key_m.group(1))
            brace_at = pos + key_m.end() - 1
            bend = _match_brace(rest, brace_at)
            if bend < 0:
                break
            branches[-1] = key_m.group(1)
            pos = bend + 1

        if kind in ("plural", "selectordinal"):
            branches = [b for b in branches if b in ("zero", "one", "two", "few", "many", "other") or b.startswith("=")]

        hashes = body.count("#")
        blocks.append({
            "var": var,
            "kind": kind,
            "branches": branches,
            "hashes": hashes,
            "span": (i, end),
        })
        # 顶层块内部的嵌套 ICU 块（如 {n, plural, one {{x, number}} other {}}）也要收集
        for b in parse_icu(body):
            nvar = b["var"]
            if nvar != var:
                blocks.append(b)
        i = end + 1
    return blocks


def _skeleton_vars(text: str) -> list[str]:
    """提取所有非 ICU 的普通占位符变量名，如 {name} {repo}。"""
    blocks = parse_icu(text)
    spans = [b["span"] for b in blocks]
    masked = list(text)
    for s, e in spans:
        for k in range(s, e + 1):
            masked[k] = " "
    names = re.findall(r"\{\s*([A-Za-z_][A-Za-z0-9_]*)\s*(?=[},])", "".join(masked))
    # ICU 选择器变量本身也算变量
    names += [b["var"] for b in blocks]
    return sorted(set(names))


def signature(text: str) -> dict:
    blocks = parse_icu(text)
    return {
        "vars": _skeleton_vars(text),
        "icu": [(b["kind"], b["var"], tuple(b["branches"])) for b in sorted(blocks, key=lambda b: b["span"])],
        "hash": sum(b["hashes"] for b in blocks),
        "printf": len(PRINTF_RE.findall(text)),
        "tags": sorted(TAG_RE.findall(text)),
    }


def check(en: str, zh: str) -> list[str]:
    e, z = signature(en), signature(zh)
    errs: list[str] = []
    if e["vars"] != z["vars"]:
        lost = sorted(set(e["vars"]) - set(z["vars"]))
        added = sorted(set(z["vars"]) - set(e["vars"]))
        if lost:
            errs.append(f"丢失变量 {lost}")
        if added:
            errs.append(f"凭空多出变量 {added}（会导致界面显示异常）")
    if e["icu"] != z["icu"]:
        e_sorted = sorted(e["icu"])
        z_sorted = sorted(z["icu"])
        if e_sorted != z_sorted:
            missing = [x for x in e_sorted if x not in z_sorted]
            added = [x for x in z_sorted if x not in e_sorted]
            if missing:
                errs.append(f"ICU 块丢失或结构改变 {missing}")
            if added:
                errs.append(f"ICU 块凭空多出 {added}")
            if not missing and not added:
                errs.append(f"ICU 块数量不一致 {len(e['icu'])} -> {len(z['icu'])}")
    if e["hash"] != z["hash"]:
        errs.append(f"ICU # 数量不一致 {e['hash']} -> {z['hash']}")
    if e["printf"] != z["printf"]:
        errs.append(f"printf 数量不一致 {e['printf']} -> {z['printf']}")
    if e["tags"] != z["tags"]:
        errs.append(f"HTML 标签不一致 {e['tags']} -> {z['tags']}")
    return errs


def load_pairs(name: str, mode: str) -> tuple[dict, dict, list[str]]:
    """返回 (source, translated, errors)"""
    problems: list[str] = []
    if mode == "done":
        sp = os.path.join(WORK, name + ".json")
        dp = os.path.join(WORK, name + ".done.json")
        if not os.path.exists(dp):
            return {}, {}, [f"{name}: 缺少 {os.path.basename(dp)}"]
        src = json.load(io.open(sp, encoding="utf-8"))
        raw = io.open(dp, "rb").read()
        if raw.startswith(b"\xef\xbb\xbf"):
            problems.append(f"{name}: .done.json 含 BOM")
        tr = json.loads(raw.decode("utf-8"))
    else:
        sp = os.path.join(WORK, name + ".json")
        op = os.path.join(WORK, name + ".out.txt")
        if not os.path.exists(op):
            return {}, {}, [f"{name}: 缺少 {os.path.basename(op)}"]
        src = json.load(io.open(sp, encoding="utf-8"))
        ks = list(src)
        indexed: dict[int, str] = {}
        for line in io.open(op, encoding="utf-8"):
            line = line.rstrip("\n")
            if not line.strip() or line.startswith("<<<IDX"):
                continue
            i, _, zh = line.partition("\t")
            if i.strip().isdigit():
                indexed[int(i)] = zh
        missing = [i for i in range(len(ks)) if i not in indexed]
        if missing:
            problems.append(f"{name}: .out.txt 缺少 {len(missing)} 条（例 {missing[:5]}）")
        tr = {ks[i]: indexed[i] for i in sorted(indexed) if i < len(ks)}
    return src, tr, problems


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("names", nargs="+")
    ap.add_argument("--out", action="store_true", help="校验 <name>.json + <name>.out.txt 模式")
    args = ap.parse_args()

    mode = "out" if args.out else "done"
    total_bad = 0
    total_items = 0
    for name in args.names:
        src, tr, problems = load_pairs(name, mode)
        if not src:
            print(f"[MISS] {name}: {'; '.join(problems)}")
            total_bad += 1
            continue
        if set(src) != set(tr):
            miss = sorted(set(src) - set(tr))[:5]
            extra = sorted(set(tr) - set(src))[:5]
            problems.append(f"key 不一致 缺{len(set(src)-set(tr))} 多{len(set(tr)-set(src))} 例缺{miss} 例多{extra}")
        bad = []
        cjk = re.compile(r"[\u4e00-\u9fff]")
        zh_count = 0
        for k, en in src.items():
            zh = tr.get(k)
            if not isinstance(zh, str):
                if k in tr:
                    bad.append((k, "值不是字符串", en, repr(zh)))
                continue
            if "\\u" in zh and "\\u" not in en:
                bad.append((k, "出现 \\uXXXX 字面转义", en, zh))
            if cjk.search(zh):
                zh_count += 1
            errs = check(en, zh)
            if errs:
                bad.append((k, "; ".join(errs), en, zh))
        total_items += len(src)
        status = "OK  " if not problems and not bad else "FAIL"
        print(f"[{status}] {name:<24} entries={len(src):<5} 含中文={zh_count:<5} 结构缺陷={len(bad)}")
        for p in problems:
            print("       -", p)
        for k, why, en, zh in bad[:6]:
            print(f"       - {k}: {why}")
            print(f"           EN: {en[:100]!r}")
            print(f"           ZH: {zh[:100]!r}")
        if len(bad) > 6:
            print(f"       ... 另有 {len(bad) - 6} 条")
        if problems or bad:
            total_bad += 1

    print(f"\n总计 {total_items} 条，失败批次 {total_bad} 个")
    return 1 if total_bad else 0


if __name__ == "__main__":
    sys.exit(main())
