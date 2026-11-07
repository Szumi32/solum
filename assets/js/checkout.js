/* Zamowienie: dane, dostawa, platnosc. W wersji demonstracyjnej platnosc jest symulowana
   i nigdzie nie sa pobierane dane karty ani kody BLIK. */
(function () {
  "use strict";
  var S = window.SOLUM;
  var C = S.Cart;
  var cfg = S.cfg;
  var form = document.querySelector("[data-checkout]");
  if (!form) return;
  var emptyBox = document.querySelector("[data-checkout-empty]");
  var grid = document.querySelector("[data-checkout-grid]");
  var sumBox = document.querySelector("[data-checkout-sum]");
  var DRAFT = "solum.szkic.v1";

  /* ---------- listy dostawy i platnosci ---------- */
  function renderOptions() {
    form.querySelector("[data-shipping-list]").innerHTML = cfg.shipping.map(function (m, i) {
      var price = C.shippingPrice(m);
      return '<label class="radio-card"><input type="radio" name="shipping" value="' + m.id + '"' + (i === 0 ? " checked" : "") + '>' +
        "<div><strong>" + S.esc(m.name) + "</strong><span>" + S.esc(m.eta) + "</span></div>" +
        '<div class="rc-price">' + (price === 0 ? "0 zł" : S.zl(price)) + "</div></label>";
    }).join("");
    form.querySelector("[data-payment-list]").innerHTML = cfg.payments.map(function (m, i) {
      return '<label class="radio-card"><input type="radio" name="payment" value="' + m.id + '"' + (i === 0 ? " checked" : "") + '>' +
        "<div><strong>" + S.esc(m.name) + "</strong><span>" + S.esc(m.note) + "</span></div><div></div></label>";
    }).join("");
  }
  function method() {
    var val = (form.querySelector('input[name="shipping"]:checked') || {}).value;
    return cfg.shipping.filter(function (m) { return m.id === val; })[0] || cfg.shipping[0];
  }
  function payment() {
    var val = (form.querySelector('input[name="payment"]:checked') || {}).value;
    return cfg.payments.filter(function (m) { return m.id === val; })[0] || cfg.payments[0];
  }

  function paintShippingFields() {
    var m = method();
    var locker = form.querySelector("[data-locker]");
    var addr = form.querySelector("[data-address]");
    var pickup = form.querySelector("[data-pickup]");
    locker.hidden = !m.locker;
    pickup.hidden = !m.pickup;
    addr.hidden = !!m.locker || !!m.pickup;
    form.querySelector("[data-locker-label]").textContent = m.lockerLabel || "Kod paczkomatu";
    var invoiceOn = form.querySelector("#invoice").checked;
    form.querySelector("[data-invoice]").hidden = !invoiceOn;
  }

  function paintSummary() {
    var m = method();
    var ship = C.shippingPrice(m);
    var disc = C.discount();
    sumBox.innerHTML =
      "<h2>Twoje zamówienie</h2>" +
      C.lines().map(function (l) { return S.lineHtml(l, true); }).join("") +
      '<div class="sum-row"><span>Wartość produktów</span><span>' + S.zl(C.subtotal()) + "</span></div>" +
      (disc ? '<div class="sum-row"><span>Kod ' + S.esc(C.code().toUpperCase()) + "</span><span>−" + S.zl(disc) + "</span></div>" : "") +
      (C.giftPrice() ? '<div class="sum-row"><span>Opakowanie na prezent</span><span>' + S.zl(C.giftPrice()) + "</span></div>" : "") +
      '<div class="sum-row"><span>Dostawa</span><span>' + (ship === 0 ? "0 zł" : S.zl(ship)) + "</span></div>" +
      '<div class="sum-row total"><span>Do zapłaty</span><span>' + S.zl(C.total(m)) + "</span></div>" +
      '<p class="form-note">Ceny zawierają VAT.</p>';
  }

  /* ---------- szkic formularza: dane zostaja po odswiezeniu (bez zgod i platnosci) ---------- */
  var DRAFT_FIELDS = ["email", "phone", "firstName", "lastName", "street", "postal", "city", "locker", "company", "nip", "note"];
  function saveDraft() {
    var d = {};
    DRAFT_FIELDS.forEach(function (k) { if (form.elements[k]) d[k] = form.elements[k].value; });
    try { sessionStorage.setItem(DRAFT, JSON.stringify(d)); } catch (e) { /* bez szkicu */ }
  }
  function loadDraft() {
    try {
      var d = JSON.parse(sessionStorage.getItem(DRAFT) || "null");
      if (d) DRAFT_FIELDS.forEach(function (k) { if (d[k] && form.elements[k]) form.elements[k].value = d[k]; });
    } catch (e) { /* bez szkicu */ }
  }

  /* ---------- walidacja ---------- */
  function nipOk(v) {
    var d = v.replace(/\D/g, "");
    if (d.length !== 10) return false;
    var w = [6, 5, 7, 2, 3, 4, 5, 6, 7];
    var sum = w.reduce(function (a, x, i) { return a + x * +d[i]; }, 0);
    return sum % 11 === +d[9];
  }
  function validators() {
    var m = method();
    var invoice = form.querySelector("#invoice").checked;
    var list = [
      ["email", function (v) { return S.EMAIL.test(v) ? "" : "Wpisz poprawny adres e-mail, na przykład ty@przyklad.pl."; }],
      ["phone", function (v) { return v.replace(/\D/g, "").length >= 9 ? "" : "Wpisz numer telefonu, przyda się kurierowi."; }],
      ["firstName", function (v) { return v ? "" : "Wpisz imię."; }],
      ["lastName", function (v) { return v ? "" : "Wpisz nazwisko."; }],
    ];
    if (m.locker) list.push(["locker", function (v) { return v.length >= 3 ? "" : "Wpisz kod punktu odbioru, na przykład KRA01M."; }]);
    if (!m.locker && !m.pickup) {
      list.push(["street", function (v) { return v ? "" : "Wpisz ulicę i numer."; }]);
      list.push(["postal", function (v) { return /^\d{2}-\d{3}$/.test(v) ? "" : "Wpisz kod w formacie 00-000."; }]);
      list.push(["city", function (v) { return v ? "" : "Wpisz miejscowość."; }]);
    }
    if (invoice) {
      list.push(["company", function (v) { return v ? "" : "Wpisz nazwę firmy."; }]);
      list.push(["nip", function (v) { return nipOk(v) ? "" : "Sprawdź NIP, powinien mieć 10 cyfr."; }]);
    }
    return list;
  }
  function validate() {
    var first = null;
    /* wyczysc pola, ktore sa teraz ukryte */
    ["street", "postal", "city", "locker", "company", "nip"].forEach(function (k) { S.setError(form.elements[k], ""); });
    validators().forEach(function (pair) {
      var input = form.elements[pair[0]];
      var msg = pair[1](input.value.trim());
      S.setError(input, msg);
      if (msg && !first) first = input;
    });
    ["terms"].forEach(function (k) {
      var input = form.elements[k];
      var msg = input.checked ? "" : "Zaakceptuj regulamin, żeby złożyć zamówienie.";
      S.setError(input, msg);
      if (msg && !first) first = input;
    });
    if (first) { first.focus(); first.scrollIntoView({ block: "center", behavior: "smooth" }); }
    return !first;
  }

  /* ---------- zamowienie ---------- */
  function orderNumber() {
    var d = new Date();
    return "SOL-" + d.getFullYear() + "-" + String(Math.floor(Math.random() * 90000) + 10000);
  }
  function buildOrder() {
    var m = method();
    var p = payment();
    var el = form.elements;
    return {
      number: orderNumber(),
      createdAt: new Date().toISOString(),
      email: el.email.value.trim(),
      phone: el.phone.value.trim(),
      name: el.firstName.value.trim() + " " + el.lastName.value.trim(),
      address: m.locker ? "Punkt odbioru: " + el.locker.value.trim().toUpperCase() : m.pickup ? "Odbiór w pracowni" : el.street.value.trim() + ", " + el.postal.value.trim() + " " + el.city.value.trim(),
      invoice: form.querySelector("#invoice").checked ? el.company.value.trim() + ", NIP " + el.nip.value.trim() : "",
      note: el.note.value.trim(),
      shippingName: m.name,
      shippingEta: m.eta,
      shippingPrice: C.shippingPrice(m),
      paymentName: p.name,
      paymentManual: !!p.manual,
      lines: C.lines(),
      subtotal: C.subtotal(),
      discount: C.discount(),
      code: C.code(),
      gift: C.giftPrice(),
      total: C.total(m),
      demo: !!cfg.demo,
    };
  }
  function finish(order, status) {
    order.status = status;
    S.store("solum.zamowienie.v1", order);
    C.clear();
    try { sessionStorage.removeItem(DRAFT); } catch (e) { /* bez szkicu */ }
    location.href = "potwierdzenie.html";
  }

  /* ---------- symulowana bramka platnosci ---------- */
  var gate;
  function openGate(order) {
    if (!gate) {
      gate = document.createElement("dialog");
      gate.className = "modal";
      gate.setAttribute("aria-label", "Płatność demonstracyjna");
      document.body.appendChild(gate);
      gate.addEventListener("close", function () { document.documentElement.style.overflow = ""; });
    }
    gate.innerHTML = '<div class="modal-in"><div class="modal-head"><h2 class="h-sub">Płatność: ' + S.esc(order.paymentName) + '</h2><button class="icon-close" type="button" data-close>Wróć</button></div>' +
      '<p class="demo-note">To symulacja bramki płatności. Nie pobieramy żadnych pieniędzy ani danych karty.</p>' +
      '<div class="sum-row total"><span>Do zapłaty</span><span>' + S.zl(order.total) + "</span></div>" +
      '<p class="form-note" data-gate-status role="status"></p>' +
      '<div class="pay-sim"><button class="btn btn-ink btn-wide" type="button" data-sim="ok">Symuluj udaną płatność</button><button class="btn btn-wide" type="button" data-sim="fail">Symuluj odrzuconą płatność</button></div></div>';
    gate.onclick = function (e) {
      if (e.target.closest("[data-close]")) { S.closeDialog(gate); return; }
      var sim = e.target.closest("[data-sim]");
      if (!sim) return;
      if (sim.dataset.sim === "ok") finish(order, "paid");
      else gate.querySelector("[data-gate-status]").textContent = "Płatność odrzucona. Twój koszyk jest bezpieczny, możesz spróbować ponownie lub wybrać inną metodę.";
    };
    S.openDialog(gate);
  }

  /* ---------- zdarzenia ---------- */
  form.addEventListener("change", function (e) {
    if (e.target.name === "shipping" || e.target.id === "invoice") paintShippingFields();
    if (e.target.name === "shipping") paintSummary();
    if (e.target.getAttribute("aria-invalid")) S.setError(e.target, "");
  });
  form.addEventListener("input", function (e) {
    saveDraft();
    if (e.target.getAttribute("aria-invalid") === "true") S.setError(e.target, "");
  });
  form.addEventListener("submit", function (e) {
    e.preventDefault();
    if (!validate()) return;
    var order = buildOrder();
    if (payment().manual) finish(order, "awaiting");
    else openGate(order);
  });

  function start() {
    var has = C.count() > 0;
    emptyBox.hidden = has;
    grid.hidden = !has;
    if (!has) return;
    renderOptions();
    loadDraft();
    paintShippingFields();
    paintSummary();
    form.querySelector("[data-demo-note]").hidden = !cfg.demo;
  }
  start();
})();

