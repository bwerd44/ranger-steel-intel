"""Monthly, append-only directional U.S. carbon steel plate scenarios. No AI/API key."""
import argparse
import concurrent.futures
import copy
import datetime as dt
import hashlib
import json
import re
from pathlib import Path
from zoneinfo import ZoneInfo
from collect import fetch, plain, date_of

ROOT = Path(__file__).resolve().parent
VERSION = 'plate-direction-3.0-balance'
FED = 'https://www.federalreserve.gov/releases/g17/current/'
EIA = 'https://www.eia.gov/outlooks/steo/report/'
GRADES = ['A36', 'A572 Grade 50', 'A516 Grade 70']


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()


def horizon(day):
    first = (day.month - 1) // 3 + 1
    return [(year, q) for year in range(day.year, day.year + 2) for q in range(1, 5) if year > day.year or q >= first]


def fresh(source, day):
    dated = date_of(source.get('evidence_date'))
    return bool(dated and 0 <= (day - dated).days <= source.get('max_age_days', 45))


def parse_macro(url, raw, now):
    text = plain(raw)
    date = re.search(r'Release Date:\s*(\w+ \d{1,2}, 20\d{2})', text)
    if not date:
        return None
    published = dt.datetime.strptime(date[1], '%B %d, %Y').date()
    if published > now.date():
        return None
    common = {'evidence_date': published.isoformat(), 'max_age_days': 60, 'retrieved_at': now.isoformat(), 'access': 'Retrieved this forecast edition', 'scope': 'Indirect; not plate tonnage or transaction prices'}
    if url == FED:
        change = re.search(r'Manufacturing output (rose|fell|increased|decreased) ([\d.]+) percent in (\w+)', text, re.I)
        if not change:
            return None
        number = float(change[2]) * (-1 if change[1].lower() in ('fell', 'decreased') else 1)
        defense = re.search(r'Output of defense and space equipment (rose|fell|increased|decreased) ([\d.]+) percent', text, re.I)
        fact = f'The Federal Reserve reports manufacturing output {change[1]} {change[2]}% in {change[3]}.'
        if defense:
            fact += f' Defense and space equipment output {defense[1]} {defense[2]}% in that release.'
        # Pin the dated release, rather than citing a mutable "current" page in history.
        return dict(common, id='fed-manufacturing', publisher='Federal Reserve', title='Industrial Production and Capacity Utilization', url=f'https://www.federalreserve.gov/releases/g17/{published:%Y%m%d}/', summary=fact, manufacturing_change=number)
    if url == EIA:
        # Store only an observed direction. An oil forecast is not a plate-price forecast.
        down = re.search(r'(Brent|spot price).{0,180}(fall|decrease|decline).{0,90}(next year|2027)', text, re.I)
        up = re.search(r'(Brent|spot price).{0,180}(rise|increase).{0,90}(next year|2027)', text, re.I)
        direction = 'lower' if down else 'higher' if up else 'not parsed'
        return dict(common, id='eia-energy', publisher='EIA', title='Short-Term Energy Outlook', url=url, summary=('EIA’s dated outlook projects a lower Brent price next year; this is an energy forecast, not a plate forecast.' if down else 'EIA published a dated energy outlook. The plate model did not extract an unambiguous forward oil-price signal.'), oil_outlook=direction)
    return None


def gather(briefing, context, now, offline=False):
    day = now.astimezone(ZoneInfo('America/Chicago')).date()
    sources = []
    for evidence in briefing.get('briefing', {}).get('sources', []):
        if fresh(evidence, day):
            sources.append(dict(copy.deepcopy(evidence), scope='Direct plate commentary' if evidence['id'] == 'ssab-market' else 'Broad steel context; not discrete plate supply'))
    checks = []
    def get(url):
        try:
            if offline:
                raise RuntimeError('Offline test')
            result = parse_macro(url, fetch(url), now)
            return result, {'source': url, 'status': 'ok' if result else 'unrecognized'}
        except Exception as error:
            return None, {'source': url, 'status': 'unavailable', 'reason': type(error).__name__}
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        for source, check in pool.map(get, (FED, EIA)):
            checks.append(check)
            if source and fresh(source, day):
                sources.append(source)
    existing = {s['id'] for s in sources}
    # Reviewed context is never redated or described as a fresh legal determination.
    for source in context.get('sources', []):
        if source['id'] not in existing and fresh(source, day):
            sources.append(dict(copy.deepcopy(source), access='Dated reviewed context; not reverified by the monthly parser'))
    return sources, checks


