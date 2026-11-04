"""Evidence-only Market Pulse, weekly comparisons, mill tracker and outcomes."""
import argparse
import concurrent.futures
import copy
import datetime as dt
import json
from pathlib import Path
import re
from zoneinfo import ZoneInfo
from collect import fetch, plain, date_of
from forecast import digest

ROOT = Path(__file__).resolve().parent
RULE_VERSION = 'plate-pulse-1.0'
METRICS = {
    'pricing': ('Plate Pricing', ('Rising', 'Stable', 'Falling')),
    'supply': ('Domestic Mill Supply', ('Tightening', 'Stable', 'Improving')),
    'lead_times': ('Mill Lead Times', ('Lengthening', 'Stable', 'Shortening')),
    'imports': ('Import Availability', ('Tightening', 'Stable', 'Improving')),
    'demand': ('Plate Demand', ('Strengthening', 'Stable', 'Weakening')),
}
MILLS = [
    {'id':'nucor','name':'Nucor','url':'https://nucor.com/products/plate/','coverage':'U.S. discrete plate mills; sheet projects excluded'},
    {'id':'ssab','name':'SSAB Americas','url':'https://www.ssab.com/en/company/investors/ssab-as-an-investment/market-situation-and-outlook','coverage':'North American plate commentary; individual plant operation not inferred'},
    {'id':'jsw','name':'JSW Steel USA','url':'https://jswsteel.us/baytown/','coverage':'Baytown plate; Mingo coil/slab context kept separate'},
    {'id':'cliffs','name':'Cleveland-Cliffs','url':'https://www.clevelandcliffs.com/investors/sec-filings/all-sec-filings/content/0000764065-26-000115/clf-20260930.htm','coverage':'U.S. plate footprint; sheet and electrical-steel projects excluded'},
]


def usable(item, day, default_days=30):
    date = date_of(item.get('evidence_date'))
    return bool(date and 0 <= (day-date).days <= item.get('max_age_days', default_days))


def pressure(metric, condition):
    if metric not in METRICS or condition not in METRICS[metric][1]:
        return 'gray', '—'
    index = METRICS[metric][1].index(condition)
    return [('red','↑'),('orange','→'),('green','↓')][index]


def observed_from_briefing(data):
    """A level is not a trend. Broad steel is never promoted to plate evidence."""
    observations = []
    for source in data.get('briefing',{}).get('sources',[]):
        if source['id'] != 'ssab-market':
            continue
        statement = source.get('observations',{}).get('pricing','')
        condition = 'Rising' if re.search(r'plate prices increased', statement, re.I) else 'Falling' if re.search(r'plate prices (decreased|fell)',statement,re.I) else 'Stable' if re.search(r'plate prices (were|remained) stable',statement,re.I) else None
        if condition:
            observations.append({'metric':'pricing','condition':condition,'scope':'discrete_plate','verified':True,'evidence_date':source['evidence_date'],'max_age_days':45,'confidence':'Low','period':source.get('period'),'basis':statement,'limitation':'Latest reported quarterly trend, not a daily spot quote. Eligible for 45 days from period end.','source':copy.deepcopy(source),'verification':'Dated producer report; not independently measured transaction prices'})
    return observations


def apply_editorial_assessments(readings, day):
    """Time-limited editorial judgments, never represented as independently verified evidence."""
    editorial = {
        'imports': ('Stable', '2026-11-04', 'Current industry assessment: import availability is broadly neutral. This is an editorial judgment, not a verified month-over-month plate import trend.'),
        'demand': ('Stable', '2026-11-04', 'Current industry assessment: plate demand is broadly neutral. Earlier reporting of improved demand does not establish that demand is still strengthening today.'),
    }
    for reading in readings:
        if reading['id'] not in editorial:
            continue
        condition, assessed_at, basis = editorial[reading['id']]
        if 0 <= (day-date_of(assessed_at)).days <= 14:
            reading.update(condition=condition,color='orange',arrow='→',confidence='Editorial assessment',evidence_date=None,assessment_date=assessed_at,basis=basis,limitation='Not independently verified. Expires after 14 days unless reassessed. Published evidence remains available in source history.',sources=[])
    return readings


