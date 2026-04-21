#!/usr/bin/env python3
"""
Claude Code JSONL to semi-processed Markdown extractor.

Usage:
    python3 extract.py <session.jsonl> [output.md]
    python3 extract.py --date 2026-04-21
    python3 extract.py --today
"""
import json, sys, os, re
from datetime import datetime, timezone
from pathlib import Path

CLAUDE_PROJECTS = Path.home() / ".claude" / "projects"
OUTPUT_DIR = Path.home() / "claude-sessions"


def summarize_tool(name, input_data):
    if "telegram" in name and "reply" in name:
        text = input_data.get("text", "")
        return f"__TELEGRAM_REPLY__:{text}"
    if name == "Read":
        return f"[Read: {input_data.get('file_path','')}]"
    if name in ("Edit", "Write"):
        return f"[{name}: {input_data.get('file_path','')}]"
    if name == "Bash":
        cmd = input_data.get("command","")[:80]
        desc = input_data.get("description","")
        return f"[Bash: {desc or cmd}]"
    if name in ("Grep", "Glob"):
        return f"[{name}: {input_data.get('pattern','') or input_data.get('query','')}]"
    if name == "WebSearch":
        return f"[WebSearch: {input_data.get('query','')}]"
    if name == "WebFetch":
        return f"[WebFetch: {input_data.get('url','')}]"
    if "Calendar" in name or "Gmail" in name or "Drive" in name:
        return f"[{name.split('__')[-1]}: {str(input_data)[:60]}]"
    key_params = ", ".join(f"{k}={str(v)[:30]}" for k,v in list(input_data.items())[:2])
    return f"[{name}({key_params})]"


