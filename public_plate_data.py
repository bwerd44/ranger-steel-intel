"""Public-only plate-market evidence. Never reads Ranger customer or transaction data."""
import csv
import datetime as dt
import io
import json
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SERIES = 'WPU10170410'
FRED = 'https://fred.stlouisfed.org/graph/fredgraph.csv?id=' + SERIES
SIMA = 'https://www.trade.gov/feature-article/sima-steel-tables'

def collect(fetch=None):
    fetch = fetch or (lambda url: urllib.request.urlopen(
        urllib.request.Request(url, headers={'User-Agent': 'RangerSteelIntel/1.0 public research'}),
        timeout=20).read().decode('utf-8-sig'))
    result = {'updated_at': dt.datetime.now(dt.timezone.utc).isoformat(),
              'privacy': 'Public sources only; no Ranger pricing, customer, allocation, RFQ or inventory records.',
              'plate_price_proxy': {'status': 'unavailable', 'series': SERIES, 'url': 'https://fred.stlouisfed.org/series/'+SERIES,
                  'scope': 'Carbon hot-rolled bars, plates and structural shapes; NOT discrete plate transaction prices.'},
              'plate_imports': {'status': 'not_machine_verified', 'url': SIMA,
                  'scope': 'Commerce SIMA category-level license and Census tables. License permits are not arrivals.',
                  'note': 'Import signal intentionally unscored until cut-length plate data can be parsed and validated.'}}
    try:
        rows = list(csv.DictReader(io.StringIO(fetch(FRED))))
        values = []
        for row in rows:
            try:
                day = row.get('DATE') or row.get('observation_date')
                val = float(row[SERIES])
                if day and val > 0:
                    values.append((day, val))
            except (ValueError, KeyError, TypeError):
                continue
        values.sort()
        if len(values) >= 7:
            last = values[-1]
            prev3 = values[-4]
            prev6 = values[-7]
            result['plate_price_proxy'].update(
                status='observed', observation_date=last[0], index=last[1],
                change_3m_pct=round(100*(last[1]/prev3[1]-1),2),
                change_6m_pct=round(100*(last[1]/prev6[1]-1),2),
                observation_count=len(values), retrieved_at=result['updated_at'])
    except Exception as exc:
        result['plate_price_proxy']['error'] = type(exc).__name__
    return result

if __name__ == '__main__':
    path = ROOT/'data/public-plate-evidence.json'
    path.write_text(json.dumps(collect(), indent=2)+'\\n')
    print('Public plate evidence refreshed')
