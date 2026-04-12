# Skill: Ingest

Triggered when the user adds a new source to process.

## Steps

1. Read the source document in full.
2. Discuss key takeaways with the user before writing anything.
3. Write a summary page in wiki/sources/ with the following frontmatter:
   ```yaml
   ---
   tags: [source]
   date: YYYY-MM-DD
   type: article | paper | video | doc | note
   source_path: raw/filename
   ---
   ```
4. Update or create relevant entity pages in wiki/entities/ (people, projects, tools, orgs).
5. Update or create relevant concept pages in wiki/concepts/ (ideas, patterns, frameworks).
6. Note any contradictions with existing wiki pages explicitly on the affected pages.
7. Update wiki/index.md — add the new source page and any new entity/concept pages.
8. Append to wiki/log.md:
   ```
   ## [YYYY-MM-DD] ingest | Source Title
   Brief one-line note on what was added and what pages were touched.
   ```

## Conventions

- Cross-reference significant concepts with [[double brackets]].
- A single source may touch 10–15 wiki pages — that is expected and correct.
- Prefer updating existing pages over creating redundant new ones.
- If unsure whether to create a new page, ask the user.
