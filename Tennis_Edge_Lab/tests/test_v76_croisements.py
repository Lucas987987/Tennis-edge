"""V7.6 croisements : jointure date + paire, attendu Pinnacle / moteur, moitiés
chronologiques, Holm, statut ; aucune donnée inventée."""
import datetime as dt
import importlib.util
import json
import pathlib
import random
import shutil
import tempfile
import unittest

LAB = pathlib.Path(__file__).resolve().parents[1]
ROOT = LAB.parent
spec = importlib.util.spec_from_file_location("tennis_edge_t_cr", LAB / "croisements.py")
cr = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cr)


def fabriquer(d, n=400, biais_veille=0.0, graine=5):
    rnd = random.Random(graine)
    (d / "clv_history").mkdir()
    (d / "simulateur").mkdir()
    shutil.copy(ROOT / "simulateur" / "table_sets.json", d / "simulateur" / "table_sets.json")
    lignes, sr, log = [], {}, []
    jour0 = dt.date(2026, 7, 1)
    for i in range(n):
        j = jour0 + dt.timedelta(days=i // 6)
        h, a = f"Joueur A{i}", f"Joueur B{i}"
        p = 0.55 + 0.4 * rnd.random()                           # favori = home
        ch, ca = round(1 / (p * 1.025), 3), round(1 / ((1 - p) * 1.025), 3)
        veille = i % 4 == 0
        if veille:                                             # le favori a joué la veille
            lignes.append({"uid": f"v{i}", "commence_time": f"{j - dt.timedelta(days=1)}T10:00:00Z", "home": h, "away": f"X{i}",
                           "tournament": "ATP Test", "home_metrics": {"open": 1.5, "close": 1.5}, "away_metrics": {"open": 2.6, "close": 2.6}})
        pv = p - (biais_veille if veille else 0.0)
        gagne = rnd.random() < pv
        w = "home" if gagne else "away"
        if rnd.random() < 0.6:                                   # en 2 sets
            s1 = s2 = w
        else:                                                    # en 3 sets : sets 1 et 2 partagés
            s1 = "home" if rnd.random() < 0.5 else "away"
            s2 = "away" if s1 == "home" else "home"
        lignes.append({"uid": f"u{i}", "commence_time": f"{j}T12:00:00Z", "home": h, "away": a, "tournament": "ATP Test",
                       "home_metrics": {"open": ch, "close": ch, "n_points": 30}, "away_metrics": {"open": ca, "close": ca}})
        # set_results sous l'autre format d'identifiant (date_noms), dans l'ordre inverse une fois sur deux
        if i % 2:
            sr[f"{j}_{cr.norm(h)}_{cr.norm(a)}"] = {"match": "home" if gagne else "away", "set1": s1, "set2": s2}
        else:
            inv = lambda v: "away" if v == "home" else "home"
            sr[f"{j}_{cr.norm(a)}_{cr.norm(h)}"] = {"match": inv("home" if gagne else "away"), "set1": inv(s1), "set2": inv(s2)}
        if i % 10 == 0:
            log.append({"uid": f"{j}_{cr.norm(h)}_{cr.norm(a)}", "joueur": a, "adversaire": h, "commence": f"{j}T12:00:00", "cote": 3.0})
    (d / "clv_history" / "clv_history_2026-07.jsonl").write_text("".join(json.dumps(x) + "\n" for x in lignes))
    (d / "set_results.json").write_text(json.dumps(sr))
    (d / "h17_signal_log.jsonl").write_text("".join(json.dumps(x) + "\n" for x in log))


class Croisements(unittest.TestCase):
    def test_table_interpolee(self):
        T = cr.Table(ROOT)
        t = T("ATP", 0.725)
        self.assertAlmostEqual(t["2-0"] + t["2-1"], 0.725, delta=0.002)   # victoire = somme des scores gagnants
        self.assertGreater(T("ATP", 0.9)["2-0"], T("ATP", 0.6)["2-0"])

    def test_bout_en_bout_sans_effet(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = pathlib.Path(tmp)
            fabriquer(d)
            doc = cr.build(d)
            self.assertEqual(doc["matchs"], 400)                      # les 100 matchs « de la veille » n'ont pas de résultat
            tous = [L for L in doc["lignes"] if L["circonstance"] == "tous les matchs" and L["issue"] == "victoire"][0]
            self.assertEqual(tous["decouverte"]["n"] + tous["confirmation"]["n"], 400)
            self.assertLess(abs(tous["decouverte"]["z"]), 3)
            h17 = [L for L in doc["lignes"] if L["circonstance"] == "H17 sur l'outsider" and L["issue"] == "victoire"][0]
            self.assertEqual(h17["decouverte"]["n"] + h17["confirmation"]["n"], 40)
            veille = [L for L in doc["lignes"] if L["circonstance"] == "favori a joué la veille" and L["issue"] == "victoire"][0]
            self.assertEqual(veille["decouverte"]["n"] + veille["confirmation"]["n"], 100)
            # la victoire est tirée sans biais : rien ne doit y être confirmé (les sets du générateur,
            # eux, ne suivent pas le moteur — l'outil a le droit de le voir)
            self.assertFalse(any(L["statut"] == "confirmé" for L in doc["lignes"] if L["issue"] == "victoire"))

    def test_effet_reel_confirme(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = pathlib.Path(tmp)
            fabriquer(d, n=2400, biais_veille=0.25)
            doc = cr.build(d)
            v = [L for L in doc["lignes"] if L["circonstance"] == "favori a joué la veille" and L["issue"] == "victoire"][0]
            self.assertEqual(v["statut"], "confirmé")
            self.assertLess(v["decouverte"]["ecart"], -15)

    def test_holm(self):
        h = cr.holm({"a": 0.01, "b": 0.04, "c": 0.5})
        self.assertAlmostEqual(h["a"], 0.03)
        self.assertAlmostEqual(h["b"], 0.08)
        self.assertAlmostEqual(h["c"], 0.5)


if __name__ == "__main__":
    unittest.main()
