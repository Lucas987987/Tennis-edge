"""Paquet 483 (26/11/2026) : notifications des favoris pour les abonnés Plus — service worker, page, confidentialité,
cron, tests du worker lancés au déploiement, aucun mot interdit dans les textes."""
import os
import re
import unittest

R = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
lire = lambda *p: open(os.path.join(R, *p), encoding='utf-8').read()


class Notifs(unittest.TestCase):
    def test_service_worker(self):
        s = lire('algo', 'sw.js')
        self.assertIn("addEventListener('push'", s)
        self.assertIn("addEventListener('notificationclick'", s)
        self.assertIn("m.url.startsWith('/')", s)                    # jamais d'adresse extérieure ouverte

    def test_page(self):
        s = lire('algo', 'index.html')
        self.assertIn('id="cp-notifs"', s)
        for k in ('on', 'essai', 'off'):
            self.assertIn(f"k === '{k}'", s)
        self.assertIn("if (!COMPTE.abonne)", s)                       # réservé au Plus
        self.assertIn('Notification.requestPermission()', s)          # seulement après un appui
        self.assertIn("si vous activez les notifications (abonnés Plus)", s)
        self.assertIn('if you turn on notifications (Plus members)', s)

    def test_worker(self):
        n = lire('workers', 'algo', 'notifs.js')
        self.assertIn("if (!abonne(u)) return rep({ ok: false, erreur: 'plus' }, 403);", n)
        self.assertIn('if (!u || !abonne(u)', n)                      # vérifié aussi à l'envoi
        self.assertIn('HOTES_PUSH', n)
        for mot in ('marché', 'cote', 'Pinnacle', 'value'):
            self.assertNotRegex(n.split('export const TXT')[1].split('// ---')[0], re.compile(mot, re.I))
        w = lire('workers', 'algo', 'wrangler.toml')
        self.assertIn('"* * * * *"', w)
        d = lire('.github', 'workflows', 'deploy_algo.yml')
        self.assertIn('workers/algo/test_notifs.mjs', d)


if __name__ == '__main__':
    unittest.main()