def derive_readings(observations, day):
    missing = {
        'pricing':'No eligible dated discrete plate price-direction evidence.',
        'supply':'Low inventories alone do not establish tightening. Current plate supply direction is not verified.',
        'lead_times':'No comparable dated plate-mill delivery schedules were verified.',
        'imports':'All-steel imports and license totals do not establish discrete plate availability.',
        'demand':'A strong market is a level, not proof of strengthening demand. Sector activity is not plate order volume.',
    }
    readings = []
    for key,(label,allowed) in METRICS.items():
        candidates = [x for x in observations if x.get('metric')==key and x.get('condition') in allowed and x.get('scope')=='discrete_plate' and x.get('verified') is True and x.get('source',{}).get('url','').startswith('https://') and usable(x,day)]
        if candidates:
            newest = max(x['evidence_date'] for x in candidates)
            current = [x for x in candidates if x['evidence_date']==newest]
            if len({x['condition'] for x in current})>1:
                readings.append({'id':key,'label':label,'condition':'Mixed','color':'orange','arrow':'↔','confidence':'Low','evidence_date':newest,'basis':'Same-date eligible plate observations conflict. No single trend is inferred.','sources':[x['source'] for x in current]})
                continue
            observation = current[-1]
            color,arrow=pressure(key,observation['condition'])
            readings.append({'id':key,'label':label,'condition':observation['condition'],'color':color,'arrow':arrow,'confidence':observation.get('confidence','Low'),'evidence_date':observation['evidence_date'],'basis':observation['basis'],'period':observation.get('period'),'limitation':observation.get('limitation','Dated public evidence; scope may be incomplete.'),'sources':[observation['source']]})
        else:
            dated=[x for x in observations if x.get('metric')==key and date_of(x.get('evidence_date')) and date_of(x['evidence_date'])<=day]
            readings.append({'id':key,'label':label,'condition':'Insufficient Data','color':'gray','arrow':'—','confidence':'Not rated','evidence_date':None,'last_evidence_date':max((x['evidence_date'] for x in dated),default=None),'basis':missing[key],'limitation':'Missing, expired or non-comparable evidence is never treated as stable.','sources':[]})
    return readings


def baseline(history, day):
    target=day-dt.timedelta(days=7)
    candidates=[s for s in history['snapshots'] if date_of(s['as_of']) and target-dt.timedelta(days=7)<=date_of(s['as_of'])<=target]
    return max(candidates,key=lambda x:(x['as_of'],x['generated_at'])) if candidates else None


def weekly_change(current, previous):
    if not previous:
        return {'status':'baseline_pending','summary':'Weekly comparison is building. There is no saved observation from the previous week yet.','previous_date':None,'changes':[]}
    changes=[]
    old={r['id']:r for r in previous['readings']}
    for reading in current['readings']:
        prior=old.get(reading['id'])
        if not prior or prior['condition']==reading['condition']:
            continue
        verified=reading['condition'] not in ('Insufficient Data','Mixed') and prior['condition'] not in ('Insufficient Data','Mixed')
        changes.append({'type':'market_change' if verified else 'coverage_change','label':reading['label'],'previous':prior['condition'],'current':reading['condition'],'explanation':reading['basis'] if verified else 'Evidence coverage changed. This does not establish a physical change in the market.','sources':reading['sources']})
    old_events={x['event_id'] for m in previous['mills'] for x in m.get('developments',[]) if x.get('event_id')}
    old_events.update(x['event_id'] for x in previous.get('developments',[]))
    for mill in current['mills']:
        for event in mill.get('developments',[]):
            # Newly entered old reports do not masquerade as events from this week.
            if event.get('event_id') not in old_events and previous['as_of']<event['evidence_date']<=current['as_of']:
                changes.append({'type':'reported_development','label':mill['name'],'previous':'No saved development','current':event['summary'],'explanation':'A dated publicly reported development was added; current operating status remains separately assessed.','sources':[event['source']]})
    for event in current.get('developments',[]):
        if event['event_id'] not in old_events and previous['as_of']<event['evidence_date']<=current['as_of']:
            changes.append({'type':'reported_context','label':event['category'],'previous':'No equivalent saved report','current':event['summary'],'explanation':event['limitation'],'sources':[event['source']]})
    material=[x for x in changes if x['type']!='coverage_change']
    summary = f'{len(material)} evidence-supported change'+('s' if len(material)!=1 else '')+' versus the saved weekly baseline.' if material else 'No material verified change was identified versus the saved weekly baseline. Missing information is not proof that conditions are unchanged.'
    return {'status':'compared','summary':summary,'previous_date':previous['as_of'],'changes':changes}


