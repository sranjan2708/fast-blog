/* =========================================================
   FAST BLOG - GLOBAL JAVASCRIPT
   Phase 16: Frontend & Responsive UI
   ========================================================= */


/* =========================================================
   MOBILE NAVIGATION
   ========================================================= */

document.addEventListener("DOMContentLoaded", function () {

    const navbarToggle = document.querySelector(".navbar-toggle");
    const navbarLinks = document.querySelector(".navbar-links");

    if (navbarToggle && navbarLinks) {

        navbarToggle.addEventListener("click", function () {

            navbarLinks.classList.toggle("active");

        });

    }


    /* =====================================================
       DELETE / CONFIRMATION FORMS
       ===================================================== */

    const confirmationForms =
        document.querySelectorAll("[data-confirm]");

    confirmationForms.forEach(function (form) {

        form.addEventListener("submit", function (event) {

            const message =
                form.getAttribute("data-confirm");

            if (message) {

                const confirmed =
                    window.confirm(message);

                if (!confirmed) {
                    event.preventDefault();
                }

            }

        });

    });


    /* =====================================================
       AUTO DISMISS MESSAGES
       ===================================================== */

    const messages =
        document.querySelectorAll(".message[data-auto-dismiss]");

    messages.forEach(function (message) {

        setTimeout(function () {

            message.style.opacity = "0";

            setTimeout(function () {
                message.remove();
            }, 300);

        }, 5000);

    });

});