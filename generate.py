#!/usr/bin/env python3
"""Генератор статических страниц kraeved.ru.

Источники данных (каталог data/):
    regions.json          — список 89 субъектов РФ
    regions_content.json  — уникальный контент по каждому субъекту
    partner_cities.json   — карта городов Цветочной-Доставки (город -> slug + магазин)
    districts.json        — расшифровка федеральных округов

Запуск: python3 generate.py
"""

import html
import json
import os
from datetime import date

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SITE_URL = "https://kraeved.ru"
METRIKA_ID = "111257526"

# Обложка для сниппетов ВКонтакте, Telegram и прочих соцсетей.
# Только растр и только абсолютный URL: SVG и относительные пути они не читают.
OG_IMAGE = "/images/og-cover.jpg"
OG_IMAGE_WIDTH = 1200
OG_IMAGE_HEIGHT = 630
OG_IMAGE_TYPE = "image/jpeg"

# Предзагрузка следующей страницы: Chrome и Edge готовят её ещё до клика.
# moderate — по наведению курсора, что почти всегда опережает сам клик.
SPECULATION_RULES = json.dumps({
    "prerender": [{
        "where": {"and": [
            {"href_matches": "/*"},
            {"not": {"href_matches": "/404.html"}},
        ]},
        "eagerness": "moderate",
    }],
}, ensure_ascii=False, separators=(',', ':'))

# Счётчик стартует из main.js после отрисовки — параметры кладём в window
METRIKA_CONFIG = json.dumps({
    "id": int(METRIKA_ID),
    "params": {
        "ssr": True, "webvisor": True, "clickmap": True,
        "ecommerce": "dataLayer", "accurateTrackBounce": True, "trackLinks": True,
    },
}, ensure_ascii=False, separators=(',', ':'))

# Базовый URL проекта Цветочная-Доставка (цветочная-доставка.рф в punycode)
FLOWERS_BASE_URL = "https://xn----7sbbagdmf4cyake3bhh7cv0m.xn--p1ai"


def load(name):
    with open(os.path.join(BASE_DIR, 'data', name), 'r', encoding='utf-8') as f:
        return json.load(f)


regions = load('regions.json')
content = load('regions_content.json')
partner_cities = load('partner_cities.json')
districts = load('districts.json')

for _r in regions:
    _r['prepositional_in'] = ('во ' if _r['prepositional'].startswith(('Вл', 'Вс')) else 'в ') + _r['prepositional']

by_slug = {r['slug']: r for r in regions}


def plural(n, one, few, many):
    """Русское склонение числительных: 1 место, 3 места, 5 мест."""
    if n % 10 == 1 and n % 100 != 11:
        return one
    if n % 10 in (2, 3, 4) and n % 100 not in (12, 13, 14):
        return few
    return many


def e(text):
    """Экранирование для вставки в HTML-текст и в значения атрибутов."""
    return html.escape(str(text), quote=True)


def city_url(city):
    """Ссылка на страницу магазина в городе.

    У партнёра нет посадочных страниц уровня города: /gorod/ отдаёт 302 на главную.
    Рабочий адрес — /gorod/magazin, поэтому подставляем конкретный магазин.
    """
    data = partner_cities.get(city)
    if not data:
        raise KeyError(f"Город «{city}» отсутствует в data/partner_cities.json")
    return f"{FLOWERS_BASE_URL}/{data['slug']}/{data['shop']}"


def region_url(slug):
    return f"/regions/{slug}/"


def district_url(code):
    return f"/districts/{districts[code]['slug']}/"


def district_regions(code):
    return [r for r in regions if r['district'] == code]


def neighbours(region, limit=6):
    """Соседние регионы того же федерального округа — для перелинковки."""
    same = [r for r in regions
            if r['district'] == region['district'] and r['slug'] != region['slug']]
    start = sum(ord(c) for c in region['slug']) % max(len(same), 1)
    return (same[start:] + same[:start])[:limit]


