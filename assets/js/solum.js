/* SOLUM: koszyk, panele i formularze wspolne dla wszystkich stron. */
(function () {
  "use strict";
  var D = window.SOLUM_DATA;
  var cfg = D.config;
  var KEY = "solum.koszyk.v1";

  function store(k, v) {
    try {
      if (v === undefined) return JSON.parse(localStorage.getItem(k) || "null");
      if (v === null) localStorage.removeItem(k);
      else localStorage.setItem(k, JSON.stringify(v));
    } catch (e) {
      /* tryb prywatny lub zablokowane dane: koszyk dziala do przeladowania strony */
    }
    return null;
  }

  function zl(n) {
    var abs = Math.round(n * 100) / 100;
    var txt = abs.toLocaleString("pl-PL", { minimumFractionDigits: abs % 1 ? 2 : 0, maximumFractionDigits: 2 });
    return txt + " zł";
  }

  function esc(s) {
    return String(s).replace(/[&<>"]/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c];
    });
  }

  function product(slug) {
    return D.products.filter(function (p) { return p.slug === slug; })[0];
  }
  function variant(p, id) {
    return p.variants.filter(function (v) { return v.id === id; })[0] || p.variants[0];
  }
  function sizeInfo(p, id) {
    var list = cfg.sizes[p.sizes === "bangle" ? "bangle" : "adjustable"];
    return list.filter(function (s) { return s.id === id; })[0] || list[0];
  }
  function unitPrice(p, v) {
    return p.price + (v.priceDelta || 0);
  }

  /* ---------- stan koszyka ---------- */
  var memory = store(KEY) || { items: [], gift: false, code: "" };
  if (!Array.isArray(memory.items)) memory = { items: [], gift: false, code: "" };
  memory.items = memory.items.filter(function (i) { return product(i.slug); });

  var listeners = [];
  function changed() {
    store(KEY, memory);
    paintCount();
    paintDrawer();
    listeners.forEach(function (fn) { fn(); });
  }

  var Cart = {
    items: function () { return memory.items; },
    onChange: function (fn) { listeners.push(fn); },
    add: function (slug, vid, size, qty) {
      var hit = memory.items.filter(function (i) { return i.slug === slug && i.variant === vid && i.size === size; })[0];
      if (hit) hit.qty = Math.min(hit.qty + (qty || 1), 9);
      else memory.items.push({ slug: slug, variant: vid, size: size, qty: qty || 1 });
      changed();
      bump();
    },
    setQty: function (index, qty) {
      if (!memory.items[index]) return;
      if (qty <= 0) memory.items.splice(index, 1);
      else memory.items[index].qty = Math.min(qty, 9);
      changed();
    },
    remove: function (index) { memory.items.splice(index, 1); changed(); },
    clear: function () { memory = { items: [], gift: false, code: "" }; changed(); },
    gift: function (v) { if (v !== undefined) { memory.gift = !!v; changed(); } return memory.gift; },
    code: function (v) { if (v !== undefined) { memory.code = v; changed(); } return memory.code; },
    count: function () { return memory.items.reduce(function (a, i) { return a + i.qty; }, 0); },
    lines: function () {
      return memory.items.map(function (i, index) {
        var p = product(i.slug);
        var v = variant(p, i.variant);
        var s = sizeInfo(p, i.size);
        var price = unitPrice(p, v);
        return {
          index: index, slug: p.slug, name: p.name, variantLabel: v.label, sizeLabel: s.label, qty: i.qty, price: price,
          total: price * i.qty, image: "assets/img/p/" + p.slug + "/" + v.id + "-hero-600.webp", url: "produkt-" + p.slug + ".html",
        };
      });
    },
    subtotal: function () { return Cart.lines().reduce(function (a, l) { return a + l.total; }, 0); },
    discount: function () {
      var c = cfg.codes[(memory.code || "").toUpperCase()];
      return c ? Math.round(Cart.subtotal() * c.percent) / 100 : 0;
    },
    giftPrice: function () { return memory.gift && Cart.count() ? cfg.giftWrap.price : 0; },
    /* Prog darmowej dostawy liczymy od wartosci towarow po rabacie */
    goodsValue: function () { return Cart.subtotal() - Cart.discount(); },
    shippingPrice: function (method) {
      if (!method) return null;
      if (method.free && Cart.goodsValue() >= cfg.freeShippingFrom) return 0;
      return method.price;
    },
    total: function (method) {
      var ship = method ? Cart.shippingPrice(method) : 0;
      return Cart.goodsValue() + Cart.giftPrice() + (ship || 0);
    },
  };

  /* ---------- naglowek i podsumowanie ---------- */
  function paintCount() {
    var n = Cart.count();
    document.querySelectorAll("[data-cart-count]").forEach(function (el) {
      el.textContent = n;
      if (n) el.setAttribute("data-filled", "");
      else el.removeAttribute("data-filled");
    });
  }
  function bump() {
    document.querySelectorAll("[data-cart-count]").forEach(function (el) {
      el.classList.add("bump");
      setTimeout(function () { el.classList.remove("bump"); }, 260);
    });
  }

  function lineHtml(l, compact) {
    var ctrl = compact
      ? '<span class="line-meta">Ilość: ' + l.qty + "</span>"
      : '<div class="line-ctrl"><div class="qty" role="group" aria-label="Ilość: ' + esc(l.name) + '">' +
        '<button type="button" data-qty="' + (l.qty - 1) + '" data-i="' + l.index + '" aria-label="Mniej">−</button>' +
        "<span>" + l.qty + "</span>" +
        '<button type="button" data-qty="' + (l.qty + 1) + '" data-i="' + l.index + '" aria-label="Więcej"' + (l.qty >= 9 ? " disabled" : "") + ">+</button></div>" +
        '<button type="button" class="line-remove" data-remove="' + l.index + '">Usuń</button></div>';
    return '<div class="line"><a href="' + l.url + '"><img src="' + l.image + '" alt="" width="600" height="750" loading="lazy"></a>' +
      '<div class="line-info"><a class="line-name" href="' + l.url + '">' + esc(l.name) + "</a>" +
      '<span class="line-meta">' + esc(l.variantLabel) + ", rozmiar " + esc(l.sizeLabel) + "</span>" + ctrl + "</div>" +
      '<div class="line-price">' + zl(l.total) + "</div></div>";
  }

  function freeMeter() {
    var left = cfg.freeShippingFrom - Cart.goodsValue();
    var pct = Math.min(100, (Cart.goodsValue() / cfg.freeShippingFrom) * 100);
    var msg = left > 0 ? "Do darmowej dostawy brakuje " + zl(left) : "Masz darmową dostawę";
    return '<div class="free-meter"><span>' + msg + '</span><div class="free-meter-bar"><span style="width:' + pct + '%"></span></div></div>';
  }

  /* ---------- panel koszyka ---------- */
  var drawer;
  function buildDrawer() {
    drawer = document.createElement("dialog");
    drawer.className = "drawer";
    drawer.setAttribute("aria-label", "Koszyk");
    drawer.innerHTML = '<div class="drawer-in"><div class="drawer-head"><h2>Koszyk</h2><button class="icon-close" type="button" data-drawer-close>Zamknij</button></div><div class="drawer-body" data-drawer-body></div><div class="drawer-foot" data-drawer-foot></div></div>';
    document.body.appendChild(drawer);
    drawer.addEventListener("click", function (e) {
      if (e.target === drawer || e.target.closest("[data-drawer-close]")) closeDialog(drawer);
      handleLineClick(e);
    });
    drawer.addEventListener("cancel", function (e) { e.preventDefault(); closeDialog(drawer); });
  }
  function paintDrawer() {
    if (!drawer) return;
    var body = drawer.querySelector("[data-drawer-body]");
    var foot = drawer.querySelector("[data-drawer-foot]");
    var lines = Cart.lines();
    if (!lines.length) {
      body.innerHTML = '<div class="empty"><p>Twój koszyk jest pusty.</p><a class="btn" href="sklep.html">Zobacz bransoletki</a></div>';
      foot.hidden = true;
      return;
    }
    foot.hidden = false;
    body.innerHTML = lines.map(function (l) { return lineHtml(l); }).join("");
    foot.innerHTML = freeMeter() +
      '<div class="sum-row total"><span>Razem bez dostawy</span><span>' + zl(Cart.goodsValue()) + "</span></div>" +
      '<a class="btn btn-ink btn-wide" href="zamowienie.html">Przejdź do zamówienia</a><a class="btn btn-wide" href="koszyk.html">Zobacz koszyk</a>';
  }
  function handleLineClick(e) {
    var q = e.target.closest("[data-qty]");
    if (q) { Cart.setQty(+q.dataset.i, +q.dataset.qty); return; }
    var r = e.target.closest("[data-remove]");
    if (r) Cart.remove(+r.dataset.remove);
  }

  function openDialog(d) {
    d.classList.remove("is-closing");
    if (!d.open) d.showModal();
    document.documentElement.style.overflow = "hidden";
  }
  function closeDialog(d) {
    if (!d.open) return;
    var done = function () {
      d.classList.remove("is-closing");
      d.close();
      document.documentElement.style.overflow = "";
    };
    if (d.classList.contains("drawer") && !window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      d.classList.add("is-closing");
      setTimeout(done, 200);
    } else done();
  }

  /* ---------- menu telefonu ---------- */
  function buildMenu() {
    var d = document.createElement("dialog");
    d.className = "menu-panel";
    d.setAttribute("aria-label", "Menu");
    var links = Array.prototype.map.call(document.querySelectorAll(".nav-main a"), function (a) {
      return '<a href="' + a.getAttribute("href") + '">' + a.textContent + "</a>";
    }).join("");
    d.innerHTML = '<div class="drawer-head"><h2>Menu</h2><button class="icon-close" type="button" data-close>Zamknij</button></div>' +
      '<nav class="menu-links">' + links + '<a href="koszyk.html">Koszyk</a></nav>' +
      '<div class="menu-small"><a href="dostawa.html">Dostawa i płatności</a><a href="zwroty.html">Zwroty i reklamacje</a><a href="rozmiary.html">Jak dobrać rozmiar</a></div>';
    document.body.appendChild(d);
    d.addEventListener("click", function (e) { if (e.target.closest("[data-close]")) closeDialog(d); });
    document.querySelectorAll("[data-menu-open]").forEach(function (b) {
      b.addEventListener("click", function () { openDialog(d); });
    });
    d.addEventListener("close", function () { document.documentElement.style.overflow = ""; });
  }

  /* ---------- komunikaty ---------- */
  var toastEl;
  function toast(msg) {
    if (!toastEl) {
      toastEl = document.createElement("div");
      toastEl.className = "toast";
      toastEl.setAttribute("role", "status");
      document.body.appendChild(toastEl);
    }
    toastEl.textContent = msg;
    toastEl.classList.add("is-on");
    clearTimeout(toastEl._t);
    toastEl._t = setTimeout(function () { toastEl.classList.remove("is-on"); }, 3200);
  }

  /* ---------- walidacja wspolna ---------- */
  var EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/;
  function setError(input, msg) {
    var field = input.closest(".field") || input.parentElement;
    var err = field.querySelector(".field-err");
    if (msg) {
      field.classList.add("has-err");
      input.setAttribute("aria-invalid", "true");
      if (!err) {
        err = document.createElement("p");
        err.className = "field-err";
        err.id = input.id + "-err";
        field.appendChild(err);
        input.setAttribute("aria-describedby", err.id);
      }
      err.textContent = msg;
    } else {
      field.classList.remove("has-err");
      input.removeAttribute("aria-invalid");
      input.removeAttribute("aria-describedby");
      if (err) err.remove();
    }
  }

  /* ---------- newsletter i kontakt ---------- */
  function bindForms() {
    document.querySelectorAll("[data-newsletter]").forEach(function (form) {
      form.addEventListener("submit", function (e) {
        e.preventDefault();
        var input = form.querySelector("input[type=email]");
        var status = form.querySelector("[data-news-status]");
        if (!EMAIL.test(input.value.trim())) {
          status.textContent = "Wpisz poprawny adres e-mail, na przykład ty@przyklad.pl.";
          input.focus();
          return;
        }
        status.textContent = cfg.demo
          ? "To wersja demonstracyjna, więc adres nie został nigdzie zapisany."
          : "Dziękujemy. Sprawdź skrzynkę, żeby potwierdzić zapis.";
        form.reset();
      });
    });

    var contact = document.querySelector("[data-contact-form]");
    if (contact) {
      contact.addEventListener("submit", function (e) {
        e.preventDefault();
        var ok = true;
        contact.querySelectorAll("[required]").forEach(function (input) {
          var msg = "";
          if (input.type === "checkbox") {
            msg = input.checked ? "" : "Zaznacz zgodę, żebyśmy mogli odpowiedzieć.";
          } else if (!input.value.trim()) {
            msg = "To pole jest wymagane.";
          } else if (input.type === "email" && !EMAIL.test(input.value.trim())) {
            msg = "Wpisz poprawny adres e-mail.";
          }
          setError(input, msg);
          if (msg && ok) { input.focus(); ok = false; }
        });
        if (!ok) return;
        var status = contact.querySelector("[data-contact-status]");
        status.hidden = false;
        status.textContent = cfg.demo
          ? "Formularz działa poprawnie, ale to wersja demonstracyjna, więc wiadomość nie została wysłana. Napisz bezpośrednio na " + cfg.shop.email + "."
          : "Dziękujemy. Odpowiemy w ciągu jednego dnia roboczego.";
        contact.reset();
      });
    }

    /* Dobor rozmiaru */
    document.querySelectorAll("[data-size-calc]").forEach(bindSizeCalc);
  }

  function bindSizeCalc(root) {
    var input = root.querySelector("input");
    var out = root.querySelector("[data-calc-out]");
    var list = cfg.sizes[root.getAttribute("data-size-calc") || "adjustable"];
    function run() {
      var v = parseFloat(String(input.value).replace(",", "."));
      if (!v) { out.textContent = "Wpisz obwód w centymetrach."; return; }
      var hit = list.filter(function (s) { return v >= s.min && v < s.max; })[0];
      if (!hit && v === list[list.length - 1].max) hit = list[list.length - 1];
      if (hit) {
        out.innerHTML = "Polecamy rozmiar <strong>" + esc(hit.label) + "</strong> (" + esc(hit.note) + ").";
      } else {
        out.textContent = "Ten obwód wykracza poza standardowe rozmiary. Napisz do nas, a zrobimy bransoletkę na miarę.";
      }
    }
    input.addEventListener("input", run);
  }

  /* ---------- start ---------- */
  function init() {
    buildDrawer();
    buildMenu();
    paintCount();
    paintDrawer();
    bindForms();
    document.querySelectorAll("[data-cart-toggle]").forEach(function (a) {
      a.addEventListener("click", function (e) {
        if (document.body.classList.contains("page-cart") || document.body.classList.contains("page-checkout")) return;
        e.preventDefault();
        openDialog(drawer);
      });
    });
    window.addEventListener("pageshow", function (e) {
      if (e.persisted) {
        memory = store(KEY) || memory;
        paintCount();
        paintDrawer();
      }
    });
  }

  window.SOLUM = {
    data: D, cfg: cfg, Cart: Cart, zl: zl, esc: esc, product: product, variant: variant, sizeInfo: sizeInfo, unitPrice: unitPrice,
    toast: toast, setError: setError, EMAIL: EMAIL, store: store, openDialog: openDialog, closeDialog: closeDialog,
    openDrawer: function () { openDialog(drawer); }, lineHtml: lineHtml, handleLineClick: handleLineClick, freeMeter: freeMeter,
    bindSizeCalc: bindSizeCalc,
  };

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
})();
