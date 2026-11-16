/* Contact page: stop double submissions while the form is being sent. */
(function () {
    "use strict";

    var form = document.querySelector("[data-contact-form]");
    if (!form) {
        return;
    }

    form.addEventListener("submit", function (event) {
        if (form.dataset.submitting === "true") {
            event.preventDefault();
            return;
        }
        form.dataset.submitting = "true";

        var button = form.querySelector("button[type='submit']");
        if (button) {
            button.disabled = true;
            button.setAttribute("aria-busy", "true");
            button.textContent = button.getAttribute("data-submit-text") || "Sending...";
        }
    });

    // Coming back with the browser "Back" button: make the form usable again
    window.addEventListener("pageshow", function (event) {
        if (event.persisted) {
            window.location.reload();
        }
    });
})();
