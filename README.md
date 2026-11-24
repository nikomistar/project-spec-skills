<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/images/logo-dark.svg">
  <img src="docs/images/logo.svg" width="56" height="56" alt="Project Spec logo">
</picture>

# Project Spec Skills

**An agent reads your repository and writes two things: a spec of what the product does, and the questions it could not settle.**

For the moment after you built fast with AI and need to know what the product really does. The **spec** is plain Markdown in your repository: one page per feature, every business rule numbered, taken only from the code. Each doubt the agent has is a **gap**: one question on its own page, which a person rechecks and decides.

This is an early project. It has been used on a few real repositories; [VALIDATION.md](VALIDATION.md) says what was checked and what was not.

![A gap in the viewer: one question about the product, with who rechecked it, who decided it, its plan and the features it is about](docs/images/viewer-gap-page.png)

## What you get

A folder in your repository, `project-spec/` unless you name another:

```text
project-spec/
  areas/    one page per part of the product: a map of its features
  notes/    one page per feature: what it is for, how it works, its numbered rules
  gaps/     one page per question about the product
  plans/    a plan for a gap a person accepted
  runs/     what each pass read, and each review
```

It is plain Markdown and also opens in Obsidian. The two layers stay apart: a spec page says only what the code does, and a doubt is never written into it.

### The spec: areas, features, rules

- **An area** is a part of the product as a person would name it: "Orders and checkout", "Accounts and access". Its page is a map: what the area covers, and one line per feature.
- **A feature** has one page, with the same sections every time: what it is for and who uses it, how it works, its fields, its business rules. A feature too big for one page has parts.
- **A rule** is one numbered row with the real values: the limit, the message, who may do it.

```markdown
# Only requested pickups are currently cancellable

A customer who no longer needs a pickup cancels it, and the service lets that
happen only before anyone has started work on it.

## Business rules

| ID | Rule |
| --- | --- |
| BR-CANCEL-01 | A pickup can be cancelled only while its state is `requested`. |
| BR-CANCEL-02 | In any other state the cancellation is refused with "Only requested pickups can be cancelled" and nothing is changed. |
```

A rule keeps its number for good, so a reviewer, a tester or a support person can say "BR-CANCEL-02 is wrong" instead of describing a screen. A page can also say who may use the feature (`access: ["admin"]`). When a file a page relies on changes, the page is marked for re-reading.

### Gaps: the questions

A gap is one question about the product that a person can check and decide: *"Should a customer be able to cancel their own packed pickup?"* The agent writes one when the code is missing something, when two places disagree, or when it cannot tell whether a behavior is meant. The page says what the code does today, asks the question, gives the evidence, and then keeps its own recheck, discussion and decision.

| State | What it means | Who moves it on |
| --- | --- | --- |
| Needs recheck | The agent wrote it; nobody has confirmed that it still describes the code. | An agent or a person rechecks it. |
| Needs decision | Rechecked. It waits for an answer. | A person: accept, reject or defer. |
| Accepted | Someone decided it should be done. A plan can be written for it. | Whoever builds it; it closes when the code answers it. |
| Deferred | Not now. | A person, later. |
| History | Done, rejected or a duplicate. | Kept, with the reason. |

The agent proposes and rechecks; only a person decides, and the agent never records a decision nobody made. A closed gap is not deleted: the spec says what the code does, and the gap is the one place that says why.

Expect many. On the two products this was first used on, the map left more than 150 gaps each, so every gap has two labels to read the queue by:

- **Its area**, the part of the product it is about.
- **Its topic**, what kind of problem it is:

| Topic | The gap is about |
| --- | --- |
| `security` | Who can reach, see or change what; tokens and secrets. |
| `validation` | A field checked differently, or not at all, by the form, the server and the database. |
| `data` | Records that can be lost, damaged or out of step with each other. |
| `logic` | A business rule that is missing, unclear or contradicts another. |
| `ui` | What a person sees: states, texts, the same thing looking different in two places. |
| `api` | What another system calls: unused, undocumented or inconsistent endpoints. |
| `ops` | Jobs, schedules, configuration, what happens when something fails. |

