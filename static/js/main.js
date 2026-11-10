(function ($) {
    "use strict";

    // Hide the loading spinner once the page is ready
    $(function () {
        $('#spinner').removeClass('show');
    });


    // Scroll animations
    new WOW().init();


    // Sticky navbar + back-to-top button
    var $window = $(window);
    var $navbar = $('.navbar');
    var $backToTop = $('.back-to-top');

    function onScroll() {
        var top = $window.scrollTop();
        $navbar.toggleClass('position-fixed bg-dark shadow-sm', top > 0);
        if (top > 300) {
            $backToTop.fadeIn('slow');
        } else {
            $backToTop.fadeOut('slow');
        }
    }
    $window.on('scroll', onScroll);
    onScroll();

    $backToTop.on('click', function () {
        $('html, body').animate({scrollTop: 0}, 1500, 'easeInOutExpo');
        return false;
    });


    // Close the mobile menu after clicking a link
    $('.navbar-nav .nav-link').on('click', function () {
        var menu = document.getElementById('navbarCollapse');
        if (menu && menu.classList.contains('show')) {
            (bootstrap.Collapse.getInstance(menu) || new bootstrap.Collapse(menu, {toggle: false})).hide();
        }
    });


    // Flash messages fade out after 5 seconds
    setTimeout(function () {
        $('.site-messages .alert').each(function () {
            (bootstrap.Alert.getInstance(this) || new bootstrap.Alert(this)).close();
        });
    }, 5000);


    // Testimonials carousel (loop only when there is more than one item)
    var $testimonials = $('.testimonial-carousel');
    if ($testimonials.length) {
        var multiple = $testimonials.children().length > 1;
        $testimonials.owlCarousel({
            autoplay: multiple,
            smartSpeed: 1000,
            loop: multiple,
            nav: false,
            dots: true,
            items: 1,
            dotsData: true,
        });
    }


    // Developer portfolio: client reviews carousel
    var $reviews = $('.review-carousel');
    if ($reviews.length) {
        var manyReviews = $reviews.children().length > 1;
        $reviews.owlCarousel({
            autoplay: manyReviews,
            smartSpeed: 1000,
            loop: manyReviews,
            nav: false,
            dots: manyReviews,
            items: 1,
        });
    }


    // Home stats: numbers count up when they scroll into view
    var counters = document.querySelectorAll('.counter');
    function runCounter(el) {
        var target = parseInt(el.getAttribute('data-target'), 10) || 0;
        var start = null;
        var duration = 1500;
        function step(time) {
            if (!start) { start = time; }
            var progress = Math.min((time - start) / duration, 1);
            el.textContent = Math.floor(progress * target);
            if (progress < 1) {
                requestAnimationFrame(step);
            } else {
                el.textContent = target;
            }
        }
        requestAnimationFrame(step);
    }
    if (counters.length && 'IntersectionObserver' in window) {
        var counterObserver = new IntersectionObserver(function (entries) {
            entries.forEach(function (entry) {
                if (entry.isIntersecting) {
                    runCounter(entry.target);
                    counterObserver.unobserve(entry.target);
                }
            });
        }, {threshold: 0.5});
        counters.forEach(function (el) { counterObserver.observe(el); });
    }


    // Developer portfolio: skill bars fill up when they scroll into view
    var skillBlocks = document.querySelectorAll('.progress-skills');
    if (skillBlocks.length) {
        if ('IntersectionObserver' in window) {
            var observer = new IntersectionObserver(function (entries) {
                entries.forEach(function (entry) {
                    if (entry.isIntersecting) {
                        entry.target.classList.add('is-visible');
                        observer.unobserve(entry.target);
                    }
                });
            }, {threshold: 0.3});
            skillBlocks.forEach(function (el) { observer.observe(el); });
        } else {
            skillBlocks.forEach(function (el) { el.classList.add('is-visible'); });
        }
    }

})(jQuery);