def mill_tracker(data, reviewed, now, offline=False):
    day=now.astimezone(ZoneInfo('America/Chicago')).date()
    def check(mill):
        try:
            if offline:raise RuntimeError('Offline test')
            return mill['id'],plain(fetch(mill['url'])),'retrieved'
        except Exception as error:return mill['id'],'',type(error).__name__
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        results={key:(text,status) for key,text,status in pool.map(check,MILLS)}
    rows=[]
    for mill in MILLS:
        text,status=results[mill['id']]
        events=[copy.deepcopy(x) for x in reviewed.get('mill_developments',[]) if x['mill_id']==mill['id'] and usable(x,day,90)]
        if mill['id']=='ssab':
            for source in data.get('briefing',{}).get('sources',[]):
                if source['id']=='ssab-market' and usable(source,day,105):
                    events.append({'event_id':'ssab-'+source['evidence_date'],'evidence_date':source['evidence_date'],'date_kind':'reporting period end','summary':source.get('observations',{}).get('pricing','Dated plate commentary available.'),'source':copy.deepcopy(source),'status':'Dated quarterly market commentary, not a plant operating report'})
        # Verify only the narrowly recognized filing statement. Keep its period date.
        for event in events:
            anchor=event.get('verification_anchor')
            event['access']='Primary statement rechecked this collection' if anchor and anchor.lower() in text.lower() else 'Dated reviewed development; not freshly reverified'
        events.sort(key=lambda x:x['evidence_date'],reverse=True)
        rows.append(dict(mill,condition='Current status unverified',color='gray',arrow='—',confidence='Not rated',checked_at=now.isoformat(),source_access=status,developments=events[:2],limitations='Production, active outages, allocations, current price announcements and lead times are not inferred from a capabilities page, earnings headlines or a scheduled outage end date.'))
    return rows


def demand_drivers(context, now):
    day=now.astimezone(ZoneInfo('America/Chicago')).date()
    sources=[s for s in context.get('sources',[]) if usable(s,day,60)]
    refs=lambda *ids:[copy.deepcopy(s) for s in sources if s['id'] in ids]
    return [
        {'name':'Energy, oil & gas','scope':'Direct equipment demand; project-dependent','grades':'A516 Grade 70 for specified vessels; A36 / A572 Grade 50 for skids and supports','analysis':'Tanks, separators, process vessels and heavy equipment can consume discrete plate. Oil prices and drilling activity are indirect indicators; funded fabrication orders, specification requirements and project timing matter more than announcements.','sources':refs('eia-energy')},
        {'name':'Power generation & data centers','scope':'Selected direct plate applications; much demand is for other products','grades':'A36 / A572 Grade 50 skids and baseplates; A516 Grade 70 where pressure equipment specifications require it','analysis':'Generator skids, tanks, baseplates and selected power equipment provide a plate channel. Building frames, rebar, electrical steel and many enclosures belong to different product markets. Electricity-demand projections do not establish plate tonnage; grid access and project execution can delay consumption.','sources':refs('data-centers')},
        {'name':'Infrastructure','scope':'Plate bridges and equipment versus structural products','grades':'A36 / A572 Grade 50 where project specifications permit','analysis':'Bridge fabrication, heavy equipment and selected industrial structures can create plate orders. Many projects primarily use beams, rebar or other steel. Funding must turn into procurement before it becomes current plate demand.','sources':refs('trade-policy')},
        {'name':'Manufacturing & industrial equipment','scope':'Broad output indicator; direct plate orders require separate evidence','grades':'A36 / A572 Grade 50 equipment frames; A516 Grade 70 specified process equipment','analysis':'Machinery, mining equipment and fabrication backlogs can affect mother-plate consumption. Manufacturing output alone cannot measure plate orders, and coil-heavy automotive activity is not interchangeable with plate demand.','sources':refs('fed-manufacturing')},
        {'name':'Defense','scope':'Specialized plate applications; specifications may exceed standard grades','grades':'A36 / A572 Grade 50 / A516 Grade 70 only when approved by contract; armor/naval grades differ','analysis':'Shipbuilding and heavy defense fabrication may consume plate, but procurement calendars, appropriations and material approvals determine timing. Growth in defense equipment output is broader than demand for these three grades. No announced budget is counted as a confirmed Ranger-grade plate order.','sources':refs('fed-manufacturing')},
    ]


