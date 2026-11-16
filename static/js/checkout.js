/* Checkout: keep the currency radio, prices and add-on list in sync. */
(function () {
    "use strict";

    var scope = document.querySelector(".checkout-page.currency-scope");
    if (!scope) {
        return;
    }

    function sync(currency) {
        // Radio follows the chosen currency (also when services.js restored it from the session)
        var radio = scope.querySelector("input[name='currency'][value='" + currency + "']");
        if (!radio) {
            // This package has no price in that currency: stay on the one that is selected
            radio = scope.querySelector("input[name='currency']:checked");
            if (!radio) {
                return;
            }
            currency = radio.value;
            scope.setAttribute("data-currency", currency);
        }
        radio.checked = true;

        // Only the add-ons priced in this currency can be picked
        scope.querySelectorAll("[data-addon-currency]").forEach(function (group) {
            var active = group.getAttribute("data-addon-currency") === currency;
            group.hidden = !active;
            group.querySelectorAll("input[type='checkbox']").forEach(function (box) {
                box.disabled = !active;
                if (!active) {
                    box.checked = false;
                }
            });
        });
    }

    scope.addEventListener("change", function (event) {
        if (event.target.name === "currency") {
            sync(event.target.value);
        }
    });

    // services.js may have switched the currency on load; follow it once it has run
    window.addEventListener("load", function () {
        sync(scope.getAttribute("data-currency"));
    });
    sync(scope.getAttribute("data-currency"));
})();
