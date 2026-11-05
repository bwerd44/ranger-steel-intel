"""Public historical steel-price proxy, walk-forward tested without lookahead.

FRED/BLS WPU101 is a steel mill products producer price index, NOT a discrete
carbon steel plate transaction price. Data coverage and revisions vary.
"""
import csv
import datetime as dt
import io
import json
import urllib.request
from pathlib import Path

ROOT=Path(__file__).resolve().parent
URL='https://fred.stlouisfed.org/graph/fredgraph.csv?id=WPU101'
MIN_TRAIN=120
MIN_TEST=36

def download(timeout=18):
    req=urllib.request.Request(URL,headers={'User-Agent':'RangerSteelIntel/1.0 public historical research'})
    with urllib.request.urlopen(req,timeout=timeout) as response:
        return response.read().decode('utf-8-sig')

def parse(text,as_of=None):
    rows=[]
    for r in csv.DictReader(io.StringIO(text)):
        try:
            day=dt.date.fromisoformat(r['DATE'])
            value=float(r['WPU101'])
            if value<=0 or (as_of and day>as_of):continue
            rows.append((day,value))
        except (ValueError,KeyError,TypeError):continue
    return sorted(set(rows))

def signal(values,i):
    if i<12:return None
    m=values[i]/values[i-6]-1
    y=values[i]/values[i-12]-1
    score=.6*m+.4*y
    return 1 if score>.015 else -1 if score<-.015 else 0

def actual(values,i):
    if i+3>=len(values):return None
    change=values[i+3]/values[i]-1
    return 1 if change>.01 else -1 if change<-.01 else 0

def evaluate(rows,as_of=None):
    if as_of:rows=[r for r in rows if r[0]<=as_of]
    if len(rows)<MIN_TRAIN+MIN_TEST+15:return {'status':'insufficient','observations':len(rows),'minimum_required':MIN_TRAIN+MIN_TEST+15}
    values=[v for _,v in rows]
    # Non-overlapping quarter endpoints, last five years reserved for out-of-sample
    # evaluation; signals use only data observed on or before each test date.
    cutoff=max(MIN_TRAIN,len(values)-60)
    tests=[i for i in range(cutoff,len(values)-3,3) if signal(values,i) is not None]
    correct=sum(signal(values,i)==actual(values,i) for i in tests)
    baseline=max(sum(actual(values,i)==k for i in tests) for k in (-1,0,1)) if tests else 0
    n=len(tests)
    current=signal(values,len(values)-1)
    labels={-1:'Downward historical momentum',0:'Neutral historical momentum',1:'Upward historical momentum'}
    return {'status':'evaluated' if n>=MIN_TEST//3 else 'insufficient','series':'WPU101','proxy':'U.S. steel mill products PPI (not discrete plate)','source_url':URL,'start':rows[0][0].isoformat(),'last_observation':rows[-1][0].isoformat(),'observations':len(rows),'holdout_quarters':n,'directional_hits':correct,'directional_hit_rate':round(correct/n,3) if n else None,'majority_baseline_hits':baseline,'majority_baseline_rate':round(baseline/n,3) if n else None,'historical_signal':labels.get(current),'signal_code':current,'method':'Six- and twelve-month momentum, three-month forward directional evaluation; nonoverlapping quarterly test observations; fixed rules, no optimization; historical revised series may contain revision bias.','warning':'This is an all-steel price proxy, not plate prices. Historical accuracy does not establish future probability or forecast confidence.'}

def refresh(path=ROOT/'data/historical-forecast.json',as_of=None):
    path=Path(path)
    try:
        rows=parse(download(),as_of)
        result=evaluate(rows,as_of)
        if result['status']!='evaluated':raise ValueError('Insufficient historical observations')
        result['retrieved_at']=dt.datetime.now(dt.timezone.utc).isoformat()
        result['data_status']='fresh'
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(json.dumps(result,indent=2)+'\n')
        return result
    except Exception as exc:
        if path.exists():
            saved=json.loads(path.read_text())
            saved['data_status']='retained; latest retrieval failed'
            saved['retrieval_error']=type(exc).__name__
            return saved
        fallback={'status':'unavailable','data_status':'unavailable','retrieval_error':type(exc).__name__}
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(json.dumps(fallback,indent=2)+'\n')
        return fallback

if __name__=='__main__':
    print(json.dumps(refresh(),indent=2))
