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


SEARCHES=[
 ('Houston','TX','industrial pressure vessel fabrication manufacturer Houston Texas'),
 ('Tulsa','OK','heavy steel plate fabrication manufacturing Tulsa Oklahoma'),
 ('Baton Rouge','LA','pressure vessel tank fabrication manufacturer Louisiana'),
 ('Wichita','KS','heavy plate fabrication manufacturer Wichita Kansas'),
 ('Little Rock','AR','industrial tank fabrication company Arkansas'),
 ('Dallas-Fort Worth','TX','industrial steel plate processing fabrication Fort Worth Texas'),
 ('Kansas City','MO','industrial equipment heavy plate fabrication Missouri'),
 ('Shreveport','LA','industrial steel fabrication manufacturer Shreveport Louisiana'),
 ('Oklahoma City','OK','industrial tank vessel fabrication manufacturer Oklahoma City'),
 ('Lafayette','LA','oilfield equipment heavy fabrication Lafayette Louisiana'),
 ('Amarillo','TX','steel plate fabrication manufacturer Amarillo Texas'),
 ('Springfield','MO','industrial steel fabrication manufacturing Springfield Missouri')
]
BLOCKED_HOSTS=('google.com','bing.com','yelp.com','yellowpages.com','facebook.com','linkedin.com','instagram.com','mapquest.com','manta.com','chamberofcommerce.com','bbb.org','indeed.com','glassdoor.com','youtube.com','wikipedia.org','reddit.com','news.google.com','worldsteel.org','britannica.com','merriam-webster.com','imdb.com','dictionary.com','vocabulary.com','thefreedictionary.com','investopedia.com','steel.org','servicesteel.org')
BAD_TITLE=re.compile(r'\b(what is|definition|meaning|examples?|explained|guide|types of|grades chart|history of|wiki|movie|film|dictionary|encyclopedia|near me|top \d+|best \d+|jobs|salary|news|article|learn about|how to|industry overview)\b|[?!]',re.I)
COMPANY_NAME=re.compile(r'\b(inc\.?|llc|ltd\.?|corp\.?|corporation|company|co\.?|manufacturing|fabrication|fabricators|industries|industrial|engineering|equipment|welding|machine|metalworks|metalworking|steelworks|tank|vessel|boiler|heat transfer)\b',re.I)
CAPABILITY=re.compile(r'\b(pressure vessels?|tank fabrication|plate rolling|plate cutting|flame cutting|plasma cutting|heavy fabrication|industrial fabrication|steel fabrication|heat exchangers?|process equipment|oilfield equipment|manufacturing facilities|custom manufacturing|structural steel fabrication)\b',re.I)

