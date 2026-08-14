#!/usr/bin/env python3
"""Проверка сборки kraeved.ru перед выкладкой на сервер.

Что проверяется:
  1. внутренние ссылки ведут на существующие файлы;
  2. sitemap.xml соответствует набору сгенерированных страниц;
  3. title, description и H1 уникальны на всех страницах (иначе поисковики склеят);
  4. на страницах нет шаблонных заглушек;
  5. og:image задан абсолютным адресом и файл существует;
  6. партнёрские ссылки отдают 200 без редиректа (--external).

Запуск:
    python3 check_links.py             # быстрая проверка, без сети
    python3 check_links.py --external  # плюс проверка ссылок на партнёра
"""

import json
import os
import re
import sys
import time
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SITE_URL = "https://kraeved.ru"

# Фразы из старого шаблонного генератора: если появятся снова — страница неуникальна
STUB_PHRASES = [
    "Краеведческий музей представляет богатую коллекцию",
    "обладает уникальной природой, богатой историей",
    "характерные для данной климатической зоны",
    "Регион богат природными достопримечательностями: реками, озёрами",
]

errors = []
warnings = []


def fail(msg):
    errors.append(msg)


def warn(msg):
    warnings.append(msg)


# tools/ — исходники для сборки обложки, на сервер не уходят
SKIP_DIRS = ('.git', 'node_modules', os.sep + 'tools')


def html_files():
    for root, _, files in os.walk(BASE_DIR):
        if any(part in root for part in SKIP_DIRS):
            continue
        for name in files:
            if name.endswith('.html'):
                yield os.path.join(root, name)


def rel(path):
    return os.path.relpath(path, BASE_DIR)


def resolve_internal(href, page_path):
    """Путь на диске, которому соответствует внутренняя ссылка."""
    href = href.split('#')[0].split('?')[0]
    if not href:
        return None
    if href.startswith('/'):
        target = os.path.join(BASE_DIR, href.lstrip('/'))
    else:
        target = os.path.join(os.path.dirname(page_path), href)
    if href.endswith('/') or os.path.isdir(target):
        target = os.path.join(target, 'index.html')
    return os.path.normpath(target)


def check_pages():
    titles, descriptions, h1s = defaultdict(list), defaultdict(list), defaultdict(list)
    canonicals = defaultdict(list)
    external = set()
    pages = sorted(html_files())

    for path in pages:
        doc = open(path, encoding='utf-8').read()
        name = rel(path)

        # только ссылки из <a>: canonical и og:url ведут на ещё не выложенный сайт
        for href in re.findall(r'<a\s[^>]*href="([^"]+)"', doc):
            if href.startswith(SITE_URL):
                href = href[len(SITE_URL):] or '/'
            elif href.startswith(('http://', 'https://')):
                external.add(href)
                continue
            if href.startswith(('#', 'mailto:', 'tel:')):
                continue
            target = resolve_internal(href, path)
            if target and not os.path.exists(target):
                fail(f"{name}: битая внутренняя ссылка {href}")

        for src in re.findall(r'(?:src|href)="(/(?:css|js|images|data)/[^"]+)"', doc):
            if not os.path.exists(os.path.join(BASE_DIR, src.lstrip('/'))):
                fail(f"{name}: нет файла {src}")

        og_img = re.search(r'<meta property="og:image" content="(.*?)">', doc)
        if not og_img:
            fail(f"{name}: нет og:image — соцсети покажут сниппет без картинки")
        else:
            url = og_img.group(1)
            if not url.startswith('https://'):
                fail(f"{name}: og:image должен быть абсолютным https-адресом, а не {url}")
            elif url.startswith(SITE_URL):
                local = os.path.join(BASE_DIR, url[len(SITE_URL):].lstrip('/'))
                if not os.path.exists(local):
                    fail(f"{name}: og:image указывает на отсутствующий файл {url}")
                elif local.lower().endswith('.svg'):
                    fail(f"{name}: og:image в SVG — ВКонтакте и Telegram его не покажут")

        title = re.search(r'<title>(.*?)</title>', doc, re.S)
        desc = re.search(r'<meta name="description" content="(.*?)">', doc, re.S)
        h1 = re.search(r'<h1[^>]*>(.*?)</h1>', doc, re.S)
        canon = re.search(r'<link rel="canonical" href="(.*?)">', doc)

        if title:
            titles[title.group(1).strip()].append(name)
        else:
            fail(f"{name}: нет <title>")
        if desc:
            d = desc.group(1).strip()
            descriptions[d].append(name)
            if len(d) > 320:
                warn(f"{name}: description длиннее 320 символов ({len(d)})")
        else:
            fail(f"{name}: нет meta description")
        if h1:
            h1s[re.sub(r'<[^>]+>', '', h1.group(1)).strip()].append(name)
        else:
            fail(f"{name}: нет <h1>")
        if canon:
            canonicals[canon.group(1)].append(name)
        else:
            fail(f"{name}: нет canonical")

        for phrase in STUB_PHRASES:
            if phrase in doc:
                fail(f"{name}: шаблонная заглушка — «{phrase}»")

    for label, mapping in (("title", titles), ("description", descriptions),
                           ("H1", h1s), ("canonical", canonicals)):
        for value, where in mapping.items():
            if len(where) > 1:
                fail(f"дубль {label} на {len(where)} страницах "
                     f"({', '.join(where[:3])}...): {value[:70]}")

    print(f"Проверено страниц: {len(pages)}")
    return external


