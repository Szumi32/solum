/* Plynne przewijanie na gore strony: po cofnieciu i po wejsciu na karte produktu.
   Skrypt laduje sie w <head> bez defer, bo musi ustawic pozycje przed pierwszym wyswietleniem strony. */
(function () {
  "use strict";

  var ENTRY_OFFSET = 96; /* o ile pikseli nizej zaczyna sie karta produktu */
  var BACK_MIN = 96; /* najmniejszy przejazd po cofnieciu */
  var BACK_MAX = 520; /* najwiekszy przejazd po cofnieciu, zeby ruch pozostal spokojny */
  var KEY = "solum.pozycja.";

  try {
    history.scrollRestoration = "manual";
  } catch (e) {
    /* starsza przegladarka: zostaje jej domyslne zachowanie */
  }

  var root = document.documentElement;
  var reduced = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  var raf = 0;
  var run = 0;
  var interrupts = ["wheel", "touchstart", "keydown", "pointerdown"];

  function saved() {
    try {
      return parseInt(sessionStorage.getItem(KEY + location.pathname), 10) || 0;
    } catch (e) {
      return 0;
    }
  }
  window.addEventListener("pagehide", function () {
    try {
      sessionStorage.setItem(KEY + location.pathname, String(Math.round(window.scrollY)));
    } catch (e) {
      /* bez pamieci pozycji */
    }
  });

  function stop() {
    run++;
    if (raf) cancelAnimationFrame(raf);
    raf = 0;
    root.style.scrollBehavior = "";
    interrupts.forEach(function (type) {
      window.removeEventListener(type, stop);
    });
  }

  function ease(t) {
    return t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;
  }

  /* Styl strony ma scroll-behavior: smooth, wiec na czas ruchu wylaczamy go i liczymy kazda klatke sami */
  function moveTo(y) {
    root.style.scrollBehavior = "auto";
    window.scrollTo(0, y);
  }

  function glide(from, transition) {
    stop();
    if (reduced) {
      moveTo(0);
      root.style.scrollBehavior = "";
      return;
    }
    if (from !== null) moveTo(from);
    var current = ++run;
    interrupts.forEach(function (type) {
      window.addEventListener(type, stop, { passive: true });
    });
    function begin() {
      if (current !== run) return;
      var start = window.scrollY;
      if (start < 1) {
        stop();
        return;
      }
      var duration = 620 + Math.min(start, BACK_MAX) * 0.55;
      var t0 = null;
      function frame(now) {
        if (current !== run) return;
        if (t0 === null) t0 = now;
        var k = Math.min(1, (now - t0) / duration);
        moveTo(start * (1 - ease(k)));
        if (k < 1) raf = requestAnimationFrame(frame);
        else stop();
      }
      raf = requestAnimationFrame(frame);
    }
    /* Ruszamy po przejsciu miedzy stronami, inaczej zdjecie produktu przeskoczyloby na koncu animacji */
    if (transition && transition.finished) transition.finished.then(begin, begin);
    else begin();
  }

  function backOffset(y) {
    return Math.max(BACK_MIN, Math.min(y, BACK_MAX));
  }

  function hasAnchorTarget() {
    var id = location.hash.slice(1);
    if (!id) return false;
    try {
      return !!document.getElementById(decodeURIComponent(id));
    } catch (e) {
      return false;
    }
  }

  function onFirstShow(transition) {
    var entries = performance.getEntriesByType ? performance.getEntriesByType("navigation") : [];
    var type = entries[0] ? entries[0].type : "navigate";
    if (type === "reload") {
      moveTo(saved());
      root.style.scrollBehavior = "";
    } else if (type === "back_forward") {
      if (!hasAnchorTarget()) glide(backOffset(saved()), transition);
    } else if (document.body && document.body.classList.contains("page-product") && !hasAnchorTarget()) {
      glide(ENTRY_OFFSET, transition);
    }
  }

  var supportsReveal = "onpagereveal" in window;
  var shown = false;
  var restored = false;

  window.addEventListener("pagereveal", function (e) {
    if (!shown) {
      shown = true;
      onFirstShow(e.viewTransition);
    } else if (restored) {
      restored = false;
      glide(backOffset(window.scrollY), e.viewTransition);
    }
  });

  /* Powrot z pamieci podrecznej przegladarki: strona wraca dokladnie tam, gdzie ja zostawiono */
  window.addEventListener("pageshow", function (e) {
    if (!e.persisted) return;
    restored = true;
    setTimeout(function () {
      if (restored) {
        restored = false;
        glide(backOffset(window.scrollY), null);
      }
    }, supportsReveal ? 150 : 0);
  });

  if (!supportsReveal) {
    document.addEventListener("DOMContentLoaded", function () {
      if (!shown) {
        shown = true;
        onFirstShow(null);
      }
    });
  }

  /* Cofanie w obrebie tej samej strony, np. miedzy filtrami w sklepie */
  window.addEventListener("popstate", function () {
    glide(null, null);
  });
})();
