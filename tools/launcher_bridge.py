from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
BACKUP_ROOT = Path(os.environ.get("LOCALAPPDATA", "")) / "Claude-zh-CN-official-backup"
CONFIG_PATH = Path(os.environ.get("APPDATA", "")) / "Claude" / "config.json"

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def emit(payload: dict[str, Any], exit_code: int = 0) -> int:
    sys.stdout.write(json.dumps(payload, ensure_ascii=False))
    sys.stdout.flush()
    return exit_code


def run_capture(command: list[str], *, timeout: float | None = None) -> subprocess.CompletedProcess[str]:
    child_env = os.environ.copy()
    child_env["PYTHONUTF8"] = "1"
    child_env["PYTHONIOENCODING"] = "utf-8"
    return subprocess.run(
        command,
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=child_env,
        timeout=timeout,
        shell=False,
    )


def python_exe() -> str:
    return sys.executable


def find_windowsapps_packages() -> list[Path]:
    base = Path(r"C:\Program Files\WindowsApps")
    if not base.exists():
        return []
    packages = sorted(
        {
            path.parent.parent
            for path in base.glob("Claude_*_x64__*/app/resources/en-US.json")
            if path.is_file()
        },
        key=lambda path: version_key(path),
        reverse=True,
    )
    return packages


def find_appdata_packages() -> list[Path]:
    local = os.environ.get("LOCALAPPDATA")
    if not local:
        return []
    anthropic = Path(local) / "AnthropicClaude"
    if not anthropic.exists():
        return []
    candidates = []
    for resource in [
        anthropic / "resources" / "en-US.json",
        anthropic / "app" / "resources" / "en-US.json",
        *anthropic.glob("app*/resources/en-US.json"),
    ]:
        if resource.is_file():
            candidates.append(resource.parent.parent)
    return sorted(
        set(candidates),
        key=lambda path: path.stat().st_mtime if path.exists() else 0,
        reverse=True,
    )


def version_key(app_dir: Path) -> tuple[int, ...]:
    name = app_dir.parent.name if app_dir.name.lower() == "app" else app_dir.name
    parts = name.split("_")
    if len(parts) < 2:
        return ()
    values: list[int] = []
    for part in parts[1].split("."):
        try:
            values.append(int(part))
        except ValueError:
            values.append(0)
    return tuple(values)


def version_label(app_dir: Path) -> str:
    key = version_key(app_dir)
    if key:
        return ".".join(str(part) for part in key)
    package = app_dir.parent.name if app_dir.name.lower() == "app" else app_dir.name
    match = re.search(r"(\d+(?:\.\d+){1,3})", package)
    return match.group(1) if match else "unknown"


def resolve_app_dir(target: str | None = None, app_dir: str | None = None) -> Path | None:
    if app_dir:
        path = Path(app_dir)
        if (path / "resources" / "en-US.json").is_file():
            return path
        if (path / "app" / "resources" / "en-US.json").is_file():
            return path / "app"
        return None

    windows = find_windowsapps_packages()
    appdata = find_appdata_packages()
    choice = (target or "auto").lower()
    if choice in {"windows-apps", "windowsapps"}:
        return windows[0] if windows else None
    if choice in {"app-data", "appdata"}:
        return appdata[0] if appdata else None
    if choice == "manual":
        return None

    try:
        result = run_capture(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                (
                    "$p = Get-Process -Name claude -ErrorAction SilentlyContinue | "
                    "Where-Object { $_.Path } | Select-Object -First 1; "
                    "if ($p) { Split-Path -Parent $p.Path }"
                ),
            ],
            timeout=6,
        )
        for line in result.stdout.splitlines():
            parent = Path(line.strip())
            if (parent / "resources" / "en-US.json").is_file():
                return parent
            if (parent / "app" / "resources" / "en-US.json").is_file():
                return parent / "app"
    except Exception:
        pass

    if windows:
        return windows[0]
    if appdata:
        return appdata[0]
    return None


def has_backup() -> bool:
    if not BACKUP_ROOT.exists():
        return False
    return any(BACKUP_ROOT.rglob("*"))


def locale_is_zh() -> bool:
    if not CONFIG_PATH.is_file():
        return False
    try:
        data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception:
        return False
    return data.get("locale") == "zh-CN"


def whitelist_has_zh(app_dir: Path) -> bool:
    assets = app_dir / "resources" / "ion-dist" / "assets"
    if not assets.exists():
        return False
    for path in assets.rglob("index-*.js"):
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if "zh-CN" in text and ("\"zh-CN\"" in text or "'zh-CN'" in text):
            return True
    return False


def zh_resources_present(app_dir: Path) -> bool:
    resources = app_dir / "resources"
    targets = [
        resources / "zh-CN.json",
        resources / "ion-dist" / "i18n" / "zh-CN.json",
        resources / "ion-dist" / "i18n" / "statsig" / "zh-CN.json",
    ]
    return all(path.is_file() for path in targets)


