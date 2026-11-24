# Vault format and helper contract

A vault has two layers. The **spec layer** (`areas/`, `notes/`) is an as-built specification: what the source code does now, and nothing else. The **gap layer** (`gaps/`, `plans/`) holds everything that is missing, doubtful, contradictory or proposed, one question per page, each with its own recheck and human decision. Chat agreements, intentions and plans are not spec. See [gaps.md](gaps.md) for how to write the gap layer.

Plain Markdown, wikilinks and flat YAML properties. Use **JSON values inside YAML** so the stdlib-only helper needs no YAML dependency. Each value is a JSON string, array, boolean or number on one line; no nested YAML or block scalars. This is valid Obsidian YAML. Put complex evidence in prose.

## Layout

```text
project-spec/            or the folder the person chose; older vaults are in knowledge/<project>/
  00-index.md           start here
  areas/                maps of related capabilities (spec)
  notes/                source-backed behaviors and rules (spec)
  gaps/                 one question per page (gap)
  plans/                one plan per accepted gap (gap)
  runs/                 review history and evidence limits
  .knowledge/           sources.json (reviewed fingerprints), review.json (reviewed Git checkpoint),
                        inventory.md (the checklist of the map)
```

Nothing in the vault is generated for reading: every file is a page someone wrote or the reviewed state under `.knowledge/`. The local reports of a sync scan (`sync.html`, `.knowledge/sync-plan.json`, `.knowledge/sync-status.md`) are ignored by Git and are not part of the vault's content. The viewer shows the spec and the gap queue from the pages themselves.

Wikilinks are vault-relative without `.md`; use full paths to avoid ambiguity. Filenames avoid `# | ^ :` and brackets. Code links are relative to the note location, URL-encoded as necessary. Source metadata paths are relative to the **repository**, not the vault.

Markdown beneath any `.obsidian`, `.trash`, or `.knowledge` path component is excluded from note discovery and validation. Deleted notes and plugin documentation must not become graph nodes.

## Page types

| Layer | `type` | Folder | Meaning |
| --- | --- | --- | --- |
| Spec | `area` | `areas/` | Map of one capability area as implemented. |
| Spec | `note` | `notes/` | One implemented behavior, rule or workflow, backed by source. |
| Gap | `gap` | `gaps/` | One question about something missing, unverified, contradictory or proposed. |
| Gap | `plan` | `plans/` | Implementation plan for exactly one accepted gap. |
| Navigation | `index` | vault root | Hand-written entry pages. |
| History | `run` | `runs/` | Record of one research, sync, audit or investigation pass. |

## Properties

```yaml
---
id: "collection-periods"
title: "Each period stores its own checklist and files"
type: "note"
status: "current"
areas: ["collections"]
tags: ["knowledge", "workflow"]
aliases: ["Collection periods"]
sources: ["src/server/cases/service.ts"]
updated: "2026-11-14"
---
```

Required on every page: `id`, `title`, `type`, `areas`, `sources`, `updated`. `status` is also required on `area`, `note`, `index`, `run` and `plan`, and is an error on `gap`.

- `id`: unique stable ASCII slug (`[a-z0-9-]+`).
- `status` on `area` and `note`: `current`, `partial`, `stale`, `superseded`. On `index`, `run` and `plan` additionally `planned`.
  - `current`: the whole feature was read and the page checked against the current sources. This is not a runtime test or a deployment claim; say in prose which version and environment you checked.
  - `partial`: some of the feature or area was not read. The page ends with a line saying what is left, and stays `partial` until the feature is finished.
  - `stale`: its sources changed or disappeared and it has not been re-read.
  - `superseded`: replaced by another page, kept as a pointer.
  - `planned` (index, run, plan): describes intent not yet carried out.
  - Doubt about a claim is not a status. If you cannot support a statement, leave it out of the spec note and open a gap.
