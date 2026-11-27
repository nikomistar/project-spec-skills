# Release validation

> The entries below record what was checked at the time, in the terms of that time. Since then the five skills were merged into two (`spec-audit` and `spec-investigation` into `project-knowledge`, `spec-plan` into `spec-change`), the generated `AS-BUILT.md`, `GAPS.md` and `graph.html` were replaced by the viewer, and the `build` command was removed. None of that has been evaluated with a fresh agent yet. `spec-change` was never run on a real change and was removed in 0.11.0.

## 2026-11-27: which features a review reads first

- Seen in real use: on a product with 94 features the flows review had read 16 of them, and the other eight reviews none. Nine lists over 94 features are 846 visits, each a "continue" its owner has to press. The owner asked whether a review can begin with the features that matter and leave a profile page for later.
- 0.19.0:
  - Each feature gets a `Priority` in the inventory file, by rule from eight signals read from the code (`money`, `accounts`, `others-data`, `destructive`; `public`, `files`, `outbound`, `central`), with the signals as the reason. A level a person sets stays.
  - A review is asked for by topic or by feature, reads the high-priority features first and stops at the end of a level. Its run page is its ledger: every feature under its level, and a `Read` line for each one it reviewed.
  - `next` prints the requests that start a review, continue it, go on with the next level, or read one high-priority feature whole. `summary` and the viewer count the features by priority and each review's progress by level.
  - The viewer's file path on a page is a button that copies the full path (`serve`) or the path in the repository (a built page).
- Forward tests, each a fresh agent session (Claude Opus) with the request and the skill only, in a throwaway clone of a public repository: a command-line toolkit for one user, 151 features in its inventory, 20 in scope. Its spec had been through nine separate reviews of those 20 features; what they wrote (27 gaps, the run pages, the counts on the index) was removed from the copy first.
  - **FAIL, and not shipped:** every review over the 20 features in one pass, each feature opened once and asked every list. 17 minutes. It wrote 11 gaps. Of the 27 from the separate passes it wrote 5 again and noted about 5 more as small things (matched by keyword, not read one by one). The abuse, failures and UI lists wrote no gap where the separate passes had written 10. The agent said it read all the code before writing and did not ask every question of the low features. The request told it to finish all 20, which itself pushes toward haste. The guide now refuses this pass.
  - **PASS:** rank. 3 minutes: 2 high, 10 medium, 8 low. The two commands that delete a folder the person names came out high. Code was opened only for the 8 features that have no page. No review was started, and the requests of `next` were passed on as printed. An earlier run with a wider wording of `destructive` also put a command that overwrites its own output file in the high level; the wording was narrowed.
  - **PASS:** every review on one high feature, asked with the request `next` printed. 8.5 minutes: 3 gaps (1 high, 2 medium) and 11 noted lines. The four findings the separate passes had for this feature were all met, one as a gap and three as noted lines. The two gaps that are new were read against the code afterwards and hold. Each of the nine run pages has the checklist by level and the `Read` line, the groups were written one before the next, and `next` then offered to continue each review and no longer listed the feature.
- **NOT RUN:**
  - A review by topic over one level with the stop at its end, and going on with the next level in the same run page.
  - The wording changed after these tests: the signals for a tool with one user, where the rules of a feature without a page go, which list writes a finding that two lists ask about.
  - A product with accounts and payments. The test product has neither, so `money`, `accounts` and `others-data` were never given, and whether the levels sort such a product usefully is not known.
  - The product with 94 features has not been ranked or reviewed with this version.
  - One feature is one sample. The 27 earlier gaps were not themselves checked, so "not written again" does not always mean "missed".
  - The viewer's path button and the counts by priority were tried in a browser on one spec, not on a narrow screen.

## 2026-11-26: the long queue, thinned

- Run by an agent with 0.18.0 on the product of the entry below, at its owner's request, as the three steps of "A queue too long to read". Step 1 closed 1 twin and 174 single gaps as duplicates of 30 new pattern gaps. Step 2 recorded the owner's one sentence ("I defer every low-priority gap of kind product-plan") on 222 gaps. Step 3 rechecked 17 high and 185 medium gaps. 772 gaps that waited became 404: 17 high, 185 medium, 187 low and 15 with no priority.
- Read afterwards from the files: the counts match, the pattern gaps have a table of their places, and a sample of the rechecks names the files and lines that were read and says what was not run.
- The recheck closed nothing: all 202 were confirmed. The code had not changed since the gaps were written, and a recheck asks only whether the page still describes the code. On a fresh queue it moves gaps to "needs decision" and removes none, so 202 decisions still wait for one person.
- `summary` printed "627 open" after the run, with the 223 deferred gaps among them, and "low 409" with 222 of those deferred. 0.18.1: a deferred gap is not open. `summary` counts it apart, `gaps` leaves it out unless asked with `--state deferred`, and the viewer's Open tab and the counts beside each review leave it out; it stays under its own tab. Helper and viewer tests cover it; `python3 scripts/verify.py` passed.
- **NOT RUN:** nobody has decided any of the 202 gaps. Whether 185 medium gaps are a queue a person reads, or whether `medium` needs an order of its own (by pattern, by area), is not known. The 30 pattern gaps were not read one by one for whether their places really share one decision.

