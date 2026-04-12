# Skill: Lint

Triggered when the user says /lint or asks to health-check the wiki.

## Steps

1. Read wiki/index.md in full to get a map of all pages.
2. Scan pages systematically and check for:

   **Contradictions** — claims on one page that conflict with claims on another.
   **Stale claims** — information that newer sources may have superseded.
   **Orphan pages** — pages with no inbound [[links]] from other pages.
   **Missing pages** — concepts or entities referenced with [[brackets]] but no page exists.
   **Missing cross-references** — two pages that should link to each other but don't.
   **Data gaps** — topics thin on detail that a web search or new source could fill.

3. Produce a lint report with sections for each issue type found. For each issue, include:
   - The affected page(s)
   - What the problem is
   - A suggested fix

4. Ask the user which issues to fix now vs. defer.
5. Apply fixes to the wiki pages and update wiki/index.md if needed.
6. Append to wiki/log.md:
   ```
   ## [YYYY-MM-DD] lint | N issues found, M fixed
   ```

## Conventions

- Do not silently fix contradictions — always surface them for the user to adjudicate.
- Suggest new sources or questions that could fill identified gaps.
