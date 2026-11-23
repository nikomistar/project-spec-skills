# Install and update

These are [Agent Skills](https://agentskills.io/specification): each folder has a `SKILL.md` entry point. They require an agent that can read your repository. The knowledge helpers need **Python 3.10+** and **Git**; they have no package dependencies. No MCP server, cloud service, paid API or Obsidian plugin is required by the bundle.

## With npm

The package is [`project-spec`](https://www.npmjs.com/package/project-spec) on the npm registry, with one command of the same name. It needs Node 18+ in addition to Python. Nothing has to be installed first:

```sh
npx project-spec install --claude      # or --codex, or --dir knowledge/tooling
npx project-spec serve                 # the viewer for the project in the current folder
npx project-spec build --out FILE      # the same viewer as one file, to show on a server
npx project-spec coverage              # what the code has that no spec page mentions yet
```

Then ask your agent to use the `project-knowledge` skill ([example prompts](workflows.md#example-prompts)).

To pin one version for everyone on a project, add it as a development dependency:

```sh
npm install --save-dev project-spec
```

The lockfile then pins the version, and `npm update project-spec` moves it forward. The command keeps every copy of the skills in step with that version:

```sh
npx project-spec status    # where the copies are and whether each is current
npx project-spec update    # refresh every copy that status lists
```

`status` and `update` look in `~/.claude/skills`, `~/.codex/skills` and the usual folders of the current project (`knowledge/tooling`, `.claude/skills`, `.codex/skills`, `.agents/skills`). `update` refreshes what is there and adds nothing new; `install` adds. A copy you edited by hand is not replaced unless you pass `--force`, and the old files are kept under `~/.project-spec/backups` first. `--skills project-knowledge` limits an install to the skills you name.

A copy of a skill holds its instructions and, for `project-knowledge`, four helper scripts: about 2,900 lines, nothing else. The viewer page stays in the package and is opened with `npx project-spec serve`. `install --with-viewer` adds the page to a copy, for a place where the helpers run without Node (a Python-only build step, for example); `install --no-viewer` takes it out again. `update` keeps a copy as it is: with the viewer if it has one, without if not. Copies made by versions before 0.10.0 have the viewer and keep it until you run `install` with `--no-viewer` for their folder.

To run the unreleased version from this repository, use `npx github:nikomistar/project-spec-skills status` in place of `npx project-spec status`.

## Upgrading from an earlier version

Two commands bring an installation up to date. `@latest` matters: without it `npx` may run a version it downloaded earlier.

```sh
npx project-spec@latest update      # refresh every copy that status lists
npx project-spec@latest check       # run it in a project that has a spec
```

When the package is a development dependency of the project, move it first with `npm install --save-dev project-spec@latest`, then run `npx project-spec update`. With the Claude Code plugin, Claude Code updates the skill; a copy made by hand is copied again.

**Your spec needs no conversion.** Every release since 0.7.0 only added optional things to the vault, so pages written by an older version still pass `check`. A spec written before the spec and the gap queue were separated is the one exception: follow the [migration guide](../skills/project-knowledge/references/migrate.md).

What each release changed, newest first. Read down to the version you have now.

| You have | What changed | What to do |
| --- | --- | --- |
| 0.14.1 | 0.14.2 writes `npx --yes project-spec` into the block for agent instruction files: without `--yes`, `npx` asks before it downloads the package, and an agent stops there. The package's links point at the repository's new address, `nikomistar/project-spec-skills`. | If you use the block, run `npx project-spec instructions --file AGENTS.md` again (and for each other file that has it). An old link to the repository still redirects. |
| 0.14.0 | 0.14.1 changed what "Change the behavior" copies in the viewer: the change comes first as an order, and nothing tells the agent to ask its questions and wait. | Nothing. A project that keeps its own copy of the viewer page gets it with `update` or a fresh copy of the file. |
| 0.13.0 | 0.14.0 added three reviews (`validation`, `data`, `failures`), the topic `validation` for gaps, the `summary` and `gaps` commands, a word filter in the gap queue, and "What was checked" on the viewer's first page. | Nothing is required. A review run page written by 0.13.0 is recognised by its name (`<date>-review-<topic>.md`). If it links to pages, `check` reports it: ask "Use project-knowledge to fix the errors check reports" and the links become plain names. To see where a spec stands: `npx project-spec summary`. |
| 0.12.0 | 0.13.0 added a topic on gaps (`security`, `data`, `logic`, `ui`, `api`, `ops`; `validation` since 0.14.0) with a filter in the queue, `access` on a feature page (who may use it), and the `review <topic>` mode. | Nothing is required: gaps without a topic and pages without `access` still pass `check`. To give old gaps a topic, ask: "Use project-knowledge in gaps mode: give every gap a topic from its page." It reads only the gap pages. `access` is filled in by a security review, or when a page is next re-read. |
| 0.11.x | 0.12.0 lets you choose the folder of the spec. A new spec goes to `project-spec/` instead of `knowledge/<project>/`, and the commands find a spec in any folder. | Nothing is required: a spec under `knowledge/<project>/` stays where it is and is still found. To shorten the path, `npx project-spec move --to project-spec` moves it and repoints its links; then update a `--vault` in your scripts and run `npx project-spec instructions --file ...` again if you use that block. |
| 0.10.0 | 0.11.0 removed the `spec-change` skill. Planning a gap and recording a code change are now part of `project-knowledge`. | `update` deletes the old `spec-change` copies and keeps them under `~/.project-spec/backups`. In saved prompts, replace "Use the spec-change skill" with "Use the project-knowledge skill to plan the gap ..." or "... to record this change in the spec". |
| 0.10.0 | 0.11.0 added the block for agent instruction files, and a gap's `created` date. | Optional: `npx project-spec instructions --file AGENTS.md`. Nothing for old gaps: the viewer takes their date from the first commit of the page. |
| 0.9.x | 0.10.0 moved the viewer out of the skill folder, and the helper tests out of the package. | Open the viewer with `npx project-spec serve`. A copy made before 0.10.0 still has the viewer, and `update` keeps it there; `npx project-spec install --dir <folder> --no-viewer` removes it. If a script of yours runs `python3 <skill>/scripts/knowledge.py serve` or `build` from a copy without the viewer, add `--with-viewer` to the install, or switch the script to `npx project-spec`. |
| 0.9.0 or 0.9.1 | 0.9.2 added the inventory file, the checklist a map is continued from. | Nothing is required. To get one for an existing spec, ask: "Use project-knowledge to take the inventory for the existing spec; do not rewrite the pages." |
| 0.8.x | 0.9.0 made a first map deep: one feature at a time, parts for a big feature (`parent`), a section for where the apps differ, and the `coverage` command. | Nothing is required. Pages written before are still valid; a page that is thin gets deeper with "Use project-knowledge to explore <feature> until it is finished." |
| 0.7.0 | 0.8.0 added `build`, the viewer as one file for a server. | Nothing. |

After any upgrade, `npx project-spec status` shows where the copies are and whether each is current.

## Claude Code plugin

The repository is also a plugin marketplace for Claude Code. Inside Claude Code:

```text
/plugin marketplace add nikomistar/project-spec-skills
/plugin install project-spec@project-spec-skills
```

The skill then appears as `/project-spec:project-knowledge`, and Claude Code updates it with the plugin. The plugin does not add the `project-spec` command; ask the agent to open the viewer (the plugin carries the page), or use `npx project-spec serve`.

## Codex

Ask the built-in skill installer:

```text
Install these skills from nikomistar/project-spec-skills:
skills/project-knowledge
```

If you already have a skill with the same name, compare versions before replacing it. The installer in Codex handles its own destination. In Codex you can name a skill with `$name`, for example `$project-knowledge`.

## Claude Code, by hand

Copy the whole skill folder (it contains the references and helper scripts, and no viewer: use `npx project-spec serve` for that) to one of:

- `~/.claude/skills/<name>/` to use it in all your projects, or
- `.claude/skills/<name>/` inside one project.

```sh
git clone https://github.com/nikomistar/project-spec-skills.git
mkdir -p ~/.claude/skills
cp -R project-spec-skills/skills/project-knowledge ~/.claude/skills/
```

Then ask in plain language, or invoke a skill by name with `/<name>`, for example `/project-knowledge`. Claude Code finds a skill from its description, so an ordinary request often picks the right one.

## Any agent with repository access

Clone this repository, then ask the agent to read the chosen `skills/<name>/SKILL.md` and follow it in your target project. Keep that skill's directory intact so its references and scripts resolve. Use your host's documented installation mechanism if it supports skills. Hosts other than Codex and Claude Code have not been integration-tested, and the format change described in [VALIDATION.md](../VALIDATION.md) has not yet been tested with an agent on any host.
