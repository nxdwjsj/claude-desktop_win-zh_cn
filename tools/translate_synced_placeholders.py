#!/usr/bin/env python3
"""Repair placeholder translations after syncing new Claude resources.

This script is intentionally conservative with structure: it preserves ICU
placeholders, HTML-like tags, product names, and technical acronyms, while
replacing untranslated UI prose with Chinese. It is meant to be run after
sync_i18n_from_installed.py --mark-untranslated.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import tools.check_i18n_coverage as coverage
import tools.sync_i18n_from_installed as sync

PLACEHOLDER_PREFIXES = ("待翻译：", "待补充翻译：")

EXACT = {
    "{mA}mA": "{mA}mA",
    "{kb}KB": "{kb}KB",
    "{pct}%": "{pct}%",
    "退出": "退出",
    "显示应用": "显示应用",
    "USB": "USB",
    "Show next suggestion": "显示下一条建议",
    "Brainstorm angles for a piece": "为文章构思角度",
    "Explore and summarize a dataset": "探索并总结数据集",
    "Stripe API key": "Stripe API 密钥",
    "reviewed": "已审阅",
    "Inline preview isn't available for this file.": "此文件不支持内联预览。",
    "Tell me more": "告诉我更多",
    "Get unstuck on a problem": "帮我突破问题卡点",
    "Redirecting you back to Claude.": "正在将你重定向回 Claude。",
    "JSON config": "JSON 配置",
    "Role defaults take priority over the org default model.": "角色默认值优先于组织默认模型。",
    "Reset server rate limits": "重置服务器速率限制",
    "No color": "无颜色",
    "Review the research design": "审阅研究设计",
    "Google Cloud KMS": "Google Cloud KMS",
    "Couldn't create the project": "无法创建项目",
    "That site is already allowed.": "该网站已在允许列表中。",
    "App indicator": "应用指示器",
    "Draft methods section from protocol": "根据方案起草方法部分",
    "Recommend the next book": "推荐下一本书",
    "type text into": "向其中输入文本",
    "Load earlier messages": "加载较早消息",
    "What can I pick up at this hour?": "这个时间我还能处理什么？",
    "Visualize this as a diagram: ": "将其可视化为图表：",
    "Bundle deleted.": "捆绑包已删除。",
    "Weekly scans paused": "每周扫描已暂停",
    "Daily scans paused": "每日扫描已暂停",
    "Wrong tone or style": "语气或风格不合适",
    "Message couldn't be sent. Try again.": "消息无法发送。请重试。",
    "Manual scan (cancelled)": "手动扫描（已取消）",
    "Couldn't remove domain.": "无法移除域名。",
    "Download and open {filename}": "下载并打开 {filename}",
    "Review submitted.": "审阅已提交。",
    "Virtualization isn't fully set up": "虚拟化尚未完全设置",
    "Show top {count, number}": "显示前 {count, number} 项",
    "Copy Slack workspace ID": "复制 Slack 工作区 ID",
    "Alt+Space": "Alt+Space",
    "Summarize contract into key terms": "将合同总结为关键条款",
    "Couldn't delete the project": "无法删除项目",
    "Couldn't read this file": "无法读取此文件",
    "Archiving session": "正在归档会话",
    "remove {count, number}": "移除 {count, number} 项",
    "{selectedOption} / {totalOptions}": "{selectedOption} / {totalOptions}",
    "Analyze this dataset": "分析这个数据集",
    "I’ll handle it while you step away": "你离开时我会继续处理",
    "It’s late-night {name}": "现在是深夜的 {name}",
    "Couldn't load repositories.": "无法加载仓库。",
    "{date} · in progress": "{date} · 进行中",
    "Closed without merging": "已关闭且未合并",
    "Code something": "写点代码",
    "Disabled at org level": "已在组织层级禁用",
    "Write a parent email": "写一封家长邮件",
    "Claude Tag version": "Claude Tag 版本",
    "It’s a late-night jam session.": "这是一场深夜即兴创作。",
    "Model settings are still loading.": "模型设置仍在加载。",
    "Spend by model view": "按模型查看消耗",
    "Show connectors for": "显示以下连接器：",
    "Already added for your organization": "已为你的组织添加",
    "Previous finding": "上一个发现项",
    "Bundle instructions": "捆绑包说明",
    "Delayed": "已延迟",
    "Configure channel": "配置频道",
    "Draft replies for emails": "起草邮件回复",
    "Prioritize this backlog": "排列这个待办列表的优先级",
    "Explain a concept": "解释一个概念",
    "Draft abstract from notes": "根据笔记起草摘要",
    "No environments": "没有环境",
    "Write a one-page product spec": "写一页产品规格说明",
    "Explain selection": "解释选中内容",
    "Synthesize this user research": "综合这份用户研究",
    "Scroll to {section} section": "滚动到 {section} 部分",
    "Bundle name": "捆绑包名称",
    "Fixing…": "正在修复…",
    "Project icon": "项目图标",
    "Research company and draft brief": "研究公司并起草简报",
    "Connected workspaces": "已连接工作区",
    "Instagram": "Instagram",
    "Reformat a messy doc": "重新整理混乱文档",
    "Now using usage credits for {model}.": "现在对 {model} 使用用量额度。",
    "From the Claude connector directory": "来自 Claude 连接器目录",
    "Buy credits": "购买额度",
    "Violet": "紫色",
    "This file is on another device": "此文件位于另一台设备上",
    "Couldn't regenerate memory right now": "现在无法重新生成记忆",
    "Build reading schedule from syllabus": "根据教学大纲制定阅读计划",
    "Anthropic Sans": "Anthropic Sans",
    "{n} merged": "已合并 {n} 个",
    "Remove this group from all projects?": "从所有项目中移除此组？",
    "Starting a runner…": "正在启动运行器…",
    "Unable to load visibility settings.": "无法加载可见性设置。",
    "Previews": "预览",
    "↓ Latest": "↓ 最新",
    "Starting session": "正在启动会话",
    "Afternoon stretch. What’s left?": "下午时段，还剩什么？",
    "Couldn't add domain.": "无法添加域名。",
    "Per seat": "按席位",
    "Interrupting session": "正在中断会话",
    "Unavailable environment": "不可用环境",
    "Channel instructions": "频道说明",
    "Claude is working": "Claude 正在工作",
    "Keep window on top": "窗口置顶",
    "Encryption key configured.": "加密密钥已配置。",
    "$ / commit": "$ / commit",
}

PHRASES = [
    ("Access denied by your organization", "访问已被你的组织拒绝"),
    ("Contact your administrator", "请联系管理员"),
    ("Contact your organization’s admin", "请联系组织管理员"),
    ("Contact your organization's admin", "请联系组织管理员"),
    ("Cowork requires QEMU", "Cowork 需要 QEMU"),
    ("Cowork requires hardware virtualization", "Cowork 需要硬件虚拟化"),
    ("Cowork requires the vhost_vsock kernel module", "Cowork 需要 vhost_vsock 内核模块"),
    ("Cowork isn't available in this build of Claude", "此 Claude 构建中不可用 Cowork"),
    ("Install it with", "请使用"),
    ("Load it with", "请使用"),
    ("then restart Claude", "然后重启 Claude"),
    ("reinstall Claude", "重新安装 Claude"),
    ("Checking virtualization support", "正在检查虚拟化支持"),
    ("hardware virtualization", "硬件虚拟化"),
    ("firmware settings", "固件设置"),
    ("this device", "此设备"),
    ("this feature", "此功能"),
    ("Couldn't open that session", "无法打开该会话"),
    ("Check your network connection", "请检查网络连接"),
    ("try again", "请重试"),
    ("Try again", "请重试"),
    ("Couldn't save", "无法保存"),
    ("Couldn't load", "无法加载"),
    ("Couldn't delete", "无法删除"),
    ("Couldn't read", "无法读取"),
    ("Couldn't leave", "无法离开"),
    ("Couldn't reach", "无法连接"),
    ("from Claude Code", "来自 Claude Code"),
    ("sign in again", "重新登录"),
    ("Sign in again", "重新登录"),
    ("desktop app", "桌面应用"),
    ("transcript may have been removed", "转录记录可能已被移除"),
    ("doesn't have permission", "没有权限"),
    ("Add your user to the", "将你的用户添加到"),
    ("group, then log out and back in", "组，然后注销并重新登录"),
    ("maker devices", "创客设备"),
    ("permission prompts", "权限提示"),
    ("recent messages", "最近消息"),
    ("other interactions", "其他交互"),
    ("connect", "连接"),
    ("developers can build hardware that displays", "开发者可以构建用于显示的硬件："),
    ("Inline preview isn't available for this file", "此文件不支持内联预览"),
    ("Role defaults take priority over the org default model", "角色默认值优先于组织默认模型"),
    ("Let members choose", "允许成员选择"),
    ("when approving connector tools in Cowork", "在 Cowork 中批准连接器工具时"),
    ("Only applies to tools that can make changes", "仅适用于可执行更改的工具"),
    ("read-only tools are not affected by this setting", "只读工具不受此设置影响"),
    ("increases risk from prompt injection", "会增加提示注入风险"),
    ("content from connected apps", "来自已连接应用的内容"),
    ("could cause Claude to take unintended actions", "可能导致 Claude 执行非预期操作"),
    ("without per-use approval", "且无需逐次批准"),
    ("This file can't be saved", "无法保存此文件"),
    ("Its path is outside the working directory", "它的路径位于工作目录之外"),
    ("or this is a remote session", "或这是远程会话"),
    ("You've hit your", "你已达到"),
    ("You've reached your", "你已达到"),
    ("spend limit", "消费限制"),
    ("out of credits", "额度已用完"),
    ("plan usage", "方案用量"),
    ("resets at", "重置时间为"),
    ("Limit resets", "限制重置时间"),
    ("Turn on usage credits", "开启用量额度"),
    ("keep going", "以继续使用"),
    ("Added to every request Claude sends to the allowed websites", "会添加到 Claude 发送给允许网站的每个请求中"),
    ("Paused by Anthropic", "已被 Anthropic 暂停"),
    ("We recommend contacting support before resuming", "建议先联系支持再恢复"),
    ("Your session has expired for Claude Code access", "你的 Claude Code 访问会话已过期"),
    ("This session reached a runner", "此会话已连接到运行器"),
    ("stays listed as idle", "因此仍会列为闲置"),
    ("revoke its token", "撤销其令牌"),
    ("Submit feedback", "提交反馈"),
    ("report a bug", "报告问题"),
    ("share your conversation", "分享你的对话"),
    ("Some folders couldn't be added", "部分文件夹无法添加"),
    ("removed from this message", "已从此消息中移除"),
    ("Server rate limits reset", "服务器速率限制已重置"),
    ("Reload to re-trigger placements", "重新加载以再次触发布置"),
    ("Checks running", "检查正在运行"),
    ("GitHub App may not be installed", "可能尚未安装 GitHub App"),
    ("Add a GitHub installation", "添加 GitHub 安装"),
    ("If a member has multiple roles", "如果成员拥有多个角色"),
    ("every model any of their roles allows", "其任一角色允许的所有模型"),
    ("Your card was saved", "你的银行卡已保存"),
    ("could not be set as default", "但无法设为默认"),
    ("Personal projects can't be left", "个人项目不能离开"),
    ("scheduled task", "计划任务"),
    ("run on demand", "按需运行"),
    ("automatically on an interval", "按间隔自动运行"),
    ("Not all repositories could be searched", "并非所有仓库都能被搜索"),
    ("full name", "完整名称"),
    ("repository access", "仓库访问权限"),
    ("Slack channel", "Slack 频道"),
    ("set instructions", "设置指令"),
    ("Changes apply to new sessions", "更改适用于新会话"),
    ("tool approvals couldn't be copied", "工具审批无法复制"),
    ("asked to approve them again", "可能需要再次批准"),
    ("Clone the repository", "克隆仓库"),
    ("into this session", "到此会话中"),
    ("Chat with Claude from anywhere on your computer", "可从电脑任意位置与 Claude 聊天"),
    ("Artifacts shared by Claude in this thread", "Claude 在此主题中分享的工件"),
    ("will appear here", "将显示在这里"),
    ("turn this workflow into a skill", "把这个工作流转成技能"),
    ("What other skills do you have", "你还有哪些其他技能"),
    ("Failed to add folder", "添加文件夹失败"),
    ("payment methods", "付款方式"),
    ("Watch for news or mentions", "关注新闻或提及"),
    ("topic, competitor, or keyword", "主题、竞争对手或关键词"),
    ("runs on its own", "可自行运行"),
    ("how often", "频率"),
    ("sample run", "示例运行"),
    ("goes live", "正式启用"),
    ("Categorize your inbox", "整理你的收件箱"),
    ("draft replies", "起草回复"),
    ("anything urgent", "任何紧急事项"),
    ("Debug export isn't available", "调试导出不可用"),
    ("shared session", "共享会话"),
    ("used in", "用于"),
    ("places", "位置"),
    ("selected model", "所选模型"),
    ("no longer available", "已不再可用"),
    ("prefix is reserved", "此前缀已保留"),
    ("protected branches", "受保护分支"),
]

WORDS = {
    "absolute": "绝对",
    "abstract": "摘要",
    "access": "访问权限",
    "account": "账号",
    "action": "操作",
    "actions": "操作",
    "active": "活跃",
    "added": "已添加",
    "add": "添加",
    "admin": "管理员",
    "administrator": "管理员",
    "allowed": "允许",
    "allow": "允许",
    "allows": "允许",
    "already": "已",
    "analyze": "分析",
    "analysis": "分析",
    "angles": "角度",
    "another": "另一台",
    "anywhere": "任意位置",
    "appear": "显示",
    "approval": "批准",
    "approvals": "审批",
    "approve": "批准",
    "archive": "归档",
    "archived": "已归档",
    "assignment": "作业",
    "attach": "附加",
    "attention": "关注",
    "automatic": "自动",
    "automatically": "自动",
    "available": "可用",
    "backlog": "待办列表",
    "before": "之前",
    "billing": "账单",
    "brief": "简报",
    "briefing": "简报",
    "browser": "浏览器",
    "build": "构建",
    "bundle": "捆绑包",
    "cancel": "取消",
    "cancelled": "已取消",
    "card": "银行卡",
    "category": "类别",
    "change": "更改",
    "changes": "更改",
    "channel": "频道",
    "channels": "频道",
    "chat": "聊天",
    "check": "检查",
    "checks": "检查",
    "choose": "选择",
    "click": "点击",
    "close": "关闭",
    "closed": "已关闭",
    "color": "颜色",
    "company": "公司",
    "compare": "比较",
    "comparison": "对比",
    "compliance": "合规",
    "concept": "概念",
    "configuration": "配置",
    "configured": "已配置",
    "configure": "配置",
    "connect": "连接",
    "connected": "已连接",
    "connection": "连接",
    "connector": "连接器",
    "connectors": "连接器",
    "content": "内容",
    "contract": "合同",
    "conversation": "对话",
    "copied": "已复制",
    "copy": "复制",
    "create": "创建",
    "created": "已创建",
    "credentials": "凭据",
    "credits": "额度",
    "daily": "每日",
    "data": "数据",
    "dataset": "数据集",
    "date": "日期",
    "debug": "调试",
    "default": "默认",
    "delete": "删除",
    "deleted": "已删除",
    "details": "详情",
    "device": "设备",
    "devices": "设备",
    "diagram": "图表",
    "directory": "目录",
    "disabled": "已禁用",
    "domain": "域名",
    "domains": "域名",
    "draft": "起草",
    "edit": "编辑",
    "email": "邮件",
    "emails": "邮件",
    "enabled": "已启用",
    "encryption": "加密",
    "environment": "环境",
    "environments": "环境",
    "error": "错误",
    "explain": "解释",
    "export": "导出",
    "failed": "失败",
    "failure": "失败",
    "feature": "功能",
    "feedback": "反馈",
    "file": "文件",
    "files": "文件",
    "finding": "发现项",
    "fixing": "正在修复",
    "folder": "文件夹",
    "folders": "文件夹",
    "from": "来自",
    "group": "组",
    "groups": "组",
    "handle": "处理",
    "hostname": "主机名",
    "hour": "小时",
    "icon": "图标",
    "idle": "闲置",
    "indicator": "指示器",
    "instructions": "指令",
    "interactions": "交互",
    "interrupting": "正在中断",
    "key": "密钥",
    "keyword": "关键词",
    "keys": "密钥",
    "late": "深夜",
    "latest": "最新",
    "left": "剩余",
    "limit": "限制",
    "limits": "限制",
    "load": "加载",
    "loading": "正在加载",
    "manual": "手动",
    "member": "成员",
    "members": "成员",
    "memory": "记忆",
    "merge": "合并",
    "merged": "已合并",
    "message": "消息",
    "messages": "消息",
    "method": "方法",
    "methods": "方法",
    "model": "模型",
    "models": "模型",
    "monthly": "每月",
    "name": "名称",
    "network": "网络",
    "news": "新闻",
    "notes": "笔记",
    "offline": "离线",
    "open": "打开",
    "organization": "组织",
    "org": "组织",
    "page": "页面",
    "paused": "已暂停",
    "pending": "待处理",
    "permission": "权限",
    "permissions": "权限",
    "plugin": "插件",
    "plugins": "插件",
    "preview": "预览",
    "previews": "预览",
    "priority": "优先级",
    "problem": "问题",
    "product": "产品",
    "progress": "进度",
    "project": "项目",
    "projects": "项目",
    "prompt": "提示词",
    "prompts": "提示",
    "protocol": "方案",
    "pull": "拉取",
    "rate": "速率",
    "read": "读取",
    "reading": "阅读",
    "recommend": "推荐",
    "reconnect": "重新连接",
    "refresh": "刷新",
    "regenerate": "重新生成",
    "remove": "移除",
    "removed": "已移除",
    "reply": "回复",
    "replies": "回复",
    "repository": "仓库",
    "repositories": "仓库",
    "request": "请求",
    "requests": "请求",
    "research": "研究",
    "reset": "重置",
    "resets": "重置",
    "resuming": "恢复",
    "review": "审阅",
    "reviewed": "已审阅",
    "role": "角色",
    "roles": "角色",
    "runner": "运行器",
    "running": "正在运行",
    "save": "保存",
    "saved": "已保存",
    "scan": "扫描",
    "scans": "扫描",
    "schedule": "计划",
    "scheduled": "计划",
    "section": "部分",
    "selected": "所选",
    "selection": "选中内容",
    "send": "发送",
    "sent": "已发送",
    "server": "服务器",
    "session": "会话",
    "sessions": "会话",
    "settings": "设置",
    "share": "分享",
    "shared": "共享",
    "site": "网站",
    "slack": "Slack",
    "source": "来源",
    "spec": "规格说明",
    "spend": "消费",
    "status": "状态",
    "style": "风格",
    "submitted": "已提交",
    "suggestion": "建议",
    "summarize": "总结",
    "support": "支持",
    "syncing": "正在同步",
    "synthesize": "综合",
    "task": "任务",
    "tasks": "任务",
    "terms": "条款",
    "text": "文本",
    "thread": "主题",
    "token": "令牌",
    "tokens": "令牌",
    "tone": "语气",
    "tool": "工具",
    "tools": "工具",
    "transcript": "转录记录",
    "trigger": "触发",
    "usage": "用量",
    "user": "用户",
    "virtualization": "虚拟化",
    "visibility": "可见性",
    "visualize": "可视化",
    "watch": "关注",
    "website": "网站",
    "websites": "网站",
    "weekly": "每周",
    "window": "窗口",
    "workflow": "工作流",
    "workflows": "工作流",
    "workspace": "工作区",
    "workspaces": "工作区",
}

KEEP_WORDS = {
    "AI", "API", "AWS", "BLE", "CLI", "Claude", "Cowork", "Code", "Google", "GitHub", "Gmail",
    "HTTP", "IDE", "JSON", "KMS", "KVM", "Linux", "MCP", "OAuth", "OpenTelemetry", "Python",
    "QEMU", "Slack", "Stripe", "USB", "URL", "Windows", "macOS", "Anthropic", "Chrome",
    "Max", "Pro", "Team", "Enterprise", "Bedrock", "Vertex", "OpenAI", "Node.js", "GitHub",
}

WORD_RE = re.compile(r"[A-Za-z][A-Za-z0-9'’.-]*")


def strip_marker(value: str) -> str:
    for prefix in PLACEHOLDER_PREFIXES:
        if value.startswith(prefix):
            return value[len(prefix):]
    return value


def should_repair(current: object) -> bool:
    if not isinstance(current, str):
        return False
    if current.startswith(PLACEHOLDER_PREFIXES):
        return True
    return coverage.classify_value(current) is not None


def is_keep_word(word: str) -> bool:
    trimmed = word.strip(".'’-")
    if not trimmed:
        return True
    if trimmed in KEEP_WORDS:
        return True
    lowered = trimmed.lower()
    if lowered in {w.lower() for w in KEEP_WORDS}:
        return True
    if re.fullmatch(r"[A-Z0-9]{2,}", trimmed):
        return True
    if re.fullmatch(r"[a-z]+_[a-z0-9_]+", lowered):
        return True
    if "." in trimmed or "/" in trimmed:
        return True
    return False


def apply_phrases(text: str) -> str:
    result = text
    for source, target in sorted(sync.PHRASE_REPLACEMENTS + PHRASES, key=lambda item: len(item[0]), reverse=True):
        result = re.sub(re.escape(source), target, result, flags=re.IGNORECASE)
    return result


def replace_word(match: re.Match[str]) -> str:
    word = match.group(0)
    lowered = word.strip(".'’-").lower()
    if not lowered:
        return word
    if is_keep_word(word):
        return word
    if lowered in WORDS:
        suffix = "" if word[-1].isalnum() else word[-1]
        return WORDS[lowered] + suffix
    return word


def polish(text: str) -> str:
    replacements = {
        "无法 create": "无法创建",
        "无法 load": "无法加载",
        "无法 save": "无法保存",
        "无法 remove": "无法移除",
        "无法 delete": "无法删除",
        "无法 read": "无法读取",
        "无法 open": "无法打开",
        "不能 be": "无法",
        "不可 available": "不可用",
        "No ": "没有",
        "no ": "没有",
        "  ": " ",
        " ,": "，",
        " .": "。",
        " :": "：",
        " ;": "；",
        " ?": "？",
        " !": "！",
    }
    result = text
    for source, target in replacements.items():
        result = result.replace(source, target)
    result = re.sub(r"\s+([，。！？；：、）])", r"\1", result)
    result = re.sub(r"([（])\s+", r"\1", result)
    result = re.sub(r"\s+", " ", result).strip()
    return result


def translate(source: object, current: object, memory: dict[str, str]) -> object:
    if not isinstance(source, str):
        return source
    raw = strip_marker(current) if isinstance(current, str) and current.startswith(PLACEHOLDER_PREFIXES) else source
    if raw in EXACT:
        return EXACT[raw]
    if raw in sync.EXACT_TRANSLATIONS:
        return sync.EXACT_TRANSLATIONS[raw]
    if raw in memory:
        return memory[raw]
    translated = sync.translate_value(raw, memory, mark_untranslated=False)
    if isinstance(translated, str) and translated != raw and not translated.startswith(PLACEHOLDER_PREFIXES):
        if coverage.classify_value(translated) is None:
            return translated
    rough = apply_phrases(raw)
    rough = WORD_RE.sub(replace_word, rough)
    rough = polish(rough)
    if rough != raw and coverage.classify_value(rough) is None:
        return rough
    marked = sync.fallback_translation(raw, mark_untranslated=True)
    if isinstance(marked, str):
        return marked
    return raw


def main() -> int:
    app_dir = sync.patch_windowsapps_json_only.find_claude_package()
    if not app_dir:
        raise SystemExit("Claude app directory not found")
    installed_resources = app_dir / "resources"
    memory = sync.translation_memory(installed_resources)
    total_changed = 0
    for name, spec in sync.RESOURCE_PAIRS.items():
        installed_en = installed_resources.parent / spec["installed_en"]
        local_path = spec["local"]
        if not installed_en.exists() or not local_path.exists():
            print(f"{name}: skipped")
            continue
        en_data = sync.load_json(installed_en)
        local_data = sync.load_json(local_path)
        changed = 0
        for key, current in list(local_data.items()):
            if key not in en_data or not should_repair(current):
                continue
            next_value = translate(en_data[key], current, memory)
            if next_value != current:
                local_data[key] = next_value
                changed += 1
        if changed:
            sync.write_json(local_path, local_data)
        total_changed += changed
        print(f"{name}: changed={changed}")
    print(f"total_changed={total_changed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
