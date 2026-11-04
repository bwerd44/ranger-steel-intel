"""Free, deterministic report generation. RSS headlines are discovery, not evidence."""
import argparse
import concurrent.futures
import datetime as dt
import email.utils
import hashlib
import html
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parent
UTC = dt.timezone.utc
CATEGORIES = ('Domestic Mill News', 'Import News', 'All Other Steel News')
QUERIES = (
    (CATEGORIES[0], 'US steel plate mill production allocation lead times shutdown'),
    (CATEGORIES[1], 'steel plate imports tariffs trade duties global'),
    (CATEGORIES[2], 'steel plate demand manufacturing fabrication energy infrastructure'),
)
SSAB = 'https://www.ssab.com/en/company/investors/ssab-as-an-investment/market-situation-and-outlook'
AISI = 'https://www.steel.org/industry-data/'


def fetch(url):
    request = urllib.request.Request(url, headers={'User-Agent': 'RangerSteelIntel/2.0 (public market research)'})
    with urllib.request.urlopen(request, timeout=18) as response:
        return response.read(2_000_000).decode('utf-8', errors='replace')


class Text(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts, self.skip = [], 0
    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style', 'noscript'):
            self.skip += 1
        if tag in ('p', 'div', 'h1', 'h2', 'h3', 'br', 'tr'):
            self.parts.append('\n')
    def handle_endtag(self, tag):
        if tag in ('script', 'style', 'noscript'):
            self.skip = max(0, self.skip - 1)
        if tag in ('p', 'div', 'h1', 'h2', 'h3', 'tr'):
            self.parts.append('\n')
    def handle_data(self, data):
        if not self.skip:
            self.parts.append(data)


def plain(raw):
    parser = Text()
    parser.feed(raw)
    return re.sub(r'\s+', ' ', html.unescape(' '.join(parser.parts))).strip()


def date_of(value):
    try:
        return dt.datetime.fromisoformat(value.replace('Z', '+00:00')).date()
    except (ValueError, AttributeError):
        return None


def canonical(url):
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme not in ('https', 'http') or not parsed.netloc:
        return ''
    query = [(k, v) for k, v in urllib.parse.parse_qsl(parsed.query) if not k.lower().startswith(('utm_', 'gclid', 'fbclid'))]
    return urllib.parse.urlunsplit((parsed.scheme, parsed.netloc.lower(), parsed.path.rstrip('/'), urllib.parse.urlencode(query), ''))


def news_category(title):
    if re.search(r'import|export|tariff|trade|duties|customs|section 232', title, re.I):
        return CATEGORIES[1]
    if re.search(r'\b(mill|nucor|ssab|jsw|cliffs|allocation|shutdown|outage)\b', title, re.I):
        return CATEGORIES[0]
    return CATEGORIES[2]


def dedupe(articles):
    """Assign once, removing syndicated title duplicates as well as repeated URLs."""
    seen_titles, seen_urls, result = set(), set(), []
    for item in sorted(articles, key=lambda x: x.get('date', ''), reverse=True):
        title = re.sub(r'\s+[-–|]\s+[^-–|]+$', '', item.get('title', ''))
        key = re.sub(r'[^a-z0-9]', '', title.lower())
        url = canonical(item.get('url', ''))
        if not key or not url or key in seen_titles or url in seen_urls:
            continue
        seen_titles.add(key)
        seen_urls.add(url)
        item = dict(item, url=url, category=news_category(title))
        result.append(item)
    return result[:45]


def collect_news(now):
    articles, checks = [], []
    def feed(query):
        category, text = query
        url = 'https://news.google.com/rss/search?' + urllib.parse.urlencode({'q': text + ' when:14d', 'hl': 'en-US', 'gl': 'US', 'ceid': 'US:en'})
        try:
            root = ET.fromstring(fetch(url))
            found = []
            for node in root.findall('./channel/item')[:25]:
                try:
                    published = email.utils.parsedate_to_datetime(node.findtext('pubDate') or '').astimezone(UTC)
                except (ValueError, TypeError):
                    continue
                age = (now.date() - published.date()).days
                if not 0 <= age <= 14:
                    continue
                title = plain(node.findtext('title') or '')
                if not re.search(r'\b(steel|plate|nucor|ssab|jsw)\b', title, re.I):
                    continue
                found.append({'title': title, 'date': published.date().isoformat(), 'url': node.findtext('link') or '', 'publisher': node.findtext('source') or 'Publisher not supplied', 'topic': category, 'verification': 'Headline only; underlying article not independently verified.', 'ranger_note': 'Discovered through Google News RSS. The headline alone does not establish plate pricing, mill allocations, lead times or current availability.'})
            return found, {'source': category + ' RSS', 'status': 'ok', 'items': len(found)}
        except Exception as error:
            return [], {'source': category + ' RSS', 'status': 'unavailable', 'reason': type(error).__name__}
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        for found, check in pool.map(feed, QUERIES):
            articles.extend(found)
            checks.append(check)
    return dedupe(articles), checks


def parse_official(url, raw, now):
    """Only recognized, dated primary-source structures become report evidence."""
    text = plain(raw)
    if urllib.parse.urlsplit(url).hostname == 'www.steel.org' and '/steel-imports-' in url:
        published = re.search(r'(\w+ \d{1,2}, 20\d{2})\s+Finished Import', text)
        period = re.search(r'of steel in (\w+ 20\d{2}), including', text)
        trend = re.search(r'Total and finished steel imports are (down|up) ([\d.]+)% and ([\d.]+)%, respectively, year-to-date vs\. (20\d{2})', text)
        if published and period and trend:
            day = dt.datetime.strptime(published[1], '%B %d, %Y').date()
            return {'id': 'aisi-imports', 'publisher': 'AISI / preliminary Census data', 'url': url, 'title': 'Monthly steel import report', 'period': period[1], 'evidence_date': day.isoformat(), 'date_kind': 'publication date', 'max_age_days': 45, 'observations': {'imports': f'AISI’s {day.isoformat()} release reports total steel imports {trend[1]} {trend[2]}% and finished steel imports {trend[1]} {trend[3]}% year to date versus {trend[4]}, using preliminary Census data through {period[1]}. These totals cover all steel products and all origins, not plate alone.'}}
    if url == SSAB:
        period = re.search(r'The market during (Q[1-4])\s+(20\d{2})', text, re.I)
        north = re.search(r'The North American plate market (.{0,600}?)(?=Market prices in China|Outlook for|How can we help|$)', text, re.I)
        if not period or not north:
            return None
        quarter, year = int(period[1][1]), int(period[2])
        end_month = quarter * 3
        end = dt.date(year + end_month // 12, end_month % 12 + 1, 1) - dt.timedelta(days=1)
        if end > now.date():
            return None
        passage = north[0].lower()
        observations = {}
        if 'strong' in passage and ('prices continued to increase' in passage or 'prices increased' in passage):
            observations['overview'] = f'SSAB describes a strong North American plate market in Q{quarter} {year}, alongside rising prices.'
            observations['pricing'] = f'SSAB reports that North American plate prices increased during Q{quarter} {year}. This describes a quarterly trend, not a current spot quote or a price for a particular grade or size.'
            observations['demand'] = f'SSAB describes the North American plate market as strong in Q{quarter} {year}. Its commentary does not quantify present demand by consuming industry.'
        if re.search(r'inventory levels.{0,160}(somewhat low|low)', passage):
            observations['domestic'] = 'SSAB assesses North American distributor inventories as somewhat low for the reported quarter. This is an inventory assessment, not a published mill allocation or delivery schedule.'
        if observations:
            return {'id': 'ssab-market', 'publisher': 'SSAB', 'url': url, 'title': 'Market situation and outlook', 'period': f'Q{quarter} {year}', 'evidence_date': end.isoformat(), 'date_kind': 'period end; publication date not supplied on page', 'max_age_days': 105, 'observations': observations}
    if url == AISI:
        match = re.search(r'week ending on (\w+ \d{1,2}, 20\d{2}).{0,80}production was ([\d,]+) net tons.{0,80}utilization rate was ([\d.]+) percent', text, re.I)
        if match:
            end = dt.datetime.strptime(match[1], '%B %d, %Y').date()
            return {'id': 'aisi-production', 'publisher': 'AISI', 'url': url, 'title': 'Weekly raw steel production', 'period': 'Week ending ' + end.isoformat(), 'evidence_date': end.isoformat(), 'date_kind': 'reporting period end', 'max_age_days': 14, 'observations': {'domestic': f'AISI estimates U.S. raw steel output at {match[2]} net tons and capacity utilization at {match[3]}% for the week ending {end.isoformat()}. These figures cover all raw steel and do not measure discrete plate availability.'}}
    return None


def refresh_evidence(reviewed, previous, now, offline=False):
    candidates = {x['id']: x for x in reviewed + previous}
    checks = []
    def retrieve(url):
        try:
            if offline:
                raise RuntimeError('offline fixture')
            parsed = parse_official(url, fetch(url), now)
            if not parsed:
                return None, {'source': url, 'status': 'unrecognized', 'reason': 'No supported dated evidence found; no new claim inferred.'}
            parsed['retrieved_at'] = now.isoformat()
            parsed['access'] = 'Retrieved from primary source this collection'
            return parsed, {'source': url, 'status': 'ok'}
        except Exception as error:
            return None, {'source': url, 'status': 'unavailable', 'reason': type(error).__name__}
    urls = [SSAB, AISI]
    if not offline:
        try:
            # AISI's live news index supplies the latest import release URL.
            index = fetch('https://www.steel.org/news/')
            links = re.findall(r'href=[\"\x27](https://www\.steel\.org/20\d{2}/\d{2}/steel-imports-[^\"\x27]+)', index)
            if links:
                urls.extend(sorted(set(html.unescape(u) for u in links), reverse=True)[:4])
            else:
                checks.append({'source': 'AISI import discovery', 'status': 'unrecognized'})
        except Exception as error:
            checks.append({'source': 'AISI import discovery', 'status': 'unavailable', 'reason': type(error).__name__})
    # Re-fetch the last known dated release too; never reset its evidence date.
    urls.extend(e['url'] for e in candidates.values() if e['id'] == 'aisi-imports' and e['url'] not in urls)
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        for parsed, check in pool.map(retrieve, urls):
            checks.append(check)
            if parsed and (parsed['id'] not in candidates or parsed['evidence_date'] >= candidates[parsed['id']]['evidence_date']):
                candidates[parsed['id']] = parsed
    active = []
    for item in candidates.values():
        date = date_of(item.get('evidence_date'))
        reviewed_at = date_of(item.get('reviewed_at') or item.get('retrieved_at'))
        if not date or not reviewed_at or not 0 <= (now.date() - date).days <= item.get('max_age_days', 30):
            continue
        if reviewed_at > now.date():
            continue
        # A successful fetch is never implied for retained reviewed evidence.
        if item.get('retrieved_at') != now.isoformat():
            item = dict(item, access='Retained dated evidence; not reverified during this collection')
        active.append(item)
    return active, checks


SECTIONS = (
    ('overview', 'Market Overview', 'Current public evidence is insufficient to establish the direction of the U.S. carbon steel plate market.', 'Quarterly producer commentary provides background rather than a live market survey.'),
    ('domestic', 'Domestic Mill Supply', 'No recent primary-source production or plate inventory evidence is available in this collection.', 'Mill-specific allocation percentages, lead times, shutdown status and grade-by-size availability are not verified by this report.'),
    ('imports', 'Imports & Trade', 'No recent verified import-volume evidence is available in this collection.', 'All-steel imports are not a measure of plate imports. Current country- and product-specific tariffs, trade restrictions, landed costs and arrival dates remain unverified; RSS trade headlines are discovery only.'),
    ('pricing', 'Pricing Trends', 'No reliable plate-specific price movement was verified in this collection.', 'No current dollar-per-ton or dollar-per-cwt assessment is available. The report does not estimate mill quotes, transaction prices or Ranger selling prices.'),
    ('demand', 'Demand Outlook', 'No recent plate-specific demand evidence is available in this collection.', 'Current manufacturing, fabrication, energy and infrastructure plate orders are not measured separately. General steel commentary cannot establish project-level demand.'),
)


def build_briefing(evidence, now):
    sections = []
    for key, title, fallback, limit in SECTIONS:
        matches = [e for e in evidence if e.get('observations', {}).get(key)]
        matches.sort(key=lambda e: e['evidence_date'], reverse=True)
        # Keep the narrative short and avoid turning the briefing into story cards.
        matches = matches[:2]
        paragraphs = [{'kind': 'reported', 'text': e['observations'][key], 'source_ids': [e['id']]} for e in matches]
        if not paragraphs:
            paragraphs = [{'kind': 'unavailable', 'text': fallback, 'source_ids': []}]
        paragraphs.append({'kind': 'context', 'text': limit, 'source_ids': []})
        sections.append({'id': key, 'title': title, 'status': 'Dated evidence' if matches else 'Data unavailable', 'paragraphs': paragraphs})
    has_plate = any(e['id'] == 'ssab-market' for e in evidence)
    overall = ('The available producer commentary points to a firm plate market in the reported quarter, while broader steel statistics add context rather than confirmation of today’s plate supply. ' if has_plate else 'The available evidence does not support a firm conclusion about current plate market direction. ')
    overall += 'A precise assessment of present spot conditions remains limited by unverified mill schedules, allocations and transaction pricing. This is a neutral interpretation of dated public evidence, not a purchasing or sales recommendation.'
    sections.append({'id': 'conditions', 'title': 'Overall Market Conditions', 'status': 'Interpretation', 'paragraphs': [{'kind': 'interpretation', 'text': overall, 'source_ids': [e['id'] for e in evidence]}]})
    return {'title': 'Morning Market Briefing', 'generated_at': now.isoformat(), 'method': 'Rules-based synthesis of dated primary-source evidence. No AI service. RSS headlines are excluded from factual briefing claims.', 'sections': sections, 'sources': evidence}


def validate(data):
    assert data['schema_version'] == 2
    sections = data['briefing']['sections']
    assert [s['id'] for s in sections] == ['overview', 'domestic', 'imports', 'pricing', 'demand', 'conditions']
    source_ids = {s['id'] for s in data['briefing']['sources']}
    for section in sections:
        assert section['paragraphs']
        for p in section['paragraphs']:
            assert p['kind'] in ('reported', 'context', 'interpretation', 'unavailable')
            assert set(p['source_ids']) <= source_ids
            if p['kind'] == 'reported':
                assert p['source_ids']
    articles = data['articles']
    assert len({canonical(a['url']) for a in articles}) == len(articles)
    assert all(a['category'] in CATEGORIES for a in articles)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--offline', action='store_true', help='Generate from dated reviewed evidence; no network. For tests only.')
    parser.add_argument('--output', type=Path, default=ROOT / 'data/latest.json')
    args = parser.parse_args()
    now = dt.datetime.now(UTC)
    reviewed = json.loads((ROOT / 'data/reviewed-evidence.json').read_text())['sources']
    previous = {}
    if args.output.exists():
        previous = json.loads(args.output.read_text())
    evidence, checks = refresh_evidence(reviewed, previous.get('briefing', {}).get('sources', []), now, args.offline)
    articles, feeds = ([], []) if args.offline else collect_news(now)
    if not articles:
        # Retain recent items only and explicitly disclose failed/empty refreshes.
        recent = [a for a in previous.get('articles', []) if date_of(a.get('date')) and 0 <= (now.date() - date_of(a['date'])).days <= 14]
        articles = dedupe(recent)
        news_status = 'retained' if articles else 'unavailable'
    else:
        news_status = 'fresh'
    data = {'schema_version': 2, 'updated_at': now.isoformat(), 'briefing': build_briefing(evidence, now), 'articles': articles, 'collection': {'mode': 'offline test' if args.offline else 'live', 'news_status': news_status, 'checks': checks + feeds}}
    validate(data)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix('.tmp')
    temporary.write_text(json.dumps(data, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    temporary.replace(args.output)
    print(f'Generated six-section briefing; {len(evidence)} dated sources; news {news_status}; {len(articles)} unique articles.')
    for check in checks + feeds:
        print(check['source'], check['status'])


if __name__ == '__main__':
    main()