- `areas`: existing **area IDs**. Each `note`, `gap` and `plan` needs at least one. Area pages may list themselves or leave empty; index and run pages may be empty.
- `sources`: existing files read as evidence, repository-relative; no directories, credentials, absolute paths or paths escaping the repo. A `current` note needs evidence; gaps, plans and maps may have none.
- `updated`: last substantive review date (`YYYY-MM-DD`).
- Optional `parent`, on a `note` only: the `id` of the feature note this note is a part of. The vault has three levels: area, feature, part. The parent is a note of the same first area that has no `parent` itself, and its body links to each of its parts; `check` rejects anything else. The viewer lists a part under its feature.
- Optional `access`, on a `note` only: who may use the feature, as the code enforces it, in the product's own role names: `["admin"]`, `["owner", "manager"]`. Use `"public"` when no sign-in is needed and `"signed-in"` when any signed-in person may. It repeats, for the viewer and for a reader scanning a list, what a numbered rule on the page already says ("BR-USERS-01: only an admin may open the page"), so it is never the only place the restriction is written, and it changes when that rule changes. Leave it out when the code was not read for it, and on a reference note; a part states its own when it differs from its feature. The viewer shows it beside the title ("Access: admin").
- Optional `review`, on a `run` page only: the topic a review pass looked at, in lower case with hyphens (`"security"`, `"validation"`, `"failures"`). Together with the page's checklist of features it tells the viewer and the `summary` command which reviews were run, when, and how far each got ([the review guide](review.md)). A run page named `<date>-review-<topic>.md` counts as one without the property.
- Optional `tags`, `aliases`, `task_ids`: string arrays. Optional `summary` and `verification`: strings. An area's `summary` introduces it in the viewer; a note's `summary` is its plain-language statement of what the product does, shown first in the viewer's Read view (write one for every note; `check` does not require it, so older vaults still open).

Gap-only properties are errors on any other page type, `gap` is an error on a page that is not a plan, and `priority` and `confidence` are allowed only on gap and plan pages. String properties (and strings inside arrays) may not contain control characters, including line separators. Gap-only properties (`kind`, `recheck`, `rechecked_by`, `rechecked_on`, `decision`, `decided_by`, `decided_on`, `duplicate_of`, optional `created`, `topic`, `priority`, `confidence`) and the plan-only `gap` property are defined in [gaps.md](gaps.md), with the rules for who may set each. Gap state (`needs-recheck`, `needs-decision`, or the decision value) is derived from them and never written into Markdown. A recheck has one meaning for every gap kind: does the `Current behavior` section still describe the code? `confirmed` means it does (confirmed, still holds; for a proposal, the capability is still absent) and `not-reproduced` means it no longer does; neither judges whether a proposal is worth doing, which is a person's decision (see [what a recheck means](gaps.md#what-a-recheck-means)). `recheck: "outdated"` means the cited sources changed after the last recorded recheck; `rechecked_by` and `rechecked_on` stay, the `Recheck` section must have text, and an open gap with it is `needs-recheck`.

## Body

Spec pages state facts about the code for a person who wants to know what the product does. The facts a person looks up are what a feature is for and its concrete rules: limits, required fields, defaults, formats, when an action is available or disabled, what an empty list shows, which message appears, who may do it, what starts a job and how often. A note gives these values, not only the mechanism that applies them, in the product's words rather than the code's.

There are two shapes of note.

A **feature note** is the one page for one screen, feature, flow or rule, and all feature notes share one shape:

| Part | Heading | Holds |
| --- | --- | --- |
| Opening | none, right under the title | What the feature is for, who uses it, where they find it. One short paragraph. |
| Flow | `## How it works` | What a person does and what happens, in order. Left out when there is no flow. |
| Fields | `## Fields` | One row per field of the feature's form: `Field`, `Required`, `Rule`, `Message when refused`. |
| Rules | `## Business rules` | One numbered rule per row: `ID`, `Rule`. Who may do it, when an action is available, limits, defaults, what is kept, sent or deleted, and when. |
| Clients | `## Where the apps differ` | Only when the product has several clients: one row per difference, `What` and a column per client (`Web`, `Mobile`). One sentence instead when they were compared and do not differ. |
| Parts | `## Parts` | Only on a feature that has parts: a link to each part and one line saying what it covers. |

The headings are written exactly so and come in this order; a section the feature does not have is left out. A field's rule is in `Fields` and is not repeated in `Business rules`. Usually 150-400 words and up to about twenty rules. A feature that needs more gets parts: notes with `parent` set to the feature note, each about one flow or one kind of use, never one kind of fact, and each written in this same shape. The feature note then holds what the feature is for, how the parts fit, the rules that hold in every part, and `## Parts`.

