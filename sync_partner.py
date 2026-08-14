#!/usr/bin/env python3
"""Обновление data/partner_cities.json по sitemap Цветочной-Доставки.

Зачем: рабочая ссылка у партнёра — только /gorod/magazin. Магазины появляются
и закрываются, поэтому карту нужно периодически сверять с их sitemap, иначе
ссылки начнут отдавать редирект на главную.

Запуск:
    python3 sync_partner.py           # показать расхождения, ничего не менять
    python3 sync_partner.py --write   # записать обновлённую карту
"""

import json
import os
import re
import sys
from collections import defaultdict
from urllib.request import Request, urlopen

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PARTNER = "https://xn----7sbbagdmf4cyake3bhh7cv0m.xn--p1ai"
SITEMAP = f"{PARTNER}/sitemap.xml"
MAP_PATH = os.path.join(BASE_DIR, 'data', 'partner_cities.json')

# Служебные разделы партнёрского сайта — это не города
NON_CITY = {'legal', 'payment', 'payment-return', '_nuxt'}


def fetch_sitemap():
    req = Request(SITEMAP, headers={'User-Agent': 'Mozilla/5.0 (compatible; kraeved-sync/1.0)'})
    with urlopen(req, timeout=60) as resp:
        return resp.read().decode('utf-8')


def parse_shops(xml):
    """{город: [магазины по убыванию числа страниц]} — популярность как прокси качества."""
    counts = defaultdict(lambda: defaultdict(int))
    for loc in re.findall(r'<loc>(.*?)</loc>', xml):
        if not loc.startswith(PARTNER + '/'):
            continue
        parts = [p for p in loc[len(PARTNER) + 1:].split('/') if p]
        if len(parts) >= 2 and parts[0] not in NON_CITY:
            counts[parts[0]][parts[1]] += 1
    return {city: [s for s, _ in sorted(shops.items(), key=lambda kv: -kv[1])]
            for city, shops in counts.items()}


def main():
    current = json.load(open(MAP_PATH, encoding='utf-8'))
    live = parse_shops(fetch_sitemap())
    print(f"У партнёра городов: {len(live)}, в нашей карте: {len(current)}")

    changes = []
    for name, entry in sorted(current.items()):
        shops = live.get(entry['slug'])
        if not shops:
            changes.append(f"ГОРОД ИСЧЕЗ: {name} (/{entry['slug']}/) — ссылки перестанут работать")
            continue
        if entry['shop'] not in shops:
            changes.append(f"магазин закрыт: {name}: {entry['shop']} -> {shops[0]}")
            entry['shop'] = shops[0]
        if entry.get('shops') != shops:
            entry['shops'] = shops

    known = {e['slug'] for e in current.values()}
    for city in sorted(set(live) - known):
        changes.append(f"НОВЫЙ ГОРОД у партнёра: /{city}/ ({live[city][0]}) — "
                       f"добавьте его в data/partner_cities.json и привяжите к региону")

    if not changes:
        print("Расхождений нет.")
    else:
        print()
        for line in changes:
            print(f"  • {line}")

    if '--write' in sys.argv:
        with open(MAP_PATH, 'w', encoding='utf-8') as f:
            json.dump(current, f, ensure_ascii=False, indent=2)
        print(f"\nКарта обновлена: {MAP_PATH}")
        print("Дальше: python3 generate.py && python3 check_links.py --external")
    elif changes:
        print("\nЗапустите с --write, чтобы применить (новые города добавляются вручную).")


if __name__ == '__main__':
    main()
