"""Collect public rental lists; never generate detail IDs or bypass verification."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import time
from urllib.parse import urljoin, urlsplit

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
SOURCES = [
    dict(name='房天下', url='https://zu.fang.com/house-a012-b01182/',
         cards='dl.list', link='p.title a', facts='p.font15', location='p.gray6.mt12',
         price='.price', detail=r'/bj/chuzu/\d+_\d+_\d+\.htm', page='i3{page}/'),
    dict(name='我爱我家', url='https://bj.5i5j.com/zufang/subway/ss331/',
         cards='.pList li', link='.listTit a', facts='.listX', location='.listX',
         price='.price', detail=r'/zufang/\d+\.html', page='n{page}/'),
    dict(name='贝壳', url='https://bj.zu.ke.com/zufang/rs%E5%9B%9E%E9%BE%99%E8%A7%82/',
         cards='.content__list--item', link='.content__list--item--title a',
         facts='.content__list--item--des', location='.content__list--item--des',
         price='.content__list--item-price', detail=r'/zufang/[A-Za-z0-9]+\.html',
         page=None),
]


def now():
    return datetime.now(timezone.utc).isoformat()


def parse(text, source, fetched_at):
    soup = BeautifulSoup(text, 'html.parser')
    rows = []
    for card in soup.select(source['cards']):
        a = card.select_one(source['link'])
        if not a or not a.get('href'):
            continue
        url = urljoin(source['url'], a['href'])
        parts = urlsplit(url)
        if parts.scheme != 'https' or parts.hostname != urlsplit(source['url']).hostname:
            continue
        if not re.fullmatch(source['detail'], parts.path):
            continue
        def get(selector):
            node = card.select_one(selector)
            return node.get_text(' ', strip=True) if node else ''
        title = a.get('title') or a.get_text(' ', strip=True)
        if not title:
            continue
        location = get(source['location'])
        facts = get(source['facts'])
        price_text = get(source['price'])
        if source['name'] == '我爱我家':
            # Some pages include nearby-area recommendations; exclude unrelated areas.
            if not re.search(r'回龙观|龙泽|霍营|朱辛庄|育知路|平西府|生命科学园', title):
                continue
            first_p = card.select_one('.listX p')
            facts = first_p.get_text(' ', strip=True) if first_p else facts
            pieces = title.split('·')
            location = ' - '.join(pieces[1:-1]) if len(pieces) >= 4 else ''
            if not price_text:
                price_match = re.search(r'(\d[\d,]*(?:\.\d+)?)\s*元/月', card.get_text(' ', strip=True))
                price_text = price_match[0] if price_match else ''
        # A range is not a single disclosed price.
        match = re.search(r'\d[\d,]*(?:\.\d+)?', price_text)
        price = float(match[0].replace(',', '')) if match and not re.search(r'\d\s*[-~至]\s*\d', price_text) else None
        image = card.select_one('img')
        image_url = urljoin(source['url'], image.get('data-original') or image.get('data-src') or image.get('src') or '') if image else None
        if image_url and urlsplit(image_url).scheme != 'https':
            image_url = None
        communities = card.select('[href*="house-xm"]') if source['name'] == '房天下' else card.select('[href*="/xiaoqu/"]')
        community = communities[-1].get_text(' ', strip=True) if communities else ''
        if source['name'] == '贝壳':
            links = card.select('.content__list--item--des a')
            community = links[-1].get_text(' ', strip=True) if links else community
        rent_type = next((t for t in ['合租', '整租', '独栋出租'] if t in facts or t in title), '未注明')
        rows.append(dict(title=title, url=url, platform=source['name'], facts=facts,
                         location=location, estate=community or '未注明小区', rentType=rent_type,
                         price=price, priceText=price_text, image=image_url,
                         tags=[n.get_text(' ', strip=True) for n in card.select('.note, .content__list--item--bottom i')],
                         fetchedAt=fetched_at, stale=False))
    return list({r['url']: r for r in rows}.values())


def collect(source, pages=3):
    started = now()
    rows, errors, seen = [], [], set()
    for page in range(1, pages + 1):
        if page > 1 and not source['page']:
            break
        url = source['url'] if page == 1 else source['url'] + source['page'].format(page=page)
        try:
            response = requests.get(url, timeout=(10, 25), headers={'User-Agent': 'RentalNotes/1.0 (public listing reader)'})
            response.raise_for_status()
            response.encoding = 'utf-8' if b'charset="utf-8"' in response.content.lower() or source['name'] == '房天下' else response.apparent_encoding
            items = parse(response.text, source, started)
            if not items:
                raise ValueError('没有可解析的独立详情链接；可能需要登录、验证或解析规则已失效')
            fresh = [r for r in items if r['url'] not in seen]
            if not fresh:
                break  # Server may return page 1 for unsupported pagination.
            rows.extend(fresh)
            seen.update(r['url'] for r in fresh)
        except (requests.RequestException, ValueError) as exc:
            errors.append(f'第{page}页：{exc}')
            break
        time.sleep(1)
    return rows, dict(platform=source['name'], sourceUrl=source['url'], attemptedAt=started,
                      status='partial' if rows and errors else 'ok' if rows else 'error',
                      count=len(rows), message='；'.join(errors) or '已获取公开列表；未核验实际可租状态')


def combine(previous, results):
    # Keep missing listings as explicitly stale records, never pretend they were refreshed.
    merged = {r['url']: dict(r, stale=True) for r in previous}
    for rows, _ in results:
        for row in rows:
            merged[row['url']] = row
    return list(merged.values())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--pages', type=int, default=3)
    args = parser.parse_args()
    path = ROOT / 'data/listings.json'
    previous = json.loads(path.read_text(encoding='utf-8')) if path.exists() else {'listings': []}
    with ThreadPoolExecutor(max_workers=3) as pool:
        results = list(pool.map(lambda s: collect(s, max(1, min(args.pages, 5))), SOURCES))
    payload = dict(generatedAt=now(), sources=[s for _, s in results],
                   listings=combine(previous['listings'], results))
    path.parent.mkdir(exist_ok=True)
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    temporary.replace(path)
    for status in payload['sources']:
        print(json.dumps(status, ensure_ascii=False))
    if not any(rows for rows, _ in results):
        print('::warning::所有来源采集失败；已保留历史记录并更新失败状态。')


if __name__ == '__main__':
    main()
