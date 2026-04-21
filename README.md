# claude-session-extract

Extract Claude Code conversation sessions from raw `.jsonl` logs into clean, readable Markdown files — ready for AI summarization or personal knowledge management.

## What it does

Claude Code stores every conversation as a `.jsonl` file in `~/.claude/projects/`. These files are large (1–5 MB), verbose, and full of tool metadata. This tool extracts what actually matters:

- **User messages**: fully preserved, no truncation
- **Claude's final replies**: complete text, marked as *(final reply)*
- **Intermediate tool calls**: summarized (e.g. `[Bash: check git status]`)
- **Session ID**: shown in full for `claude --resume <id>` restore

**Compression**: typically 95–97% size reduction (1.4 MB → 39 KB).

## Usage

```bash
# Extract a specific session
python3 extract.py ~/.claude/projects/-Users-you/session-uuid.jsonl

# Extract all sessions modified on a specific date
python3 extract.py --date 2026-04-21

# Extract today's sessions
python3 extract.py --today
```

Output files are saved to `~/claude-sessions/` by default (configurable via `OUTPUT_DIR`).

## Output format

```markdown
# Claude Code Session
- **Session ID**: `a1bb5eb3-...` (resume with `claude --resume ...`)
- **Time**: 2026-04-19 23:00 to 2026-04-21 13:00
- **Messages**: 306

**User** `10:02`
How do I set up a daily cron job in Python?

**Claude** `10:02` *(final reply)*
You can use the `schedule` library or a system cron. Here's the simplest approach...
```

## Use with AI summarization

The extracted Markdown is compact enough to feed directly into Claude for summarization:

```
Summarize the main topics, decisions and conclusions from this conversation:
[paste extracted .md content]
```

## Requirements

Python 3.6+, no external dependencies.

## Configuration

Edit the constants at the top of `extract.py`:

```python
CLAUDE_PROJECTS = Path.home() / ".claude" / "projects"
OUTPUT_DIR = Path.home() / "claude-sessions"
```

## License

MIT
