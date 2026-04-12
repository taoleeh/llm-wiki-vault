# AGENTS.md

## How this vault works
This is an LLM-maintained wiki. You write and maintain all files in wiki/.
Raw sources go in raw/ (never modify them). You own everything in wiki/.
Skills live in skills/skills/ — most are loaded on demand, not at session start.

---

## On session start

1. Load these skill files unconditionally:
   - skills/skills/caveman/SKILL.md
   - skills/skills/verification-before-completion/SKILL.md
   - skills/skills/using-superpowers/SKILL.md

2. Read skills/index.md to know what other skills are available and their triggers.
   Do not load any other skill files until their trigger occurs.

3. Read wiki/index.md to orient yourself in the knowledge base (if it exists).

4. Read the last 3 entries of wiki/log.md for recent context (if it exists).

---

## Wiki structure

```
vault/
  AGENTS.md              ← this file
  skills/
    index.md             ← skill manifest, loaded on session start
    ingest.md            ← wiki operation skills
    research.md
    lint.md
    wrap-up.md
    skills/<skill-name>/        ← all other skills live in subfolders
      SKILL.md
  wiki/
    index.md             ← master catalog of all wiki pages, always update after changes
    log.md               ← append-only session log, never overwrite
    sources/             ← one summary page per ingested source
    entities/            ← people, projects, tools, organisations
    concepts/            ← ideas, patterns, frameworks
    queries/             ← valuable answers filed back as pages
  raw/                   ← immutable source documents, never modify
```

---

## Wiki conventions

- All wiki pages use YAML frontmatter:
  ```yaml
  ---
  tags: [source | entity | concept | query]
  date: YYYY-MM-DD
  ---
  ```
- Cross-reference significant concepts with [[double brackets]].
- wiki/index.md lists every page with a one-line summary, organised by category.
- wiki/log.md entries use this prefix format:
  `## [YYYY-MM-DD] <action> | <title>`
  where action is one of: ingest, query, lint, wrap-up

---

## Skill triggers

When a user request matches a trigger in skills/index.md, read that skill file
and follow its instructions exactly before proceeding.

For the four wiki operation skills, triggers are:

| Trigger | Skill |
|---------|-------|
| User adds a file to raw/ or says "ingest" | skills/ingest.md |
| User asks a question or says "research" | skills/research.md |
| User says /lint | skills/lint.md |
| User says /wrap-up or session is ending | skills/wrap-up.md |

---

## Routing

*(empty for now — add entries here as specific wiki pages are created and become useful retrieval targets)*
