import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'simulateur'))
import elo as E  # noqa: E402


class TestInitiales(unittest.TestCase):
    def test_initiale_reliee(self):
        connus = {E.cle('Benjamín Pérez Mora'): 'Benjamín Pérez Mora', E.cle('Jiang Yi Qing'): 'Jiang Yi Qing'}
        al = E.unifier_strict(connus, ['B. Perez Mora', 'J. Yi Qing'])
        self.assertEqual(al.get(E.cle('B. Perez Mora')), E.cle('Benjamín Pérez Mora'))
        self.assertEqual(al.get(E.cle('J. Yi Qing')), E.cle('Jiang Yi Qing'))

    def test_pas_de_fusion_douteuse(self):
        connus = {E.cle('Rodrigo Duarte'): 'Rodrigo Duarte', E.cle('Maria Pena'): 'Maria Pena'}
        self.assertEqual(E.unifier_strict(connus, ['R. Ferro Duarte', 'M. Perez Pena']), {})

    def test_mauvaise_initiale(self):
        connus = {E.cle('Benjamin Perez Mora'): 'Benjamin Perez Mora'}
        self.assertEqual(E.unifier_strict(connus, ['C. Perez Mora']), {})


if __name__ == '__main__':
    unittest.main()
