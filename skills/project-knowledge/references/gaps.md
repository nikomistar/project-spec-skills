# Writing gap and plan pages

This page is self-contained: it is enough to create, update or close a gap page, or to write a plan page, in a project-knowledge vault. Nothing else needs to be read first.

## Why gaps are separate from the spec

A vault has two layers. Spec pages (`areas/`, `notes/`) say what the code does today, nothing more. Gap pages (`gaps/`) hold every doubt, missing piece, contradiction or idea, one question per page. Plan pages (`plans/`) say how to build one accepted gap. The layers stay apart so a reader can trust the spec without wondering which sentences are proposals, and so a person can look at each gap on its own and decide it. An agent proposes; a person decides.

Gap and plan pages link to spec notes with wikilinks. Spec pages never link back to gaps or plans (the validator rejects it).

## Files and properties

A gap lives in `gaps/<slug>.md`; a plan in `plans/<gap-id>.md`. Frontmatter is one property per line with a JSON value (strings in double quotes, arrays on one line).

Every page: `id` (unique ASCII slug), `title`, `type`, `areas` (at least one existing area id), `sources` (repository-relative files read; may be empty for gaps and plans), `updated` (`YYYY-MM-DD`, last substantive edit).

A gap must not have `status`; its progress is carried by `recheck` and `decision`.