def head(title, description, canonical, og_type="website", extra=""):
    return f'''<meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{e(title)}</title>
    <meta name="description" content="{e(description)}">
    <link rel="canonical" href="{canonical}">
    <meta property="og:title" content="{e(title)}">
    <meta property="og:description" content="{e(description)}">
    <meta property="og:type" content="{og_type}">
    <meta property="og:url" content="{canonical}">
    <meta property="og:locale" content="ru_RU">
    <meta property="og:site_name" content="Краевед.ру">
    <meta property="og:image" content="{SITE_URL}{OG_IMAGE}">
    <meta property="og:image:secure_url" content="{SITE_URL}{OG_IMAGE}">
    <meta property="og:image:type" content="{OG_IMAGE_TYPE}">
    <meta property="og:image:width" content="{OG_IMAGE_WIDTH}">
    <meta property="og:image:height" content="{OG_IMAGE_HEIGHT}">
    <meta property="og:image:alt" content="Краевед.ру — достопримечательности и природа регионов России">
    <link rel="image_src" href="{SITE_URL}{OG_IMAGE}">
    <meta name="twitter:card" content="summary_large_image">
    <meta name="twitter:image" content="{SITE_URL}{OG_IMAGE}">
    <link rel="icon" href="/favicon.svg" type="image/svg+xml">
    <link rel="preconnect" href="https://mc.yandex.ru" crossorigin>
    <link rel="stylesheet" href="/css/style.css">{extra}
    <script type="speculationrules">{SPECULATION_RULES}</script>
    <script>window.__metrika={METRIKA_CONFIG};</script>
    <script src="/js/main.js" defer></script>
    <noscript><div><img src="https://mc.yandex.ru/watch/{METRIKA_ID}" style="position:absolute;left:-9999px;" alt=""/></div></noscript>'''


HEADER = '''    <header class="header">
        <div class="header-inner">
            <a href="/" class="logo">
                <svg viewBox="0 0 24 24" fill="currentColor"><path d="M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7zm0 9.5c-1.38 0-2.5-1.12-2.5-2.5s1.12-2.5 2.5-2.5 2.5 1.12 2.5 2.5-1.12 2.5-2.5 2.5z"/></svg>
                Краевед.ру
            </a>
            <button class="nav-toggle" aria-label="Меню">&#9776;</button>
            <nav class="nav">
                <a href="/regions/">Все регионы</a>
                <a href="/regions/#respubliki">Республики</a>
                <a href="/regions/#kraya">Края</a>
                <a href="/regions/#oblasti">Области</a>
            </nav>
            <div class="search-box">
                <input type="search" class="search-input" placeholder="Найти регион..." aria-label="Поиск">
                <button type="button" aria-label="Искать"><svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor"><path d="M15.5 14h-.79l-.28-.27C15.41 12.59 16 11.11 16 9.5 16 5.91 13.09 3 9.5 3S3 5.91 3 9.5 5.91 16 9.5 16c1.61 0 3.09-.59 4.23-1.57l.27.28v.79l5 4.99L20.49 19l-4.99-5zm-6 0C7.01 14 5 11.99 5 9.5S7.01 5 9.5 5 14 7.01 14 9.5 11.99 14 9.5 14z"/></svg></button>
                <div class="search-results"></div>
            </div>
        </div>
    </header>'''


def footer(year=None):
    year = year or date.today().year
    district_footer_links = "".join(
        f'<li><a href="{district_url(code)}">{e(d["name"])}</a></li>'
        for code, d in districts.items())
    return f'''    <footer class="footer">
        <div class="footer-inner">
            <div><h4>Краевед.ру</h4><p>Краеведческий портал о природе, достопримечательностях и туристических местах регионов России.</p></div>
            <div><h4>Разделы</h4><ul>
                <li><a href="/regions/">Все регионы</a></li>
                <li><a href="/regions/#respubliki">Республики</a></li>
                <li><a href="/regions/#kraya">Края</a></li>
                <li><a href="/regions/#oblasti">Области</a></li>
            </ul></div>
            <div><h4>Федеральные округа</h4><ul>{district_footer_links}</ul></div>
        </div>
        <div class="footer-bottom">© {year} Краевед.ру</div>
    </footer>'''


