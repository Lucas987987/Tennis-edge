#!/usr/bin/env python3
"""Référentiel unique des bookmakers du Lab (V6.6).

Tous les moteurs (V4, V5/V6, V6.3 incrémental, V6.4, V6.6, historique) lisent
les drapeaux ici. Ne jamais recopier ces listes ailleurs.

Champs
------
jouable     : prix réellement accessible à un parieur quelque part (book de
              détail, Pinnacle, bourse Betfair...). False = flux de données pur.
jouable_fr  : opérateur agréé ANJ, donc jouable légalement depuis la France.
              Le flux doit être la version .fr ; « unibet » (international)
              n'est pas « unibet.fr ».
duplicate_of: même cotation publiée sous deux noms (ex. bet365 / bet365.fr) :
              jamais deux confirmations indépendantes.
exchange    : bourse : la commission est déduite des gains nets.

Incertitudes documentées (à vérifier sur anj.fr/offre-de-jeu-et-marche/operateurs-agrees)
------------------------------------------------------------------------------------------
- bet365.fr : scripts/book_index.py et scripts/barometre.py le comptent comme
  agréé ANJ ; à notre connaissance bet365 n'est PAS agréé ANJ (la France est
  un pays exclu de bet365). Marqué jouable_fr=False, fr_incertain=True.
- bwin / netbet : bwin.fr et netbet.fr sont agréés ANJ, mais les flux
  « bwin » et « netbet » de la source sont a priori les versions
  internationales (.com) : jouable_fr=False, fr_incertain=True.
- pmu : PMU (paris sportifs) est agréé ANJ : jouable_fr=True.
- Opérateurs ANJ connus (2026, liste indicative) : Winamax, Unibet.fr,
  Betclic, PMU, ParionsSport (FDJ), ZEbet, NetBet.fr, bwin.fr, Genybet, Vbet,
  Circus, Feelingbet, PokerStars Sports, Olybet, Barrière Bet.
- Aucun flux « données seules » (sbobet, 4casters, sharpbet...) n'apparaît
  dans les partitions actuelles ; s'il en arrive, ils sont jouable=False.
"""
from __future__ import annotations

BETFAIR_COMMISSION = 0.05  # 5 % des gains nets, taux de base Betfair

ANJ_FR = frozenset({
    'winamax.fr', 'winamax', 'unibet.fr', 'betclic', 'betclic.fr', 'pmu', 'pmu.fr',
    'parionssport', 'parions-sport', 'fdj', 'zebet', 'zebet.fr', 'netbet.fr',
    'bwin.fr', 'genybet', 'genybet.fr', 'vbet.fr', 'circus', 'circusbet.fr',
    'feelingbet', 'feelingbet.fr', 'pokerstars.fr', 'olybet.fr', 'barrierebet',
})

DATA_ONLY = frozenset({'sbobet', '4casters', 'sharpbet', 'betinasia', 'singbet'})
# Books RETIRÉS des alertes et des prix d'entrée (décision de Lucas, appliquée le 22/10/2026) :
# toujours collectés et gardés dans les données, jamais proposés comme prix « jouable ».
RETIRES = frozenset({'leovegas'})

DUPLICATES = {'bet365.fr': 'bet365'}
EXCHANGES = {'betfair-ex': BETFAIR_COMMISSION, 'betfair': BETFAIR_COMMISSION,
             'smarkets': 0.02, 'matchbook': 0.02}
FR_UNCERTAIN = frozenset({'bet365.fr', 'bwin', 'netbet'})
SHARP_REFERENCE = 'pinnacle'


def normalize(book) -> str:
    return str(book or '').strip().lower()


def flags(book) -> dict:
    """Drapeaux d'un bookmaker (toujours un dict complet, jamais d'exception)."""
    name = normalize(book)
    return {
        'book': name,
        'jouable': bool(name) and name not in DATA_ONLY and name not in RETIRES,
        'retire': name in RETIRES,
        'jouable_fr': name in ANJ_FR,
        'fr_incertain': name in FR_UNCERTAIN,
        'duplicate_of': DUPLICATES.get(name),
        'exchange': name in EXCHANGES,
        'commission': EXCHANGES.get(name, 0.0),
        'reference_sharp': name == SHARP_REFERENCE,
    }


def canonical(book) -> str:
    """Nom servant au dédoublonnage : bet365.fr -> bet365."""
    name = normalize(book)
    return DUPLICATES.get(name, name)


def effective_odds(book, odds):
    """Cote réellement encaissée : 1 + (cote − 1) × (1 − commission)."""
    if odds is None:
        return None
    commission = EXCHANGES.get(normalize(book), 0.0)
    return 1 + (odds - 1) * (1 - commission)


def pnl(book, odds, won: bool) -> float:
    """Profit pour une mise d'une unité, commission de bourse déduite."""
    return effective_odds(book, odds) - 1 if won else -1.0


def fair_close_proportional(close_side, close_other):
    """Dé-margination proportionnelle : p = (1/c_côté)/(1/c_dom + 1/c_ext). Comparaison seulement."""
    if not close_side or not close_other or close_side <= 1 or close_other <= 1:
        return None
    inv_side, inv_other = 1 / close_side, 1 / close_other
    return (inv_side + inv_other) / inv_side


def power_exponent(close_side, close_other, tol=1e-12, max_iter=200):
    """k > 0 tel que (1/c_côté)^k + (1/c_autre)^k = 1 (bissection). None si échec."""
    if not close_side or not close_other or close_side <= 1 or close_other <= 1:
        return None
    a, b = 1 / close_side, 1 / close_other
    f = lambda k: a ** k + b ** k - 1          # strictement décroissante en k
    low, high = 1e-6, 1.0
    while f(high) > 0:                          # marge positive : k > 1
        high *= 2
        if high > 1e6:
            return None
    if f(low) < 0:
        return None
    for _ in range(max_iter):
        mid = (low + high) / 2
        if f(mid) > 0:
            low = mid
        else:
            high = mid
        if high - low < tol:
            break
    k = (low + high) / 2
    return k if abs(f(k)) < 1e-9 else None


def fair_close(close_side, close_other):
    """Cote de clôture sans marge, méthode PUISSANCE (V6.6).

    p_côté = (1/c_côté)^k avec k tel que la somme des deux probabilités vaut 1.
    Contrairement à la méthode proportionnelle, elle attribue davantage de
    marge à l'outsider (biais favori-outsider), ce qui évite de gonfler le
    CLV des grosses cotes. Repli proportionnel si la résolution échoue.
    """
    k = power_exponent(close_side, close_other)
    if k is None:
        return fair_close_proportional(close_side, close_other)
    return 1 / ((1 / close_side) ** k)


def clv_pin_pct(book, entry_odds, close_side, close_other):
    """CLV vs clôture Pinnacle sans marge (méthode puissance), entrée nette de commission."""
    fair = fair_close(close_side, close_other)
    entry = effective_odds(book, entry_odds)
    if fair is None or entry is None:
        return None
    return 100 * (entry / fair - 1)


def table(books) -> dict:
    return {normalize(b): flags(b) for b in sorted({normalize(x) for x in books if x})}
