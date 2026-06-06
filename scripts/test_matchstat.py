#!/usr/bin/env python3
"""
TEST — Tennis API (Matchstat) sur RapidAPI.
Fait UN SEUL appel getDateFixtures pour une date de Roland-Garros et affiche
le format. Objectif : vérifier que les résultats récents sont accessibles en
gratuit et exploitables, AVANT d'intégrer. Économe : 1 requête par tour (type).

Clé lue depuis la variable d'environnement RAPIDAPI_KEY (jamais en dur).
"""
import urllib.request, urllib.error, json, os

RAPIDAPI_KEY = os.environ.get('RAPIDAPI_KEY', '')
HOST = 'tennis-api-atp-wta-itf.p.rapidapi.com'

# Date à tester : un jour de Roland-Garros (ajuste si besoin)
TEST_DATE = os.environ.get('TEST_DATE', '2026-06-04')
# Pour économiser le quota, on ne teste qu'ATP par défaut (mets 'atp,wta' pour les deux)
TOURS = os.environ.get('TEST_TOURS', 'atp').split(',')

def fetch(tour, date):
    url = f"https://{HOST}/tennis/v2/{tour}/fixtures/{date}"
    print(f"  URL appelée: {url}")
    print(f"  Clé présente: {'oui ('+str(len(RAPIDAPI_KEY))+' caractères)' if RAPIDAPI_KEY else 'NON'}")
    req = urllib.request.Request(url, headers={
        'x-rapidapi-host': HOST,
        'x-rapidapi-key': RAPIDAPI_KEY,
        'Content-Type': 'application/json',
    })
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            remaining = r.headers.get('x-ratelimit-requests-remaining', '?')
            data = json.loads(r.read())
            return data, remaining
    except urllib.error.HTTPError as e:
        # Afficher le message d'erreur détaillé de RapidAPI
        body = e.read().decode('utf-8', errors='replace')
        print(f"  ⚠️ HTTP {e.code} — corps de la réponse:")
        print(f"  {body[:500]}")
        raise

def explore(obj, prefix='', depth=0):
    """Affiche la structure d'un objet JSON (clés et types) sur 2 niveaux."""
    if depth > 2: return
    if isinstance(obj, dict):
        for k, v in list(obj.items())[:15]:
            t = type(v).__name__
            sample = ''
            if isinstance(v, (str,int,float,bool)):
                sample = f" = {repr(v)[:50]}"
            print(f"  {prefix}{k} ({t}){sample}")
            if isinstance(v, (dict,list)) and depth < 2:
                explore(v, prefix+'  ', depth+1)
    elif isinstance(obj, list):
        print(f"  {prefix}[liste de {len(obj)} éléments]")
        if obj:
            explore(obj[0], prefix+'  ', depth+1)

def test():
    if not RAPIDAPI_KEY:
        print("❌ RAPIDAPI_KEY absente des variables d'environnement")
        return
    for tour in TOURS:
        tour = tour.strip()
        print(f"\n{'='*50}\n=== {tour.upper()} — fixtures du {TEST_DATE} ===\n{'='*50}")
        try:
            data, remaining = fetch(tour, TEST_DATE)
            print(f"Requêtes restantes ce mois: {remaining}\n")
            print("--- STRUCTURE DE LA RÉPONSE ---")
            explore(data)

            # Essayer de localiser la liste de matchs
            matches = None
            if isinstance(data, list):
                matches = data
            elif isinstance(data, dict):
                for key in ['data','fixtures','matches','results','events']:
                    if key in data and isinstance(data[key], list):
                        matches = data[key]
                        print(f"\n(liste de matchs trouvée sous la clé '{key}')")
                        break

            if matches:
                print(f"\n--- {len(matches)} matchs ce jour ---")
                for m in matches[:6]:
                    # Affichage best-effort des champs clés
                    print(f"\n  Match brut: {json.dumps(m, ensure_ascii=False)[:300]}")
            else:
                print("\n⚠️ Pas de liste de matchs identifiée — voir structure ci-dessus")
        except Exception as e:
            print(f"❌ Erreur: {e}")

if __name__ == '__main__':
    test()