A rule is numbered `BR-<FEATURE>-<NN>` (`BR-INVITE-03`): `BR`, a short upper-case word for the feature that is the same in all rules of the note and used by no other note, and a number from 01. The number is the rule's name, quoted in tickets, tests and gaps. A rule keeps it when its text changes; a new rule takes the next free number; the number of a removed rule is not used again; rules are never renumbered. One rule per row, one or two sentences, with the value.

A **reference note** lists things the code registers in one place and that belong to no single feature (background jobs, emails and notifications, routes, roles and what each may do, plan limits, flags, the states of a record) as one Markdown table, one row per item, with the count and the place in the code the list comes from, which is also in `sources`. Columns name the facts a reader asks about; a cell holds a value from the code in a few words ("daily at 06:00 UTC", "retried 3 times"), two short sentences at most, and links the feature note when the item has one. Form fields and the actions on a screen are not reference notes: they are in the feature's note. Inside a table a wikilink's alias separator is written `\|`.

What a note does not carry:

- A line naming its area: `areas` has it and the viewer shows it.
- A "Verification" section, test commands or PASS/FAIL: what was run is recorded on the run page.
- Line numbers in links to code (`#L40`). Name the symbol (`createPeriod`, `INVITE_TTL_DAYS`) and link the file where that helps; a name still finds the place after the next edit.
- More `sources` than decide the behavior, usually one to five files. Each one marks the page for re-reading when it changes, so shared plumbing and files that only sit on the path make every page look outdated.

A feature note (illustrative):

```markdown
---
id: "team-invitations"
title: "Inviting a teammate"
type: "note"
status: "current"
areas: ["identity"]
sources: ["src/server/teams/invite.ts", "src/features/team/InviteForm.tsx"]
summary: "An owner or admin adds a person to the team by email. The person joins the first time they sign in with that address."
updated: "2026-11-16"
---

# Inviting a teammate

A team grows by invitation: an owner or admin enters an email on the Team page, and the person who signs in with that address becomes a member.

## How it works

The owner or admin types an email and presses **Send**. The person gets a link, signs in or creates an account with that address, and is on the team. Until then the invitation is listed as pending and can be sent again.

## Fields

| Field | Required | Rule | Message when refused |
| --- | --- | --- | --- |
| Email | yes | trimmed and lower-cased, at most 254 characters, a valid address | "Enter a valid email address" |
| Can manage the team | no | off by default, so the person joins as a member | |

## Business rules

| ID | Rule |
| --- | --- |
| BR-INVITE-01 | Only an owner or an admin sees **Invite**. Only an owner sees "Can manage the team". |
| BR-INVITE-02 | **Send** stays disabled until the email is valid. |
| BR-INVITE-03 | An address already on the team is refused with "This person is already on the team". |
| BR-INVITE-04 | A team on the Free plan has 3 members ([[notes/plan-limits\|plan limits]]). A fourth invitation is refused with "Your plan allows 3 members". |
| BR-INVITE-05 | An invitation expires after 7 days (`INVITE_TTL_DAYS`). Sending it again starts the 7 days over. |
| BR-INVITE-06 | An invitation is used up by the first sign-in with that address, which must have a verified email ([[notes/verified-email\|why]]). |
```

A reference note (illustrative): one table, every item, the count and where the list comes from:

```markdown
# Background jobs

All 4 jobs registered in [`worker/index.ts`](../../../src/worker/index.ts), the only place jobs are registered.

| Job | Starts | Does | Runs when | On failure |
| --- | --- | --- | --- | --- |
| `send-digest` | daily at 06:00 UTC | emails each member the day's open items ([[notes/daily-digest\|digest]]) | `DIGEST_ENABLED` is set | retried 3 times, 5 minutes apart |
| `purge-links` | hourly | deletes share links expired more than 30 days ago | always | next run picks them up |
| `finalize-upload` | an upload completes | checks size and type, moves the file to storage | always | the upload is marked failed |
| `rollover-period` | a person completes a period | opens the next period from the series plan | the series repeats | the period stays complete, the next one is not opened |
```

