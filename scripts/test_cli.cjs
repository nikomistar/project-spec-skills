// Checks for the project-spec command; run with Node, no dependencies.
// Everything happens under a temporary HOME and a temporary project folder.
const assert = require('node:assert/strict');
const { spawnSync } = require('node:child_process');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');

const ROOT = path.join(__dirname, '..');
const CLI = path.join(ROOT, 'bin/project-spec.mjs');
const VERSION = JSON.parse(fs.readFileSync(path.join(ROOT, 'package.json'), 'utf8')).version;
const temp = fs.realpathSync(fs.mkdtempSync(path.join(os.tmpdir(), 'project-spec-cli-')));
const home = path.join(temp, 'home');
const project = path.join(temp, 'project');
fs.mkdirSync(home);
fs.mkdirSync(project);

function run(args, { cwd = project, env = {} } = {}) {
  const result = spawnSync(process.execPath, [CLI, ...args], { cwd, encoding: 'utf8', env: { ...process.env, HOME: home, USERPROFILE: home, ...env } });
  return { code: result.status, out: result.stdout, err: result.stderr };
}
const skills = fs.readdirSync(path.join(ROOT, 'skills')).filter(n => fs.existsSync(path.join(ROOT, 'skills', n, 'SKILL.md'))).sort();
const claude = path.join(home, '.claude/skills');
const codex = path.join(home, '.codex/skills');
const tooling = path.join(project, 'knowledge/tooling');
const read = file => fs.readFileSync(file, 'utf8');

