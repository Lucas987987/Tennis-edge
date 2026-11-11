# -*- coding: utf-8 -*-
"""11/11/2026 (paquet 227) — une étude sur l'archive doit utiliser l'Elo réglé comme celui de la production.

Audit du 11/11/2026 : 19 études rejouaient l'archive avec « Elo() » sans réglage, alors que la production tourne avec les
options de simulateur/elo_etat.json. Sur 2016–2022, le signal favori / outsider appris contre l'Elo sans réglage (β 1,2 à
1,5) ne vaut plus rien une fois ajouté à l'Elo de production (β juste : 0,5 à 0,7) ; le « parcours dans le tournoi »
mesurait surtout les victoires qu'un Elo figé pendant le tournoi n'avait pas encore comptées.

Deux garde-fous :
  1. elo.de_production() rend un Elo réglé EXACTEMENT comme elo_etat.json ;
  2. aucune étude (simulateur/etude_*.py) ne crée un « Elo() » sans réglage, sauf les 19 d'avant l'audit, listées
     ci-dessous. La liste ne peut que RACCOURCIR : une étude reprise avec elo.de_production() doit en sortir.
"""
import glob
import json
import os
import re
import sys
import unittest

ICI = os.path.dirname(os.path.abspath(__file__))
RACINE = os.path.join(ICI, '..')
sys.path.insert(0, os.path.join(RACINE, 'simulateur'))
import elo as E  # noqa: E402

# Études d'avant l'audit qui créent un « Elo() » sans réglage (figé le 11/11/2026). NE RIEN AJOUTER ICI.
AVANT_AUDIT = frozenset((
    'etude_5_derniers_styles', 'etude_age', 'etude_bilans_contexte', 'etude_changement_surface',
    'etude_classement_serie', 'etude_cpi', 'etude_duels_styles', 'etude_ecart_pinnacle', 'etude_live_reevaluation',
    'etude_pistes_saison', 'etude_pistes_tournoi', 'etude_prior_elo', 'etude_profils_contexte', 'etude_retour_absence',
    'etude_set_decisif', 'etude_signaux_combines', 'etude_statistiques_styles', 'etude_tiebreaks',
    'etude_tiebreaks_joueurs'))
ELO_NU = re.compile(r'\bElo\(\s*\)')


def etudes_sur_elo_nu(dossier):
    """Noms des études dont le CODE (hors commentaires et chaînes de documentation simples) crée un Elo() sans réglage."""
    out = set()
    for f in glob.glob(os.path.join(dossier, 'etude_*.py')):
        with open(f, encoding='utf-8') as fh:
            code = '\n'.join(ligne.split('#', 1)[0] for ligne in fh.read().splitlines())
        if ELO_NU.search(code):
            out.add(os.path.basename(f)[:-3])
    return out


class EloDeProduction(unittest.TestCase):
    def test_options_identiques_a_l_etat(self):
        with open(os.path.join(RACINE, 'simulateur', 'elo_etat.json'), encoding='utf-8') as f:
            etat = json.load(f)
        options, bas = E.options_production(RACINE)
        self.assertEqual(options, etat.get('options') or {})
        self.assertEqual(bas, etat.get('depart_bas'))

    def test_elo_vide_et_regle(self):
        el, bas = E.de_production(RACINE)
        options, bas2 = E.options_production(RACINE)
        self.assertEqual(bas, bas2)
        self.assertEqual(el.options(), {'poids_surface': float(options.get('poids_surface', 0.5)),
                                        'welo': options.get('welo'),
                                        'incertitude': float(options.get('incertitude', 0.0))})
        self.assertEqual(el.matchs('personne'), 0)                 # vide : rien n'est repris des joueurs de l'état
        self.assertAlmostEqual(el.proba('a', 'b', 'Hard'), 0.5)

    def test_meme_pronostic_qu_un_elo_regle_a_la_main(self):
        """Rejoué sur quelques matchs, il donne le même % qu'un Elo construit avec les options de l'état."""
        options, _ = E.options_production(RACINE)
        a, _ = E.de_production(RACINE)
        b = E.Elo(**options)
        for g, p, s, part in (('x', 'y', 'Hard', 0.70), ('x', 'z', 'Clay', 0.60), ('y', 'z', 'Hard', None),
                              ('z', 'x', 'Grass', 0.55), ('x', 'y', 'Hard', 0.66)):
            self.assertAlmostEqual(a.proba(g, p, s), b.proba(g, p, s), places=12)
            a.maj(g, p, s, False, part)
            b.maj(g, p, s, False, part)
        self.assertAlmostEqual(a.proba('x', 'z', 'Hard'), b.proba('x', 'z', 'Hard'), places=12)

    def test_un_etat_sans_options_donne_l_elo_de_base(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, 'simulateur'))
            with open(os.path.join(d, 'simulateur', 'elo_etat.json'), 'w', encoding='utf-8') as f:
                json.dump({'joueurs': {}}, f)
            el, bas = E.de_production(d)
            self.assertIsNone(bas)
            self.assertEqual(el.options(), E.Elo().options())


class EtudesSurLEloDeProduction(unittest.TestCase):
    def test_aucune_nouvelle_etude_sur_un_elo_sans_reglage(self):
        nouvelles = etudes_sur_elo_nu(os.path.join(RACINE, 'simulateur')) - AVANT_AUDIT
        self.assertFalse(nouvelles, f"{sorted(nouvelles)} : remplacer « E.Elo() » par « E.de_production(racine) » "
                                    f"(même réglage que la production, mise à jour après chaque match)")

    def test_la_liste_ne_fait_que_raccourcir(self):
        """Une étude reprise (ou supprimée) doit sortir de la liste : elle ne doit pas y rester par oubli."""
        encore = etudes_sur_elo_nu(os.path.join(RACINE, 'simulateur'))
        reprises = AVANT_AUDIT - encore
        self.assertFalse(reprises, f"{sorted(reprises)} n'utilisent plus un Elo sans réglage : les retirer de AVANT_AUDIT")
        self.assertLessEqual(len(AVANT_AUDIT), 19)

    def test_la_detection_voit_un_elo_nu_et_ignore_les_commentaires(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            for nom, code in (('etude_a', 'import elo as E\nel = E.Elo()\n'),
                              ('etude_b', 'import elo as E\nel, bas = E.de_production()\n'),
                              ('etude_c', 'import elo as E\n# avant : el = E.Elo()\nel = E.Elo(**OPTIONS)\n'),
                              ('autre', 'import elo as E\nel = E.Elo()\n')):
                with open(os.path.join(d, nom + '.py'), 'w', encoding='utf-8') as f:
                    f.write(code)
            self.assertEqual(etudes_sur_elo_nu(d), {'etude_a'})


if __name__ == '__main__':
    unittest.main()
