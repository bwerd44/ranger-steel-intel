import datetime,email.utils,json,os,re,urllib.parse,urllib.request,xml.etree.ElementTree as ET
from pathlib import Path
QUERIES=[('Plate supply','carbon steel plate mill capacity allocation A36 A572'),('Mills','Nucor SSAB JSW plate mill shutdown production'),('Trade','steel plate imports Section 232 tariff Brazil Korea'),('Demand','steel plate fabrication manufacturing pressure vessel infrastructure')]
NOTES={'Plate supply':'Ranger watch: check availability, mill lead times and replacement costs before committing to large plate orders.','Mills':'Ranger watch: confirm any capacity or allocation change directly with suppliers before changing quotes.','Trade':'Ranger watch: assess landed import cost and delivery timing; verify applicable trade rules.','Demand':'Ranger watch: identify plate-consuming fabricators and project demand in core sales territories.'}
items=[];seen=set()
for topic,q in QUERIES:
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
   items.append({'title':title,'url':link,'topic':topic,'date':date,'ranger_note':NOTES[topic]})
 except Exception as ex:print('Feed failed:',topic,str(ex))
items.sort(key=lambda a:a['date'],reverse=True)
output=Path('data/latest.json');output.parent.mkdir(parents=True,exist_ok=True)
if items:output.write_text(json.dumps({'updated_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'articles':items[:35]},indent=2),encoding='utf-8');print('Saved',len(items),'articles')
else:print('No new articles; keeping previous data')