## 2026-11-26: a queue nobody can read

- Seen in real use: on a product with 82 features, the map and nine reviews left 772 open gaps, about 230,000 words: 18 high, 225 medium, 513 low and 16 with no priority. 386 of them are proposals (`product-plan`), and 55 had been rechecked. The owner said nobody will read it. One low proposal about a blog editor had a paragraph added by each of four reviews.
- Why: a review asks its questions of every entry point and wrote a page for every "no", whatever its weight. The guide asked for one gap per feature for the same doubt, so one pattern was written many times ("characters PostgreSQL text cannot store" at least four times, "an unused API remains registered" eleven). And the queue listed everything.
- 0.18.0:
  - A review writes a gap for what its list rates `high` or `medium`, and one line under "Noted" on the run page for what it rates `low`. A person can still ask for everything as gaps.
  - The same doubt in three features or more is one gap with a table of the places.
  - The gap guide says how to thin a queue that is already too long: twins and patterns first, then one decision of a person for a whole class, then a recheck from the top.
  - `summary` prints the open gaps by priority, and the viewer folds the low-priority gaps of the open queue until someone asks for them.
  - The requests in the README, the docs and the viewer no longer say "each doubt as its own gap".
- Checked: helper and viewer tests for the line of `summary` and the folded gaps; `summary` on that vault printed "high 18, medium 225, low 513, none 16". `python3 scripts/verify.py` passed.
- **NOT RUN:** no review has been run with the new bar. It is not known how many gaps it leaves, whether an agent then rates things `medium` to keep them or `low` to be rid of them, or whether anyone reads "Noted". The queue of that product was not thinned. The folded queue was not opened on that vault in a browser. The map still writes every doubt it meets as a gap, about 150 on each of the first two products.

## 2026-11-24: nine reviews on a small desktop app

- The first run of `logic` and `flows`, and the first time all nine reviews were run on one product: a macOS screen recorder with a static website and one small server function, 54 files. One agent (Claude Opus 5.5) mapped it and then ran each review as a pass of its own, with 0.16.0 read from this repository. The time was not recorded.
- The map: 12 of 12 features, 113 rules, 12 gaps. The nine reviews added 21 rules and 37 gaps: flows 13, logic 9, data 4, UI 4, failure paths 3, abuse 2, security 1, validation 1, API 0. That is 49 open gaps, 18 medium and 31 low, none high. `check` passed. The agent said about five of the flows and logic gaps were doubts it had noticed while mapping and held back, so the share of those two reviews is overstated. 26 times a review met a doubt that was already in the queue and added a line to that gap.
- Three gaps were read against the code by a second agent and hold. An update that finishes installing quits the app without looking whether a recording is running, and the new copy empties the temporary folder when it starts. A second running copy empties the same folder under the first. The website says the app never connects to the internet, and the app asks GitHub for updates. The first two lie between two features and were written by the flows review. The other 46 gaps were not rechecked.
- What the run showed, and what 0.17.0 changes:
  - `summary` printed "22 open gaps with topic logic" beside both `logic` and `flows`, and nothing said which review wrote which gap. A gap now names the review that wrote it (`review`); `summary` counts by it, `gaps --review` lists by it, and the viewer's queue has a "Found by" filter.
  - The lists speak of accounts, roles, forms, a server and a database, and the agent had to translate them for a desktop app: what mattered was a permission of the system, the app started from its disk image, a system dialog, a second running copy. The guide has a section that says how to ask the same questions of such a product.
  - Logic called lost work `high` and flows did not name it, so a lost recording got `medium`. Flows now names it too.
  - Abuse and failure paths both asked about limits, and an abuse gap on an app with one user got the topic `security`. The guide says which review asks what, and that such a gap gets `ops`.
  - The UI list required a gap for a control built twice that looks and behaves the same. It is now named on the run page and is not a gap.
  - A question the product has nothing for is named on the run page in every review, not only in abuse. A design document in the repository is not reviewed; that is an audit.