/* ---------- strona potwierdzenia ---------- */
(function () {
  "use strict";
  var S = window.SOLUM;
  var box = document.querySelector("[data-confirmation]");
  if (!box) return;
  var o = S.store("solum.zamowienie.v1");
  var none = document.querySelector("[data-confirmation-none]");
  if (!o) { none.hidden = false; return; }
  box.hidden = false;
  var paid = o.status === "paid";
  var lines = o.lines.map(function (l) { return S.lineHtml(l, true); }).join("");
  var s = S.cfg.shop;
  box.innerHTML =
    '<h1 class="h-page">Dziękujemy, ' + S.esc(o.name.split(" ")[0]) + ". Zamówienie przyjęte.</h1>" +
    '<p class="muted">Numer zamówienia: <strong class="bank">' + S.esc(o.number) + "</strong></p>" +
    (o.demo ? '<p class="demo-note">To wersja demonstracyjna sklepu. Zamówienie nie trafiło do realizacji, nie pobrano żadnej płatności i nie wysłano e-maila.</p>' : "") +
    '<div class="confirm-box"><div class="confirm-grid">' +
    "<div><h3>Płatność</h3><p>" + S.esc(o.paymentName) + (paid ? ", opłacone" : ", czekamy na wpłatę") + "</p></div>" +
    "<div><h3>Dostawa</h3><p>" + S.esc(o.shippingName) + "<br>" + S.esc(o.shippingEta) + "</p></div>" +
    "<div><h3>Adres</h3><p>" + S.esc(o.name) + "<br>" + S.esc(o.address) + "</p></div>" +
    "<div><h3>Kontakt</h3><p>" + S.esc(o.email) + "<br>" + S.esc(o.phone) + "</p></div>" +
    (o.invoice ? "<div><h3>Faktura</h3><p>" + S.esc(o.invoice) + "</p></div>" : "") +
    "</div></div>" +
    (o.paymentManual
      ? '<div class="confirm-box"><h2 class="h-sub">Dane do przelewu</h2><p class="bank">' + S.esc(s.legalName) + "<br>" + S.esc(s.bankName) + "<br>" + S.esc(s.bankAccount) + "<br>Tytuł: " + S.esc(o.number) + "<br>Kwota: " + S.zl(o.total) + "</p></div>"
      : "") +
    '<div class="confirm-box"><h2 class="h-sub">Co dalej</h2><ol class="steps"><li><h3>Potwierdzenie</h3><p>Wyślemy szczegóły na ' + S.esc(o.email) + ".</p></li><li><h3>Wykonanie</h3><p>Robimy bransoletkę ręcznie w ciągu " + S.cfg.dispatchDays + " dni roboczych.</p></li><li><h3>Nadanie</h3><p>Dostaniesz numer przesyłki, gdy paczka wyruszy.</p></li></ol></div>" +
    "<div>" + lines +
    (o.discount ? '<div class="sum-row"><span>Rabat</span><span>−' + S.zl(o.discount) + "</span></div>" : "") +
    (o.gift ? '<div class="sum-row"><span>Opakowanie na prezent</span><span>' + S.zl(o.gift) + "</span></div>" : "") +
    '<div class="sum-row"><span>Dostawa</span><span>' + (o.shippingPrice === 0 ? "0 zł" : S.zl(o.shippingPrice)) + "</span></div>" +
    '<div class="sum-row total"><span>Razem</span><span>' + S.zl(o.total) + "</span></div></div>" +
    '<div><a class="btn" href="sklep.html">Wróć do sklepu</a></div>';
})();
