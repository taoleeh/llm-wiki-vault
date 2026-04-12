# Skill: Research

Triggered when the user asks a question or wants to explore a topic.

## Steps

1. Read wiki/index.md to find relevant existing pages.
2. Read those pages and synthesize an answer with citations to wiki pages.
3. If the answer requires information not in the wiki, say so clearly and suggest:
   - A source the user could add to raw/ for ingestion.
   - A web search the user could run and paste back.
4. If the answer is valuable (non-trivial synthesis, comparison, analysis), file it back
   into the wiki as a new page in wiki/queries/:
   ```yaml
   ---
   tags: [query]
   date: YYYY-MM-DD
   question: "The original question"
   ---
   ```
5. Update wiki/index.md if a new page was created.
6. Append to wiki/log.md:
   ```
   ## [YYYY-MM-DD] query | Short description of question
   ```

## Conventions

- Answers that disappear into chat history are wasted work — file anything worth keeping.
- Cite wiki pages, not raw sources directly.
- If the question reveals a gap (concept mentioned but no page exists), flag it for the user.
