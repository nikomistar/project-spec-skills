#!/usr/bin/env node
// project-spec: one command for the viewer and for keeping the skill copies current.
// No dependencies. The skills themselves are Python and Markdown; this only starts them and copies them.
import { spawnSync } from 'node:child_process';
import { createHash } from 'node:crypto';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const SKILLS = path.join(ROOT, 'skills');
// The viewer is not part of a skill: a skill holds only what writing a spec needs. It lives in the package, and a
// copy of the skill gets it only when asked (--with-viewer) or when it already had one.
const VIEWER = path.join(ROOT, 'viewer', 'viewer.html');
const VIEWER_SKILL = 'project-knowledge';
const VIEWER_REL = 'assets/viewer.html';
const PACKAGE = JSON.parse(fs.readFileSync(path.join(ROOT, 'package.json'), 'utf8'));
const MARKER = '.project-spec.json'; // written into every copy: which version it is and what its files looked like
const SKIP = new Set(['__pycache__', '.DS_Store', MARKER]);
const KNOWLEDGE = new Set(['serve', 'build', 'check', 'snapshot', 'move', 'summary', 'gaps']);
const MAINTAIN = new Set(['scan', 'receipt', 'finish']);
const COVERAGE = 'coverage'; // its own helper, which takes no command word
// Skills earlier versions shipped; project-knowledge took over what they did. spec-change (changing the product from
// an edited spec) was dropped: its planning guide is part of project-knowledge, and the spec is kept current by the
// agent that changes the code (see `project-spec instructions`).
const RETIRED = ['spec-audit', 'spec-change', 'spec-investigation', 'spec-plan'];
// Folders inside a project where a copy of the skills may live.
const PROJECT_PLACES = ['knowledge/tooling', '.claude/skills', '.codex/skills', '.agents/skills'];

const USAGE = `project-spec ${PACKAGE.version}

Read the spec
  project-spec serve [--repo DIR] [--vault DIR] [--port N] [--no-open]
      Open the viewer for the repository (default: the current folder).
  project-spec build --out FILE [--source-url URL] [--with-sources] [--allow-missing-sources]
      Write the viewer as one HTML file, to show the spec on a server.
  project-spec summary
      Where the spec stands: how much of the map is finished, the gaps by state and topic, each review and when it ran.
  project-spec gaps [--state open|closed|all|STATE] [--topic T] [--priority P] [--area ID] [--review R]
      List gaps, the most urgent first, each with its file.
  project-spec check | snapshot [options]
      The knowledge helper; --repo defaults to the current folder.
  project-spec move --to DIR
      Move the spec to another folder of the repository; links from its pages to your files are repointed.
  project-spec coverage [--path FOLDER]... [--all]
      What the code has that no spec page mentions yet: folders, messages and limits.
  project-spec scan | receipt | finish [options]
      The sync helper; --repo defaults to the current folder.

Keep the skills current
  project-spec status
      Where copies of the skills are and whether they match this version (for the spec itself: summary).
  project-spec install [--claude] [--codex] [--dir DIR]... [--skills a,b] [--with-viewer | --no-viewer] [--force]
      Copy the skills into ~/.claude/skills, ~/.codex/skills or a folder you name.
      A copy holds the instructions and the helpers. --with-viewer adds the viewer page to it, for a
      place without Node; --no-viewer takes it out of a copy that has it.
  project-spec update [--force]
      Refresh every copy that status lists and remove retired skills. Nothing new is added.

A copy you edited by hand is never replaced unless you pass --force; the old files
are kept under ~/.project-spec/backups first.

Keep the spec current
  project-spec instructions [--file FILE]... [--vault DIR] [--remove]
      A short block for AGENTS.md, CLAUDE.md and the like. It asks whoever changes the code to
      correct the spec in the same task, as an edit the size of the change. Printed, or written
      into each FILE you name; run again, it replaces the block and leaves the rest of the file.`;

class Problem extends Error {}

function commit() {
  if (typeof PACKAGE.gitHead === 'string') return PACKAGE.gitHead;
  const git = spawnSync('git', ['-C', ROOT, 'rev-parse', 'HEAD'], { encoding: 'utf8' });
  // Only when this folder is itself the work tree, not a package sitting inside someone's repository.
  const top = spawnSync('git', ['-C', ROOT, 'rev-parse', '--show-toplevel'], { encoding: 'utf8' });
  return git.status === 0 && top.status === 0 && fs.realpathSync(top.stdout.trim()) === fs.realpathSync(ROOT) ? git.stdout.trim() : '';
}