def extract_session(jsonl_path):
    messages = []
    tool_use_map = {}

    with open(jsonl_path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except:
                continue

            obj_type = obj.get("type")
            if obj_type not in ("user", "assistant"):
                continue

            ts = obj.get("timestamp", "")
            role = obj_type
            content = obj.get("message", {}).get("content", "")

            parts = []
            if isinstance(content, str):
                if content.strip():
                    parts.append(content.strip())
            elif isinstance(content, list):
                for item in content:
                    itype = item.get("type")
                    if itype == "text":
                        text = item.get("text", "").strip()
                        if text:
                            parts.append(text)
                    elif itype == "tool_use":
                        tool_id = item.get("id")
                        tool_name = item.get("name", "")
                        tool_input = item.get("input", {})
                        tool_use_map[tool_id] = tool_name
                        summary = summarize_tool(tool_name, tool_input)
                        parts.append(summary)
                    elif itype == "tool_result":
                        result_content = item.get("content", [])
                        if isinstance(result_content, list):
                            for rc in result_content:
                                if rc.get("type") == "text":
                                    text = rc.get("text","")
                                    if text.startswith("sent (id:"):
                                        continue
                                    if len(text) < 120 and len(text) > 2:
                                        parts.append(f"  -> {text}")

            if parts:
                messages.append({
                    "role": role,
                    "ts": ts,
                    "content": "\n".join(parts),
                    "is_last": False
                })

    # Mark the last assistant message before each user message
    for i, msg in enumerate(messages):
        if msg["role"] == "user" and i > 0:
            for j in range(i - 1, -1, -1):
                if messages[j]["role"] == "assistant":
                    messages[j]["is_last"] = True
                    break
    if messages and messages[-1]["role"] == "assistant":
        messages[-1]["is_last"] = True

    return messages


def format_markdown(messages, session_id, jsonl_path):
    if not messages:
        return None

    timestamps = [m["ts"] for m in messages if m["ts"]]
    start_ts = min(timestamps) if timestamps else ""
    end_ts = max(timestamps) if timestamps else ""

    def fmt_ts(ts_str):
        if not ts_str:
            return ""
        try:
            dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
            return dt.strftime("%Y-%m-%d %H:%M")
        except:
            return ts_str[:16]

    lines = [
        f"# Claude Code Session",
        f"- **Session ID**: `{session_id}` (resume with `claude --resume {session_id}`)",
        f"- **Time**: {fmt_ts(start_ts)} to {fmt_ts(end_ts)}",
        f"- **Messages**: {len(messages)}",
        f"- **Source**: {jsonl_path}",
        ""
    ]

    for msg in messages:
        role_label = "**User**" if msg["role"] == "user" else "**Claude**"
        ts_short = fmt_ts(msg["ts"])
        content = msg["content"]
        is_last = msg.get("is_last", False)

        if msg["role"] == "user":
            clean = re.sub(r'<channel[^>]+>', '', content)
            clean = re.sub(r'</channel>', '', clean)
            clean = re.sub(r'<[^>]+>', '', clean).strip()
            if clean:
                lines.append(f"{role_label} `{ts_short}`")
                lines.append(clean)
                lines.append("")
        else:
            telegram_replies = []
            other_parts = []
            for part in content.split("\n"):
                if part.startswith("__TELEGRAM_REPLY__:"):
                    telegram_replies.append(part[len("__TELEGRAM_REPLY__:"):])
                else:
                    other_parts.append(part)

            if is_last and telegram_replies:
                lines.append(f"{role_label} `{ts_short}` *(final reply)*")
                lines.append(telegram_replies[-1])
                lines.append("")
            elif telegram_replies:
                preview = telegram_replies[-1][:120]
                lines.append(f"{role_label} `{ts_short}`")
                lines.append(f"[reply: {preview}...]")
                lines.append("")
            elif other_parts:
                clean = "\n".join(other_parts).strip()
                if clean and is_last:
                    lines.append(f"{role_label} `{ts_short}`")
                    lines.append(clean[:300])
                    lines.append("")

    return "\n".join(lines)


def process_session(jsonl_path, output_path=None):
    session_id = Path(jsonl_path).stem
    messages = extract_session(jsonl_path)

    if not messages:
        print(f"  skip (empty): {session_id[:8]}")
        return None

    md = format_markdown(messages, session_id, str(jsonl_path))
    if not md:
        return None

    if output_path is None:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        first_ts = messages[0]["ts"]
        try:
            dt = datetime.fromisoformat(first_ts.replace("Z", "+00:00"))
            date_str = dt.strftime("%Y-%m-%d")
        except:
            date_str = "unknown"
        output_path = OUTPUT_DIR / f"{date_str}_{session_id[:8]}.md"

    with open(output_path, "w") as f:
        f.write(md)

    print(f"  ok {session_id[:8]} -> {output_path} ({len(messages)} messages)")
    return output_path


def process_all_for_date(date_str):
    results = []
    for project_dir in CLAUDE_PROJECTS.iterdir():
        if not project_dir.is_dir():
            continue
        for jsonl_file in project_dir.glob("*.jsonl"):
            mtime = datetime.fromtimestamp(jsonl_file.stat().st_mtime, tz=timezone.utc)
            if mtime.strftime("%Y-%m-%d") == date_str:
                result = process_session(jsonl_file)
                if result:
                    results.append(result)
    return results


if __name__ == "__main__":
    args = sys.argv[1:]

    if not args:
        print("Usage:")
        print("  python3 extract.py <session.jsonl>")
        print("  python3 extract.py --date 2026-04-21")
        print("  python3 extract.py --today")
        sys.exit(0)

    if args[0] == "--today":
        today = datetime.now().strftime("%Y-%m-%d")
        print(f"Extracting today ({today})...")
        results = process_all_for_date(today)
        print(f"\nDone: {len(results)} sessions extracted")

    elif args[0] == "--date" and len(args) > 1:
        date_str = args[1]
        print(f"Extracting {date_str}...")
        results = process_all_for_date(date_str)
        print(f"\nDone: {len(results)} sessions extracted")

    else:
        jsonl_path = args[0]
        output_path = args[1] if len(args) > 1 else None
        process_session(jsonl_path, output_path)
