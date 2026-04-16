// Admin CSRF helper.
//
// Wraps window.fetch so every state-changing call to /admin/* carries the
// `X-CSRF-Token` header from the `admin_csrf` cookie. Pair with the
// double-submit-cookie check in middleware/admin_middleware.py.
//
// Safe to load on any admin page; no-ops on GET/HEAD/OPTIONS and on
// cross-origin URLs.

(function () {
    if (window.__adminFetchPatched) return;
    window.__adminFetchPatched = true;

    function readCsrf() {
        var m = document.cookie.match(/(?:^|; )admin_csrf=([^;]*)/);
        return m ? decodeURIComponent(m[1]) : '';
    }

    function isAdminPath(url) {
        if (typeof url !== 'string') return false;
        if (url.startsWith('/admin')) return true;
        try {
            var u = new URL(url, window.location.origin);
            return u.origin === window.location.origin && u.pathname.startsWith('/admin');
        } catch (_e) {
            return false;
        }
    }

    var UNSAFE = { POST: 1, PUT: 1, PATCH: 1, DELETE: 1 };

    var origFetch = window.fetch.bind(window);
    window.fetch = function (input, init) {
        init = init || {};
        var url = (typeof input === 'string') ? input : (input && input.url) || '';
        var method = (init.method || (input && input.method) || 'GET').toUpperCase();

        if (UNSAFE[method] && isAdminPath(url)) {
            var headers = new Headers(init.headers || (input && input.headers) || undefined);
            if (!headers.has('X-CSRF-Token')) {
                headers.set('X-CSRF-Token', readCsrf());
            }
            init.headers = headers;
        }
        return origFetch(input, init);
    };
})();