def page(head_html, body_html):
    return f'''<!DOCTYPE html>
<html lang="ru">
<head>
    {head_html}
</head>
<body>
{HEADER}
{body_html}
{footer()}
</body>
</html>'''


# ---------------------------------------------------------------- страница региона

def meta_description(region, c):
    """Уникальное описание: строится из реальных достопримечательностей региона."""
    names = ', '.join(a['name'] for a in c['attractions'][:3])
    return (f"Достопримечательности {region['genitive']}: {names}. "
            f"Что посмотреть, природа и туристические места. "
            f"Административный центр — {region['capital']}.")


def page_title(region, c):
    first = c['attractions'][0]['name']
    return f"{region['name']} — достопримечательности и природа: {first} | Краевед.ру"


def schema_org(region, c, canonical):
    """Разметка: хлебные крошки + перечень достопримечательностей региона."""
    items = [{
        "@type": "ListItem",
        "position": i + 1,
        "item": {
            "@type": "TouristAttraction",
            "name": a['name'],
            "description": a['short'],
            "address": {
                "@type": "PostalAddress",
                "addressRegion": region['name'],
                "addressCountry": "RU",
            },
        },
    } for i, a in enumerate(c['attractions'])]

    data = [
        {
            "@context": "https://schema.org",
            "@type": "BreadcrumbList",
            "itemListElement": [
                {"@type": "ListItem", "position": 1, "name": "Главная", "item": SITE_URL + "/"},
                {"@type": "ListItem", "position": 2, "name": "Регионы", "item": SITE_URL + "/regions/"},
                {"@type": "ListItem", "position": 3, "name": region['name'], "item": canonical},
            ],
        },
        {
            "@context": "https://schema.org",
            "@type": "ItemList",
            "name": f"Достопримечательности: {region['name']}",
            "numberOfItems": len(items),
            "itemListElement": items,
        },
    ]
    return ('\n    <script type="application/ld+json">'
            + json.dumps(data, ensure_ascii=False, separators=(',', ':'))
            + '</script>')


def flowers_blocks(region, c):
    """Блок о цветах региона и партнёрская врезка. Возвращает (в статью, в сайдбар)."""
    cities = region.get('flowersCities', [])
    article = f'''
                <h2>Цветы и растения {region['genitive']}</h2>
                <p>{e(c['flowers'])}</p>'''

    if not cities:
        return article, ""

    city = cities[0]
    link = city_url(city)
    if len(cities) == 1:
        where = f"в {e(city)}"
    else:
        where = f"в {e(city)} и других городах региона"

    article += f'''
        <section class="flowers-article">
            <h3>Доставка цветов {where}</h3>
            <p>Букет из живых цветов — способ поздравить близких {where}, даже находясь далеко.
            Заказ и доставку берёт на себя наш партнёр — сервис «Цветочная-Доставка».</p>
            <a href="{link}" class="flowers-link" target="_blank" rel="noopener">
                Заказать цветы в {e(city)} →
            </a>
        </section>'''

    links = ', '.join(
        f'<a href="{city_url(x)}" target="_blank" rel="noopener">{e(x)}</a>' for x in cities)
    sidebar = f'''
                <div class="flowers-promo">
                    <h3>Доставка цветов</h3>
                    <p>Города региона, куда доставляют букеты: {links}</p>
                    <a href="{link}" class="btn" target="_blank" rel="noopener">Выбрать букет</a>
                </div>'''
    return article, sidebar