def search_candidates(market,excluded):
 """Require an identifiable manufacturer and evidence on its own website."""
 import xml.etree.ElementTree as ET
 from qualify_prospects import VisibleText,safe_site
 city,state,phrase=market
 # Product/industry terms must occur on the page, not merely in a generic result snippet.
 targeted=phrase+' (fabrication OR manufacturing OR vessel OR equipment) -definition -meaning -wikipedia -dictionary -jobs'
 url='https://www.bing.com/search?'+urllib.parse.urlencode({'q':targeted,'format':'rss'})
 req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0 (compatible; RangerSteelIntel/2.0)'})
 with urllib.request.urlopen(req,timeout=12) as response:raw=response.read(350000)
 root=ET.fromstring(raw)
 found=[]
 for node in root.findall('./channel/item')[:30]:
  title=re.sub(r'\s+',' ',node.findtext('title') or '').strip()
  link=node.findtext('link') or ''
  p=urllib.parse.urlsplit(link)
  host=(p.hostname or '').lower().removeprefix('www.')
  if p.scheme not in ('http','https') or not host or any(host==h or host.endswith('.'+h) for h in BLOCKED_HOSTS):continue
  if BAD_TITLE.search(title):continue
  # Never accept an article or glossary as the business homepage.
  if p.path.strip('/') and p.path.strip('/').lower() not in ('home','index.html','index.php'):continue
  homepage=urllib.parse.urlunsplit((p.scheme,p.netloc,'/','',''))
  if not safe_site(homepage):continue
  try:
   request=urllib.request.Request(homepage,headers={'User-Agent':'Mozilla/5.0 (compatible; RangerSteelIntel/2.0)'})
   with urllib.request.urlopen(request,timeout=7) as response:
    if 'html' not in response.headers.get('Content-Type','').lower():continue
    final=response.geturl()
    if not safe_site(final):continue
    rawpage=response.read(180000).decode('utf-8','replace')
   parser=VisibleText();parser.feed(rawpage)
   body=re.sub(r'\s+',' ',' '.join(parser.parts))
   if not CAPABILITY.search(body):continue
   # Site must actually reference the market; never assign the query's city as a proven address.
   location_match=re.search(r'\b'+re.escape(city)+r'\b',body,re.I)
   state_match=re.search(r'\b'+re.escape(state)+r'\b',body,re.I)
   if not (location_match or state_match):continue
   # Prefer the company title of the homepage over arbitrary search-result headings.
   title_match=re.search(r'<title[^>]*>(.*?)</title>',rawpage,re.I|re.S)
   site_title=re.sub(r'\s+',' ',re.sub(r'<[^>]+>',' ',title_match.group(1))).strip() if title_match else ''
   options=[re.split(r'\s+[-|–]\s+| : ',site_title)[0].strip(),re.split(r'\s+[-|–]\s+| : ',title)[0].strip()]
   name=next((n for n in options if 5<=len(n)<=70 and COMPANY_NAME.search(n) and not BAD_TITLE.search(n)),None)
   if not name or norm(name) in excluded or name.lower() in ('industrial','steel','metal','manufacturing','fabrication','equipment','engineering','welding','machine','tank','vessel'):continue
   ident=hashlib.sha256(host.encode()).hexdigest()[:16]
   found.append({'id':ident,'name':name,'city':city if location_match else 'Location requires verification','state':state,
     'category':'Manufacturer website corroborates industrial capabilities',
     'why':'Company homepage contains industrial manufacturing or fabrication language and a regional reference. Full-size plate buying is not confirmed.',
     'website':homepage,'source_url':final,
     'discovered_from':'Company homepage with capability and regional reference','verified_plate_buyer':False})
  except Exception:continue
 return found


def directory_candidates(market,excluded):
 """Geocoded public business discovery; does not depend on Overpass."""
 city,state,phrase=market
 query_text='metal fabrication '+city+' '+state
 params=urllib.parse.urlencode({'q':query_text,'format':'jsonv2','addressdetails':1,'limit':25,'dedupe':1})
 url='https://nominatim.openstreetmap.org/search?'+params
 request=urllib.request.Request(url,headers={'User-Agent':'RangerSteelIntel/2.1 (public business research; GitHub Pages)','Accept':'application/json'})
 with urllib.request.urlopen(request,timeout=12) as response:records=json.load(response)
 found=[]
 for record in records:
  address=record.get('address') or {}
  if (address.get('state_code') or '').upper() not in ('',state):continue
  name=(record.get('name') or '').strip()
  if len(name)<5 or norm(name) in excluded or BAD_TITLE.search(name):continue
  if not (COMPANY_NAME.search(name) or re.search(r'fabricat|manufactur|industrial|metal|steel|machine|weld',record.get('display_name',''),re.I)):continue
  kind=record.get('type','')
  if kind in ('residential','house','road','administrative','city','county','state'):continue
  osmtype=record.get('osm_type','node')
  osmid=record.get('osm_id')
  if not osmid:continue
  found.append({'id':hashlib.sha256((osmtype+str(osmid)).encode()).hexdigest()[:16],
   'name':name,'city':address.get('city') or address.get('town') or address.get('village') or city,
   'state':state,'category':'Publicly mapped industrial business — capabilities unverified',
   'why':'Named business located through public geographic business data. Confirm full-size plate buying and in-house processing.',
   'website':None,'source_url':f'https://www.openstreetmap.org/{osmtype}/{osmid}',
   'discovered_from':'OpenStreetMap Nominatim named business','verified_plate_buyer':False})
 return found