- `python3 scripts/verify.py` passed, with helper and viewer tests for the new property, the line of `summary`, `gaps --review` and the "Found by" filter.
- **NOT RUN:** none of these changes has been run by an agent. It was one product, small, and not a web application, so `logic` and `flows` have still not been run on the kind of product their lists were written for. No person has decided any of the 49 gaps, so how many are worth having is not known. Whether a review still wrote a twin of a gap that was already there was not checked.

## 2026-11-24: the rules themselves, and what lies between features

- Asked by the project's owner, not seen in a run: which of the things that matter to a person using the product no review looks at. Security, abuse and validation ask whether a rule is enforced; data, failure paths, API and UI ask about records, failures, calls and screens. `logic` was a topic for gaps with no list of questions, so a review of it went through "Another topic" with questions the agent made up on the day. And every review read one feature and stopped where it ends, so nothing asked what one feature leaves for the next.
- 0.16.0: a review named `logic` with seven questions (rules that disagree, a case nobody decided, at the edge, acting on oneself, one rule in two places, rules about time, what changed afterwards), and a review named `flows` with seven (what it needs first, what it hands on, the ways out, left in the middle, going back, waiting, in another order). The gaps of both have the topic `logic`. Both go one feature at a time like every review; `flows` starts at a feature's edges and reads the feature on the other side, so its run page keeps the checklist of features. `summary` and the viewer list both among the reviews; helper and viewer tests cover the lines and the rows. `python3 scripts/verify.py` passed.
- Where the questions come from: they were written for this release from common faults of products built fast, and were not compared with published lists the way the abuse questions were.
- **NOT RUN:** no agent has run a logic or a flows review on any product. It is not observed what they find, how many of the gaps are real, or how long they take. Two things may make them long: the first logic question compares a feature's rules with every page that names the same record, and a flows review reads the code of the neighbouring features too. Whether an agent can tell "nobody decided this case" from "it was meant" is not known; the guide sends such a doubt to a `knowledge-gap`. `summary` and the viewer show the same count of open logic gaps beside both `logic` and `flows`, as they do for `security` and `abuse`.

## 2026-11-24: one wrong page hid the whole spec

- Seen in real use: a spec built for a server had one rule number used twice on one page. `build` printed the error and wrote nothing, and `serve` answers the same vault with only the list of errors, so nobody could read any page until that one was fixed. The person called it a crash.
- 0.15.1: `serve` and `build` show every page that could be read, and the viewer says what `check` reports: a notice on the first page, the count beside Recent changes, and there every error grouped by its page with a request for an agent. Of two pages with one id the viewer shows the first. `build` exits 0 and prints how many errors the page lists; `check` still exits 1. A vault with no page that can be read is refused as before.
- The properties of a page used to be checked until the first problem, so a page with four things wrong took four runs. Now every problem is one line of the same run. A page with one problem prints what it printed before.
- Checked: helper tests for a built and a served vault with a wrong link, a page that cannot be read and two pages with one id; for seven problems on one page and six on one gap; a viewer test for the notice, the list and the copied request. Opened in a browser on the fictional example with a rule numbered twice and a page with four wrong properties: the spec opened, the notice said 5 errors, and Recent changes listed them under their two pages. `python3 scripts/verify.py` passed.
- **NOT RUN:** not tried on the vault where it was seen, in its container. A built page was not opened on a server. Whether people notice the notice, or read "5 errors" beside Recent changes as five changes, is not observed. Errors that are not about one page's properties (a missing link, a number used twice) were already reported together and were not changed.

## 2026-11-24: what a security review did not ask

- Seen in real use: a person reading one product's upload code found four weaknesses that the security review of the same product had not written down. A signed upload link fixed the place of the file and neither its type nor its size, and the file was then served to anyone from the product's own domain as whatever type the uploader named; one endpoint read a whole original file into the server's memory with no maximum; the type the uploader declared chose the decoder and the paid conversion; and nothing limited how many upload links one account could ask for. All four were found by reading the code, and the last was also seen in the product's data, so a pass that only reads could have found them.
- Why the review missed them: its questions were asked of one entry point at a time, and these lie between the request, the storage, the job and the address the file is served from. Its one question on files asked for type and size "on the server", and nothing asked what a request costs, what is paid for, or what one account may do how often. Settings of storage that the repository holds were left to tools.
- Compared with other published review instructions and lists before writing: two of them leave denial of service, rate limits and memory use out on purpose, one does not report what is behind a sign-in. The questions were taken from the OWASP API Security Top 10 2023 (unrestricted resource consumption, sensitive business flows), the OWASP file upload cheat sheet and ASVS 5.0, in this skill's own words.
- 0.15.0: a review named `abuse` with nine questions, asked of everything a caller can send (a text, a body, a list, an imported table, a file) and followed to where it ends up; a question the product has nothing for is skipped and the run page says so. Its gaps have the topic `security`. The `security` review keeps to who may do what, and has three more questions: another way to the same action, steps that can be skipped, and what a browser calls with a cookie. `summary` and the viewer list `abuse` among the reviews; helper and viewer tests cover the line and the row. `python3 scripts/verify.py` passed.
- **NOT RUN:** no agent has run an abuse review, on that product or any other. It is not observed that the new questions find the four weaknesses, how many of the gaps such a pass writes are real, or how long it takes. The three new security questions have not been run either. `summary` and the viewer show the same count of open security gaps beside both `security` and `abuse`, because the two reviews share the topic; whether people read that as double counting is not known.

