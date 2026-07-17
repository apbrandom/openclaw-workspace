# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

This is Vadim's personal OpenClaw workspace — the home directory for an AI assistant named **Лиза (Lisa)**. It is not a software project in the traditional sense; it is a configuration + knowledge base + memory system for a local AI agent.

**Vadim's profile:** Maritime superintendent and mechanical engineer (ship power plants), iOS development experience, learning OpenClaw deeply. Communicates in Russian. Needs engineering-level explanations, not beginner handholding.

## Session Protocol (Claude Code)

**At session start:** read `ROADMAP.md` and `ARCHITECTURE.md`. `ROADMAP.md` holds the concept (where we're heading) and the testable spec (R-XX requirements) for Lisa's behavior — the single source of truth for "what/how Lisa must do." `ARCHITECTURE.md` holds how the system is actually built right now — components, scripts, data stores, who calls whom — so structure doesn't need to be re-derived via Explore each session. Neither file is loaded into Lisa's own runtime (would bloat her per-message context); this is Claude-Code-only reading.

**At session end:** if goals, architecture, current state, or any R-XX requirement changed during the session, sync the relevant section of `ROADMAP.md` and/or `ARCHITECTURE.md`. Do not wait to be reminded — maintaining these files is Claude Code's job.

## Infrastructure

**OpenClaw** (v2026.5.28) — the core AI gateway, Node.js, ports 18789/18791 (loopback only).

```bash
systemctl --user status openclaw-gateway      # check status
systemctl --user restart openclaw-gateway     # restart
```

**Ollama** — local LLM, port 11434 (loopback only).

```bash
curl http://localhost:11434/api/tags   # health check
ollama run qwen3:14b   # primary Лизы @ 32k, KV q8_0. (30B-A3B-2507 настроена как опция, но не primary — галлюцинирует карточки, не зовёт ship-скилл)
```

**PDF tools** (installed system-wide):
```bash
pdftotext /path/file.pdf /path/out.txt                # extract text
pdftoppm -r 150 -png /path/file.pdf /tmp/page         # PDF → PNG
~/.openclaw/tools-venv/bin/python -c "import fitz; ..." # PyMuPDF for complex ops
```

There is no test suite, no build step, no linter. Verification is manual:
```bash
wc -c /path/to/file    # verify file size after edits (SOUL.md mandates this)
git status             # track workspace changes
```

## Architecture

```
OpenClaw Gateway (Node.js, ports 18789/18791)
├── Local LLM: Ollama / Qwen3 14B FP8 (port 11434)
├── Cloud LLM: Claude Opus (claude.ai subscription)
├── Memory: LanceDB (autoCapture + autoRecall) + SQLite (~/.openclaw/memory/main.sqlite)
├── Embeddings: nomic-embed-text via Ollama
├── Web search: SearXNG
├── Telegram: @Lisa_Local_Bot (display name «LisaDaemonBot»)
└── Skills: mcporter, oracle, notion, nano-pdf (skills/), obsidian (skills/)
```

**Hardware:** Minisforum X1 Pro, Ryzen AI 9 HX370, 32 GB DDR5 (WSL2 limited to 22 GB), RTX 5070 Ti eGPU (16 GB VRAM). WSL2 Ubuntu 26.04 LTS. No Docker.

## Key Files

| File | Purpose |
|------|---------|
| `ROADMAP.md` | Concept + testable spec (R-XX) for Lisa. Read at session start, sync at session end |
| `ARCHITECTURE.md` | How the system is built right now: components, scripts, data stores, dependencies. Read at session start, sync at session end. Claude-Code-only, not loaded into Lisa's runtime |
| `AGENTS.md` | Workspace rules: memory system, group chat behavior, heartbeats, red lines |
| `SOUL.md` | Lisa's identity, tone, partnership principles, mandatory file-editing rules |
| `MEMORY.md` | Long-term curated memory: hardware, infra config, Vadim's profile, current status |
| `IDENTITY.md` | Brief identity card |
| `HEARTBEAT.md` | Checklist for periodic proactive tasks |
| `memory/YYYY-MM-DD.md` | Daily session logs (raw notes) |
| `vault/ships/` | Vessel knowledge cards (ATLAS 1, TISA, PRUT, TURAN) in YAML+Markdown |
| `vault/ships_docs/` | Detailed ship documents |
| `vault/events/` | Important event log |
| `skills/nano-pdf/SKILL.md` | PDF creation/editing skill |
| `skills/obsidian/SKILL.md` | Obsidian vault sync skill |

## File Editing Rules (from SOUL.md — mandatory)

Before editing any file:
1. Run `wc -c /path/to/file` and note the size.
2. Announce intent if changing more than one section.

When editing:
- Change **only** the specified section.
- Use targeted edits (append, patch), not full rewrites.

After editing:
1. Run `wc -c /path/to/file` again.
2. New size must be **larger** if content was added.
3. If smaller — something was deleted; report it honestly.

## Memory System

Lisa wakes up fresh each session. Continuity comes from files:
- `MEMORY.md` — load only in main sessions (contains private context; do not expose in group chats)
- `memory/YYYY-MM-DD.md` — create daily notes here; write decisions and lessons, not just events
- `vault/ships/` — auto-update ship cards when a vessel is mentioned

Runtime provides startup context (AGENTS.md, SOUL.md, recent daily memory). Do not manually re-read these unless something is missing.

## Conventions

- **Language:** Russian for conversation, English for code and commands.
- **Response length:** 1-3 lines for completed tasks, ≤200 words for technical questions, ≤400 words for complex topics.
- **No AI clichés:** No "как я могу помочь?", no unnecessary apologies, no "конечно!".
- **Tone:** Direct partner, not a subordinate. Light irony is fine; sycophancy is not.
- Prefer `trash` over `rm`. Ask before any destructive or outbound action.
- Maximum 2 emoji per response.
