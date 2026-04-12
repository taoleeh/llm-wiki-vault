# Skills Index

Load this file on session start. Do NOT load individual skill files until their trigger occurs.
When a trigger matches, read `skills/skills/<name>/SKILL.md` and follow its instructions.

---

## Wiki Operations

| Skill | File | Load when... |
|-------|------|--------------|
| ingest | skills/ingest.md | User drops a new source, says "ingest", or adds a file to raw/ |
| research | skills/research.md | User asks a question requiring wiki lookup or topic exploration |
| lint | skills/lint.md | User says /lint or asks to health-check the wiki |
| wrap-up | skills/wrap-up.md | User says /wrap-up or the session is ending |

---

## UI & Design

| Skill | File | Load when... |
|-------|------|--------------|
| frontend-design | skills/skills/frontend-design/SKILL.md | Building web components, pages, artifacts, or any UI from scratch |
| audit | skills/skills/audit/SKILL.md | User asks to audit interface quality, accessibility, performance, or theming |
| critique | skills/skills/critique/SKILL.md | User asks for UX/design feedback or evaluation |
| harden | skills/skills/harden/SKILL.md | User asks to make UI production-ready, handle edge cases, add error handling or i18n |
| normalize | skills/skills/normalize/SKILL.md | User asks to match design system, fix inconsistencies, or standardize UI |
| extract | skills/skills/extract/SKILL.md | User asks to extract reusable components or design tokens |
| animate | skills/skills/animate/SKILL.md | User asks to add animations or micro-interactions |
| delight | skills/skills/delight/SKILL.md | User asks to make UI more memorable, joyful, or personality-driven |
| optimize | skills/skills/optimize/SKILL.md | User asks to improve UI performance, loading speed, or rendering |
| polish | skills/skills/polish/SKILL.md | User asks for final quality pass before shipping |
| distill | skills/skills/distill/SKILL.md | User asks to simplify or reduce complexity in a design |
| bolder | skills/skills/bolder/SKILL.md | User asks to make a design more visually impactful or interesting |
| quieter | skills/skills/quieter/SKILL.md | User asks to tone down an aggressive or overly bold design |
| colorize | skills/skills/colorize/SKILL.md | User asks to add color or fix monochromatic interfaces |
| clarify | skills/skills/clarify/SKILL.md | User asks to improve UX copy, error messages, labels, or microcopy |
| adapt | skills/skills/adapt/SKILL.md | User asks to make UI work across screen sizes, devices, or platforms |
| onboard | skills/skills/onboard/SKILL.md | User asks to design or improve onboarding flows or empty states |
| web-design-guidelines | skills/skills/web-design-guidelines/SKILL.md | User asks to review UI against best practices or accessibility standards |
| teach-impeccable | skills/skills/teach-impeccable/SKILL.md | One-time setup to establish persistent design guidelines for a project |

---

## Frontend / React

| Skill | File | Load when... |
|-------|------|--------------|
| react-best-practices | skills/skills/react-best-practices/SKILL.md | Writing, reviewing, or refactoring React or Next.js code |
| react-native-skills | skills/skills/react-native-skills/SKILL.md | Building React Native or Expo mobile apps |
| composition-patterns | skills/skills/composition-patterns/SKILL.md | Refactoring components with composition or scaling component architecture |

---

## Cloudflare

| Skill | File | Load when... |
|-------|------|--------------|
| cloudflare | skills/skills/cloudflare/SKILL.md | Any Cloudflare development task: Workers, Pages, KV, D1, R2, AI, tunnels, security |
| wrangler | skills/skills/wrangler/SKILL.md | Running wrangler CLI commands for Workers, KV, R2, D1, secrets, deployments |
| workers-best-practices | skills/skills/workers-best-practices/SKILL.md | Writing or reviewing Cloudflare Workers code for production |
| web-perf | skills/skills/web-perf/SKILL.md | Auditing, profiling, or optimizing page load performance or Lighthouse scores |

---

## Stripe

| Skill | File | Load when... |
|-------|------|--------------|
| stripe-best-practices | skills/skills/stripe-best-practices/SKILL.md | Building, modifying, or reviewing any Stripe integration |
| upgrade-stripe | skills/skills/upgrade-stripe/SKILL.md | Upgrading Stripe API versions or SDKs |

---

## Bittensor

| Skill | File | Load when... |
|-------|------|--------------|
| bittensor-sdk | skills/skills/bittensor-sdk/SKILL.md | Any Bittensor operations: wallet, staking, subnet queries, metagraph, emissions |

---

## Dev Workflow

| Skill | File | Load when... |
|-------|------|--------------|
| test-driven-development | skills/skills/test-driven-development/SKILL.md | Implementing any feature or bugfix, before writing implementation code |
| systematic-debugging | skills/skills/systematic-debugging/SKILL.md | Encountering any bug, test failure, or unexpected behavior |
| writing-plans | skills/skills/writing-plans/SKILL.md | Given a spec or requirements for a multi-step task, before touching code |
| executing-plans | skills/skills/executing-plans/SKILL.md | Executing a written implementation plan with review checkpoints |
| subagent-driven-development | skills/skills/subagent-driven-development/SKILL.md | Executing implementation plans with independent parallel tasks |
| dispatching-parallel-agents | skills/skills/dispatching-parallel-agents/SKILL.md | Facing 2+ independent tasks that can run without shared state |
| using-git-worktrees | skills/skills/using-git-worktrees/SKILL.md | Starting feature work needing isolation, or before executing implementation plans |
| verification-before-completion | skills/skills/verification-before-completion/SKILL.md | About to claim work is complete or passing — before any success claims |
| requesting-code-review | skills/skills/requesting-code-review/SKILL.md | Completing tasks or implementing major features before merging |
| receiving-code-review | skills/skills/receiving-code-review/SKILL.md | Receiving code review feedback before implementing suggestions |
| finishing-a-development-branch | skills/skills/finishing-a-development-branch/SKILL.md | Implementation complete, tests pass, deciding how to integrate work |
| brainstorming | skills/skills/brainstorming/SKILL.md | Before any creative work — creating features, building components, adding functionality |
| playwright-cli | skills/skills/playwright-cli/SKILL.md | Automating browser interactions, testing web apps, filling forms, taking screenshots |

---

## Meta / Agent

| Skill | File | Load when... |
|-------|------|--------------|
| find-skills | skills/skills/find-skills/SKILL.md | User asks "how do I do X", "find a skill for X", or wants to extend capabilities |
| writing-skills | skills/skills/writing-skills/SKILL.md | Creating, editing, or verifying skills before deployment |
| using-superpowers | skills/skills/using-superpowers/SKILL.md | Starting any conversation — establishes how to find and use skills |
| caveman | skills/skills/caveman/SKILL.md | (see skill for trigger) |
| caveman-commit | skills/skills/caveman-commit/SKILL.md | (see skill for trigger) |
| caveman-review | skills/skills/caveman-review/SKILL.md | (see skill for trigger) |