## 2026-11-23: an agent that cannot answer npx

- Seen in real use: an agent following the block in a project's instruction file ran `npx project-spec check`, and `npx` stopped to ask whether it may download the package. The agent could not answer and ran the helper script of a local copy of the skill.
- 0.14.2: the block's two commands are `npx --yes project-spec ...`, with an automated test that the printed block has no command without it. The commands the README gives to a person are unchanged; a person can answer the question.
- The GitHub account that holds the repository was renamed. 0.14.1 on npm still names the old address for the repository, the homepage and the issues; 0.14.2 carries the new one. Nothing depended on the old address to work: `npx` takes the package from npm by name.
- `python3 scripts/verify.py` passed.
- **NOT RUN:** no agent has run the new block in a project that does not have the package, so it is not observed that `--yes` is enough there, for example where the agent's sandbox has no network.

## 2026-11-20: a change request that does not make the agent wait

- Seen in real use of 0.14.0: the viewer's "Change the behavior" request opened with "Ask your questions first, then change the code". The person had written the whole change ("add limit same as on mobile"), and the agent still stopped and changed nothing until told again.
- 0.14.1: the request is the opening line, then "Make this change:" with the person's words, then the step that records the change in the spec. Asked from a gap page, it also asks to close the gap as done once the change answers it. Viewer tests cover the text on a gap and on a feature page. `python3 scripts/verify.py` passed.
- **NOT RUN:** no agent has been given the new request, so it is not observed that it now acts at once, or that it still asks when the words are unclear.

## 2026-11-20: the first reviews, three more lists, and where the spec stands

- The first two security reviews were run by agents on real products with 0.13.0. One covered 90 features and 1,096 entry points and wrote 29 gaps (6 high, 10 medium, 13 low); the product's owner read the six high ones and said they look right, two of them matching what they know of the code. The other covered 82 features and left 141 open gaps with the topic. Neither count has been rechecked gap by gap, so how many are real is still not known, and the time and cost of the passes were not recorded.
- What those runs showed and this change answers: the run page of one review linked to every feature, which `check` refuses for a run page, and one gap cited a file named `secrets.ts` as a source, which `check` refuses as a credential file. The review guide now says to write feature names as plain text and to name such a file in `Evidence`.
- 0.14.0. Three more lists of questions: validation (the form, the server and the database on the same field, 10 questions), data (10) and failure paths (9). `validation` is a seventh topic for gaps.
- A run page says which review it is (`review`, or its name `<date>-review-<topic>.md`). From that, the inventory file and the gaps, `summary` prints where the spec stands and `gaps` lists gaps by state, topic, priority and area; the skill has a `status` mode that relays them. The viewer's first page shows the same: the map with the share of features finished and one line per review. Tried on the example and on a real vault with 287 gaps, 3 of them failing `check`: the report still answered and said that three pages were left out.
- The gap queue finds gaps by the words in them. On a real vault of 189 gaps, typing two words in headless Chrome left one gap, kept the focus in the field and updated the counts on the tabs.
- `python3 scripts/verify.py` passed.
- **NOT RUN:** no agent has run a validation, data or failure review, or been asked for the status. The `summary` report on a vault whose inventory headings are written differently from the format ("## Name: finished") counts nothing for the map; that was seen on no real vault but is possible.

## 2026-11-20: a topic on every gap, who may use a feature, and a review of one topic

- 0.13.0. A gap has an optional `topic` from a closed list (`security`, `data`, `logic`, `ui`, `api`, `ops`); `check` refuses any other value, and a gap without one still passes. The queue has a Topic filter when at least one gap has a topic, and the topic leads the line under a gap's title. A feature page may state who may use it (`access`, a list of roles); the viewer shows it under the title. Helper and viewer tests cover both, and the queue and a page were opened in headless Chrome on the example.
- `project-knowledge` has a `review <topic>` mode with a guide of fixed questions for security, the API and the UI, a run page to continue from, and the rule that what the code answers becomes a rule on the page and each doubt a gap. The viewer's Copy for AI offers it on a feature or an area. The README describes three kinds of run: the first map, the small update after a change, and a review of one topic.
- `python3 scripts/verify.py` passed (124 helper tests, the viewer tests, the command tests).
- **NOT RUN:** no agent has run a review. It is not observed how long one takes, how many of its gaps are real, whether it asks every question of every entry point, or whether it keeps to reading. The time stated in the README for the first map (one to a few hours) is one user's experience on two products, not a measurement. No existing vault has had topics added to its gaps.

