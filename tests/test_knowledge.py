import importlib.util
import json
import os
import re
import subprocess
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path

SPEC = importlib.util.spec_from_file_location('knowledge', Path(__file__).resolve().parent.parent / 'skills/project-knowledge/scripts' / 'knowledge.py')
k = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(k)


class Fixture(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.repo = self.root / 'repo'
        self.vault = self.root / 'vault'
        self.repo.mkdir()
        self.vault.mkdir()
        (self.repo / 'source.txt').write_text('evidence', encoding='utf-8')
        self.note('areas/a.md', 'a', 'area', areas=[])
        self.note('00-index.md', 'index', 'index', areas=[], body='[[areas/a]]')
        self.note('notes/n.md', 'n', 'note', sources=['source.txt'], body='Привет [[areas/a|область]] `[[missing]]`\n```\n[[missing]]\n```')

    def tearDown(self):
        self.temp.cleanup()

    def note(self, path, ident, ptype='note', areas=None, sources=None, body='', status='current', **extra):
        meta = {'id': ident, 'title': 'Тест ' + ident, 'type': ptype, 'status': status,
                'areas': ['a'] if areas is None else areas, 'sources': sources or [], 'updated': '2026-11-14'}
        if status is None:
            del meta['status']
        meta.update(extra)
        file = self.vault / path
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text('---\n' + ''.join(f'{key}: {json.dumps(value, ensure_ascii=False)}\n' for key, value in meta.items()) + '---\n' + body, encoding='utf-8')

    def run_cli(self, *args):
        out, err = StringIO(), StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            status = k.main([*args, '--repo', str(self.repo), '--vault', str(self.vault)])
        return status, out.getvalue(), err.getvalue()


class KnowledgeTests(Fixture):
    def test_links_and_duplicates(self):
        self.assertEqual(self.run_cli('check')[0], 0)
        self.note('other/a.md', 'other', 'area', areas=[])
        self.note('notes/n.md', 'n', sources=['source.txt'], body='[[a]] [[absent]]')
        self.note('notes/duplicate.md', 'n', sources=['source.txt'])
        status, _, err = self.run_cli('check')
        self.assertEqual(status, 1)
        self.assertIn('ambiguous wikilink a', err)
        self.assertIn('missing wikilink absent', err)
        self.assertIn('duplicate id n', err)

    def test_missing_and_escaping_source(self):
        self.note('notes/n.md', 'n', sources=['missing', '../outside', '.env'])
        status, _, err = self.run_cli('check')
        self.assertEqual(status, 1)
        self.assertIn('missing or not a file', err)
        self.assertIn('stay inside', err)
        self.assertIn('credential', err)
        (self.repo / 'escape').symlink_to(self.root, target_is_directory=True)
        self.note('notes/n.md', 'n', sources=['escape/secret'])
        self.assertIn('outside', self.run_cli('check')[2])

    def test_obsidian_internal_and_trash_notes_are_ignored(self):
        self.note('.trash/deleted.md', 'n', sources=['source.txt'])
        for name in ('.obsidian/plugins/example/README.md', '.knowledge/internal.md'):
            file = self.vault / name
            file.parent.mkdir(parents=True, exist_ok=True)
            file.write_text('not a vault note', encoding='utf-8')
        status, output, errors = self.run_cli('check')
        self.assertEqual(status, 0, errors)
        self.assertIn('3 notes', output)

    def test_credential_symlink_alias_is_rejected(self):
        (self.repo / '.env').write_text('secret', encoding='utf-8')
        (self.repo / 'innocent.txt').symlink_to(self.repo / '.env')
        self.note('notes/n.md', 'n', sources=['innocent.txt'])
        self.assertIn('credential source is forbidden', self.run_cli('check')[2])

    def test_output_symlinks_do_not_overwrite_canonical_note(self):
        original_script = k.__file__
        fake_script = self.root / 'skill/scripts/knowledge.py'
        fake_script.parent.mkdir(parents=True)
        (self.root / 'skill/assets').mkdir()
        (self.root / 'skill/assets/viewer.html').write_text('__KNOWLEDGE_DATA__', encoding='utf-8')
        k.__file__ = str(fake_script)
        note = self.vault / 'notes/n.md'
        original = note.read_bytes()
        try:
            (self.vault / '.knowledge').mkdir()
            snapshot = self.vault / '.knowledge/sources.json'
            snapshot.symlink_to(note)
            self.assertEqual(self.run_cli('snapshot', '--all')[0], 1)
            self.assertEqual(original, note.read_bytes())
            snapshot.unlink()
            (self.vault / '.knowledge').rmdir()
            (self.vault / '.knowledge').symlink_to(self.vault / 'notes', target_is_directory=True)
            with self.assertRaisesRegex(ValueError, 'output path contains symlink'):
                self.run_cli('snapshot', '--all')
            self.assertEqual(original, note.read_bytes())
        finally:
            k.__file__ = original_script

    def test_strict_check_and_command_boundaries(self):
        status, _, err = self.run_cli('check', '--strict')
        self.assertEqual(status, 1)
        self.assertIn('unbaselined source', err)
        self.assertEqual(self.run_cli('snapshot', '--all')[0], 0)
        self.assertEqual(self.run_cli('check', '--strict')[0], 0)
        (self.repo / 'source.txt').write_text('changed', encoding='utf-8')
        status, _, err = self.run_cli('check')
        self.assertEqual(status, 0)
        self.assertIn('changed source', err)
        status, _, err = self.run_cli('check', '--strict')
        self.assertEqual(status, 1)
        self.assertIn('changed source', err)
        for args in (('serve', '--strict'), ('snapshot', '--all', '--strict'),
                     ('serve', '--all'), ('serve', '--notes', 'n'), ('build',), ('clean',)):
            with self.subTest(args=args), self.assertRaises(SystemExit) as exc:
                self.run_cli(*args)
            self.assertEqual(exc.exception.code, 2)

    def test_conflict_groups_block_all_commands_but_prose_is_valid(self):
        self.note('notes/n.md', 'n', sources=['source.txt'], body='> quoted\n=======\n> still quoted')
        self.assertEqual(self.run_cli('check')[0], 0)
        path = self.vault / 'notes/n.md'
        path.write_text(path.read_text().replace('status: "current"', 'status: "partial"'))
        self.assertEqual(self.run_cli('check')[0], 0)
        for group in ('<<<<<<< ours\nleft\n=======\nright\n>>>>>>> theirs',
                      '```\n<<<<<<< ours\nleft\n||||||| base\nbase\n=======\nright\n>>>>>>> theirs\n```'):
            self.note('notes/n.md', 'n', sources=['source.txt'], body=group)
            for args in (('check',), ('snapshot', '--all')):
                with self.subTest(group=group, args=args):
                    status, _, err = self.run_cli(*args)
                    self.assertEqual(status, 1)
                    self.assertIn('unresolved Git conflict markers', err)
            self.assertFalse((self.vault / '.knowledge/sources.json').exists())
            self.assertFalse((self.vault / 'graph.html').exists())

    def test_real_git_conflict_with_custom_width(self):
        def git(*args, check=True):
            return subprocess.run(['git', '-C', str(self.root), *args], capture_output=True, text=True, check=check)
        # The vault is inside a disposable repository for a real Git merge.
        git('init', '-b', 'main')
        git('config', 'user.email', 'test@example.invalid')
        git('config', 'user.name', 'Test')
        (self.root / '.gitattributes').write_text('vault/notes/n.md conflict-marker-size=5\n')
        git('add', '.')
        git('commit', '-m', 'base')
        git('checkout', '-b', 'other')
        self.note('notes/n.md', 'n', sources=['source.txt'], body='other change')
        git('commit', '-am', 'other')
        git('checkout', 'main')
        self.note('notes/n.md', 'n', sources=['source.txt'], body='main change')
        git('commit', '-am', 'main')
        self.assertNotEqual(git('merge', 'other', check=False).returncode, 0)
        content = (self.vault / 'notes/n.md').read_text()
        self.assertIn('<<<<< HEAD', content)
        self.assertIn('=====\n', content)
        self.assertIn('>>>>> other', content)
        for args in (('check',), ('snapshot', '--all')):
            with self.subTest(args=args):
                status, _, err = self.run_cli(*args)
                self.assertEqual(status, 1)
                self.assertIn('unresolved Git conflict markers', err)
        self.assertFalse((self.vault / '.knowledge/sources.json').exists())
        self.assertFalse((self.vault / 'graph.html').exists())
        self.assertFalse(k.has_conflict_markers('> quoted\n=====\n> another quote'))
        self.assertFalse(k.has_conflict_markers('<<<<< ours\n=====\n>>>>>> theirs'))

    def test_real_default_conflict_with_operator_content(self):
        def git(*args, check=True):
            return subprocess.run(['git', '-C', str(self.root), *args], capture_output=True, text=True, check=check)
        git('init', '-b', 'main')
        git('config', 'user.email', 'test@example.invalid')
        git('config', 'user.name', 'Test')
        self.note('notes/n.md', 'n', sources=['source.txt'], body='base side')
        git('add', '.')
        git('commit', '-m', 'base')
        git('checkout', '-b', 'other')
        self.note('notes/n.md', 'n', sources=['source.txt'], body='<\nright side')
        git('commit', '-am', 'other')
        git('checkout', 'main')
        self.note('notes/n.md', 'n', sources=['source.txt'], body='left side')
        git('commit', '-am', 'main')
        git('checkout', 'other')
        self.assertNotEqual(git('merge', 'main', check=False).returncode, 0)
        content = (self.vault / 'notes/n.md').read_text()
        self.assertIn('<<<<<<< HEAD\n<\nright side', content)
        self.assertTrue(k.has_conflict_markers(content))
        for args in (('check',), ('snapshot', '--all')):
            status, _, err = self.run_cli(*args)
            self.assertEqual(status, 1, args)
            self.assertIn('unresolved Git conflict markers', err)
        self.assertFalse(k.has_conflict_markers('```\n<\n=\n>\n```'))
        self.assertTrue(k.has_conflict_markers('<<<<<<< HEAD\n< nested\n=======\nx\n>>>>>>> main'))

    def test_snapshot_freshness_and_build(self):
        self.assertEqual(self.run_cli('snapshot', '--all')[0], 0)
        baseline = (self.vault / '.knowledge/sources.json').read_bytes()
        self.assertEqual(self.run_cli('snapshot', '--all')[0], 0)
        self.assertEqual(baseline, (self.vault / '.knowledge/sources.json').read_bytes())
        (self.repo / 'source.txt').write_text('changed', encoding='utf-8')
        self.assertIn('changed source', self.run_cli('check')[2])
        self.note('notes/n.md', 'n', sources=['source.txt'], body='Привет </script>')
        template = Path(k.__file__).parent.parent / 'assets/viewer.html'
        # Build is tested with an isolated temporary template, never the shared asset.
        original = k.__file__
        fake_script = self.root / 'skill/scripts/knowledge.py'
        fake_script.parent.mkdir(parents=True)
        (self.root / 'skill/assets').mkdir()
        (self.root / 'skill/assets/viewer.html').write_text('<script>const x=__KNOWLEDGE_DATA__</script>', encoding='utf-8')
        k.__file__ = str(fake_script)
        try:
            html = k.live_page(self.repo.resolve(), self.vault.resolve())
        finally:
            k.__file__ = original
        self.assertEqual(baseline, (self.vault / '.knowledge/sources.json').read_bytes())
        self.assertFalse((self.vault / 'graph.html').exists())
        self.assertIn('Привет', html)
        self.assertIn('\\u003c/script\\u003e', html)
        notes, edges, _, warnings, _ = k.load_vault(self.repo.resolve(), self.vault.resolve())
        self.assertTrue(next(n for n in k.graph_of(notes, edges, warnings)['nodes'] if n['id'] == 'n')['stale'])
        self.assertFalse((self.vault / '.knowledge/graph.json').exists(), 'nothing is generated into the vault')


GAP_BODY = ''.join(f'## {name}\n\ntext\n\n' for name in k.GAP_SECTIONS)


def section_body(**texts):
    return ''.join(f'## {name}\n\n{texts.get(name, "text")}\n\n' for name in k.GAP_SECTIONS)


class GapLayerTests(Fixture):
    GAP = {'kind': 'product-gap', 'recheck': 'not-checked', 'decision': 'open'}

    def gap(self, ident='g', body=GAP_BODY, **props):
        merged = {**self.GAP, **props}
        status = merged.pop('status', None)
        self.note(f'gaps/{ident}.md', ident, 'gap', body=body, status=status, **merged)

    def errors(self):
        status, _, err = self.run_cli('check')
        return status, err

    def assertInvalid(self, fragment):
        status, err = self.errors()
        self.assertEqual(status, 1, err)
        self.assertIn(fragment, err)

    def build(self):
        """What the viewer is given for this vault, saved as .knowledge/graph.json so a test can read it. (status, out, err)"""
        repo, vault = self.repo.resolve(), self.vault.resolve()
        notes, edges, errors, warnings, _ = k.load_vault(repo, vault)
        if errors:
            return 1, '', '\n'.join(errors)
        target = vault / '.knowledge/graph.json'
        target.parent.mkdir(exist_ok=True)
        target.write_text(json.dumps(k.graph_of(notes, edges, warnings), ensure_ascii=False), encoding='utf-8')
        return 0, '', ''

    def test_status_rules_per_type(self):
        for kind, status, ok in [('note', 'current', True), ('note', 'planned', False), ('area', 'planned', False),
                                 ('note', 'unverified', False), ('note', 'conflict', False),
                                 ('run', 'planned', True), ('index', 'planned', True), ('run', 'unverified', False)]:
            with self.subTest(kind=kind, status=status):
                path = self.vault / 'notes/x.md'
                path.unlink(missing_ok=True)
                self.note('notes/x.md', 'x', kind, sources=['source.txt'], status=status,
                          areas=[] if kind in {'run', 'index'} else None)
                self.assertEqual(self.errors()[0], 0 if ok else 1, self.errors()[1])
        self.note('notes/x.md', 'x', sources=['source.txt'], status='unverified')
        self.assertInvalid('record it as a gap')

    def test_non_gap_requires_status_and_gap_forbids_it(self):
        self.note('notes/x.md', 'x', status=None)
        self.assertInvalid('missing properties: status')
        (self.vault / 'notes/x.md').unlink()
        self.gap(status='current')
        self.assertInvalid('gaps use recheck and decision')

    def test_valid_gap_and_plan_pass_strict_check(self):
        self.gap()
        self.gap('g2', recheck='confirmed', rechecked_by='agent', rechecked_on='2026-11-15', decision='accepted',
                 decided_by='Ann', decided_on='2026-11-15', priority='high', confidence='medium',
                 body=section_body(Recheck='ran it', Decision='Ann said yes'))
        self.note('plans/p.md', 'p', 'plan', status='planned', gap='g2')
        self.run_cli('snapshot', '--all')
        status, err = self.errors()
        self.assertEqual(status, 0, err)
        self.assertEqual(self.run_cli('check', '--strict')[0], 0)

    # gap properties
    def test_gap_property_rules(self):
        cases = [
            ({'kind': 'wish'}, 'kind must be one of'),
            ({'recheck': 'maybe'}, 'recheck must be one of'),
            ({'decision': 'later'}, 'decision must be one of'),
            ({'recheck': 'confirmed'}, 'rechecked_by is required'),
            ({'recheck': 'confirmed', 'rechecked_by': 'agent'}, 'rechecked_on is required'),
            ({'recheck': 'confirmed', 'rechecked_by': ' ', 'rechecked_on': '2026-11-15'}, 'rechecked_by must name'),
            ({'recheck': 'confirmed', 'rechecked_by': 'agent', 'rechecked_on': '2026-13-45'}, 'rechecked_on'),
            ({'rechecked_by': 'Ann'}, "absent while recheck is 'not-checked'"),
            ({'rechecked_on': '2026-11-15'}, "absent while recheck is 'not-checked'"),
            ({'decision': 'accepted'}, 'decided_by is required'),
            ({'decision': 'rejected', 'decided_by': 'Ann'}, 'decided_on is required'),
            ({'decision': 'deferred', 'decided_by': 'agent', 'decided_on': '2026-11-15'}, 'agent may not decide'),
            ({'decision': 'accepted', 'decided_by': 'Ann', 'decided_on': 'yesterday'}, 'decided_on must be'),
            ({'decided_by': 'Ann'}, "absent while decision is 'open'"),
            ({'decided_on': '2026-11-15'}, "absent while decision is 'open'"),
            ({'decision': 'duplicate'}, 'duplicate_of is required'),
            ({'decision': 'duplicate', 'duplicate_of': 'g'}, 'different gap'),
            ({'decision': 'duplicate', 'duplicate_of': 'nope'}, 'not the id of an existing gap'),
            ({'decision': 'duplicate', 'duplicate_of': 'n'}, 'not the id of an existing gap'),
            ({'duplicate_of': 'other'}, "only valid when decision is 'duplicate'"),
            ({'priority': 3}, 'priority must be a string'),
        ]
        self.gap('other')
        for props, fragment in cases:
            with self.subTest(props=props):
                self.gap(**props)
                self.assertInvalid(fragment)
        (self.vault / 'gaps/g.md').unlink()
        self.assertEqual(self.errors()[0], 0)

    def test_duplicate_done_and_agent_bookkeeping_are_valid(self):
        self.gap('other')
        self.gap('g', decision='duplicate', duplicate_of='other')
        self.gap('h', decision='done', body=section_body(Decision='Closed: src/x implements it'))
        self.assertEqual(self.errors()[0], 0, self.errors()[1])

    def test_gap_only_properties_rejected_on_other_pages(self):
        self.note('notes/x.md', 'x', sources=['source.txt'], kind='conflict')
        self.assertInvalid('kind is only valid on gap pages')
        self.note('notes/x.md', 'x', sources=['source.txt'], gap='g')
        self.assertInvalid('gap is only valid on plan pages')

    # plans
    def test_plan_rules(self):
        self.gap('open-gap')
        self.gap('ok-gap', decision='done', body=section_body(Decision='seen in code'))
        for props, fragment in [({'gap': 'open-gap'}, "has decision 'open'"), ({'gap': 'missing'}, 'not the id of an existing gap'),
                                ({'gap': 'n'}, 'not the id of an existing gap'), ({'gap': ' '}, 'plan requires gap')]:
            with self.subTest(props=props):
                self.note('plans/p.md', 'p', 'plan', status='planned', **props)
                self.assertInvalid(fragment)
        self.note('plans/p.md', 'p', 'plan', status='planned', gap='ok-gap', areas=[])
        self.assertInvalid('plan requires an area')
        self.note('plans/p.md', 'p', 'plan', status='unverified', gap='ok-gap')
        self.assertInvalid('status must be one of')
        self.note('plans/p.md', 'p', 'plan', status='current', gap='ok-gap')
        self.assertEqual(self.errors()[0], 0, self.errors()[1])

    # body rules
    def test_spec_pages_cannot_link_to_gap_layer(self):
        self.gap()
        self.note('notes/n.md', 'n', sources=['source.txt'], body='see [[gaps/g]]')
        self.assertInvalid('link from the gap to this page instead')
        self.note('notes/n.md', 'n', sources=['source.txt'])
        self.note('areas/a.md', 'a', 'area', areas=[], body='[[g]]')
        self.assertInvalid('spec pages must not link to the gap layer')
        self.note('areas/a.md', 'a', 'area', areas=[])
        self.gap(body=GAP_BODY + 'link to [[notes/n]]')
        self.note('00-index.md', 'index', 'index', areas=[], body='[[areas/a]] [[gaps/g]]')
        self.assertEqual(self.errors()[0], 0, self.errors()[1])

    def test_plan_link_from_note_is_rejected(self):
        self.gap(decision='accepted', decided_by='Ann', decided_on='2026-11-15', body=section_body())
        self.note('plans/p.md', 'p', 'plan', status='planned', gap='g')
        self.note('notes/n.md', 'n', sources=['source.txt'], body='[[plans/p]]')
        self.assertInvalid('spec pages must not link')

    def test_gap_sections(self):
        names = k.GAP_SECTIONS
        self.gap(body=''.join(f'## {n}\ntext\n' for n in names[:-1]))
        self.assertInvalid("exactly one '## Decision' section (found 0)")
        self.gap(body=GAP_BODY + '## Gap\nagain\n')
        self.assertInvalid("exactly one '## Gap' section (found 2)")
        self.gap(body=GAP_BODY.replace('## Evidence', '### Evidence'))
        self.assertInvalid("'## Evidence' section (found 0)")
        # headings in code fences do not count, and order is free
        shuffled = ''.join(f'## {n}\ntext\n' for n in reversed(names))
        self.gap(body=shuffled + '```\n## Decision\n```\n')
        self.assertEqual(self.errors()[0], 0, self.errors()[1])
        self.gap(body=''.join(f'## {n}\ntext\n' for n in names[:-1]) + '```\n## Decision\n```\n')
        self.assertInvalid("(found 0)")

    def test_decision_and_recheck_sections_must_not_be_empty(self):
        self.gap(decision='rejected', decided_by='Ann', decided_on='2026-11-15', body=section_body(Decision=' '))
        self.assertInvalid('Decision section must say who decided')
        self.gap(recheck='not-reproduced', rechecked_by='Ann', rechecked_on='2026-11-15', body=section_body(Recheck=''))
        self.assertInvalid('Recheck section must say what was checked')
        self.gap(body=section_body(Decision='', Recheck=''))
        self.assertEqual(self.errors()[0], 0, self.errors()[1])
        self.gap(recheck='confirmed', rechecked_by='agent', rechecked_on='2026-11-15', body=section_body(Recheck='```\ncmd\n```'))
        self.assertEqual(self.errors()[0], 0, self.errors()[1])

    def test_sources_optional_on_gap_and_plan_but_required_on_current_note(self):
        self.gap()
        self.assertEqual(self.errors()[0], 0)
        self.note('notes/x.md', 'x', sources=[])
        self.assertInvalid('current note requires sources')

    # derived state and generated files
    def test_gap_state_table(self):
        base = {'kind': 'product-gap'}
        checked = {'recheck': 'confirmed', 'rechecked_by': 'agent', 'rechecked_on': '2026-11-15'}
        self.assertEqual(k.gap_state({**base, 'recheck': 'not-checked', 'decision': 'open'}), 'needs-recheck')
        for recheck in ('confirmed', 'not-reproduced'):
            self.assertEqual(k.gap_state({**base, 'recheck': recheck, 'decision': 'open'}), 'needs-decision')
        for decision in ('accepted', 'rejected', 'deferred', 'done', 'duplicate'):
            for recheck in k.RECHECKS:
                self.assertEqual(k.gap_state({'recheck': recheck, 'decision': decision}), decision)

    def test_viewer_data_carries_the_gap_fields(self):
        self.gap('open')
        self.gap('acc', recheck='confirmed', rechecked_by='Bob', rechecked_on='2026-11-15', decision='accepted',
                 decided_by='Ann', decided_on='2026-11-16', body=section_body())
        self.note('plans/p.md', 'p', 'plan', status='planned', gap='acc')
        self.assertEqual(self.build()[0], 0)
        nodes = {n['id']: n for n in json.loads((self.vault / '.knowledge/graph.json').read_text())['nodes']}
        fields = {'kind', 'recheck', 'recheckedBy', 'recheckedOn', 'decision', 'decidedBy', 'decidedOn', 'state', 'gap', 'layer'}
        self.assertTrue(all(fields <= n.keys() for n in nodes.values()))
        self.assertEqual((nodes['open']['state'], nodes['open']['status'], nodes['open']['layer']), ('needs-recheck', '', 'gap'))
        self.assertEqual((nodes['acc']['state'], nodes['acc']['recheckedBy'], nodes['acc']['decidedOn']), ('accepted', 'Bob', '2026-11-16'))
        self.assertEqual((nodes['p']['gap'], nodes['p']['layer'], nodes['p']['status']), ('acc', 'gap', 'planned'))
        self.assertEqual((nodes['n']['layer'], nodes['n']['state'], nodes['n']['kind']), ('spec', '', ''))
        self.assertEqual(nodes['index']['layer'], 'nav')

    def test_cited_files_are_repository_text_files_only(self):
        (self.repo / 'docs').mkdir()
        (self.repo / 'docs/plan.md').write_text('# План\n\n| a | b |\n', encoding='utf-8')
        (self.repo / 'logo.bin').write_bytes(b'\x00\x01')
        (self.repo / 'latin.txt').write_bytes(b'caf\xe9')
        (self.repo / '.env').write_text('SECRET=1', encoding='utf-8')
        (self.root / 'outside.txt').write_text('outside', encoding='utf-8')
        (self.repo / 'escape.txt').symlink_to(self.root / 'outside.txt')
        (self.repo / 'big.txt').write_text('line\n' * 100_000, encoding='utf-8')
        self.vault.rename(self.repo / 'vault')
        self.vault = self.repo / 'vault'
        self.note('notes/n.md', 'n', sources=['source.txt'], body=(
            '[plan](../../docs/plan.md#L3) [logo](../../logo.bin) [latin](../../latin.txt) [env](../../.env) '
            '[out](../../../outside.txt) [esc](../../escape.txt) [big](../../big.txt) [area](../areas/a.md) '
            '[web](https://example.com/x.md) [gone](../../missing.md) `[code](../../docs/hidden.md)`'))
        repo, vault = self.repo.resolve(), self.vault.resolve()
        notes, _, errors, _, _ = k.load_vault(repo, vault)
        self.assertEqual(errors, [])
        files, skipped = k.cited_files(repo, vault, notes)
        self.assertEqual(sorted(files), ['big.txt', 'docs/plan.md', 'source.txt'])
        self.assertEqual(files['docs/plan.md'], {'text': '# План\n\n| a | b |\n', 'truncated': False})
        self.assertEqual(files['source.txt']['text'], 'evidence')
        self.assertTrue(files['big.txt']['truncated'])
        self.assertLessEqual(len(files['big.txt']['text']), k.FILE_LIMIT)
        self.assertEqual(skipped, [])
        original = k.FILES_LIMIT
        k.FILES_LIMIT = 100
        try:
            files, skipped = k.cited_files(repo, vault, notes)
        finally:
            k.FILES_LIMIT = original
        self.assertEqual((sorted(files), skipped), (['docs/plan.md', 'source.txt'], ['big.txt']))

    def serve(self):
        import threading
        server = k.make_server(self.repo.resolve(), self.vault.resolve(), 0)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(lambda: (server.shutdown(), server.server_close(), thread.join(5)))
        return server.server_address[1]

    def fetch(self, port, path='/', host=None):
        import http.client
        connection = http.client.HTTPConnection('127.0.0.1', port, timeout=10)
        self.addCleanup(connection.close)
        connection.request('GET', path, headers={'Host': host} if host else {})
        response = connection.getresponse()
        return response.status, response.read().decode('utf-8'), dict(response.getheaders())

    def test_serve_shows_the_vault_as_it_is_on_disk(self):
        port = self.serve()
        status, page, headers = self.fetch(port)
        self.assertEqual(status, 200)
        self.assertEqual(headers['Content-Type'], 'text/html; charset=utf-8')
        self.assertEqual(headers['Cache-Control'], 'no-store')
        data = json.loads(re.search(r'<script id="knowledge-data" type="application/json">\s*(.*?)\s*</script>', page, re.S).group(1))
        self.assertTrue(data['live'])
        self.assertEqual(data['files']['source.txt']['text'], 'evidence')
        self.assertEqual(data['vaultPath'], '../vault')
        self.assertEqual(data['repoRoot'], str(self.repo.resolve()))
        self.assertEqual((data['history'], data['pending']), ([], []))
        self.assertEqual({n['id'] for n in data['nodes']}, {'a', 'index', 'n'})
        # nothing was written, and a change on disk shows on the next load without a build
        self.assertFalse((self.vault / 'graph.html').exists() or (self.vault / '.knowledge').exists())
        (self.repo / 'source.txt').write_text('changed </script>', encoding='utf-8')
        self.note('notes/new.md', 'new', sources=['source.txt'])
        page = self.fetch(port, '/index.html?x=1')[1]
        self.assertIn('"id": "new"', page)
        self.assertIn('changed \\u003c/script\\u003e', page)
        # only the page itself, and only when addressed as this machine
        self.assertEqual(self.fetch(port, '/notes/n.md')[0], 404)
        self.assertEqual(self.fetch(port, '/../repo/source.txt')[0], 404)
        self.assertEqual(self.fetch(port, '/', host='evil.example')[0], 403)
        self.assertEqual(self.fetch(port, '/', host='localhost:1')[0], 200)
        # a wrong page does not hide the spec: the viewer is shown, and carries what check reports
        self.note('notes/bad.md', 'bad', sources=['source.txt'], body='[[<absent>]]')
        status, page, _ = self.fetch(port)
        self.assertEqual(status, 200)
        self.assertIn('knowledge-data', page)
        self.assertIn('"errors": ["notes/bad.md: missing wikilink \\u003cabsent\\u003e"]', page)
        self.assertIn('"id": "bad"', page)
        # only a vault with no page that can be read is answered with the bare list
        for file in self.vault.rglob('*.md'):
            file.write_text('no properties <b>', encoding='utf-8')
        status, page, _ = self.fetch(port)
        self.assertEqual(status, 200)
        self.assertIn('The spec has ', page)
        self.assertIn('missing frontmatter', page)
        self.assertNotIn('knowledge-data', page)

    def git(self, *args):
        return subprocess.run(['git', '-C', str(self.repo), '-c', 'user.name=T', '-c', 'user.email=t@example.com', '-c', 'commit.gpgsign=false', *args],
                              check=True, capture_output=True, text=True).stdout

    def test_a_gap_says_when_it_appeared(self):
        k._added_cache.clear()
        repo = self.repo.resolve()
        self.vault.rename(self.repo / 'vault')
        self.vault = self.repo / 'vault'
        vault = self.vault.resolve()
        props = dict(sources=[], kind='product-gap', recheck='not-checked', decision='open', status=None, body=GAP_BODY)

        def added():
            notes, edges, errors, warnings, _ = k.load_vault(repo, vault, freshness=False)
            self.assertEqual(errors, [])
            return {n['id']: n['added'] for n in k.page_payload(repo, vault, notes, edges, warnings, sources=False)['nodes']}

        self.note('gaps/old.md', 'old', 'gap', **props)
        self.note('gaps/said.md', 'said', 'gap', created='2026-01-05', **props)
        self.assertEqual((added()['old'], added()['said']), ('', '2026-01-05'), 'without Git only the page itself can say')
        self.git('init', '-q')
        self.git('add', '-A')
        self.git('commit', '-q', '-m', 'First', '--date', '2026-03-01T12:00:00')
        self.note('gaps/old.md', 'old', 'gap', priority='high', **props)
        self.note('gaps/fresh.md', 'fresh', 'gap', **props)
        self.git('add', 'vault/gaps/old.md')
        self.git('commit', '-q', '-m', 'Second', '--date', '2026-04-02T12:00:00')
        found = added()
        self.assertEqual((found['old'], found['said'], found['fresh'], found['n']), ('2026-03-01', '2026-01-05', '', ''),
                         'the first commit of the page, the page\'s own word before that, nothing for a page not committed, nothing for a spec page')
        self.note('gaps/said.md', 'said', 'gap', created='5 January', **props)
        self.assertIn('created must be YYYY-MM-DD', self.run_cli('check')[2])
        self.note('gaps/said.md', 'said', 'gap', created='2026-01-05', **props)
        self.note('notes/n.md', 'n', sources=['source.txt'], created='2026-01-05')
        self.assertIn('created', self.run_cli('check')[2])

    def test_a_gap_has_a_topic_and_a_note_says_who_may_use_it(self):
        gap = dict(sources=[], kind='product-gap', recheck='not-checked', decision='open', status=None, body=GAP_BODY)
        self.note('gaps/g.md', 'g', 'gap', topic='security', **gap)
        self.note('notes/n.md', 'n', sources=['source.txt'], access=['admin', 'owner'])
        self.assertEqual(self.run_cli('check')[0], 0)
        notes, edges, errors, warnings, _ = k.load_vault(self.repo.resolve(), self.vault.resolve(), freshness=False)
        nodes = {n['id']: n for n in k.page_payload(self.repo.resolve(), self.vault.resolve(), notes, edges, warnings, sources=False)['nodes']}
        self.assertEqual((nodes['g']['topic'], nodes['g']['access'], nodes['n']['topic'], nodes['n']['access']),
                         ('security', [], '', ['admin', 'owner']))
        # the list of topics is closed, so the queue does not grow five spellings of one thing
        self.note('gaps/g.md', 'g', 'gap', topic='Security', **gap)
        self.assertIn('topic must be one of security, validation, data, logic, ui, api, ops', self.run_cli('check')[2])
        self.note('gaps/g.md', 'g', 'gap', **gap)
        self.assertEqual(self.run_cli('check')[0], 0, 'a gap without a topic is an older gap, not an error')
        self.note('notes/n.md', 'n', sources=['source.txt'], topic='security')
        self.assertIn('topic is only valid on gap pages', self.run_cli('check')[2])
        for value, message in (([], 'access must name at least one role'), ([' '], 'access must name at least one role'),
                               ('admin', 'access must be a string array')):
            self.note('notes/n.md', 'n', sources=['source.txt'], access=value)
            self.assertIn(message, self.run_cli('check')[2])
        self.note('notes/n.md', 'n', sources=['source.txt'])
        self.note('gaps/g.md', 'g', 'gap', access=['admin'], **gap)
        self.assertIn('access is only valid on note pages', self.run_cli('check')[2])

    def test_summary_counts_features_and_review_progress_by_priority(self):
        (self.vault / '.knowledge').mkdir(exist_ok=True)
        # a feature's `Priority` line is under its own heading; one under another heading is not its line
        (self.vault / '.knowledge/inventory.md').write_text(
            '# Inventory\n\n## Checkout: finished\n\nFolders: src/pay\nPriority: high (money, others-data)\n\n- [x] web /pay\n\n'
            '## Profile: finished\n\npriority: Medium (files)\n\n## About: not started\n\nPriority: low\n\n'
            '## Search: not started\n\nPriority: soon\n\n## Left out\n\nPriority: high\n', encoding='utf-8')
        self.note('runs/sec.md', 'sec', 'run', areas=[], review='security', status='partial',
                  body='## Feature checklist\n\n### High\n\n- [x] Checkout\n\n### Medium\n\n- [ ] Profile\n\n## Noted\n\n- Checkout: a line\n')
        # a run page written before features had a priority has one list and no levels
        self.note('runs/data.md', 'data', 'run', areas=[], review='data', body='## Features\n\n- [x] Checkout\n- [x] Profile\n')
        at = Path(os.path.relpath(self.vault.resolve(), self.repo.resolve())).as_posix() + '/'
        lines = self.run_cli('summary')[1].splitlines()
        self.assertIn('map: 2 of 4 features finished (50%), 0 in progress, 2 not started', lines)
        self.assertIn('features by priority: 1 high, 1 medium, 1 low, 1 not ranked', lines)
        reviews = [line.strip() for line in lines[lines.index('reviews:') + 1:]]
        self.assertEqual(reviews[0], 'security   started 2026-11-14, 1 of 2 features (high 1 of 1, medium 0 of 1), not finished; '
                         + at + 'runs/sec.md; 0 open gaps with topic security')
        self.assertEqual(reviews[3], 'data       last run 2026-11-14, 2 of 2 features; ' + at + 'runs/data.md; 0 open gaps with topic data')
        self.assertEqual(k.map_state(self.vault)['priority'], {'high': 1, 'medium': 1, 'low': 1, 'none': 1})
        # an inventory that ranks nothing says nothing about priority
        (self.vault / '.knowledge/inventory.md').write_text('# Inventory\n\n## Chats: finished\n', encoding='utf-8')
        self.assertNotIn('priority', k.map_state(self.vault))
        self.assertFalse([line for line in self.run_cli('summary')[1].splitlines() if line.startswith('features by priority')])

    def test_next_prints_the_requests_that_start_or_continue_a_review(self):
        ask = 'Use the project-knowledge skill'
        out = self.run_cli('next')[1].splitlines()
        self.assertIn('has no inventory file', out[0])
        self.assertEqual(out[1], '  ' + ask + ' to build a knowledge vault for this repository.')
        (self.vault / '.knowledge').mkdir(exist_ok=True)
        inventory = self.vault / '.knowledge/inventory.md'
        inventory.write_text('# Inventory\n\n## Checkout: finished\n\n## Profile: finished\n', encoding='utf-8')
        out = self.run_cli('next')[1].splitlines()
        self.assertEqual(out[1:], ['features by priority: 0 high, 0 medium, 0 low, 2 not ranked',
                                   'the features are not ranked yet, so a review has no order to read them in:', '  ' + ask + ' to rank the features.'])
        inventory.write_text('# Inventory\n\n## Checkout: finished\n\nPriority: high (money)\n\n## Team members: finished\n\nPriority: high (accounts)\n\n'
                             '## Profile: finished\n\nPriority: medium (files)\n\n## Search: not started\n', encoding='utf-8')
        levels = '## Feature checklist\n\n### High\n\n- [{}] Checkout\n- [{}] `Team members`\n\n### Medium\n\n- [ ] Profile\n'
        self.note('runs/sec.md', 'sec', 'run', areas=[], review='security', status='partial', body=levels.format('x', ' '))
        self.note('runs/data.md', 'data', 'run', areas=[], review='data', status='partial', body=levels.format('x', 'X'))
        # a checklist that is one list, from before features had a priority
        self.note('runs/logic.md', 'logic', 'run', areas=[], review='logic', status='partial', body='- [x] Checkout\n- [ ] Profile\n')
        status, text, err = self.run_cli('next')
        self.assertEqual((status, err), (0, ''))
        out = text.splitlines()
        self.assertEqual(out[1:5], ['features by priority: 2 high, 1 medium, 0 low, 1 not ranked', '1 features have no priority and are in no level:',
                                    '  ' + ask + ' to rank the features that have no priority yet.', 'high: Checkout; Team members'])

        def entry(first):
            at = out.index(first)
            return out[at + 1]

        self.assertEqual(entry('  flows      not run'), '    ' + ask + ' in review mode: review the high-priority features for their flows.')
        self.assertEqual(entry('  security   high 1 of 2, medium 0 of 1'), '    ' + ask + ' to continue the security review from its run page.')
        self.assertEqual(entry('  data       high 2 of 2, medium 0 of 1'), '    ' + ask + ' in review mode: go on with the data review for the medium-priority features.',
                         'a level that is done is not offered again; the next one is')
        self.assertEqual(entry('  logic      1 of 2 features'), '    ' + ask + ' to continue the logic review from its run page.')
        topics = [line.split()[0] for line in out[out.index('by topic: one list of questions over one level of features') + 1:] if line.startswith('  ') and not line.startswith('    ')]
        self.assertEqual(topics[:9], ['flows', 'logic', 'security', 'abuse', 'validation', 'data', 'failures', 'api', 'ui'], 'in the order the guide runs them')
        # by feature: how many of the nine reviews have ticked it, whatever marks its name has on the run page
        self.assertEqual(entry('  Checkout: 3 of 9 reviews'), '    ' + ask + ' in review mode: run every review on the feature "Checkout".')
        self.assertEqual(entry('  Team members: 1 of 9 reviews'), '    ' + ask + ' in review mode: run every review on the feature "Team members".')
        # a review that has read every level says so and asks for nothing
        self.note('runs/data.md', 'data', 'run', areas=[], review='data', body=levels.format('x', 'x').replace('- [ ] Profile', '- [x] Profile'))
        out = self.run_cli('next')[1].splitlines()
        self.assertIn('  data       high 2 of 2, medium 1 of 1, finished', out)
        self.assertFalse(out[out.index('  data       high 2 of 2, medium 1 of 1, finished') + 1].startswith('    '))

    def test_summary_and_gaps_say_where_the_spec_stands(self):
        gap = dict(sources=[], kind='product-gap', recheck='not-checked', decision='open', status=None, body=GAP_BODY)
        self.note('gaps/role.md', 'role', 'gap', topic='security', priority='high', **gap)
        self.note('gaps/leak.md', 'leak', 'gap', topic='security', priority='low', review='abuse', **gap)
        self.note('gaps/plain.md', 'plain', 'gap', **gap)
        self.note('gaps/later.md', 'later', 'gap', topic='security', priority='low',
                  **(gap | {'decision': 'deferred', 'decided_by': 'Ann', 'decided_on': '2026-11-15'}))
        self.note('gaps/old.md', 'old', 'gap', topic='security', **(gap | {'decision': 'duplicate', 'duplicate_of': 'role'}))
        (self.vault / '.knowledge').mkdir(exist_ok=True)
        (self.vault / '.knowledge/inventory.md').write_text(
            '# Inventory\n\n## Apps and packages\n\n## Chats: finished\n\n- [x] web /chats\n\n## Orders: in progress\n\n## Reviews: not started\n\n'
            '## Search: Finished\n\n## Left out\n', encoding='utf-8')
        # a review is a run page that says so, or one named <date>-review-<topic>.md; the newest of a topic counts
        self.note('runs/2026-01-02-review-security.md', 'sec-old', 'run', areas=[], body='- [x] Chats\n- [x] Orders\n', updated='2026-01-02')
        self.note('runs/sec.md', 'sec-new', 'run', areas=[], review='security', status='partial', body='## Features\n\n- [x] Chats\n- [ ] Orders\n- [ ] Search\n')
        self.note('runs/2026-01-03-review-texts.md', 'texts', 'run', areas=[], body='No checklist.\n', updated='2026-01-03')
        self.note('runs/2026-01-04-orders-review.md', 'orders', 'run', areas=[], body='- [x] Orders\n')
        at = Path(os.path.relpath(self.vault.resolve(), self.repo.resolve())).as_posix() + '/'
        status, out, err = self.run_cli('summary')
        self.assertEqual((status, err), (0, ''), 'a report: no warnings, exit 0')
        lines = out.splitlines()
        self.assertIn('map: 2 of 4 features finished (50%), 1 in progress, 1 not started', lines)
        self.assertIn('gaps: 3 open (needs recheck 3, needs decision 0, accepted 0), 1 deferred, 1 closed', lines)
        self.assertIn('open gaps by topic: security 2 (1 high), no topic 1', lines)
        self.assertIn('open gaps by priority: high 1, low 1, none 1', lines)
        reviews = [line.strip() for line in lines[lines.index('reviews:') + 1:]]
        self.assertEqual(reviews[0], 'security   started 2026-11-14, 1 of 3 features, not finished; ' + at + 'runs/sec.md; 2 open gaps with topic security')
        self.assertEqual(reviews[1], 'abuse      not run; 2 open gaps with topic security; 1 open gap written by it',
                         'an abuse review writes security gaps, and a gap that names its review is counted for it')
        self.assertEqual(reviews[2], 'validation not run; 0 open gaps with topic validation')
        self.assertEqual(reviews[4], 'logic      not run; 0 open gaps with topic logic')
        self.assertEqual(reviews[5], 'flows      not run; 0 open gaps with topic logic', 'a flows review writes logic gaps')
        self.assertEqual(reviews[8], 'failures   not run; 0 open gaps with topic ops')
        self.assertEqual(reviews[9], 'texts      last run 2026-01-03; ' + at + 'runs/2026-01-03-review-texts.md; 0 open gaps with topic texts',
                         'a topic of the person\'s own is listed after the nine; a page that only ends in -review is not a review')
        self.assertEqual(len(reviews), 10)
        # without an inventory file the map's progress is unknown, and said to be
        (self.vault / '.knowledge/inventory.md').unlink()
        self.assertIn('map: no inventory file', self.run_cli('summary')[1])
        # gaps: the open ones by default, the most urgent first, each with its file
        listed = self.run_cli('gaps')[1].splitlines()
        self.assertEqual([line.split()[3] for line in listed[:-1]], [at + 'gaps/role.md', at + 'gaps/leak.md', at + 'gaps/plain.md'])
        self.assertEqual(listed[-1], 'gaps: 3 listed')
        self.assertEqual(self.run_cli('gaps', '--topic', 'security', '--priority', 'high')[1].splitlines()[-1], 'gaps: 1 listed')
        self.assertIn(at + 'gaps/plain.md', self.run_cli('gaps', '--topic', 'none')[1])
        self.assertEqual(self.run_cli('gaps', '--review', 'abuse')[1].splitlines()[-1], 'gaps: 1 listed', 'the gaps one review wrote')
        self.assertIn(at + 'gaps/leak.md', self.run_cli('gaps', '--review', 'abuse')[1])
        self.assertEqual(self.run_cli('gaps', '--review', 'none')[1].splitlines()[-1], 'gaps: 2 listed')
        self.assertEqual(self.run_cli('gaps', '--state', 'closed')[1].splitlines()[-1], 'gaps: 1 listed')
        self.assertEqual(self.run_cli('gaps', '--state', 'all')[1].splitlines()[-1], 'gaps: 5 listed')
        self.assertEqual(self.run_cli('gaps', '--state', 'deferred')[1].splitlines()[-1], 'gaps: 1 listed',
                         'a gap a person deferred is not open work: it is counted and listed on its own')
        # a broken page is left out and counted, and the report still answers
        self.note('gaps/bad.md', 'bad', 'gap', topic='Security', **gap)
        status, out, _ = self.run_cli('summary')
        self.assertEqual(status, 0)
        self.assertEqual(out.splitlines()[-1], 'check: 1 errors on 1 pages, which are left out above; run check to see them')
        self.note('gaps/bad.md', 'bad', 'gap', **gap)
        # `review` belongs to run and gap pages and is one lower-case word
        self.note('notes/n.md', 'n', sources=['source.txt'], review='security')
        self.assertIn('review is only valid on run and gap pages', self.run_cli('check')[2])
        self.note('notes/n.md', 'n', sources=['source.txt'])
        self.note('runs/sec.md', 'sec-new', 'run', areas=[], review='Security review')
        self.assertIn('review is only valid on run and gap pages and names the review', self.run_cli('check')[2])

    def test_history_and_pending_pages_come_from_git(self):
        k._history_cache.clear()
        repo, vault = self.repo.resolve(), self.vault.resolve()
        self.assertEqual((k.vault_history(repo, vault), k.vault_pending(repo, vault)), ([], []), 'a vault outside the repository has no history')
        self.vault.rename(self.repo / 'vault')
        self.vault = self.repo / 'vault'
        vault = self.vault.resolve()
        self.assertEqual((k.vault_history(repo, vault), k.vault_pending(repo, vault)), ([], []), 'nor has a folder that is not a Git work tree')
        self.git('init', '-q')
        self.note('notes/n.md', 'n', sources=['source.txt'], summary='Old "line".')
        (self.vault / 'AS-BUILT.md').write_text('generated', encoding='utf-8')
        (self.vault / '.knowledge').mkdir()
        (self.vault / '.knowledge/x.md').write_text('internal', encoding='utf-8')
        self.git('add', '-A')
        self.git('commit', '-q', '-m', 'First pass')
        self.note('notes/n.md', 'n', sources=['source.txt'], summary='New line.', body='changed text')
        self.note('areas/a.md', 'a', 'area', areas=[], body='only the text changed')
        self.note('notes/extra.md', 'extra', sources=['source.txt'], summary='Brand new.')
        (self.vault / '00-index.md').unlink()
        (self.repo / 'source.txt').write_text('code changed too', encoding='utf-8')
        self.git('add', '-A')
        self.git('commit', '-q', '-m', 'Second \x01 pass')
        history = k.vault_history(repo, vault)
        self.assertEqual([(c['subject'], c['more'], len(c['sha'])) for c in history], [('Second  pass', 0, 40), ('First pass', 0, 40)])
        self.assertRegex(history[0]['date'], r'^\d{4}-\d{2}-\d{2}$')
        self.assertEqual(history[0]['pages'], [
            {'path': '00-index.md', 'status': 'removed'},
            {'path': 'areas/a.md', 'status': 'changed'},
            {'path': 'notes/extra.md', 'status': 'added'},
            {'path': 'notes/n.md', 'status': 'changed', 'was': 'Old "line".', 'now': 'New line.'},
        ])
        # generated files, internal files and application files are not history of the spec
        self.assertEqual(sorted(p['path'] for p in history[1]['pages']), ['00-index.md', 'areas/a.md', 'notes/n.md'])
        self.assertIs(k.vault_history(repo, vault), history, 'one Git call per HEAD')
        self.assertEqual(k.vault_pending(repo, vault), [])
        self.note('notes/n.md', 'n', sources=['source.txt'], summary='Edited again.')
        self.note('gaps/fresh.md', 'fresh', 'gap', sources=[], kind='product-gap', recheck='not-checked', decision='open', status=None)
        (self.vault / 'notes/extra.md').unlink()
        (self.vault / 'GAPS.md').write_text('generated', encoding='utf-8')
        self.assertEqual(k.vault_pending(repo, vault), [
            {'path': 'gaps/fresh.md', 'status': 'added'}, {'path': 'notes/extra.md', 'status': 'removed'}, {'path': 'notes/n.md', 'status': 'changed'}])
        # long commits are cut, and the cut is counted
        original = k.HISTORY_PAGES
        k.HISTORY_PAGES = 2
        k._history_cache.clear()
        try:
            cut = k.vault_history(repo, vault)[0]
        finally:
            k.HISTORY_PAGES = original
            k._history_cache.clear()
        self.assertEqual((len(cut['pages']), cut['more']), (2, 2))
        # the same from a repository folder below the top of the work tree
        inner = self.repo / 'app'
        inner.mkdir()
        (self.repo / 'vault').rename(inner / 'vault')
        self.git('add', '-A')
        self.git('commit', '-q', '-m', 'Moved')
        moved = k.vault_history(inner.resolve(), (inner / 'vault').resolve())
        self.assertEqual(moved[0]['subject'], 'Moved')
        self.assertIn({'path': 'areas/a.md', 'status': 'added'}, moved[0]['pages'])
        self.assertEqual(k.vault_pending(inner.resolve(), (inner / 'vault').resolve()), [])
        k._history_cache.clear()

    def built(self, *args):
        out = self.root / 'site/spec.html'
        status, printed, err = self.run_cli('build', '--out', str(out), *args)
        data = json.loads(re.search(r'<script id="knowledge-data" type="application/json">\s*(.*?)\s*</script>', out.read_text(encoding='utf-8'), re.S).group(1)) if out.is_file() else None
        return status, printed, err, data

    def test_a_skill_copy_without_the_viewer_says_where_it_is(self):
        original = k.__file__
        lean = self.root / 'lean/project-knowledge/scripts/knowledge.py'
        lean.parent.mkdir(parents=True)
        out = self.root / 'page.html'
        k.__file__ = str(lean)
        try:
            for command in (['serve'], ['build', '--out', str(out)]):
                said = self.refused(*command)
                self.assertIn('the viewer is not part of this copy of the skill', said)
                self.assertIn('npx project-spec serve', said)
            self.assertFalse(out.exists())
            self.assertEqual(self.run_cli('check')[0], 0, 'everything that writes or checks the spec works without the viewer')
            # a page of your own is shown instead, when it has the one placeholder
            mine = self.root / 'mine.html'
            mine.write_text('<pre id="data">__KNOWLEDGE_DATA__</pre>', encoding='utf-8')
            self.assertEqual(self.run_cli('build', '--out', str(out), '--viewer', str(mine))[0], 0)
            self.assertTrue(out.read_text(encoding='utf-8').startswith('<pre id="data">{"'))
            mine.write_text('no placeholder', encoding='utf-8')
            self.assertIn('must contain the placeholder __KNOWLEDGE_DATA__ exactly once', self.refused('build', '--out', str(out), '--viewer', str(mine)))
            self.assertIn('is not a file', self.refused('serve', '--viewer', str(self.root / 'absent.html')))
            self.assertIn('--viewer is only for serve and build', self.refused('check', '--viewer', str(mine)))
        finally:
            k.__file__ = original
            k.VIEWER = None

    def refused(self, *args):
        """What a command that stops with a usage error says."""
        err = StringIO()
        with self.assertRaises(SystemExit), redirect_stdout(StringIO()), redirect_stderr(err):
            k.main([*args, '--repo', str(self.repo), '--vault', str(self.vault)])
        return err.getvalue()

    def test_build_writes_one_page_for_a_server_without_source_text(self):
        status, printed, err, data = self.built()
        self.assertEqual((status, err), (0, 'WARNING: notes/n.md: unbaselined source source.txt\n'))
        self.assertIn('build: wrote ' + str(self.root / 'site/spec.html'), printed)
        self.assertIn('their text is not included', printed)
        self.assertEqual((data['built'], data.get('live'), data['files'], data['sourceUrl'], data['commit']), (True, None, {}, '', ''))
        self.assertNotIn('repoRoot', data, 'a page for a server does not name a folder of this machine')
        self.assertEqual({n['id'] for n in data['nodes']}, {'a', 'index', 'n'})
        self.assertNotIn('evidence', (self.root / 'site/spec.html').read_text(encoding='utf-8'))
        # nothing appeared in the vault, and no temporary file was left beside the page
        self.assertFalse((self.vault / '.knowledge').exists())
        self.assertEqual([f.name for f in (self.root / 'site').iterdir()], ['spec.html'])
        # the text of cited files only when asked for, with a warning about who may see it
        status, printed, _, data = self.built('--with-sources')
        self.assertEqual((status, data['files']['source.txt']['text']), (0, 'evidence'))
        self.assertIn('the text of 1 cited source files is inside the file', printed)

    def test_build_can_run_where_part_of_the_repository_is_missing(self):
        self.note('notes/m.md', 'm', sources=['source.txt', 'Dockerfile'])
        status, printed, err, data = self.built()
        self.assertEqual(status, 0, 'the page is built, and says what is wrong')
        self.assertIn('source is missing or not a file', err)
        self.assertEqual(data['errors'], ['notes/m.md: Dockerfile: source is missing or not a file'])
        self.assertIn('build: 1 errors on 1 pages are listed on the page', printed)
        status, printed, err, data = self.built('--allow-missing-sources')
        self.assertEqual(status, 0)
        self.assertIn('build: 1 cited files are not in this folder, so nobody compared them with the pages: Dockerfile', printed)
        self.assertNotIn('Dockerfile', err)
        self.note('notes/o.md', 'o', sources=['Dockerfile'])
        data = self.built('--allow-missing-sources')[3]
        pages = {n['id']: (n['sources'], n['stale']) for n in data['nodes']}
        self.assertEqual(pages['o'], (['Dockerfile'], False), 'a file nobody could read does not mark its page as changed')
        self.assertEqual(pages['m'], (['source.txt', 'Dockerfile'], True), 'source.txt has no accepted fingerprint')
        (self.vault / 'notes/o.md').unlink()
        # a folder where a file should be is still an error, and so is the same vault for check
        (self.repo / 'Dockerfile').mkdir()
        status, _, _, data = self.built('--allow-missing-sources')
        self.assertEqual((status, data['errors']), (0, ['notes/m.md: Dockerfile: source is missing or not a file']))
        (self.repo / 'Dockerfile').rmdir()
        self.assertEqual(self.run_cli('check')[0], 1)
        self.assertIn('only for build', self.refused('check', '--allow-missing-sources'))

    def test_build_and_serve_work_where_git_is_not_installed(self):
        import os
        from unittest import mock
        k._history_cache.clear()
        self.vault.rename(self.repo / 'vault')
        self.vault = self.repo / 'vault'
        self.git('init', '-q')
        self.git('add', '-A')
        self.git('commit', '-q', '-m', 'First')
        empty = self.root / 'no-tools'
        empty.mkdir()
        with mock.patch.dict(os.environ, {'PATH': str(empty)}):
            status, printed, err, data = self.built()
            self.assertEqual((status, data['commit'], data['history'], data['pending']), (0, '', [], []), err)
            self.assertNotIn('commit ', printed)
            self.assertIn('knowledge-data', k.live_page(self.repo.resolve(), self.vault.resolve()))
            self.assertIn('--ignore-dirty needs --repo to be a Git work tree', self.refused('check', '--ignore-dirty'))
        k._history_cache.clear()
        self.assertEqual([c['subject'] for c in self.built()[3]['history']], ['First'], 'with Git back, the history is too')

    def test_build_links_cited_files_to_the_commit_it_was_built_from(self):
        k._history_cache.clear()
        self.vault.rename(self.repo / 'vault')
        self.vault = self.repo / 'vault'
        out = str(self.root / 'site/spec.html')
        self.assertIn('--repo is not a Git work tree with a commit', self.refused('build', '--out', out, '--source-url', 'https://github.com/o/r/blob/{commit}'))
        self.git('init', '-q')
        self.git('add', '-A')
        self.git('commit', '-q', '-m', 'First')
        head = self.git('rev-parse', 'HEAD').strip()
        status, printed, _, data = self.built('--source-url', 'https://github.com/o/r/blob/{commit}/')
        self.assertEqual((status, data['commit'], data['sourceUrl']), (0, head, 'https://github.com/o/r/blob/' + head))
        self.assertIn('commit ' + head[:7], printed)
        self.assertEqual([c['subject'] for c in data['history']], ['First'])
        self.assertNotIn('shallow clone', printed)
        for bad in ('javascript:alert(1)', 'github.com/o/r', 'https://', 'https://x.example/a b'):
            with self.subTest(url=bad):
                self.assertIn('--source-url must be an http(s) address', self.refused('build', '--out', out, '--source-url', bad))

    def test_build_refuses_a_broken_vault_and_a_file_inside_the_vault(self):
        for out in (self.vault / 'spec.html', self.vault / 'notes/deep/spec.html', self.root):
            with self.subTest(out=out):
                self.assertIn('--out must be a file outside the vault', self.refused('build', '--out', str(out)))
            self.assertFalse((self.vault / 'spec.html').exists() or (self.vault / 'notes/deep').exists())
        for args in (['build'], ['check', '--out', 'x.html'], ['serve', '--with-sources'], ['check', '--source-url', 'https://x.example']):
            with self.subTest(args=args):
                self.assertIn('build', self.refused(*args))
        # one wrong page does not hide the spec: the page is built with every page that could be read, and lists the errors
        self.note('notes/bad.md', 'bad', sources=['source.txt'], body='[[<absent>]]')
        self.note('notes/twice.md', 'n', sources=['source.txt'])
        (self.vault / 'notes/unread.md').write_text('no properties', encoding='utf-8')
        status, printed, err, data = self.built()
        self.assertEqual(status, 0, err)
        self.assertIn('missing wikilink <absent>', err)
        self.assertEqual(sorted(data['errors']), ['notes/bad.md: missing wikilink <absent>', 'notes/twice.md: duplicate id n',
                                                  'notes/unread.md: missing frontmatter'])
        ids = [n['id'] for n in data['nodes']]
        self.assertIn('bad', ids)
        self.assertEqual(ids.count('n'), 1, 'of two pages with one id the viewer gets one')
        self.assertIn('build: 3 errors on 3 pages are listed on the page', printed)
        # check is still the gate, and a vault with no page that can be read has nothing to show
        self.assertEqual(self.run_cli('check')[0], 1)
        (self.root / 'site/spec.html').unlink()
        for file in self.vault.rglob('*.md'):
            file.write_text('no properties', encoding='utf-8')
        status, _, err, data = self.built()
        self.assertEqual((status, data), (1, None))
        self.assertIn('build: failed', err)

    def test_every_problem_of_a_page_is_reported_at_once(self):
        (self.vault / 'notes/many.md').write_text(
            '---\nid: "Many Things"\ntitle: "T"\ntype: "note"\nstatus: "done"\nareas: []\nsources: []\n'
            'updated: "2026-13-45"\ntags: [broken\nkind: "product-gap"\ntitle: "again"\n---\n', encoding='utf-8')
        err = self.run_cli('check')[2]
        mine = sorted(line.split('notes/many.md: ', 1)[1] for line in err.splitlines() if 'notes/many.md: ' in line)
        self.assertEqual(len(mine), 7, err)
        for part in ('invalid id', 'invalid or duplicate property (title)', 'kind is only valid on gap pages', 'note requires an area',
                     'status must be one of', 'tags: Expecting', 'updated is not a real date'):
            self.assertTrue(any(m.startswith(part) for m in mine), part + '\n' + err)
        self.assertIn('check: failed, 7 errors on 1 pages', err)
        # a gap with several things wrong says all of them, and nothing about what it could not read
        (self.vault / 'notes/many.md').unlink()
        (self.vault / 'gaps').mkdir(exist_ok=True)
        (self.vault / 'gaps/g.md').write_text(
            '---\nid: "g"\ntitle: "G"\ntype: "gap"\nareas: ["a"]\nsources: []\nupdated: "2026-11-14"\nkind: "bogus"\n'
            'recheck: "confirmed"\ndecision: "accepted"\ndecided_by: "agent"\ntopic: "Security"\nrechecked_on: nope\n---\n', encoding='utf-8')
        err = self.run_cli('check')[2]
        mine = [line.split('gaps/g.md: ', 1)[1] for line in err.splitlines() if 'gaps/g.md: ' in line]
        self.assertEqual(len(mine), 6, err)
        for part in ('rechecked_on: Expecting', 'kind must be one of', "rechecked_by is required when recheck is 'confirmed'",
                     "decided_on is required when decision is 'accepted'", "decided_by must be a person's name", 'topic must be one of'):
            self.assertTrue(any(m.startswith(part) for m in mine), part + '\n' + err)

    def test_history_of_a_shallow_clone_leaves_out_the_commit_without_parents(self):
        k._history_cache.clear()
        self.vault.rename(self.repo / 'vault')
        self.vault = self.repo / 'vault'
        self.git('init', '-q')
        self.git('add', '-A')
        self.git('commit', '-q', '-m', 'First')
        self.note('notes/n.md', 'n', sources=['source.txt'], summary='Second line.')
        self.git('commit', '-q', '-am', 'Second')
        self.note('notes/n.md', 'n', sources=['source.txt'], summary='Third line.')
        self.git('commit', '-q', '-am', 'Third')
        clone = self.root / 'clone'
        subprocess.run(['git', 'clone', '-q', '--depth', '2', self.repo.resolve().as_uri(), str(clone)], check=True, capture_output=True)
        history = k.vault_history(clone.resolve(), (clone / 'vault').resolve())
        self.assertEqual([(c['subject'], [p['status'] for p in c['pages']]) for c in history], [('Third', ['changed'])],
                         'Second is where the clone stops: Git would show every page as added there')
        self.repo, self.vault = clone, clone / 'vault'
        self.assertIn('build: this is a shallow clone', self.built()[1])

    def test_move_keeps_the_vault_true_in_its_new_folder(self):
        k._added_cache.clear()
        repo = self.repo.resolve()
        (self.repo / 'knowledge').mkdir()
        self.vault.rename(self.repo / 'knowledge/demo')
        self.vault = self.repo / 'knowledge/demo'
        (self.repo / 'my file.txt').write_text('x', encoding='utf-8')
        body = '\n'.join([
            'The [code](../../../source.txt#L2) stays reachable, [spaced](<../../../my file.txt>) and [encoded](../../../my%20file.txt) too.',
            'A page of the vault is [here](../00-index.md), the web is [there](https://example.com/a/../b) and `[this](../../../source.txt)` is code.',
            '', '```', '[fenced](../../../source.txt)', '```', '', '[ref]: ../../../source.txt'])
        self.note('notes/n.md', 'n', sources=['source.txt'], body=body)
        self.note('gaps/g.md', 'g', 'gap', sources=[], kind='product-gap', recheck='not-checked', decision='open', status=None, body=GAP_BODY)
        self.assertEqual(self.run_cli('snapshot', '--all')[0], 0)
        self.git('init', '-q')
        self.git('add', '-A')
        self.git('commit', '-q', '-m', 'First', '--date', '2026-03-01T12:00:00')
        for to, why in (('knowledge/demo/inner', 'must not be inside the vault'), ('../elsewhere', 'inside the repository'), ('knowledge/demo', 'already there')):
            self.assertIn(why, self.refused('move', '--to', to))
        (self.repo / 'taken').mkdir()
        (self.repo / 'taken/file').write_text('x', encoding='utf-8')
        self.assertIn('taken already exists and is not empty', self.refused('move', '--to', 'taken'))
        self.assertIn('move requires --to DIR', self.refused('move'))
        self.assertIn('--to is only for move', self.refused('check', '--to', 'x'))
        status, out, _ = self.run_cli('move', '--to', 'project-spec')
        self.assertEqual(status, 0)
        self.assertIn('move: knowledge/demo -> project-spec; 4 links to repository files repointed on 1 pages; 1 gaps given the day they first appeared', out)
        self.assertIn('check finds 0 errors and 0 warnings', out)
        self.assertFalse((self.repo / 'knowledge').exists(), 'the folder it left is removed when nothing else is in it')
        moved = (self.repo / 'project-spec/notes/n.md').read_text(encoding='utf-8')
        self.assertIn('[code](../../source.txt#L2) stays reachable, [spaced](<../../my file.txt>) and [encoded](../../my%20file.txt) too.', moved)
        self.assertIn('[here](../00-index.md), the web is [there](https://example.com/a/../b) and `[this](../../../source.txt)` is code.', moved)
        self.assertIn('[fenced](../../../source.txt)', moved, 'code is left as written')
        self.assertIn('[ref]: ../../source.txt', moved)
        self.assertIn('created: "2026-03-01"', (self.repo / 'project-spec/gaps/g.md').read_text(encoding='utf-8'))
        self.vault = self.repo / 'project-spec'
        self.assertEqual(self.run_cli('check', '--strict')[0], 0, 'the reviewed fingerprints came along')
        self.assertEqual(k.find_vault(repo), self.vault.resolve())

    def test_serve_finds_the_single_vault_and_asks_when_unsure(self):
        with self.assertRaisesRegex(ValueError, 'no vault found: no folder with 00-index.md up to three folders deep; pass --vault'):
            k.find_vault(self.repo)
        # the vault is wherever the person put it, up to three folders deep; hidden folders, dependencies and
        # anything nested deeper (an example project with a vault of its own) are not the repository's vault
        for place in ('.hidden/spec', 'node_modules/pkg/spec', 'examples/demo/knowledge/demo'):
            (self.repo / place).mkdir(parents=True)
            (self.repo / place / '00-index.md').write_text('x', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'no vault found'):
            k.find_vault(self.repo)
        for place in ('project-spec', 'docs/product/spec'):
            (self.repo / place).mkdir(parents=True)
            (self.repo / place / '00-index.md').write_text('x', encoding='utf-8')
            self.assertEqual(k.find_vault(self.repo), self.repo / place)
            (self.repo / place / '00-index.md').unlink()
        (self.repo / 'knowledge/one').mkdir(parents=True)
        (self.repo / 'knowledge/one/00-index.md').write_text('x', encoding='utf-8')
        self.assertEqual(k.find_vault(self.repo), self.repo / 'knowledge/one')
        (self.repo / 'knowledge/two').mkdir()
        (self.repo / 'knowledge/two/00-index.md').write_text('x', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, r'several vaults found \(knowledge/one, knowledge/two\); pass --vault'):
            k.find_vault(self.repo)
        # every command finds the vault the same way
        with self.assertRaisesRegex(ValueError, 'several vaults found'):
            k.main(['check', '--repo', str(self.repo)])
        (self.repo / 'knowledge/two/00-index.md').unlink()
        (self.repo / 'knowledge/one/00-index.md').write_text('---\nid: "index"\ntitle: "T"\ntype: "index"\nstatus: "current"\nareas: []\nsources: []\nupdated: "2026-11-14"\n---\n', encoding='utf-8')
        out = StringIO()
        with redirect_stdout(out), redirect_stderr(StringIO()):
            self.assertEqual(k.main(['check', '--repo', str(self.repo)]), 0)
        self.assertIn('check: 1 notes', out.getvalue())

    def test_a_feature_too_big_for_one_page_has_parts(self):
        self.note('notes/chats.md', 'chats', sources=['source.txt'], body='Parts: [[notes/group-chats|group chats]].')
        self.note('notes/group-chats.md', 'group-chats', sources=['source.txt'], parent='chats')
        status, out, err = self.run_cli('check')
        self.assertEqual(status, 0, err)
        notes, edges, errors, _, _ = k.load_vault(self.repo.resolve(), self.vault.resolve())
        self.assertIn(('chats', 'group-chats'), edges)
        self.assertEqual(k.node_of(next(n for n in notes if n['meta']['id'] == 'group-chats'))['parent'], 'chats')
        cases = (
            (dict(parent='chats'), 'Parts: none listed.', 'notes/group-chats.md: its feature notes/chats.md does not link to it'),
            (dict(parent='nobody'), None, 'parent nobody is not the id of an existing note'),
            (dict(parent='a'), None, 'parent a is not the id of an existing note'),
            (dict(parent='group-chats'), None, 'parent must name a different note'),
            (dict(parent=''), None, 'parent is only valid on note pages and names the feature note'),
        )
        for extra, parent_body, message in cases:
            with self.subTest(message=message):
                self.note('notes/chats.md', 'chats', sources=['source.txt'], body=parent_body or 'Parts: [[notes/group-chats|group chats]].')
                self.note('notes/group-chats.md', 'group-chats', sources=['source.txt'], **extra)
                status, _, err = self.run_cli('check')
                self.assertEqual(status, 1)
                self.assertIn(message, err)
        # three levels and no more, and a part stays in its feature's area
        self.note('notes/chats.md', 'chats', sources=['source.txt'], body='[[notes/group-chats|group chats]] [[notes/renaming|renaming]]')
        self.note('notes/group-chats.md', 'group-chats', sources=['source.txt'], parent='chats', body='[[notes/renaming|renaming]]')
        self.note('notes/renaming.md', 'renaming', sources=['source.txt'], parent='group-chats')
        self.assertIn('parent group-chats is itself a part of chats; a part belongs to a feature, not to another part', self.run_cli('check')[2])
        self.note('areas/b.md', 'b', 'area', areas=[])
        self.note('notes/renaming.md', 'renaming', sources=['source.txt'], parent='chats', areas=['b'])
        self.assertIn('parent chats is in another area', self.run_cli('check')[2])
        self.note('areas/a.md', 'a', 'area', areas=[], parent='chats')
        self.assertIn('parent is only valid on note pages', self.run_cli('check')[2])

    def test_area_pages_are_maps_without_tables_or_links_into_notes(self):
        table = '| Screen | What it does |\n| --- | --- |\n| Profile | Edits the name. [[notes/n|Profile]] |\n'
        for body in (table, '| a | b |\n|:-|-:|\n| 1 | 2 |', 'a | b\n--- | ---\n1 | 2', '| one column |\n| --- |\n| x |'):
            with self.subTest(body=body):
                self.note('areas/a.md', 'a', 'area', areas=[], body=body)
                self.assertInvalid('an area page is a map and holds no table (1 found)')
        for link in ('[[notes/n#Profile]]', '[[n#Profile|the profile part]]', '[[notes/n#^block]]', '| [[notes/n#Profile\\|alias]] |'):
            with self.subTest(link=link):
                self.note('areas/a.md', 'a', 'area', areas=[], body=f'See {link}.')
                self.assertInvalid('an area page links whole notes, not a part of one')
        self.note('areas/a.md', 'a', 'area', areas=[], body='See [[notes/n#Profile|it]].')
        self.assertIn('not a part of one (notes/n#Profile);', self.errors()[1])
        # what stays allowed: whole notes, tables in code, lists, and tables or heading links on other pages
        self.note('areas/a.md', 'a', 'area', areas=[], body='- [[notes/n|The rule]]: one line about it.\n\n```\n| a | b |\n| - | - |\n```\n\nA line with a | pipe.')
        self.note('notes/n.md', 'n', sources=['source.txt'], body=table + '\nSee [[areas/a#Coverage]].')
        self.note('notes/m.md', 'm', sources=['source.txt'], body='Part of [[notes/n#Profile]].')
        self.gap(body=section_body() + '\nSee [[notes/n#Profile]].')
        status, err = self.errors()
        self.assertEqual(status, 0, err)

    def test_a_rule_number_is_used_once(self):
        rules = '## Business rules\n\n| ID | Rule |\n| --- | --- |\n| BR-PROFILE-01 | A name has 1 to 120 characters. |\n| BR-PROFILE-02 | The email cannot be changed here. |\n'
        self.note('notes/n.md', 'n', sources=['source.txt'], body=rules)
        self.note('notes/m.md', 'm', sources=['source.txt'], body='| ID | Rule |\n| --- | --- |\n| BR-TEAM-01 | Only owners rename a team. |\n\nSee BR-PROFILE-01.\n\n```\n| BR-PROFILE-01 | an example |\n```')
        status, err = self.errors()
        self.assertEqual(status, 0, err)
        # the same number on another page, and twice on one page
        self.note('notes/m.md', 'm', sources=['source.txt'], body='| ID | Rule |\n| --- | --- |\n| BR-PROFILE-02 | Something else. |')
        self.assertInvalid('notes/n.md: rule BR-PROFILE-02 is numbered twice (also on notes/m.md)')
        self.note('notes/m.md', 'm', sources=['source.txt'], body='')
        self.note('notes/n.md', 'n', sources=['source.txt'], body=rules + '| BR-PROFILE-01 | A second rule with the first number. |')
        self.assertInvalid('notes/n.md: rule BR-PROFILE-01 is numbered twice (on this page)')

    def test_run_pages_cannot_link_to_vault_pages(self):
        for body in ('[[notes/n]]', 'see [[n|the note]] and [[areas/a]]', '![[notes/n]]', '[n](../notes/n.md)', '[n]: ../00-index.md'):
            with self.subTest(body=body):
                self.note('runs/r.md', 'r', 'run', areas=[], body=body)
                self.assertInvalid('run pages are history, not part of the map')
        self.note('runs/r.md', 'r', 'run', areas=[], body='see [[n]] and [[areas/a]]')
        self.assertIn('(2 links)', self.errors()[1])
        self.note('runs/r.md', 'r', 'run', areas=[], body='Updated `notes/n` and `[[areas/a]]`; read [source](../../repo/source.txt) and https://example.com.')
        self.assertEqual(self.errors()[0], 0, self.errors()[1])
        self.note('00-index.md', 'index', 'index', areas=[], body='[[areas/a]] [[runs/r]]')
        self.assertEqual(self.build()[0], 0)
        graph = json.loads((self.vault / '.knowledge/graph.json').read_text())
        self.assertEqual([e for e in graph['edges'] if e['source'] == 'r'], [])

    # defects
    def test_fence_detection_follows_commonmark(self):
        bad = '[[missing]]'
        for body in (f'```npm test``` passed.\n{bad}', f'```\ncode\n```js\n{bad}\n```\n{bad}', f'~~~\n~~~ x\n{bad}\n~~~\n{bad}'):
            with self.subTest(body=body):
                self.note('notes/n.md', 'n', sources=['source.txt'], body=body)
                self.assertInvalid('missing wikilink missing')
        for body in (f'```js\n{bad}\n```', f'~~~ weird `x`\n{bad}\n~~~', f'````\n```\n{bad}\n````', f'```\n{bad}'):
            with self.subTest(body=body):
                self.note('notes/n.md', 'n', sources=['source.txt'], body=body)
                self.assertEqual(self.errors()[0], 0, self.errors()[1])
        self.assertEqual(k.prose('```npm test``` passed. [[a]]'), ' passed. [[a]]')

    def test_escaped_pipe_wikilink_in_table(self):
        self.note('notes/n.md', 'n', sources=['source.txt'], body='| a |\n| - |\n| [[areas/a\\|Alias]] |\n| [[a\\|Alias]] [[a|B]] [[a\\|x]] |')
        self.assertEqual(self.errors()[0], 0, self.errors()[1])
        self.note('notes/n.md', 'n', sources=['source.txt'], body='| [[nope\\|Alias]] |')
        self.assertInvalid('missing wikilink nope')

    def test_utf8_bom_is_accepted(self):
        file = self.vault / 'notes/n.md'
        file.write_bytes(b'\xef\xbb\xbf' + file.read_bytes())
        status, err = self.errors()
        self.assertEqual(status, 0, err)

    def test_credential_denylist(self):
        for name in ('.npmrc', '.netrc', '.htpasswd', 'id_rsa', 'id_ed25519', 'id_ecdsa', 'x/terraform.tfstate',
                     'terraform.tfstate.backup', 'service-account.json', 'service-account-prod.json', 'deep/dir/.NPMRC'):
            with self.subTest(name=name):
                self.assertTrue(k.credential_path(name))
        for name in ('id_rsa.pub', 'id_ed25519.pub', 'service-accounts.md', 'service_account.py', 'npmrc.md', 'src/service-account.ts'):
            with self.subTest(name=name):
                self.assertFalse(k.credential_path(name))
        (self.repo / '.npmrc').write_text('//registry:_authToken=x')
        self.note('notes/n.md', 'n', sources=['.npmrc'])
        self.assertInvalid('credential source is forbidden')

    def test_crlf_only_difference_is_reported_as_line_endings(self):
        source = self.repo / 'source.txt'
        source.write_bytes(b'one\ntwo\n')
        self.run_cli('snapshot', '--all')
        source.write_bytes(b'one\r\ntwo\r\n')
        status, _, err = self.run_cli('check')
        self.assertEqual(status, 0)
        self.assertIn('line endings differ in source source.txt', err)
        self.assertNotIn('changed source', err)
        self.assertEqual(self.run_cli('check', '--strict')[0], 1)
        source.write_bytes(b'one\r\nthree\r\n')
        self.assertIn('changed source', self.run_cli('check')[2])
        # and the reverse direction
        source.write_bytes(b'one\r\ntwo\r\n')
        self.run_cli('snapshot', '--all')
        source.write_bytes(b'one\ntwo\n')
        self.assertIn('line endings differ', self.run_cli('check')[2])

    def test_generated_writes_are_atomic(self):
        self.run_cli('snapshot', '--all')
        snapshot = self.vault / '.knowledge/sources.json'
        before = snapshot.read_bytes()
        real = k.os.replace
        calls = []

        def failing(src, dst):
            calls.append(dst)
            raise OSError('disk full')
        k.os.replace = failing
        try:
            (self.repo / 'source2.txt').write_text('x')
            self.note('notes/m.md', 'm', sources=['source2.txt'])
            with self.assertRaises(OSError):
                self.run_cli('snapshot', '--all')
        finally:
            k.os.replace = real
        self.assertTrue(calls)
        self.assertEqual(before, snapshot.read_bytes())
        self.assertEqual([p.name for p in snapshot.parent.iterdir()], ['sources.json'])
        self.assertEqual(self.run_cli('snapshot', '--all')[0], 0)
        self.assertEqual([p.name for p in snapshot.parent.iterdir()], ['sources.json'])
        self.assertEqual(oct(snapshot.stat().st_mode & 0o777), oct(0o666 & ~self.umask()))

    def test_missing_source_severity_follows_gap_decision(self):
        live = [{}, {'decision': 'accepted', 'decided_by': 'Ann', 'decided_on': '2026-11-15'},
                {'decision': 'deferred', 'decided_by': 'Ann', 'decided_on': '2026-11-15'}]
        closed = [{'decision': 'done'}, {'decision': 'rejected', 'decided_by': 'Ann', 'decided_on': '2026-11-15'},
                  {'decision': 'duplicate', 'duplicate_of': 'other'}]
        self.gap('other')
        for props in live + closed:
            with self.subTest(props=props):
                self.gap('g', sources=['gone.txt'], body=section_body(), **props)
                status, err = self.errors()
                if props in live:
                    self.assertEqual(status, 1)
                    self.assertIn('missing or not a file', err)
                else:
                    self.assertEqual(status, 0, err)
                    self.assertIn('WARNING: gaps/g.md: missing source gone.txt', err)
        (self.vault / 'gaps/g.md').unlink()
        self.gap('done', decision='done', body=section_body())
        self.gap('acc', decision='accepted', decided_by='Ann', decided_on='2026-11-15', body=section_body())
        self.note('plans/p1.md', 'p1', 'plan', status='planned', gap='done', sources=['gone.txt'])
        status, err = self.errors()
        self.assertEqual(status, 0, err)
        self.assertIn('plans/p1.md: missing source gone.txt', err)
        self.note('plans/p2.md', 'p2', 'plan', status='planned', gap='acc', sources=['gone.txt'])
        self.assertInvalid('p2.md: gone.txt: source is missing')

    def test_edges_include_gap_and_plan_links_and_plan_gap(self):
        self.gap('g', decision='accepted', decided_by='Ann', decided_on='2026-11-15', body=section_body() + '[[notes/n]]')
        self.note('plans/p.md', 'p', 'plan', status='planned', gap='g', body='nothing linked')
        self.build()
        graph = json.loads((self.vault / '.knowledge/graph.json').read_text())
        edges = {(e['source'], e['target']) for e in graph['edges']}
        self.assertIn(('g', 'n'), edges)
        self.assertIn(('p', 'g'), edges)

    def test_priority_confidence_duplicate_of_nodes_and_recheck_staleness(self):
        self.gap('other')
        self.gap('dup', decision='duplicate', duplicate_of='other')
        self.gap('c', recheck='confirmed', rechecked_by='Bob', rechecked_on='2026-11-15', priority='high',
                 confidence='low', sources=['source.txt'], body=section_body())
        self.gap('nc', sources=['source.txt'])
        self.run_cli('snapshot', '--all')
        self.build()
        nodes = {n['id']: n for n in json.loads((self.vault / '.knowledge/graph.json').read_text())['nodes']}
        self.assertEqual((nodes['c']['priority'], nodes['c']['confidence'], nodes['c']['duplicateOf']), ('high', 'low', ''))
        self.assertEqual((nodes['dup']['duplicateOf'], nodes['n']['priority'], nodes['n']['duplicateOf']), ('other', '', ''))
        self.assertFalse(nodes['c']['recheckOutdated'])
        (self.repo / 'source.txt').write_text('different')
        self.build()
        nodes = {n['id']: n for n in json.loads((self.vault / '.knowledge/graph.json').read_text())['nodes']}
        self.assertTrue(nodes['c']['recheckOutdated'])   # rechecked, and its source changed since
        self.assertFalse(nodes['nc']['recheckOutdated'])  # never rechecked: nothing to flag
        # stored fields are never rewritten
        self.assertIn('recheck: "confirmed"', (self.vault / 'gaps/c.md').read_text())

    # review round 1
    def test_embeds_are_resolved_and_cannot_reach_the_gap_layer(self):
        self.gap(decision='done', body=section_body())
        self.note('notes/n.md', 'n', sources=['source.txt'], body='![[gaps/g]]')
        self.assertInvalid('spec pages must not link to the gap layer (embed gaps/g)')
        self.note('notes/n.md', 'n', sources=['source.txt'], body='![[nowhere]]')
        self.assertInvalid('missing embed nowhere')
        self.note('notes/n.md', 'n', sources=['source.txt'], body='![[pic.png]]')
        self.assertInvalid('missing embed pic.png')
        (self.vault / 'attachments').mkdir()
        (self.vault / 'attachments/pic.png').write_bytes(b'png')
        self.assertEqual(self.errors()[0], 0, self.errors()[1])
        self.note('notes/n.md', 'n', sources=['source.txt'], body='![[areas/a]] ![[a#x|alias]]')
        self.assertEqual(self.errors()[0], 0, self.errors()[1])

    def test_markdown_links_to_the_gap_layer_are_rejected_from_spec_pages(self):
        self.gap(decision='done', body=section_body())
        for body in ('[x](../gaps/g.md)', '[x](<../gaps/g.md#top>)', '[x](../gaps/%67.md)', '[queue](../GAPS.md)',
                     '[queue](../gaps.md)', '[x]: ../gaps/g.md'):
            with self.subTest(body=body):
                self.note('notes/n.md', 'n', sources=['source.txt'], body=body)
                self.assertInvalid('spec pages must not link to the gap layer')
        self.note('areas/a.md', 'a', 'area', areas=[], body='[x](../gaps/g.md)')
        self.assertInvalid('spec pages must not link to the gap layer')
        self.note('areas/a.md', 'a', 'area', areas=[])
        for body in ('[ok](../source.txt) [web](https://example.invalid/gaps/g.md) `[c](../gaps/g.md)`', '```\n[c](../gaps/g.md)\n```'):
            self.note('notes/n.md', 'n', sources=['source.txt'], body=body)
            self.assertEqual(self.errors()[0], 0, self.errors()[1])
        self.gap(body=section_body() + '[n](../notes/n.md)', decision='done')
        self.assertEqual(self.errors()[0], 0, self.errors()[1])

    def test_links_in_title_or_summary_of_spec_pages_are_rejected(self):
        for key, value in (('title', 'See [[gaps/g]]'), ('summary', 'See [q](GAPS.md)'), ('summary', '![[gaps/g]]')):
            with self.subTest(key=key):
                self.note('notes/n.md', 'n', sources=['source.txt'], **{key: value})
                self.assertInvalid(f'{key} of a spec page must not contain links')
        self.note('areas/a.md', 'a', 'area', areas=[], summary='[[g]]')
        self.assertInvalid('summary of a spec page must not contain links')
        self.note('areas/a.md', 'a', 'area', areas=[], summary='Plain [brackets] and (parens).')
        self.note('notes/n.md', 'n', sources=['source.txt'])
        self.assertEqual(self.errors()[0], 0, self.errors()[1])

    def test_control_characters_in_properties_are_rejected(self):
        for char in ('\r', '\n', '\t', '\x00', '\x7f', '\x85', ' ', ' '):
            for key, value in (('title', 'a' + char + 'b'), ('summary', 'a' + char + 'b'), ('tags', ['x' + char]), ('sources', ['source.txt' + char])):
                with self.subTest(char=repr(char), key=key):
                    self.note('notes/n.md', 'n', **{key: value, **({} if key == 'sources' else {'sources': ['source.txt']})})
                    # Raw U+0085/U+2028/U+2029 break the one-property-per-line frontmatter before validation.
                    self.assertInvalid('ERROR: notes/n.md')
        for char in ('\\u0085', '\\u2028', '\\u2029'):  # JSON escapes survive line splitting, so validation must catch them
            self.note('notes/n.md', 'n', sources=['source.txt'])
            path = self.vault / 'notes/n.md'
            path.write_text(path.read_text().replace('title: "Тест n"', 'title: "a' + char + 'b"'))
            self.assertInvalid('title must not contain control characters')
        self.gap(rechecked_by='agent, 2026-11-15)\r\r## accepted', recheck='confirmed', rechecked_on='2026-11-15', body=section_body())
        self.assertInvalid('rechecked_by must not contain control characters')

    def test_outdated_recheck(self):
        for props, fragment in (({'recheck': 'outdated'}, 'rechecked_by is required'),
                                ({'recheck': 'outdated', 'rechecked_by': 'agent', 'rechecked_on': '2026-11-15'}, None)):
            with self.subTest(props=props):
                self.gap(body=section_body(), **props)
                if fragment:
                    self.assertInvalid(fragment)
                else:
                    self.assertEqual(self.errors()[0], 0, self.errors()[1])
        self.gap(recheck='outdated', rechecked_by='agent', rechecked_on='2026-11-15', body=section_body(Recheck=' '))
        self.assertInvalid('Recheck section must say what was checked')
        self.assertEqual(k.gap_state({'decision': 'open', 'recheck': 'outdated'}), 'needs-recheck')
        self.assertEqual(k.gap_state({'decision': 'accepted', 'recheck': 'outdated'}), 'accepted')
        self.gap(recheck='outdated', rechecked_by='Bob', rechecked_on='2026-11-15', body=section_body(), sources=['source.txt'])
        self.build()
        node = next(n for n in json.loads((self.vault / '.knowledge/graph.json').read_text())['nodes'] if n['id'] == 'g')
        self.assertEqual((node['state'], node['recheckOutdated']), ('needs-recheck', True))

    def test_recheck_outdated_flag_ignores_line_endings_and_non_gaps(self):
        source = self.repo / 'source.txt'
        source.write_bytes(b'a\nb\n')
        self.gap(recheck='confirmed', rechecked_by='Bob', rechecked_on='2026-11-15', body=section_body(), sources=['source.txt'])
        self.run_cli('snapshot', '--all')
        flags = lambda: {n['id']: n['recheckOutdated'] for n in json.loads((self.vault / '.knowledge/graph.json').read_text())['nodes']}
        self.build()
        self.assertEqual(set(flags().values()), {False})
        source.write_bytes(b'a\r\nb\r\n')
        self.build()
        self.assertFalse(flags()['g'])
        source.write_bytes(b'different')
        self.build()
        self.assertTrue(flags()['g'])
        self.assertFalse(flags()['n'])

    def test_priority_and_confidence_only_on_gaps_and_plans(self):
        for key in ('priority', 'confidence'):
            with self.subTest(key=key):
                self.note('notes/n.md', 'n', sources=['source.txt'], **{key: 'high'})
                self.assertInvalid(f'{key} is only valid on gap and plan pages')
                self.note('areas/a.md', 'a', 'area', areas=[], **{key: 'high'})
                self.assertInvalid(f'{key} is only valid on gap and plan pages')
                self.note('areas/a.md', 'a', 'area', areas=[])
        self.note('notes/n.md', 'n', sources=['source.txt'])
        self.gap('done-gap', decision='done', body=section_body())
        self.note('plans/p.md', 'p', 'plan', status='planned', gap='done-gap', priority='high', confidence='low')
        self.gap('g2', priority='high', confidence='low')
        self.assertEqual(self.errors()[0], 0, self.errors()[1])

    def test_credential_denylist_folds_lookalikes_and_covers_more_names(self):
        for name in ('.ſſh/id_rſa', '.SSH/id_rsa', 'a/.git/config', '.git', '.git-credentials', 'credentials.json',
                     'client_secret_123.json', 'secrets.yaml', 'secrets.json', '.envrc', '.pgpass', '.pypirc', '_netrc',
                     '.vault-token', '.terraformrc', '.kube/config', 'home/.docker/config.json',
                     'application_default_credentials.json', 'id_dsa', 'x.jks', 'x.ppk', 'x.p8', 'prod.tfvars', 'a.auto.tfvars', 'x.gpg'):
            with self.subTest(name=name):
                self.assertTrue(k.credential_path(name))
        for name in ('config', '.kube/other', 'docker/config.json', 'secret.md', 'credentials.md', 'src/.github/x.yml', 'client.json'):
            with self.subTest(name=name):
                self.assertFalse(k.credential_path(name))
        (self.repo / '.ssh').mkdir()
        (self.repo / '.ssh/id_rsa').write_text('private')
        self.note('notes/n.md', 'n', sources=['.ſſh/id_rſa'])
        self.assertInvalid('credential source is forbidden')
        self.assertEqual(self.run_cli('snapshot', '--all')[0], 1)
        self.assertFalse((self.vault / '.knowledge/sources.json').exists())

    # review round 2
    def test_embed_of_a_dotted_note_name_resolves_as_a_note(self):
        self.note('notes/v1.2-rule.md', 'dotted', sources=['source.txt'])
        self.note('notes/n.md', 'n', sources=['source.txt'], body='![[notes/v1.2-rule]] ![[v1.2-rule]] [[notes/v1.2-rule]]')
        self.assertEqual(self.errors()[0], 0, self.errors()[1])
        self.note('notes/n.md', 'n', sources=['source.txt'], body='![[notes/v9.9-missing]]')
        self.assertInvalid('missing embed notes/v9.9-missing')
        (self.vault / 'pic.v2.png').write_bytes(b'x')
        self.note('notes/n.md', 'n', sources=['source.txt'], body='![[pic.v2.png]]')
        self.assertEqual(self.errors()[0], 0, self.errors()[1])

    def test_wikilink_pattern_is_linear_on_unbalanced_brackets(self):
        import time
        started = time.perf_counter()
        self.assertEqual(k.LINK.findall('[[' * 20000), [])
        self.assertEqual(k.LINK.findall('![[x]] [[y|z]] [[a]]'), [('!', 'x'), ('', 'y|z'), ('', 'a')])
        self.assertLess(time.perf_counter() - started, 1.0)

    # first real sync: recheck wording, cascading errors, dirty sources, partial snapshots
    def test_failed_page_is_a_link_target_and_causes_no_follow_on_errors(self):
        # One broken page of each kind: a note, an area (by id), a gap (by id).
        self.note('notes/broken.md', 'broken', status=None)
        self.note('areas/ba.md', 'ba', 'area', areas=[], updated='2026-13-45')
        self.gap('fg', recheck='bogus')
        self.gap('dup', decision='duplicate', duplicate_of='fg')
        self.note('plans/p.md', 'p', 'plan', status='planned', gap='fg')
        self.note('notes/m.md', 'm', areas=['a', 'ba'], sources=['source.txt'],
                  body='[[broken]] [[notes/broken]] ![[broken]] [[nowhere]]')
        status, err = self.errors()
        self.assertEqual(status, 1, err)
        errors = [line for line in err.splitlines() if line.startswith('ERROR:')]
        self.assertEqual(len(errors), 4, err)  # three broken pages plus the one genuinely missing link
        self.assertIn('notes/m.md: missing wikilink nowhere', err)
        for noise in ('missing wikilink broken', 'missing embed broken', 'unknown area', 'is not the id of an existing gap', 'has decision'):
            self.assertNotIn(noise, err)
        self.assertIn('check: failed, 4 errors on 4 pages', err)

    def test_snapshot_notes_needs_only_the_selected_pages_valid(self):
        self.note('notes/broken.md', 'broken', status=None)
        self.note('notes/m.md', 'm', sources=['source.txt'], body='[[broken]]')
        self.assertEqual(self.run_cli('check')[0], 1)
        status, out, err = self.run_cli('snapshot', '--notes', 'n')
        self.assertEqual(status, 0, err)
        self.assertIn('1 errors on 1 other pages do not block this snapshot', err)
        baseline = json.loads((self.vault / '.knowledge/sources.json').read_text())
        self.assertEqual(sorted(baseline), ['n'])
        # A selected page that links to the broken page is refused; the link only looks fine because the error is not repeated.
        status, _, err = self.run_cli('snapshot', '--notes', 'n', 'm')
        self.assertEqual(status, 1)
        self.assertIn('notes/m.md: link broken names a page that failed validation', err)
        self.assertEqual(sorted(json.loads((self.vault / '.knowledge/sources.json').read_text())), ['n'])
        # The selected page itself must be valid, including one whose own frontmatter fails.
        before = (self.vault / '.knowledge/sources.json').read_bytes()
        self.note('notes/m.md', 'm', sources=['source.txt'], body='[[nowhere]]')
        self.assertEqual(self.run_cli('snapshot', '--notes', 'm')[0], 1)
        self.assertEqual(self.run_cli('snapshot', '--notes', 'broken')[0], 1)
        self.assertEqual(self.run_cli('snapshot', '--notes', 'absent')[0], 1)
        self.assertEqual(before, (self.vault / '.knowledge/sources.json').read_bytes())
        # Whole-vault commands still demand a fully valid vault.
        self.note('notes/m.md', 'm', sources=['source.txt'])
        for args in (('snapshot', '--all'), ('check',)):
            self.assertEqual(self.run_cli(*args)[0], 1, args)
        # A damaged baseline is vault-wide, so it blocks even a partial snapshot.
        (self.vault / 'notes/broken.md').unlink()
        (self.vault / '.knowledge/sources.json').write_text('[]')
        self.assertEqual(self.run_cli('snapshot', '--notes', 'n')[0], 1)

    def git_in(self, top, *args):
        return subprocess.run(['git', '-C', str(top), *args], capture_output=True, text=True, check=True).stdout

    def init_git(self, top):
        self.git_in(top, 'init', '-b', 'main')
        self.git_in(top, 'config', 'user.email', 'test@example.invalid')
        self.git_in(top, 'config', 'user.name', 'Test')
        self.git_in(top, 'add', '.')
        self.git_in(top, 'commit', '-m', 'base')

    def test_ignore_dirty_forgives_only_uncommitted_changes(self):
        self.init_git(self.repo)
        self.assertEqual(self.run_cli('snapshot', '--all')[0], 0)
        (self.repo / 'source.txt').write_text('edited', encoding='utf-8')
        status, _, err = self.run_cli('check', '--strict')
        self.assertEqual(status, 1)
        self.assertNotIn('not counted', err)
        status, out, err = self.run_cli('check', '--strict', '--ignore-dirty')
        self.assertEqual(status, 0, err)
        self.assertIn('WARNING: notes/n.md: changed source source.txt (uncommitted change, not counted)', err)
        self.assertIn('(1 uncommitted, not counted)', out)
        self.git_in(self.repo, 'add', 'source.txt')  # staged still counts as uncommitted
        self.assertEqual(self.run_cli('check', '--strict', '--ignore-dirty')[0], 0)
        self.git_in(self.repo, 'commit', '-m', 'edit')  # committed changes are real
        status, _, err = self.run_cli('check', '--strict', '--ignore-dirty')
        self.assertEqual(status, 1)
        self.assertIn('changed source source.txt\n', err + '\n')
        self.assertNotIn('not counted', err)
        # Untracked sources and a repo that is a subdirectory of the work tree.
        (self.repo / 'new.txt').write_text('one', encoding='utf-8')
        self.note('notes/u.md', 'u', sources=['new.txt'])
        self.assertEqual(self.run_cli('snapshot', '--notes', 'u')[0], 0)
        (self.repo / 'new.txt').write_text('two', encoding='utf-8')
        self.assertEqual(self.run_cli('check', '--strict', '--ignore-dirty')[0], 1)  # n is still committed-changed
        # An untracked file has no HEAD blob to equal the accepted bytes, so it is never forgiven.
        self.assertIn('changed source new.txt\n', self.run_cli('check', '--ignore-dirty')[2])

    def test_markdown_links_to_failed_pages_keep_their_type(self):
        self.note('gaps/g/broken.md', 'gb', 'gap', status=None)  # fails, but declares itself a gap
        self.note('notes/broken.md', 'broken', status=None)
        self.note('notes/u.md', 'u', sources=['source.txt'], body='[x](../gaps/g/broken.md)')
        self.note('notes/m.md', 'm', sources=['source.txt'], body='[x](broken.md)')
        self.note('runs/r.md', 'r', 'run', areas=[], body='[x](../notes/broken.md)')
        status, err = self.errors()
        self.assertIn('notes/u.md: spec pages must not link to the gap layer (../gaps/g/broken.md)', err)
        self.assertIn('runs/r.md: run pages are history', err)
        self.assertNotIn('ERROR: notes/m.md', err)  # a failed note is a fine target
        self.assertEqual(self.run_cli('snapshot', '--notes', 'u')[0], 1)
        # An unknown type cannot be judged: no error of its own, but it blocks the snapshot of the linking page.
        self.note('notes/unk.md', 'unk', status=None)
        (self.vault / 'notes/unk.md').write_text('---\nid: "unk"\n---\n')
        self.note('notes/m.md', 'm', sources=['source.txt'], body='[x](unk.md)')
        self.assertNotIn('ERROR: notes/m.md', self.errors()[1])
        status, _, err = self.run_cli('snapshot', '--notes', 'm')
        self.assertEqual(status, 1)
        self.assertIn('notes/m.md: link unk.md names a page that failed validation', err)

    def test_plan_gap_and_duplicate_of_cascade_only_for_failed_gaps(self):
        self.gap('fg', recheck='bogus')  # fails, still a gap
        self.note('plans/p.md', 'p', 'plan', status='planned', gap='fg', sources=['source.txt'])
        self.gap('dup', decision='duplicate', duplicate_of='fg')
        self.note('notes/broken.md', 'broken', status=None)
        self.note('plans/q.md', 'q', 'plan', status='planned', gap='broken', sources=['source.txt'])
        self.gap('dup2', decision='duplicate', duplicate_of='broken')
        status, err = self.errors()
        self.assertIn('plans/q.md: gap broken is not the id of an existing gap', err)
        self.assertIn('duplicate_of broken is not the id of an existing gap', err)
        self.assertNotIn('ERROR: plans/p.md', err)
        self.assertNotIn('ERROR: gaps/dup.md', err)
        for ident in ('p', 'dup'):
            with self.subTest(ident=ident):
                status, _, err = self.run_cli('snapshot', '--notes', ident)
                self.assertEqual(status, 1)
                self.assertIn('names a page that failed validation', err)

    def test_ignore_dirty_does_not_hide_a_committed_unreviewed_change(self):
        self.init_git(self.repo)
        self.assertEqual(self.run_cli('snapshot', '--all')[0], 0)
        (self.repo / 'source.txt').write_text('committed change', encoding='utf-8')
        self.git_in(self.repo, 'commit', '-am', 'edit')
        self.assertEqual(self.run_cli('check', '--strict', '--ignore-dirty')[0], 1)
        (self.repo / 'source.txt').write_text('committed change\n', encoding='utf-8')  # whitespace edit on top
        status, _, err = self.run_cli('check', '--strict', '--ignore-dirty')
        self.assertEqual(status, 1, err)
        self.assertNotIn('not counted', err)
        # Line-ending variants of the accepted bytes still count as uncommitted-only drift.
        self.git_in(self.repo, 'checkout', 'source.txt')
        (self.repo / 'source.txt').write_bytes(b'one\ntwo\n')
        self.git_in(self.repo, 'commit', '-am', 'back')
        self.assertEqual(self.run_cli('snapshot', '--all')[0], 0)
        (self.repo / 'source.txt').write_bytes(b'one\r\ntwo\r\n')
        status, _, err = self.run_cli('check', '--strict', '--ignore-dirty')
        self.assertEqual(status, 0, err)
        self.assertIn('line endings differ in source source.txt (uncommitted change, not counted)', err)

    def test_cascade_suppression_hides_only_the_missing_error(self):
        self.note('notes/broken.md', 'broken', status=None)
        self.note('gaps/g/broken.md', 'gb', 'gap', status=None)  # a failed page that still says it is a gap
        self.note('notes/other/broken.md', 'broken2', status=None)
        self.note('notes/w.md', 'w', sources=['source.txt'], body='[[broken]]')  # two failed pages share the name
        self.note('notes/v.md', 'v', sources=['source.txt'], body='[[gaps/g/broken]]')
        self.note('notes/x.md', 'x', areas=['n'], sources=['source.txt'])  # n is a note, not an area
        status, err = self.errors()
        self.assertEqual(status, 1, err)
        self.assertIn('notes/w.md: ambiguous wikilink broken', err)
        self.assertIn('notes/v.md: spec pages must not link to the gap layer', err)
        self.assertIn('notes/x.md: unknown area n', err)

    def test_snapshot_notes_refuses_a_page_with_a_bad_area_or_wrong_type_target(self):
        self.note('areas/ba.md', 'ba', 'area', areas=[], updated='2026-13-45')
        self.note('notes/m.md', 'm', areas=['a', 'ba'], sources=['source.txt'])
        before = (self.vault / '.knowledge/sources.json').read_bytes() if (self.vault / '.knowledge/sources.json').exists() else None
        status, _, err = self.run_cli('snapshot', '--notes', 'm')
        self.assertEqual(status, 1)
        self.assertIn('notes/m.md: area ba names a page that failed validation', err)
        self.assertEqual(before, (self.vault / '.knowledge/sources.json').read_bytes() if (self.vault / '.knowledge/sources.json').exists() else None)
        self.note('notes/m.md', 'm', areas=['n'], sources=['source.txt'])
        status, _, err = self.run_cli('snapshot', '--notes', 'm')
        self.assertEqual(status, 1)
        self.assertIn('notes/m.md: unknown area n', err)

    def test_ignore_dirty_in_a_subdirectory_of_the_work_tree_and_outside_git(self):
        with self.assertRaises(SystemExit) as exc, redirect_stderr(StringIO()):
            self.run_cli('check', '--ignore-dirty')
        self.assertEqual(exc.exception.code, 2)
        self.assertEqual(self.run_cli('snapshot', '--all')[0], 0)
        self.init_git(self.root)
        (self.repo / 'source.txt').write_text('edited', encoding='utf-8')
        status, _, err = self.run_cli('check', '--strict', '--ignore-dirty')
        self.assertEqual(status, 0, err)
        self.assertIn('(uncommitted change, not counted)', err)
        for args in (('serve', '--ignore-dirty'), ('snapshot', '--all', '--ignore-dirty')):
            with self.subTest(args=args), self.assertRaises(SystemExit) as exc, redirect_stderr(StringIO()):
                self.run_cli(*args)
            self.assertEqual(exc.exception.code, 2)

    @staticmethod
    def umask():
        mask = k.os.umask(0)
        k.os.umask(mask)
        return mask


if __name__ == '__main__':
    unittest.main()
