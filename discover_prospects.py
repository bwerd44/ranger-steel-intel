"""Discover potential industrial plate accounts from public OpenStreetMap business listings.
Unverified research candidates only. No paid API or claims about actual plate purchasing.
"""
import datetime as dt
import hashlib
import json
from pathlib import Path
import re
import urllib.parse
import urllib.request
from qualify_prospects import qualify_batch

ROOT=Path(__file__).resolve().parent
CITIES=[
 ("Tulsa","OK",36.154,-95.993),("Oklahoma City","OK",35.468,-97.516),
 ("Houston","TX",29.760,-95.370),("Dallas-Fort Worth","TX",32.800,-97.040),
 ("Little Rock","AR",34.746,-92.290),("Wichita","KS",37.687,-97.330),
 ("Kansas City","MO",39.100,-94.580),("Denver","CO",39.740,-104.990),
 ("Albuquerque","NM",35.084,-106.650),("Shreveport","LA",32.526,-93.750),
 ("Jackson","MS",32.299,-90.185),("Omaha","NE",41.257,-95.934),
 ("Baton Rouge","LA",30.451,-91.187),("Lake Charles","LA",30.226,-93.217),
 ("Lafayette","LA",30.224,-92.020),("New Orleans","LA",29.951,-90.072),
 ("Amarillo","TX",35.222,-101.831),("Longview","TX",32.501,-94.740),
 ("Victoria","TX",28.805,-97.003),("Ponca City","OK",36.707,-97.085),
 ("Springfield","MO",37.209,-93.292),("Fort Smith","AR",35.385,-94.398),
 ("Joplin","MO",37.084,-94.513),("Fayetteville","AR",36.062,-94.158),
 ("Topeka","KS",39.048,-95.678),("Lawton","OK",34.603,-98.395)]
KEYWORDS=re.compile(r'fabricat|machine.shop|metal.work|weld|industrial.equipment|pressure.vessel|tank.manufactur|boiler|heat.exchang|process.equipment|oilfield.equipment|steel.fabricat|metal.manufactur',re.I)
NEGATIVE=re.compile(r'coil.processing|tower|telecom|auto.body|jewelry|scrap|recycl|retail|roofing|fence|fencing|ornamental',re.I)

def norm(s):return re.sub(r'[^a-z0-9]','',s.lower())
def candidate(element,city,state,excluded):
 tags=element.get('tags',{})
 name=(tags.get('name') or tags.get('brand') or '').strip()
 if len(name)<4 or norm(name) in excluded:return None
 descriptor=' '.join(str(tags.get(k,'')) for k in ('industrial','craft','shop','name','description','product','manufacturing','operator'))
 if NEGATIVE.search(descriptor) or not KEYWORDS.search(descriptor):return None
 if tags.get('shop') and not (tags.get('craft') or tags.get('industrial')):return None
 website=next((tags[k] for k in ('website','contact:website','url') if tags.get(k,'').startswith(('http://','https://'))),None)
 category='Industrial metal fabrication / equipment candidate'
 if re.search('tank|vessel|boiler|heat.exchang',descriptor,re.I):category='Tank / vessel / thermal equipment candidate'
 elif re.search('machine|equipment|oilfield',descriptor,re.I):category='Heavy equipment / machine shop candidate'
 elif re.search('weld|fabricat|metal.work',descriptor,re.I):category='Fabrication / welding candidate'
 osmtype=element.get('type','node');osmid=element.get('id')
 if not osmid:return None
 return {'id':hashlib.sha256((osmtype+str(osmid)).encode()).hexdigest()[:16],
 'name':name,'city':tags.get('addr:city') or city,'state':state,'category':category,
 'why':'Public business tags suggest a relevant industry. Full-size plate purchases, grades, processing capability and volume have NOT been verified.',
 'website':website,'source_url':f'https://www.openstreetmap.org/{osmtype}/{osmid}',
 'discovered_from':'OpenStreetMap public business listing','verified_plate_buyer':False}

def query(city):
 name,state,lat,lon=city
 q=f'[out:json][timeout:12];(nwr(around:12000,{lat},{lon})["craft"~"metal_construction|welder|metal_worker|metalworking",i];nwr(around:35000,{lat},{lon})["industrial"~"machine_shop|metalworking|manufacturing|factory",i];);out tags center 60;'
 last=None
 for endpoint in ('https://overpass-api.de/api/interpreter','https://overpass.private.coffee/api/interpreter'):
  try:
   req=urllib.request.Request(endpoint,data=urllib.parse.urlencode({'data':q}).encode(),headers={'User-Agent':'RangerSteelIntel/2.0 (public lead research)'})
   with urllib.request.urlopen(req,timeout=15) as response:return json.load(response).get('elements',[])
  except Exception as exc:last=exc
 raise last

def main():
 today=dt.datetime.now(dt.timezone.utc)
 profile=json.loads((ROOT/'data/prospect-profile.json').read_text())
 excluded={norm(n) for n in profile['excluded_companies']}
 path=ROOT/'data/prospects.json'
 old=json.loads(path.read_text()) if path.exists() else {'leads':[]}
 leads={x['id']:x for x in old.get('leads',[]) if x.get('id')}
 checks=[]
 # Rotate three geographic markets per day; previous discoveries remain in the pool.
 offset=today.date().toordinal()%len(CITIES)
 for i in range(2):
  city=CITIES[(offset+i*5)%len(CITIES)]
  try:
   items=query(city)
   count=0
   for element in items:
    c=candidate(element,city[0],city[1],excluded)
    if c and c['id'] not in leads:
     c['first_seen']=today.date().isoformat();leads[c['id']]=c;count+=1
   checks.append({'market':city[0],'status':'ok','new':count})
  except Exception as exc:checks.append({'market':city[0],'status':'unavailable','error':type(exc).__name__})
 # Do not manufacture leads if source is unavailable.
 items=[x for x in leads.values() if norm(x['name']) not in excluded]
 items.sort(key=lambda x:(x.get('first_seen',''),x['name']),reverse=True)
 qualified=qualify_batch(items,limit=12)
 result={'schema_version':1,'updated_at':today.isoformat(),'method':'Public industrial business listings, rotating geographic discovery; tags indicate possible industry fit only. Website capability signals are research clues, not verified buying history or volume.','checks':checks,'website_reviews_this_run':qualified,'leads':items[:300]}
 path.write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n')
 print('Prospect discovery:',len(result['leads']),'candidates;',checks)
if __name__=='__main__':main()
