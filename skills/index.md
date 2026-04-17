# Skills Index

Load this file on session start. Do NOT load individual skill files until their trigger occurs.
When a trigger matches, read the corresponding skill file and follow its instructions.

---

## Wiki Operations

| Skill | File | Load when... |
|-------|------|--------------|
| ingest | skills/ingest.md | User drops a new source, says "ingest", or adds a file to raw/ |
| research | skills/research.md | User asks a question requiring wiki lookup or topic exploration |
| lint | skills/lint.md | User says /lint or asks to health-check the wiki |
| wrap-up | skills/wrap-up.md | User says /wrap-up or the session is ending |
