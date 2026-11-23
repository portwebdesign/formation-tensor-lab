"""Recount every official member row before using compact roll-call inputs."""
from collections import defaultdict
import csv
import io
import json
from pathlib import Path
import zipfile

ACTIONS={'Ja':0,'Nej':1,'Avstår':2,'Frånvarande':3}
PARTIES=('S','M','SD','C','KD','MP','V','L')


def recount(paths):
    totals={};parties={};members=defaultdict(set)
    for path in paths:
        with zipfile.ZipFile(path) as archive:
            names=archive.namelist()
            if len(names)!=1 or not names[0].endswith('.csv'):
                raise ValueError('One official CSV is required in each archive.')
            with archive.open(names[0]) as raw:
                for row in csv.reader(io.TextIOWrapper(raw,encoding='utf-8-sig',newline='')):
                    if not row:continue
                    if len(row)!=14 or row[6] not in PARTIES+('-',) or row[8] not in ACTIONS:
                        raise ValueError('Unexpected official member-action row.')
                    vote,member,party=row[2],row[5],row[6]
                    if member in members[vote]:raise ValueError('Duplicate member in a roll call.')
                    members[vote].add(member)
                    k=ACTIONS[row[8]]
                    totals.setdefault(vote,[0]*4)[k]+=1
                    parties.setdefault(vote,{}).setdefault(party,[0]*4)[k]+=1
    return totals,parties


def audit(root,rows):
    root=Path(root)
    paths=sorted((root/'data/parliament/raw').glob('votering-*.csv.zip'))
    if len(paths)!=4:raise ValueError('The four pinned session archives are required.')
    totals,parties=recount(paths)
    if set(totals)!={r['id'] for r in rows}:raise ValueError('Raw and compact vote identifiers differ.')
    for r in rows:
        vid=r['id']
        if totals[vid]!=r['counts'] or sum(totals[vid])!=349:
            raise ValueError('Raw and compact member totals differ.')
        for p in PARTIES:
            if parties[vid].get(p,[0]*4)!=r['party_counts'].get(p,[0]*4):
                raise ValueError('Raw and compact party-action counts differ.')
        if parties[vid].get('-',[0]*4)!=r['independent_counts']:
            raise ValueError('Independent member actions differ.')
    return {'status':'passed','official_archives':4,'rollcalls':len(rows),
            'member_rows':sum(sum(c) for c in totals.values()),
            'party_action_cells_compared':len(rows)*8*4,
            'independent_actions_preserved':True}