## 2026-11-19: the spec in a folder of your choice

- A new vault went to `knowledge/<project>/` whatever the person wanted, which gives `ProjectA/knowledge/ProjectA`, and the helpers looked only under `knowledge/`: a real vault kept in `project-spec/` needed `--vault` on every command.
- 0.12.0: the person names the folder and the default is `project-spec/`. The helpers and the command find the one folder with `00-index.md` up to three folders deep, outside hidden folders, dependencies and build output. Tried on three repositories: a vault in `project-spec/` and one in `knowledge/<project>/` were found without `--vault` (14 and 35 ms), and this repository, whose only vault belongs to an example four folders deep, reported none.
- `move --to` moves a vault and repoints the links from its pages to repository files. On a copy of the example it moved the vault to `project-spec/` and then to `docs/product/spec/`, repointing 33 links on 10 pages each time, and `check --strict` passed after each. Automated tests cover links with fragments, spaces and percent-encoding, links in code (left alone), links inside the vault (left alone), a gap's date carried into `created`, and the refusals.
- The sync helper finds the vault the same way and no longer queues a copy of the skill kept in `.claude/skills`, `.codex/skills` or `.agents/skills` as a change of the application.
- `python3 scripts/verify.py` passed.
- **NOT RUN:** `move` on a large real vault, on Windows paths, and with pages that link to repository files by reference definitions in unusual forms. No agent has yet created a vault under the new default.

## 2026-11-19: one skill, a small update after a change, and the queue by date

- `spec-change` is removed: the product has no way to edit a spec and have it built, and the skill was never run on a real change. Its planning guide moved into `project-knowledge` (`plan <gap>`). `update` removes old copies of the skill and keeps their files in the backup folder; this has an automated test.
- `project-knowledge` has a mode for the agent that just changed code, "Record a change": only the rules the diff changed, no filling in, no run page, no checkpoint. `project-spec instructions` prints a block of 16 lines that asks any agent for the same, or writes it into `AGENTS.md`, `CLAUDE.md` and the like; writing, replacing and removing the block have automated tests.
- A gap has a day it appeared: its `created` property, else the day its page was first committed. The queue shows it and can list the newest first; its states are tabs and the filters have a row of their own. Helper and viewer tests cover this, and the queue was opened in headless Chrome on two real vaults (184 and 159 gaps) and on the example.
- Re-check of the skill text against the helpers and the example found and fixed: two sentences that disagreed about when a feature gets parts; "usually one to five" sources, which an agent had read as a limit of five on every page; `coverage` counting Python docstrings as sentences a person sees; and an example that had no inventory file, no closed gap and a refusal message on no page. The example now passes its own `coverage --path src`. The six screenshots in the README and the docs were retaken.
- The Copy for AI dialog keeps one size: the requests are a list on the left, the fields for the chosen one are in the middle and the copied text is on the right. Measured in headless Chrome at 1360 by 860, the card had the same position and size (1080 by 640) for three different requests; before, its height followed the text and the centred card moved with every choice.
- Seen in a real pass after 0.11.0: an agent ran the application's tests for each feature it reviewed ("reviewed, with 56 tests passing"). The skill never asked for that, but it never ruled it out, and its "PASS, FAIL or NOT RUN" wording invited it. 0.11.1 says it plainly: read the tests, do not run them, except on request or to settle one question in an investigation.
- `python3 scripts/verify.py` passed.
- **NOT RUN:** no agent has recorded a change under the new mode or under the block, so it is not observed that the edit stays small, or what it costs. Whether each named agent really reads the file the docs name for it was not checked in those agents. The claim that a later sync is cheap for recorded changes rests on the instruction in `sync.md`, not on a run.

## 2026-11-18: a skill copy without the viewer and the tests

- A copy of `project-knowledge` was 9,179 lines, of which 3,879 were the viewer page and 2,432 the helper tests. 0.10.0 moves the page to `viewer/` in the package and the tests to `tests/` in the repository; a copy is now the instructions and four helpers.
- `serve` and `build` find the page in the package or clone, or in a copy made with `install --with-viewer`, and otherwise stop with a message naming `npx project-spec serve`. `update` keeps the page in a copy that has it, so copies made by earlier versions keep working, and removes the old test files. `--viewer FILE` shows the vault with a page of one's own. All of this has automated tests, including a build run from an installed copy with and without the page. `python3 scripts/verify.py` passed.
- The package was packed, installed into an empty project and tried: `install --dir`, the files in the copy, `build` from the package, and `build` from the copy with and without `--with-viewer`.
- **NOT RUN:** the Claude Code plugin and third-party skill installers with the new layout, and a custom page with `--viewer` beyond the automated test.

