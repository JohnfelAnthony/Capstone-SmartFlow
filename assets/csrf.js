(function () {
    function readCookie(name) {
        var cookieName = name + "=";
        var cookies = document.cookie ? document.cookie.split(";") : [];
        for (var index = 0; index < cookies.length; index += 1) {
            var cookie = cookies[index].trim();
            if (cookie.indexOf(cookieName) === 0) {
                return decodeURIComponent(cookie.substring(cookieName.length));
            }
        }
        return "";
    }

    if (typeof window.fetch !== "function") {
        return;
    }

    var originalFetch = window.fetch.bind(window);
    window.fetch = function (input, init) {
        var requestUrl = typeof input === "string" ? input : (input && input.url) || "";
        var requestInit = init || {};
        var requestPath = "";

        try {
            requestPath = new URL(requestUrl, window.location.origin).pathname;
        } catch (_error) {
            requestPath = "";
        }

        if (requestPath === "/_dash-update-component") {
            var headers = new Headers(requestInit.headers || (input && input.headers) || {});
            var csrfToken = readCookie("smartflow_csrf_token");
            if (csrfToken) {
                headers.set("X-CSRF-Token", csrfToken);
            }
            requestInit.headers = headers;
        }

        return originalFetch(input, requestInit);
    };
})();