def main():
 today=dt.datetime.now(dt.timezone.utc)
 profile=json.loads((ROOT/'data/prospect-profile.json').read_text())
 excluded={norm(n) for n in profile['excluded_companies']}
 path=ROOT/'data/prospects.json'
 old=json.loads(path.read_text()) if path.exists() else {'leads':[]}
 leads={x['id']:x for x in old.get('leads',[]) if x.get('id') and x.get('discovered_from')!='Public search result; company identity and city require verification'}
 # Publish independently sourced manufacturer leads even if automated search sources fail.
 seed_path=ROOT/'data/prospect-seeds.json'
 if seed_path.exists():
  for entry in json.loads(seed_path.read_text()).get('leads',[]):
   if norm(entry['name']) in excluded:continue
   host=urllib.parse.urlsplit(entry['website']).hostname or entry['name']
   ident=hashlib.sha256(host.lower().removeprefix('www.').encode()).hexdigest()[:16]
   for existing_id, existing in list(leads.items()):
    if existing_id!=ident and (urllib.parse.urlsplit(existing.get('website','')).hostname or '').lower().removeprefix('www.')==host.lower().removeprefix('www.'):
     del leads[existing_id]
   if ident not in leads:
    leads[ident]={**entry,'id':ident,'first_seen':today.date().isoformat(),
      'discovered_from':'Reviewed public manufacturer website','verified_plate_buyer':False,
      'qualification':{'fit':'Worth reviewing','score':0,'signals':[{'label':label,'excerpt':'Published company capability'} for label in entry.get('signals',[])],
       'checked_at':today.isoformat(),'evidence_url':entry['source_url'],
       'note':'Manufacturing capabilities supported by a public company source. Direct mother-plate purchasing and account status not verified.'}}
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
 # Independently search for business websites, even if mapping endpoints fail.
 search_offset=today.date().toordinal()%len(SEARCHES)
 for i in range(4):
  market=SEARCHES[(search_offset+i*3)%len(SEARCHES)]
  try:
   found=search_candidates(market,excluded)
   count=0
   for c in found:
    if c['id'] not in leads:
     c['first_seen']=today.date().isoformat();leads[c['id']]=c;count+=1
   checks.append({'market':market[0]+' web search','status':'ok','new':count})
  except Exception as exc:checks.append({'market':market[0]+' web search','status':'unavailable','error':type(exc).__name__})
 # Rotate free public geographic discovery across three markets each day.
 for i in range(3):
  market=SEARCHES[(search_offset+i*4)%len(SEARCHES)]
  try:
   found=directory_candidates(market,excluded)
   added=0
   for c in found:
    if c['id'] not in leads:
     c['first_seen']=today.date().isoformat();leads[c['id']]=c;added+=1
   checks.append({'market':market[0]+' geographic directory','status':'ok','new':added})
  except Exception as exc:checks.append({'market':market[0]+' geographic directory','status':'unavailable','error':type(exc).__name__})
 # Do not manufacture leads if source is unavailable.
 items=[x for x in leads.values() if norm(x['name']) not in excluded and x.get('discovered_from')!='Brave business web search; unverified']
 items.sort(key=lambda x:(x.get('first_seen',''),x['name']),reverse=True)
 qualified=qualify_batch([x for x in items if x.get('discovered_from')!='Reviewed public manufacturer website'],limit=12)
 result={'schema_version':1,'updated_at':today.isoformat(),'method':'Free public business directories, rotating geographic discovery and manufacturer websites. No paid API required. Purchasing history is unverified.','checks':checks,'website_reviews_this_run':qualified,'new_this_run':sum(c.get('new',0) for c in checks),'leads':items[:300]}
 path.write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n')
 print('Prospect discovery:',len(result['leads']),'candidates;',checks)
if __name__=='__main__':main()