def signals(sources):
    out = []
    for source in sources:
        sid = source['id']
        if sid == 'ssab-market':
            pricing = source.get('observations', {}).get('pricing', '').lower()
            inventory = source.get('observations', {}).get('domestic', '').lower()
            if 'prices increased' in pricing:
                out.append({'name': 'Reported plate price momentum', 'weight': 2.0, 'source_id': sid, 'basis': 'SSAB reported an increase in its dated North American plate commentary.'})
            if 'somewhat low' in inventory:
                out.append({'name': 'Distributor inventory constraint', 'weight': 1.0, 'source_id': sid, 'basis': 'Producer assessment of inventories; not a verified allocation percentage.'})
        elif sid == 'fed-manufacturing':
            n = source.get('manufacturing_change', 0)
            out.append({'name': 'Manufacturing demand context', 'weight': 0.25 if n > 0 else -0.25 if n < 0 else 0, 'source_id': sid, 'basis': 'Broad manufacturing; capped at one quarter of a directional point.'})
    return out


def direction(score):
    return 'Firming' if score >= 1.5 else 'Mild upward bias' if score >= .5 else 'Broadly stable' if score > -.5 else 'Mild downward bias' if score > -1.5 else 'Softening'


def ordinal(score):
    return 2 if score >= 1.5 else 1 if score >= .5 else 0 if score > -.5 else -1 if score > -1.5 else -2


def drivers(sources, q, distance):
    ids = {s['id'] for s in sources}
    ref = lambda *names: [name for name in names if name in ids]
    return [
        {'name': 'Mill production, allocations & shutdowns', 'scope': 'Direct plate risk; current mill schedules unverified', 'analysis': ('Near-term inventory tightness can sustain price pressure if mills cannot replenish distributors. ' if distance < 2 else 'The base case assumes some supply adjustment over time, without assigning an opening date to any mill. ') + 'Raw-steel utilization is broader context. No allocation percentage, shutdown duration or restart is assumed as a confirmed fact.', 'source_ids': ref('ssab-market', 'aisi-production')},
        {'name': 'Imports, Section 232 & trade policy', 'scope': 'Direct plate channel; current shipment treatment unverified', 'analysis': 'The base case holds the reviewed trade framework unchanged as a scenario assumption. Duties, exclusions, antidumping orders and origin rules can alter landed plate competition. All-steel import totals do not prove plate arrivals. Policy easing or a surge in plate-specific licenses would shift this outlook downward; tighter restrictions would shift it upward.', 'source_ids': ref('trade-policy', 'aisi-imports')},
        {'name': 'Economy, manufacturing & fabrication', 'scope': 'Broad indicator with a plate demand channel', 'analysis': 'Factory activity and financing conditions influence equipment orders, fabrication backlogs and inventory cycles. Broad manufacturing output supplies only a small model adjustment; it does not measure A36, Grade 50 or pressure-vessel plate orders. A sustained contraction would outweigh the assumed seasonal support.', 'source_ids': ref('fed-manufacturing')},
        {'name': 'Energy, oil & gas', 'scope': 'Plate for tanks, vessels and process equipment; indirect cost effects', 'analysis': 'Energy projects can support A516 Grade 70 and structural plate demand, while oil, natural gas, electricity and diesel affect investment and operating costs in different ways. The base case does not translate oil prices one-for-one into plate demand. Project sanctions, drilling budgets, LNG equipment orders and freight costs could change the outcome.', 'source_ids': ref('eia-energy')},
        {'name': 'Infrastructure, defense & government policy', 'scope': 'Direct plate applications and broader structural-steel demand', 'analysis': 'Bridges, heavy equipment and eligible defense fabrication can consume plate. Funding announcements become demand only after appropriations, procurement and fabrication orders. Domestic-content rules may shift sourcing. No unverified policy change, election outcome or announced project is counted as a confirmed plate order.', 'source_ids': ref('fed-manufacturing', 'trade-policy')},
        {'name': 'Data centers & power infrastructure', 'scope': 'Mostly indirect; building frames are primarily structural products', 'analysis': 'DOE research supports an electricity-demand growth scenario, not a plate-tonnage estimate. Plate exposure is concentrated in generator skids, tanks, enclosures and selected power equipment. Structural frames, rebar, electrical steel and coil-based products are separate markets. Grid constraints, delayed interconnections or cancelled projects could reduce the expected pull-through.', 'source_ids': ref('data-centers')},
        {'name': 'Historical cycles & seasonality', 'scope': 'Explicit model assumption; not a fitted historical relationship', 'analysis': {1: 'The model allows modest first-quarter restocking support, conditional on real orders.', 2: 'The model allows modest spring construction and equipment support, conditional on project execution.', 3: 'The model allows a small summer activity drag; it does not assume a mill outage.', 4: 'The model allows a year-end inventory and holiday drag, even when supply is constrained.'}[q] + ' Restocking and destocking can amplify steel cycles. The seasonal weights and mean reversion are judgmental, not a backtested plate-price model. No HRC futures or coil index enters the calculation.', 'source_ids': []},
    ]


