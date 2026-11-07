/* Strona produktu: warianty, rozmiary, dodawanie do koszyka, podglad 3D. */
(function () {
  "use strict";
  var S = window.SOLUM;
  var root = document.querySelector("[data-product]");
  if (!root) return;
  var p = S.product(root.dataset.product);
  var form = root.querySelector("[data-buy-form]");
  var gallery = root.querySelector("[data-gallery]");
  var sizeList = S.cfg.sizes[p.sizes === "bangle" ? "bangle" : "adjustable"];
  var viewerState = { open: false, api: null };

  function current() {
    var data = new FormData(form);
    return { variant: S.variant(p, data.get("variant")), size: data.get("size") };
  }

  /* ---------- zdjecia wariantu ---------- */
  function paintGallery(v) {
    gallery.querySelectorAll(".shot").forEach(function (fig) {
      var shot = fig.dataset.shot;
      var has = v.shots.indexOf(shot) !== -1;
      fig.hidden = !has;
      if (!has) return;
      var img = fig.querySelector("img");
      var base = "assets/img/p/" + p.slug + "/" + v.id + "-" + shot;
      var next = new Image();
      fig.classList.add("is-swapping");
      next.onload = function () {
        img.srcset = base + "-600.webp 600w, " + base + "-1200.webp 1200w";
        img.src = base + "-1200.webp";
        img.alt = "Bransoletka " + p.name + ", " + v.label;
        fig.classList.remove("is-swapping");
      };
      next.onerror = function () { fig.classList.remove("is-swapping"); };
      next.src = base + "-1200.webp";
    });
  }

  function paintPrice(v) {
    var txt = S.zl(S.unitPrice(p, v));
    root.querySelector("[data-price]").textContent = txt;
    var sticky = document.querySelector("[data-sticky-price]");
    if (sticky) sticky.textContent = txt;
  }

  function onVariant() {
    var v = current().variant;
    root.querySelector("[data-variant-label]").textContent = v.label;
    paintPrice(v);
    paintGallery(v);
    if (viewerState.open) loadViewer(v);
    try { history.replaceState(null, "", "#" + v.id); } catch (e) { /* adres bez kotwicy */ }
  }

  function onSize() {
    var c = current();
    var s = sizeList.filter(function (x) { return x.id === c.size; })[0];
    root.querySelector("[data-size-note]").textContent = s ? s.note : "";
  }

  form.addEventListener("change", function (e) {
    if (e.target.name === "variant") onVariant();
    if (e.target.name === "size") onSize();
  });

  /* Wariant z adresu, np. #obsydian */
  var fromHash = location.hash.slice(1);
  if (fromHash) {
    var inp = form.querySelector('input[name="variant"][value="' + CSS.escape(fromHash) + '"]');
    if (inp && !inp.checked) { inp.checked = true; onVariant(); }
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

  /* ---------- tabela rozmiarow ---------- */
  var guide;
  function openGuide() {
    if (!guide) {
      guide = document.createElement("dialog");
      guide.className = "modal";
      guide.setAttribute("aria-label", "Jak zmierzyć rękę");
      var bangle = p.sizes === "bangle";
      var rows = sizeList.map(function (s) { return "<tr><th scope=\"row\">" + S.esc(s.label) + "</th><td>" + S.esc(s.note) + "</td></tr>"; }).join("");
      guide.innerHTML = '<div class="modal-in"><div class="modal-head"><h2 class="h-sub">Jak zmierzyć rękę</h2><button class="icon-close" type="button" data-close>Zamknij</button></div>' +
        (bangle
          ? "<p>Obręcz zakłada się przez dłoń. Złącz kciuk z małym palcem, tak jak przy wkładaniu bransolety, i zmierz centymetrem najszerszy obwód dłoni.</p>"
          : "<p>Owiń centymetr krawiecki wokół nadgarstka, tuż nad kością. Jeśli nie masz centymetra, użyj paska papieru i zmierz go linijką. Przesuwny węzeł pozwala później dopasować obwód o około 2 cm.</p>") +
        '<div class="calc" data-size-calc="' + (bangle ? "bangle" : "adjustable") + '"><div class="field"><label for="calc-cm">' + (bangle ? "Obwód dłoni" : "Obwód nadgarstka") + ' w cm</label><input id="calc-cm" type="text" inputmode="decimal" placeholder="np. 17"></div><p class="calc-out" data-calc-out role="status">Wpisz obwód w centymetrach.</p></div>' +
        '<table class="spec"><tbody>' + rows + "</tbody></table>" +
        '<p class="form-note">Potrzebujesz innego rozmiaru? <a href="kontakt.html">Napisz do nas</a>, a zrobimy bransoletkę na miarę.</p></div>';
      document.body.appendChild(guide);
      guide.addEventListener("click", function (e) {
        if (e.target === guide || e.target.closest("[data-close]")) S.closeDialog(guide);
      });
      guide.addEventListener("close", function () { document.documentElement.style.overflow = ""; });
      S.bindSizeCalc(guide.querySelector("[data-size-calc]"));
    }
    S.openDialog(guide);
  }
  root.querySelector("[data-size-guide]").addEventListener("click", openGuide);

  /* ---------- podglad 3D ---------- */
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
            setViewerNote("Nie udało się wczytać modelu 3D. Zdjęcia poniżej pokazują tę samą bransoletkę.");
          },
        });
      })
      .catch(function () {
        setViewerNote("Twoja przeglądarka nie obsługuje podglądu 3D. Zdjęcia pokazują tę samą bransoletkę.");
      });
  }

  viewerBtn.addEventListener("click", function () {
    viewerState.open = !viewerState.open;
    viewerEl.hidden = !viewerState.open;
    viewerBtn.textContent = viewerState.open ? "Wróć do zdjęcia" : "Obróć w 3D";
    if (viewerState.open) loadViewer(current().variant);
    else if (viewerState.api) viewerState.api.pause();
    if (viewerState.open && viewerState.api) viewerState.api.resume();
  });

  onSize();
})();
