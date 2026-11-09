/* Strona produktu: dodawanie do koszyka, termin nadania i podglad 3D. */
(function () {
  "use strict";
  var S = window.SOLUM;
  var root = document.querySelector("[data-product]");
  if (!root) return;
  var p = S.product(root.dataset.product);
  var form = root.querySelector("[data-buy-form]");

  function current() {
    var data = new FormData(form);
    return { variant: S.variant(p, data.get("variant")), size: data.get("size") };
  }

  /* ---------- koszyk ---------- */
  function addToCart() {
    var c = current();
    S.Cart.add(p.slug, c.variant.id, c.size, 1);
    S.openDrawer();
  }
  form.addEventListener("submit", function (e) { e.preventDefault(); addToCart(); });

  var stickyBar = document.querySelector("[data-sticky-buy]");
  var stickyAdd = document.querySelector("[data-sticky-add]");
  if (stickyBar) {
    stickyBar.hidden = false;
    stickyAdd.addEventListener("click", addToCart);
    var btn = form.querySelector("button[type=submit]");
    /* Pasek pojawia sie, gdy glowny przycisk jest juz nad krawedzia ekranu.
       Liczymy to przy przewijaniu, bo szybki skok moze ominac przycisk i nie wywolac obserwatora. */
    var ticking = false;
    var updateSticky = function () {
      ticking = false;
      stickyBar.classList.toggle("is-on", btn.getBoundingClientRect().bottom < 0);
    };
    window.addEventListener("scroll", function () {
      if (!ticking) { ticking = true; requestAnimationFrame(updateSticky); }
    }, { passive: true });
    updateSticky();
  }

  /* ---------- termin nadania: dni robocze od dzis ---------- */
  function addBusinessDays(date, n) {
    var d = new Date(date);
    while (n > 0) {
      d.setDate(d.getDate() + 1);
      if (d.getDay() !== 0 && d.getDay() !== 6) n--;
    }
    return d;
  }
  var dispatch = root.querySelector("[data-dispatch]");
  if (dispatch) {
    dispatch.textContent = addBusinessDays(new Date(), S.cfg.dispatchDays).toLocaleDateString("pl-PL", { weekday: "long", day: "numeric", month: "long" });
  }

  /* ---------- podglad 3D ---------- */
  var viewerState = { open: false, api: null };
  var viewerEl = root.querySelector("[data-viewer]");
  var viewerBtn = root.querySelector("[data-viewer-open]");

  function setViewerNote(html) {
    viewerEl.innerHTML = '<div class="viewer-load">' + html + "</div>";
  }

  function loadViewer(v) {
    var url = "assets/models/" + p.slug + "/" + v.id + ".glb";
    if (viewerState.api) {
      viewerState.api.load(url);
      return;
    }
    setViewerNote("Ładuję model 3D…");
    import("./viewer.js")
      .then(function (mod) {
        viewerEl.innerHTML = "";
        viewerState.api = mod.mountViewer(viewerEl, url, {
          onError: function () {
            setViewerNote("Nie udało się wczytać modelu 3D. Obrazy poniżej pokazują ten sam produkt.");
          },
        });
      })
      .catch(function () {
        setViewerNote("Twoja przeglądarka nie obsługuje podglądu 3D. Obrazy pokazują ten sam produkt.");
      });
  }

  viewerBtn.addEventListener("click", function () {
    viewerState.open = !viewerState.open;
    viewerEl.hidden = !viewerState.open;
    viewerBtn.textContent = viewerState.open ? "Wróć do obrazu" : "Obróć w 3D";
    if (viewerState.open) {
      if (viewerState.api) viewerState.api.resume();
      else loadViewer(current().variant);
    } else if (viewerState.api) {
      viewerState.api.pause();
    }
  });
})();