def generate_region_page(region):
    c = content[region['slug']]
    canonical = f"{SITE_URL}{region_url(region['slug'])}"
    district = districts[region['district']]

    attractions = "\n                    ".join(
        f'''<li>
                        <details class="attraction-item">
                            <summary>{e(a['name'])} — {e(a['short'])}</summary>
                            <div class="attraction-desc">{e(a['full'])}</div>
                        </details>
                    </li>''' for a in c['attractions'])

    flowers_article, flowers_sidebar = flowers_blocks(region, c)

    nearby = "".join(
        f'<li><a href="{region_url(n["slug"])}">{e(n["name"])}</a></li>'
        for n in neighbours(region))

    head_html = head(
        page_title(region, c),
        meta_description(region, c),
        canonical,
        og_type="article",
        extra=schema_org(region, c, canonical),
    )

    body = f'''    <div class="region-header">
        <div class="region-header-inner">
            <nav class="breadcrumb">
                <a href="/">Главная</a><span>›</span>
                <a href="/regions/">Регионы</a><span>›</span>
                {e(region['name'])}
            </nav>
            <h1>{e(region['name'])}: достопримечательности и природа</h1>
            <p class="capital">{e(region['type'])} • Административный центр: {e(region['capital'])} • <a href="{district_url(region['district'])}">{e(district['name'])}</a></p>
        </div>
    </div>

    <main class="main">
        <div class="region-content">
            <article class="region-main">
                <h2>О регионе</h2>
                <p>{e(c['description'])}</p>

                <h2>Что посмотреть {region['prepositional_in']}: {len(c['attractions'])} {plural(len(c['attractions']), "достопримечательность", "достопримечательности", "достопримечательностей")}</h2>
                <ul class="attractions-list">
                    {attractions}
                </ul>
                {flowers_article}
                <div class="source">
                    <p>Источники: данные особо охраняемых природных территорий (заповедники и национальные парки),
                    материалы региональных музеев-заповедников и краеведческих музеев, реестр объектов
                    культурного наследия, списки Всемирного наследия ЮНЕСКО.</p>
                </div>
            </article>

            <aside class="region-sidebar">
                <div class="sidebar-card">
                    <h3>Справка</h3>
                    <ul>
                        <li><strong>Тип:</strong> {e(region['type'])}</li>
                        <li><strong>Центр:</strong> {e(region['capital'])}</li>
                        <li><strong>Округ:</strong> <a href="{district_url(region['district'])}">{e(region['district'])}</a></li>
                        <li><strong>Объектов на странице:</strong> {len(c['attractions'])}</li>
                    </ul>
                </div>
                {flowers_sidebar}
                <div class="sidebar-card">
                    <h3>Рядом: {e(region['district'])}</h3>
                    <p class="sidebar-note"><a href="{district_url(region['district'])}">Все регионы округа ({len(district_regions(region['district']))})</a></p>
                    <ul>{nearby}</ul>
                </div>
                <div class="sidebar-card">
                    <h3>Все регионы</h3>
                    <ul><li><a href="/regions/">Каталог 89 субъектов России</a></li></ul>
                </div>
            </aside>
        </div>
    </main>'''

    return page(head_html, body)


# ------------------------------------------------------------------ каталог регионов

GROUPS = [
    ("respubliki", "Республики", lambda r: r['type'] == 'Республика'),
    ("kraya", "Края", lambda r: r['type'] == 'Край'),
    ("oblasti", "Области", lambda r: r['type'] == 'Область'),
    ("goroda", "Города федерального значения", lambda r: r['type'].startswith('Город')),
    ("ao", "Автономные округа и области", lambda r: 'Автономн' in r['type']),
]


def region_card(r):
    c = content[r['slug']]
    rest = len(c['attractions']) - 1
    teaser = c['attractions'][0]['name']
    badge = '<span class="card-flowers">🌷 доставка цветов</span>' if r.get('hasFlowers') else ''
    return f'''<a href="{region_url(r['slug'])}" class="region-card">
                    <h3>{e(r['name'])}</h3>
                    <p class="region-card-capital">{e(r['capital'])}</p>
                    <p class="region-card-teaser">{e(teaser)} и ещё {rest} {plural(rest, 'место', 'места', 'мест')}</p>
                    {badge}
                </a>'''