def python_available() -> bool:
    try:
        result = run_capture([python_exe(), "--version"], timeout=5)
        return result.returncode == 0
    except Exception:
        return False


def powershell_available() -> bool:
    return shutil.which("powershell") is not None


def build_status(target: str | None = None, app_dir: str | None = None) -> dict[str, Any]:
    resolved = resolve_app_dir(target=target, app_dir=app_dir)
    installed = resolved is not None
    localized = False
    language = "未安装"
    version = "unknown"
    install_path = "未找到 Claude Desktop"
    message = "未找到 Claude Desktop 安装。"
    checks = [
        {"label": "Claude Desktop", "value": "未找到", "tone": "danger"},
        {"label": "中文资源", "value": "未知", "tone": "warn"},
        {"label": "语言白名单", "value": "未知", "tone": "warn"},
        {
            "label": "备份文件",
            "value": "待生成" if not has_backup() else "已准备",
            "tone": "good" if has_backup() else "warn",
        },
        {
            "label": "Python / PowerShell",
            "value": "可用" if python_available() and powershell_available() else "缺失",
            "tone": "good" if python_available() and powershell_available() else "danger",
        },
    ]

    state = "missing"
    selected_target = target or "auto"
    if resolved:
        install_path = str(resolved)
        version = version_label(resolved)
        zh_files = zh_resources_present(resolved)
        whitelist = whitelist_has_zh(resolved)
        locale = locale_is_zh()
        backup = has_backup()
        localized = zh_files and whitelist
        language = "zh-CN" if locale or localized else "未安装"
        checks[0] = {"label": "Claude Desktop", "value": "已安装", "tone": "good"}
        checks[1] = {
            "label": "中文资源",
            "value": "已写入" if zh_files else "未安装",
            "tone": "good" if zh_files else "warn",
        }
        checks[2] = {
            "label": "语言白名单",
            "value": "包含 zh-CN" if whitelist else "待写入",
            "tone": "good" if whitelist else "warn",
        }
        checks[3] = {
            "label": "备份文件",
            "value": "已准备" if backup else "待生成",
            "tone": "good" if backup else "warn",
        }
        if localized:
            state = "ready"
            message = "Claude Desktop 中文版可以打开。"
        else:
            state = "repair"
            message = "Claude Desktop 已找到，可以安装中文补丁。"

        if "WindowsApps" in install_path:
            selected_target = "windows-apps" if selected_target == "auto" else selected_target
        elif "AnthropicClaude" in install_path:
            selected_target = "app-data" if selected_target == "auto" else selected_target

    return {
        "state": state,
        "installed": installed,
        "localized": localized,
        "version": version,
        "language": language,
        "target": selected_target,
        "installPath": install_path,
        "message": message,
        "checks": checks,
        "appDir": str(resolved) if resolved else None,
    }


def stop_claude() -> None:
    try:
        run_capture(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                (
                    "Get-Process -Name claude -ErrorAction SilentlyContinue | "
                    "Stop-Process -Force -ErrorAction SilentlyContinue"
                ),
            ],
            timeout=15,
        )
        time.sleep(1.5)
    except Exception:
        pass


def open_claude(app_dir: Path | None) -> tuple[bool, str]:
    candidates: list[Path] = []
    if app_dir:
        parent = app_dir.parent if app_dir.name.lower() == "app" else app_dir
        candidates.extend(
            [
                app_dir / "Claude.exe",
                parent / "Claude.exe",
                parent / "app" / "Claude.exe",
            ]
        )
    local = os.environ.get("LOCALAPPDATA")
    if local:
        candidates.append(Path(local) / "AnthropicClaude" / "Claude.exe")

    for path in candidates:
        if path.is_file():
            try:
                subprocess.Popen([str(path)], cwd=str(path.parent))
                return True, f"已启动: {path}"
            except OSError as exc:
                return False, f"启动失败: {exc}"

    try:
        result = run_capture(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                "Start-Process 'shell:AppsFolder\\Claude_pzs8sxrjxfjc!Claude'",
            ],
            timeout=10,
        )
        if result.returncode == 0:
            return True, "已通过 AppX 协议启动 Claude Desktop。"
    except Exception as exc:
        return False, f"启动失败: {exc}"
    return False, "未找到 Claude.exe，无法打开。"


def run_python_script(script_name: str, app_dir: Path | None) -> tuple[int, str]:
    command = [python_exe(), "-B", str(ROOT / script_name)]
    if app_dir:
        command.extend(["--app-dir", str(app_dir)])
    result = run_capture(command, timeout=None)
    output = (result.stdout or "") + (("\n" + result.stderr) if result.stderr else "")
    return result.returncode, output.strip()


