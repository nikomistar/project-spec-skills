#!/usr/bin/env python3
"""Validate and build a project-knowledge vault using only the standard library."""
import argparse
import datetime as dt
import hashlib
import html
import json
import os
import posixpath
import re
import sys
import subprocess
import tempfile
import unicodedata
from urllib.parse import quote, unquote, urlsplit
from pathlib import Path, PurePosixPath

TYPES = {'index', 'area', 'note', 'gap', 'plan', 'run'}
SPEC_STATUSES = {'current', 'partial', 'stale', 'superseded'}
NAV_STATUSES = SPEC_STATUSES | {'planned'}
KINDS = ('product-gap', 'verification-gap', 'product-plan', 'conflict', 'knowledge-gap')
TOPICS = ('security', 'validation', 'data', 'logic', 'ui', 'api', 'ops')  # what a gap is about; one value, optional
REVIEWS = ('security', 'abuse', 'validation', 'data', 'logic', 'flows', 'api', 'ui', 'failures')  # the reviews the skill has a list of questions for
REVIEW_TOPICS = {'abuse': 'security', 'flows': 'logic', 'failures': 'ops'}  # the topic a review's gaps get, where it is not the review's own word
REVIEW_FILE = re.compile(r'(?:^|/)\d{4}-\d{2}-\d{2}-review-([a-z0-9-]+)\.md$')
TICK = re.compile(r'^[ \t]*[-*] \[([ xX])\]', re.M)
INVENTORY_HEAD = re.compile(r'^##[ \t]+.+:[ \t]*(finished|in progress|not started)[ \t]*$', re.M | re.I)
CLOSED = ('done', 'rejected', 'duplicate')
RECHECKS = ('not-checked', 'confirmed', 'not-reproduced', 'outdated')
DECISIONS = ('open', 'accepted', 'rejected', 'deferred', 'done', 'duplicate')
DECIDED = ('accepted', 'rejected', 'deferred')
STATE_ORDER = ('needs-recheck', 'needs-decision', 'accepted', 'deferred', 'rejected', 'done', 'duplicate')
GAP_ONLY = ('kind', 'recheck', 'rechecked_by', 'rechecked_on', 'decision', 'decided_by', 'decided_on', 'duplicate_of', 'created', 'topic')
GAP_SECTIONS = ('Current behavior', 'Gap', 'Evidence', 'Recheck', 'Discussion', 'Decision')
LAYERS = {'area': 'spec', 'note': 'spec', 'gap': 'gap', 'plan': 'gap', 'index': 'nav', 'run': 'nav'}
UNCOUNTED = ' (uncommitted change, not counted)'  # suffix of a freshness warning that --ignore-dirty does not count
CONTROL = re.compile('[\x00-\x1f\x7f\x85\u2028\u2029]')
SCHEME = re.compile(r'^[A-Za-z][A-Za-z0-9+.-]*:')
MD_LINK = re.compile(r'\]\(\s*(<[^>]*>|[^\s)]*)')
# The delimiter row of a GFM table: | --- | :-: |, with or without the outer pipes, at least one pipe.
TABLE_RULE = re.compile(r'^ {0,3}\|?[ \t]*:?-+:?[ \t]*(\|[ \t]*:?-+:?[ \t]*)+\|?[ \t]*$|^ {0,3}\|[ \t]*:?-+:?[ \t]*\|?[ \t]*$')
# A numbered business rule: the first cell of a table row, e.g. | BR-PROFILE-01 | ... |
RULE_ROW = re.compile(r'^ {0,3}\|[ \t]*(BR-[A-Z0-9]+(?:-[A-Z0-9]+)*-\d{2,4})[ \t]*\|')
MD_REF = re.compile(r'^ {0,3}\[[^\]\n]+\]:\s*(<[^>]*>|\S+)', re.M)
GAP_PAGE_ONLY = ('priority', 'confidence')
ARRAYS = {'areas', 'sources', 'tags', 'aliases', 'task_ids', 'access'}
STRINGS = {'id', 'title', 'type', 'status', 'updated', 'summary', 'verification', 'priority', 'confidence', 'gap', 'parent', 'review',
           *GAP_ONLY}
REQUIRED = {'id', 'title', 'type', 'areas', 'sources', 'updated'}
LINK = re.compile(r'(!?)\[\[([^\[\]\n]+)\]\]')  # no brackets inside, so a run of '[[' cannot backtrack
FENCE = re.compile(r'^ {0,3}(`{3,}|~{3,})(.*)$')
HEADING = re.compile(r'^ {0,3}(#{1,6})(?:[ \t]+(.*?))?[ \t]*$')
CREDENTIAL_NAMES = {'.env', '.aws', '.ssh', '.gnupg', 'credentials', 'secrets', '.npmrc', '.netrc', '.htpasswd',
                    'id_rsa', 'id_ed25519', 'id_ecdsa', 'id_dsa', '.git', '.git-credentials', 'credentials.json',
                    '.envrc', '.pgpass', '.pypirc', '_netrc', '.vault-token', '.terraformrc',
                    'application_default_credentials.json'}
CREDENTIAL_SUFFIXES = ('.pem', '.key', '.p12', '.pfx', '.tfstate', '.tfstate.backup', '.jks', '.ppk', '.p8', '.tfvars', '.gpg')
CREDENTIAL_PAIRS = {('.kube', 'config'), ('.docker', 'config.json')}


def safe_path(root, value):
    p = PurePosixPath(value)
    if not value or p.is_absolute() or '..' in p.parts or '\\' in value:
        raise ValueError('path must be relative and stay inside its root')
    candidate = root.joinpath(*p.parts)
    if not candidate.resolve().is_relative_to(root):
        raise ValueError('path resolves outside its root')
    return candidate


def output_path(root, value):
    path = safe_path(root, value)
    current = root
    for part in PurePosixPath(value).parts:
        current = current / part
        if current.is_symlink():
            raise ValueError(f'output path contains symlink: {value}')
    return path


def fold(part):
    """Compatibility-fold a path part so look-alike characters (e.g. U+017F) cannot dodge name checks."""
    return unicodedata.normalize('NFKC', part).casefold()


def credential_path(value):
    parts = [fold(p) for p in PurePosixPath(value).parts]
    if any(pair in CREDENTIAL_PAIRS for pair in zip(parts, parts[1:])):
        return True
    return any(p in CREDENTIAL_NAMES or p.startswith('.env.') or p.endswith(CREDENTIAL_SUFFIXES) or
               (p.startswith('service-account') and p.endswith('.json')) or
               (p.startswith('client_secret') and p.endswith('.json')) or p.startswith('secrets.') for p in parts)


def lines_with_code(body, state=None):
    """Yield (line, in_code) following CommonMark fenced code rules.

    A backtick opener cannot have a backtick in its info string, and a closer
    cannot have an info string at all.
    """
    fence = None
    for line in re.split(r'\r\n|\n|\r', body):
        match = FENCE.match(line)
        if fence is None:
            if match and not (match.group(1)[0] == '`' and '`' in match.group(2)):
                fence = (match.group(1)[0], len(match.group(1)))
                yield line, True
            else:
                yield line, False
        else:
            yield line, True
            if match and match.group(1)[0] == fence[0] and len(match.group(1)) >= fence[1] and not match.group(2).strip():
                fence = None
    if state is not None:
        state['fence'] = fence  # still open when the text ended


def prose(body):
    return '\n'.join(re.sub(r'(`+).*?\1', '', line) for line, in_code in lines_with_code(body) if not in_code)


def heading_of(line):
    """Return (level, text) for an ATX heading line, else None."""
    match = HEADING.match(line)
    if not match:
        return None
    return len(match.group(1)), re.sub(r'(?:^|[ \t]+)#+$', '', match.group(2) or '').strip()


def sections(body):
    """Return [(name or None, text)] for each level-1/2 heading outside code, in order."""
    found, current = [], None
    for line, in_code in lines_with_code(body):
        head = None if in_code else heading_of(line)
        if head and head[0] <= 2:
            current = (head[1] if head[0] == 2 else None, [])
            found.append(current)
        elif current is not None:
            current[1].append(line)
    return [(name, '\n'.join(lines)) for name, lines in found]


