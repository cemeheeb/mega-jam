"""Выгрузка диалога с Claude Code в читаемый журнал — как свидетельство хода работы для организаторов джема.

    python3 tools/devlog/export_session.py                 # последняя сессия этого проекта
    python3 tools/devlog/export_session.py <файл.jsonl>    # конкретная запись сессии

Пишет devlog/claude-session-<дата>.md. В журнал попадают: сообщения автора, ответы ассистента,
вопросы ассистента с ответами автора и по одной строке на каждое действие ассистента (что сделано
и с каким файлом). Не попадают: вывод команд, внутренние рассуждения модели, служебные вставки
редактора (открытые файлы, выделенный текст), системные напоминания.
"""

import glob
import json
import os
import re
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SESSIONS = os.path.expanduser("~/.claude/projects/" + ROOT.replace("/", "-"))
LOCAL = timezone(timedelta(hours=5))   # часовой пояс автора, UTC+5

# служебные вставки, которые автор не писал
STRIP = re.compile(r"<(system-reminder|ide_selection|ide_opened_file|local-command-caveat|local-command-stdout|"
                   r"command-name|command-message|command-args|task-notification)>.*?</\1>", re.S)


def stamp(ts: str) -> str:
    t = datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone(LOCAL)
    return t.strftime("%Y-%m-%d %H:%M:%S") + " UTC+5"


def clean_user(text: str) -> str:
    text = STRIP.sub("", text)
    text = re.sub(r"\[SYSTEM NOTIFICATION - NOT USER INPUT\].*", "", text, flags=re.S)
    text = re.sub(r"</?pasted_content[^>]*>", "", text)   # обёртка вставленного текста, сам текст остаётся
    return text.strip()


def rel(path: str) -> str:
    return path[len(ROOT) + 1:] if path.startswith(ROOT + "/") else os.path.basename(path)


def action_line(name: str, inp: dict) -> str:
    """Одна строка о действии ассистента: что сделано, без вывода."""
    if name == "Bash":
        return f"runs a command: {inp.get('description', '').strip() or '(no description)'}"
    if name in ("Write", "Edit", "Read"):
        verb = {"Write": "writes file", "Edit": "edits file", "Read": "reads file"}[name]
        return f"{verb}: {rel(inp.get('file_path', ''))}"
    if name == "Agent":
        return f"delegates to a sub-agent: {inp.get('description', '')}"
    if name.startswith("mcp__unreal__"):
        return f"calls Unreal Editor: {inp.get('tool_name') or inp.get('toolset_name') or name}"
    if name == "TaskStop":
        return "stops a background task"
    return f"uses tool {name}"


def main():
    if len(sys.argv) > 1:
        src = sys.argv[1]
    else:
        files = sorted(glob.glob(os.path.join(SESSIONS, "*.jsonl")), key=os.path.getmtime)
        if not files:
            sys.exit(f"нет записей сессий в {SESSIONS}")
        src = files[-1]

    out, questions = [], {}
    stats = Counter()
    models = Counter()
    first = last = None
    for line in open(src, encoding="utf-8"):
        try:
            r = json.loads(line)
        except json.JSONDecodeError:
            continue
        kind = r.get("type")
        if kind not in ("user", "assistant") or r.get("isSidechain") or r.get("isMeta"):
            continue
        ts = r.get("timestamp")
        msg = r.get("message") or {}
        content = msg.get("content")
        if ts:
            first = first or ts
            last = ts
        when = stamp(ts) if ts else "?"
        if r.get("isCompactSummary"):
            out.append(f"\n---\n\n*[{when}] The conversation got long; the tool compacted earlier context into a summary and work continued.*\n")
            continue
        blocks = [{"type": "text", "text": content}] if isinstance(content, str) else (content or [])

        if kind == "user":
            for b in blocks:
                if b.get("type") == "text":
                    text = clean_user(b.get("text", ""))
                    if text:
                        stats["author messages"] += 1
                        out.append(f"\n---\n\n### [{when}] AUTHOR\n\n{text}\n")
                elif b.get("type") == "tool_result" and b.get("tool_use_id") in questions:
                    c = b.get("content")
                    ans = c if isinstance(c, str) else " ".join(x.get("text", "") for x in c or [] if isinstance(x, dict))
                    ans = re.sub(r"\s*You can now continue with these answers in mind\.\s*$", "", ans.strip())
                    ans = ans.replace("Your questions have been answered: ", "")
                    stats["author answers to questions"] += 1
                    out.append(f"\n**[{when}] AUTHOR answers:** {ans}\n")
        else:
            if msg.get("model"):
                models[msg["model"]] += 1
            for b in blocks:
                t = b.get("type")
                if t == "text" and b.get("text", "").strip():
                    stats["assistant messages"] += 1
                    out.append(f"\n### [{when}] CLAUDE\n\n{b['text'].strip()}\n")
                elif t == "tool_use":
                    name, inp = b.get("name", ""), b.get("input") or {}
                    if name == "AskUserQuestion":
                        questions[b.get("id")] = True
                        lines = [f"\n**[{when}] CLAUDE asks:**\n"]
                        for q in inp.get("questions", []):
                            lines.append(f"- {q.get('question', '')}")
                            for o in q.get("options", []):
                                lines.append(f"  - {o.get('label', '')}: {o.get('description', '')}")
                        out.append("\n".join(lines) + "\n")
                    elif name not in ("ToolSearch", "ListAgents"):
                        stats["assistant actions"] += 1
                        out.append(f"- `{when}` Claude {action_line(name, inp)}")

    day = datetime.fromisoformat(first.replace("Z", "+00:00")).astimezone(LOCAL).strftime("%Y-%m-%d")
    dst = os.path.join(ROOT, "devlog", f"claude-session-{day}.md")
    head = [
        "# Development log: conversation with Claude Code",
        "",
        "This is an export of the author's working conversation with the AI coding assistant Claude Code",
        "(Anthropic) during the jam. The conversation is in Russian.",
        "",
        f"- Session: `{os.path.basename(src)[:-6]}`",
        f"- Period: {stamp(first)} — {stamp(last)}",
        f"- Models: {', '.join(m for m in models if not m.startswith('<')) or 'n/a'}",
        f"- Author messages: {stats['author messages']}, answers to the assistant's questions: {stats['author answers to questions']}",
        f"- Assistant messages: {stats['assistant messages']}, assistant actions (commands, file edits, editor calls): {stats['assistant actions']}",
        "",
        "What is included: every message typed by the author, every reply of the assistant, the assistant's",
        "questions with the author's answers, and one line per assistant action saying what was done.",
        "",
        "What is left out: command output, the model's internal reasoning, text the editor attached automatically",
        "(opened files, selections) and system reminders. Timestamps are from the tool's own session record.",
        "",
        "Produced by `tools/devlog/export_session.py` from the session record kept by Claude Code.",
        "",
    ]
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    with open(dst, "w", encoding="utf-8") as f:
        f.write("\n".join(head) + "\n".join(out) + "\n")
    print("written", dst, f"({os.path.getsize(dst) // 1024} KB)")
    print(dict(stats))


if __name__ == "__main__":
    main()
