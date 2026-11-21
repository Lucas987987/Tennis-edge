"""Paquet 325 (21/11/2026, Lucas : « dans nos autres projections, on doit retrouver tout ce que l'on peut trouver ; le %
de chance que l'outsider gagne un set ; une image qui reprend toutes les projections »)."""
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RACINE / 'simulateur'))
import scenarios_match as SM  # noqa: E402

HTML = (RACINE / 'algo' / 'index.html').read_text(encoding='utf-8')
FONCS = HTML[HTML.index('function projectionsDe(m){'):HTML.index('function scenariosListe(m){')]
CARTE = HTML[HTML.index('function modeProjections(){'):HTML.index('/* ───────────── carte bilan (?bilan=1)')]

MATCH = {'p_home': 0.64, 'circuit': 'ATP', 'meilleur_des': 3,
         'sets': {'2-0': 0.40, '2-1': 0.24, '1-2': 0.17, '0-2': 0.19},
         'lignes_algo': {'meilleur_des': 3, 'set1_home': 0.6, 'set_decisif': 0.41, 'tie_break': 0.49,
                         'total_plus_20.5': 0.69, 'total_plus_21.5': 0.63, 'total_plus_22.5': 0.54, 'total_plus_23.5': 0.47,
                         'handicap_favori_1.5': 0.58, 'handicap_favori_3.5': 0.40},
         'scenarios': {'j': [{'long': 0.24, 'si_set1_perdu': 0.30}, {'long': 0.17, 'si_set1_perdu': 0.2}],
                       'jeux': {'p10': 18, 'mediane': 23, 'p90': 30}},
         'rythme': {'prevision': {'minutes': 114}}}


def texte(m):
    if not shutil.which('node'):
        raise unittest.SkipTest('node absent')
    js = (FONCS + "\nconst pct1=v=>(Math.round(v*1000)/10).toFixed(1).replace('.',',')+' %';"
          "const hm=x=>Math.floor(x/60)+' h '+String(Math.round(x%60)).padStart(2,'0');"
          f"console.log(JSON.stringify(projectionsTexte({json.dumps(m)},['Zverev','Fils'],pct1,hm)));")
    with tempfile.NamedTemporaryFile('w', suffix='.js', delete=False) as f:
        f.write(js)
    return json.loads(subprocess.run(['node', f.name], capture_output=True, text=True, check=True).stdout)


class Texte(unittest.TestCase):
    def test_tout_y_est(self):
        L = texte(MATCH)
        self.assertIn('▪️ Fils gagne au moins un set : 60,0 %', L)              # 1 − Zverev 2-0
        self.assertIn('▪️ Zverev gagne en deux sets secs : 40,0 %', L)
        self.assertIn('▪️ Zverev gagne le 1er set : 60,0 %', L)
        self.assertIn('▪️ Si Zverev perd le 1er set, il gagne quand même : 30,0 %', L)
        self.assertIn('▪️ Match en 3 sets : 41,0 %', L)
        self.assertIn('▪️ Zverev gagne de plus de 3,5 jeux : 40,0 %', L)
        self.assertIn('▪️ Nombre de jeux : 23 le plus souvent (de 18 à 30, 8 fois sur 10)', L)
        self.assertIn('▪️ Durée prévue : 1 h 54', L)
        self.assertEqual(sum(x.startswith('▪️ Plus de') for x in L), 3)           # la ligne la plus proche de 50 % ± 1

    def test_outsider_a_domicile_ou_exterieur(self):
        m = dict(MATCH, p_home=0.36, sets={'2-0': 0.19, '2-1': 0.17, '1-2': 0.24, '0-2': 0.40})
        self.assertIn('▪️ Zverev gagne au moins un set : 60,0 %', texte(m))

    def test_scenarios_incoherents_ignores(self):
        m = dict(MATCH, scenarios={'j': [{'long': 0.04, 'si_set1_perdu': 0.04}, {'long': 0.05}], 'jeux': {'p10': 1, 'mediane': 2, 'p90': 3}})
        L = texte(m)
        self.assertFalse(any('perd le 1er set' in x or 'Nombre de jeux' in x for x in L))

    def test_les_deux_textes(self):
        self.assertIn('const proj = projectionsTexte(m, [H, A], pct1, hm);', HTML)
        self.assertIn('const proj = projectionsTexte(m, N, pct1, hm);', HTML)
        self.assertNotIn("proj.push(`▪️ Plus de 20,5 jeux", HTML)


class Carte(unittest.TestCase):
    def test_mode_et_script(self):
        self.assertIn("else if (Q.get('projections')) modeProjections();", HTML)
        vs = (RACINE / 'scripts' / 'video_simulation.py').read_text(encoding='utf-8')
        self.assertIn("index.html?projections=1&lang=", vs)
        wf = (RACINE / '.github' / 'workflows' / 'video_simulation.yml').read_text(encoding='utf-8')
        self.assertIn('--projections --sortie videos', wf)
        self.assertIn('videos/projections_${lang}.png', wf)

    def test_regles(self):
        import re
        bas = CARTE.lower()
        for mot in ('cotes?', 'pinnacle', 'value', 'paris?', 'bookmakers?', 'handicap', 'march[eé]'):
            self.assertIsNone(re.search(r'\b' + mot + r'\b', bas.replace('europe/paris', '')), mot)
        self.assertNotIn('gamesetalgo.com', bas)
        self.assertIn('${SIGNE}', CARTE)
        self.assertIn('ne changent pas le % de victoire', CARTE)


class Scenarios(unittest.TestCase):
    def test_distribution_coupee_repesee(self):
        D = [{'score': [[6, 3], [6, 4]], 'vainqueur': 0, 'probabilite': 0.30},
             {'score': [[4, 6], [3, 6]], 'vainqueur': 1, 'probabilite': 0.20},
             {'score': [[4, 6], [6, 3], [6, 4]], 'vainqueur': 0, 'probabilite': 0.05},
             {'score': [[6, 4], [3, 6], [3, 6]], 'vainqueur': 1, 'probabilite': 0.05}]       # 60 % de la masse
        sets = {'2-0': 0.35, '2-1': 0.15, '1-2': 0.15, '0-2': 0.35}
        a = SM.scenarios(D, sets)
        self.assertAlmostEqual(a['j'][0]['long'] + a['j'][1]['long'], 0.30, places=4)
        b = SM.scenarios(D)                                                           # sans le score en sets : l'ancien calcul
        self.assertAlmostEqual(b['j'][0]['long'] + b['j'][1]['long'], 0.10 / 0.60, places=3)

    def test_distribution_complete_inchangee(self):
        D = [{'score': [[6, 3], [6, 4]], 'vainqueur': 0, 'probabilite': 0.6},
             {'score': [[4, 6], [6, 3], [4, 6]], 'vainqueur': 1, 'probabilite': 0.4}]
        self.assertEqual(SM.scenarios(D, {'2-0': 0.6, '1-2': 0.4}), SM.scenarios(D))


if __name__ == '__main__':
    unittest.main()