All sample paths and symbols are illustrative. Area pages list their notes with one line each and the reviewed, discovered and deferred scope; they describe no behavior themselves. The index links all areas. Scope is stated as what was read and what comes next, never as an invented completeness percentage. Runs record revision, dirty scope, bounds and outcomes.

The validator enforces these body rules:

1. An `area` or `note` page may not reference the gap layer in any form: a wikilink, an embed (`![[...]]`) or a Markdown link to a `gap` or `plan` page, or any link inside its `title` or `summary`. Link from the gap to the note instead. Links from gaps, plans and index pages to anything are fine.
2. A `run` page links to no vault page, by wikilink, embed or Markdown link. It names the pages it touched by path in code formatting (`notes/example`). A run touches many pages; as links they would make every run a hub and the area clusters would collapse into one ball in Obsidian's graph. Links to source files and URLs are fine, and the index may link to a run.
3. An `area` page holds no table and links whole notes only, never a heading or block inside one (`[[notes/x#Part]]`). Behavior is described in notes; a part that needs its own link is its own note. Tables and links to parts of a note are fine on other pages, and a table inside a code fence does not count.
4. A rule number (`BR-PROFILE-01` in the first cell of a table row on a note) appears once in the vault. The same number on two rows, on one page or two, is an error: a number names one rule for good.
5. A gap has six `##` sections with exactly these headings, each once: `Current behavior`, `Gap`, `Evidence`, `Recheck`, `Discussion`, `Decision`. Headings inside code fences do not count.
6. When `decision` is not `open`, `Decision` needs text; when `recheck` is not `not-checked`, `Recheck` needs text.

## Where the vault is

A vault is a folder of the repository that holds `00-index.md`. The person may put it anywhere; a new one goes to `project-spec/` at the root unless they name another folder. Nothing inside a page depends on that place except Markdown links from a page to a file of the repository, which are relative to the page. So a vault is moved with the helper, not by hand: `knowledge.py move --repo REPO --to FOLDER` moves the folder, repoints those links, writes `created` into each gap that lacks it (Git will show the page as new in its new place), removes the folder it left when nothing else is in it, and runs the checks. Page ids, wikilinks, `sources` and the reviewed fingerprints stay as they are. After a move, anything outside the vault that names the old folder is yours to update: a `--vault` in a script, the block in an agent instruction file.

## The inventory file

