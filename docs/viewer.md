# The viewer

The vault is plain Markdown: easy for an agent to write, tiring for a person to read file by file. The viewer is the reading side. It is one local page that reads the vault from disk every time it loads, so there is nothing to build first.

It is made for one loop:

1. **Read.** The first page shows the areas and, under them, what was checked: how much of the map is finished, and each review (security, abuse, validation, data, logic, flows, API, UI, failure paths) with the day it was last run or "Not run yet" and the request to copy. A tree lists the areas and the features in each. A feature page says in plain words what the feature is for and how it works, then lists its fields and its numbered business rules; when the page states who may use the feature, "Access: admin" is shown under the title; the source files and the properties are folded away. A breadcrumb, Back and Forward and a "You are here" card say where you are, and the related pages are listed beside the text.
2. **Find.** Search (Cmd/Ctrl+K) covers pages, gaps and the text of the files the pages cite. A rule number such as `BR-CANCEL-02` finds its page.
3. **Ask.** "Copy for AI" on any page turns the page and your own words into a request for your agent that names the page file. For a gap: recheck it, record a check you did yourself, record your decision, lay out the options, plan it. For any page: change the behavior, ask a question, or remove a page that is only noise. For a feature or an area: review it for one topic (security, validation, data, API, UI or failure paths). Each choice says what will happen, and you see the exact text before you copy it.
4. **Let the agent work.** Paste the brief into your agent. For a change of behavior it makes the change you described, and then corrects the page so it says what the code does now.
5. **Decide.** The gap queue lists the open questions, the most urgent first and forty at a time. The states are tabs (Open, Needs recheck, Needs decision, History); under them are a field that finds gaps by the words in them, the filters for area, kind, topic (security, validation, data, logic, UI, API, operations) and priority, and the order: the most urgent first, or the newest first, by the day each gap appeared. A closed question (done, rejected or a duplicate) leaves the queue: it is under **History**, and on its feature's page under "Closed questions", so the reason behind a rule stays one press away.
6. **See what moved.** Recent changes lists the pages whose cited sources changed since the last review, the pages not committed yet, and the vault's Git history with what each summary said before and after.