def check_sitemap():
    path = os.path.join(BASE_DIR, 'sitemap.xml')
    if not os.path.exists(path):
        fail("нет sitemap.xml")
        return
    locs = re.findall(r'<loc>(.*?)</loc>', open(path, encoding='utf-8').read())
    in_map = set(locs)

    if len(locs) != len(in_map):
        dup = [u for u, c in Counter(locs).items() if c > 1]
        fail(f"дубли URL в sitemap: {dup[:5]}")

    data = os.path.join(BASE_DIR, 'data')
    regions = json.load(open(os.path.join(data, 'regions.json'), encoding='utf-8'))
    districts = json.load(open(os.path.join(data, 'districts.json'), encoding='utf-8'))
    expected = {f"{SITE_URL}/", f"{SITE_URL}/regions/"}
    expected |= {f"{SITE_URL}/regions/{r['slug']}/" for r in regions}
    expected |= {f"{SITE_URL}/districts/{d['slug']}/" for d in districts.values()}

    for url in expected - in_map:
        fail(f"страница отсутствует в sitemap: {url}")
    for url in in_map - expected:
        fail(f"лишний URL в sitemap: {url}")

    for url in in_map:
        local = os.path.join(BASE_DIR, url[len(SITE_URL):].lstrip('/'), 'index.html')
        if not os.path.exists(os.path.normpath(local)):
            fail(f"в sitemap URL без файла: {url}")

    print(f"URL в sitemap: {len(in_map)}")


def http_status(url, attempts=3):
    """Статус и конечный URL. 5xx повторяем: партнёр троттлит частые запросы."""
    last = (None, "нет ответа")
    for attempt in range(attempts):
        req = Request(url, method='HEAD',
                      headers={'User-Agent': 'Mozilla/5.0 (compatible; kraeved-linkcheck/1.0)'})
        try:
            with urlopen(req, timeout=25) as resp:
                return resp.status, resp.url
        except HTTPError as exc:
            last = (exc.code, url)
            if exc.code < 500:
                return last
        except (URLError, OSError) as exc:
            last = (None, str(exc))
        time.sleep(1.5 * (attempt + 1))
    return last


def check_external(urls):
    urls = sorted(u for u in urls if 'mc.yandex.ru' not in u and 'schema.org' not in u)
    print(f"Проверка {len(urls)} внешних ссылок...")

    # партнёрский сайт отдаёт 502 при параллельных запросах — держим поток спокойным
    with ThreadPoolExecutor(max_workers=3) as pool:
        for url, (status, final) in zip(urls, pool.map(http_status, urls)):
            if status is None:
                warn(f"недоступна {url}: {final}")
            elif status in (301, 302, 303, 307, 308) or final.rstrip('/') != url.rstrip('/'):
                fail(f"редирект {status} на партнёрской ссылке {url} -> {final}")
            elif status >= 400:
                fail(f"HTTP {status}: {url}")


def main():
    external = check_pages()
    check_sitemap()

    if '--external' in sys.argv:
        check_external(external)
    else:
        print(f"Внешних ссылок: {len(external)} (проверка сети пропущена, "
              f"запустите с --external)")

    print()
    for w in warnings:
        print(f"  предупреждение: {w}")
    if errors:
        print(f"\nОШИБОК: {len(errors)}")
        for err in errors:
            print(f"  ✗ {err}")
        return 1
    print("Ошибок нет.")
    return 0


if __name__ == '__main__':
    sys.exit(main())