## 2026-11-18: a long gap queue and closed gaps

- Seen on a real vault with 184 gaps: the queue was one list of 184 rows with the seven closed ones among them, and a feature's page showed no trace of a question that had been decided.
- 0.10.0: the queue shows open gaps only, forty at a time; closed gaps (done, rejected, duplicate) are under History, the most recently closed first, and on the feature's page in a fold. The viewer tests cover the counts, the portions, History and the fold. `python3 scripts/verify.py` passed, and the queue, History and a feature page were opened in headless Chrome on that vault.
- The rule that closing a gap puts its answer on the feature's page as a numbered rule, named in the gap's `Decision`, is an instruction only: nothing checks it, and no agent has closed a gap under it yet.

## 2026-11-18: a checklist for the first map

- 0.9.2 gives the inventory a file of its own, `.knowledge/inventory.md`, with a state per feature and a checkbox per entry point, and tells the agent to write it before the first page, to add what it finds on the way, to compare it with the code at the end and to continue from it when a session was interrupted. Before, the inventory was a list on the run page with no format and nothing said about continuing.
- This is a change to the instructions only. No helper reads the file, so nothing checks that it is true. `python3 scripts/verify.py` passed.
- **NOT RUN:** no agent has yet made a map with it, so it is not observed that an agent keeps the file current, or that a second session continues from it instead of starting again.

## 2026-11-18: depth of a first map

Observed on a second real project, a monorepo with a web app and a mobile app (about 5,400 code files, 600,000 lines without migrations):

- A first map made with 0.7.0 in one session produced 71 notes. The chat feature has 160 code files and 25,000 lines across the two apps and 25 server procedures; its single page had 13 rules and cited 5 files. The page said both apps "offer the same actions", from a comparison of which server procedures each app calls. The reader called the spec full of holes.
- The instructions then told the agent to follow representative paths and to finish a broad map before deepening, and gave no way to tell a finished feature from a sampled one. 0.9.0 replaces that with an inventory, one feature finished before the next, parts for a feature too big for one page (`parent`), a section for where clients differ, and `coverage.py`.
- `coverage.py` was run on that project. For the chat folders it listed 98 sentences and numbers no page mentions, among them refusals the page lacks ("You cannot remove yourself", "Ask an Expert chats can't be renamed", "Only a group chat can be the Moderators chat") and whole folders no page cites (49 files of the chat window, 39 files of the mobile chat). Whole-repository run: about 8 seconds.
- `parent`, the order and filter of the gap queue by priority, and `coverage.py` have automated tests; `python3 scripts/verify.py` passed.
- **NOT RUN:** no agent has yet made or deepened a map with the new instructions, so whether they produce deeper pages is not observed. The size limits in them (about twenty rules a page, eight entry points, 2,000 lines) are a first guess. The report's idea of a sentence fits TypeScript, JSX and Python strings; it found none in that project's mobile screens, and other languages are untried.

## 2026-11-17: the viewer as one file for a server

- `build` has automated tests: the page is written without the text of cited files unless asked, `--out` inside the vault and a vault with errors are refused, `{commit}` in `--source-url` is filled in, and a shallow clone's first commit is left out of the history. The viewer tests cover links to the code host and file names without one. `python3 scripts/verify.py` passed.
- The page was built for the example and for a real vault of 237 pages (about 1 MB without source text, 4.8 MB with the text of 488 files), served by a plain local HTTP server and opened in headless Chrome: a feature page, the links to the code host and the Recent changes page were checked.
- `--allow-missing-sources` (0.8.1) has an automated test: a cited file that is not there stops the build without the option and is listed with it.
- A real Docker build of an application (Alpine, no Git, no `.git` folder) first failed with `No such file or directory: 'git'`. The helper now treats a missing Git as a folder without history; the same image build then wrote the page. This has an automated test.
- **NOT RUN:** the page behind a real application route, the Next.js example in the README, a build inside a CI job, and a browser other than Chrome.

## 2026-11-17: npm package and Claude Code plugin

- The package was packed with `npm pack`, the tarball installed into an empty project, and `project-spec version`, `install --dir`, `status` and `check` were run from it. The packed file list is checked by `scripts/test_cli.cjs` (no compiled Python files, nothing outside the command and the skills).
- `.claude-plugin/marketplace.json` and `plugin.json` passed `claude plugin validate` (Claude Code 2.1.197). Adding the marketplace and installing the plugin in Claude Code were **NOT RUN**.
- The `Publish to npm` workflow has not run yet: it first runs on the first version tag pushed after the package exists on the registry and a trusted publisher is configured there.

