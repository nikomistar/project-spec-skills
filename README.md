<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/images/logo-dark.svg">
  <img src="docs/images/logo.svg" width="56" height="56" alt="Project Spec logo">
</picture>

# Project Spec Skills

**An agent reads your repository and writes two things: a spec of what the product does, and the questions it could not settle.**

For the moment after you built fast with AI and need to know what the product really does. The **spec** is plain Markdown in your repository: one page per feature, every business rule numbered, taken only from the code. Each doubt the agent has is a **gap**: one question on its own page, which a person rechecks and decides.

This is an early project. It has been used on a few real repositories; [VALIDATION.md](VALIDATION.md) says what was checked and what was not.

![A gap in the viewer: one question about the product, with who rechecked it, who decided it, its plan and the features it is about](docs/images/viewer-gap-page.png)

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

This first map is the long run: from one to a few hours of agent time, more for a big product. To go on where a session stopped: `Use the project-knowledge skill and continue the map from the inventory file.`

**3. Have it checked.** The map writes down what the product does and only the doubts it met on the way. The checks are a second request: nine [reviews](#reviews), each with a fixed list of questions. When the map is finished, paste this:

```text
Use the project-knowledge skill to rank the features: which ones should a review
read first, and why? Then tell me what I can run next.
```

It marks each feature high, medium or low from what it does, and answers with requests you can paste: one per review (`review the high-priority features for security`) and one per high-priority feature (`run every review on the feature "Checkout"`). A review stops when it has read the high-priority features and says how to go on. `npx project-spec next` prints the requests again at any time, with how far each review got.

**4. Read what it wrote:**

```sh
npx project-spec serve
```

The first page says how much is mapped and which reviews ran. The gap queue lists the questions, the most urgent first, with the low-priority ones folded away.

The agent writes only Markdown in that folder. It does not change application code, commit or push. Other ways to install, and pinning one version for a team: [Install and update](docs/install.md).

## Reviews

A review is a pass for one topic: the agent goes through every way into the product again with a fixed list of questions, so nothing is skipped because it looked fine. What the code answers becomes a rule on the feature's page. A doubt worth a decision becomes a gap with that topic; a small one is a line under "Noted" on the review's run page.

| Ask for | What it looks for |
| --- | --- |
| `its flows` | What lies between features: a state the next feature does not know, a link that leads nowhere, a step left in the middle, waiting for someone who never answers. |
| `its logic` | Rules that disagree with each other, a state, role or plan nobody decided for, what happens at the limit and to the last admin, what a plan or price change does to what already exists. |
| `security` | Who can reach each entry point, whose record it is, another way in that skips the check, which fields may be changed, what comes back, sign-in, secrets. |
| `abuse` | What one account can send too big or do too often, what the server believes because the caller said it, paid work and messages with no limit, what other people are served. |
| `validation` | One field checked differently by the form, the server and the database; an import or an admin screen that skips the rules. |
| `data` | States a record can get stuck in, what a delete leaves behind, writes with no transaction, two people saving at once. |
| `failure paths` | What happens when a job or another service fails: retries, half-done work, errors nobody sees. |
| `its API` | Endpoints nothing calls, two ways to do one thing, calls marked as outdated, a written contract that disagrees with the code. |
| `its UI` | Missing loading, empty and error states, the same control built twice, one thing under two names. |

**One review.** Paste this, with the words from the first column in place of `security`:

```text
Use the project-knowledge skill in review mode: review the product for security.
Go by the inventory file, one feature at a time, and ask every question of the
review guide. Read the code and run nothing. Write what matters as gaps, note
the small things on the run page, and tell me how many features you reviewed.
```

If the session stops before the end: `Use project-knowledge to continue the security review from its run page.`

**Which, and how many at once.**

- **By topic or by feature.** One list of questions over the features (`review the high-priority features for security`), or every list on one feature that matters (`run every review on the feature "Checkout"`). Every list over every feature in one go is not offered: it is quick and finds a fraction.
- **High first, the rest when you say.** A review stops after the high-priority features. Going on with the medium ones is your call, and `npx project-spec next` has the request.
- **One agent at a time.** Several agents on one spec do not see each other's gaps and write the same question twice.
- **Which features first.** The agent gives each feature a priority from what it does (money, accounts, other people's data, deleting, files, what is public) and writes it into the inventory file with the reason: `Priority: high (money, others-data)`. A review reads the high ones first. Change any line; your word stays.
- **Not every product needs all nine.** Begin with `its flows` and `its logic`. Add `security`, `abuse` and `validation` when the product has accounts and a server. An app with no server has little for `its API`.
- **To keep one short**, name an area: `review the billing area for security`.

A review opens every entry point again, so it takes about as long as the map of the features it covers; reading one level at a time keeps that short. It reads code and is not a scanner: for vulnerable or outdated packages use `npm audit` or a similar tool. `summary` and the viewer's first page show which reviews have run, when, and which have not.

## What you get

A folder of plain Markdown in your repository, `project-spec/` unless you name another. It also opens in Obsidian.

**The spec** says only what the code does. Each part of the product ("Orders and checkout") has a page that lists its features. Each feature has one page with the same sections every time: what it is for, how it works, its fields, and its business rules as numbered rows with the real values: the limit, the message, who may do it. A rule keeps its number for good, so anyone can say "BR-CANCEL-02 is wrong" instead of describing a screen.

![A feature page in the viewer: what the feature is for, how it works, and its business rules as numbered rows](docs/images/viewer-page.png)

**Gaps** are the questions, one per page: *"Should a customer be able to cancel their own packed pickup?"* The agent writes one when the code is missing something, when two places disagree, or when it cannot tell whether a behavior is meant, and it can recheck one against the code. Only a person decides: accept, reject or defer. A closed gap is kept with its reason, because the spec says what the code does and the gap is the one place that says why.

## Keep it current

A spec is only worth reading while it is true. The cheap way is to let whoever changes the code correct the spec in the same task, as an edit the size of the change: a changed validation message is one row of one table, not a new review of the project.

```sh
npx project-spec instructions --file AGENTS.md      # or CLAUDE.md, GEMINI.md, .cursor/rules/project-spec.mdc
```

This writes a short block into the file your agent reads at the start of a session (Codex, Cursor, Claude Code, Gemini CLI, GitHub Copilot). It asks the agent to read a feature's page before changing it and to correct the changed rules afterwards. For everything since the last review, by everyone: `Use project-knowledge to sync the vault.`

## Commands

### In the terminal

| Command | What it does |
| --- | --- |
| `npx project-spec serve` | Open the spec and the gap queue in the browser. |
| `npx project-spec summary` | Where the spec stands: how much of the product is mapped, the gaps by state and topic, each review and when it last ran. |
| `npx project-spec next` | What a review can take up next, as requests to paste into your agent: by topic and by feature, the high-priority features first. |
| `npx project-spec gaps --topic security` | List gaps, the most urgent first, each with its file. Also `--state`, `--priority`, `--area`, `--review`. |
| `npx project-spec check` | Find broken pages and the pages whose code changed since they were read. |
| `npx project-spec coverage` | What the code has that no page mentions yet. |
| `npx project-spec instructions --file AGENTS.md` | Ask every agent in the repository to keep the spec current ([above](#keep-it-current)). |
| `npx project-spec move --to DIR` | Move the spec to another folder without breaking its links. |
| `npx project-spec@latest update` | Refresh the installed skill. An older spec needs no conversion; [what each release changed](docs/install.md#upgrading-from-an-earlier-version). |

### Ask your agent

The skill has no commands of its own: you ask in words.

| When | Prompt |
| --- | --- |
| You want to know where things stand | `Use project-knowledge: what is the status of the spec?` |
| You changed the code | `Use project-knowledge to record this change in the spec.` |
| Others changed the code | `Use project-knowledge to record what changed last week.` |
| You want the gaps checked | `Use project-knowledge in gaps mode: recheck the high-priority gaps against the code.` |
| A gap is accepted | `Use project-knowledge to plan the gap <name>. Plan only.` |
| A page looks thin | `Use project-knowledge to explore <feature> until it is finished.` |
| You have one question | `Use project-knowledge to investigate: <question>.` |
| A document says how it should work | `Use project-knowledge to audit <document> against the code.` |

The request for a review is [above](#reviews). More prompts are in [Working with the skills](docs/workflows.md#example-prompts).

## The viewer

`npx project-spec serve` opens one local page, read from the files on disk. Nothing is built or uploaded, and it is not copied into your project. It shows the spec, the gap queue with its filters, and what was checked; "Copy for AI" turns a page and your own words into a request for your agent. [The viewer](docs/viewer.md) shows every screen, and says how to show the spec on a development server for the rest of the team.

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
