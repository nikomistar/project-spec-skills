# Reviewing one topic

A map says what the product does. A review goes through the same product again with one topic in mind (is it safe, do the form and the server check the same things, is its API in order) and a fixed list of questions, so that nothing is skipped because it looked fine. It is a separate pass that a person asks for by name. It opens every entry point in its scope again, so it costs about as much reading as the features it covers; do one topic per pass.

A review leaves three things:

- **Rules the pages were missing.** What the code answers plainly (only an admin may open this, a file may be 10 MB at most) is a numbered rule on the feature's page, like any other rule.
- **Gaps.** Each doubt is one gap with `topic` set, in the same queue as every other gap.
- **A run page** that says which features were reviewed and which were not, so the pass can be continued.

It never changes application code and never decides a gap.

## What a review is not

A review reads code. It runs no scanner, no test and no application, like every other pass of this skill.

- Known vulnerabilities in dependencies, outdated packages, secrets in the Git history and the settings of what is deployed are found by tools, not by reading. Name the tool under "Not covered" in the report (`npm audit`, `pip-audit`, `osv-scanner`, a secret scanner). Run one only when the person asks. Settings the repository holds (a storage bucket, a queue or a function declared in a file) are code, and are read.
- It is not a penetration test and not a certificate. "No gaps found" means the questions below found nothing in the code that was read. Say it that way, never "the product is secure".

## The pass

1. **Scope.** The whole product, an area, one feature, or what changed since a commit or a day ("review the security of what changed last week" takes the features the diff touches). Say which before you start.
2. **The list.** A review needs a map: [the inventory file](../SKILL.md#the-inventory-file) is its list of features and entry points. Without a vault, say so and offer a map first. A question about one feature in a repository that has no vault is an **investigate**, and it ends as a report. A feature the inventory has as `not started` is reviewed from the code alone, and the run page says its page does not exist yet.
3. **The run page.** Create `runs/<date>-review-<topic>.md` with `review: "<topic>"` and `status: "partial"`: the topic, the scope, the revision, and the features in scope as a checklist (`- [ ] Name of the feature`). Write a feature's name as plain text, or its page's path in code formatting: a run page never links to vault pages, and `check` refuses it when it does. Tick a feature when every question was asked of every one of its entry points. Save it after each feature. A later session reads this page first and goes on with the first unticked feature. The viewer and the `summary` command read this page to say which reviews were run, when, and how far each got, so keep the property, the name and the checklist as written here.
4. **One feature at a time.** Read the feature's page, then open each entry point and answer the topic's questions from the code. The page tells you where to look; it is not the evidence. Ask every question of every entry point it applies to, and do not stop at the first finding.
5. **Each answer goes to one place.**
   - The code does it, and the page does not say so: add the rule to the page, with the next free number. For security, also set [the page's `access`](format.md#properties).
   - The code does it, and the page says so: nothing to write.
   - The code does not do it, does it in one place and not in another, or you cannot tell whether it is meant: a gap.
6. **Finish.** Run `check`. Set the run page to `current` when every feature in scope is ticked. Report real counts: features reviewed out of those in scope, rules added, gaps written by priority, and "Not covered" with the tools that would cover it.

## Writing the gaps

The rules in [gaps.md](gaps.md) apply. A review adds these:

- **Look in the queue first.** A gap that already asks the question gets `topic` when it has none and a dated line in `Discussion`; it does not get a twin.
- **One doubt per page.** The same missing check in several entry points of one feature is one gap that lists them. In two features it is two gaps, because each feature has its own owner and decision.
- **The title is the question a person decides**: "Should a member be able to change another member's role by saving the profile form?", not "Broken access control in users.save".
- **`topic` is the one the list below names**, the same for every gap of the pass, so the queue can be filtered to what this review found.
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

Gaps get `topic: "security"`; give the run page `review: "abuse"`. A security review asks who may do a thing. This one asks what a person who may do it can do too much of: send something too big, do it too often, or send something that is not what it says. Read every entry point as an ordinary member with an account of their own, not as an outsider.

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

## Failure paths

Gaps get `topic: "ops"`; name the run page `<date>-review-failures.md` with `review: "failures"`. For what runs on its own, what the product sends out, and every call to another service.

1. **When another service is down.** Is there a timeout? What does the person see, and is anything left half-done?
2. **Trying again.** Is a failed job or call retried, how many times, with what delay? Is it safe to run twice (an email sent twice, a charge made twice)?
3. **Giving up.** After the last attempt, where does the work go? Does anybody learn of it: a person on a screen, the team in a log or an alert?
4. **Failing quietly.** An error caught and dropped, a result nobody checks, an email or a notification that fails with no trace.
5. **Partial work.** A job over many records that stops in the middle: does the next run go on, start over, or skip what is left?
6. **Schedules.** What happens when a run is missed or two runs overlap? In which time zone is the schedule read?
7. **Limits.** A queue, a list or an upload that can grow without a bound; a job that reads every record at once.
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
7. **The written contract.** An OpenAPI file, a README or types shared with clients that say something else than the code is a `conflict` gap.
8. **Calls out.** Is there a timeout and a retry? What does the person see when the other service is down? Is the call safe to repeat?

## UI

Gaps get `topic: "ui"`. For every screen, in every client.

1. **States.** What does a person see while it loads, when the list is empty, when the request fails, when they have no permission, when the record does not exist? A state the screen does not handle is a gap.
2. **The same thing built twice.** Go through the component folders and list each control that exists more than once: two date pickers, three confirm dialogs, two ways to show an error. Copies that look or behave differently are a gap that names the screens. Copies that are the same are one `low` gap per control, as a proposal to keep one.
3. **Words.** One action or thing under different names on different screens, one refusal with different messages, text written in one language where the product is translated.
4. **Actions.** Something that cannot be undone and asks no confirmation, a button that stays active while its request runs, input lost without a warning when the person leaves.
5. **Shown and allowed.** A control shown to a person whose request the server refuses, or hidden from one the server would allow.
6. **Forms.** An error shown only as a general message when it belongs to one field. What the form and the server check differently is the business of a validation review; write a gap for one you meet, with `topic: "validation"`.
7. **Clients.** What one client has and another lacks; this also goes into "Where the apps differ" on the feature's page.
8. **Basics for everyone.** A field without a label, a button with an icon and no name, information given by colour alone. Read from the code; this is not an accessibility audit.

## Another topic

A person may name a topic that has no list here: performance, texts, privacy, "are there duplicate components". Write five to ten questions for it, show them to the person, and run the same pass with them. Give the run page the person's word as `review` (lower case, with hyphens), and the gaps the nearest of the seven `topic` values in [gaps.md](gaps.md).