## 2026-11-17: one page per feature, numbered rules

Observed facts, with their limits:

- The rules of 0.5 were used on a real vault in another project. They asked for a separate table page per kind of thing in each area (forms, screen actions, permissions, routes, jobs). The result was 59 such table pages out of 146 notes, feature pages that did not say what the feature is for, an average of 12 cited files per note (88 at most), and one shared file cited by 24 notes, so that a single change marked dozens of pages for re-reading. A person reading it called the pages strange and never used the related links.
- 0.6.0 changes the instructions (one page per feature with fixed sections, numbered business rules, one to five cited files, no line numbers, reference pages only for lists no feature owns), the validator (a rule number appears once in the vault) and the viewer (the page text is always shown, related pages are listed beside it, rule numbers are marked).
- The validator rule and the viewer changes have automated tests, and `python3 scripts/verify.py` passed. The viewer was opened in a browser on that vault and on the example. The new `check` ran on that vault, by then 212 notes, with no errors.
- The page shape, the rule numbering and the regroup pass in the migration guide are instruction text. No fresh agent has been run with them yet, and that vault has not been regrouped. Whether an agent keeps rule numbers stable across later syncs has not been observed.

## 2026-11-15: first real use, and fixes since

Observed facts, with their limits:

- The spec/gap format was used for a real migration, and then for a first sync, of a 99-page vault in another project. The structural check of the migrated vault finished with no errors.
- `maintain.py finish` could not advance the checkpoint, because another contributor had uncommitted edits to files the range touched. The documented `deferred` disposition was not accepted by the helper at that time.
- That use exposed eight problems: `deferred` could not be used; strict `check` could not pass while someone else's work was uncommitted; a vault commit made during a pending range moved the scan target; `receipt` cleared dispositions without saying so; the recheck values read as "the defect was reproduced", which left proposal and research gaps without an honest route to `needs-decision`; one frontmatter error produced many misleading "missing wikilink" errors; `snapshot --notes` was blocked by unrelated errors; and nothing said how `done` and a recheck relate.
- The code fixes in this change have automated tests: partial finish (`deferred`, exit status 3), `check --strict --ignore-dirty`, the target and receipt messages and retargeting, the recheck labels printed in `GAPS.md`, link registration for pages with errors, and `snapshot --notes` on selected pages. The rule for closing a gap as `done` (an agent that sets `done` records a `not-reproduced` recheck), the single meaning of recheck for every gap kind, and the migration guide are instruction text only: no test checks that an agent follows them, and the helpers do not enforce the `done` rule. No fresh agent has yet been run with the changed instructions, and the migrated vault has not been re-synced with them.

This is one project, one vault and one contributor setup. It shows that the format could be applied and which things went wrong; it is not a measure of how reliably an agent will follow the changed instructions.

## 2026-11-15: spec/gap split, not yet revalidated

The vault format, validator, viewer and skill instructions changed to separate the as-built spec from a per-item gap layer (new `gap` properties, `plan` pages, generated `AS-BUILT.md` and `GAPS.md`, new `maintain.py receipt`, merge rules for gap pages). Every observation recorded below was made on the **previous** version. The agent smoke tests, the concurrent merge evaluation and the browser observations have **NOT been rerun** against the new format, and nothing below should be read as a result for it. The example vault's Markdown was migrated by hand and its generated artifacts are regenerated separately. Rerun `python3 scripts/verify.py` and the scenarios in [the evaluation guide](docs/evaluation.md) before relying on this release.

## Observations on the previous version

This file records observed checks for the toolkit and its concurrent-merge update. The fictional worked reports under `examples/parcel-desk/reports/` illustrate output shapes; they are not transcripts of these independent evaluations.

## Independent agent smoke tests

Fresh Codex agent contexts received one skill and only the raw fictional spec, source and tests, without the example reports or expected answers.

| Skill | Observed outcome |
| --- | --- |
| `spec-audit` | Found CAN-1's packed-owner mismatch, reproduced the adapter response, distinguished the missing regression test and left DEC-1 as an open decision. Covered the stated ownership and collected-state requirements. No application edits. |
| `spec-investigation` | Traced the service exception and adapter mapping, reproduced owner 409 versus other-customer 403 with unchanged state, and distinguished the local fixture from a real failed request. No application edits. |
| `spec-plan` | Proposed the shared service change with ordered tests, observable response/state criteria and unchanged ownership/collected rules. Kept partner behavior undecided. No implementation edits. |
| `project-knowledge` | Built a source-backed map in a separate Git fixture, preserving a preexisting human note byte for byte. After a new commit, discovered two changed source paths including a previously unmapped entrypoint, updated affected notes, retained all original IDs, and advanced the reviewed checkpoint using an exact-plan receipt. A no-change rerun left canonical notes, views, fingerprints and cursor byte-identical. |