def atomic_write(path, text):
    """Write text next to its destination and replace it, so readers never see a partial file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    mask = os.umask(0)
    os.umask(mask)
    mode = path.stat().st_mode & 0o777 if path.is_file() else 0o666 & ~mask
    fd, name = tempfile.mkstemp(dir=path.parent, prefix='.knowledge-', suffix='.tmp')
    try:
        with os.fdopen(fd, 'wb') as handle:
            handle.write(text.encode('utf-8'))
        os.chmod(name, mode)
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def check_date(key, value):
    if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', value):
        raise ValueError(f'{key} must be YYYY-MM-DD')
    try:
        dt.date.fromisoformat(value)
    except ValueError:
        raise ValueError(f'{key} is not a real date')


def gap_state(meta):
    """Derived, never stored: needs-recheck, needs-decision, or the decision itself."""
    if meta['decision'] != 'open':
        return meta['decision']
    return 'needs-recheck' if meta['recheck'] in {'not-checked', 'outdated'} else 'needs-decision'


def date_problem(key, value):
    try:
        check_date(key, value)
    except ValueError as exc:
        return [str(exc)]
    return []


def meta_problems(meta, unread=()):
    """Every frontmatter problem of one page, as author-facing messages, so that one pass of fixing is enough.

    unread: properties whose line could not be read. They are reported by the caller, so nothing is said here
    about them being missing, and what cannot be judged without them is left for the next run.
    """
    out = []
    missing = REQUIRED - meta.keys() - set(unread)
    if missing:
        out.append('missing properties: ' + ', '.join(sorted(missing)))
    for key in sorted(STRINGS & meta.keys()):
        if not isinstance(meta[key], str):
            out.append(f'{key} must be a string')
    for key in sorted(ARRAYS & meta.keys()):
        if not isinstance(meta[key], list) or any(not isinstance(x, str) for x in meta[key]):
            out.append(f'{key} must be a string array')
    if out or REQUIRED - meta.keys():
        return out  # the checks below read these properties
    for key in sorted((STRINGS | ARRAYS) & meta.keys()):
        if any(CONTROL.search(value) for value in (meta[key] if isinstance(meta[key], list) else [meta[key]])):
            out.append(f'{key} must not contain control characters (line breaks, tabs, U+0085, U+2028, U+2029)')
    if not re.fullmatch(r'[a-z0-9-]+', meta['id']):
        out.append('invalid id')
    kind = meta['type']
    if not meta['title'].strip() or kind not in TYPES:
        out.append('invalid title or type; type must be one of ' + ', '.join(sorted(TYPES)))
    out += date_problem('updated', meta['updated'])
    if kind not in TYPES:
        return out  # which properties a page may have depends on its type
    if kind in {'note', 'gap', 'plan'} and not meta['areas']:
        out.append(f'{kind} requires an area')
    if kind == 'gap':
        if 'status' in meta:
            out.append('a gap must not have status; gaps use recheck and decision instead')
        out += gap_problems(meta, unread)
    else:
        for key in GAP_ONLY:
            if key in meta:
                out.append(f'{key} is only valid on gap pages')
        if kind != 'plan':
            for key in GAP_PAGE_ONLY:
                if key in meta:
                    out.append(f'{key} is only valid on gap and plan pages')
        if kind in {'area', 'note'}:
            for key in ('title', 'summary'):
                if re.search(r'\[\[|\[[^\]\n]*\]\([^)\n]*\)', meta.get(key, '')):
                    out.append(f'{key} of a spec page must not contain links; describe the page in plain text')
        allowed = SPEC_STATUSES if kind in {'area', 'note'} else NAV_STATUSES
        if 'status' not in meta:
            if 'status' not in unread:
                out.append('missing properties: status')
        elif meta['status'] not in allowed:
            hint = ''
            if meta['status'] in {'unverified', 'conflict'}:
                hint = f"; '{meta['status']}' is no longer a status: record it as a gap under gaps/"
            out.append(f"status must be one of {', '.join(sorted(allowed))}{hint}")
        elif kind == 'note' and meta['status'] == 'current' and not meta['sources']:
            out.append('current note requires sources')
    if 'access' in meta:
        if kind != 'note':
            out.append('access is only valid on note pages: it names who may use the feature the note describes')
        elif not meta['access'] or any(not x.strip() for x in meta['access']):
            out.append('access must name at least one role, or be left out when the code was not read for it')
    if 'review' in meta and (kind not in ('run', 'gap') or not re.fullmatch(r'[a-z0-9-]+', meta['review'])):
        out.append('review is only valid on run and gap pages and names the review, in lower case: "security"')
    if 'parent' in meta and (kind != 'note' or not meta['parent'].strip()):
        out.append('parent is only valid on note pages and names the feature note this one is a part of')
    if kind == 'plan':
        if not meta.get('gap', '').strip() and 'gap' not in unread:
            out.append('plan requires gap: the id of the accepted gap it implements')
    elif 'gap' in meta:
        out.append('gap is only valid on plan pages')
    return out


def validate_meta(meta):
    """Raise ValueError with an author-facing message for the first frontmatter problem."""
    problems = meta_problems(meta)
    if problems:
        raise ValueError(problems[0])


def gap_problems(meta, unread=()):
    out, known = [], {}
    for key, values in (('kind', KINDS), ('recheck', RECHECKS), ('decision', DECISIONS)):
        if key not in meta:
            if key not in unread:
                out.append(f'gap requires {key} (one of {", ".join(values)})')
        elif meta[key] not in values:
            out.append(f'{key} must be one of {", ".join(values)}')
        else:
            known[key] = meta[key]
    if known.get('recheck') == 'not-checked':
        for key in ('rechecked_by', 'rechecked_on'):
            if key in meta:
                out.append(f"{key} must be absent while recheck is 'not-checked'")
    elif 'recheck' in known:
        for key in ('rechecked_by', 'rechecked_on'):
            if key not in meta and key not in unread:
                out.append(f"{key} is required when recheck is '{meta['recheck']}'")
        if 'rechecked_by' in meta and not meta['rechecked_by'].strip():
            out.append('rechecked_by must name a person, or be "agent"')
        if 'rechecked_on' in meta:
            out += date_problem('rechecked_on', meta['rechecked_on'])
    if known.get('decision') == 'open':
        for key in ('decided_by', 'decided_on'):
            if key in meta:
                out.append(f"{key} must be absent while decision is 'open'")
    elif known.get('decision') in DECIDED:
        for key in ('decided_by', 'decided_on'):
            if key not in meta and key not in unread:
                out.append(f"{key} is required when decision is '{meta['decision']}'")
    if 'decided_by' in meta and (not meta['decided_by'].strip() or meta['decided_by'].strip().lower() == 'agent'):
        out.append("decided_by must be a person's name: an agent may not decide, only record what a person decided")
    if 'decided_on' in meta:
        out += date_problem('decided_on', meta['decided_on'])
    if 'created' in meta:
        out += date_problem('created', meta['created'])
    if 'topic' in meta and meta['topic'] not in TOPICS:
        out.append(f'topic must be one of {", ".join(TOPICS)}')
    if known.get('decision') == 'duplicate':
        if not meta.get('duplicate_of', '').strip() and 'duplicate_of' not in unread:
            out.append("duplicate_of is required when decision is 'duplicate': give the id of the other gap")
    elif 'decision' in known and 'duplicate_of' in meta:
        out.append("duplicate_of is only valid when decision is 'duplicate'")
    return out


def has_conflict_markers(content):
    # Git emits labeled openers; keep candidates of different widths independent.
    active = {}
    for line in content.splitlines():
        opener = re.fullmatch(r'(<+)[ \t]+\S.*', line)
        if opener:
            active.setdefault(len(opener.group(1)), set()).add(1)
        for width, states in active.items():
            if 1 in states and re.fullmatch(r'\|{' + str(width) + r'}(?:[ \t].*)?', line):
                states.add(2)
            if (1 in states or 2 in states) and line == '=' * width:
                states.add(3)
            if 3 in states and re.fullmatch(r'>{' + str(width) + r'}(?:[ \t].*)?', line):
                return True
    return False


def tolerates_missing_source(meta, ids):
    """Missing sources only warn on stale/superseded pages, closed gaps and plans of done gaps."""
    if meta.get('status') in {'stale', 'superseded'}:
        return True
    if meta['type'] == 'gap':
        return meta['decision'] in {'done', 'rejected', 'duplicate'}
    if meta['type'] == 'plan':
        return ids.get(meta['gap'], {}).get('meta', {}).get('decision') == 'done'
    return False


def markdown_target(rel, raw):
    """Vault-relative path a Markdown link points at, or None for URLs, anchors and absolute paths."""
    target = unquote(re.split(r'[?#]', raw[1:-1] if raw.startswith('<') else raw, maxsplit=1)[0])
    if not target or target.startswith('/') or SCHEME.match(target):
        return None
    return posixpath.normpath(posixpath.join(posixpath.dirname(rel), target))


def attachment_exists(vault, target, cache):
    """Embedded non-Markdown files (images, PDFs) resolve by path or bare name anywhere in the vault."""
    if not cache:
        cache['names'], cache['paths'] = set(), set()
        for file in vault.rglob('*'):
            parts = file.relative_to(vault).parts
            if file.is_file() and not any(part in {'.obsidian', '.trash', '.knowledge'} for part in parts):
                cache['names'].add(parts[-1].casefold())
                cache['paths'].add('/'.join(parts).casefold())
    wanted = target.casefold()
    return wanted in cache['paths'] or ('/' not in wanted and wanted in cache['names'])


def line_ending_variant(data, old):
    """True when data matches the baseline digest after converting all line endings to LF or CRLF."""
    lf = data.replace(b'\r\n', b'\n')
    return old in {hashlib.sha256(lf).hexdigest(), hashlib.sha256(lf.replace(b'\n', b'\r\n')).hexdigest()}


def run_git(repo, args, **options):
    """Git's answer for the repository. Where Git is not installed (a build container, say) it is the answer
    of a folder that is not a work tree, so the caller goes on without history instead of stopping."""
    try:
        return subprocess.run(['git', '-C', str(repo), *args], capture_output=True, **options)
    except FileNotFoundError:
        return subprocess.CompletedProcess(args, 127, b'', b'')


def head_blob(repo, source):
    """Bytes of the source as committed at HEAD, or None when HEAD has no such file (untracked, new or no commits)."""
    result = run_git(repo, ['cat-file', 'blob', f'HEAD:./{posixpath.normpath(source)}'])
    return None if result.returncode else result.stdout


def uncommitted_paths(repo):
    """Repo-relative paths Git reports as modified, staged or untracked (one status call), or None outside a work tree."""
    probe = run_git(repo, ['rev-parse', '--is-inside-work-tree', '--show-prefix'])
    lines = probe.stdout.decode(errors='replace').split('\n')
    if probe.returncode or lines[0] != 'true':
        return None
    prefix = lines[1] if len(lines) > 1 else ''
    status = run_git(repo, ['status', '--porcelain=v1', '-z', '--untracked-files=all'])
    if status.returncode:
        return None
    raw, found, i = status.stdout.split(b'\0'), set(), 0
    while i < len(raw) and raw[i]:
        item = os.fsdecode(raw[i])
        i += 1
        names = [item[3:]]
        if 'R' in item[:2] or 'C' in item[:2]:
            names.append(os.fsdecode(raw[i]))
            i += 1
        found.update(name[len(prefix):] for name in names if name.startswith(prefix))
    return found


class PageProblems(ValueError):
    """Everything that is wrong with one page's properties."""

    def __init__(self, problems):
        super().__init__(problems[0])
        self.problems = problems


