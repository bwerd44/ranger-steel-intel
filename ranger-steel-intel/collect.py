import datetime,email.utils,json,os,re,urllib.parse,urllib.request,xml.etree.ElementTree as ET
from pathlib import Path
QUERIES=[('Domestic Mill News','Domestic mills','US carbon steel plate mill production allocation shutdown capacity'),('Domestic Mill News','Plate supply','US discrete plate mill lead times capacity A36 A572'),('Import News','Imports','steel plate imports US global trade tariffs duties'),('Import News','Trade policy','US steel import Section 232 antidumping countervailing plate'),('All Other Steel News','Industry demand','carbon steel plate manufacturing infrastructure pressure vessels'),('All Other Steel News','Industry news','steel industry manufacturing demand plate fabrication')]
NOTES={'Domestic Mill News':'Market context: domestic mill production, availability and lead times can influence plate supply across distribution channels.','Import News':'Market context: trade rules, freight and overseas supply can influence imported plate availability and landed costs.','All Other Steel News':'Market context: industrial activity and end-market demand can affect consumption of carbon steel plate.'}
items=[];seen=set()
for category,topic,q in QUERIES:
 url='https://news.google.com/rss/search?'+urllib.parse.urlencode({'q':q+' when:7d','hl':'en-US','gl':'US','ceid':'US:en'})
 try:
  req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0 RangerSteelIntel/1.0'})
  with urllib.request.urlopen(req,timeout=20) as r: root=ET.fromstring(r.read())
  for node in root.findall('./channel/item')[:10]:
   title=(node.findtext('title') or '').strip();link=(node.findtext('link') or '').strip();pub=node.findtext('pubDate') or ''
   key=re.sub(r'\W+','',title.lower())[:95]
   if not title or not link or key in seen:continue
   seen.add(key)
   try:date=email.utils.parsedate_to_datetime(pub).date().isoformat()
   except Exception:date=''
   items.append({'title':title,'url':link,'topic':topic,'category':category,'date':date,'ranger_note':NOTES[category]})
 except Exception as ex:print('Feed failed:',topic,str(ex))
items.sort(key=lambda a:a['date'],reverse=True)
output=Path('data/latest.json');output.parent.mkdir(parents=True,exist_ok=True)
if items:output.write_text(json.dumps({'updated_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'articles':items[:35]},indent=2),encoding='utf-8');print('Saved',len(items),'articles')
else:print('No new articles; keeping previous data')
