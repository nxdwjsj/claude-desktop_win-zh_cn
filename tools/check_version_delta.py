#!/usr/bin/env python3
r"""检查 Claude Desktop 是否有新版本，并报告汉化需要补多少翻译。

用途：Claude Desktop 升级后运行本脚本，它会告诉你：
  - 当前安装的版本 vs 上次汉化时的版本
  - 新版新增了多少 i18n key
  - 其中多少条已有中文、多少条需要新翻译

用法:
  python check_version_delta.py
"""
from __future__ import annotations

import io
import json
import os
import pathlib
import re
import subprocess

CJK = re.compile(r"[\u4e00-\u9fff]")
TOOL = pathlib.Path(r"D:\claude-desktop_win-zh_cn-0.1.0")
STATE = pathlib.Path(os.environ["LOCALAPPDATA"]) / "Claude-zh-CN-official-backup" / "patched-version.json"


def find_app() -> pathlib.Path | None:
    """定位 Claude 的 app 目录。

    注意：不要靠 glob 枚举 C:\\Program Files\\WindowsApps —— 该目录枚举在
    普通权限下会返回空（ACL 限制），但 Get-AppxPackage 与直接路径访问可用。
    因此优先用 Get-AppxPackage，再退回直接探测。
    """
    try:
        r = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "$p=Get-AppxPackage -Name Claude -ErrorAction SilentlyContinue | "
             "Sort-Object Version -Descending | Select-Object -First 1; "
             "if ($p) { $p.InstallLocation }"],
            capture_output=True, text=True, timeout=15,
        )
        loc = (r.stdout or "").strip()
        if loc:
            for cand in (pathlib.Path(loc) / "app", pathlib.Path(loc)):
                if (cand / "resources" / "en-US.json").exists():
                    return cand
    except (OSError, subprocess.SubprocessError):
        pass

    wa = pathlib.Path(r"C:\Program Files\WindowsApps")
    if wa.exists():
        for d in wa.glob("Claude_*"):
            cand = d / "app"
            if (cand / "resources" / "en-US.json").exists():
                return cand

    alt = pathlib.Path(os.environ.get("LOCALAPPDATA", "")) / "AnthropicClaude"
    for cand in (alt / "app", alt):
        if (cand / "resources" / "en-US.json").exists():
            return cand
    return None


def flat(d, p=""):
    for k, v in d.items():
        if isinstance(v, dict):
            yield from flat(v, p + k + ".")
        else:
            yield p + k, v


def main() -> int:
    app = find_app()
    if not app:
        print("[X] 未找到 Claude 安装目录")
        return 1
    res = app / "resources"

    # 版本号：app/version 是 Electron 版本，包名里才是 Claude 版本
    pkg_ver = ""
    m = re.search(r"Claude_([\d.]+)_x64", str(app))
    if m:
        pkg_ver = m.group(1)

    cfg = pathlib.Path(os.environ["LOCALAPPDATA"]) / "Claude-3p" / "config.json"
    cfg_ver = ""
    if cfg.exists():
        try:
            cfg_ver = json.loads(cfg.read_text(encoding="utf-8")).get("updaterLastSeenVersion", "")
        except (OSError, json.JSONDecodeError):
            pass

    lines = []
    lines.append("Claude 安装目录 : %s" % app)
    lines.append("包版本(pkg)     : %s" % (pkg_ver or "未知"))
    lines.append("配置版本(updater): %s" % (cfg_ver or "未知"))

    # 上次汉化记录
    last = None
    if STATE.exists():
        try:
            last = json.loads(STATE.read_text(encoding="utf-8"))
            lines.append("上次汉化版本    : %s" % last.get("version", "未知"))
        except (OSError, json.JSONDecodeError):
            pass
    else:
        lines.append("上次汉化版本    : 无记录（首次运行本脚本）")

    lines.append("")
    lines.append("=" * 52)
    lines.append("覆盖率检查")
    lines.append("=" * 52)

    total_need = 0
    for label, en_rel, zh_rel in (
        ("壳层 desktop", "en-US.json", "zh-CN.json"),
        ("前端 frontend", "ion-dist/i18n/en-US.json", "ion-dist/i18n/zh-CN.json"),
    ):
        enp, zhp = res / en_rel, res / zh_rel
        if not enp.exists():
            lines.append("%-14s [X] 缺少 en-US 资源" % label)
            continue
        en = dict(flat(json.loads(enp.read_text(encoding="utf-8"))))
        zh = {}
        if zhp.exists():
            zh = dict(flat(json.loads(zhp.read_text(encoding="utf-8"))))
        missing_key = [k for k in en if k not in zh]
        needs = [k for k in en if k in zh and not (isinstance(zh[k], str) and CJK.search(zh[k]))]
        tr = len(en) - len(missing_key) - len(needs)
        pct = 100.0 * tr / len(en) if en else 0
        total_need += len(missing_key) + len(needs)
        lines.append("%-14s 总 %d 条, 中文 %d 条 (%.1f%%)" % (label, len(en), tr, pct))
        lines.append("%-14s   缺 key %d 条, 缺翻译 %d 条" % ("", len(missing_key), len(needs)))

    lines.append("")
    if total_need == 0:
        lines.append("[OK] 汉化覆盖完整，无需补翻译。")
    else:
        lines.append("[!] 有 %d 条文案需要补翻/补 key。" % total_need)
        lines.append("    直接运行 update-zh-cn.ps1 可自动补齐 key（新文案先显示英文），")
        lines.append("    把本脚本输出发给 AI 助手可继续补齐中文翻译。")

    # 记录本次版本
    try:
        STATE.parent.mkdir(parents=True, exist_ok=True)
        STATE.write_text(
            json.dumps({"version": pkg_ver, "app": str(app), "needs": total_need},
                       ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except OSError:
        pass

    out = "\n".join(lines)
    report = TOOL / "version-report.txt"
    try:
        report.write_text(out + "\n", encoding="utf-8")
    except OSError:
        pass
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