def error_page(message):
    """The vault-relative page an error message is about, or None for vault-wide errors."""
    head = message.split(': ', 1)[0]
    return head if head.endswith('.md') else None


def load_vault(repo, vault, freshness=True, dirty=None, report=None, absent=None):
    """dirty: repo-relative paths with uncommitted changes. Their freshness warning is marked, not counted, only when
    the accepted fingerprint equals the file's HEAD blob (up to LF/CRLF), so the sole drift is uncommitted.

    absent, when given, collects cited files that are not there instead of reporting them: for a build that sees
    only part of the repository, such as a Docker build context. Their pages are not marked as changed.

    report, when given, receives 'failed': {page path: parsed id or None} for pages that failed validation.
    """
    errors, warnings, notes, failed, failed_kind, cascade = [], [], [], {}, {}, []
    baseline_file = vault / '.knowledge/sources.json'
    baseline = {}
    if baseline_file.exists():
        try:
            safe_path(vault, '.knowledge/sources.json')
            baseline = json.loads(baseline_file.read_text(encoding='utf-8'))
            if not isinstance(baseline, dict) or any(not isinstance(v, dict) for v in baseline.values()):
                raise ValueError('expected object of note source maps')
        except (OSError, ValueError) as exc:
            errors.append(f'Invalid source snapshot: {exc}')
            baseline = {}
    for file in sorted(vault.rglob('*.md')):
        relative = file.relative_to(vault)
        if any(part in {'.obsidian', '.trash', '.knowledge'} for part in relative.parts):
            continue
        rel = relative.as_posix()
        meta = None
        try:
            safe_path(vault, rel)
            content = file.read_text(encoding='utf-8').removeprefix('\ufeff')
            if has_conflict_markers(content):
                raise ValueError('unresolved Git conflict markers')
            match = re.match(r'\A---\s*\n(.*?)\n---\s*(?:\n|$)', content, re.S)
            if not match:
                raise ValueError('missing frontmatter')
            meta, problems, unread = {}, [], set()
            for line in match.group(1).splitlines():
                if not line.strip() or line.lstrip().startswith('#'):
                    continue
                key, sep, value = line.partition(':')
                if not sep or not re.fullmatch(r'[a-z_]+', key) or key in meta or key in unread:
                    problems.append('invalid or duplicate property' + (f' ({key.strip()[:40]})' if key.strip() else ''))
                    continue
                try:
                    meta[key] = json.loads(value.strip())
                except json.JSONDecodeError as exc:
                    # Every line that cannot be read is named, so the page is fixed in one pass.
                    unread.add(key)
                    problems.append(f'{key}: {exc}')
            problems += meta_problems(meta, unread)
            if problems:
                raise PageProblems(problems)
            notes.append({'meta': meta, 'path': rel, 'body': content[match.end():]})
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            errors += [f'{rel}: {problem}' for problem in (exc.problems if isinstance(exc, PageProblems) else [exc])]
            # The page still exists as a link target; only its own errors are real.
            ident = meta.get('id') if isinstance(meta, dict) else None
            failed[rel] = ident if isinstance(ident, str) and re.fullmatch(r'[a-z0-9-]+', ident) else None
            kind = meta.get('type') if isinstance(meta, dict) else None
            failed_kind[rel] = kind if kind in TYPES else None
    failed_ids = {i for i in failed.values() if i}
    failed_id_kinds = {}
    for rel, ident in failed.items():
        if ident:
            failed_id_kinds.setdefault(ident, set()).add(failed_kind[rel])
    failed_stems = {rel[:-3]: failed_kind[rel] for rel in failed}
    failed_names = {}
    for stem, kind in failed_stems.items():
        failed_names.setdefault(PurePosixPath(stem).name, []).append(kind)
    ids, paths, basenames = {}, {}, {}
    for note in notes:
        meta, rel = note['meta'], note['path']
        if meta['id'] in ids:
            errors.append(f"{rel}: duplicate id {meta['id']}")
        ids[meta['id']] = note
        stem = rel[:-3]
        paths[stem] = note
        basenames.setdefault(PurePosixPath(stem).name, []).append(note)
    area_ids = {n['meta']['id'] for n in notes if n['meta']['type'] == 'area'}
    edges, attachments, rule_pages, linked, parts = set(), {}, {}, set(), []
    for note in notes:
        meta, rel = note['meta'], note['path']
        note['stale'] = False
        if meta.get('parent'):
            # Three levels and no more: an area, its features, and the parts of a feature that is too big for one page.
            other, name = ids.get(meta['parent']), meta['parent']
            if other is None and name in failed_ids and failed_id_kinds[name] & {None, 'note'}:
                cascade.append(f'{rel}: parent {name} names a page that failed validation')
            elif other is None or other['meta']['type'] != 'note':
                errors.append(f'{rel}: parent {name} is not the id of an existing note')
            elif other is note:
                errors.append(f'{rel}: parent must name a different note')
            elif other['meta'].get('parent'):
                errors.append(f"{rel}: parent {name} is itself a part of {other['meta']['parent']}; a part belongs to a feature, not to another part")
            elif other['meta']['areas'][:1] != meta['areas'][:1]:
                errors.append(f"{rel}: parent {name} is in another area; a part has the same first area as its feature")
            else:
                edges.add((other['meta']['id'], meta['id']))
                parts.append((other, note))
        if meta['type'] == 'gap':
            note['state'] = gap_state(meta)
        if meta['type'] == 'gap' and meta.get('duplicate_of'):
            other = ids.get(meta['duplicate_of'])
            if other is None and meta['duplicate_of'] in failed_ids and failed_id_kinds[meta['duplicate_of']] & {None, 'gap'}:
                cascade.append(f"{rel}: duplicate_of {meta['duplicate_of']} names a page that failed validation")
            elif other is None or other['meta']['type'] != 'gap':
                errors.append(f"{rel}: duplicate_of {meta['duplicate_of']} is not the id of an existing gap")
            elif other is note:
                errors.append(f'{rel}: duplicate_of must name a different gap')
        if meta['type'] == 'plan':
            other = ids.get(meta['gap'])
            if other is None and meta['gap'] in failed_ids and failed_id_kinds[meta['gap']] & {None, 'gap'}:
                cascade.append(f"{rel}: gap {meta['gap']} names a page that failed validation")
            elif other is None or other['meta']['type'] != 'gap':
                errors.append(f"{rel}: gap {meta['gap']} is not the id of an existing gap")
            else:
                edges.add((meta['id'], other['meta']['id']))
            if other is not None and other['meta']['type'] == 'gap' and other['meta']['decision'] not in {'accepted', 'done'}:
                errors.append(f"{rel}: gap {meta['gap']} has decision '{other['meta']['decision']}'; a plan needs an accepted or done gap")
        if meta['type'] == 'gap':
            found = [name for name, _ in sections(note['body']) if name is not None]
            for name in GAP_SECTIONS:
                if found.count(name) != 1:
                    errors.append(f"{rel}: gap needs exactly one '## {name}' section (found {found.count(name)})")
            texts = {name: text for name, text in sections(note['body']) if name in GAP_SECTIONS}
            if meta['decision'] != 'open' and found.count('Decision') == 1 and not texts['Decision'].strip():
                errors.append(f"{rel}: the Decision section must say who decided and why once decision is '{meta['decision']}'")
            if meta['recheck'] != 'not-checked' and found.count('Recheck') == 1 and not texts['Recheck'].strip():
                errors.append(f"{rel}: the Recheck section must say what was checked once recheck is '{meta['recheck']}'")
        for area in meta['areas']:
            if area not in ids and area in failed_ids and failed_id_kinds[area] & {None, 'area'}:
                # Only the "missing" error is hidden; a failed page known to be another type still reports it.
                cascade.append(f'{rel}: area {area} names a page that failed validation')
                continue
            if area not in area_ids:
                errors.append(f'{rel}: unknown area {area}')
            elif area != meta['id']:
                edges.add((area, meta['id']))
        text = prose(note['body'])
        run_links = 0
        for embed, link in LINK.findall(text):
            # Inside Markdown tables Obsidian requires the alias separator to be written as \|.
            target = re.split(r'\\?\|', link, maxsplit=1)[0].split('#', 1)[0].split('^', 1)[0].strip()
            if not target:
                continue
            if target.endswith('.md'):
                target = target[:-3]
            choices = basenames.get(target, []) if '/' not in target else ([paths[target]] if target in paths else [])
            broken_kinds = failed_names.get(target, []) if '/' not in target else ([failed_stems[target]] if target in failed_stems else [])
            broken = len(broken_kinds)
            if broken == 1 and not choices:
                # The one candidate exists but failed validation; its own errors are the root cause of "missing".
                if meta['type'] in {'area', 'note'} and broken_kinds[0] in {'gap', 'plan'}:
                    errors.append(f"{rel}: spec pages must not link to the gap layer ({'embed ' if embed else ''}{target}); link from the gap to this page instead")
                else:
                    cascade.append(f'{rel}: link {target} names a page that failed validation')
                    if meta['type'] == 'run':
                        run_links += 1
                continue
            if embed and not choices and PurePosixPath(target).suffix:
                # Not a note: Obsidian embeds images and PDFs by file name.
                if not attachment_exists(vault, target, attachments):
                    errors.append(f'{rel}: missing embed {target}')
                continue
            if len(choices) + broken != 1:
                errors.append(f"{rel}: {'ambiguous' if len(choices) + broken > 1 else 'missing'} {'embed' if embed else 'wikilink'} {target}")
            elif meta['type'] in {'area', 'note'} and choices[0]['meta']['type'] in {'gap', 'plan'}:
                errors.append(f"{rel}: spec pages must not link to the gap layer ({'embed ' if embed else ''}{target}); link from the gap to this page instead")
            elif meta['type'] == 'run':
                run_links += 1
            elif meta['type'] == 'area' and choices[0]['meta']['type'] == 'note' and re.search(r'[#^]', re.split(r'\\?\|', link, maxsplit=1)[0]):
                errors.append(f"{rel}: an area page links whole notes, not a part of one ({link.split('|')[0].replace(chr(92), '')}); "
                              "if that part needs its own link, make it its own note and list it here")
            else:
                edges.add((meta['id'], choices[0]['meta']['id']))
                linked.add((meta['id'], choices[0]['meta']['id']))
        if meta['type'] == 'area':
            # An area page is a map of its notes. A table on it is behavior written in the wrong place.
            tables = sum(1 for line in text.split('\n') if TABLE_RULE.match(line))
            if tables:
                errors.append(f"{rel}: an area page is a map and holds no table ({tables} found); a table describes behavior: "
                              "write a note for each thing it describes and list the notes on the area page")
        if meta['type'] == 'note':
            # People quote a rule by its number in tickets, tests and chats, so a number means one rule for good.
            seen = set()
            for line in text.split('\n'):
                rule = RULE_ROW.match(line)
                if not rule:
                    continue
                ident = rule.group(1)
                first = rule_pages.setdefault(ident, rel)
                if first != rel or ident in seen:
                    errors.append(f"{rel}: rule {ident} is numbered twice ({'on this page' if first == rel else 'also on ' + first}); "
                                  "a rule keeps its number and a number is never used again, so give the newer rule the next free one")
                seen.add(ident)
        if meta['type'] in {'area', 'note'}:
            gap_files = {n['path'].casefold() for n in notes if n['meta']['type'] in {'gap', 'plan'}} | {'gaps.md'}
            gap_files |= {f.casefold() for f, kind in failed_kind.items() if kind in {'gap', 'plan'}}
            unknown_files = {f.casefold() for f, kind in failed_kind.items() if kind is None}
            for raw in MD_LINK.findall(text) + MD_REF.findall(text):
                resolved = markdown_target(rel, raw)
                if resolved is not None and resolved.casefold() in gap_files:
                    errors.append(f"{rel}: spec pages must not link to the gap layer ({raw.strip('<>')}); link from the gap to this page instead")
                elif resolved is not None and resolved.casefold() in unknown_files:
                    cascade.append(f'{rel}: link {raw.strip("<>")} names a page that failed validation')
        if meta['type'] == 'run':
            # A run touches many pages; as links they would turn it into a hub that glues every cluster together.
            page_files = {n['path'].casefold() for n in notes} | {f.casefold() for f in failed}
            run_links += sum(1 for raw in MD_LINK.findall(text) + MD_REF.findall(text)
                             if (markdown_target(rel, raw) or '').casefold() in page_files)
            if run_links:
                errors.append(f"{rel}: run pages are history, not part of the map, and must not link to vault pages ({run_links} link{'s' if run_links != 1 else ''}); name a page by its path in code formatting, e.g. `notes/example`")
        closed = tolerates_missing_source(meta, ids)
        note['changed'] = False
        for source in meta['sources']:
            try:
                if credential_path(source):
                    raise ValueError('credential source is forbidden')
                path = safe_path(repo, source)
                if credential_path(path.resolve().relative_to(repo).as_posix()):
                    raise ValueError('credential source is forbidden')
                if not path.is_file():
                    if absent is not None and not path.exists():
                        absent.append(source)
                        continue
                    if closed:
                        warnings.append(f'{rel}: missing source {source}')
                        note['stale'] = True
                        continue
                    raise ValueError('source is missing or not a file')
                if freshness:
                    old = baseline.get(meta['id'], {}).get(source)
                    data = path.read_bytes()
                    if old != hashlib.sha256(data).hexdigest():
                        mark = ''
                        if old and dirty is not None and posixpath.normpath(source) in dirty:
                            # Forgive only pure uncommitted drift: the accepted bytes are what HEAD holds (up to line endings).
                            blob = head_blob(repo, source)
                            if blob is not None and (hashlib.sha256(blob).hexdigest() == old or line_ending_variant(blob, old)):
                                mark = UNCOUNTED
                        if old and line_ending_variant(data, old):
                            warnings.append(f'{rel}: line endings differ in source {source}{mark}')
                        else:
                            note['changed'] = note['changed'] or bool(old)
                            warnings.append(f"{rel}: {'changed' if old else 'unbaselined'} source {source}{mark}")
                        note['stale'] = True
            except (OSError, ValueError) as exc:
                errors.append(f'{rel}: {source}: {exc}')
    for feature, part in parts:
        # The viewer nests a part under its feature from `parent`; a plain Markdown reader has only the link.
        if (feature['meta']['id'], part['meta']['id']) not in linked:
            errors.append(f"{part['path']}: its feature {feature['path']} does not link to it; list every part on the feature's page")
    if report is not None:
        report['failed'] = failed
        report['cascade'] = cascade
    return notes, sorted(edges), errors, warnings, baseline


