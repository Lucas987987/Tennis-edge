import sys, os
rep = os.path.abspath(sys.argv[1])
p = os.path.join(rep, 'pistes_common.py')
s = open(p, encoding='utf-8').read()
avant = """    if any(gc in t for gc in GRANDS_CHELEMS):
        return 'Grand Chelem'
"""
assert avant in s, 'motif Grand Chelem introuvable'
open(p, 'w', encoding='utf-8').write(s.replace(avant, '', 1))
q = os.path.join(rep, 'segments_study.py')
s2 = open(q, encoding='utf-8').read().replace("'Grand Chelem', ", '').replace(
    'libelles_non_classes', 'libelles_non_classes_DISPARUE')
open(q, 'w', encoding='utf-8').write(s2)
print('  rebuggé : Grand Chelem retiré + affichage de "autre" retiré')