def make_edition(sources, checks, now, edition_id, historical=None):
    local = now.astimezone(ZoneInfo('America/Chicago'))
    historical = historical or {'status':'unavailable'}
    score_signals = signals(sources)
    direct = any(s['id'] == 'ssab-market' and 'pricing' in s.get('observations', {}) for s in sources)
    # Plate-first directional factors. Weights are judgmental, not fitted.
    # Missing plate-specific evidence remains missing; never interpreted as neutral.
    observed = {s['id']: s for s in sources}
    plate = observed.get('ssab-market', {})
    obs = plate.get('observations', {})
    pricing = obs.get('pricing', '').lower()
    inventory = obs.get('domestic', '').lower()
    factor_weights = {'domestic_plate_supply': .35, 'plate_price_momentum': .25,
                      'plate_imports_trade': .20, 'end_user_plate_demand': .15,
                      'historical_macro': .05}
    # Inputs are scored only when dated, plate-specific observations exist.
    # An unverified recovery is a scenario risk, not a scored fact.
    demand_text = obs.get('demand', '').lower()
    factor_weights = {'domestic_plate_supply': .30, 'plate_price_momentum': .20,
                      'plate_imports_trade': .20, 'end_user_plate_demand': .20,
                      'distributor_inventory': .10}
    factor_inputs = {
        'domestic_plate_supply': {'value': None, 'evidence': 'No independently verified plate allocation, mill output or lead-time series'},
        'plate_price_momentum': {'value': 1 if 'prices increased' in pricing else -1 if 'prices decreased' in pricing else None,
                                 'evidence': 'Dated SSAB North American plate pricing commentary'},
        'plate_imports_trade': {'value': None, 'evidence': 'No verified current discrete plate arrivals or landed-price trend'},
        'end_user_plate_demand': {'value': 1 if 'strong' in demand_text else -1 if 'weak' in demand_text else None,
                                  'evidence': 'Dated producer plate demand commentary; no end-user order book'},
        'distributor_inventory': {'value': 1 if 'somewhat low' in inventory else -1 if 'elevated' in inventory else None,
                                  'evidence': 'SSAB distributor inventory assessment'}
    }
    known_weight = sum(factor_weights[k] for k, v in factor_inputs.items() if v['value'] is not None)
    raw_score = round(2 * sum(factor_weights[k] * v['value'] for k, v in factor_inputs.items() if v['value'] is not None), 4)
    direct = factor_inputs['plate_price_momentum']['value'] is not None
    historical_weight = 0  # Broad steel PPI failed its baseline; excluded.
    quarter_rows = []
    # Persistence is conditional on the absence of verified recovery, NOT an assumed mill restart.
    # Longer horizons get weaker conviction, without mechanically forcing a neutral price call.
    for distance, (year, q) in enumerate(horizon(local.date())):
        # Distinguish near-term price change from the persistence of high price levels.
        # No evidence supports a signed directional call in distant quarters.
        horizon_strength = [1.0, .65, .35, 0.0, 0.0]
        if not direct or distance >= 3:
            score = None
        else:
            score = round(raw_score * horizon_strength[distance], 4)
        label = f'Q{q} {year}'
        price = direction(score) if score is not None else 'Insufficient evidence'
        availability = ('Tightness persists in base case; recovery unverified'
                        if factor_inputs['domestic_plate_supply']['value'] == 1 else 'Supply condition unverified')
        coverage = round(known_weight, 2)
        confidence = ('Moderate' if score is not None and distance == 0 and coverage >= .7 else 'Low' if score is not None else 'Insufficient evidence')
        current = distance == 0
        analysis = (f'The base case for {label} is {price.lower()}, with {availability.lower()}. '
                    if direct else f'No defensible directional call for {label} from the currently verified plate inputs; supply and demand scenarios remain conditional. ')
        analysis += ('Current inventory and pricing evidence does not prove repeated quarterly increases or a future supply recovery. '
                     'Confidence declines with the forecast horizon because current evidence cannot establish next year’s actual mill output, imports or orders. ')
        analysis += {1: 'Restocking could support orders after year-end, but weak factory demand or financing constraints could offset it.',
                     2: 'Spring construction and equipment activity could support plate consumption if funded projects move into fabrication.',
                     3: 'Summer activity and import arrivals may reduce pressure, but neither is scored as a verified recovery.',
                     4: 'Year-end inventory reduction could restrain demand, while constrained supply could limit price relief.'}[q]
        spread = 1 + distance * .2
        scenarios = []
        for name, offset, text, avail in [
            ('Bullish', spread, 'Longer plate lead times, an extended outage, tighter trade restrictions or executed energy, infrastructure and power-equipment orders would strengthen prices. Data-center spending matters only where it creates actual plate fabrication orders.', 'Tighter than base case'),
            ('Base case', 0, analysis, availability),
            ('Bearish', -spread, 'A manufacturing slowdown, destocking, cancelled capital projects, improved mill availability or greater landed import competition would weaken prices. Cheaper HRC by itself is not sufficient evidence of cheaper discrete plate.', 'More available than base case'),
        ]:
            scenario_score = None if score is None else round(score + offset, 4)
            scenarios.append({'name': name, 'direction': direction(scenario_score) if direct else 'Conditional only', 'availability': avail, 'analysis': text, 'chart_value': ordinal(scenario_score) if direct else None})
        source_ids = [s['id'] for s in sources]
        quarter_rows.append({'id': f'{year}-Q{q}', 'label': label, 'year': year, 'quarter': q, 'price_direction': price, 'availability': availability, 'analysis': analysis, 'confidence': confidence, 'confidence_reason': 'Qualitative evidence strength, not a probability. Confidence declines with distance and missing plate-specific allocation, lead-time and transaction data.', 'base_score': score, 'seasonal_adjustment': 0, 'decay': horizon_strength[min(distance,4)], 'evidence_coverage': coverage, 'scenarios': scenarios, 'drivers': drivers(sources, q, distance), 'indicators': [
            'Plate-specific mill lead times shortening or lengthening for two consecutive reporting periods; authenticated allocation or outage notices.',
            'Plate-specific import licenses, actual arrivals and landed offers changing direction; a new official Section 232 or AD/CVD action.',
            'Two successive monthly contractions or expansions in manufacturing output, accompanied by changes in fabrication orders.',
            'Energy, LNG, infrastructure, defense or data-center power projects advancing to procurement—or being delayed or cancelled.',
            'Verified plate transaction assessments reversing direction; inventory replenishment exceeding or falling short of end-user orders.'
        ], 'source_ids': source_ids})
    edition = {'id': edition_id, 'month': local.strftime('%Y-%m'), 'generated_at': now.isoformat(), 'as_of': local.date().isoformat(), 'model_version': VERSION, 'historical_validation': historical, 'historical_weight': historical_weight, 'factor_weights': factor_weights, 'factor_inputs': factor_inputs, 'evidence_coverage': round(known_weight,2), 'grades': GRADES, 'forecast_type': 'Directional scenarios; no dollar price targets', 'baseline': 'Each quarter describes price pressure versus the preceding quarter; the current quarter describes its remaining period versus prevailing conditions. It is not an absolute price path.', 'sources': sources, 'source_checks': checks, 'signals': [], 'input_score': raw_score if direct else None, 'quarters': quarter_rows,
        'methodology': [
            'This is a deterministic, rules-based scenario model. No AI model, paid service, market-data subscription or AI API is running.',
            'Version 3.0 plate balance factors: domestic plate supply 30%, pricing 20%, plate imports 20%, end-user plate demand 20%, distributor inventory 10%. Weights are provisional and not backtested.',
            'Missing mill allocation, plate lead-time and import data are explicitly unscored, not assumed neutral. Coverage is disclosed and no model confidence is calibrated.',
            'Near-term observed momentum is discounted for Q1 and Q2 ahead; Q3 and Q4 ahead show insufficient evidence instead of mechanically projecting a trend. This is not a claim of supply recovery.',
            'Broad steel PPI historical proxy is excluded because its holdout accuracy did not beat the majority baseline.',
            'Bullish and bearish stress cases are conditional, not calibrated probability forecasts.',
            'Trade policy, imports, all-steel output, energy, infrastructure, defense and data centers are disclosed scenario channels, not automatic numerical plate premiums. Raw-steel data cannot confirm plate availability. HRC futures and coil-price indexes are excluded.',
            'The same directional framework covers A36, A572 Grade 50 and A516 Grade 70. Grade, thickness, width, origin, heat treatment and testing requirements can create different availability. A516 Grade 70 pressure-vessel or normalized specifications can be more restrictive; no grade spread or specification premium is estimated.',
            'Each calendar month produces one immutable edition. Explicit revisions append a new edition and reason; prior snapshots remain unchanged. Forecasts are regenerated only with the inputs available at that edition, never backfilled to look historically accurate.',
        ]}
    edition['content_hash'] = digest(edition)
    return edition