def write_json(path, value):
    atomic_write(path, json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def recheck_marker(note):
    """Automatic marker: a recorded recheck exists but a cited source's bytes changed since its fingerprint."""
    return note['meta']['recheck'] in {'confirmed', 'not-reproduced'} and bool(note.get('changed'))


FILE_LIMIT = 300_000    # characters of one cited file sent to the viewer
FILES_LIMIT = 4_000_000  # characters of all cited files together


def cited_files(repo, vault, notes):
    """Text of the repository files the pages cite, so the viewer can show them instead of sending the reader to a raw file.

    Keys are repository-relative paths. Only files inside the repository and outside the vault are taken, never
    credential paths, binaries or symlinks that leave the repository. Returns (files, skipped paths).
    """
    wanted = set()
    for note in notes:
        for source in note['meta']['sources']:
            wanted.add(posixpath.normpath(source))
        text = prose(note['body'])
        for raw in MD_LINK.findall(text) + MD_REF.findall(text):
            target = markdown_target(note['path'], raw)
            if target is not None:
                wanted.add(Path(os.path.relpath(os.path.normpath(vault / target), repo)).as_posix())
    files, skipped, total = {}, [], 0
    for rel in sorted(wanted):
        if rel.startswith('../') or rel in ('..', '.') or credential_path(rel):
            continue
        file = repo / rel
        try:
            resolved = file.resolve()
            if not file.is_file() or not resolved.is_relative_to(repo) or resolved.is_relative_to(vault):
                continue
            data = file.read_bytes()
            if b'\0' in data:
                continue
            text = data.decode('utf-8')
        except (OSError, UnicodeDecodeError, ValueError):
            continue
        truncated = len(text) > FILE_LIMIT
        if truncated:
            text = text[:FILE_LIMIT].rsplit('\n', 1)[0]
        if total + len(text) > FILES_LIMIT:
            skipped.append(rel)
            continue
        total += len(text)
        files[rel] = {'text': text, 'truncated': truncated}
    return files, skipped


def node_of(note):
    m = note['meta']
    gap = m['type'] == 'gap'
    return {k: m[k] for k in ('id', 'title', 'type', 'areas', 'sources', 'updated')} | {
        'status': '' if gap else m['status'],
        'tags': m.get('tags', []), 'path': note['path'], 'body': note['body'],
        'summary': m.get('summary', ''), 'stale': note['stale'],
        'kind': m.get('kind', ''), 'recheck': m.get('recheck', ''), 'recheckedBy': m.get('rechecked_by', ''),
        'recheckedOn': m.get('rechecked_on', ''), 'decision': m.get('decision', ''), 'decidedBy': m.get('decided_by', ''),
        'decidedOn': m.get('decided_on', ''), 'priority': m.get('priority', ''), 'confidence': m.get('confidence', ''),
        'topic': m.get('topic', ''), 'access': m.get('access', []), 'review': m.get('review', ''),
        'parent': m.get('parent', ''), 'duplicateOf': m.get('duplicate_of', ''), 'recheckOutdated': gap and (m['recheck'] == 'outdated' or recheck_marker(note)), 'state': note.get('state', ''), 'gap': m.get('gap', ''),
        'layer': LAYERS[m['type']]}


def graph_of(notes, edges, warnings):
    nodes = [node_of(note) for note in notes]
    title = next((n['title'] for n in nodes if n['path'] == '00-index.md'), 'Project knowledge')
    return {'title': title, 'generatedAt': dt.datetime.now(dt.timezone.utc).isoformat(), 'nodes': nodes,
            'edges': [{'source': a, 'target': b} for a, b in edges], 'warnings': warnings}


VIEWER = None  # --viewer FILE: a page of your own to show the vault with


def viewer_template():
    """The text of the viewer page. The page is not part of the skill, which holds only what writing a spec needs:
    it comes with the project-spec package, with a copy made by `install --with-viewer`, or from --viewer."""
    here = Path(__file__).resolve().parent
    places = [Path(VIEWER)] if VIEWER else [here.parent / 'assets/viewer.html', *([here.parents[2] / 'viewer/viewer.html'] if len(here.parents) > 2 else [])]
    found = next((place for place in places if place.is_file()), None)
    if not found:
        raise ValueError(f'--viewer {VIEWER} is not a file' if VIEWER else
                         'the viewer is not part of this copy of the skill. Run `npx project-spec serve` in the repository (the viewer comes '
                         'with the npm package), add it to this copy with `npx project-spec install --dir <folder of the skill copies> --with-viewer`, '
                         'or open the vault folder in Obsidian')
    template = found.read_text(encoding='utf-8')
    if template.count('__KNOWLEDGE_DATA__') != 1:
        raise ValueError(f'{found} must contain the placeholder __KNOWLEDGE_DATA__ exactly once')
    return template


def viewer_html(payload):
    template = viewer_template()
    serialized = json.dumps(payload, ensure_ascii=False).replace('&', '\\u0026').replace('<', '\\u003c').replace('>', '\\u003e').replace('\u2028', '\\u2028').replace('\u2029', '\\u2029')
    return template.replace('__KNOWLEDGE_DATA__', serialized)


VAULT_DEPTH = 3  # project-spec/, knowledge/<product>/ and docs/<product>/spec/ are all within reach
NOT_A_VAULT_PLACE = {'node_modules', 'vendor', 'dist', 'build', 'out', 'target', 'coverage', '__pycache__', 'venv', 'Pods'}


def find_vault(repo):
    """The repository's vault when it has exactly one: a folder that holds `00-index.md`, wherever the person put it.

    Looks at most three folders deep and not inside hidden folders, dependencies or build output, so a vault that
    belongs to something nested deeper (an example project, a package's own docs) is not taken for the repository's.
    """
    found = []

    def look(folder, depth):
        try:
            entries = sorted(e for e in folder.iterdir()
                             if e.is_dir() and not e.is_symlink() and not e.name.startswith('.') and e.name not in NOT_A_VAULT_PLACE)
        except OSError:
            return
        for entry in entries:
            if (entry / '00-index.md').is_file():
                found.append(entry)  # nothing inside a vault is another vault
            elif depth < VAULT_DEPTH:
                look(entry, depth + 1)

    look(repo, 1)
    if len(found) != 1:
        raise ValueError(('no vault found: no folder with 00-index.md up to three folders deep' if not found else
                          'several vaults found (' + ', '.join(p.relative_to(repo).as_posix() for p in found) + ')') + '; pass --vault')
    return found[0]


def repoint(text, old_dir, new_dir, old_vault):
    """`text` of a page that sat in `old_dir` and now sits in `new_dir`, with the links that leave the vault repointed.

    All three are absolute POSIX paths. A link to another page of the vault is relative to something that moved with
    it, so it stays as written; a link to a file of the repository is rewritten so it names the same file from the
    new place. Links in code are left alone. Returns (text, how many links changed).
    """
    changed = 0

    def target(match):
        nonlocal changed
        raw = match.group(1)
        angle = raw.startswith('<')
        inner = raw[1:-1] if angle else raw
        cut = re.search(r'[?#]', inner)
        path, tail = (inner[:cut.start()], inner[cut.start():]) if cut else (inner, '')
        where = unquote(path)
        if not where or where.startswith('/') or SCHEME.match(where):
            return match.group(0)
        absolute = posixpath.normpath(posixpath.join(old_dir, where))
        if absolute == old_vault or absolute.startswith(old_vault + '/'):
            return match.group(0)
        fresh = posixpath.relpath(absolute, new_dir)
        fresh = fresh if angle else quote(fresh, safe="/-._~!$&'()*+,;=:@")
        if fresh == path:
            return match.group(0)
        changed += 1
        return match.group(0)[:match.start(1) - match.start(0)] + (f'<{fresh}{tail}>' if angle else fresh + tail)

    lines = []
    for line, in_code in lines_with_code(text):
        if not in_code:
            # an inline code span is not a link either
            pieces = re.split(r'(`+.*?`+)', line)
            line = ''.join(piece if i % 2 else MD_REF.sub(target, MD_LINK.sub(target, piece)) for i, piece in enumerate(pieces))
        lines.append(line)
    return '\n'.join(lines), changed


def move_vault(repo, vault, dest):
    """Move the vault to `dest`, another folder of the same repository, and keep it true: links from pages to files
    of the repository are repointed, and each gap keeps the day it appeared. Returns a list of lines to print.

    Page ids, wikilinks, `sources` and the reviewed fingerprints do not depend on where the vault is, so nothing
    else changes. Raises ValueError with the reason when the move cannot be made; nothing is touched then.
    """
    import shutil
    dest = Path(os.path.abspath(dest))
    if dest == vault:
        raise ValueError('the vault is already there')
    if not dest.is_relative_to(repo) or dest == repo:
        raise ValueError('--to must be a folder inside the repository')
    if dest.is_relative_to(vault):
        raise ValueError('--to must not be inside the vault it moves')
    if dest.exists() and (not dest.is_dir() or any(dest.iterdir())):
        raise ValueError(f'{dest.relative_to(repo).as_posix()} already exists and is not empty')
    first = added_dates(repo, vault)
    edits, links, pages, dated = {}, 0, 0, 0
    for file in sorted(vault.rglob('*.md')):
        rel = file.relative_to(vault)
        if any(part in {'.obsidian', '.trash'} for part in rel.parts) or file.is_symlink():
            continue
        try:
            before = file.read_bytes().decode('utf-8')
        except (OSError, UnicodeDecodeError):
            continue
        after, count = repoint(before.replace('\r\n', '\n'), (vault / rel).parent.as_posix(), (dest / rel).parent.as_posix(), vault.as_posix())
        # Git will show the page as new in its new place, so a gap that has no `created` gets the day it first appeared.
        head = re.match(r'---\n(.*?)\n---\n', after, re.S)
        day = first.get(rel.as_posix())
        if head and day and re.search(r'^type:\s*"gap"\s*$', head.group(1), re.M) and not re.search(r'^created:', head.group(1), re.M):
            after = re.sub(r'^(type:\s*"gap"\s*)$', lambda m: m.group(1) + f'\ncreated: "{day}"', after, count=1, flags=re.M)
            dated += 1
        if count:
            links, pages = links + count, pages + 1
        if after != before.replace('\r\n', '\n'):
            edits[rel] = after
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        dest.rmdir()
    shutil.move(str(vault), str(dest))
    for rel, text in edits.items():
        atomic_write(dest / rel, text)
    old, new = vault.relative_to(repo).as_posix(), dest.relative_to(repo).as_posix()
    lines = [f'move: {old} -> {new}; {links} links to repository files repointed on {pages} pages'
             + (f'; {dated} gaps given the day they first appeared' if dated else '')]
    _, _, errors, warnings, _ = load_vault(repo, dest)
    lines.append(f'move: check finds {len(errors)} errors and {len(warnings)} warnings in the new place')
    lines += [f'  {error}' for error in errors[:20]]
    left = vault.parent
    if left != repo and left.is_dir() and left != dest.parent:
        rest = sorted(p.name for p in left.iterdir())
        if rest:
            lines.append(f'move: {left.relative_to(repo).as_posix()}/ still holds {", ".join(rest)}')
        else:
            left.rmdir()  # nothing of anyone's is left in it
    lines.append(f'move: now update what names the old folder: a `--vault {old}` in your scripts, and the block in AGENTS.md or CLAUDE.md '
                 '(`project-spec instructions --file ...` writes it again)')
    return lines


HISTORY_COMMITS = 30  # commits shown under Recent changes
HISTORY_PAGES = 80    # pages listed for one commit
_history_cache = {}


def page_pathspec(repo, vault):
    """Git pathspec for the vault's own pages (no generated files), and the prefix to strip from the paths Git prints."""
    rel = Path(os.path.relpath(vault, repo)).as_posix()
    if rel == '..' or rel.startswith('../'):
        return None, None
    prefix = '' if rel == '.' else rel + '/'
    return [f':(glob){prefix}**/*.md', f':(exclude,glob){prefix}AS-BUILT.md', f':(exclude,glob){prefix}GAPS.md',
            f':(exclude,glob){prefix}.knowledge/**'], prefix


def front_value(line):
    """The string a `key: "value"` frontmatter line holds, as the vault writes it (a JSON string)."""
    raw = line.split(':', 1)[1].strip()
    try:
        value = json.loads(raw)
    except ValueError:
        value = raw
    return value if isinstance(value, str) else ''


def shallow_commits(repo):
    """Commits whose parents a shallow clone left out. Empty in a full clone and outside Git."""
    found = run_git(repo, ['rev-parse', '--git-path', 'shallow'])
    if found.returncode:
        return set()
    try:
        return set((repo / os.fsdecode(found.stdout).strip()).read_text(encoding='ascii').split())
    except (OSError, UnicodeDecodeError):
        return set()


def vault_history(repo, vault):
    """Recent commits that touched vault pages, newest first: sha, date, subject and what happened to each page.

    A page entry carries `was` and `now` when its summary (or, failing that, its title) changed in that commit.
    Empty outside a Git work tree. Cached per HEAD, because every page load asks for it.
    """
    spec, prefix = page_pathspec(repo, vault)
    if spec is None:
        return []
    head = run_git(repo, ['rev-parse', 'HEAD'])
    if head.returncode:
        return []
    key = (str(repo), str(vault), head.stdout.strip())
    if key in _history_cache:
        return _history_cache[key]
    # Git prints paths from the top of the work tree, which may be above the repository folder given here.
    top = run_git(repo, ['rev-parse', '--show-prefix']).stdout.decode(errors='replace').strip()
    prefix = top + prefix
    # A marker nobody could have written into a commit message or a page beforehand separates the commits.
    marker = '\x01' + os.urandom(12).hex() + '\x01'
    try:
        log = run_git(repo, ['-c', 'core.quotepath=off', 'log', f'-n{HISTORY_COMMITS}', '--date=short', '--no-color',
                              '--no-renames', '-p', '-U0', f'--format={marker}%H%x02%ad%x02%s', '--', *spec],
                      timeout=20)
    except subprocess.TimeoutExpired:
        return []
    if log.returncode:
        return []
    commits, boundary = [], shallow_commits(repo)
    for chunk in log.stdout.decode('utf-8', errors='replace').split(marker)[1:]:
        header, _, body = chunk.partition('\n')
        sha, date, subject = (header.split('\x02', 2) + ['', ''])[:3]
        if sha in boundary:  # its parents were not fetched, so Git would show every page as added
            continue
        subject = CONTROL.sub('', subject)
        pages, page = [], None
        for line in body.split('\n'):
            if line.startswith('diff --git '):
                name = line.rsplit(' b/', 1)[-1]
                page = {'path': name[len(prefix):], 'status': 'changed', 'fields': {}} if name.startswith(prefix) else None
                if page:
                    pages.append(page)
            elif page is None:
                continue
            elif line.startswith('new file mode'):
                page['status'] = 'added'
            elif line.startswith('deleted file mode'):
                page['status'] = 'removed'
            elif line[:1] in '+-' and line[1:].startswith(('summary:', 'title:')):
                field = line[1:].split(':', 1)[0]
                page['fields'].setdefault(field, {})['now' if line[0] == '+' else 'was'] = front_value(line[1:])
        for page in pages:
            fields = page.pop('fields')
            change = next((fields[f] for f in ('summary', 'title') if fields.get(f, {}).get('was') != fields.get(f, {}).get('now')), {})
            if page['status'] == 'changed' and change.get('was') and change.get('now'):
                page['was'], page['now'] = change['was'], change['now']
        if pages:
            commits.append({'sha': sha, 'date': date, 'subject': subject, 'pages': pages[:HISTORY_PAGES], 'more': max(0, len(pages) - HISTORY_PAGES)})
    _history_cache.clear()
    _history_cache[key] = commits
    return commits


_added_cache = {}


def added_dates(repo, vault):
    """The day each vault page was first committed, by its path in the vault. Empty outside a Git work tree.

    A gap's own `created` property wins over this; the history only answers for pages written before that property
    existed. A renamed page counts from the rename. Cached per HEAD, because every page load asks for it.
    """
    spec, prefix = page_pathspec(repo, vault)
    head = run_git(repo, ['rev-parse', 'HEAD']) if spec else None
    if spec is None or head.returncode:
        return {}
    key = (str(repo), str(vault), head.stdout.strip())
    if key not in _added_cache:
        top = run_git(repo, ['rev-parse', '--show-prefix']).stdout.decode(errors='replace').strip()
        try:
            log = run_git(repo, ['-c', 'core.quotepath=off', 'log', '--date=short', '--no-color', '--no-renames', '--diff-filter=A',
                                  '--name-only', '--format=%x01%H%x02%ad', '--', *spec], timeout=20)
        except subprocess.TimeoutExpired:
            return {}
        found, boundary = {}, shallow_commits(repo)
        for chunk in (log.stdout.decode('utf-8', errors='replace').split('\x01')[1:] if not log.returncode else []):
            header, _, names = chunk.partition('\n')
            sha, _, date = header.partition('\x02')
            if sha in boundary:  # its parents were not fetched, so every page looks added there
                continue
            for name in names.split('\n'):
                if name.startswith(top + prefix):
                    found[name[len(top + prefix):]] = date.strip()  # newest first, so the oldest commit has the last word
        _added_cache[key] = found
    return _added_cache[key]


def vault_pending(repo, vault):
    """Vault pages with uncommitted changes: [{path, status}], empty outside Git."""
    spec, prefix = page_pathspec(repo, vault)
    if spec is None:
        return []
    status = run_git(repo, ['-c', 'core.quotepath=off', 'status', '--porcelain=v1', '-z', '--untracked-files=all', '--no-renames', '--', *spec])
    if status.returncode:
        return []
    top = run_git(repo, ['rev-parse', '--show-prefix']).stdout.decode(errors='replace').strip()
    pending = []
    for item in status.stdout.split(b'\0'):
        text = os.fsdecode(item)
        name = text[3:]
        name = name[len(top):] if name.startswith(top) else name
        if len(text) > 3 and name.startswith(prefix):
            code = text[:2]
            pending.append({'path': name[len(prefix):],
                            'status': 'added' if '?' in code or 'A' in code else 'removed' if 'D' in code else 'changed'})
    return sorted(pending, key=lambda p: p['path'])


def map_state(vault):
    """How far the map has got, from the inventory file: its features by state. None when the vault has no such file."""
    try:
        text = (vault / '.knowledge' / 'inventory.md').read_text(encoding='utf-8')
    except OSError:
        return None
    states = [m.group(1).lower() for m in INVENTORY_HEAD.finditer(text)]
    return {'finished': states.count('finished'), 'inProgress': states.count('in progress'), 'notStarted': states.count('not started')}


def review_of(note):
    """The topic a run page is a review of: its `review` property, else its name (<date>-review-<topic>.md), else ''."""
    if note['meta']['type'] != 'run':
        return ''
    named = REVIEW_FILE.search(note['path'])
    return (note['meta'].get('review', '').strip() or (named.group(1) if named else '')).lower()


def open_gaps(notes):
    """The gaps that wait for somebody: not closed, and not put off by a person (deferred)."""
    return [n for n in notes if n['meta']['type'] == 'gap' and n['state'] not in CLOSED and n['state'] != 'deferred']


def reviews_state(notes):
    """One entry per review the skill knows and per review a run page names: its latest run and the open gaps of its topic."""
    last = {}
    for note in notes:
        key = review_of(note)
        if key and (key not in last or note['meta']['updated'] > last[key]['meta']['updated']):
            last[key] = note
    out = []
    for key in [*REVIEWS, *sorted(set(last) - set(REVIEWS))]:
        topic, run = REVIEW_TOPICS.get(key, key), last.get(key)
        ticks = TICK.findall(run['body']) if run else []
        done = sum(1 for t in ticks if t != ' ')
        out.append({'review': key, 'topic': topic, 'run': run['path'] if run else '', 'on': run['meta']['updated'] if run else '',
                    'done': done, 'of': len(ticks),
                    'finished': bool(run) and done == len(ticks) and run['meta']['status'] != 'partial',
                    'openGaps': sum(1 for g in open_gaps(notes) if g['meta'].get('topic') == topic),
                    'ownGaps': sum(1 for g in open_gaps(notes) if g['meta'].get('review', '').lower() == key)})
    return out


def priority_rank(meta):
    value = meta.get('priority', '').strip().lower()
    digit = re.fullmatch(r'p?([0-4])', value)
    if not value:
        return 6
    return int(digit.group(1)) if digit else {'critical': 0, 'urgent': 0, 'highest': 0, 'high': 1, 'medium': 2, 'normal': 2, 'low': 3, 'lowest': 4}.get(value, 5)


def summary_lines(repo, vault, notes, warnings):
    """The state of a vault in a few lines, for an agent asked "what is the status of the spec"."""
    def count(kind):
        return sum(1 for n in notes if n['meta']['type'] == kind)

    gaps = [n for n in notes if n['meta']['type'] == 'gap']
    prefix = Path(os.path.relpath(vault, repo)).as_posix() + '/'
    lines = [f"spec: {prefix[:-1]}; {count('area')} areas, {count('note')} feature and reference pages, {len(gaps)} gaps"]
    state = map_state(vault)
    if state is None:
        lines.append('map: no inventory file, so how much of the product is mapped is not recorded')
    else:
        total = sum(state.values())
        done = f" ({round(100 * state['finished'] / total)}%)" if total else ''
        lines.append(f"map: {state['finished']} of {total} features finished{done}, {state['inProgress']} in progress, {state['notStarted']} not started")
    partial = sum(1 for n in notes if n['meta']['type'] in ('note', 'area') and n['meta']['status'] == 'partial')
    stale = sum(1 for n in notes if n['meta']['type'] in ('note', 'area') and n['stale'])
    lines.append(f'pages: {partial} partial, {stale} with code changed since the last check')
    by_state = {s: sum(1 for g in gaps if g['state'] == s) for s in STATE_ORDER}
    closed = sum(by_state[s] for s in CLOSED)
    lines.append(f"gaps: {len(gaps) - closed - by_state['deferred']} open (needs recheck {by_state['needs-recheck']}, "
                 f"needs decision {by_state['needs-decision']}, accepted {by_state['accepted']}), {by_state['deferred']} deferred, {closed} closed")
    topics = []
    for topic in [*TOPICS, '']:
        mine = [g for g in open_gaps(notes) if g['meta'].get('topic', '') == topic]
        if mine:
            high = sum(1 for g in mine if priority_rank(g['meta']) <= 1)
            topics.append(f"{topic or 'no topic'} {len(mine)}" + (f' ({high} high)' if high else ''))
    if topics:
        lines.append('open gaps by topic: ' + ', '.join(topics))
    ranks = [priority_rank(g['meta']) for g in open_gaps(notes)]
    by_priority = [f'{name} {count}' for name, count in (('high', sum(r <= 1 for r in ranks)), ('medium', ranks.count(2)),
                                                          ('low', sum(r in (3, 4) for r in ranks)), ('other', ranks.count(5)),
                                                          ('none', ranks.count(6))) if count]
    if by_priority:
        lines.append('open gaps by priority: ' + ', '.join(by_priority))
    lines.append('reviews:')
    for r in reviews_state(notes):
        if not r['run']:
            text = 'not run'
        else:
            text = ('last run ' if r['finished'] else 'started ') + r['on']
            if r['of']:
                text += f", {r['done']} of {r['of']} feature{'' if r['of'] == 1 else 's'}" + ('' if r['finished'] else ', not finished')
            text += f"; {prefix}{r['run']}"
        own = f"; {r['ownGaps']} open gap{'' if r['ownGaps'] == 1 else 's'} written by it" if r['ownGaps'] else ''
        lines.append(f"  {r['review']:<11}{text}; {r['openGaps']} open gap{'' if r['openGaps'] == 1 else 's'} with topic {r['topic']}{own}")
    return lines


def gap_lines(notes, state='open', topic='', priority='', area='', prefix='', review=''):
    """The gaps a filter leaves, the most urgent first: state, priority, topic, file, title."""
    wanted = []
    for g in (n for n in notes if n['meta']['type'] == 'gap'):
        m = g['meta']
        if state == 'open' and (g['state'] in CLOSED or g['state'] == 'deferred') or state == 'closed' and g['state'] not in CLOSED:
            continue
        if state not in ('open', 'closed', 'all') and g['state'] != state:
            continue
        if topic and (m.get('topic', '') or 'none') != topic:
            continue
        if priority and (m.get('priority', '').strip().lower() or 'none') != priority.lower():
            continue
        if area and area not in m['areas']:
            continue
        if review and (m.get('review', '').lower() or 'none') != review.lower():
            continue
        wanted.append(g)
    wanted.sort(key=lambda g: (STATE_ORDER.index(g['state']), priority_rank(g['meta']), g['meta']['title']))
    lines = [f"{g['state']:<15}{g['meta'].get('priority', '') or '-':<8}{g['meta'].get('topic', '') or '-':<11}{prefix}{g['path']}  {g['meta']['title']}"
             for g in wanted]
    return lines + [f'gaps: {len(wanted)} listed']


def shown_notes(notes):
    """The pages the viewer can show: every page that could be read. Of two pages with one id it shows the first."""
    seen, out = set(), []
    for note in notes:
        if note['meta']['id'] not in seen:
            seen.add(note['meta']['id'])
            out.append(note)
    return out


def page_payload(repo, vault, notes, edges, warnings, sources=True, errors=()):
    notes = shown_notes(notes)
    files = cited_files(repo, vault, notes)[0] if sources else {}
    graph, first = graph_of(notes, edges, warnings), added_dates(repo, vault)
    for node, note in zip(graph['nodes'], notes):
        # When a gap appeared: the day its page says, else the day the page was first committed, else unknown (a new page).
        node['added'] = note['meta'].get('created', '') or first.get(note['path'], '') if note['meta']['type'] == 'gap' else ''
    return graph | {
        'errors': list(errors),  # what `check` reports; the pages are shown all the same, and the viewer lists these
        'vaultPath': Path(os.path.relpath(vault, repo)).as_posix(), 'files': files, 'map': map_state(vault),
        'history': vault_history(repo, vault), 'pending': vault_pending(repo, vault)}


def live_page(repo, vault):
    """The viewer for the vault as it is on disk right now, with what `check` reports listed in it.

    One wrong page must not hide the rest of the spec, so only a vault with no page that can be read is answered
    with a bare list of what stops it from loading."""
    try:
        notes, edges, errors, warnings, _ = load_vault(repo, vault)
    except (OSError, ValueError) as exc:
        notes, errors = [], [str(exc)]
    if errors and not notes:
        items = ''.join(f'<li>{html.escape(message)}</li>' for message in errors)
        return ('<!doctype html><meta charset="utf-8"><title>Spec cannot be shown</title>'
                '<body style="font:15px/1.5 system-ui,sans-serif;max-width:860px;margin:48px auto;padding:0 20px">'
                f'<h1>The spec has {len(errors)} error{"s" if len(errors) != 1 else ""}</h1>'
                '<p>Fix the pages below (the <code>check</code> command prints the same list), then reload.</p>'
                f'<ul>{items}</ul></body>')
    return viewer_html(page_payload(repo, vault, notes, edges, warnings, errors=errors) | {'live': True})


def source_base(value, commit):
    """The address `--source-url` names, with `{commit}` filled in. Raises ValueError with the reason when it cannot be used."""
    if CONTROL.search(value) or ' ' in value or not re.match(r'https?://[^/]', value, re.I):
        raise ValueError('--source-url must be an http(s) address, e.g. https://github.com/OWNER/REPO/blob/{commit}')
    if '{commit}' in value and not commit:
        raise ValueError('--source-url names {commit}, but --repo is not a Git work tree with a commit')
    return value.replace('{commit}', commit).rstrip('/')


def built_page(repo, vault, notes, edges, warnings, with_sources=False, source_url='', errors=()):
    """The viewer as one file to put on a server: the vault as it is now, with nothing read later.

    The text of cited repository files is left out unless asked for, because the file may be shown to people
    who cannot read the repository. Returns (html, payload).
    """
    head = run_git(repo, ['rev-parse', 'HEAD'])
    commit = '' if head.returncode else head.stdout.decode('ascii', errors='replace').strip()
    payload = page_payload(repo, vault, notes, edges, warnings, with_sources, errors) | {
        'built': True, 'commit': commit, 'sourceUrl': source_base(source_url, commit) if source_url else ''}
    return viewer_html(payload), payload


def make_server(repo, vault, port):
    """A read-only viewer on this machine only. Each page load reads the vault and the cited files again."""
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            # The page carries source code, so answer only when addressed as this machine (no DNS rebinding).
            host = (self.headers.get('Host') or '').rsplit(':', 1)[0].strip('[]')
            if host not in ('127.0.0.1', 'localhost', '::1'):
                return self.send_error(403)
            if urlsplit(self.path).path not in ('/', '/index.html'):
                return self.send_error(404)
            body = live_page(repo, vault).encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('Content-Security-Policy', "default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'")
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    return ThreadingHTTPServer(('127.0.0.1', port), Handler)


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=['check', 'snapshot', 'serve', 'build', 'move', 'summary', 'gaps'])
    parser.add_argument('--repo', required=True, type=Path)
    parser.add_argument('--vault', type=Path, help='default: the single vault in the repository, a folder with 00-index.md')
    parser.add_argument('--strict', action='store_true', help='fail check when freshness warnings exist')
    parser.add_argument('--port', type=int, default=8757, help='serve: port on 127.0.0.1 (another free port is used if it is taken)')
    parser.add_argument('--open', action='store_true', help='serve: open the page in the default browser')
    parser.add_argument('--out', type=Path, help='build: the HTML file to write, outside the vault')
    parser.add_argument('--to', type=Path, metavar='DIR', help='move: the folder of the repository the vault moves to')
    parser.add_argument('--state', default='open', help='gaps: open (default; deferred gaps are left out), closed, all, or one state such as needs-decision or deferred')
    parser.add_argument('--topic', default='', help='gaps: one topic, or "none" for gaps without one')
    parser.add_argument('--priority', default='', help='gaps: one priority, or "none" for gaps without one')
    parser.add_argument('--area', default='', help='gaps: the id of one area')
    parser.add_argument('--review', default='', help='gaps: the review that wrote the gap, or "none" for gaps no review wrote')
    parser.add_argument('--viewer', type=Path, metavar='FILE',
                        help='serve, build: a page of your own instead of the viewer; it gets the data where it says __KNOWLEDGE_DATA__')
    parser.add_argument('--with-sources', action='store_true', help='build: include the text of the repository files the pages cite')
    parser.add_argument('--source-url', default='', help='build: where a cited file can be read, e.g. https://github.com/OWNER/REPO/blob/{commit}')
    parser.add_argument('--allow-missing-sources', action='store_true',
                        help='build: do not stop when a cited file is not there, for a build that sees only part of the repository')
    parser.add_argument('--ignore-dirty', action='store_true',
                        help='check: do not count freshness warnings for sources with uncommitted changes (needs a Git work tree)')
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--all', action='store_true')
    group.add_argument('--notes', nargs='+')
    args = parser.parse_args(argv)
    if args.strict and args.command != 'check':
        parser.error('--strict is only for check')
    if args.ignore_dirty and args.command != 'check':
        parser.error('--ignore-dirty is only for check')
    if args.open and args.command != 'serve':
        parser.error('--open is only for serve')
    if args.command == 'build' and not args.out:
        parser.error('build requires --out FILE')
    if args.command != 'build' and (args.out or args.with_sources or args.source_url or args.allow_missing_sources):
        parser.error('--out, --with-sources, --source-url and --allow-missing-sources are only for build')
    if args.command == 'snapshot' and not (args.all or args.notes):
        parser.error('snapshot requires --all or --notes')
    if args.command != 'snapshot' and (args.all or args.notes):
        parser.error('--all and --notes are only for snapshot')
    repo = args.repo.resolve()
    if not repo.is_dir():
        parser.error('repo must be an existing directory')
    vault = args.vault.resolve() if args.vault else find_vault(repo)
    if not vault.is_dir():
        parser.error('repo and vault must be existing directories')
    if args.command != 'gaps' and (args.state != 'open' or args.topic or args.priority or args.area or args.review):
        parser.error('--state, --topic, --priority, --area and --review are only for gaps')
    if args.state not in ('open', 'closed', 'all', *STATE_ORDER):
        parser.error('--state must be open, closed, all or one of ' + ', '.join(STATE_ORDER))
    if args.viewer and args.command not in ('serve', 'build'):
        parser.error('--viewer is only for serve and build')
    if (args.command == 'move') != bool(args.to):
        parser.error('move requires --to DIR' if args.command == 'move' else '--to is only for move')
    if args.command == 'move':
        try:
            print('\n'.join(move_vault(repo, vault, args.to if args.to.is_absolute() else repo / args.to)))
        except (OSError, ValueError) as exc:
            parser.error(str(exc))
        return 0
    if args.command in ('serve', 'build'):
        global VIEWER
        VIEWER = args.viewer.resolve() if args.viewer else None
        try:
            viewer_template()
        except (OSError, ValueError) as exc:
            parser.error(str(exc))
    if args.command == 'serve':
        try:
            server = make_server(repo, vault, args.port)
        except OSError:  # the usual port is taken
            server = make_server(repo, vault, 0)
        url = f'http://127.0.0.1:{server.server_address[1]}/'
        print(f'serve: {url} shows {vault} as it is on disk; reload the page after a change, Ctrl+C to stop', flush=True)
        if args.open:
            import webbrowser
            webbrowser.open(url)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            server.server_close()
        return 0
    dirty = None
    if args.ignore_dirty:
        dirty = uncommitted_paths(repo)
        if dirty is None:
            parser.error('--ignore-dirty needs --repo to be a Git work tree')
    report = {}
    absent = [] if args.allow_missing_sources else None
    notes, edges, errors, warnings, baseline = load_vault(repo, vault, args.command != 'snapshot', dirty, report, absent)
    ignored = []
    if args.command == 'snapshot' and args.notes:
        # Only the selected pages must be valid; errors elsewhere are counted, not blocking.
        wanted = set(args.notes)
        by_id = {n['meta']['id']: n['path'] for n in notes}
        by_id.update({ident: page for page, ident in report['failed'].items() if ident})
        selected = {by_id[i] for i in wanted if i in by_id}
        blocking = []
        for message in errors:
            page = error_page(message)
            if page is None or page in selected or any(f'duplicate id {i}' in message for i in wanted):
                blocking.append(message)
            else:
                ignored.append(message)
        # A selected page that leans on a page which failed validation cannot be accepted yet.
        blocking += [m for m in report['cascade'] if error_page(m) in selected]
        errors = blocking
        missing = wanted - by_id.keys()
        if missing:
            errors.append('Unknown note IDs: ' + ', '.join(sorted(missing)))
    if args.command in ('summary', 'gaps'):
        # A report, not a check: it still answers when some pages are broken, and says that they are left out.
        lines = (summary_lines(repo, vault, notes, warnings) if args.command == 'summary'
                 else gap_lines(notes, args.state, args.topic, args.priority, args.area,
                                Path(os.path.relpath(vault, repo)).as_posix() + '/', args.review))
        if errors:
            pages = len({error_page(m) for m in errors if error_page(m)})
            lines.append(f'check: {len(errors)} errors on {pages} pages, which are left out above; run check to see them')
        print('\n'.join(lines))
        return 0
    for message in errors:
        print('ERROR:', message, file=sys.stderr)
    for message in warnings:
        print('WARNING:', message, file=sys.stderr)
    counted = [w for w in warnings if not w.endswith(UNCOUNTED)]
    # A built page with errors in it is still the spec, and it lists them. `check` is the gate; build only shows.
    shown_anyway = args.command == 'build' and errors and notes
    if errors and not shown_anyway:
        pages = len({error_page(m) for m in errors if error_page(m)})
        print(f'{args.command}: failed, {len(errors)} errors on {pages} pages', file=sys.stderr)
    if (errors and not shown_anyway) or (args.strict and counted):
        return 1
    if ignored:
        print(f'{args.command}: {len(ignored)} errors on {len({error_page(m) for m in ignored if error_page(m)})} other pages do not block this snapshot (run check to see them)', file=sys.stderr)
    if args.command == 'build':
        out = Path(os.path.abspath(args.out))
        if out.is_dir() or out.resolve().is_relative_to(vault):
            parser.error('--out must be a file outside the vault: nothing is generated into the vault')
        try:
            page, payload = built_page(repo, vault, notes, edges, warnings, args.with_sources, args.source_url, errors)
        except ValueError as exc:
            parser.error(str(exc))
        atomic_write(out, page)
        files = len(payload['files'])
        print(f'build: wrote {out} ({len(page.encode("utf-8")) // 1024} kB), {len(payload["nodes"])} notes, {len(warnings)} warnings'
              + (f', commit {payload["commit"][:7]}' if payload['commit'] else ''))
        if errors:
            pages = len({error_page(m) for m in errors if error_page(m)})
            print(f'build: {len(errors)} errors on {pages} pages are listed on the page, under Recent changes; '
                  'the pages that could be read are shown all the same. Run check first where a wrong page must stop the build')
        print('build: ' + (f'the text of {files} cited source files is inside the file; show it only to people who may read the repository'
                           if args.with_sources else 'cited source files are named but their text is not included (--with-sources adds it)'))
        if absent:
            names = sorted(set(absent))
            print(f'build: {len(names)} cited files are not in this folder, so nobody compared them with the pages: ' + ', '.join(names[:8]) + (' ...' if len(names) > 8 else ''))
        if shallow_commits(repo):
            print('build: this is a shallow clone, so the Changes page starts at the first commit that was fetched in full; fetch the whole history to show more')
        return 0
    if args.command == 'snapshot':
        for note in notes:
            meta = note['meta']
            if args.all or meta['id'] in args.notes:
                hashes = {}
                for source in meta['sources']:
                    path = safe_path(repo, source)
                    if path.is_file():
                        hashes[source] = hashlib.sha256(path.read_bytes()).hexdigest()
                baseline[meta['id']] = hashes
        dest = output_path(vault, '.knowledge/sources.json')
        write_json(dest, dict(sorted(baseline.items())))
    uncounted = len(warnings) - len(counted)
    print(f'{args.command}: {len(notes)} notes, {len(edges)} links, {len(warnings)} warnings' + (f' ({uncounted} uncommitted, not counted)' if uncounted else ''))
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (OSError, ValueError) as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        sys.exit(1)
