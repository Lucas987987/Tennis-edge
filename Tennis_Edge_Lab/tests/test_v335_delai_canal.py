"""Paquet 335 — « le prix est-il encore là ? » pour le canal public et MISER, découpé ATP / WTA / Challenger."""
import datetime as dt
import importlib.util
import json
import pathlib
import sys
import tempfile
import unittest

LAB = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LAB))
spec = importlib.util.spec_from_file_location("t335_delai", LAB / "delai_alertes.py")
da = importlib.util.module_from_spec(spec)
spec.loader.exec_module(da)
UTC = dt.timezone.utc
START = dt.datetime(2026, 10, 20, 15, tzinfo=UTC)
T0 = START - dt.timedelta(hours=2)


def cp(h, o):
    return (START - dt.timedelta(hours=h), o, None)


def pin(tournoi):
    return {"start": START, "home": "Alpha Un", "away": "Beta Deux", "tournament": tournoi,
            "curves": {"home": {"open": cp(30, 2.1), "close": cp(0.1, 2.0), "horizons": {}},
                       "away": {"open": cp(30, 1.8), "close": cp(0.1, 1.9), "horizons": {}}}}


class Lecture(unittest.TestCase):
    def test_circuits(self):
        for t, c in (("ATP Challenger Yokohama", "Challenger"), ("WTA Wuhan", "WTA"), ("ATP Paris", "ATP"),
                     ("ITF M25 Monastir", "ITF"), ("Tournament Paris", "inconnu"), ("Women Singles", "WTA"),
                     ("Men Singles", "ATP")):
            self.assertEqual(da.circuit(t), c, t)
        self.assertEqual(da.circuit("", "WTA Linz"), "WTA")          # repli sur le tournoi de la cote Pinnacle

    def test_canal_un_pari_par_match_joueur_book_jouable(self):
        lignes = [
            {"t": "2026-10-20T13:00:00", "uid": "m1", "joueur": "Alpha Un", "tournoi": "ATP Challenger X",
             "retards": [["bet365", 2.2, 8.0], ["leovegas", 2.3, 9.0], ["unibet", 2.15, 6.0]]},
            {"t": "2026-10-20T13:20:00", "uid": "m1", "joueur": "Alpha Un", "retards": [["bet365", 2.25, 9.0], ["bet365.fr", 2.25, 9.0]]},
            {"t": "2026-10-20T13:30:00", "uid": "m2", "joueur": "Gamma", "retards": []}]
        miser = [{"uid": "m1", "joueur": "Alpha Un", "marche": "match", "book": "tipico", "cote": 2.2, "signale_le": "2026-10-20T13:00:00+00:00", "relance": False},
                 {"uid": "m1", "joueur": "Alpha Un", "marche": "match", "book": "tipico", "cote": 2.3, "signale_le": "2026-10-20T14:00:00+00:00", "relance": True},
                 {"uid": "m3", "joueur": "D", "marche": "set1", "book": "tipico", "cote": 2.3, "signale_le": "2026-10-20T14:00:00+00:00"}]
        with tempfile.TemporaryDirectory() as tmp:
            pathlib.Path(tmp, "canal_public_log.jsonl").write_text("\n".join(json.dumps(x) for x in lignes))
            pathlib.Path(tmp, "miser_signal_log.jsonl").write_text("\n".join(json.dumps(x) for x in miser))
            c, m = da.lire_canal(tmp), da.lire_miser(tmp)
            self.assertEqual(da.alert_uids(tmp), {"m1"})
        self.assertEqual([(a["book"], a["cote"]) for a in c], [("bet365", 2.2), ("unibet", 2.15)])   # leovegas exclu, bet365.fr = bet365
        self.assertEqual([(a["code"], a["cote"]) for a in m], [("MISER", 2.2)])

    def test_par_circuit_et_regle_de_lecture(self):
        records = {("a", "pinnacle"): pin("ATP Challenger X"), ("b", "pinnacle"): pin("WTA Y")}
        serie = {"home": [(T0 - dt.timedelta(days=60), 2.2)], "away": []}
        series = {"a": {"winamax.fr": serie}, "b": {"bet365": serie}}
        al = []
        for i in range(31):
            jour = T0 - dt.timedelta(days=i)
            al.append({"code": "CANAL", "uid": "a", "joueur": "Alpha Un", "book": "winamax.fr", "cote": 2.2, "t": jour, "tournoi": ""})
        al.append({"code": "H17", "uid": "b", "joueur": "Alpha Un", "book": "bet365", "cote": 2.2, "t": T0, "tournoi": "WTA Y"})
        lignes, sans = da.mesurer(al, records, series)
        self.assertEqual(sans, 0)
        pc = {(r["hypothese"], r["circuit"], r["delai_min"]): r for r in da.par_circuit(lignes)}
        self.assertEqual(pc[("CANAL", "Challenger", 5)]["lecture"], "tient")            # 31 alertes, CLV > 0 partout
        self.assertEqual(pc[("CANAL FR", "Challenger", 5)]["n"], 31)                    # winamax.fr : licence française
        self.assertEqual(pc[("H17", "WTA", 5)]["lecture"], "trop tôt (n < 30)")
        self.assertIn(("toutes", "WTA", 5), pc)
        self.assertNotIn(("toutes", "Challenger", 5), pc, "« toutes » = H13 à H19 seulement")
        R = {(r["hypothese"], r["delai_min"]): r for r in da.resume(lignes)}
        self.assertEqual(R[("toutes", 5)]["n"], 1)
        self.assertEqual(R[("CANAL", 5)]["lecture"], "tient")

    def test_aucune_clv_dans_les_journaux_publics(self):
        src = (LAB / "delai_alertes.py").read_text(encoding="utf-8")
        bloc = src.split("def run(sink):")[1]
        self.assertNotIn("clv_au_prix_disponible", bloc.split("print(")[1])


if __name__ == "__main__":
    unittest.main()