def validate(history):
    assert history['schema_version'] == 1
    ids = set()
    for edition in history['editions']:
        assert edition['id'] not in ids
        ids.add(edition['id'])
        body = {k: v for k, v in edition.items() if k != 'content_hash'}
        assert digest(body) == edition['content_hash'], 'Historical forecast changed'
        expected = [f'{y}-Q{q}' for y, q in horizon(dt.date.fromisoformat(edition['as_of']))]
        assert [q['id'] for q in edition['quarters']] == expected
        refs = {s['id'] for s in edition['sources']}
        assert len(refs) == len(edition['sources'])
        for q in edition['quarters']:
            assert set(q['source_ids']) <= refs
            assert len(q['scenarios']) == 3
            assert all(set(d['source_ids']) <= refs for d in q['drivers'])
            assert [x['name'] for x in q['scenarios']] == ['Bullish', 'Base case', 'Bearish']
            assert all(x['chart_value'] is None or -2 <= x['chart_value'] <= 2 for x in q['scenarios'])


def update(history, briefing, context, now, revision_reason='', offline=False, historical=None):
    validate(history)
    month = now.astimezone(ZoneInfo('America/Chicago')).strftime('%Y-%m')
    existing = [e for e in history['editions'] if e['month'] == month]
    if existing and not revision_reason:
        return history, False
    sources, checks = gather(briefing, context, now, offline)
    new_id = month if not existing else f'{month}-r{len(existing)+1}'
    edition = make_edition(sources, checks, now, new_id, historical)
    if revision_reason:
        edition.pop('content_hash')
        edition['revision_reason'] = revision_reason
        edition['content_hash'] = digest(edition)
    result = copy.deepcopy(history)
    result['editions'].append(edition)
    result['latest_id'] = new_id
    validate(result)
    return result, True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--offline', action='store_true', help='Test with dated evidence only; not a live forecast refresh')
    parser.add_argument('--revision-reason', default='', help='Explicitly append a revision without replacing the prior edition')
    parser.add_argument('--output', type=Path, default=ROOT/'data/forecasts.json')
    args = parser.parse_args()
    now = dt.datetime.now(dt.timezone.utc)
    history = json.loads(args.output.read_text()) if args.output.exists() else {'schema_version': 1, 'latest_id': None, 'editions': []}
    briefing = json.loads((ROOT/'data/latest.json').read_text())
    context = json.loads((ROOT/'data/forecast-context.json').read_text())
    hp = ROOT/'data/historical-forecast.json'
    historical = json.loads(hp.read_text()) if hp.exists() else {'status':'unavailable'}
    data, changed = update(history, briefing, context, now, args.revision_reason, args.offline, historical)
    if changed:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        temp = args.output.with_suffix('.tmp')
        temp.write_text(json.dumps(data, ensure_ascii=False, indent=2)+'\n')
        temp.replace(args.output)
        print('Appended forecast edition', data['latest_id'], '; preserved', len(data['editions'])-1, 'past editions')
    else:
        print('Existing monthly forecast preserved unchanged:', data['latest_id'])

if __name__ == '__main__':
    main()
