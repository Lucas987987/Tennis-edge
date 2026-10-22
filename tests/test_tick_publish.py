# -*- coding: utf-8 -*-
"""Tests de la publication des ticks par run (correction B+D, prototype).
Dépôts Git locaux temporaires uniquement : ni réseau, ni main, ni R2.

    pytest tests/test_tick_publish.py
"""
import gzip
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import threading
import unittest

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RACINE, 'scripts'))


def _charger(nom):
    spec = importlib.util.spec_from_file_location(nom, os.path.join(RACINE, 'scripts', nom + '.py'))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


TP = _charger('tick_publish')
PW = _charger('r2_partition_worker')
JOUR = '2026-10-14'


def git(*a, cwd=None):
    r = subprocess.run(['git', *a], cwd=cwd, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    return r.stdout.strip()


def ticks(run, n, provider='kalshi'):
    return [{'ts': f'{JOUR}T10:{run % 60:02d}:{i % 60:02d}.{i:03d}', 'ticker': f'T{run}',
             'mid': 0.5 + i / 1000, 'run': run, 'i': i} for i in range(n)]


def gz(rows):
    return gzip.compress(''.join(json.dumps(r, sort_keys=True) + '\n' for r in rows).encode(), mtime=0)


def lire(data):
    return [json.loads(x) for x in gzip.decompress(data).splitlines() if x.strip()]


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.t = self.tmp.name
        self.bare = os.path.join(self.t, 'remote.git')
        git('init', '-q', '--bare', '-b', 'inbox', self.bare)
        seed = os.path.join(self.t, 'seed')
        git('clone', '-q', self.bare, seed)
        git('checkout', '-q', '-b', 'inbox', cwd=seed)
        open(os.path.join(seed, 'README'), 'w').write('inbox')
        git('add', '.', cwd=seed)
        git('-c', 'user.name=t', '-c', 'user.email=t@t', 'commit', '-qm', 'init', cwd=seed)
        git('push', '-q', 'origin', 'inbox', cwd=seed)

    def tearDown(self):
        self.tmp.cleanup()

    def clone(self, nom):
        p = os.path.join(self.t, nom)
        git('clone', '-q', '-b', 'inbox', self.bare, p)
        return p

    def etat_remote(self):
        v = os.path.join(self.t, 'verif')
        if os.path.exists(v):
            subprocess.run(['rm', '-rf', v])
        git('clone', '-q', '-b', 'inbox', self.bare, v)
        return v


class Publication(Base):
    def test_pushes_concurrents_zero_perte(self):
        n_runs, par_run = 8, 50
        clones = [self.clone(f'c{i}') for i in range(n_runs)]
        # Tous partent du même état distant puis poussent en même temps.
        barriere = threading.Barrier(n_runs)
        res, erreurs = {}, []

        def tache(i):
            try:
                barriere.wait()
                res[i] = TP.publish_segment(clones[i], 'inbox', 'kalshi', JOUR, 1000 + i, 1,
                                            gz(ticks(i, par_run)), base_wait=0.01)
            except Exception as e:  # noqa
                erreurs.append(repr(e))
        th = [threading.Thread(target=tache, args=(i,)) for i in range(n_runs)]
        [t.start() for t in th]
        [t.join() for t in th]
        self.assertEqual(erreurs, [])
        self.assertTrue(all(v == 'published' for v in res.values()))
        v = self.etat_remote()
        data, rep = TP.consolidate(os.path.join(v, 'inbox'), 'kalshi', JOUR)
        self.assertEqual(rep['sources'], n_runs)
        self.assertEqual(rep['lines_out'], n_runs * par_run)   # aucun tick perdu
        self.assertEqual(rep['duplicates_removed'], 0)
        # Historique linéaire : aucun commit de merge, aucun conflit.
        self.assertEqual(git('rev-list', '--merges', '--count', 'HEAD', cwd=v), '0')

    def test_reprise_apres_rejets_du_push(self):
        hook = os.path.join(self.bare, 'hooks', 'pre-receive')
        compteur = os.path.join(self.t, 'n')
        open(hook, 'w').write(f'#!/bin/sh\nn=$(cat {compteur} 2>/dev/null || echo 0)\n'
                              f'echo $((n+1)) > {compteur}\n[ "$n" -ge 2 ] || exit 1\n')
        os.chmod(hook, 0o755)
        c = self.clone('a')
        attentes = []
        r = TP.publish_segment(c, 'inbox', 'kalshi', JOUR, 1, 1, gz(ticks(1, 10)),
                               sleep=attentes.append, base_wait=1, jitter=0)
        self.assertEqual(r, 'published')
        self.assertEqual(attentes, [1, 2])      # attente croissante, 2 rejets puis succès
        v = self.etat_remote()
        self.assertEqual(len(TP.list_segments(os.path.join(v, 'inbox'), 'kalshi', JOUR)), 1)

    def test_run_au_sha_perime_reprend_apres_un_autre_push(self):
        a, b = self.clone('a'), self.clone('b')     # b est périmé après le push de a
        TP.publish_segment(a, 'inbox', 'kalshi', JOUR, 1, 1, gz(ticks(1, 5)))
        TP.publish_segment(b, 'inbox', 'kalshi', JOUR, 2, 1, gz(ticks(2, 5)))
        v = self.etat_remote()
        _, rep = TP.consolidate(os.path.join(v, 'inbox'), 'kalshi', JOUR)
        self.assertEqual(rep['lines_out'], 10)

    def test_republication_idempotente_et_refus_d_ecrasement(self):
        c = self.clone('a')
        d = gz(ticks(1, 5))
        self.assertEqual(TP.publish_segment(c, 'inbox', 'kalshi', JOUR, 1, 1, d), 'published')
        self.assertEqual(TP.publish_segment(c, 'inbox', 'kalshi', JOUR, 1, 1, d), 'exists')
        with self.assertRaises(TP.PublishError):
            TP.publish_segment(c, 'inbox', 'kalshi', JOUR, 1, 1, gz(ticks(9, 5)), retries=2,
                               sleep=lambda s: None)
        self.assertEqual(git('rev-list', '--count', 'HEAD', cwd=self.etat_remote()), '2')


class ArtifactEtRecuperation(Base):
    def test_echec_definitif_ecrit_artifact_puis_recuperation_idempotente(self):
        art = os.path.join(self.t, 'artifact')
        cassé = os.path.join(self.t, 'cassé')
        git('clone', '-q', '-b', 'inbox', self.bare, cassé)
        git('remote', 'set-url', 'origin', os.path.join(self.t, 'inexistant.git'), cwd=cassé)
        data = gz(ticks(7, 30))
        r = TP.publish_or_artifact(cassé, 'inbox', 'kalshi', JOUR, 7, 1, data, art,
                                   retries=2, sleep=lambda s: None)
        self.assertEqual(r, 'artifact')
        noms = sorted(os.listdir(art))
        self.assertEqual(len(noms), 2)                      # segment + manifeste
        # Récupération depuis un autre dépôt sain, deux fois.
        c = self.clone('ok')
        self.assertEqual(TP.recover(art, c, 'inbox'), {'published': 1, 'exists': 0, 'rejected': 0})
        self.assertEqual(TP.recover(art, c, 'inbox'), {'published': 0, 'exists': 1, 'rejected': 0})
        v = self.etat_remote()
        out, rep = TP.consolidate(os.path.join(v, 'inbox'), 'kalshi', JOUR)
        self.assertEqual(rep['lines_out'], 30)
        self.assertEqual(lire(out), ticks(7, 30))

    def test_artifact_corrompu_rejete(self):
        art = os.path.join(self.t, 'art')
        os.makedirs(art)
        d = gz(ticks(3, 5))
        n = TP.segment_name('kalshi', JOUR, 3, 1)
        open(os.path.join(art, n), 'wb').write(d[:-4] + b'XXXX')
        json.dump(TP.build_manifest('kalshi', JOUR, 3, 1, d),
                  open(os.path.join(art, n.replace('.jsonl.gz', '.manifest.json')), 'w'))
        self.assertEqual(TP.recover(art, self.clone('ok'), 'inbox')['rejected'], 1)

    def test_publication_reussie_n_ecrit_pas_d_artifact(self):
        art = os.path.join(self.t, 'art')
        r = TP.publish_or_artifact(self.clone('a'), 'inbox', 'kalshi', JOUR, 1, 1,
                                   gz(ticks(1, 3)), art)
        self.assertEqual(r, 'published')
        self.assertFalse(os.path.exists(art))


class Consolidation(Base):
    def _remplir(self, ordre):
        inbox = os.path.join(self.t, 'inb')
        d = os.path.join(inbox, 'polymarket', JOUR)
        os.makedirs(d)
        runs = {10: ticks(10, 20), 11: ticks(11, 20), 12: ticks(12, 20)}
        runs[12] = runs[12] + runs[10][:7]          # 7 doublons exacts d'un autre run
        for rid in ordre:
            open(os.path.join(d, TP.segment_name('polymarket', JOUR, rid, 1)), 'wb').write(gz(runs[rid]))
        return inbox

    def test_deduplication_deterministe_quel_que_soit_l_ordre_d_ecriture(self):
        sorties = []
        for ordre in ([10, 11, 12], [12, 11, 10], [11, 12, 10]):
            sorties.append(TP.consolidate(self._remplir(ordre), 'polymarket', JOUR))
            subprocess.run(['rm', '-rf', os.path.join(self.t, 'inb')])
        self.assertEqual({s[1]['sha256'] for s in sorties}, {sorties[0][1]['sha256']})
        self.assertEqual(sorties[0][1]['lines_out'], 60)
        self.assertEqual(sorties[0][1]['duplicates_removed'], 7)
        self.assertEqual(sorties[0][0], sorties[1][0])

    def test_republication_sous_autre_tentative_ne_cree_pas_de_doublon(self):
        inbox = os.path.join(self.t, 'inb')
        d = os.path.join(inbox, 'kalshi', JOUR)
        os.makedirs(d)
        for att in (1, 2):
            open(os.path.join(d, TP.segment_name('kalshi', JOUR, 5, att)), 'wb').write(gz(ticks(5, 12)))
        _, rep = TP.consolidate(inbox, 'kalshi', JOUR)
        self.assertEqual((rep['lines_out'], rep['duplicates_removed']), (12, 12))

    def test_extraction_du_segment_d_un_run(self):
        jour_f = os.path.join(self.t, f'kx_ticks_{JOUR}.jsonl.gz')
        base = gz(ticks(1, 40)) + gz(ticks(2, 40))          # membres déjà sur main
        open(jour_f, 'wb').write(base)
        taille = os.path.getsize(jour_f)
        run = gz(ticks(3, 25)) + gz(ticks(4, 25))           # ajoutés par le run
        open(jour_f, 'ab').write(run)
        seg = TP.extract_run_ticks(jour_f, taille)
        self.assertEqual(seg, run)
        self.assertEqual(len(lire(seg)), 50)
        # Base + segment == fichier du jour d'aujourd'hui, octet pour octet.
        self.assertEqual(base + seg, open(jour_f, 'rb').read())

    def test_segment_tronque_refuse(self):
        f = os.path.join(self.t, 'x.gz')
        open(f, 'wb').write(gz(ticks(1, 20)) + gz(ticks(2, 20))[:-9])
        with self.assertRaises(Exception):
            TP.extract_run_ticks(f, len(gz(ticks(1, 20))))


class CompatibiliteR2V64(Base):
    def test_fichier_consolide_accepte_par_l_analyse_v64_et_octets_stables(self):
        inbox = os.path.join(self.t, 'inb')
        d = os.path.join(inbox, 'kalshi', JOUR)
        os.makedirs(d)
        for rid in (1, 2, 3):
            open(os.path.join(d, TP.segment_name('kalshi', JOUR, rid, 1)), 'wb').write(gz(ticks(rid, 100)))
        data, rep = TP.consolidate(inbox, 'kalshi', JOUR)
        st = PW.analyze('kalshi', JOUR, data)         # même analyse que le worker R2
        self.assertEqual((st['lines'], st['unique_ticks'], st['duplicate_lines'],
                          st['malformed_lines'], st['ts_outside_day_lines']), (300, 300, 0, 0, 0))
        data2, _ = TP.consolidate(inbox, 'kalshi', JOUR)
        self.assertEqual(PW.git_blob_sha(data), PW.git_blob_sha(data2))   # blob SHA-1 reproductible
        self.assertEqual(gzip.decompress(data)[-1:], b'\n')

    def test_nommage_destination_inchange(self):
        # Le fichier consolidé garde parts/<kx|pm>_ticks_<jour>.jsonl.gz : le chemin
        # lu par l'archivage V6.4 ne change pas.
        src = open(os.path.join(RACINE, 'scripts', 'r2_partition_worker.py'), encoding='utf-8').read()
        self.assertIn('_ticks_', src)
        self.assertEqual(TP.PROVIDERS, {'kalshi': 'kx', 'polymarket': 'pm'})


class CadencesInchangees(unittest.TestCase):
    """Cette correction ne touche aucun workflow : cadences et groupes intacts."""
    def test_workflows_collecteurs_identiques_a_main(self):
        for wf in ('kalshi_collector.yml', 'polymarket_collector.yml'):
            r = subprocess.run(['git', 'diff', '--quiet', 'origin/main', '--',
                                f'.github/workflows/{wf}'], cwd=RACINE)
            self.assertIn(r.returncode, (0, 128), wf)   # 128 : pas de remote (hors checkout)

    def test_groupes_de_concurrence_et_duree(self):
        for wf, grp, dur in (('kalshi_collector.yml', 'kalshi-collector', 'KX_DURATION:-900'),
                             ('polymarket_collector.yml', 'polymarket-collector', 'PM_DURATION:-900')):
            t = open(os.path.join(RACINE, '.github', 'workflows', wf), encoding='utf-8').read()
            self.assertIn(f'group: {grp}\n  cancel-in-progress: false', t)
            self.assertIn(dur, t)

    def test_aucun_collecteur_n_importe_tick_publish(self):
        for f in ('kalshi_collector.py', 'polymarket_collector_scripts.py'):
            self.assertNotIn('tick_publish', open(os.path.join(RACINE, 'scripts', f), encoding='utf-8').read())


if __name__ == '__main__':
    unittest.main()