const skillNames = () =>
  fs.readdirSync(SKILLS, { withFileTypes: true })
    .filter(e => e.isDirectory() && fs.existsSync(path.join(SKILLS, e.name, 'SKILL.md')))
    .map(e => e.name)
    .sort();

const sha = file => createHash('sha256').update(fs.readFileSync(file)).digest('hex');
const hasViewer = dir => fs.existsSync(path.join(dir, VIEWER_REL));
// The files a copy of a skill should have: the skill's own, and the viewer when this copy carries it.
function freshFiles(name, viewer) {
  const fresh = filesOf(path.join(SKILLS, name));
  if (viewer && name === VIEWER_SKILL) fresh[VIEWER_REL] = sha(VIEWER);
  return fresh;
}

function filesOf(dir, base = dir, out = {}) {
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    if (SKIP.has(entry.name) || entry.name.endsWith('.pyc')) continue;
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) filesOf(full, base, out);
    else if (entry.isFile()) out[path.relative(base, full).split(path.sep).join('/')] = createHash('sha256').update(fs.readFileSync(full)).digest('hex');
  }
  return out;
}

function readMarker(dir) {
  try {
    const marker = JSON.parse(fs.readFileSync(path.join(dir, MARKER), 'utf8'));
    return marker && typeof marker === 'object' && marker.files && typeof marker.files === 'object' ? marker : null;
  } catch {
    return null;
  }
}

// What a copy is, compared with this package: current, older, modified by hand, unknown, or absent.
// `viewer` says whether the copy should carry the viewer; left out, a copy keeps what it has.
function inspect(dir, name, viewer = hasViewer(dir)) {
  if (!fs.existsSync(path.join(dir, 'SKILL.md'))) return { state: 'absent' };
  const fresh = freshFiles(name, viewer);
  const now = filesOf(dir);
  const same = (a, b) => Object.keys(a).length === Object.keys(b).length && Object.keys(a).every(k => a[k] === b[k]);
  const marker = readMarker(dir);
  if (!marker) return same(now, fresh) ? { state: 'current', adopt: true } : { state: 'unknown' };
  const edited = Object.keys(marker.files).filter(f => now[f] !== undefined && now[f] !== marker.files[f]).sort();
  if (edited.length) return { state: 'modified', edited, version: marker.version };
  const tracked = Object.fromEntries(Object.keys(marker.files).filter(f => now[f] !== undefined).map(f => [f, now[f]]));
  return same(tracked, fresh) ? { state: 'current', version: marker.version } : { state: 'older', version: marker.version };
}

const STATE_TEXT = {
  current: () => 'current',
  older: i => `older (${i.version || 'unknown version'})`,
  modified: i => `edited by hand: ${i.edited.join(', ')}`,
  unknown: () => 'differs, no version recorded',
  absent: () => 'not installed',
};

function backup(dir, name) {
  const stamp = new Date().toISOString().replace(/[-:]/g, '').replace(/\..*/, '');
  let target = path.join(os.homedir(), '.project-spec', 'backups', stamp, name);
  for (let n = 2; fs.existsSync(target); n++) target = path.join(os.homedir(), '.project-spec', 'backups', `${stamp}-${n}`, name);
  fs.mkdirSync(path.dirname(target), { recursive: true });
  fs.cpSync(dir, target, { recursive: true });
  return target;
}

// Copies one skill into place. Files an earlier install put there and this version no longer has are removed;
// files nobody recorded (yours) are left alone.
function place(dir, name, viewer) {
  const source = path.join(SKILLS, name);
  const fresh = freshFiles(name, viewer);
  const marker = readMarker(dir);
  for (const old of Object.keys(marker ? marker.files : {})) {
    if (fresh[old] === undefined) fs.rmSync(path.join(dir, old), { force: true });
  }
  if (name === VIEWER_SKILL && !viewer) {
    fs.rmSync(path.join(dir, VIEWER_REL), { force: true });
    try {
      fs.rmdirSync(path.dirname(path.join(dir, VIEWER_REL))); // only when nothing else is in it
    } catch {}
  }
  for (const rel of Object.keys(fresh)) {
    const to = path.join(dir, rel);
    fs.mkdirSync(path.dirname(to), { recursive: true });
    fs.copyFileSync(rel === VIEWER_REL && name === VIEWER_SKILL ? VIEWER : path.join(source, rel), to);
  }
  fs.writeFileSync(path.join(dir, MARKER), JSON.stringify({ package: PACKAGE.name, version: PACKAGE.version, commit: commit(), files: fresh }, null, 2) + '\n');
}