try {
  assert.deepEqual(skills, ['project-knowledge']);
  assert.equal(run(['version']).out.trim(), VERSION);
  assert.ok(run([]).out.includes('project-spec install'));
  assert.equal(run(['nonsense']).code, 2);

  // nothing installed yet
  assert.ok(run(['status']).out.includes('No copies found.'));
  assert.equal(run(['update']).code, 2);
  assert.equal(run(['install']).code, 2, 'install does not guess where');
  assert.ok(run(['install', '--skills', 'nope', '--claude']).err.includes('no such skill: nope'));

  // install for one agent, and into the project
  let r = run(['install', '--claude']);
  assert.equal(r.code, 0, r.err);
  assert.equal((r.out.match(/installed to/g) || []).length, 1);
  for (const name of skills) assert.ok(fs.existsSync(path.join(claude, name, 'SKILL.md')), name);
  assert.equal(read(path.join(claude, 'project-knowledge/scripts/knowledge.py')), read(path.join(ROOT, 'skills/project-knowledge/scripts/knowledge.py')));
  assert.ok(!fs.existsSync(path.join(claude, 'project-knowledge/scripts/__pycache__')));
  // a copy holds what writing a spec needs: the instructions and the helpers, no viewer page and no tests
  assert.ok(!fs.existsSync(path.join(claude, 'project-knowledge/assets')));
  assert.deepEqual(fs.readdirSync(path.join(claude, 'project-knowledge/scripts')).sort(), ['coverage.py', 'knowledge.py', 'maintain.py', 'merge.py']);
  const marker = JSON.parse(read(path.join(claude, 'project-knowledge/.project-spec.json')));
  assert.equal(marker.version, VERSION);
  assert.ok(['LICENSE', 'SKILL.md', 'agents/openai.yaml', 'references/gaps.md', 'references/plan.md', 'scripts/knowledge.py'].every(f => marker.files[f]), Object.keys(marker.files).join());
  r = run(['install', '--dir', 'knowledge/tooling', '--skills', 'project-knowledge']);
  assert.equal(r.code, 0, r.err);
  assert.deepEqual(fs.readdirSync(tooling), ['project-knowledge']);

  // status sees the home copy and the project copy
  r = run(['status']);
  assert.ok(r.out.includes('~/.claude/skills') && r.out.includes(tooling), r.out);
  assert.ok(!r.out.includes('.codex'));
  assert.ok(r.out.includes('Everything installed is current.'));
  assert.ok(/knowledge\/tooling\n  project-knowledge: current\n/.test(r.out), r.out);
  assert.ok(run(['install', '--claude']).out.includes('already current'));

  // an older copy is refreshed; a file this version dropped is removed, a file of yours is kept
  const mine = path.join(claude, 'project-knowledge');
  const old = JSON.parse(read(path.join(mine, '.project-spec.json')));
  const sha = value => require('node:crypto').createHash('sha256').update(value).digest('hex');
  fs.writeFileSync(path.join(mine, 'retired.md'), 'old');
  fs.writeFileSync(path.join(mine, 'mine.md'), 'keep me');
  fs.writeFileSync(path.join(mine, 'SKILL.md'), 'older text');
  old.version = '0.1.0';
  old.files['retired.md'] = sha('old');
  old.files['SKILL.md'] = sha('older text');
  fs.writeFileSync(path.join(mine, '.project-spec.json'), JSON.stringify(old));
  assert.ok(run(['status']).out.includes('project-knowledge: older (0.1.0)'));
  assert.ok(run(['status']).out.includes('1 to refresh: project-spec update'));
  r = run(['update']);
  assert.equal(r.code, 0, r.out + r.err);
  assert.ok(r.out.includes(`~/.claude/skills/project-knowledge: updated to ${VERSION}`), r.out);
  assert.ok(!fs.existsSync(path.join(mine, 'retired.md')));
  assert.equal(read(path.join(mine, 'mine.md')), 'keep me');
  assert.equal(read(path.join(mine, 'SKILL.md')), read(path.join(ROOT, 'skills/project-knowledge/SKILL.md')));
  assert.ok(run(['status']).out.includes('Everything installed is current.'));

  // a copy edited by hand is not replaced, unless forced, and then the old files are kept
  fs.appendFileSync(path.join(tooling, 'project-knowledge/SKILL.md'), '\nmy note\n');
  assert.ok(run(['status']).out.includes('project-knowledge: edited by hand: SKILL.md'));
  r = run(['update']);
  assert.equal(r.code, 1);
  assert.ok(r.out.includes('NOT updated, edited by hand (SKILL.md); pass --force'));
  assert.ok(read(path.join(tooling, 'project-knowledge/SKILL.md')).endsWith('my note\n'));
  r = run(['update', '--force']);
  assert.equal(r.code, 0, r.out + r.err);
  const kept = /the old copy is in (~\/\.project-spec\/backups\/\S+)/.exec(r.out);
  assert.ok(kept, r.out);
  assert.ok(read(path.join(home, kept[1].slice(2), 'SKILL.md')).endsWith('my note\n'));
  assert.equal(read(path.join(tooling, 'project-knowledge/SKILL.md')), read(path.join(ROOT, 'skills/project-knowledge/SKILL.md')));

  // copies made by hand before this command existed: adopted when identical, backed up when not;
  // a skill this version no longer has (spec-change among them) is removed, with its files kept
  const byHand = path.join(project, '.claude/skills');
  fs.cpSync(path.join(ROOT, 'skills/project-knowledge'), path.join(codex, 'project-knowledge'), { recursive: true });
  fs.cpSync(path.join(ROOT, 'skills/project-knowledge'), path.join(byHand, 'project-knowledge'), { recursive: true });
  fs.writeFileSync(path.join(byHand, 'project-knowledge/SKILL.md'), 'something older');
  for (const [folder, name] of [['spec-audit', 'spec-audit'], ['spec-change', 'spec-change'], ['spec-plan', 'spec-plan'], ['spec-investigation', 'somebody-elses-skill']]) {
    fs.mkdirSync(path.join(codex, folder), { recursive: true });
    fs.writeFileSync(path.join(codex, folder, 'SKILL.md'), `---\nname: ${name}\ndescription: old\n---\n\nold skill\n`);
  }
  r = run(['status']);
  assert.ok(/\.codex\/skills\n  project-knowledge: current\n  spec-audit: retired, update removes it\n  spec-change: retired, update removes it\n  spec-plan: retired, update removes it\n/.test(r.out), r.out);
  assert.ok(/\.claude\/skills\n  project-knowledge: differs, no version recorded\n/.test(r.out), r.out);
  assert.ok(r.out.includes('4 to refresh: project-spec update'), r.out);
  r = run(['update']);
  assert.equal(r.code, 0, r.out + r.err);
  assert.ok(r.out.includes('~/.codex/skills/project-knowledge: recorded as current'), r.out);
  assert.ok(/\.claude\/skills\/project-knowledge: updated to .*the old copy is in/.test(r.out), r.out);
  const gone = /spec-change: removed, this skill is retired; the old copy is in (~\/\.project-spec\/backups\/\S+)/.exec(r.out);
  assert.ok(gone, r.out);
  assert.ok(read(path.join(home, gone[1].slice(2), 'SKILL.md')).includes('old skill'));
  assert.ok(!fs.existsSync(path.join(codex, 'spec-audit')) && !fs.existsSync(path.join(codex, 'spec-plan')) && !fs.existsSync(path.join(codex, 'spec-change')));
  assert.ok(fs.existsSync(path.join(codex, 'spec-investigation/SKILL.md')), 'a folder that only shares the name is somebody else\'s');
  assert.ok(fs.existsSync(path.join(codex, 'project-knowledge/.project-spec.json')));
  assert.ok(run(['status']).out.includes('Everything installed is current.'));
  fs.rmSync(path.join(project, '.claude'), { recursive: true });
  // update adds nothing new: a copy that was removed stays removed
  fs.rmSync(path.join(claude, 'project-knowledge'), { recursive: true });
  run(['update']);
  assert.ok(!fs.existsSync(path.join(claude, 'project-knowledge')));

  // the viewer goes into a copy only when asked, stays in a copy that has it, and comes out when asked
  const lean = path.join(project, 'lean');
  const page = path.join(lean, 'project-knowledge/assets/viewer.html');
  const example = path.join(ROOT, 'examples/parcel-desk');
  const helper = (...args) => spawnSync(process.platform === 'win32' ? 'python' : 'python3', [path.join(lean, 'project-knowledge/scripts/knowledge.py'), ...args, '--repo', example], { encoding: 'utf8' });
  assert.equal(run(['install', '--dir', lean, '--with-viewer', '--no-viewer']).code, 2);
  r = run(['install', '--dir', lean, '--skills', 'project-knowledge']);
  assert.ok(r.out.includes(`installed to ${VERSION}`) && !r.out.includes('with the viewer'), r.out);
  let built = helper('build', '--out', path.join(temp, 'lean.html'));
  assert.equal(built.status, 2, built.stderr);
  assert.ok(built.stderr.includes('the viewer is not part of this copy of the skill') && built.stderr.includes('npx project-spec serve'), built.stderr);
  assert.equal(helper('check').status, 0, 'a copy without the viewer still checks a vault');
  r = run(['install', '--dir', lean, '--skills', 'project-knowledge', '--with-viewer']);
  assert.ok(r.out.includes(`updated to ${VERSION}, with the viewer`), r.out);
  assert.equal(read(page), read(path.join(ROOT, 'viewer/viewer.html')));
  built = helper('build', '--out', path.join(temp, 'lean.html'));
  assert.equal(built.status, 0, built.stderr);
  assert.ok(read(path.join(temp, 'lean.html')).includes('Parcel Desk'));
  // a copy an earlier version made: it has the viewer and the helper tests; update keeps the first and removes the second
  const before = JSON.parse(read(path.join(lean, 'project-knowledge/.project-spec.json')));
  fs.writeFileSync(path.join(lean, 'project-knowledge/scripts/test_knowledge.py'), 'old test');
  fs.writeFileSync(page, 'old viewer');
  before.version = '0.9.2';
  before.files['scripts/test_knowledge.py'] = sha('old test');
  before.files['assets/viewer.html'] = sha('old viewer');
  fs.writeFileSync(path.join(lean, 'project-knowledge/.project-spec.json'), JSON.stringify(before));
  const inLean = { cwd: project };
  fs.mkdirSync(path.join(project, '.agents/skills'), { recursive: true });
  fs.renameSync(path.join(lean, 'project-knowledge'), path.join(project, '.agents/skills/project-knowledge'));
  const agents = path.join(project, '.agents/skills/project-knowledge');
  assert.ok(run(['status'], inLean).out.includes('project-knowledge: older (0.9.2), with the viewer'), run(['status'], inLean).out);
  r = run(['update'], inLean);
  assert.ok(r.out.includes(`.agents/skills/project-knowledge: updated to ${VERSION}, with the viewer`), r.out);
  assert.equal(read(path.join(agents, 'assets/viewer.html')), read(path.join(ROOT, 'viewer/viewer.html')));
  assert.ok(!fs.existsSync(path.join(agents, 'scripts/test_knowledge.py')));
  r = run(['install', '--dir', path.join(project, '.agents/skills'), '--skills', 'project-knowledge', '--no-viewer']);
  assert.ok(r.out.includes(`updated to ${VERSION}`) && !r.out.includes('with the viewer'), r.out);
  assert.ok(!fs.existsSync(path.join(agents, 'assets')));
  assert.ok(run(['status'], inLean).out.includes('Everything installed is current.'));
  fs.rmSync(path.join(project, '.agents'), { recursive: true });

  // the block for the project's agent instruction files: printed, written, replaced, removed
  const start = '<!-- project-spec:start -->';
  const end = '<!-- project-spec:end -->';
  assert.equal(run(['instructions']).code, 2, 'no vault to name in the block');
  fs.mkdirSync(path.join(project, 'knowledge/demo'), { recursive: true });
  fs.writeFileSync(path.join(project, 'knowledge/demo/00-index.md'), '# Demo\n');
  r = run(['instructions']);
  assert.equal(r.code, 0, r.err);
  assert.ok(r.out.startsWith(start) && r.out.trim().endsWith(end), r.out);
  assert.ok(r.out.includes('`knowledge/demo/` is this project\'s as-built spec') && !r.out.includes('{vault}'), r.out);
  assert.ok(r.out.split('\n').length < 25, 'the block stays short: it is read at the start of every session');
  assert.ok(r.out.includes('`npx --yes project-spec check --vault knowledge/demo`') && !/npx project-spec/.test(r.out),
    'an agent cannot answer the question npx asks before it downloads a package');
  fs.writeFileSync(path.join(project, 'AGENTS.md'), '# Rules\n\nUse tabs.\n');
  r = run(['instructions', '--file', 'AGENTS.md', '--file', 'CLAUDE.md', '--file', '.cursor/rules/project-spec.mdc']);
  assert.ok(r.out.includes('AGENTS.md: block added') && r.out.includes('CLAUDE.md: written') && r.out.includes('project-spec.mdc: written'), r.out);
  assert.ok(read(path.join(project, 'AGENTS.md')).startsWith('# Rules\n\nUse tabs.\n\n' + start));
  assert.ok(read(path.join(project, 'CLAUDE.md')).startsWith(start));
  assert.ok(read(path.join(project, '.cursor/rules/project-spec.mdc')).startsWith('---\ndescription: Keep the project spec current\nalwaysApply: true\n---\n\n' + start));
  assert.ok(run(['instructions', '--file', 'AGENTS.md']).out.includes('AGENTS.md: already current'));
  // an older block is replaced, and what the person wrote around it stays
  fs.writeFileSync(path.join(project, 'AGENTS.md'), `# Rules\n\n${start}\nold words\n${end}\n\nUse tabs.\n`);
  assert.ok(run(['instructions', '--file', 'AGENTS.md', '--vault', 'knowledge/demo']).out.includes('AGENTS.md: block updated'));
  const rules = read(path.join(project, 'AGENTS.md'));
  assert.ok(rules.startsWith('# Rules\n\n' + start) && rules.endsWith(end + '\n\nUse tabs.\n') && !rules.includes('old words'), rules);
  r = run(['instructions', '--remove', '--file', 'AGENTS.md', '--file', 'CLAUDE.md', '--file', 'README.md']);
  assert.ok(r.out.includes('AGENTS.md: block removed') && r.out.includes('CLAUDE.md: removed (the file held nothing else)') && r.out.includes('README.md: no project-spec block there'), r.out);
  assert.equal(read(path.join(project, 'AGENTS.md')), '# Rules\n\nUse tabs.\n');
  assert.ok(!fs.existsSync(path.join(project, 'CLAUDE.md')) && !fs.existsSync(path.join(project, 'README.md')));
  assert.equal(run(['instructions', '--remove']).code, 2);
  assert.equal(run(['instructions', '--vault', 'knowledge/tooling']).code, 2, 'a folder without 00-index.md is not a vault');
  // the vault is found wherever the person put it, without naming it
  fs.renameSync(path.join(project, 'knowledge/demo'), path.join(project, 'project-spec'));
  assert.ok(run(['instructions']).out.includes('`project-spec/` is this project\'s as-built spec'));
  fs.mkdirSync(path.join(project, 'docs/spec'), { recursive: true });
  fs.writeFileSync(path.join(project, 'docs/spec/00-index.md'), '# Other\n');
  r = run(['instructions']);
  assert.ok(r.code === 2 && r.err.includes('several vaults found (docs/spec, project-spec)'), r.err);
  fs.rmSync(path.join(project, 'docs'), { recursive: true });
  fs.rmSync(path.join(project, 'project-spec'), { recursive: true });
  fs.rmSync(path.join(project, '.cursor'), { recursive: true });

  // the helpers are started from the package, in the current folder by default
  const dry = { env: { PROJECT_SPEC_DRY_RUN: '1', PROJECT_SPEC_PYTHON: 'py' } };
  const script = path.join(ROOT, 'skills/project-knowledge/scripts');
  assert.equal(run(['serve'], dry).out.trim(), `py ${script}/knowledge.py serve --repo . --open`);
  assert.equal(run(['serve', '--no-open', '--port', '9000', '--repo', 'x'], dry).out.trim(), `py ${script}/knowledge.py serve --port 9000 --repo x`);
  assert.equal(run(['build', '--out', 'site/spec.html'], dry).out.trim(), `py ${script}/knowledge.py build --out site/spec.html --repo .`);
  assert.equal(run(['check', '--strict'], dry).out.trim(), `py ${script}/knowledge.py check --strict --repo .`);
  assert.equal(run(['move', '--to', 'project-spec'], dry).out.trim(), `py ${script}/knowledge.py move --to project-spec --repo .`);
  assert.equal(run(['summary'], dry).out.trim(), `py ${script}/knowledge.py summary --repo .`);
  assert.equal(run(['gaps', '--topic', 'security'], dry).out.trim(), `py ${script}/knowledge.py gaps --topic security --repo .`);
  assert.equal(run(['next'], dry).out.trim(), `py ${script}/knowledge.py next --repo .`);
  r = run(['summary'], { cwd: path.join(ROOT, 'examples/parcel-desk') });
  assert.ok(r.code === 0 && r.out.includes('map: 1 of 1 features finished (100%)') && r.out.includes('security   last run 2026-11-16, 1 of 1 feature;'), r.out + r.err);
  assert.equal(run(['scan', '--write-status'], dry).out.trim(), `py ${script}/maintain.py scan --write-status --repo .`);
  assert.equal(run(['coverage', '--path', 'src/chat'], dry).out.trim(), `py ${script}/coverage.py --path src/chat --repo .`);
  r = run(['check'], { cwd: path.join(ROOT, 'examples/parcel-desk') });
  assert.equal(r.code, 0, r.err);
  assert.ok(/check: \d+ notes/.test(r.out), r.out);
  assert.equal(run(['check'], { env: { PROJECT_SPEC_PYTHON: 'no-such-python-anywhere' } }).code, 2);

  // the Claude Code plugin manifest names the same version, and the marketplace lists that plugin
  const pkg = JSON.parse(read(path.join(ROOT, 'package.json')));
  const plugin = JSON.parse(read(path.join(ROOT, '.claude-plugin/plugin.json')));
  const market = JSON.parse(read(path.join(ROOT, '.claude-plugin/marketplace.json')));
  assert.equal(plugin.version, pkg.version, 'plugin.json and package.json name different versions');
  assert.deepEqual(market.plugins.map(p => [p.name, p.source]), [[plugin.name, './']]);
  assert.equal(Object.keys(pkg.bin).join(), 'project-spec');

  // what goes to the npm registry: the command and the skills, and nothing a local run left behind
  const npm = spawnSync(process.platform === 'win32' ? 'npm.cmd' : 'npm', ['pack', '--dry-run', '--json', '--ignore-scripts'], { cwd: ROOT, encoding: 'utf8' });
  if (npm.status === 0) {
    const packed = JSON.parse(npm.stdout)[0].files.map(f => f.path);
    for (const needed of ['bin/project-spec.mjs', 'README.md', 'LICENSE', ...skills.map(n => `skills/${n}/SKILL.md`), 'viewer/viewer.html'])
      assert.ok(packed.includes(needed), `the package lacks ${needed}`);
    const stray = packed.filter(f => /__pycache__|\.pyc$|^examples\/|^docs\/|^scripts\/|^tests\/|\/test_[^/]*\.py$|^skills\/.*\.html$/.test(f));
    assert.deepEqual(stray, [], 'the package carries files it should not');
  } else console.log('NOT RUN: package contents (npm not available)');

  console.log('PASS: package command installs, updates, reports and starts the helpers');
} finally {
  fs.rmSync(temp, { recursive: true, force: true });
}
