"""Conservative website-based qualification of public industrial business candidates."""
import concurrent.futures
import datetime as dt
from html.parser import HTMLParser
import ipaddress
import re
import socket
import urllib.parse
import urllib.request

class VisibleText(HTMLParser):
    def __init__(self):
        super().__init__();self.parts=[];self.hidden=0
    def handle_starttag(self,tag,attrs):
        if tag in ('script','style','noscript'):self.hidden+=1
        if tag in ('p','h1','h2','h3','li','title','div'):self.parts.append(' ')
    def handle_endtag(self,tag):
        if tag in ('script','style','noscript'):self.hidden=max(0,self.hidden-1)
    def handle_data(self,data):
        if not self.hidden:self.parts.append(data)

SIGNALS=[
 ('Pressure vessels / tanks',r'\b(pressure vessels?|storage tanks?|tank fabrication|vessel fabrication|asme vessels?)\b',4),
 ('Heavy plate processing',r'\b(plate rolling|plate burning|plate cutting|plasma cutting|oxy.?fuel cutting|flame cutting|heavy plate|plate fabrication)\b',5),
 ('Plate grades',r'\b(a36|a572|a516|sa.?516|grade 50|grade 70)\b',4),
 ('Heavy industrial equipment',r'\b(heat exchangers?|process equipment|oilfield equipment|industrial skids?|heavy equipment|industrial boilers?)\b',3),
 ('Industrial fabrication',r'\b(structural fabrication|steel fabrication|industrial welding|custom metal fabrication|heavy fabrication)\b',2),
 ('Mother plate / sheet sizes',r'\b(96.{0,8}240|120.{0,8}480|8.{0,5}20.{0,10}plate|10.{0,5}40.{0,10}plate)\b',4),
]
DISQUALIFY=re.compile(r'\b(coil processing|slitting coils|coil slitting|telecommunication towers?|cell towers?|ornamental iron|fence installation|automotive body repair)\b',re.I)

def safe_site(url):
    try:
        p=urllib.parse.urlsplit(url)
        if p.scheme not in ('http','https') or not p.hostname or p.username or p.password:return False
        if p.hostname.lower() in ('localhost','localhost.localdomain') or p.hostname.lower().endswith(('.local','.internal')):return False
        try:
            addr=ipaddress.ip_address(p.hostname)
            if not addr.is_global:return False
        except ValueError:pass
        # Avoid resolving non-public hosts on GitHub runners.
        for info in socket.getaddrinfo(p.hostname,None,type=socket.SOCK_STREAM):
            if not ipaddress.ip_address(info[4][0]).is_global:return False
        return True
    except (ValueError,OSError):return False

def qualify(lead, now=None):
    now=now or dt.datetime.now(dt.timezone.utc)
    url=lead.get('website')
    result={'fit':'Unverified','score':0,'signals':[],'checked_at':now.isoformat(),'evidence_url':None,
            'note':'No company website available for independent capability review.'}
    if not url:return result
    if not safe_site(url):
        result['note']='Company website URL could not be safely validated.';return result
    try:
        req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0 (compatible; RangerSteelIntel/2.0; public business research)','Accept':'text/html'})
        with urllib.request.urlopen(req,timeout=9) as response:
            final=response.geturl()
            if not safe_site(final):raise ValueError('Unsafe redirect')
            if 'html' not in response.headers.get('Content-Type','').lower():raise ValueError('Non-HTML page')
            raw=response.read(300000).decode('utf-8','replace')
        parser=VisibleText();parser.feed(raw)
        content=re.sub(r'\s+',' ',' '.join(parser.parts))[:90000]
        found=[{'label':label,'excerpt':re.search(pattern,content,re.I).group(0),'weight':weight} for label,pattern,weight in SIGNALS if re.search(pattern,content,re.I)]
        score=sum(x['weight'] for x in found)
        excluded=bool(DISQUALIFY.search(content))
        result.update(score=score,signals=[{'label':x['label'],'excerpt':x['excerpt']} for x in found],evidence_url=final,
                      fit='Potentially strong' if score>=8 and not excluded else 'Worth reviewing' if score>=3 and not excluded else 'Likely poor fit' if excluded else 'Unverified',
                      note='Website keyword signals only. Confirm full-size plate purchasing, in-house processing, grades, thicknesses and volume before qualifying.' if found else 'No plate-related capabilities were identified in the accessible website text.')
    except Exception as exc:
        result['note']='Website review unavailable ('+type(exc).__name__+'). No buying capability inferred.'
    return result

def qualify_batch(leads, limit=12):
    now=dt.datetime.now(dt.timezone.utc)
    candidates=[x for x in leads if x.get('website') and (not x.get('qualification',{}).get('checked_at') or
        (now-dt.datetime.fromisoformat(x['qualification']['checked_at'])).days>=14)]
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        results=list(pool.map(lambda lead:qualify(lead,now),candidates[:limit]))
    for lead, result in zip(candidates[:limit],results):lead['qualification']=result
    return len(results)
