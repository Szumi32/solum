/* Strona koszyka. */
(function () {
  "use strict";
  var S = window.SOLUM;
  var C = S.Cart;
  var list = document.querySelector("[data-cart-lines]");
  var side = document.querySelector("[data-cart-side]");
  var empty = document.querySelector("[data-cart-empty]");
  var grid = document.querySelector("[data-cart-grid]");
  if (!list) return;
  var codeNote = "";

  function paint() {
    var lines = C.lines();
    var has = lines.length > 0;
    empty.hidden = has;
    grid.hidden = !has;
    if (!has) return;
    list.innerHTML = lines.map(function (l) { return S.lineHtml(l); }).join("");
    var code = C.code();
    var disc = C.discount();
    var cheapest = S.cfg.shipping.filter(function (m) { return m.price > 0; }).reduce(function (a, m) { return Math.min(a, C.shippingPrice(m)); }, Infinity);
    side.innerHTML =
      "<h2>Podsumowanie</h2>" +
      S.freeMeter() +
      '<div class="sum-row"><span>Wartość produktów</span><span>' + S.zl(C.subtotal()) + "</span></div>" +
      (disc ? '<div class="sum-row"><span>Kod ' + S.esc(code.toUpperCase()) + "</span><span>−" + S.zl(disc) + "</span></div>" : "") +
      '<label class="gift"><input type="checkbox" id="gift-wrap" data-gift' + (C.gift() ? " checked" : "") + "><span>" + S.esc(S.cfg.giftWrap.name) + " (" + S.zl(S.cfg.giftWrap.price) + ")</span></label>" +
      '<div class="sum-row"><span>Dostawa</span><span>' + (cheapest === 0 ? "od 0 zł" : "od " + S.zl(cheapest)) + "</span></div>" +
      '<div class="sum-row total"><span>Razem bez dostawy</span><span>' + S.zl(C.goodsValue() + C.giftPrice()) + "</span></div>" +
      '<a class="btn btn-ink btn-wide" href="zamowienie.html">Przejdź do zamówienia</a>' +
      '<form class="field" data-code-form novalidate><label for="code">Kod rabatowy</label><div class="code-row"><input id="code" type="text" value="' + S.esc(code) + '" autocomplete="off"><button class="btn" type="submit">Użyj</button></div><p class="form-note" role="status">' + S.esc(codeNote) + "</p></form>";
  }

  document.addEventListener("click", function (e) {
    if (list.contains(e.target)) S.handleLineClick(e);
  });
  side.addEventListener("change", function (e) {
    if (e.target.matches("[data-gift]")) {
      C.gift(e.target.checked);
      /* panel rysuje sie od nowa, wiec przywracamy fokus na pole */
      var again = side.querySelector("[data-gift]");
      if (again) again.focus();
    }
  });
  side.addEventListener("submit", function (e) {
    if (!e.target.matches("[data-code-form]")) return;
    e.preventDefault();
    var val = e.target.querySelector("input").value.trim();
    var hit = S.cfg.codes[val.toUpperCase()];
    if (!val) { codeNote = ""; C.code(""); return; }
    if (hit) { codeNote = "Kod aktywny: " + hit.label + "."; C.code(val); }
    else { codeNote = "Ten kod nie jest aktywny. Sprawdź pisownię."; C.code(""); }
    var codeInput = side.querySelector("#code");
    if (codeInput) codeInput.focus();
  });

  C.onChange(paint);
  paint();
})();