// `viewer`: true adds the viewer to the copy, false takes it out, undefined keeps what the copy has (none when new).
function apply(root, name, force, lines, viewer) {
  const dir = path.join(root, name);
  const carries = name === VIEWER_SKILL && (viewer === undefined ? hasViewer(dir) : viewer);
  const found = inspect(dir, name, carries);
  const label = `${shorten(dir)}`;
  if (found.state === 'current' && !found.adopt) return lines.push(`  ${label}: already current`);
  if (found.state === 'modified' && !force) {
    lines.push(`  ${label}: NOT updated, edited by hand (${found.edited.join(', ')}); pass --force to replace it`);
    return false;
  }
  let kept = '';
  if (found.state === 'modified' || found.state === 'unknown') kept = `; the old copy is in ${shorten(backup(dir, name))}`;
  place(dir, name, carries);
  lines.push(`  ${label}: ${found.state === 'absent' ? 'installed' : found.adopt ? 'recorded as current' : 'updated'} to ${PACKAGE.version}${carries ? ', with the viewer' : ''}${kept}`);
}

const shorten = p => (p.startsWith(os.homedir() + path.sep) ? '~' + p.slice(os.homedir().length) : p);
const homes = () => [path.join(os.homedir(), '.claude', 'skills'), path.join(os.homedir(), '.codex', 'skills')];

// Every folder that holds at least one of the skills: the two home folders and the usual places in this project.
function knownRoots() {
  const roots = [...homes(), ...PROJECT_PLACES.map(p => path.resolve(p))];
  const names = [...skillNames(), ...RETIRED];
  return [...new Set(roots)].filter(root => names.some(name => fs.existsSync(path.join(root, name, 'SKILL.md'))));
}

// A retired skill is recognised by its folder name and by the name its SKILL.md declares.
function retiredIn(root) {
  return RETIRED.filter(name => {
    try {
      return new RegExp(`^name:\\s*${name}\\s*$`, 'm').test(fs.readFileSync(path.join(root, name, 'SKILL.md'), 'utf8'));
    } catch {
      return false;
    }
  });
}

function take(args, flag) {
  const out = [];
  for (let i = args.indexOf(flag); i >= 0; i = args.indexOf(flag)) {
    if (args[i + 1] === undefined || args[i + 1].startsWith('--')) throw new Problem(`${flag} needs a value`);
    out.push(args[i + 1]);
    args.splice(i, 2);
  }
  return out;
}
function flag(args, name) {
  const i = args.indexOf(name);
  if (i >= 0) args.splice(i, 1);
  return i >= 0;
}
function done(args) {
  if (args.length) throw new Problem(`unknown option: ${args[0]}`);
}

function status(args) {
  done(args);
  const names = skillNames();
  const roots = knownRoots();
  console.log(`project-spec ${PACKAGE.version}${commit() ? ' (' + commit().slice(0, 7) + ')' : ''}`);
  if (!roots.length) return console.log('No copies found. Install with: project-spec install --claude (or --codex, or --dir DIR)');
  let behind = 0;
  for (const root of roots) {
    console.log(`\n${shorten(root)}`);
    for (const name of names) {
      const found = inspect(path.join(root, name), name);
      if (found.state !== 'current' && found.state !== 'absent') behind++;
      console.log(`  ${name}: ${STATE_TEXT[found.state](found)}${name === VIEWER_SKILL && hasViewer(path.join(root, name)) ? ', with the viewer' : ''}`);
    }
    for (const name of retiredIn(root)) {
      behind++;
      console.log(`  ${name}: retired, update removes it`);
    }
  }
  console.log(behind ? `\n${behind} to refresh: project-spec update` : '\nEverything installed is current.');
}

