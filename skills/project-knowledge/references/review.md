# Reviewing one topic

A map says what the product does. A review goes through the same product again with one topic in mind (is it safe, do the form and the server check the same things, do its rules agree with each other, is its API in order) and a fixed list of questions, so that nothing is skipped because it looked fine. It is a separate pass that a person asks for by name. It opens every entry point in its scope again, so it costs about as much reading as the features it covers.

A review is asked for in one of two ways: **by topic**, one list of questions over the features ("review the product for security"), or **by feature**, every list on one feature ("run every review on the checkout"). Either way it reads the high-priority features first and stops when that level is done; the person says whether it goes on with the rest ([Which features first](#which-features-first), [By topic or by feature](#by-topic-or-by-feature)).

A review leaves three things:

- **Rules the pages were missing.** What the code answers plainly (only an admin may open this, a file may be 10 MB at most) is a numbered rule on the feature's page, like any other rule.
- **Gaps.** Each doubt that is worth a person's decision is one gap with `topic` set, in the same queue as every other gap. A small one is a line on the run page ([What is worth a gap](#what-is-worth-a-gap)).
- **A run page** that says which features were reviewed and which were not, so the pass can be continued.

It never changes application code and never decides a gap.

## What a review is not

A review reads code. It runs no scanner, no test and no application, like every other pass of this skill.

- Known vulnerabilities in dependencies, outdated packages, secrets in the Git history and the settings of what is deployed are found by tools, not by reading. Name the tool under "Not covered" in the report (`npm audit`, `pip-audit`, `osv-scanner`, a secret scanner). Run one only when the person asks. Settings the repository holds (a storage bucket, a queue or a function declared in a file) are code, and are read.
- A document in the repository that says how the product should work (a design note, an architecture page) is not evidence for a review and is not reviewed by it. Comparing it with the code is [an audit](audit.md).
- It is not a penetration test and not a certificate. "No gaps found" means the questions below found nothing in the code that was read. Say it that way, never "the product is secure".

## The pass

1. **Scope.** The whole product, an area, one feature, or what changed since a commit or a day ("review the security of what changed last week" takes the features the diff touches). Say which before you start.
2. **The list.** A review needs a map: [the inventory file](../SKILL.md#the-inventory-file) is its list of features and entry points. Without a vault, say so and offer a map first. A question about one feature in a repository that has no vault is an **investigate**, and it ends as a report. A feature the inventory has as `not started` is reviewed from the code alone, and the run page says its page does not exist yet. A review does not write that page. What the code answers plainly about such a feature goes on the run page under `## Rules found`, one line each with the file, for the map to take up when it reaches the feature. Take the features in the order of [Which features first](#which-features-first), and write each feature's `Priority` first when the inventory does not have it.
3. **The run page.** Each review has one run page, and it is the ledger of that review: `runs/<date>-review-<topic>.md` with `review: "<topic>"` and `status: "partial"`. It says the topic, the scope, the revision, and lists the features of the product (or of the scope the person named) as a checklist (`- [ ] Name of the feature`), under one heading per level and in the order they will be read:

   ```markdown
   ## Feature checklist

   ### High

   - [ ] Checkout
   - [ ] Team members

   ### Medium

   - [ ] Profile

   ### Low

   - [ ] About page

   ## Read

   - Checkout: followed `web /checkout`, `api order.create` and `job capture-payment` to `src/orders/service.ts`; questions 7 and 13 had nothing to ask (no files, no job of its own).
   ```

   - **The whole list, not only this pass.** The checklist names every feature of every level, with the feature's name as the inventory has it. This pass ticks the ones it reviews; the others stay unticked, so the page says what the review has not read. Leave out a level that has no feature.
   - **One page per review, used again.** A later pass of the same review, for the next level or for one more feature, goes on in this page: it ticks there, adds a feature the list lacks under its level, and sets `updated`. Make a new page only when the person asks to run the review again from the start.
   - **A line under `Read` for each reviewed feature**: which entry points were followed and to which file, and which questions had nothing to ask there. A feature is ticked when every question was asked of every one of its entry points and this line is written. A tick without the line is not a review.
   - Write a feature's name as plain text, or its page's path in code formatting: a run page never links to vault pages, and `check` refuses it when it does. Save the page after each feature. A later session reads it first and goes on with the first unticked feature of the level it was asked for.
   - The viewer and the `summary` and `next` commands read this page to say which reviews were run, when, and how far each got in each level. So keep the property, the name, the three level headings and the checklist as written here, and use no other checkbox on the page.
4. **One feature at a time.** Read the feature's page, then open each entry point and answer the topic's questions from the code. The page tells you where to look; it is not the evidence. Ask every question of every entry point it applies to, and do not stop at the first finding. A question the product has nothing for (it has no accounts, takes no files, calls no other service) is skipped: name it once on the run page, under the checklist, with the reason.
5. **Each answer goes to one place.**
   - The code does it, and the page does not say so: add the rule to the page, with the next free number. For security, also set [the page's `access`](format.md#properties).
   - The code does it, and the page says so: nothing to write.
   - The code does not do it, does it in one place and not in another, or you cannot tell whether it is meant: a gap when it matters, a line on the run page when it is small ([What is worth a gap](#what-is-worth-a-gap)).
6. **Stop at the end of the level.** A pass covers one level: the high features unless the person named another level, a feature or an area. When its last feature is ticked, stop, even if time is left. Go on into the next level only when the person asked for more than one ("every level", "the whole product").
7. **Finish.** Run `check`. The sources of a gap or a page this pass wrote and read are accepted with `snapshot --notes <ids>`; do not snapshot a page whose changed source you did not read. Set the run page to `current` when every box on it is ticked, so a review that has read one level of three stays `partial`. Then run `next` and give the person its requests as they are printed: how to go on with this review, which other reviews have not read this level, and which features can be read whole. Do not choose for them. Report real counts: features reviewed out of those in scope, for each level, rules added, gaps written by priority, lines noted, and "Not covered" with the tools that would cover it. A level that was not reviewed is said to be not reviewed, never clean.

## Which features first

A product has features where a mistake costs money, access or somebody's data, and features where it costs a wrong avatar. A review reads the first kind first. The order comes from what each feature does, read from the code as a few fixed signals, and not from how important a feature looks.

**The signals.** Give a feature each signal that is its own business, and not one it only passes by: the checkout has `money`, a page that shows a price does not.

| Signal | The feature |
| --- | --- |
| `money` | takes, moves or prices money: a payment, a plan, an invoice, a balance, a discount |
| `accounts` | decides who gets in and what they may do: sign-in, recovery, roles, invites, sessions, keys and tokens |
| `others-data` | reads or changes records that belong to another person, team or tenant, or lets an admin act on anyone's |
| `destructive` | removes or overwrites what cannot be brought back: a bulk delete, the deletion of an account, an import that replaces, files on a person's disk |
| `public` | can be reached by a stranger without signing in, or is called by another system (a webhook, a public API). This is not a page's `access: ["public"]`, which only says the feature has no sign-in |
| `files` | takes a file from a caller, or an address the product then fetches |
| `outbound` | sends messages to people or calls another service, above all one that is paid for |
| `central` | is on the way every user takes (signing up, the first use, paying), or writes a record that three or more other features read |

**The level follows from the signals by rule**: `high` with `money`, `accounts`, `others-data` or `destructive`; `medium` with any of the other four and none of those; `low` with no signal. Do not raise or lower a level by feel: a level a person cannot trace to a signal is a guess. Write it in [the inventory file](format.md#the-inventory-file) as one line under the feature's heading, with its signals as the reason:

```text
Priority: high (money, others-data)
Priority: medium (files)
Priority: low
```

- **When it is written.** With the inventory, from what the entry points show, and corrected when the feature is finished and its code was read. A review of a vault whose inventory has no `Priority` lines writes them first, for the features in scope: from the inventory and the features' pages, opening code only for a feature that has no page. This is minutes of reading, not a pass. A level is a level of the whole inventory: when a person asks for "the high-priority features" and part of the inventory has no `Priority`, rank that part first, because a feature nobody ranked may belong to the level. A review of features the person named ranks only those.
- **A person's word wins.** Only the person knows that one export feeds the accountant and that nobody uses the old importer. When they set a level, write it with their reason and their name, `Priority: high (set by Ana: the accountant's export)`, and never change that line.
- **Say the list before the pass.** Before the first feature, tell the person how many features each level has and name the high ones, so they can correct the list. Do not wait for an answer.
- **The person's order wins.** If they name the features or the order to read them in, read them in that order.
- **When most are high, the level sorts nothing.** If more than half of the features in scope come out `high`, read the signals again and keep each only where it is the feature's own business. Say in the report how many you moved.
- **A level is an order, not a verdict.** A `low` feature is reviewed last and only when the person asks, and a mistake can live there too. The report says for each level how many features were reviewed; it never calls an unreviewed level clean. A person may name a level as the scope ("review the medium features for security").

**One topic.** Inside each level, a review of one topic takes first the features that carry one of that topic's signals:

| Review | Its signals |
| --- | --- |
| `security` | `accounts`, `others-data`, `public`, `files`, `money` |
| `abuse` | `public`, `files`, `outbound`, `money` |
| `validation` | `public`, `files`, `money` |
| `data` | `money`, `others-data`, `destructive`, `central` |
| `logic` | `money`, `accounts`, `central` |
| `flows` | `money`, `accounts`, `central`, `destructive` |
| `failures` | `outbound`, `destructive`, `money` |
| `api` | `public`, `outbound` |
| `ui` | none: the order of the level |

So a profile page that takes an avatar is `medium` because of `files`: a security review reads it before any `low` feature and first among the `medium` ones, and a logic review reads it late.

## By topic or by feature

Do not take every list over every feature in one pass, even when a person asks for "everything". The code is then read once and the lists are answered from memory: it is quick and finds a fraction of what the same lists find one at a time. Offer the two ways below and let the person pick; `next` prints the request for each.

**By topic.** One list of questions over one level of features. This is [the pass](#the-pass) above. A person who wants several topics gets them as separate passes, one after another, each finished before the next starts so that it finds the gaps of the ones before it in the queue: `flows` and `logic` first, then `security`, `abuse`, `validation`, `data`, `failures`, `api` and `ui`. Say which of them have little to ask of this product (an API review of an app that calls nothing), so the person can leave them out.

**By feature.** Every list on one feature, for a feature that matters enough to be read whole. One feature per pass; a few small ones of the same area when the person names the area.

1. Read the feature's page, open every one of its entry points and follow each to the code that decides the behavior.
2. Ask the lists in four groups, in this order: `flows` and `logic`; then `security`, `abuse` and `validation`; then `data`, `failures` and `api`; then `ui`.
3. Finish a group before you start the next: its rules, its gaps and its noted lines written, the feature ticked and its `Read` line written on that group's run pages, the files saved. Answer each group from the code and open a file again when you need it, not from what you remember of the group before.
4. A gap gets the `review` of the list whose question found it, and that list's `topic` unless a rule of this guide names another (a flows review that meets a skipped check, a tool with nobody else to harm). The first list that meets a finding writes it. A later list that asks about the same thing adds nothing, and its `Read` line says where the finding is.
5. Each review's run page is the same ledger as in a pass by topic. Where a review has none yet, make it with the whole checklist; this pass ticks one feature on each of the nine.
6. Then stop, report what each list found, and give the person the requests `next` prints.

**The person chooses what goes on.** After the high level a review has read what matters most, and the rest is the person's call: the same review on the medium features, another review on the high ones, or one more feature read whole. A person who wants no stops says so ("every level", "do not stop between levels") and gets the levels one after another.

## A product that is not a web application

The lists are written in the words of a product with accounts, forms, a server and a database. A desktop or mobile app, a command-line tool or a library has the same questions under other names. Ask them of what the product has:

- **A role or a permission** is also what the system grants the app: the microphone, the screen, a folder, notifications. It can be refused, and taken away later.
- **A step of a flow** is also a system dialog, the installer, the first launch, an update.
- **A record** is also a file on disk, a setting, a temporary folder.
- **Two at once** is also two running copies of the app, or the old version and the new one during an update.
- **Another service** is also the operating system, the store, the update feed.
- **The signals** of [Which features first](#which-features-first) are read the same way.
  - `public` is what a stranger can reach: a command a person runs on their own machine is not public, a local server that listens beyond this machine is.
  - `destructive` is a command that deletes or clears a folder or a file the person names. Writing its own output under a name it chose is not, even when a file of that name was there.
  - `files` is a path, a folder or an address the person passes in, where reading or writing it is what the command is for. An optional side file every command takes (a history, a cache) does not count.
  - `outbound` is a call over the network. Starting a program on the same machine is not.
  - `central` is the step every use begins with: the install, the setup, the first command the others build on.
- **Nobody else to harm.** In a tool with one user, on their own machine, a missing check on a path or a file harms no other person. Such a gap is about that person's own work: give it `topic: "data"` when it can lose their files and `topic: "ops"` otherwise, and keep `security` for what another person or another system can reach.

What the system does in such a moment (which dialog it shows, whether it starts a second copy) is often not in the repository. Say what the code does and does not handle, name the rest under "Not covered", and write the doubt as a `knowledge-gap`.

A review most of whose questions have nothing to ask (an API review of an app that calls nothing) is still run. It is short, and its run page says which questions were skipped.

## What is worth a gap

A gap asks a person for a decision, and a person reads a queue of forty, not of seven hundred. A review asks ten questions of every entry point of every feature, and most of what it meets is small. Written as a page each, the small things bury the few that matter. So a review writes a gap only for what is worth the decision, and notes the rest.

- **A gap** is for what the topic's list rates `high` or `medium`.
- **A line on the run page** is for what it rates `low`: a small inconsistency, a proposal for polish, something that could be nicer. It goes under `## Noted`, one line each: the feature, what the code does with the file in code formatting, and the question. It has no page, no recheck and no decision.

```text
## Noted

- Blog editor: after a version conflict the form keeps the text and offers no way to merge it (`src/features/blog/editor/BlogEditor.tsx`). Keep a copy while it reloads?
- Pricing: the header has no Log in action on a phone (`src/features/pricing/Header.tsx`). Meant?
```

- **Between `medium` and `low`**, ask what happens if nobody ever reads it. When the answer is "nothing much", it is a line.
- **A small thing in many places can be worth one gap.** One form that trims a field differently is a line; ten of them are a question about the product ("One doubt per page", below).
- **A line becomes a gap** when a person asks for it, or when a later pass finds it is worse than it looked. Then write the gap and strike the line.
- **A person may ask for everything as gaps** ("write the low ones as gaps too"). Then do, with `priority: "low"`.

## Writing the gaps

The rules in [gaps.md](gaps.md) apply. A review adds these:

- **Look in the queue first.** A gap that already asks the question does not get a twin. It gets `topic` when it has none, and a dated line in `Discussion` only when this pass saw what the page does not say: another entry point, another consequence. Meeting the same question again is not news and adds no line.
- **One doubt per page.** The same missing check in several entry points of one feature is one gap that lists them. In two features it is two gaps, because each feature has its own owner and decision.
- **In three features or more it is a pattern, and one gap.** The decision is one for the whole product, so ask it once: the title asks it of the product ("Should every text field refuse characters the database cannot store?"), `Current behavior` has a table of the places (feature, entry point, what the code does there), `areas` names every area it touches, and `priority` is that of the worst place. When a later feature shows the same thing, add a row to that gap and a dated line to `Discussion`. When you meet the third place and two gaps already ask it, write the pattern gap and close the two as `duplicate` of it.
- **The title is the question a person decides**: "Should a member be able to change another member's role by saving the profile form?", not "Broken access control in users.save".
- **`topic` is the one the list below names**, the same for every gap of the pass, so the queue can be filtered to what this review found.
- **`review` is this pass's word**, the same as on the run page: `review: "flows"`. It says which review wrote the gap, which `topic` cannot say when two reviews share one. `summary`, `gaps --review` and the viewer count by it. A gap that was already in the queue keeps what it has.
- **`kind` as usual**: `product-gap` when a rule the product enforces elsewhere is not enforced here, `conflict` when two places disagree (the web refuses what the server accepts), `knowledge-gap` when you cannot tell whether it is meant, `product-plan` for something to add (a limit on sign-in attempts).
- **`priority`**: `high` when a person can read or change what is not theirs, act without signing in, or move money; `medium` when it needs a signed-in insider or an unusual condition; `low` otherwise.
- **Evidence says how it is reached, in words**: which entry point, which check is absent, which symbol. `NOT RUN` for what was only read. No working request, script or payload: the page is for the person who fixes it.
- **A file `check` treats as a credential file** (`.env`, a file named `secrets` or `credentials`, a key) cannot be in a page's `sources`. Name it in `Evidence` in code formatting and cite the file that uses it.
- **A security gap describes a weakness of a live product.** Before the vault is published where people outside the team can read it, tell the person these pages are in it.

## Security

Gaps get `topic: "security"`. This review asks who may do what. How big, how often and at what cost a person who may do it can do it is the business of [an abuse review](#abuse); write a gap for one you meet, and leave the questions to that pass. Ask these of every entry point.

1. **Who can reach it?** Nobody signed in, anyone signed in, one role? Find the check on the server: that a request without a session is refused, and that each role the client tells apart is told apart there too. A menu that hides the link and a redirect in the client are not a check.
2. **Whose record is it?** When the request carries an id, does the server check that the record belongs to the caller, their team or their tenant? Is every list filtered by the caller on the server?
3. **Is there another way to it?** The same record or action through an older version of the call, an admin, internal or debug route, a live channel a client subscribes to, the mobile app's endpoint, an import or a job: does each apply the check the main way applies? A way in that skips it is a gap.
4. **What may be changed?** Which fields does it accept? Can the caller set one they must not: role, owner, tenant, price, balance, status, a "verified" flag? Look for a request body passed whole into an update.
5. **What comes back?** Fields the caller should not see: password hashes, tokens, other people's contact details, internal notes. Does an error tell whether an account or a record exists?
6. **What is done with the input?** Is raw input put into a query, a shell command, a file path, HTML shown to other people, a URL the server fetches, or a redirect target?
7. **Files and exports.** Where is a file a person uploaded, or one the product made for them, kept? Who can fetch it, and can its address be guessed?
8. **Steps that can be skipped.** Where an action takes several steps (pay, then confirm; prove an email, then get in; accept an invite, then get a role), does the server check at the last step that the earlier ones happened, or does it take the client's word?
9. **Signing in and recovery.** Is the number of attempts limited for sign-in, reset, invite and code entry? How long does a reset, invite or sign-in link live, and does it work twice? What ends a session: a password change, a removed role?
10. **Secrets.** A key in client code or in the repository, a secret written to a log, a token in a URL.

And by kind of entry point:

11. **What a browser calls.** When the session is kept in a cookie: is a request that changes something protected against being sent from another site (a token, `SameSite`)? Which sites may call with the cookie (CORS)? Is the cookie kept from scripts and sent only over HTTPS? Calls between servers have none of this; the next question is theirs.
12. **What another system calls.** Is the sender proven (a signature, a shared secret)? Can the same call be replayed?
13. **What runs on its own.** With whose rights does the job act? Does it cross tenants? Does it trust records that users control?
14. **What the product sends out.** Is the address taken from the request? Does the message carry another person's data, or a link with a token?
15. **Money and what cannot be undone.** Does the amount come from the client? Is a repeated request safe? Is there a confirmation?

## Abuse

Gaps get `topic: "security"`; give the run page `review: "abuse"`. A security review asks who may do a thing. This one asks what a person who may do it can do too much of: send something too big, do it too often, or send something that is not what it says. Read every entry point as an ordinary member with an account of their own, not as an outsider. Where there is no other person to harm (an app with one user, on their own machine), a missing limit is not about security: give that gap `topic: "ops"`.

Three things differ from the other passes:

- **Start from what a caller can send**, feature by feature: a text, a request body, a list, an imported table, a file. Ask each question of each of them. A question the product has nothing for (it takes no files, it pays no other service) is skipped, and the run page says which were skipped and why.
- **Follow it to where it ends**, not only to the code that receives it: the table, the queue, the job that works on it, the storage, the address other people fetch it from. Most of what this review finds lies between two of these, where each part takes the other to have checked.
- **Read the settings the repository holds** for those places (a bucket, a queue, a function, a delivery address, declared in a Terraform, CDK, serverless or compose file): what is public, who may write. What is set up outside the repository goes under "Not covered".

1. **How big.** For each thing a caller sends, is there a maximum: the length of a text, the size of a body, the items of a list, the rows of an import, the depth of nested data, the bytes of a file, the pixels of an image? Is it applied before the server has read the whole thing?
2. **What one request costs.** Does it read a whole file, list or table into memory, go through every item, query without a page size, run a pattern or a search the caller wrote, or resize, convert or unpack something? Does one action become many (a message to every member of a group, a job for each row)? Is there a limit on time? Could one request, or a few at once, stop the server for everyone else?
3. **Said or checked.** What does the server believe because the caller said it: a type, a size, a count, a name, a total? Does what was said choose how the thing is handled (which parser, which decoder, which queue)?
4. **How many and how often.** What limits how many records, links, invites, exports or uploads one account makes, in an hour and in all? Is the limit counted for the account, or only for the address the request comes from? Does it hold when several requests arrive at once, or is the count read first and the record written after? What a member sets to run on its own (a schedule, a rule, a webhook of their own): how many may there be, and how often may each run?
5. **Past the server.** Does anything reach storage or another service without passing the server: a signed link to upload with, a client that holds a key? What does the link fix (the place, the type, the size, how long it works), and which of the limits above still hold on that way?
6. **Paid work.** Which requests make the product pay: a message sent, a conversion, a moderation or AI call, storage kept? What limits them for one account, and is there a ceiling for all accounts together?
7. **What is sent.** How many emails, texts or notifications can one account make the product send, and to whom: only to people who agreed, or to any address it types? Can it put words or a link of its own into them? How often can one person get the same message: is a reminder, a digest or a retry sent once, or again on every run until something stops it?
8. **What is left behind.** What happens to what was refused, or failed on the way: is it deleted, or kept and still reachable? What does an action leave that was started and never finished?
9. **What other people get.** Is what one person sent given to others as it arrived? From which address, as which type, and can it be a page with a script on the product's own domain?

`priority` is `high` when one account can stop the product for everyone, make it pay or send messages without a limit, or put a page of its own on the product's domain; `medium` when the harm has a bound (one account fills its own storage, a job runs late); `low` otherwise. `kind` is `product-gap` when a limit the product applies in one place is absent in another, and `product-plan` for a limit it has nowhere.

## Validation

Gaps get `topic: "validation"`. For every form, and for every entry point that takes input, put three places side by side: the form in each client, the server, and the database column. A review of validation also brings the `Fields` table of each feature's page up to date, with the rule of each side where they differ.

1. **A check only the form has.** Is every rule the form applies also applied on the server? One that is not can be skipped by calling the server directly.
2. **Different limits.** The same field with another length, range, count or format in the form and on the server (60 characters in the form, 100 on the server).
3. **Required here, optional there.** In the form, on the server, in the database (`NOT NULL`).
4. **What the database holds.** A column shorter than the allowed length, uniqueness kept only in code, a number column that cannot hold the allowed range.
5. **Other ways in.** The same field through create and edit, the web and the mobile app, an import, a public API, an admin screen, a job: does each apply the same rules? An import or an admin screen that skips them is a gap.
6. **What is done to the value.** Trimming, letter case (two accounts whose emails differ only in case), empty text against no value, leading zeros, characters outside the Latin alphabet.
7. **Numbers, money and dates.** Negative and zero, decimals and rounding, a maximum; a date in the past or far ahead, an end before the start, the time zone a date is read in.
8. **Lists and files.** A maximum number of items, each item checked, size and type of a file.
9. **The refusal.** Does the person learn which field and why? Is it the same message for the same rule in every client? A server refusal the form shows only as "Something went wrong" is a gap.
10. **Fields nobody checks.** A value stored as it arrives: free text with no maximum, a URL or an email with no format check, a status taken from the request.

`kind` is `conflict` when two places disagree, `product-gap` when a rule the feature states is not enforced somewhere, `knowledge-gap` when you cannot tell which side is meant.

## Data

Gaps get `topic: "data"`. For every kind of record the product keeps (take them from the schema), and every entry point that writes one.

1. **States.** Which states can the record be in, and which changes between them does the code allow? Is there a state it cannot leave, or one nothing ever sets?
2. **Deleting.** What is left behind: rows that point to a deleted record, files, search entries, scheduled jobs? Where records are only marked as deleted, does every list and every lookup by id leave them out?
3. **Several writes for one action.** Are they in one transaction? What is the state after the second of three fails?
4. **Two at once.** Two people saving the same record, the same button pressed twice, the same webhook delivered twice: is the last write silently kept, is something counted or charged twice?
5. **Rules kept only in code.** Uniqueness, a reference to another record, a sum that must match its parts: does the database enforce it, or only the one code path that was read?
6. **Copies of one fact.** A total stored beside its lines, a counter beside the rows it counts, a name copied into another table: what keeps them equal, and what repairs them?
7. **Money and time.** How is money stored and rounded, and where is it rounded twice? In which time zone is "today" or "this month" decided?
8. **History.** Is it recorded who changed what and when, where the product promises it? Can a change be undone?
9. **Changes of the schema.** A column a migration added that old rows leave empty, with code that assumes a value.
10. **Leaving.** What happens to a person's or a team's data when the account is deleted, and to what others still need (invoices, shared records)?

## Logic

Gaps get `topic: "logic"`. The other reviews ask whether a rule is enforced. This one reads the rules themselves: where two of them disagree, and what the product never decided. Start from the numbered rules on the feature's page and from the code that decides (every condition, every comparison with a limit, every refusal), with the reference notes for the roles, the plans and the states of a record beside you: most of what this review finds is a case one of those lists has and the code has no answer for.

1. **Rules that disagree.** Is the same thing decided differently in two places: a pickup this feature lets a customer cancel and another refuses, a limit of 5 here and 10 there, a role that may do it from one screen and not from another? Compare the feature's rules with the rules of every page that names the same record or action.
2. **A case nobody decided.** Where the code branches on a state, a role, a plan or a type, go through every value the list has. Which have no branch of their own, and what happens to them: the same as the last branch, nothing, an error? A trial that ended, a member who was suspended, a record that was archived.
3. **At the edge.** Exactly at the limit: is the fifth allowed or refused, and does the message say the same number? Zero and one: an order with no lines, a team with no members. And the last one: can the last admin be removed, the only owner leave, the default item be deleted?
4. **Acting on oneself.** Can a person take away their own role, delete an account that still owns things, approve their own request, invite or pay themselves? Is that meant?
5. **One rule in two places.** A price, a total, a discount, a due date, "may this person do it": is it worked out once, or again in each client, in the list and on the record's page, on the server and in a job? Are the formula and the order the same (the discount before the tax, or after it)?
6. **Rules about time.** Something that ends, expires or falls due: what makes it happen, a job or the next time somebody looks? What is true between the moment and the job? Is the last day inside or outside?
7. **What changed afterwards.** A rule was checked when the record was made, and then the plan, the role, the price or a setting changed: a team of 8 on a plan that now allows 5, a record owned by someone whose role was taken away, an order made at the old price. Does the code say what happens, and does it read the value of then or of now?

`priority` is `high` when a person can lose money, access or work, or the product can be left where nobody may act (no admin, no owner); `medium` when it takes an unusual case; `low` otherwise. `kind` is `conflict` when two places disagree, `product-gap` when a rule the feature states does not hold in one case, and `knowledge-gap` when the code does something in a case and you cannot tell whether that was decided or only happens.

## Flows

Gaps get `topic: "logic"`; give the run page `review: "flows"`. Every other review reads one feature and stops where it ends. What a person came to do takes several of them (sign up, set up, invite, pay, cancel), and each is written as if the one before had gone well. This review reads what lies between them.

Go one feature at a time like any review, and start at its edges: every way a person arrives (a link, a redirect, an email, a button on another screen), every way they leave, and every record it passes on. Follow each to the feature on the other side and read that code too; the page of one feature does not say what the next one expects. A gap that lies between two features is one gap that names both.

1. **What it needs first.** What must already exist for the feature to work: a team, a proven email, a payment method, a setting another feature fills in? Can a person get here without it: a new account, a link straight to the screen, an invite accepted before the profile was finished? What do they see: the way to the missing step, an empty screen, an error?
2. **What it hands on.** For each state the feature can leave a record in: which features take the record next, and does each know every one of those states? A payment made and not yet confirmed, an invite sent and not accepted, a draft. Look at the lists, the dashboards, the jobs and the emails that read the record.
3. **The ways out.** Every link, redirect, button and message that leads out of the feature: does the place exist, and does it let the person in as they arrive (not signed in, with another role, on another device, a day later)? Is there a state from which no person and no job can move the record on?
4. **Left in the middle.** A person closes the page after the second step, the link runs out, the payment is abandoned. Can they go on from where they were? Does what they left stand in their way (an email taken by an account that was never finished)? Who else sees the half-made thing?
5. **Going back.** After each step, can it be undone or cancelled? What becomes of what the later steps already did: the invites sent, the money taken, the records made for it?
6. **Waiting.** Where the next step belongs to another person or another system (an approval, an invite to accept, a payment to be confirmed, a job): what does each side see meanwhile? When it never comes, does it run out, is anyone reminded, can it be withdrawn? And when it comes late, after the request was cancelled or answered by someone else?
7. **In another order.** A person opens the third step by its address, presses Back after the last one, has the same flow open in two tabs, or does a step twice. What do they see, and what is made twice? Whether the server refuses a skipped step is the business of [a security review](#security); write a gap for one you meet, with `topic: "security"`.

`priority` is `high` when a person is left with no way on (they paid and cannot get in, they cannot finish signing up), pays for what they did not get, or loses work they had made (a recording, a draft, an upload); `medium` when there is a way round; `low` otherwise. `kind` is `product-gap` when one feature leaves a state the next does not handle, `conflict` when two features say different things about the same step, `product-plan` for a step the product has nowhere (no way to withdraw an invite), and `knowledge-gap` when you cannot tell.

## Failure paths

Gaps get `topic: "ops"`; name the run page `<date>-review-failures.md` with `review: "failures"`. For what runs on its own, what the product sends out, and every call to another service.

1. **When another service is down.** Is there a timeout? What does the person see, and is anything left half-done?
2. **Trying again.** Is a failed job or call retried, how many times, with what delay? Is it safe to run twice (an email sent twice, a charge made twice)?
3. **Giving up.** After the last attempt, where does the work go? Does anybody learn of it: a person on a screen, the team in a log or an alert?
4. **Failing quietly.** An error caught and dropped, a result nobody checks, an email or a notification that fails with no trace.
5. **Partial work.** A job over many records that stops in the middle: does the next run go on, start over, or skip what is left?
6. **Schedules.** What happens when a run is missed or two runs overlap? In which time zone is the schedule read?
7. **Limits.** A queue, a list or a folder that grows without a bound in ordinary use; a job that reads every record at once. What one caller can send too big or do too often on purpose is the business of [an abuse review](#abuse).
8. **Configuration.** A setting or key that is missing: does the product refuse to start, or run and fail later? Is there a default that is wrong for production?
9. **What the person is told.** After a failure, does the screen say what happened and what to do, or only that something went wrong?

## API

Gaps get `topic: "api"`. For what another system can call, and for the calls the product makes.

1. **Who calls it?** Search every client in the repository, the tests and the documentation. An endpoint nothing calls is a gap ("Is it still needed?"), unless the API is public for outside callers; then say where it is documented.
2. **The reverse.** A client that calls something the server does not have, sends a field the server ignores, or reads a field the server does not return.
3. **Two ways to do one thing.** An old and a new version of the same call. Which do the clients use, and is the old one marked?
4. **Marked as outdated and still used.** A procedure the code marks deprecated (a comment, an annotation, a `legacy` or `v1` name) that a client still calls, and calls to another service that the code or its SDK marks deprecated. Outdated package versions are for a tool; see "What a review is not".
5. **Input.** Does every endpoint check its input on the server? Do lists have a maximum page size?
6. **Consistency.** The same thing under two names, errors of different shape or status, dates or money in different formats between endpoints.
7. **The written contract.** An OpenAPI file, a README or types shared with clients that say something else than the code is a `conflict` gap, or a noted line when it is small.
8. **Calls out.** Is there a timeout and a retry? What does the person see when the other service is down? Is the call safe to repeat?

## UI

Gaps get `topic: "ui"`. For every screen, in every client.

1. **States.** What does a person see while it loads, when the list is empty, when the request fails, when they have no permission, when the record does not exist? A state the screen does not handle is a gap.
2. **The same thing built twice.** Go through the component folders and list each control that exists more than once: two date pickers, three confirm dialogs, two ways to show an error. Copies that look or behave differently are a gap that names the screens. Copies that look and behave the same are not a gap: name them on the run page, for whoever wants to keep one.
3. **Words.** One action or thing under different names on different screens, one refusal with different messages, text written in one language where the product is translated.
4. **Actions.** Something that cannot be undone and asks no confirmation, a button that stays active while its request runs, input lost without a warning when the person leaves.
5. **Shown and allowed.** A control shown to a person whose request the server refuses, or hidden from one the server would allow.
6. **Forms.** An error shown only as a general message when it belongs to one field. What the form and the server check differently is the business of a validation review; write a gap for one you meet, with `topic: "validation"`.
7. **Clients.** What one client has and another lacks; this also goes into "Where the apps differ" on the feature's page.
8. **Basics for everyone.** A field without a label, a button with an icon and no name, information given by colour alone. Read from the code; this is not an accessibility audit.

## Another topic

A person may name a topic that has no list here: performance, texts, privacy, "are there duplicate components". Write five to ten questions for it, show them to the person, and run the same pass with them. Give the run page the person's word as `review` (lower case, with hyphens), and the gaps the nearest of the seven `topic` values in [gaps.md](gaps.md).