def generate_catalog():
    canonical = f"{SITE_URL}/regions/"
    counts = {key: [r for r in regions if test(r)] for key, _, test in GROUPS}
    total_attractions = sum(len(content[r['slug']]['attractions']) for r in regions)
    with_flowers = [r for r in regions if r.get('hasFlowers')]

    sections = []
    for key, title, _ in GROUPS:
        group = counts[key]
        if not group:
            continue
        cards = "\n                ".join(region_card(r) for r in group)
        sections.append(f'''        <section class="region-group" id="{key}">
            <h2>{title} ({len(group)})</h2>
            <div class="regions-grid">
                {cards}
            </div>
        </section>''')

    head_html = head(
        "Все регионы России — 89 субъектов РФ с достопримечательностями | Краевед.ру",
        f"Каталог всех 89 регионов России: {total_attractions} достопримечательностей, природные "
        f"и туристические места. Республики, края, области, автономные округа и города федерального значения.",
        canonical,
    )

    body = f'''    <main class="main">
        <div class="catalog-header">
            <nav class="breadcrumb"><a href="/">Главная</a><span>›</span>Регионы</nav>
            <h1>Все регионы России</h1>
            <p>Полный список 89 субъектов Российской Федерации: природа, достопримечательности и туристические места каждого региона.</p>
            <div class="catalog-stats">
                <div class="stat-item"><div class="stat-number">{len(regions)}</div><div class="stat-label">Регионов</div></div>
                <div class="stat-item"><div class="stat-number">{total_attractions}</div><div class="stat-label">Достопримечательностей</div></div>
                <div class="stat-item"><div class="stat-number">{len(counts['respubliki'])}</div><div class="stat-label">Республик</div></div>
                <div class="stat-item"><div class="stat-number">{len(counts['oblasti'])}</div><div class="stat-label">Областей</div></div>
                <div class="stat-item"><div class="stat-number">{len(with_flowers)}</div><div class="stat-label">С доставкой цветов</div></div>
            </div>
        </div>

{chr(10).join(sections)}
    </main>'''

    return page(head_html, body)


# ------------------------------------------------------------ страницы округов

def generate_district_page(code):
    d = districts[code]
    group = district_regions(code)
    canonical = f"{SITE_URL}{district_url(code)}"
    total = sum(len(content[r['slug']]['attractions']) for r in group)
    flowers = [r for r in group if r.get('hasFlowers')]

    cards = "\n                ".join(region_card(r) for r in group)
    others = "".join(
        f'<li><a href="{district_url(other)}">{e(districts[other]["name"])}</a></li>'
        for other in districts if other != code)

    highlights = ', '.join(
        content[r['slug']]['attractions'][0]['name'] for r in group[:4])

    head_html = head(
        f"{d['name']} — {len(group)} регионов и {total} достопримечательностей | Краевед.ру",
        f"{d['name']}: {len(group)} субъектов РФ, {total} достопримечательностей. "
        f"{highlights} и другие природные и туристические места. Центр округа — {d['center']}.",
        canonical,
        extra=f'''
    <script type="application/ld+json">{json.dumps({
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Главная", "item": SITE_URL + "/"},
            {"@type": "ListItem", "position": 2, "name": "Регионы", "item": SITE_URL + "/regions/"},
            {"@type": "ListItem", "position": 3, "name": d['name'], "item": canonical},
        ],
    }, ensure_ascii=False, separators=(',', ':'))}</script>''',
    )

    body = f'''    <main class="main">
        <div class="catalog-header">
            <nav class="breadcrumb">
                <a href="/">Главная</a><span>›</span>
                <a href="/regions/">Регионы</a><span>›</span>
                {e(d['name'])}
            </nav>
            <h1>{e(d['name'])}</h1>
            <p>{e(d['description'])}</p>
            <div class="catalog-stats">
                <div class="stat-item"><div class="stat-number">{len(group)}</div><div class="stat-label">Регионов</div></div>
                <div class="stat-item"><div class="stat-number">{total}</div><div class="stat-label">Достопримечательностей</div></div>
                <div class="stat-item"><div class="stat-number">{len(flowers)}</div><div class="stat-label">С доставкой цветов</div></div>
            </div>
        </div>

        <section class="region-group">
            <h2>Регионы округа</h2>
            <div class="regions-grid">
                {cards}
            </div>
        </section>

        <section class="region-group">
            <h2>Другие федеральные округа</h2>
            <ul class="district-list">{others}</ul>
        </section>
    </main>'''

    return page(head_html, body)


