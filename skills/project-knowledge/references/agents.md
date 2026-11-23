# A standing instruction for the project's agents

A spec stays true most cheaply when whoever changes the code corrects the spec in the same task, while the change is still in front of them. The block below asks for exactly that, in a few lines, from any agent that works in the repository, whether or not it has this skill. It goes into the file the agent reads at the start of a session:

| Agent | File |
| --- | --- |
| Codex, Cursor, Gemini CLI, GitHub Copilot and others that read it | `AGENTS.md` |
| Claude Code | `CLAUDE.md` |
| Gemini CLI, by default | `GEMINI.md` |
| Cursor rules | `.cursor/rules/project-spec.mdc` |
| GitHub Copilot | `.github/copilot-instructions.md` |

Add it only when the person agrees: it is a rule for everyone who works in the repository. `npx project-spec instructions --file AGENTS.md` writes it with the vault's path filled in, and replaces the block when run again; by hand, copy the text between the two marker lines, markers included, and put the vault's path where it says `{vault}`. Keep the block as short as it is: it is read at the start of every session. Its commands say `npx --yes`: without it `npx` asks before it downloads the package, and an agent cannot answer.

<!-- project-spec:start -->
## Project spec

`{vault}/` is this project's as-built spec. `notes/` has one page per feature with its numbered business rules (`BR-CHAT-03`), `gaps/` has the open questions, `00-index.md` is the way in. It says what the code does now.

- Before you change a feature, read its page.
- When your change alters what the product does, correct the spec in the same task, and keep the edit as small as the change:
  - a changed limit, message, condition or permission: correct that rule's row; the rule keeps its number
  - a new rule: a new row with the next free number; a rule that is gone: delete its row and never reuse the number
  - a new screen, endpoint or job: add it to its feature's page; a new feature gets a page of its own, linked from its area's page
- Edit only the pages of features you changed. Do not re-read other code, rewrite a page or start a review of the whole spec. A refactor, a rename, a test or a styling change needs no spec edit.
- Then run `npx --yes project-spec check --vault {vault}`. Run `npx --yes project-spec snapshot --vault {vault} --notes <ids of the pages you edited>` when `check` names no changed source for those pages other than files you changed.
- A doubt about the product is not written into a page: tell the person. Do not decide or close a gap.

With the project-knowledge skill installed, follow its "Record a change" section, which has the full rules.
<!-- project-spec:end -->