function install(args) {
  const force = flag(args, '--force');
  const roots = [];
  if (flag(args, '--claude')) roots.push(homes()[0]);
  if (flag(args, '--codex')) roots.push(homes()[1]);
  roots.push(...take(args, '--dir').map(d => path.resolve(d)));
  const only = take(args, '--skills').flatMap(v => v.split(',')).map(v => v.trim()).filter(Boolean);
  const withViewer = flag(args, '--with-viewer');
  const noViewer = flag(args, '--no-viewer');
  done(args);
  if (withViewer && noViewer) throw new Problem('--with-viewer and --no-viewer cannot be used together');
  const viewer = withViewer ? true : noViewer ? false : undefined;
  if (!roots.length) throw new Problem('say where to install: --claude, --codex or --dir DIR');
  const names = skillNames();
  const unknown = only.filter(n => !names.includes(n));
  if (unknown.length) throw new Problem(`no such skill: ${unknown.join(', ')} (there are: ${names.join(', ')})`);
  let ok = true;
  for (const root of roots) {
    const lines = [];
    for (const name of only.length ? only : names) if (apply(root, name, force, lines, viewer) === false) ok = false;
    console.log(lines.join('\n'));
  }
  return ok ? 0 : 1;
}

function update(args) {
  const force = flag(args, '--force');
  done(args);
  const roots = knownRoots();
  if (!roots.length) throw new Problem('no copies found to update; install first: project-spec install --claude (or --codex, or --dir DIR)');
  let ok = true;
  for (const root of roots) {
    const lines = [];
    for (const name of skillNames()) {
      if (fs.existsSync(path.join(root, name, 'SKILL.md')) && apply(root, name, force, lines) === false) ok = false;
    }
    for (const name of retiredIn(root)) {
      const dir = path.join(root, name);
      const kept = backup(dir, name);
      fs.rmSync(dir, { recursive: true, force: true });
      lines.push(`  ${shorten(dir)}: removed, this skill is retired; the old copy is in ${shorten(kept)}`);
    }
    console.log(lines.join('\n'));
  }
  const missing = roots.flatMap(root => skillNames().filter(name => !fs.existsSync(path.join(root, name, 'SKILL.md'))).map(name => `${shorten(root)}/${name}`));
  if (missing.length) console.log(`\nNot installed there, so left out: ${missing.join(', ')}`);
  return ok ? 0 : 1;
}

// The block lives in the skill, so an agent without this command can copy it by hand.
const BLOCK_FILE = path.join(SKILLS, 'project-knowledge', 'references', 'agents.md');
const BLOCK_START = '<!-- project-spec:start -->';
const BLOCK_END = '<!-- project-spec:end -->';

// As the helpers do: the one folder that holds 00-index.md, at most three folders deep, outside hidden folders,
// dependencies and build output.
const NOT_A_VAULT_PLACE = new Set(['node_modules', 'vendor', 'dist', 'build', 'out', 'target', 'coverage', '__pycache__', 'venv', 'Pods']);
function findVault(repo) {
  const found = [];
  const look = (folder, depth) => {
    let entries = [];
    try {
      entries = fs.readdirSync(folder, { withFileTypes: true }).filter(e => e.isDirectory() && !e.name.startsWith('.') && !NOT_A_VAULT_PLACE.has(e.name));
    } catch {
      return;
    }
    for (const entry of entries.sort((x, y) => (x.name < y.name ? -1 : 1))) {
      const dir = path.join(folder, entry.name);
      if (fs.existsSync(path.join(dir, '00-index.md'))) found.push(dir);
      else if (depth < 3) look(dir, depth + 1);
    }
  };
  look(repo, 1);
  if (found.length !== 1) {
    throw new Problem(`${found.length ? 'several vaults found (' + found.map(f => path.relative(repo, f)).join(', ') + ')' : 'no vault found: no folder with 00-index.md up to three folders deep'}; name the vault with --vault DIR`);
  }
  return found[0];
}