`.knowledge/inventory.md` is the checklist of a map: what the product has, and how far the spec has got with it. The agent writes it before the first page and keeps it true afterwards ([the rules](../SKILL.md#the-inventory-file)); no helper writes it, and like everything under `.knowledge/` it is not a page of the vault. The `summary` command and the viewer count its feature headings by state, so write each as `## Name: finished`, `in progress` or `not started`. It is committed with the vault, which is how a second session, or a second person, continues where the first one stopped.

```markdown
# Inventory

Taken at `4f2a9c1` on 2026-11-18. Apps and packages: web-app, mobile-app, packages/api, packages/jobs.

## Chats: in progress

Folders: web-app/src/features/messages, mobile-app/src/features/messages, packages/api/src/chat
Pages: notes/chats, notes/chats-group
Left: the support chat screens, the mobile app

- [x] web /messages
- [x] web /messages/[id]
- [ ] mobile ChatScreen
- [x] api chat.send
- [ ] job chat-digest

## Reviews: not started

Folders: web-app/src/features/reviews

- [ ] web /products/[id]/reviews
- [ ] api review.create

## Left out

- packages/storybook: a component gallery for developers, no behavior of the product
```

- A feature's heading is its name and one of three states: `not started`, `in progress`, `finished`. A feature with parts is still one heading; its parts are among its pages.
- One checkbox per entry point: the client or kind and the name the code registers it under. Use the product's own kinds; `web`, `mobile`, `admin`, `api`, `job`, `email`, `webhook` and `command` are common ones, not a fixed list. A box is ticked when the entry point was followed to the code that decides its behavior, not when it was seen.
- `Pages` names the feature's pages by path. `Left` says in words what is not read yet, and is the same thing the `partial` page says in its last line. A `finished` feature has every box ticked and no `Left` line.
- "Left out" holds what was looked at and is not part of the product, each with its reason.

## Helper

Four scripts in `$SKILL_DIR/scripts/`; see [SKILL.md](../SKILL.md) for the variables.

`coverage.py --repo PATH [--vault PATH] [--path FOLDER]... [--all]` reads the repository's code files and the spec pages (`area` and `note`) and prints what the code has that no page mentions. It writes nothing and always exits 0. Code files are the tracked and the untracked-but-not-ignored files with a source-code extension, outside the vault, without tests, fixtures, stories, mocks, migrations, dependencies and build output. For each folder it prints the number of files and lines, how many of the files a page cites in `sources`, how many **sentences a person can see** the folder has and how many are on no page, and the same for **named numbers**. A sentence is a string or text between tags of 12 to 200 characters that starts with a capital letter and has at least three words, outside log calls; it is on a page when a page contains it, ignoring case, curly quotes and spacing. A named number is an upper-case constant set to a number (`MAX_FILES = 10`); it is on a page when a page contains its name. A file with 40 or more sentences is an article or a template and counts as a file only. A folder in which no page cites any file is one line however deep it goes; folders are ordered by how much they have that no page mentions. With `--path` only those folders are read and every unmentioned sentence and number is listed with its file, then the largest files no page cites. The first 40 folders and 60 items are printed unless `--all` is given. The report finds places to read; it cannot find a rule that has neither a message nor a named number.

`knowledge.py {check,snapshot,summary,gaps,serve,build,move} --repo PATH [--vault PATH]`

- `summary`: read-only, a few lines for a person or an agent asking where the spec stands. The vault and its page counts; `map`, the features of the inventory file by state with the share finished; the pages that are `partial` or whose code changed; the gaps by state; the open gaps by topic, with how many are of high priority; and one line per review (`security`, `abuse`, `validation`, `data`, `api`, `ui`, `failures`, then any other a run page names): not run, or the day of its latest run page, how many features its checklist has ticked, the page, and the open gaps of its topic. Pages that fail `check` are left out and the last line says how many.
- `gaps`: read-only, one line per gap: state, priority, topic, file, title, the most urgent first, and a count. `--state open` (the default), `closed`, `all` or one state; `--topic` and `--priority` take a value or `none`; `--area` takes an area id.

- `check`: read-only, exit 1 for structural errors; freshness warnings normally leave exit status 0. Add `--strict` to also fail on warnings. Page-level errors are printed first, and a failing `check` or `snapshot` ends with a line giving the number of errors and the number of pages they are on. A page whose frontmatter fails validation still counts as a target for links, embeds, area membership, a plan's `gap` and `duplicate_of`, so one broken page yields its own errors only; fix it and nothing else needs touching. Only the "missing" error is hidden this way: an ambiguous link (two or more candidates), a link to a page of the wrong type (a spec page linking a gap, or an `areas` entry naming a page known to be another type) and a run page's link are still reported. `snapshot --notes X` refuses X while X's area references, links, `gap` or `duplicate_of` point at a page that failed validation. Missing source files are errors except on explicitly `stale` or `superseded` notes (warnings). Changed or unbaselined evidence warns. A source that differs from its baseline only by line endings (typically a Windows checkout) warns "line endings differ in source X"; do not snapshot on that checkout, because it would record the converted bytes. Nothing is rewritten.

  `--strict --ignore-dirty` is for a working tree shared with someone else's uncommitted work. Only the "changed source" and "line endings differ" warnings can be forgiven, and only when the drift is purely uncommitted: the file has uncommitted changes (modified or staged) and the accepted fingerprint equals the file's content at `HEAD` (or that content with LF/CRLF converted). If `HEAD` itself differs from what was accepted, the change was committed unreviewed and the warning counts, however many uncommitted edits sit on top. A forgiven warning is still printed, marked as not counted, and the summary says how many were forgiven. Never forgiven: a source with no baseline (unbaselined; nothing was accepted, so there is no uncommitted-only drift) and an untracked file or one new since `HEAD` (no committed content to compare with, even if a baseline exists). A Git-ignored file never counts as uncommitted. Without the flag nothing changes. Structural errors, missing files and committed drift stay visible and fatal. The flag is valid only with `check`. It is not for CI: a CI checkout has no uncommitted work, and using it there would only let real drift through. Outside a Git work tree the flag is an error. There is no acknowledgement file, so when the other contributor commits, the warning counts again.
- `snapshot --notes ID...` or `--all`: explicitly accept raw-byte SHA-256 fingerprints of selected pages' sources into `.knowledge/sources.json`; preserve other baselines. `--notes` is blocked only by errors on the selected pages themselves (frontmatter, body rules, resolvable links, acceptable sources), by an unknown or duplicated selected id, and by errors that belong to no page, such as a damaged `sources.json`. It reports how many errors on other pages it is not blocked by, which lets you accept a fixed page while others are still being repaired. `--all` needs a fully valid vault.

Rules the validator applies beyond the basics: `decided_by: "agent"` is rejected in every decision state; `decided_by` and `decided_on` are validated but optional on `done` and `duplicate`; a missing source file cited by a gap is an error while its decision is `open`, `accepted` or `deferred` and a warning once it is `done`, `rejected` or `duplicate`, and a plan follows its gap (a warning when the gap is `done`).

`maintain.py {scan,receipt,finish}` supports [sync](sync.md); `merge.py inspect` supports [merge](merge.md).

## Data contract for the HTML view

```json
{
  "title": "Project knowledge", "generatedAt": "ISO-8601",
  "nodes": [{
    "id": "collection-periods", "title": "A rule", "type": "note",
    "status": "current", "areas": ["collections"], "tags": ["knowledge"],
    "path": "notes/collection-periods.md", "body": "Markdown without frontmatter",
    "sources": ["src/service.ts"], "summary": "", "updated": "2026-11-14", "stale": false,
    "kind": "", "recheck": "", "recheckedBy": "", "recheckedOn": "",
    "decision": "", "decidedBy": "", "decidedOn": "", "state": "",
    "gap": "", "layer": "spec", "recheckOutdated": false, "priority": "", "confidence": "", "duplicateOf": "", "added": "",
    "topic": "", "access": [], "review": ""
  }],
  "edges": [{"source": "collections", "target": "collection-periods"}],
  "map": {"finished": 12, "inProgress": 1, "notStarted": 3},
  "warnings": []
}
```

The added fields are empty strings when they do not apply. `recheckOutdated` is true when `recheck` is `outdated` or the automatic marker applies. `priority`, `confidence`, `topic` and `duplicateOf` are gap properties, empty when absent. `access` is a note's list of roles, empty when absent. `review` is a run page's topic, empty when absent. `map` counts the features of the inventory file by state, and is `null` when the vault has none. `added` is the day a gap appeared: its `created` property, else the day its page was first committed, else empty (a page not committed yet, or no Git history); it is empty for every other page. `layer` is `spec` for areas and notes, `gap` for gaps and plans, `nav` for index and run pages. For a gap node `status` is `""` and `gap` stays empty; for a plan node `gap` holds the gap id. The viewer treats missing fields as empty, so older data still opens.

Extract prose wikilinks, excluding inline and fenced code examples. Resolve full vault paths and unique basenames; reject missing or ambiguous notes. Strip aliases and heading or block fragments when checking file existence; headings are not validated. Area membership also adds navigation edges. Label the result as a knowledge and coverage map, not a runtime dependency graph.

Canonical Markdown must not contain raw merge conflicts. Validation rejects complete Git groups with a labeled opening marker, matching marker widths (including configured widths), and an optional diff3 base section, even inside code fences. Unlabeled or custom conflict formats are outside this detector; also inspect unresolved Git index entries. A `conflict` gap that records attributed claims and a next check is valid; it does not resolve them. See [concurrent merges](merge.md).

`serve` shows the vault in a browser: `knowledge.py serve --repo REPO [--vault VAULT] [--port N] [--open]`. Without `--vault`, this and every other command use the repository's single vault: the one folder that holds `00-index.md`, looked for up to three folders deep and not inside hidden folders, dependencies or build output. They stop with a message when there is none or several. It listens on `127.0.0.1` only (port 8757, or a free one when that is taken), answers only `/` and only when addressed as this machine, never writes, and builds the page again from disk on every request, so a reload shows the current files. When the vault has errors the page lists them. The page data is the graph above plus `live: true`, `vaultPath` (the vault's path relative to the repository), `history`, `pending` and `files`. `history` is the last 30 commits that touched vault pages (not `.knowledge/`), newest first, each `{"sha", "date", "subject", "pages", "more"}`; a page entry is `{"path", "status"}` with `status` `added`, `changed` or `removed`, plus `was` and `now` when the commit changed the page's `summary` (or, failing that, its `title`); at most 80 pages are listed per commit and `more` counts the rest. `pending` lists vault pages with uncommitted changes in the same `{"path", "status"}` shape. Both are empty outside a Git work tree. `files` is the text of the repository files that pages cite in `sources` or link to, keyed by repository-relative path, each `{"text", "truncated"}`. A file is included only when it is inside the repository and outside the vault, is not a credential path, and is UTF-8 text; one file is cut at 300,000 characters and all files together at 4,000,000, after which the rest stay ordinary links. The viewer opens a link to an included file in place: Markdown rendered, anything else as numbered lines, with the lines of a `#L10` or `#L10-L20` fragment marked.

`build` writes the same viewer as one file, for a server that shows the spec to people who do not have the repository: `knowledge.py build --repo REPO [--vault VAULT] --out FILE [--source-url URL] [--with-sources]`. `--out` must be a file outside the vault. The command stops with the `check` errors when the vault has any, and writes nothing then; freshness warnings do not stop it. The page data is the graph plus `built: true`, `commit` (the full `HEAD`, empty outside Git), `sourceUrl`, `vaultPath`, `history`, `pending` and `files`. `files` is empty unless `--with-sources` is given, because the text of cited files is source code. `--source-url` must be an `http(s)` address; `{commit}` in it is replaced by `HEAD`, and it is an error to name `{commit}` outside a Git work tree. `--allow-missing-sources` is for a build that sees only part of the repository (a Docker build context): a cited path where nothing exists is not an error and does not mark its page as changed, and the command lists those files; `check` and `snapshot` never accept it. On a built page a cited file whose text is not included is a link to `sourceUrl/<repository path>` (with `#L10-L20` when lines are named) in a new tab, or plain text when there is no `sourceUrl`; it is never a relative link, which would lead into the site that hosts the page. In a shallow clone the commit whose parents were not fetched is left out of `history` (by `serve` too), since Git would show every page as added there, and `build` says that the history is short.

`serve` and `build` need the viewer page, which is not part of the skill folder. They look for `assets/viewer.html` in this copy of the skill (`project-spec install --with-viewer` puts it there), then for `viewer/viewer.html` in the package or clone the skill sits in, and stop with a message naming `npx project-spec serve` when there is neither; every other command works without it. `--viewer FILE` shows the vault with a page of your own instead: any HTML file with the placeholder once, which receives the data described above.

The viewer page has exactly one `__KNOWLEDGE_DATA__` placeholder for script-safe JSON. Treat contents as untrusted text: no raw Markdown HTML execution, unsafe URL schemes, external scripts, fonts, analytics or fetches. Render readable basic Markdown, pipe tables and wikilinks; leave unsupported syntax as text. The viewer has a tree of areas with their notes (a note is listed under its first area; superseded notes are not listed), a search over pages, gaps and the cited files, and five places: the overview, a page, the gap queue, the map and recent changes. A note shows its title, `summary`, the page text and the gaps about it that are not closed, then its source files folded; an area shows its notes with their summaries and folds its own text. The pages linked to or from the page are a short list beside it. Navigation keeps a trail for Back and Forward and writes the place into the address (`#/page/notes/example`, `#/gaps`), so a reload or a copied link returns to it. The map draws one frame per primary area (the area page, or the first entry of `areas`) with its pages inside; an edge between a page and its primary area is not drawn because the frame says it, links inside one area are solid and links across areas dashed; `nav` pages are not drawn. Recent changes reads `history`, `pending` and the "changed source" lines of `warnings`. "Copy for AI" only composes text from the page, a choice of what the agent should do and the reader's own words, and copies it to the clipboard. The reader's name, the recently viewed pages and the last commit seen are kept in the browser's `localStorage`, and the viewer works without it.

## Format references

- [Internal links](https://help.obsidian.md/links)
- [Properties](https://help.obsidian.md/properties)
- [Graph view](https://help.obsidian.md/plugins/graph)

The bundle is self-contained. [Official Obsidian Skills](https://github.com/obsidianmd/obsidian-skills) can help with advanced format requests but are optional.