## Start

You need an agent that can read your repository (Claude Code or Codex), Python 3.10+, Git, and Node 18+ for the `npx` commands.

**1. Install the skill** (once per machine):

```sh
npx project-spec install --claude      # or --codex
```

**2. Open your agent in the project and paste this:**

```text
Use the project-knowledge skill to build a knowledge vault for this repository.
Put it in project-spec/.

First take the inventory: every app and package, and every way into each one:
what a person can open, what another system can call, what runs on its own and
what the product sends out. Write it to the inventory file before any page.

Then go one feature at a time and finish each before the next. Describe only
what the code does: one page per feature with numbered business rules, and
every doubt as its own gap.

If you run out of time, stop at the end of a feature and tell me how many
features are finished, in progress and not started.
```

**3. Read what it wrote:**

```sh
npx project-spec serve
```

This first map is the long run: from one to a few hours of agent time, more for a big product. To go on where a session stopped: `Use the project-knowledge skill and continue the map from the inventory file.`

The agent writes only Markdown in that folder. It does not change application code, commit or push. Other ways to install, and pinning one version for a team: [Install and update](docs/install.md).

## Commands

### In the terminal

| Command | What it does |
| --- | --- |
| `npx project-spec serve` | Open the spec and the gap queue in the browser. |
| `npx project-spec summary` | Where the spec stands: how much of the product is mapped, the gaps by state and topic, each review and when it last ran. |
| `npx project-spec gaps --topic security` | List gaps, the most urgent first, each with its file. Also `--state`, `--priority`, `--area`. |
| `npx project-spec check` | Find broken pages and the pages whose code changed since they were read. |
| `npx project-spec coverage` | What the code has that no page mentions yet. |
| `npx project-spec instructions --file AGENTS.md` | Ask every agent in the repository to keep the spec current ([below](#keep-it-current)). |
| `npx project-spec build --out FILE` | The viewer as one file, to show on a server. |
| `npx project-spec move --to DIR` | Move the spec to another folder without breaking its links. |
| `npx project-spec status` / `update` | Where the skill is installed, and refresh those copies. |

### Ask your agent

The skill has no commands of its own: you ask in words.

| When | Prompt |
| --- | --- |
| You want to know where things stand | `Use project-knowledge: what is the status of the spec?` |
| You changed the code | `Use project-knowledge to record this change in the spec.` |
| Others changed the code | `Use project-knowledge to record what changed last week.` |
| You want one topic checked on purpose | `Use project-knowledge in review mode: review the product for security.` |
| You want the gaps checked | `Use project-knowledge in gaps mode: recheck the high-priority gaps against the code.` |
| A gap is accepted | `Use project-knowledge to plan the gap <name>. Plan only.` |
| A page looks thin | `Use project-knowledge to explore <feature> until it is finished.` |
| You have one question | `Use project-knowledge to investigate: <question>.` |
| A document says how it should work | `Use project-knowledge to audit <document> against the code.` |

More prompts are in [Working with the skills](docs/workflows.md#example-prompts).

### Reviews

The map raises the doubts it meets on the way. A review is a separate pass for one topic: the agent goes through every way into the product again with a fixed list of questions, so nothing is skipped because it looked fine. What the code answers becomes a rule on the feature's page; each doubt becomes a gap with that topic.

| Ask for | What it looks for |
| --- | --- |
| `security` | Who can reach each entry point, whose record it is, another way in that skips the check, which fields may be changed, what comes back, sign-in, secrets. |
| `abuse` | What one account can send too big or do too often, what the server believes because the caller said it, paid work and messages with no limit, what other people are served. |
| `validation` | One field checked differently by the form, the server and the database; an import or an admin screen that skips the rules. |
| `data` | States a record can get stuck in, what a delete leaves behind, writes with no transaction, two people saving at once. |
| `its API` | Endpoints nothing calls, two ways to do one thing, calls marked as outdated, a written contract that disagrees with the code. |
| `its UI` | Missing loading, empty and error states, the same control built twice, one thing under two names. |
| `failure paths` | What happens when a job or another service fails: retries, half-done work, errors nobody sees. |

A review opens every entry point again, so it takes about as long as the map of the features it covers. Run one topic at a time, and name an area (`review the billing area for security`) to keep it short. It reads code and is not a scanner: for vulnerable or outdated packages use `npm audit` or a similar tool. `summary` and the viewer's first page show which reviews have run, when, and which have not.

## Keep it current

A spec is only worth reading while it is true. The cheap way is to let whoever changes the code correct the spec in the same task, as an edit the size of the change: a changed validation message is one row of one table, not a new review of the project.

```sh
npx project-spec instructions --file AGENTS.md      # or CLAUDE.md, GEMINI.md, .cursor/rules/project-spec.mdc
```

This writes a short block into the file your agent reads at the start of a session (Codex, Cursor, Claude Code, Gemini CLI, GitHub Copilot). It asks the agent to read a feature's page before changing it and to correct the changed rules afterwards. For everything since the last review, by everyone: `Use project-knowledge to sync the vault.`

## The viewer

One local page, read from the files on disk. Nothing is built or uploaded, and it is not copied into your project. The spec also opens in Obsidian, so the viewer is optional.

- **Read** a feature page: its purpose, its flow, its rules.
- **Work the gaps**: the queue by state, with filters for area, topic, kind and priority and a field that finds a gap by its words.
- **Ask**: "Copy for AI" turns a page and your own words into a request for your agent.
- **See what was checked**: the first page shows how much is mapped and when each review last ran.

![A feature page in the viewer: what the feature is for, how it works, and its business rules as numbered rows](docs/images/viewer-page.png)

| Gap queue | Copy for AI |
| --- | --- |
| ![The gap queue with its states as tabs and filters for words, area, kind, topic and priority](docs/images/viewer-gaps.png) | ![The Copy for AI dialog with the exact text that will be copied](docs/images/viewer-copy.png) |
| **Search** | **Recent changes** |
| ![Search results grouped into features, gaps and files](docs/images/viewer-search.png) | ![The vault's Git history, one line per commit](docs/images/viewer-changes.png) |

[The viewer](docs/viewer.md) describes every screen, and how to show the spec on a development server for the rest of the team.

## Upgrading

```sh
npx project-spec@latest update      # refresh every installed copy of the skill
npx project-spec@latest check       # an older spec still passes; this lists anything to fix
```

Your spec needs no conversion: every release since 0.7.0 only added optional things to it. [Upgrading from an earlier version](docs/install.md#upgrading-from-an-earlier-version) says what each release changed and what to do.

## Read more

| Page | What is in it |
| --- | --- |
| [Install and update](docs/install.md) | npm, the Claude Code plugin, Codex, a manual copy, keeping copies current. |
| [What the spec contains](docs/spec.md) | The sections of a feature page, big features and several apps, how deep the first map goes, the files in the vault. |
| [Working with the skills](docs/workflows.md) | Example prompts, reviews, keeping the spec current, deciding gaps, two people updating the vault. |
| [The viewer](docs/viewer.md) | Every screen, a short command to open it, and the spec on a server. |
| [Parcel Desk](examples/parcel-desk/README.md) | A small fictional project with a ready-made vault to try the viewer on. |
| [VALIDATION.md](VALIDATION.md) | What was actually checked for each release, and the limits. |
| [CONTRIBUTING.md](CONTRIBUTING.md) | Checks, skill boundaries and how releases are made. |

## What it does not do

- The agent writes the claims. The helpers check structure and track which files changed; a helper alone does not understand your code.
- The spec says what the code does. It does not prove that the deployed application works.
- Nothing runs by itself: no schedule, no hooks, no commits or pushes. You share the Markdown through your normal Git workflow.
- No MCP server, cloud service, paid API or Obsidian plugin is needed.

The skill and the example are original work under the [MIT license](LICENSE). This is an independent project; Obsidian and the agent hosts are not its sponsors.
