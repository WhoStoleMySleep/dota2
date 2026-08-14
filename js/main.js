/**
 * Kraeved.ru — поиск, навигация, ускорение переходов.
 *
 * Принципы:
 *   - индекс поиска (search-index.json) грузится только когда пользователь
 *     тянется к поиску, а не на каждой странице;
 *   - соседние страницы префетчатся при наведении, чтобы переход был мгновенным;
 *   - счётчик подключается после того, как страница отрисована.
 */

(function () {
    'use strict';

    // ------------------------------------------------------------ мобильное меню

    function initNavToggle() {
        var toggle = document.querySelector('.nav-toggle');
        var nav = document.querySelector('.nav');
        if (!toggle || !nav) return;

        toggle.addEventListener('click', function () {
            nav.classList.toggle('active');
            this.setAttribute('aria-expanded', nav.classList.contains('active'));
        });
    }

    // ------------------------------------------------------------------- поиск

    var regionsData = null;
    var loadingIndex = null;

    function loadIndex() {
        if (regionsData) return Promise.resolve(regionsData);
        if (loadingIndex) return loadingIndex;

        loadingIndex = fetch('/data/search-index.json')
            .then(function (r) { return r.ok ? r.json() : []; })
            .then(function (data) { regionsData = data; return data; })
            .catch(function () { regionsData = []; return []; });

        return loadingIndex;
    }

    function searchRegions(query) {
        if (!regionsData) return [];
        var q = query.toLowerCase();
        var results = [];
        for (var i = 0; i < regionsData.length && results.length < 10; i++) {
            var r = regionsData[i];
            if ((r.n + ' ' + r.c + ' ' + r.t).toLowerCase().indexOf(q) !== -1) {
                results.push(r);
            }
        }
        return results;
    }

    function renderResults(results, container) {
        if (!results.length) {
            container.innerHTML =
                '<div class="search-no-results">Ничего не найдено</div>';
            container.classList.add('active');
            return;
        }

        var html = '';
        for (var i = 0; i < results.length; i++) {
            var r = results[i];
            html += '<a href="/regions/' + r.s + '/">' +
                    '<strong>' + r.n + '</strong>' +
                    '<span class="region-type">' + r.t + ' • ' + r.c + '</span></a>';
        }
        container.innerHTML = html;
        container.classList.add('active');
    }

    function initSearch() {
        var inputs = document.querySelectorAll('.search-input');

        Array.prototype.forEach.call(inputs, function (input) {
            var box = input.closest('.search-box');
            var results = box && box.querySelector('.search-results');
            if (!results) return;

            // индекс подтягиваем при первом же интересе к поиску
            var warm = function () { loadIndex(); };
            input.addEventListener('focus', warm, { once: true });
            input.addEventListener('pointerenter', warm, { once: true });

            var timer;
            input.addEventListener('input', function () {
                var value = this.value.trim();
                clearTimeout(timer);

                if (value.length < 2) {
                    results.classList.remove('active');
                    return;
                }

                timer = setTimeout(function () {
                    loadIndex().then(function () {
                        renderResults(searchRegions(value), results);
                    });
                }, 150);
            });

            input.addEventListener('focus', function () {
                if (this.value.trim().length >= 2) results.classList.add('active');
            });
        });

        document.addEventListener('click', function (e) {
            if (e.target.closest('.search-box')) return;
            var open = document.querySelectorAll('.search-results.active');
            Array.prototype.forEach.call(open, function (el) {
                el.classList.remove('active');
            });
        });
    }

    // ------------------------------------------------- мгновенные переходы

    // Chrome и Edge умеют Speculation Rules — там разметка в <head> уже всё делает.
    // Для остальных браузеров подкладываем страницу при наведении.
    function initPrefetch() {
        if (HTMLScriptElement.supports &&
            HTMLScriptElement.supports('speculationrules')) return;

        var link = document.createElement('link');
        if (!('relList' in link) || !link.relList.supports('prefetch')) return;

        var conn = navigator.connection;
        if (conn && (conn.saveData || /2g/.test(conn.effectiveType || ''))) return;

        var done = {};
        var timer;

        function prefetch(href) {
            if (done[href]) return;
            done[href] = true;
            var el = document.createElement('link');
            el.rel = 'prefetch';
            el.href = href;
            document.head.appendChild(el);
        }

        function onEnter(e) {
            var a = e.target.closest && e.target.closest('a[href^="/"]');
            if (!a || a.target === '_blank' || a.hasAttribute('download')) return;
            var href = a.getAttribute('href');
            if (href.indexOf('#') === 0) return;

            clearTimeout(timer);
            timer = setTimeout(function () { prefetch(a.href); }, 60);
        }

        document.addEventListener('pointerenter', onEnter, true);
        document.addEventListener('pointerleave', function () {
            clearTimeout(timer);
        }, true);
        document.addEventListener('touchstart', onEnter, { capture: true, passive: true });
    }

    // ------------------------------------------------------- отложенный счётчик

    // Метрика тяжелее самого сайта, поэтому подключаем её после отрисовки:
    // по первому взаимодействию или через 2.5 с — что случится раньше.
    function initMetrika() {
        var cfg = window.__metrika;
        if (!cfg || !cfg.id) return;

        var started = false;
        var events = ['pointerdown', 'keydown', 'scroll', 'touchstart'];

        function start() {
            if (started) return;
            started = true;
            events.forEach(function (name) {
                window.removeEventListener(name, start, { passive: true });
            });

            (function (m, e, t, r, i, k, a) {
                m[i] = m[i] || function () { (m[i].a = m[i].a || []).push(arguments); };
                m[i].l = 1 * new Date();
                k = e.createElement(t); a = e.getElementsByTagName(t)[0];
                k.async = 1; k.src = r; a.parentNode.insertBefore(k, a);
            })(window, document, 'script', 'https://mc.yandex.ru/metrika/tag.js?id=' + cfg.id, 'ym');

            window.ym(cfg.id, 'init', cfg.params);
        }

        events.forEach(function (name) {
            window.addEventListener(name, start, { passive: true, once: true });
        });
        setTimeout(start, 2500);
    }

    // --------------------------------------------------------------- запуск

    function init() {
        initNavToggle();
        initSearch();
        initPrefetch();
        initMetrika();
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
