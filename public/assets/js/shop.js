/* Katalog: filtr po materiale zapisany w adresie (#kamien) i sortowanie. */
(function () {
  "use strict";
  var grid = document.querySelector("[data-catalog]");
  if (!grid) return;
  var chips = Array.prototype.slice.call(document.querySelectorAll("[data-filter]"));
  var sortSel = document.querySelector("[data-sort]");
  var note = document.querySelector("[data-result-note]");
  var cards = Array.prototype.slice.call(grid.querySelectorAll(".card"));

  function odmiana(n) {
    if (n === 1) return "bransoletka";
    var d = n % 10, t = n % 100;
    return d >= 2 && d <= 4 && (t < 12 || t > 14) ? "bransoletki" : "bransoletek";
  }

  function apply() {
    var f = decodeURIComponent(location.hash.slice(1));
    if (!chips.some(function (c) { return c.dataset.filter === f; })) f = "";
    chips.forEach(function (c) { c.setAttribute("aria-pressed", String(c.dataset.filter === f)); });
    var shown = 0;
    cards.forEach(function (card) {
      var on = !f || card.dataset.category === f;
      card.classList.toggle("is-out", !on);
      if (on) shown++;
    });
    if (note) note.textContent = shown + " " + odmiana(shown);
  }

  function sort() {
    var how = sortSel ? sortSel.value : "";
    var sorted = cards.slice().sort(function (a, b) {
      if (how === "asc") return a.dataset.price - b.dataset.price;
      if (how === "desc") return b.dataset.price - a.dataset.price;
      return a.dataset.order - b.dataset.order;
    });
    sorted.forEach(function (c) { grid.appendChild(c); });
  }

  chips.forEach(function (c) {
    c.addEventListener("click", function () {
      var f = c.dataset.filter;
      /* pushState nie wywoluje popstate, wiec sam wybor filtra nie przewija strony. Dziala tylko cofanie. */
      try {
        history.pushState(null, "", f ? "#" + f : location.pathname + location.search);
      } catch (e) {
        location.hash = f;
      }
      apply();
    });
  });
  if (sortSel) sortSel.addEventListener("change", sort);
  window.addEventListener("hashchange", apply);
  apply();
})();