| Search | Copy for AI |
| --- | --- |
| ![Search results grouped into features, gaps and files](images/viewer-search.png) | ![The Copy for AI dialog with the exact text that will be copied](images/viewer-copy.png) |
| **Recent changes** | **Gap queue** |
| ![The vault's Git history, one line per commit](images/viewer-changes.png) | ![The gap queue filtered by state, kind and area, the most urgent first](images/viewer-gaps.png) |

![The map of pages, one frame per area](images/viewer-map.png)

The screenshots show the fictional [Parcel Desk](../examples/parcel-desk/README.md) example. The viewer only reads: it listens on `127.0.0.1`, makes no network requests and writes nothing to the repository. "Copy for AI" puts text on your clipboard; the only thing it keeps in your browser is the name you sign a check or a decision with. A link to a file in the repository opens inside the viewer, Markdown rendered and code with the cited lines marked.

## Open it with one command

With the [package](install.md#with-npm) installed in your project, add a script to `package.json`:

```json
{
  "scripts": {
    "spec": "project-spec serve"
  }
}
```

`npm run spec` then opens the viewer for that project; without adding the package, `npx project-spec serve` does the same.

The viewer is part of the package, not of the skill: a copy of the skill holds the instructions and the helpers that write and check a spec, and no page. Where there is no Node, add the page to a copy with `npx project-spec install --dir <folder> --with-viewer` from a machine that has it (or work from a clone of this repository), and the command is the helper itself, where `<skill>` is the `project-knowledge` folder:

```sh
python3 <skill>/scripts/knowledge.py serve --repo . --open
```

Give that a short name once, as a `Makefile` target (the second line starts with a tab) or a shell alias:

```make
spec:
	python3 <skill>/scripts/knowledge.py serve --repo . --open
```

```sh
alias spec='python3 ~/.claude/skills/project-knowledge/scripts/knowledge.py serve --open --repo'
```

The spec is found by itself when the repository has one (a folder with `00-index.md`, up to three folders deep); with several, add `--vault PATH`. The page is served on port 8757, or another free port when that one is taken; `--port N` picks one. `project-spec serve` opens the browser unless you add `--no-open`; the helper opens it only with `--open`. If the vault has errors, the spec is shown all the same: the first page says how many there are, and Recent changes lists every one of them by page, with a request for an agent that names them all. A page that could not be read at all is listed there as not shown.

## Without the viewer

The vault is the product; the viewer is one way to read it. Three others:

- **Obsidian.** Choose **Open folder as vault** and pick the vault folder. Links, properties, search and the graph work as they are ([details](workflows.md)). It has no gap queue by state and priority, no "Copy for AI" and no mark on a page whose code changed.
- **Your agent.** Ask it in words: "list the gaps that wait for my decision", "recheck the high-priority gaps", "what does the spec say about cancelling an order". The `project-knowledge` skill has a mode for each.
- **A page of your own.** `project-spec serve --viewer FILE` and `build --viewer FILE` show the vault with any HTML file that contains `__KNOWLEDGE_DATA__` once; the helper puts the pages, links and gap states there as JSON ([the data contract](../skills/project-knowledge/references/format.md)).

## Show it on a server

`serve` is for your own machine. To let the rest of the team read the spec on a development or staging server, write the viewer as one file and let your application return it:

```sh
project-spec build --out build/spec.html \
  --source-url 'https://github.com/OWNER/REPO/blob/{commit}'
```

In a copy of the skill that has the viewer (`install --with-viewer`), the same command is `python3 <skill>/scripts/knowledge.py build --repo . --out build/spec.html`. The file is the whole viewer: the pages, the search, the map, the gap queue and the history, with no other files and no network requests. It is a copy of the vault at the moment of the build, so build it again on every deploy.

| Option | What it does |
| --- | --- |
| `--out FILE` | Where to write the page. It must be outside the vault: nothing is generated into the vault. |
| `--source-url URL` | Where a cited file can be read. The file's path in the repository is added to this address, and `{commit}` becomes the commit the page was built from. Without it, cited files are shown as names. |
| `--with-sources` | Put the text of the cited files into the page, as `serve` does, so they open inside the viewer. Leave it out when people who may not read the repository can open the page. |
| `--allow-missing-sources` | Do not stop when a cited file is not there. For a build that sees only part of the repository, such as a Docker build whose `.dockerignore` leaves files out. The command lists the files it did not find. |

The spec describes how the product works inside, and with `--with-sources` it carries source code. So treat the file like the repository:

- Keep it out of folders the web server publishes by itself (`public/`, `static/`). Return it from a route that checks who is asking.
- Build it only for the environments that should have it, and make the route answer 404 everywhere else.
- If your application sets a `Content-Security-Policy`, the page needs inline scripts and styles and nothing else.

For example, a route in a Next.js application (a sketch: put your own sign-in check where `signedIn()` is):

```ts
// src/app/development/spec/route.ts
import { readFile } from "node:fs/promises";
import path from "node:path";

export const dynamic = "force-dynamic";

export async function GET() {
  if (process.env.SPEC_PAGE !== "on" || !(await signedIn())) {
    return new Response("Not found", { status: 404 });
  }
  const page = await readFile(path.join(process.cwd(), "build/spec.html"));
  return new Response(page, {
    headers: {
      "Content-Type": "text/html; charset=utf-8",
      "Cache-Control": "no-store",
      "X-Robots-Tag": "noindex",
      "Content-Security-Policy":
        "default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'",
    },
  });
}
```

The build needs Python, so run it where the application is built (a CI job or a build stage), not inside a running container that has none. Without Git, or without the `.git` folder (a Docker build usually leaves it out), the page is built all the same, with an empty history and no commit to put into `{commit}`. The **Recent changes** page comes from the Git history: in a shallow clone it starts at the first commit that was fetched in full, and the command says so. In GitHub Actions, `fetch-depth: 0` on the checkout step gives it the whole history.