def action_install(target: str | None = None, app_dir: str | None = None) -> dict[str, Any]:
    lines = ["[准备] 正在定位 Claude Desktop..."]
    resolved = resolve_app_dir(target=target, app_dir=app_dir)
    if not resolved:
        return {
            "ok": False,
            "state": "missing",
            "message": "未找到 Claude Desktop 安装。",
            "log": "\n".join(lines + ["[错误] 未找到可写入的 Claude app 目录。"]),
        }

    lines.append(f"[检测] 安装路径: {resolved}")
    lines.append("[准备] 正在关闭 Claude Desktop...")
    stop_claude()

    lines.append("[资源] 正在写入 zh-CN JSON 资源...")
    code, out = run_python_script("patch_windowsapps_json_only.py", resolved)
    if out:
        lines.extend(out.splitlines())
    if code != 0:
        return {
            "ok": False,
            "state": "error",
            "message": "JSON 资源补丁失败。",
            "log": "\n".join(lines),
        }

    lines.append("[运行时] 正在写入 chunk 文案、字体和会话增强...")
    code, out = run_python_script("patch_chunks_zh_cn.py", resolved)
    if out:
        lines.extend(out.splitlines())
    if code != 0:
        return {
            "ok": False,
            "state": "error",
            "message": "chunk 补丁失败。",
            "log": "\n".join(lines),
        }

    status = build_status(target=target, app_dir=str(resolved))
    if not status["localized"]:
        lines.append("[校验] 安装后校验未通过，请查看上方输出。")
        return {
            "ok": False,
            "state": "repair",
            "message": "安装后校验未通过。",
            "log": "\n".join(lines),
        }

    lines.append("[完成] 中文补丁已安装。")
    return {
        "ok": True,
        "state": "ready",
        "message": "中文补丁已安装，Claude Desktop 可以打开。",
        "log": "\n".join(lines),
    }


def action_restore(target: str | None = None, app_dir: str | None = None) -> dict[str, Any]:
    lines = ["[准备] 正在定位 Claude Desktop..."]
    resolved = resolve_app_dir(target=target, app_dir=app_dir)
    if not resolved:
        return {
            "ok": False,
            "state": "missing",
            "message": "未找到 Claude Desktop 安装。",
            "log": "\n".join(lines + ["[错误] 未找到可恢复的 Claude app 目录。"]),
        }

    lines.append(f"[检测] 安装路径: {resolved}")
    lines.append("[准备] 正在关闭 Claude Desktop...")
    stop_claude()
    lines.append("[恢复] 正在从官方备份恢复资源...")
    code, out = run_python_script("restore_claude_zh_cn_windowsapps.py", resolved)
    if out:
        lines.extend(out.splitlines())
    if code != 0:
        return {
            "ok": False,
            "state": "error",
            "message": "恢复失败。",
            "log": "\n".join(lines),
        }

    lines.append("[完成] 已恢复原样，Claude 数据保持不变。")
    return {
        "ok": True,
        "state": "repair",
        "message": "已恢复原样，Claude 数据保持不变。",
        "log": "\n".join(lines),
    }


def action_open(target: str | None = None, app_dir: str | None = None) -> dict[str, Any]:
    resolved = resolve_app_dir(target=target, app_dir=app_dir)
    ok, detail = open_claude(resolved)
    return {
        "ok": ok,
        "state": "ready" if ok else "error",
        "message": "Claude Desktop 已启动。" if ok else detail,
        "log": f"[启动] {detail}",
    }


def action_check_update(target: str | None = None, app_dir: str | None = None) -> dict[str, Any]:
    status = build_status(target=target, app_dir=app_dir)
    log = [
        "[更新] 正在读取当前 Claude Desktop 版本...",
        f"[更新] 当前版本: {status['version']}",
        f"[更新] 安装路径: {status['installPath']}",
        "[更新] 当前已是可用版本；Claude 官方更新后请重新安装补丁。",
    ]
    return {
        "ok": True,
        "state": status["state"],
        "message": f"当前版本 {status['version']} 已可用。",
        "log": "\n".join(log),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Claude Desktop zh-CN launcher bridge")
    parser.add_argument("command", choices=["status", "install", "restore", "open", "check-update"])
    parser.add_argument("--target", default="auto")
    parser.add_argument("--app-dir", default=None)
    args = parser.parse_args(argv)

    try:
        if args.command == "status":
            return emit({"ok": True, "status": build_status(target=args.target, app_dir=args.app_dir)})
        if args.command == "install":
            return emit(action_install(target=args.target, app_dir=args.app_dir))
        if args.command == "restore":
            return emit(action_restore(target=args.target, app_dir=args.app_dir))
        if args.command == "open":
            return emit(action_open(target=args.target, app_dir=args.app_dir))
        if args.command == "check-update":
            return emit(action_check_update(target=args.target, app_dir=args.app_dir))
    except Exception as exc:
        return emit(
            {
                "ok": False,
                "state": "error",
                "message": f"桥接层异常: {exc}",
                "log": str(exc),
            },
            exit_code=1,
        )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