def accuracy(forecasts, actuals, day):
    results=[]; pending=0
    for edition in forecasts.get('editions',[]):
        for quarter in edition['quarters']:
            year,q=quarter['year'],quarter['quarter']
            end=dt.date(year+q//4,q%4*3+1,1)-dt.timedelta(days=1)
            if end>=day:continue
            start=dt.date(year,(q-1)*3+1,1)
            issued=date_of(edition.get('as_of'))
            required_basis='remaining_period_vs_issue' if issued and issued>start else 'quarter_over_quarter'
            matching=[o for o in actuals if o.get('quarter_id')==quarter['id'] and o.get('scope')=='discrete_plate' and o.get('basis')==required_basis and (required_basis!='remaining_period_vs_issue' or (o.get('period_start')==edition['as_of'] and o.get('period_end')==end.isoformat())) and o.get('verified') is True and date_of(o.get('reviewed_at')) and date_of(o['reviewed_at'])<=day and o.get('direction') in ('Rising','Stable','Falling') and o.get('source',{}).get('url','').startswith('https://') and date_of(o.get('evidence_date')) and end<date_of(o['evidence_date'])<=day]
            expected={'Firming':'Rising','Mild upward bias':'Rising','Broadly stable':'Stable','Mild downward bias':'Falling','Softening':'Falling'}.get(quarter['price_direction'])
            if not matching or not expected:
                pending+=1;continue
            actual=min(matching,key=lambda o:o['evidence_date'])
            results.append({'edition':edition['id'],'quarter':quarter['label'],'predicted':expected,'observed':actual['direction'],'agreement':expected==actual['direction'],'source':actual['source'],'evidence_date':actual['evidence_date'],'limitation':'Qualitative directional agreement only; not a price-return, magnitude or probability accuracy score.'})
    return {'status':'available' if results else 'not_yet_evaluable','results':results,'completed_quarters_pending':pending,'summary':'Directional comparisons are shown only for completed quarters with reviewed, like-for-like discrete plate observations.' if results else 'Not yet evaluable. No completed forecast quarter has a sufficiently verified, like-for-like plate outcome. No accuracy score or actual price has been invented.'}


def validate_history(history):
    assert history['schema_version']==1
    ids=set()
    for snapshot in history['snapshots']:
        assert snapshot['id'] not in ids
        ids.add(snapshot['id'])
        assert digest({k:v for k,v in snapshot.items() if k!='content_hash'})==snapshot['content_hash'],'Saved pulse history changed'
        assert [x['id'] for x in snapshot['readings']]==list(METRICS)


def build(data, reviewed, context, forecasts, history, now, offline=False):
    validate_history(history)
    day=now.astimezone(ZoneInfo('America/Chicago')).date()
    observations=observed_from_briefing(data)+copy.deepcopy(reviewed.get('observations',[]))
    snapshot={'id':now.isoformat(),'as_of':day.isoformat(),'generated_at':now.isoformat(),'rule_version':RULE_VERSION,'readings':apply_editorial_assessments(derive_readings(observations,day),day),'mills':mill_tracker(data,reviewed,now,offline),'observations':observations}
    snapshot['developments']=[]
    for source in data.get('briefing',{}).get('sources',[]):
        if source['id'] in ('aisi-production','aisi-imports') and usable(source,day,45):
            snapshot['developments'].append({'event_id':source['id']+'-'+source['evidence_date'],'evidence_date':source['evidence_date'],'category':'Broad steel production' if source['id']=='aisi-production' else 'Import context','summary':' '.join(source.get('observations',{}).values()),'limitation':'Broad steel context, not a verified change in discrete plate availability. Date is the source’s evidence/reporting date.','source':copy.deepcopy(source)})
    snapshot['developments'] += [copy.deepcopy(e) for e in reviewed.get('market_developments',[]) if e.get('verified') is True and usable(e,day,30) and e.get('source',{}).get('url','').startswith('https://')]
    prior=baseline(history,day)
    snapshot['content_hash']=digest(snapshot)
    comparison=weekly_change(snapshot,prior)
    # At most one identical observation set per day. New evidence can append a revision.
    semantic=lambda s:digest({'readings':[{k:r.get(k) for k in ('id','condition','confidence','evidence_date','basis')} for r in s['readings']],'events':[[e['event_id'] for e in m.get('developments',[])] for m in s['mills']],'developments':[e['event_id'] for e in s.get('developments',[])]})
    same=[s for s in history['snapshots'] if s['as_of']==snapshot['as_of'] and semantic(s)==semantic(snapshot)]
    for reading in snapshot['readings']:
        old=next((r for r in prior['readings'] if r['id']==reading['id']),None) if prior else None
        reading['previous']=dict(condition=old['condition'],evidence_date=old.get('evidence_date'),observed_at=prior['as_of']) if old else None
    # Only presentation gets previous-reading fields; immutable snapshot hashes stay valid.
    presentation=copy.deepcopy(snapshot)
    new_history=copy.deepcopy(history)
    clean=copy.deepcopy(snapshot)
    for reading in clean['readings']:reading.pop('previous',None)
    clean['content_hash']=digest({k:v for k,v in clean.items() if k!='content_hash'})
    if not same:new_history['snapshots'].append(clean)
    validate_history(new_history)
    return {'schema_version':1,'updated_at':now.isoformat(),'pulse':presentation['readings'],'weekly':comparison,'mills':presentation['mills'],'demand_drivers':demand_drivers(context,now),'accuracy':accuracy(forecasts,reviewed.get('quarterly_outcomes',[]),day),'recent_history':[{'as_of':h['as_of'],'readings':[{'label':r['label'],'condition':r['condition'],'evidence_date':r.get('evidence_date')} for r in h['readings']]} for h in new_history['snapshots'][-30:]],'history_count':len(new_history['snapshots']),'history_started':new_history['snapshots'][0]['as_of'] if new_history['snapshots'] else day.isoformat(),'rules':[
        'Red / ↑ = increasing pressure. Orange / → or ↔ = stable or mixed. Green / ↓ = easing pressure. Gray / — = insufficient or expired evidence. Colors do not mean good or bad.',
        'Only explicit dated discrete-plate directional observations qualify. Low inventories, strong demand levels, all-steel production and aggregate imports cannot establish a change in plate supply or demand.',
        'Recognized producer quarterly plate-price direction is eligible for 45 days from period end, at Low confidence. Other reviewed observations default to 30 days unless their record documents a different window. Future dates and expired observations are excluded.',
        'Conflicting eligible readings on the same evidence date show Mixed at Low confidence. Missing data never defaults to Stable.',
        'Daily snapshots preserve evidence and readings. The weekly baseline is the latest saved snapshot on or before seven days ago, no more than fourteen days old. Missing weeks are not backfilled. Coverage changes are separate from physical market changes.',
        'Mill webpages are checked daily, but only recognized or reviewed dated developments are shown. A planned outage end is never treated as a confirmed restart. Capabilities pages do not verify current operations or allocations.',
        'Forecast accuracy needs a completed quarter and reviewed like-for-like observations for discrete plate. A current-quarter forecast requires the matching remaining-period baseline; a full-quarter result cannot substitute. Coil/HRC, all-steel output, within-quarter price changes and unverified headlines do not qualify. No suitable automated actual-price series is configured.',
    ]},new_history


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--offline',action='store_true')
    args=parser.parse_args()
    read=lambda name:json.loads((ROOT/'data'/name).read_text())
    hp=ROOT/'data/pulse-history.json'
    history=json.loads(hp.read_text()) if hp.exists() else {'schema_version':1,'snapshots':[]}
    forecasts=read('forecasts.json')
    context={'sources':forecasts['editions'][-1]['sources'] if forecasts['editions'] else []}
    result,history=build(read('latest.json'),read('market-evidence.json'),context,forecasts,history,dt.datetime.now(dt.timezone.utc),args.offline)
    for name,content in [('pulse-history.json',history),('intelligence.json',result)]:
        path=ROOT/'data'/name;temp=path.with_suffix('.tmp');temp.write_text(json.dumps(content,indent=2,ensure_ascii=False)+'\n');temp.replace(path)
    print('Market Pulse:',', '.join(x['label']+'='+x['condition'] for x in result['pulse']))
    print('Weekly:',result['weekly']['status'],'History snapshots:',result['history_count'],'Accuracy:',result['accuracy']['status'])

if __name__=='__main__':main()
