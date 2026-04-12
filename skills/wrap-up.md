# Skill: Wrap-Up

Triggered when the user says /wrap-up or the session is ending.

## Steps

1. Review the current session conversation and extract:
   - **Decisions made** — architectural choices, preferences, directions chosen
   - **Corrections** — things you got wrong that the user fixed
   - **Successful patterns** — approaches that worked well
   - **Unresolved issues** — open questions, things to pick up next session
   - **New preferences** — anything learned about how the user wants to work

2. Append a session summary to wiki/log.md:
   ```
   ## [YYYY-MM-DD] wrap-up | Session summary
   
   ### Decisions
   - ...
   
   ### Corrections
   - ...
   
   ### Patterns
   - ...
   
   ### Open issues
   - ...
   ```

3. Update any wiki pages that the session's decisions or corrections affect.

4. If the session revealed new routing rules (e.g. a new skill trigger, a new wiki section),
   suggest an update to AGENTS.md and skills/index.md for the user to approve.

5. Update wiki/index.md if new pages were created during the session.

## Conventions

- The log entry is the minimum. Do not skip wiki page updates if they are warranted.
- Unresolved issues should be specific enough that the next session can pick them up cold.
- Never truncate — capture everything worth remembering.