# --------------------------------------------------------------------- главная

POPULAR =['krym', 'krasnodarskiy-kray', 'kareliya', 'altay', 'buryatiya', 'kamchatskiy-kray',
           'dagestan', 'moskva', 'sankt-peterburg', 'tatarstan', 'murmanskaya-oblast', 'irkutskaya-oblast']


def generate_index():
    canonical = f"{SITE_URL}/"
    total_attractions = sum(len(content[r['slug']]['attractions']) for r in regions)

    cards = "\n                ".join(region_card(by_slug[s]) for s in POPULAR)

    district_links = "\n                ".join(
        f'<a href="{district_url(code)}" class="region-type-btn">{e(d["name"])} ({len(district_regions(code))})</a>'
        for code, d in districts.items())

    head_html = head(
        "Краевед.ру — достопримечательности и природа 89 регионов России",
        f"Краеведческий портал: {total_attractions} достопримечательностей всех 89 регионов России. "
        f"Природные памятники, заповедники, туристические места, флора регионов.",
        canonical,
        extra=f'''
    <script type="application/ld+json">{json.dumps({
        "@context": "https://schema.org",
        "@type": "WebSite",
        "name": "Краевед.ру",
        "url": SITE_URL + "/",
        "description": "Краеведческий портал о природе и достопримечательностях регионов России",
        "inLanguage": "ru-RU",
    }, ensure_ascii=False, separators=(',', ':'))}</script>''',
    )

    body = f'''    <section class="hero">
        <h1>Краеведческий портал России</h1>
        <p>{total_attractions} достопримечательностей всех {len(regions)} регионов: заповедники и национальные парки,
        памятники архитектуры, природные чудеса и туристические маршруты.</p>
    </section>

    <main class="main">
        <section>
            <h2 class="section-title">Популярные регионы</h2>
            <div class="regions-grid">
                {cards}
            </div>
        </section>

        <section>
            <h2 class="section-title">Федеральные округа</h2>
            <div class="region-types">
                {district_links}
            </div>
        </section>

        <section>
            <h2 class="section-title">О портале</h2>
            <p>Краевед.ру собирает сведения о природных и культурных достопримечательностях субъектов
            Российской Федерации. Для каждого региона описаны реальные объекты — заповедники, национальные
            парки, памятники природы и архитектуры, — а также растения и цветы, характерные для местной флоры.</p>
            <p><a href="/regions/">Перейти к каталогу всех {len(regions)} регионов →</a></p>
        </section>
    </main>'''

    return page(head_html, body)


# --------------------------------------------------------------------- 404

