"""Rebuild the reviewed event table from explicit records and the frozen source ledger.

No network request or political role inference is performed by this command.
"""
from collections import Counter
import csv
from datetime import date
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]

def main():
    ledger=json.loads((HERE/'source-ledger.json').read_text())
    sources={s['id']:s for s in ledger['sources']}
    def event(identifier,kind,when,actor,party,source_id,description,**extra):
        source=sources[source_id]
        return {'id':identifier,'event_type':kind,'event_date':when,'event_time':None,
            'timezone':'Europe/Stockholm','actor':actor,'actor_party':party,
            'status':'announced_future' if when>'2026-11-22' else 'observed',
            'formal_rejection_count_delta':0,'source_ids':[source_id],
            'source_publication_at':source['first_publication_at'],
            'source_updated_at':source['updated_at'],'source_accessed_at_utc':source['accessed_at_utc'],
            'source_url':source['url'],'description':description,
            'cabinet_consent_inferred':False,'future_pm_ballot_inferred':False,**extra}
    events=[
        event('caretaker-start','caretaker_continuation','2026-09-17','Ulf Kristersson','M','caretaker-20260917','The prime minister requested discharge; discharged ministers continued until a successor government took office.'),
        event('s-first-task','exploratory_mandate_started','2026-09-18','Magdalena Andersson','S','s-mandate-20260918','Speaker assigned exploration of a government tolerated by the Riksdag.',episode_id='S-exploration'),
        event('s-resumption-announced','mandate_resumption_announced','2026-10-02','Magdalena Andersson','S','s-resumption-20261002','Speaker announced resumption from 5 October with a report deadline of 12 October.',episode_id='S-exploration',effective_at='2026-10-05',report_deadline='2026-10-12'),
        event('s-resumption-effective','exploratory_mandate_resumed','2026-10-05','Magdalena Andersson','S','s-resumption-20261002','Effective resumption date stated in the 2 October announcement; the later 13 October report confirms continuation of the same exploratory episode.',episode_id='S-exploration',date_basis='announced_effective_date_corroborated_by_later_report'),
        event('s-report','exploratory_report_received','2026-10-13','Magdalena Andersson','S','s-nomination-20261013','Speaker received the report; Andersson did not consider further exploration meaningful at that point.',episode_id='S-exploration',report_completion='completed'),
        event('s-nomination','formal_nomination','2026-10-13','Magdalena Andersson','S','s-nomination-20261013','Speaker formally proposed Andersson for an S single-party government; this is separate from the subsequent vote.',episode_id='S-nomination',cabinet_parties_proposed=['S'],scheduled_vote_date='2026-10-15',scheduled_vote_time='12:00'),
        event('s-rejection','formal_pm_vote','2026-10-15','Magdalena Andersson','S','s-vote-20261015','The formal proposal was rejected.',episode_id='S-nomination',formal_rejection_count_delta=1,ballot_counts={'yes':99,'no':248,'abstain':0,'absent':2},ballot_result='rejected',party_counts={'S':[99,0,0,0],'M':[0,70,0,0],'SD':[0,62,0,0],'V':[0,29,0,1],'C':[0,25,0,0],'KD':[0,22,0,0],'MP':[0,21,0,1],'L':[0,19,0,0]}),
        event('c-first-task','exploratory_mandate_started','2026-10-19','Elisabeth Thand Ringqvist','C','c-mandate-20261019','Speaker assigned C exploration after conversations following the rejected S proposal.',episode_id='C-exploration',report_deadline='2026-10-26'),
        event('c-report','exploratory_report_received','2026-10-26','Elisabeth Thand Ringqvist','C','c-report-20261026','Speaker received the exploratory report and announced further telephone consultations.',episode_id='C-exploration',report_completion='completed'),
        event('c-nomination-announced','nomination_announced','2026-10-29','Elisabeth Thand Ringqvist','C','c-announcement-20261029','Speaker announced a formal proposal for 30 October and a vote on 3 November.',episode_id='C-nomination',effective_at='2026-10-30',cabinet_parties_proposed=['C','S','KD','MP','L'],scheduled_vote_date='2026-11-03',scheduled_vote_time='13:00'),
        event('c-nomination','formal_nomination','2026-10-30','Elisabeth Thand Ringqvist','C','c-formal-20261030','The parliamentary record confirms the formal proposal and its first tabling.',episode_id='C-nomination',meeting_interval_local=['10:00','10:02'],cabinet_parties_proposed=['C','S','KD','MP','L'],publication_date_unknown=True),
        event('c-rejection','formal_pm_vote','2026-11-03','Elisabeth Thand Ringqvist','C','c-vote-20261103','The formal proposal was rejected.',episode_id='C-nomination',formal_rejection_count_delta=1,ballot_counts={'yes':25,'no':324,'abstain':0,'absent':0},ballot_result='rejected',party_counts={'S':[0,99,0,0],'M':[0,70,0,0],'SD':[0,62,0,0],'V':[0,30,0,0],'C':[25,0,0,0],'KD':[0,22,0,0],'MP':[0,22,0,0],'L':[0,19,0,0]}),
        event('m-first-task','exploratory_mandate_started','2026-11-03','Ulf Kristersson','M','m-mandate-20261103','Speaker assigned M exploration after the C proposal was rejected.',episode_id='M-exploration',report_deadline='2026-11-10'),
        event('m-extension','exploratory_mandate_extended','2026-11-06','Ulf Kristersson','M','m-extension-20261106','Speaker extended the exploratory task by additional days; other parties remained free to negotiate.',episode_id='M-exploration',new_report_deadline=None),
        event('m-deadline-announced','report_deadline_announced','2026-11-10','Ulf Kristersson','M','m-deadline-20261110','Speaker specified 17 November as the reporting date.',episode_id='M-exploration',report_deadline='2026-11-17'),
        event('m-report-incomplete','exploratory_report_received','2026-11-17','Ulf Kristersson','M','m-report-20261117','Kristersson reported but could not submit a final report; this was not a formal PM vote.',episode_id='M-exploration',report_completion='incomplete'),
        event('process-adjournment','process_adjournment','2026-11-17','Andreas Norlén',None,'m-report-20261117','Speaker gave Kristersson and all other party leaders a one-week adjournment for continuing negotiations.',episode_id='M-exploration',nomination_announced=False),
        event('next-round-announcement','consultations_announced','2026-11-20','Andreas Norlén',None,'next-round-20261120','Speaker announced party consultations and M final reporting for 24 November.',effective_at='2026-11-24',nomination_announced=False),
        event('next-round','consultations_scheduled','2026-11-24','Andreas Norlén',None,'next-round-20261120','Scheduled consultations with all eight parties and M final reporting; no formal PM ballot date in this notice.',nomination_announced=False,scheduled_meetings=[['S','09:30'],['M','10:00'],['SD','10:30'],['V','11:00'],['C','11:30'],['KD','12:00'],['MP','12:30'],['L','13:00']],press_conference_earliest_local='16:30')]
    assert len({e['id'] for e in events})==len(events)
    types=Counter(e['event_type'] for e in events)
    rejected=sum(e['formal_rejection_count_delta'] for e in events)
    for e in events:
        if 'ballot_counts' in e:
            assert sum(e['ballot_counts'].values())==349
            assert sum(v[1] for v in e['party_counts'].values())==e['ballot_counts']['no']
            assert e['ballot_counts']['no']>=175
    statements=[
        {'id':'speaker-pressure-account','classification':'source-attributed_actor_explanation','source_id':'c-announcement-20261029','statement_date':'2026-10-29','description':'Speaker described linking exploration to formal ballots as a way to mark stage completion and increase pressure as the extra-election endpoint approaches. This is an actor explanation, not an identified causal effect.','candidacy_context':'Thand Ringqvist agreed to candidacy although she had explored an Andersson-led centre arrangement rather than seeking the premiership herself.','future_vote_inferred':False},
        {'id':'parallel-negotiations','classification':'institutional_actor_statement','source_id':'m-extension-20261106','statement_date':'2026-11-06','description':'An exploratory assignment does not restrict other parties from conducting negotiations.','exclusive_bargaining_right_inferred':False},
        {'id':'c-conditional-negotiation','classification':'national_party_statement','source_id':'c-condition-20261116','statement_date':'2026-11-16','description':'C selected the S alternative for further talks, conditional on V dropping its cabinet demand and V/MP supporting the proposed package.','future_pm_ballot':'unknown','budget_vote':'unknown'},
        {'id':'s-proposed-cabinet','classification':'national_party_proposal','source_id':'s-proposal-20261113','statement_date':'2026-11-13','description':'S proposed S/C/MP cabinet membership with close V cooperation; other parties still had to take positions.','cabinet_parties_proposed':['S','C','MP'],'cabinet_consent_inferred':False},
        {'id':'v-cabinet-demand','classification':'national_party_document','source_id':'v-platform-2026','statement_date':None,'description':'The preliminary congress platform states that V should join a government when its votes are needed. The parties and actual proposal remain relevant.','future_pm_ballot':'unknown','budget_vote':'unknown'},
        {'id':'anonymous-offer-report','classification':'anonymous_broadcast_report','source_id':'svt-offer-20261120','statement_date':None,'description':'SVT reported an offer to V and a refusal. No completed agreement, actual future PM vote or enacted policy follows.','future_pm_ballot':'unknown','budget_vote':'unknown'},
        {'id':'latest-live-context','classification':'public_broadcaster_live_page','source_id':'sr-live-20261122','statement_date':None,'description':'The live page contains additional local/former-party-actor opinions and reports attributed to other media. No national party decision or third formal PM rejection is admitted from these entries.'}]
    rules={'source_ids':['constitution-rf','formation-faq'],'legal_regime':'Instrument of Government chapter 6 sections 4–6 and 11','rejection_threshold_no':175,'formal_rejection_limit':4,'formal_rejections_observed':rejected,'formal_rejection_allowance_remaining':4-rejected,'extra_election_after_four_rejections':'Within three months unless an ordinary election is already due within that period.','pm_proposal_decided_by':'Riksdag on the Speaker proposal after consultations','formal_vote_deadline_days':4,'exploratory_assignment_consumes_formal_rejection':False,'exploratory_duration':'Set or extended by Speaker; no general maximum formation duration stated in guidance.','government_change_after_approval':'PM reports ministers, then a special Council of State marks government change.','caretaker_continues_until_new_government_takes_office':True}
    summary={'initial_exploratory_assignments':types['exploratory_mandate_started'],'distinct_exploratory_holders':3,'mandate_resumptions':types['exploratory_mandate_resumed'],'mandate_extensions':types['exploratory_mandate_extended'],'general_process_adjournments':types['process_adjournment'],'formal_nominations_observed':types['formal_nomination'],'formal_pm_votes_observed':types['formal_pm_vote'],'formal_rejections_observed':rejected,'new_government_taking_office_observed':0,'event_records':len(events),'future_scheduled_records':sum(e['status']=='announced_future' for e in events),'event_type_counts':dict(types),'days_since_caretaker_start':(date(2026,11,22)-date(2026,9,17)).days,'m_exploration_as_of_cutoff':'ongoing/incomplete report; not formally rejected','sequence_is_independent_formation_episodes':False,'source_coverage':'Focused official event inventory, not proof that every informal contact was recorded.'}
    payload={'schema':'formation-tensor.events2026.v1','as_of_date':'2026-11-22','timezone':'Europe/Stockholm','summary':summary,'rules':rules,'events':events,'actor_statements':statements,'interpretation':'Observed events, announced future events, and actor statements are separate. Repeated consultations and extensions do not consume formal rejection attempts.','source_accessibility':'All sources retrieved or text-read 22 November 2026. Displayed publication dates do not establish identical historical availability.'}
    (HERE/'events2026.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n')
    fields=['id','event_type','event_date','event_time','actor','actor_party','status','formal_rejection_count_delta','source_publication_at','source_updated_at','source_accessed_at_utc','source_url','description']
    with (HERE/'chronology.csv').open('w',newline='') as h:
        w=csv.DictWriter(h,fieldnames=fields);w.writeheader();w.writerows({k:e[k] for k in fields} for e in events)
    owned_names={'README.md','build_curated_events.py','test_curated_events.py',
                 'events2026.json','chronology.csv','source-ledger.json',
                 'source-specifications.json'}
    files=[p for p in HERE.rglob('*') if p.is_file()
           and (p.parent==HERE and p.name in owned_names or p.parent==HERE/'sources')]
    manifest={'schema':'formation-tensor.formation-data-manifest.v1','status':'passed','files':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(files)},'scope':'Reviewed source observations and typed chronology; no forecast or automatic political role admission.'}
    (HERE/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(summary))

if __name__=='__main__':main()
