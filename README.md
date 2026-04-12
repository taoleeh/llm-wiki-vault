# LLM Wiki Vault

A ready-to-use vault template for building a personal knowledge base with an LLM agent. Based on the [LLM Wiki pattern](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f) by Andrej Karpathy and the agent skill system popularised by the Claude Code and OpenCode communities.

Drop your sources in. Let the agent build and maintain the wiki. Never re-explain your context again.

---

## What this is

Most people use LLMs like search engines — paste a document, ask a question, get an answer, repeat from scratch next session. Nothing accumulates.

This vault changes that. Instead of retrieving from raw documents at query time, the agent **incrementally builds and maintains a persistent wiki** — a structured, interlinked collection of markdown files that compounds over time. Every source you ingest, every question you ask, every decision you make gets filed and cross-referenced. The next session picks up exactly where the last one left off.

The agent does all the maintenance. You do the thinking.

---

## What's included

```
vault/
├── AGENTS.md                  ← agent operating instructions
├── raw/                       ← your source documents (immutable)
├── wiki/                      ← agent-maintained knowledge base (created on first session)
└── skills/
    ├── index.md               ← skill manifest, loaded on session start
    ├── ingest.md              ← process a new source into the wiki
    ├── research.md            ← query the wiki and file valuable answers back
    ├── lint.md                ← health-check the wiki for gaps and contradictions
    ├── wrap-up.md             ← extract session learnings and persist them
    └── skills/                ← add your own skill library
```

The `skills/skills` folder is designed to be extended with your own skill library. The four wiki operation skills (`ingest`, `research`, `lint`, `wrap-up`) are the only ones included — everything else is up to you.

---

## How it works

**Three layers:**

- **`raw/`** — your curated source documents. Articles, PDFs, notes, transcripts. Immutable — the agent reads from them but never modifies them.
- **`wiki/`** — agent-generated markdown files. Summaries, entity pages, concept pages, cross-references, synthesis. The agent owns this entirely.
- **`AGENTS.md`** — the operating schema. Tells the agent how the wiki is structured, what conventions to follow, and which skills to load when.

**Four operations:**

- **Ingest** — drop a file in `raw/`, tell the agent to ingest it. It reads the source, extracts key information, updates relevant wiki pages, and logs the session. A single source may touch 10–15 wiki pages.
- **Research** — ask a question. The agent reads the wiki index, finds relevant pages, and synthesizes an answer. Valuable answers get filed back into the wiki as new pages so the work compounds.
- **Lint** — ask the agent to health-check the wiki. It surfaces contradictions, orphan pages, missing cross-references, and data gaps.
- **Wrap-up** — end every session with `/wrap-up`. The agent extracts decisions, corrections, and open issues, and writes them to the log. The next session reads the last few entries to resume context.

---

## Setup

**1. Clone the repo**

```bash
git clone https://github.com/taoleeh/llm-wiki-vault ~/vault
cd ~/vault
```

**2. Add your existing skills** (optional)

If you have an existing skill library, copy your skill subfolders into `skills/skills/` and add their entries to `skills/index.md`. The index format is:

```markdown
| skill-name | skills/skills/skill-name/SKILL.md | Load when... |
```

**3. Launch your agent**

```bash
opencode   # or: claude, codex, etc.
```

**4. Send this exact message to start your first session:**

> "Read raw/llmwiki.md in full. This describes the wiki pattern we are using.
> Then initialize the wiki structure by creating wiki/index.md and wiki/log.md,
> and ingest raw/llmwiki.md as the first source."

This single message does three things: gives the agent the pattern, scaffolds the wiki folder structure, and completes the first ingest — so you come out of the first session with a functioning wiki rather than an empty folder.

---

## Session workflow

```
Start session
  → agent reads AGENTS.md
  → agent loads 3 always-on skills
  → agent reads skills/index.md
  → agent reads wiki/index.md
  → agent reads last 3 log entries

During session
  → drop files in raw/, say "ingest"
  → ask questions, say "research"

End session
  → say "/wrap-up"
  → agent logs decisions, updates wiki, closes open threads
```

---

## Compatibility

This vault is agent-agnostic. It works with any LLM agent that reads a config file from the working directory:

| Agent | Config file |
|-------|-------------|
| OpenCode | AGENTS.md |
| Claude Code | CLAUDE.md (rename AGENTS.md) |
| OpenAI Codex | AGENTS.md |
| Gemini CLI | GEMINI.md (rename AGENTS.md) |

The skill system uses plain markdown files with a YAML frontmatter header. No vendor lock-in.

---

## Extending with skills

The `skills/index.md` manifest is how the agent discovers capabilities on demand. To add a skill:

1. Create `skills/skills/your-skill-name/SKILL.md` with a YAML frontmatter header:
   ```yaml
   ---
   name: your-skill-name
   description: What this skill does and when to use it
   ---
   ```
2. Add a row to `skills/index.md`:
   ```markdown
   | your-skill-name | skills/skills/your-skill-name/SKILL.md | Load when... |
   ```

The agent reads the index at session start and loads individual skill files only when their trigger condition is met. Skills that are large or detailed cost nothing until they're actually needed.

---

## Credits

- **LLM Wiki pattern** — Andrej Karpathy
- **Agent skill system** — Claude Code / Anthropic skill ecosystem
- **notebooklm-py** — Teng Ling (optional complement for bulk document offloading)

---

## License

MIT