def generate_404():
    popular = "".join(
        f'<li><a href="{region_url(s)}">{e(by_slug[s]["name"])}</a></li>' for s in POPULAR[:6])

    head_html = head(
        "Страница не найдена — Краевед.ру",
        "Такой страницы на портале нет. Перейдите в каталог регионов России.",
        f"{SITE_URL}/404.html",
        extra='\n    <meta name="robots" content="noindex, follow">',
    )

    body = f'''    <main class="main">
        <div class="catalog-header">
            <h1>Страница не найдена</h1>
            <p>Возможно, адрес набран с опечаткой или страница была перемещена.
            Все материалы портала собраны в каталоге регионов.</p>
        </div>

        <section class="region-group">
            <h2>Куда пойти дальше</h2>
            <ul class="district-list">
                <li><a href="/regions/">Все {len(regions)} регионов</a></li>
                {popular}
            </ul>
        </section>
    </main>'''

    return page(head_html, body)


# --------------------------------------------------------------------- sitemap / robots

def generate_sitemap():
    today = date.today().isoformat()
    urls = [(SITE_URL + "/", "weekly", "1.0"), (SITE_URL + "/regions/", "weekly", "0.9")]
    urls += [(f"{SITE_URL}{district_url(code)}", "monthly", "0.7") for code in districts]
    urls += [(f"{SITE_URL}{region_url(r['slug'])}", "monthly", "0.8") for r in regions]

    body = "\n".join(f'''    <url>
        <loc>{loc}</loc>
        <lastmod>{today}</lastmod>
        <changefreq>{freq}</changefreq>
        <priority>{prio}</priority>
    </url>''' for loc, freq, prio in urls)

    return f'''<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
{body}
</urlset>
'''


def generate_search_index():
    """Минимальный индекс для строки поиска: короткие ключи, только нужные поля."""
    return json.dumps(
        [{"s": r['slug'], "n": r['name'], "c": r['capital'], "t": r['type']} for r in regions],
        ensure_ascii=False, separators=(',', ':'))


def generate_robots():
    return f'''User-agent: *
Allow: /

Sitemap: {SITE_URL}/sitemap.xml

Host: kraeved.ru
'''


# --------------------------------------------------------------------- сборка

def check_data():
    """Проверки перед генерацией — чтобы битые данные не попали в сборку."""
    problems = []
    for r in regions:
        if r['slug'] not in content:
            problems.append(f"нет контента: {r['slug']}")
            continue
        c = content[r['slug']]
        if len(c['attractions']) < 3:
            problems.append(f"мало достопримечательностей: {r['slug']}")
        for city in r.get('flowersCities', []):
            if city not in partner_cities:
                problems.append(f"{r['slug']}: город «{city}» не найден у партнёра")
        if r['district'] not in districts:
            problems.append(f"{r['slug']}: неизвестный округ {r['district']}")
    if problems:
        raise SystemExit("Ошибки в данных:\n  " + "\n  ".join(problems))


def write(path, text):
    full = os.path.join(BASE_DIR, path)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, 'w', encoding='utf-8') as f:
        f.write(text)


def main():
    check_data()

    print(f'Генерация {len(regions)} страниц регионов...')
    for region in regions:
        write(os.path.join('regions', region['slug'], 'index.html'),
              generate_region_page(region))
    print(f'  ✓ {len(regions)} страниц')

    write('regions/index.html', generate_catalog())
    print('  ✓ regions/index.html')

    for code in districts:
        write(os.path.join('districts', districts[code]['slug'], 'index.html'),
              generate_district_page(code))
    print(f'  ✓ {len(districts)} страниц федеральных округов')

    write('index.html', generate_index())
    print('  ✓ index.html')

    write(os.path.join('data', 'search-index.json'), generate_search_index())
    print('  ✓ data/search-index.json')

    write('404.html', generate_404())
    print('  ✓ 404.html')

    write('sitemap.xml', generate_sitemap())
    print('  ✓ sitemap.xml')

    write('robots.txt', generate_robots())
    print('  ✓ robots.txt')

    flowers = [r for r in regions if r.get('hasFlowers')]
    total = sum(len(content[r['slug']]['attractions']) for r in regions)
    print(f'\nГотово. Достопримечательностей: {total}. '
          f'Регионов с доставкой цветов: {len(flowers)}.')


if __name__ == '__main__':
    main()