Each of these three runs also executed the existing fixture suite: 3 tests passed. The suite intentionally lacks the packed success case. Passing it does not establish compliance with CAN-1.

The first knowledge sync produced 12 pages and 52 links. After the final evidence-guard correction, a further test-only commit was reviewed with the updated helper: the checkpoint advanced successfully, all previous IDs and the human note were preserved, and a fresh scan was clear. This final map had 13 pages and 62 links with zero validation warnings. Its four tests and focused probes passed. The fixture had no remote, so this demonstrates local integrated history review, not a live multi-contributor remote sync. The intentional partner decision remained open.

## Repeatable checks

`python3 scripts/verify.py` passed locally on macOS with Python 3.14, including an invocation from outside the repository directory:

- All four skill frontmatter entries and local Markdown links.
- 43 knowledge helper tests, including changed-source freshness, incremental review safeguards and concurrent-merge inspection. Regression cases reject local-only evidence, dirty excluded paths and changes hidden by Git index flags, without advancing fingerprints or the reviewed cursor; clean tracked evidence is accepted.
- 3 fictional application tests.
- Strict example vault validation: 11 notes, 59 links, zero warnings.
- The regenerated graph matches the shipped one, ignoring only generation time.
- Viewer JavaScript syntax, using the available Node executable, plus a focused DOM-stub check that bold text preserves nested wiki links, source links and code without interpreting raw HTML. The stub check does not independently test URL validation or replace browser observations.

The skill-authoring validator also passed for all four skill folders. The portable verification command requires no installed skill-authoring tools. Node is optional and its syntax check reports `NOT RUN` when unavailable.

## Concurrent merge validation

A fresh Codex agent used the merge workflow on updates created in two separate local clones sharing a local bare remote. It resolved five textual conflicts, retained both contributors' useful handoffs, reconciled duplicate IDs through a canonical note and a superseded pointer, and preserved both email-policy proposals as an explicit conflict. Source, spec and tests were unchanged; both contributor tips remained in the integration history.

The divergent reviewed-state proposals were replaced with the coherent common-base pair. After raw tracked-byte verification, only selected reviewed guard notes received accepted fingerprints. The shared cursor stayed at the common checkpoint. The final vault had 15 pages and 84 links with zero strict validation warnings; three existing fixture tests passed. The integration branch guard remained visible and shared `finish` was not run on that temporary branch. No remote push, browser or Obsidian GUI check was part of this merge evaluation. This verifies local two-clone reconciliation, not a hosted multi-user service or live simultaneous editing.

Independent review also reproduced and verified fixes for bytecode writes during inspection and conflict-marker false negatives. Tests cover ordinary and configured marker widths, a conflict containing a standalone `<` line, and valid fenced operator text. The inspector denies Git transports and rejects partial/promisor configuration before object inspection; its tests use simulated configuration, not a live promisor remote. Snapshot checks compare the repository and a copied skill folder before and after inspection to verify no file changes. Marker detection covers complete labeled Git groups; custom unlabeled conflict formats still require manual/index inspection.

## Browser observations

Chrome on macOS loaded the example through a loopback HTTP server. Observed: 11 materials; search for `packed` narrowed the list; the gap filter showed three items; side-list and graph-node selection opened readable notes; bold text rendered; an internal wikilink changed the selected note; and the planned item showed the `Product plan` badge. After the renderer correction, a bold internal link still navigated correctly and coverage sections displayed as readable prose.

The evidence link targeted the correct fictional `src/pickups.py` URL. Chrome blocked opening its content with `ERR_BLOCKED_BY_CLIENT`. A separate HTTP read returned 200 and bytes identical to that source file. Browser evidence-content viewing is therefore **BLOCKED**, not passed. The README describes the repository-relative path fallback for an editor.

Direct `file://` loading, a narrow viewport and this example's Obsidian GUI were **NOT RUN**. The generated HTML embeds its data and scripts and has no external resource dependency, but static inspection is not a direct-file browser test.

## Limits

These are bounded smoke tests, not a benchmark or a guarantee of complete project coverage. Codex agents executed the skills from their folders; an installation/restart round trip was not part of the evaluation. Other agent hosts and their installation mechanisms have not been integration-tested. No production system, authentication provider, database or real customer data is part of this fixture.

See [the evaluation guide](docs/evaluation.md) for repeatable prompts, isolation requirements and the evaluator's rubric.