function instructions(args) {
  const repo = path.resolve(take(args, '--repo').pop() || '.');
  const named = take(args, '--vault').pop();
  const files = take(args, '--file');
  const remove = flag(args, '--remove');
  done(args);
  if (remove && !files.length) throw new Problem('--remove needs --file FILE');
  let block = '';
  if (!remove) {
    const text = fs.readFileSync(BLOCK_FILE, 'utf8');
    const from = text.indexOf(BLOCK_START);
    const to = text.indexOf(BLOCK_END);
    const vault = named ? path.resolve(named) : findVault(repo);
    if (!fs.existsSync(path.join(vault, '00-index.md'))) throw new Problem(`${vault} is not a vault: it has no 00-index.md`);
    const rel = path.relative(repo, vault).split(path.sep).join('/');
    if (!rel || rel.startsWith('..')) throw new Problem('the vault must be a folder inside the repository');
    block = text.slice(from, to + BLOCK_END.length).replaceAll('{vault}', rel);
  }
  if (!files.length) return console.log(block), 0;
  for (const name of files) {
    const file = path.resolve(name);
    const before = fs.existsSync(file) ? fs.readFileSync(file, 'utf8') : null;
    const from = before === null ? -1 : before.indexOf(BLOCK_START);
    const to = before === null ? -1 : before.indexOf(BLOCK_END);
    const has = from >= 0 && to > from;
    let after = before;
    let what;
    if (remove) {
      if (!has) what = 'no project-spec block there';
      else {
        const head = before.slice(0, from).replace(/\s+$/, '');
        const tail = before.slice(to + BLOCK_END.length).trim();
        after = [head, tail].filter(Boolean).join('\n\n') + (head || tail ? '\n' : '');
        what = after ? 'block removed' : 'removed (the file held nothing else)';
      }
    } else if (before === null) {
      // A Cursor rule file needs its own header to be applied in every session.
      after = (file.endsWith('.mdc') ? '---\ndescription: Keep the project spec current\nalwaysApply: true\n---\n\n' : '') + block + '\n';
      what = 'written';
    } else if (has) {
      after = before.slice(0, from) + block + before.slice(to + BLOCK_END.length);
      what = after === before ? 'already current' : 'block updated';
    } else {
      after = before.replace(/\s*$/, '') + (before.trim() ? '\n\n' : '') + block + '\n';
      what = 'block added';
    }
    if (after !== before) {
      if (after) {
        fs.mkdirSync(path.dirname(file), { recursive: true });
        fs.writeFileSync(file, after);
      } else fs.rmSync(file);
    }
    console.log(`  ${path.relative(process.cwd(), file) || file}: ${what}`);
  }
  return 0;
}

function python(script, command, args) {
  if (!args.includes('--repo')) args.push('--repo', '.');
  if (command === 'serve') {
    if (!flag(args, '--no-open') && !args.includes('--open')) args.push('--open');
  }
  const exe = process.env.PROJECT_SPEC_PYTHON || (process.platform === 'win32' ? 'python' : 'python3');
  const full = [path.join(SKILLS, 'project-knowledge', 'scripts', script), ...(command === COVERAGE ? [] : [command]), ...args];
  if (process.env.PROJECT_SPEC_DRY_RUN) return console.log([exe, ...full].join(' ')), 0;
  const run = spawnSync(exe, full, { stdio: 'inherit' });
  if (run.error) throw new Problem(`could not start ${exe}: ${run.error.message}. The helpers need Python 3.10 or newer; set PROJECT_SPEC_PYTHON to its path.`);
  return run.status === null ? 1 : run.status;
}

function main(argv) {
  const [command, ...args] = argv;
  if (!command || command === 'help' || command === '--help' || command === '-h') return console.log(USAGE), 0;
  if (command === 'version' || command === '--version') return console.log(PACKAGE.version), 0;
  if (command === 'status') return status(args) || 0;
  if (command === 'install') return install(args);
  if (command === 'update') return update(args);
  if (command === 'instructions') return instructions(args);
  if (KNOWLEDGE.has(command)) return python('knowledge.py', command, args);
  if (MAINTAIN.has(command)) return python('maintain.py', command, args);
  if (command === COVERAGE) return python('coverage.py', command, args);
  throw new Problem(`unknown command: ${command}\n\n${USAGE}`);
}

try {
  process.exitCode = main(process.argv.slice(2));
} catch (error) {
  if (!(error instanceof Problem)) throw error;
  console.error(`project-spec: ${error.message}`);
  process.exitCode = 2;
}
