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

})(jQuery);
