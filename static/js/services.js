/* Service & pricing pages: BDT / USD currency switch.
   - Updates every price and WhatsApp link without reloading the page.
   - Remembers the choice for this browser tab (sessionStorage). */
(function () {
    "use strict";

    var STORAGE_KEY = "osa-currency";
    var CURRENCIES = ["bdt", "usd"];

    function saved() {
        try {
            var value = window.sessionStorage.getItem(STORAGE_KEY);
            return CURRENCIES.indexOf(value) !== -1 ? value : null;
        } catch (e) {
            return null;
        }
    }

    function remember(currency) {
        try {
            window.sessionStorage.setItem(STORAGE_KEY, currency);
        } catch (e) { /* storage blocked: the switch still works for this page */ }
    }

    function apply(currency) {
        document.querySelectorAll(".currency-scope").forEach(function (scope) {
            scope.setAttribute("data-currency", currency);
        });

        document.querySelectorAll("[data-set-currency]").forEach(function (button) {
            button.setAttribute("aria-pressed", button.getAttribute("data-set-currency") === currency ? "true" : "false");
        });

        // WhatsApp message must mention the price in the chosen currency
        document.querySelectorAll(".js-whatsapp-link").forEach(function (link) {
            var href = link.getAttribute("data-href-" + currency);
            if (href) {
                link.setAttribute("href", href);
            }
        });
    }

    document.addEventListener("click", function (event) {
        var button = event.target.closest("[data-set-currency]");
        if (!button) {
            return;
        }
        var currency = button.getAttribute("data-set-currency");
        apply(currency);
        remember(currency);
    });

    var initial = saved();
    if (initial) {
        apply(initial);
    }
})();