| Property | When | Values |
| --- | --- | --- |
| `type` | always | `"gap"` |
| `kind` | always | one of `product-gap` (accepted requirement missing or unmet), `verification-gap` (behavior exists but evidence is missing), `product-plan` (a proposal or open product choice), `conflict` (credible sources disagree), `knowledge-gap` (a specific behavior is unexplained or undocumented; never the vault's own research backlog) |
| `recheck` | always | `not-checked`, `confirmed` (still holds), `not-reproduced` (no longer holds), `outdated` (the cited sources changed after the last recorded recheck); see [What a recheck means](#what-a-recheck-means) |
| `rechecked_by` | when `recheck` is not `not-checked` | a person's name, or `agent`; an agent always writes `agent`, and a person's name appears only when that person ran the check and said so |
| `rechecked_on` | when `recheck` is not `not-checked` | `YYYY-MM-DD` |
| `decision` | always | `open`, `accepted`, `rejected`, `deferred`, `done`, `duplicate` |
| `decided_by` | when `decision` is `accepted`, `rejected` or `deferred` | a person's name; the value `agent` is an error |
| `decided_on` | when `decision` is `accepted`, `rejected` or `deferred` | `YYYY-MM-DD` |
| `duplicate_of` | when `decision` is `duplicate` | id of another existing gap (not itself) |
| `created` | optional, gap pages only | `YYYY-MM-DD`: the day the gap was written. Set it when you create the gap and never change it. The viewer shows it on the gap and can list the newest gaps first; for a page without it, the viewer uses the day the page was first committed. |
| `topic` | optional, gap pages only | what the gap is about, one of `security` (who may reach, see or change what; tokens and secrets), `validation` (a field checked differently, or not at all, by the form, the server and the database), `data` (records lost, damaged or out of step with each other), `logic` (a business rule that is missing, unclear or contradicts another), `ui` (what a person sees: texts, states, the same thing looking or behaving differently in two places), `api` (what another system calls: unused, undocumented or inconsistent endpoints), `ops` (jobs, schedules, configuration, deployment). One value: the one a person looking for this gap would filter by. `kind` says what sort of doubt it is; `topic` says what it is about. The viewer filters the queue by it. |
| `review` | optional, gap pages a review wrote | the review that wrote the gap, in the word of its run page: `"security"`, `"abuse"`, `"flows"`. Set by [a review](review.md) on every gap it creates, and never changed afterwards. `topic` says what the gap is about; this says which pass found it, and two reviews can share a topic. |
| `priority`, `confidence` | optional, gap and plan pages only | short strings, e.g. `"high"`. Use `high`, `medium` or `low` for `priority` (or `P0` to `P4`): the viewer lists the most urgent gap of each state first, can show one priority only, and can list the newest gaps first instead. |

`decided_by` and `decided_on` are also allowed on `done` and `duplicate` but not required. With `outdated`, `rechecked_by` and `rechecked_on` stay in place as the record of the last recheck actually done. A fresh recheck replaces all three fields and adds a new dated entry to the `Recheck` section; keep the older entries.

The `rechecked_*` fields must be absent only while `recheck` is `not-checked`; `decided_*` absent while `decision` is `open`; `duplicate_of` absent for any other decision. Optional `tags`, `aliases`, `task_ids`, `summary` and `verification` work as on other pages.

A plan page has `type: "plan"`, a `status` (`current`, `partial`, `planned`, `stale` or `superseded`; use `planned` until the work is done) and `gap`: the id of an existing gap whose `decision` is `accepted` or `done`.

## The six sections

Every gap has exactly these `##` headings, once each (order does not matter). A missing or repeated heading is a validation error.

- `## Current behavior`: what the code does today in this area, as plain fact, linking the relevant spec notes. No opinion about what it should do.
- `## Gap`: the one question this page asks, phrased so a person can answer it. If the finding has a second aspect with a different next step or owner, make it a second page.
- `## Evidence`: what supports the question: files and symbols read, commands run with results, `NOT RUN` for anything only read. Label documented intent, static reading and observed execution separately.
- `## Recheck`: while `not-checked`, write "Not checked yet." Otherwise: who re-verified, how, when, and what they found, newest entry last. When you set `outdated`, add a dated line saying which source changed. The pass that raised the gap is not a recheck.
- `## Discussion`: append-only log, see below.
- `## Decision`: while `open`, write "Open." Otherwise the decision and its reason, in the words of the person who decided. For `done`, say where in the code the question is now closed. For `duplicate`, name the surviving gap.

When `recheck` is not `not-checked`, the Recheck section must have text; when `decision` is not `open`, so must Decision.

## What a recheck means

A recheck asks one question of every gap, whatever its kind: **does the page's `Current behavior` section still describe the code?** It is not a verdict on the gap's worth. The reason to ask is that a person decides on the gap only after someone has confirmed the page still describes reality, and that needs to be possible for proposals and questions about unexplained behavior too, not only for defects.

- `confirmed` ("confirmed (still holds)"): yes. What `Current behavior` says, including what it says is absent, is what the code does now.
- `not-reproduced` ("not reproduced (no longer holds)"): no. The code no longer matches the description: the capability exists, the defect is gone, the sources stopped disagreeing. The usual next step is `decision: "done"`, or rewriting the gap around what is true now.

What that means for each kind:

| Kind | `confirmed` (still holds) | `not-reproduced` (no longer holds) |
| --- | --- | --- |
| `product-gap` | The requirement is still unmet: the code does not do what it asks for. | The code now meets the requirement, or the defect cannot be reproduced. |
| `verification-gap` | The behavior is as described and the evidence is still missing. | Evidence now exists (a test, a run, a log), or the behavior differs from the description. |
| `product-plan` | The proposed capability is still absent and nothing already implements it. | Something in the code now does what was proposed. |
| `conflict` | Both sources still say what the page says, and they still disagree. | One source changed or the claims no longer clash. |
| `knowledge-gap` | The thing is still unexplained or undocumented: no code, comment or document answers it. | The code or a source now answers the question. |

A recheck never judges whether a proposal is worth doing, whether a requirement is right or which side of a conflict should win. That is the person's decision, made afterwards. For a proposal or a question about unexplained behavior the recheck is usually quick, for example reading the code to confirm the capability is absent, and it is still required: without it the gap stays in `needs-recheck` and cannot reach `needs-decision`. Write what you read in `Recheck` so the person can see the page was checked, not assumed.

## A queue too long to read

A queue of several hundred open gaps is not read by anyone. When a person says so, thin it in this order, and say how many gaps each step moved:

1. **Twins and patterns.** Gaps that ask the same question of the same feature are duplicates: keep the one with the most evidence and close the others as `duplicate` with `duplicate_of`. The same question in three features or more becomes one gap for the pattern, with a table of the places, and the single gaps are closed as its duplicates ([the review guide](review.md#writing-the-gaps)). This is bookkeeping and needs no decision.
2. **One decision for a class.** A person may decide many gaps in one sentence: "I defer every low-priority proposal", "reject the gaps about the old admin screens". That is a decision a person made: record it on each gap it covers, with their name in `decided_by`, today in `decided_on` and their sentence in `Decision`. Never choose the class yourself, and name the gaps it covered in your report.
3. **Recheck from the top.** Recheck `high` first, then `medium`, against the current code. What no longer holds is closed as done; what holds is what the person reads.

Lower a `priority` only when the page itself shows it was set too high, and say so in `Discussion`. Do not delete a gap to shorten the queue.

## Discussion entries

One bullet per entry, oldest first, never edited or removed afterwards:

```text
- 2026-11-15 · Name: what was said, proposed or learned.
```

Use `agent` as the name for entries you write yourself. Layout of options, objections and questions belongs here, not in `Decision`, which records only the outcome.

## Who sets which field

| Field | Who |
| --- | --- |
| New gap: `kind`, `topic`, `recheck: "not-checked"`, `decision: "open"`, `created` (today), optional `priority`/`confidence` | The agent that found it |
| `topic` on an older gap that has none | An agent, from the gap page alone; it is bookkeeping and no recheck |
| `recheck`, `rechecked_by`, `rechecked_on`, `Recheck` text | Whoever actually performed the check; an agent writes `agent` only for a check it ran itself, with its commands and results. An agent may also set `recheck: "outdated"` when a cited source changed since the recorded recheck, keeping the other two fields |
| `decision: accepted`, `rejected`, `deferred` with `decided_by`, `decided_on` | A person only. An agent writes it only when a person said so in the conversation, and records that person's name |
| `decision: done` | An agent may set it after reading current code that closes the question; it cites where in `Decision` and records that reading as a recheck (see below). A person closing a gap as done records the decision in `decided_by`/`Decision`; their name goes in `rechecked_by` only if they read or ran the current code themselves, otherwise the recheck fields stay as they are |
| `decision: duplicate`, `duplicate_of` | Agent or person (bookkeeping) |
| `Discussion` | Anyone, by appending |

Never guess a decision from silence, from a plan existing, or from a task being created. If it is unclear whether a person decided, leave `open` and ask in `Discussion`.

## Closing a gap as done

When an agent sets `decision: "done"` because it read (or ran) the current code and the gap no longer holds, that reading is itself a recheck, and the page should say so. In the same edit record `recheck: "not-reproduced"`, `rechecked_by: "agent"`, today's `rechecked_on`, and add a dated entry to `Recheck` saying what was read or run. In `Decision`, say where in the code the question is now closed. The two sections answer different questions: `Recheck` is how you know it no longer holds, `Decision` is where the code does it. Without the recheck fields a closed gap looks as if nobody ever looked at the code. When a person closes a gap as done, they record the decision in `decided_by` and `Decision`. Their name goes in `rechecked_by` (not `agent`) only if they read or ran the current code themselves and add a `Recheck` entry saying what they did; if they decided without doing so, leave the recheck fields as they are. If you are not sure the question is closed, leave it open.

Closing a gap is also the moment its answer becomes part of the spec. Before you set `done`, open the page of the feature the gap is about and make sure it states what is true now as a numbered rule, read from the current code: add the rule, or correct the one that was there. Then name that rule in the gap's `Decision` ("Closed by BR-USERS-07") next to the place in the code. The same goes for `rejected`: the behavior stays as it is, so the feature's page should already state it as a rule, and `Decision` names that rule beside the person's reason. The link goes one way, from the gap to the spec page; a spec page still never mentions a gap.

A closed gap is not deleted. The spec says what the code does; the closed gap is the only place that says why, who decided and what was checked. The viewer takes closed gaps (`done`, `rejected`, `duplicate`) out of the queue, lists them under History with the most recently closed first, and shows them on the feature's page as closed questions, folded under the text. Delete a gap only when a person calls the page noise.

## Derived state

Computed by the helper, never written into Markdown:

| `decision` | `recheck` | State |
| --- | --- | --- |
| `open` | `not-checked` or `outdated` | `needs-recheck` |
| `open` | `confirmed` or `not-reproduced` | `needs-decision` |
| anything else | any | the `decision` value |

Every open gap passes through a recheck before `needs-decision`, including proposals (`product-plan`) and questions about unexplained behavior (`knowledge-gap`). Rechecking a proposal means confirming the capability is still absent, not judging the proposal.

## Example gap page (illustrative)

````markdown
---
id: "invoice-retry-limit"
title: "Should failed invoice emails retry more than once?"
type: "gap"
kind: "product-plan"
topic: "ops"
areas: ["billing"]
sources: ["src/billing/mailer.py"]
recheck: "confirmed"
rechecked_by: "Dana Ruiz"
rechecked_on: "2026-11-15"
decision: "open"
priority: "medium"
updated: "2026-11-15"
---

# Should failed invoice emails retry more than once?

## Current behavior

`send_invoice` makes one delivery attempt and logs a failure; it does not schedule another. See [[notes/invoice-delivery|Invoice delivery]].

## Gap

Customers with a temporary mail outage never receive the invoice. Should the mailer retry, and if so how many times and over what period?

## Evidence

- Static: `send_invoice` in `src/billing/mailer.py` has no retry loop or queue call.
- Documented intent: none found; no requirement mentions retries.
- No test covers a failed first attempt (NOT RUN, nothing to run).

## Recheck

2026-11-15, Dana Ruiz: re-read `send_invoice` and ran it against a stubbed transport that raises on the first call; the invoice stays unsent, one error is logged and nothing schedules a second attempt. No queue or retry code exists elsewhere in `src/billing/`. Confirmed (still holds): the capability is absent. Whether to add it is the open question below.

## Discussion

- 2026-11-15 · agent: Options are (a) fixed three retries within an hour, (b) hand the email to the existing job queue, (c) leave as is and show a "resend" button.
- 2026-11-16 · Dana Ruiz: Leaning to (b); need to check queue limits first.

## Decision

Open.
````

## Writing a plan page

Create one only for a gap whose `decision` is `accepted`. Name it `plans/<gap-id>.md`, give it its own `id` (for example `<gap-id>-plan`), set `gap` to the gap's id and use the gap's areas. The body states the goal and what exists today (with links to spec notes), the ordered steps with the files they touch, observable acceptance checks, what is out of scope, and which checks have not been run. A plan records intent for one decision; it does not add facts to the spec. When the work lands, an agent that reads the code may set the gap to `done`, and the spec notes are then updated from the code.
