// Generator statycznych stron SOLUM.
// Uruchom: node zrodla/build.mjs   (wynik trafia do public/)
//
// Strony opisowe leza w zrodla/strony/*.html, a karty produktow powstaja z dane/products.json.
// Dzieki temu kazda strona ma pelny HTML, wlasny tytul i opis, a menu edytuje sie w jednym miejscu.
import { readFileSync, writeFileSync, readdirSync, existsSync } from "node:fs";
import { join, dirname } from "node:path";
import { createHash } from "node:crypto";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const pub = join(here, "..", "public");
const readJson = (p) => JSON.parse(readFileSync(join(here, p), "utf8"));

const config = readJson("dane/config.json");
const products = readJson("dane/products.json");
const materials = readJson("dane/materials.json");
const logo = readFileSync(join(pub, "assets/logo/solum-logo.svg"), "utf8").replace('fill="#1f1d19"', 'fill="currentColor"');

const esc = (s) => String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
const zl = (n) => `${n.toLocaleString("pl-PL").replace(/ /g, " ")} zł`;
const fromPrice = (p) => Math.min(...p.variants.map((v) => p.price + (v.priceDelta || 0)));
const hasRange = (p) => new Set(p.variants.map((v) => v.priceDelta || 0)).size > 1;
const priceLabel = (p) => (hasRange(p) ? `od ${zl(fromPrice(p))}` : zl(fromPrice(p)));

const SHOTS = ["hero", "macro", "detail", "top"];
const SHOT_ALT = { hero: "widok z boku", macro: "zbliżenie na materiał", detail: "zbliżenie na zapięcie", top: "widok z góry" };
const imgBase = (slug, vid, shot) => `assets/img/p/${slug}/${vid}-${shot}`;
const srcset = (base) => `${base}-600.webp 600w, ${base}-1200.webp 1200w`;

function productImg(p, v, shot, { sizes, cls = "", eager = false, alt } = {}) {
  const base = imgBase(p.slug, v.id, shot);
  const text = alt ?? `Bransoletka ${p.name}, ${v.label}, ${SHOT_ALT[shot]}`;
  return `<img class="${cls}" src="${base}-1200.webp" srcset="${srcset(base)}" sizes="${sizes}" width="1200" height="1500" alt="${esc(text)}"${eager ? ' fetchpriority="high"' : ' loading="lazy"'} decoding="async">`;
}

function sceneImg(name, alt, w, h, sizes, eager = false) {
  const base = `assets/img/s/${name}`;
  return `<img src="${base}-${w}.webp" srcset="${base}-${Math.round(w / 2)}.webp ${Math.round(w / 2)}w, ${base}-${w}.webp ${w}w" sizes="${sizes}" width="${w}" height="${h}" alt="${esc(alt)}"${eager ? ' fetchpriority="high"' : ' loading="lazy"'} decoding="async">`;
}

function card(p, { sizes = "(min-width: 1000px) 24vw, (min-width: 640px) 32vw, 48vw", named = true } = {}) {
  const v = p.variants[0];
  const count = p.variants.length;
  return `<article class="card" data-category="${p.category}" data-price="${fromPrice(p)}" data-order="${p.featured}" data-materials="${esc(p.variants.map((x) => x.stone || x.woodType || "").join(" "))}">
  <a href="produkt-${p.slug}.html" class="card-link">
    <div class="card-media"${named ? ` style="view-transition-name: p-${p.slug}"` : ""}>
      ${productImg(p, v, "hero", { sizes, alt: `Bransoletka ${p.name}` })}
      ${productImg(p, v, "macro", { sizes, cls: "card-alt", alt: "" })}
    </div>
    <div class="card-body">
      <h3 class="card-title">${esc(p.name)}</h3>
      <p class="card-sub">${esc(p.tagline)}</p>
      <p class="card-meta"><span class="price">${priceLabel(p)}</span><span class="card-count">${count} ${count === 1 ? "wariant" : count < 5 ? "warianty" : "wariantów"}</span></p>
    </div>
  </a>
</article>`;
}

const bySlug = (s) => products.find((p) => p.slug === s);
const cards = (slugs, opts) => slugs.map((s) => card(bySlug(s), opts)).join("\n");

// ------------------------------------------------------------------ uklad

const NAV = [
  ["sklep.html", "Sklep"],
  ["materialy.html", "Materiały"],
  ["pracownia.html", "Pracownia"],
  ["kontakt.html", "Kontakt"],
];

function header(active) {
  const links = NAV.map(([h, t]) => `<a href="${h}"${h === active ? ' aria-current="page"' : ""}>${t}</a>`).join("");
  return `<a class="skip" href="#tresc">Przejdź do treści</a>
<p class="topbar">Darmowa dostawa od ${zl(config.freeShippingFrom)} · Każdą bransoletkę robimy ręcznie i nadajemy w ${config.dispatchDays} dni robocze</p>
<header class="site-head">
  <div class="site-head-in">
    <a class="logo" href="index.html" aria-label="SOLUM, strona główna">${logo}</a>
    <nav class="nav-main" aria-label="Główna">${links}</nav>
    <div class="nav-tools">
      <a class="cart-link" href="koszyk.html" data-cart-toggle>Koszyk <span class="cart-count" data-cart-count>0</span></a>
      <button class="menu-btn" type="button" data-menu-open aria-haspopup="dialog">Menu</button>
    </div>
  </div>
</header>`;
}

function footer() {
  const s = config.shop;
  const cats = config.categories.map((c) => `<li><a href="sklep.html#${c.id}">${c.name}</a></li>`).join("");
  const pays = config.payments.map((p) => p.name).join(", ");
  return `<footer class="site-foot">
  <div class="foot-news">
    <div>
      <h2 class="h-section">Nowe partie kamieni, raz w miesiącu</h2>
      <p class="muted">Piszemy, gdy trafi do nas surowiec z nowego złoża. Bez promocji co tydzień.</p>
    </div>
    <form class="news-form" data-newsletter novalidate>
      <label for="news-email">Adres e-mail</label>
      <div class="news-row">
        <input id="news-email" name="email" type="email" autocomplete="email" placeholder="ty@przyklad.pl" required>
        <button class="btn btn-ink" type="submit">Zapisz się</button>
      </div>
      <p class="form-note" data-news-status role="status">Zapis oznacza zgodę na otrzymywanie newslettera. Możesz z niego zrezygnować w każdej chwili.</p>
    </form>
  </div>
  <div class="foot-cols">
    <div class="foot-brand">
      <a class="logo" href="index.html" aria-label="SOLUM, strona główna">${logo}</a>
      <p class="muted">Ręcznie robione bransoletki z kamienia, bursztynu, drewna, skóry, lnu i jedwabiu.</p>
    </div>
    <nav aria-label="Sklep"><h3>Sklep</h3><ul><li><a href="sklep.html">Wszystkie bransoletki</a></li>${cats}</ul></nav>
    <nav aria-label="Pomoc"><h3>Pomoc</h3><ul>
      <li><a href="dostawa.html">Dostawa i płatności</a></li>
      <li><a href="zwroty.html">Zwroty i reklamacje</a></li>
      <li><a href="rozmiary.html">Jak dobrać rozmiar</a></li>
      <li><a href="pielegnacja.html">Pielęgnacja</a></li>
      <li><a href="faq.html">Pytania i odpowiedzi</a></li>
    </ul></nav>
    <div><h3>Kontakt</h3><ul>
      <li><a href="mailto:${s.email}">${s.email}</a></li>
      <li><a href="tel:${s.phone.replace(/\s/g, "")}">${s.phone}</a></li>
      <li class="muted">${s.hours}</li>
      <li><a href="pracownia.html">O pracowni</a></li>
    </ul></div>
  </div>
  <div class="foot-legal">
    <p>© ${new Date().getFullYear()} ${s.name}. ${s.legalName}, NIP ${s.nip}</p>
    <p class="foot-pay">Płatności: ${pays}</p>
    <p><a href="regulamin.html">Regulamin</a> <a href="prywatnosc.html">Polityka prywatności</a></p>
  </div>
</footer>`;
}

// Numer wersji w adresach CSS i JS: po kazdej zmianie przegladarka klienta pobierze nowe pliki.
function assetVersion() {
  const h = createHash("sha1");
  for (const f of ["css/solum.css", "js/scroll.js", "js/solum.js", "js/shop.js", "js/product.js", "js/cart.js", "js/checkout.js", "js/data.js"]) {
    h.update(readFileSync(join(pub, "assets", f)));
  }
  return h.digest("hex").slice(0, 8);
}

function layout({ title, description, body, active = "", bodyClass = "", scripts = [], head = "" }) {
  const v = assetVersion();
  const scr = scripts.map((s) => `<script src="assets/js/${s}.js?v=${v}" defer></script>`).join("\n");
  const full = title === "SOLUM" ? "SOLUM, ręcznie robione bransoletki z naturalnych materiałów" : `${title} | SOLUM`;
  const site = config.siteUrl ? `<meta property="og:url" content="${esc(config.siteUrl)}">` : "";
  return `<!doctype html>
<html lang="pl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="claude:viewport-fit-sides" content="cover">
<title>${esc(full)}</title>
<meta name="description" content="${esc(description)}">
${config.demo && !head.includes('name="robots"') ? '<meta name="robots" content="noindex, nofollow">\n' : ""}<meta name="theme-color" content="#f2efe8">
<meta property="og:title" content="${esc(full)}">
<meta property="og:description" content="${esc(description)}">
<meta property="og:type" content="website">
<meta property="og:locale" content="pl_PL">
<meta property="og:image" content="${config.siteUrl ? config.siteUrl.replace(/\/$/, "") + "/" : ""}assets/img/s/dom-hero-1800.webp">
${site}
<link rel="icon" href="favicon.ico" sizes="any">
<link rel="icon" href="favicon.svg" type="image/svg+xml">
<link rel="apple-touch-icon" href="apple-touch-icon.png">
<link rel="manifest" href="site.webmanifest">
<link rel="preload" href="assets/fonts/instrument-sans-latin-ext-wght-normal.woff2" as="font" type="font/woff2" crossorigin>
<link rel="preload" href="assets/fonts/instrument-sans-latin-wght-normal.woff2" as="font" type="font/woff2" crossorigin>
<script src="assets/js/scroll.js?v=${v}"></script>
<link rel="stylesheet" href="assets/css/solum.css?v=${v}">
${head}
<script src="assets/js/data.js?v=${v}" defer></script>
<script src="assets/js/solum.js?v=${v}" defer></script>
${scr}
</head>
<body class="${bodyClass}">
${header(active)}
<main id="tresc">
${body}
</main>
${footer()}
</body>
</html>
`;
}

// ------------------------------------------------------------------ dane dla JS

function publicProduct(p) {
  const { variants, ...rest } = p;
  return {
    ...rest,
    variants: variants.map(({ model, ...v }) => {
      const shots = SHOTS.filter((s) => existsSync(join(pub, imgBase(p.slug, v.id, s) + "-1200.webp")));
      return { ...v, shots: shots.length ? shots : SHOTS };
    }),
  };
}

writeFileSync(
  join(pub, "assets/js/data.js"),
  `window.SOLUM_DATA=${JSON.stringify({ config, materials, products: products.map(publicProduct) })};\n`,
);

// ------------------------------------------------------------------ produkt

function materialBlocks(p) {
  const blocks = [];
  const seen = new Set();
  const add = (m) => {
    if (m && !seen.has(m.name)) {
      seen.add(m.name);
      blocks.push(m);
    }
  };
  for (const v of p.variants) {
    const stone = v.stone || p.stone;
    if (stone) add(materials.stones[stone]);
    const wood = v.woodType;
    if (wood) add(materials.woods[wood]);
  }
  if (p.category === "skora") add(materials.fibers.skora);
  const opisy = JSON.stringify(p.materials).toLowerCase();
  if (/\blen\b|lniana|lnian/.test(opisy) && p.category !== "skora") add(materials.fibers.len);
  if (opisy.includes("jedwab")) add(materials.fibers.jedwab);
  return blocks;
}

function mohsScale(m) {
  const pct = ((m.mohs - 1) / 9) * 100;
  return `<div class="mohs" role="img" aria-label="Twardość ${String(m.mohs).replace(".", ",")} w skali Mohsa od 1 do 10">
    <div class="mohs-bar"><span style="left:${pct}%"></span></div>
    <div class="mohs-ticks"><span>1</span><span>Skala Mohsa</span><span>10</span></div>
  </div>`;
}

function productPage(p) {
  const v0 = p.variants[0];
  const sizeList = config.sizes[p.sizes === "bangle" ? "bangle" : "adjustable"];
  const defaultSize = sizeList[1];
  const variantInputs = p.variants
    .map((v, i) => {
      const price = p.price + (v.priceDelta || 0);
      const swatch = v.swatchText
        ? `<span class="swatch swatch-text">${esc(v.swatchText)}</span>`
        : `<span class="swatch"><img src="assets/img/p/${p.slug}/${v.id}-swatch.webp" width="96" height="96" alt="" loading="lazy"></span>`;
      return `<label class="variant-opt">
        <input type="radio" name="variant" value="${v.id}" data-price="${price}"${i === 0 ? " checked" : ""}>
        ${swatch}<span class="variant-name">${esc(v.label)}</span>
      </label>`;
    })
    .join("\n");
  const sizeInputs = sizeList
    .map(
      (s) => `<label class="size-opt" title="${esc(s.note)}">
        <input type="radio" name="size" value="${s.id}"${s.id === defaultSize.id ? " checked" : ""}>
        <span>${esc(s.label)}</span>
      </label>`,
    )
    .join("\n");
  const gallery = SHOTS.map((shot, i) => {
    const sizes = i === 0 ? "(min-width: 1000px) 60vw, 100vw" : "(min-width: 1000px) 30vw, 100vw";
    const body = productImg(p, v0, shot, { sizes, eager: i === 0 });
    return `<figure class="shot shot-${shot}" data-shot="${shot}"${i === 0 ? ` style="view-transition-name: p-${p.slug}"` : ""}>${body}${
      i === 0
        ? `<div class="viewer" data-viewer hidden></div>
           <button class="btn btn-float" type="button" data-viewer-open>Obróć w 3D</button>`
        : ""
    }</figure>`;
  }).join("\n");
  const blocks = materialBlocks(p);
  const materialHtml = blocks
    .map(
      (m) => `<div class="mat-card">
        <h3>${esc(m.name)}</h3>
        <p class="muted">${esc(m.origin)}</p>
        <p>${esc(m.text)}</p>
        ${m.mohs ? mohsScale(m) + `<p class="form-note">${esc(m.mohsNote)}</p>` : ""}
      </div>`,
    )
    .join("\n");
  const rows = p.materials.map(([a, b]) => `<tr><th scope="row">${esc(a)}</th><td>${esc(b)}</td></tr>`).join("");
  const related = products
    .filter((x) => x.slug !== p.slug)
    .sort((a, b) => (b.category === p.category) - (a.category === p.category) || a.featured - b.featured)
    .slice(0, 4);
  const s = config.shop;
  const ld = {
    "@context": "https://schema.org",
    "@type": "Product",
    name: p.name,
    description: p.lead,
    brand: { "@type": "Brand", name: "SOLUM" },
    image: `assets/img/p/${p.slug}/${v0.id}-hero-1200.webp`,
    offers: {
      "@type": "AggregateOffer",
      priceCurrency: "PLN",
      lowPrice: fromPrice(p),
      highPrice: Math.max(...p.variants.map((v) => p.price + (v.priceDelta || 0))),
      availability: "https://schema.org/InStock",
    },
  };
  const body = `<div class="wrap pdp" data-product="${p.slug}">
  <nav class="crumbs" aria-label="Okruszki"><a href="index.html">SOLUM</a> <span>/</span> <a href="sklep.html#${p.category}">${esc(config.categories.find((c) => c.id === p.category).name)}</a> <span>/</span> <span aria-current="page">${esc(p.name)}</span></nav>
  <div class="pdp-grid">
    <div class="gallery" data-gallery>
      ${gallery}
    </div>
    <div class="buy">
      <div class="buy-in">
        <h1 class="h-page">${esc(p.name)}</h1>
        <p class="buy-tag">${esc(p.tagline)}</p>
        <p class="buy-price"><span data-price>${zl(p.price + (v0.priceDelta || 0))}</span> <span class="muted buy-vat">z VAT</span></p>
        <p class="buy-lead">${esc(p.lead)}</p>
        <form data-buy-form>
          <fieldset class="opt">
            <legend>${esc(p.variantLabel)}: <strong data-variant-label>${esc(v0.label)}</strong></legend>
            <div class="variant-list">${variantInputs}</div>
          </fieldset>
          <fieldset class="opt">
            <legend>Rozmiar: <strong data-size-note>${esc(defaultSize.note)}</strong></legend>
            <div class="size-list">${sizeInputs}</div>
            <button class="link-btn" type="button" data-size-guide>Jak zmierzyć rękę?</button>
          </fieldset>
          <button class="btn btn-ink btn-wide" type="submit">Dodaj do koszyka</button>
        </form>
        <ul class="buy-notes">
          <li>Nadamy do <strong data-dispatch></strong>. Robimy ją ręcznie po złożeniu zamówienia.</li>
          <li>Dostawa od 11 zł, darmowa od ${zl(config.freeShippingFrom)}.</li>
          <li>${config.returnDays} dni na zwrot i ${config.repairYears} lata bezpłatnych napraw zapięcia.</li>
        </ul>
        <div class="acc">
          <details open><summary>Z czego jest zrobiona</summary><table class="spec"><tbody>${rows}<tr><th scope="row">Waga</th><td>${esc(p.weight)}</td></tr></tbody></table></details>
          <details><summary>Pielęgnacja</summary><p>Zdejmuj bransoletkę do kąpieli, sprzątania i ćwiczeń. Przecieraj suchą, miękką ściereczką i przechowuj osobno. Więcej w <a href="pielegnacja.html">poradniku pielęgnacji</a>.</p></details>
          <details><summary>Dostawa i zwroty</summary><p>Wysyłamy InPostem, Orlen Paczką i DPD. Możesz też odebrać zamówienie w pracowni. Szczegóły znajdziesz na stronach <a href="dostawa.html">dostawa i płatności</a> oraz <a href="zwroty.html">zwroty i reklamacje</a>.</p></details>
          <details><summary>Dane producenta</summary><p>${esc(s.legalName)}, ${esc(s.address)}, ${esc(s.city)}. Kontakt: <a href="mailto:${s.email}">${s.email}</a>.</p></details>
        </div>
      </div>
    </div>
  </div>
  <section class="pdp-story">
    <h2 class="h-section">O tej bransoletce</h2>
    <div class="story-cols">${p.story.map((t) => `<p>${esc(t)}</p>`).join("")}</div>
  </section>
  <section class="pdp-mats">
    <h2 class="h-section">Karta materiału</h2>
    <div class="mat-grid">${materialHtml || `<div class="mat-card"><h3>Len i jedwab</h3><p>${esc(materials.fibers.len.text)}</p></div>`}</div>
  </section>
  <section class="pdp-related">
    <div class="sec-head"><h2 class="h-section">Może Ci się spodobać</h2><a class="link-arrow" href="sklep.html">Wszystkie bransoletki</a></div>
    <div class="grid-cards">${related.map((r) => card(r, { named: false })).join("\n")}</div>
  </section>
</div>
<div class="sticky-buy" data-sticky-buy hidden>
  <div><strong>${esc(p.name)}</strong><span data-sticky-price>${zl(p.price + (v0.priceDelta || 0))}</span></div>
  <button class="btn btn-ink" type="button" data-sticky-add>Dodaj do koszyka</button>
</div>
<script type="application/ld+json">${JSON.stringify(ld)}</script>`;
  return layout({
    title: `${p.name}: ${p.tagline}`,
    description: p.lead,
    body,
    active: "sklep.html",
    bodyClass: "page-product",
    scripts: ["product"],
  });
}

for (const p of products) writeFileSync(join(pub, `produkt-${p.slug}.html`), productPage(p));

// ------------------------------------------------------------------ strony opisowe

const s = config.shop;
const tokens = {
  "shop.name": s.name,
  "shop.legalName": s.legalName,
  "shop.address": s.address,
  "shop.city": s.city,
  "shop.nip": s.nip,
  "shop.regon": s.regon,
  "shop.email": s.email,
  "shop.phone": s.phone,
  "shop.phoneHref": s.phone.replace(/\s/g, ""),
  "shop.hours": s.hours,
  "shop.bankName": s.bankName,
  "shop.bankAccount": s.bankAccount,
  freeFrom: zl(config.freeShippingFrom),
  dispatchDays: config.dispatchDays,
  returnDays: config.returnDays,
  repairYears: config.repairYears,
  year: new Date().getFullYear(),
};

const shippingRows = config.shipping
  .map(
    (m) => `<tr><th scope="row">${esc(m.name)}</th><td>${m.price === 0 ? "bezpłatnie" : zl(m.price)}</td><td>${esc(m.eta)}</td><td>${m.free ? `darmowa od ${zl(config.freeShippingFrom)}` : "bez progu"}</td></tr>`,
  )
  .join("");
const paymentRows = config.payments.map((m) => `<li><strong>${esc(m.name)}</strong><span class="muted">${esc(m.note)}</span></li>`).join("");

const allCards = [...products].sort((a, b) => a.featured - b.featured).map((p) => card(p)).join("\n");
const filterChips = [`<button type="button" class="chip" data-filter="" aria-pressed="true">Wszystkie</button>`]
  .concat(config.categories.map((c) => `<button type="button" class="chip" data-filter="${c.id}" aria-pressed="false">${c.name}</button>`))
  .join("");

const fragments = {
  "cards:home-a": cards(["lawica", "okruch", "rzemien", "zrab"]),
  "cards:home-b": cards(["pasmo", "sloje", "osnowa", "watek"], { named: true }),
  "cards:all": allCards,
  "filters": filterChips,
  "table:shipping": `<div class="table-wrap"><table class="table"><thead><tr><th scope="col">Sposób dostawy</th><th scope="col">Koszt</th><th scope="col">Czas</th><th scope="col">Próg darmowej dostawy</th></tr></thead><tbody>${shippingRows}</tbody></table></div>`,
  "list:payments": `<ul class="pay-list">${paymentRows}</ul>`,
  "img:dom-hero": sceneImg("dom-hero", "Trzy bransoletki SOLUM na jasnym kamieniu: bursztynowa, z krzemienia pasiastego i ze skóry", 1800, 1400, "(min-width: 900px) 58vw, 100vw", true),
  "img:kamien": sceneImg("kamien", "Rozsypane koraliki z lapisu, krzemienia, nefrytu i amazonitu", 1100, 1375, "(min-width: 900px) 24vw, 48vw"),
  "img:bursztyn": sceneImg("bursztyn", "Okruchy bursztynu w kolorze koniaku, miodu i mleka", 1100, 1375, "(min-width: 900px) 24vw, 48vw"),
  "img:drewno": sceneImg("drewno", "Toczone koraliki z dębu bagiennego, oliwki i orzecha", 1100, 1375, "(min-width: 900px) 24vw, 48vw"),
  "img:skora": sceneImg("skora", "Pas ze skóry garbowanej roślinnie, skórzana plecionka i cewka lnu", 1100, 1375, "(min-width: 900px) 24vw, 48vw"),
  "img:pracownia": sceneImg("pracownia", "Bransoletka w trakcie nawlekania: cewka lnu, nić z koralikami z krzemienia i rozsypane kamienie", 1800, 1100, "100vw"),
  "img:zapiecie": productImg(bySlug("lawica"), bySlug("lawica").variants[0], "detail", { sizes: "(min-width: 900px) 40vw, 100vw", alt: "Przesuwny węzeł z jedwabnej nici w bransoletce Ławica" }),
  "img:kolek": productImg(bySlug("rzemien"), bySlug("rzemien").variants[0], "detail", { sizes: "(min-width: 900px) 40vw, 100vw", alt: "Kołek z drewna oliwnego i lniane szwy w bransoletce Rzemień" }),
};

function stoneCards() {
  const m = materials;
  const stone = Object.values(m.stones)
    .map(
      (x) => `<article class="mat-card"><h3>${esc(x.name)}</h3><p class="muted">${esc(x.origin)}</p><p>${esc(x.text)}</p>${mohsScale(x)}<p class="form-note">${esc(x.mohsNote)}</p></article>`,
    )
    .join("");
  const list = (o) => Object.values(o).map((x) => `<article class="mat-card"><h3>${esc(x.name)}</h3><p class="muted">${esc(x.origin)}</p><p>${esc(x.text)}</p></article>`).join("");
  return { stone, wood: list(m.woods), fiber: list(m.fibers) };
}
const sc = stoneCards();
fragments["mat:stones"] = sc.stone;
fragments["mat:woods"] = sc.wood;
fragments["mat:fibers"] = sc.fiber;

function render(text) {
  return text
    .replace(/\{\{([\w.:-]+)\}\}/g, (m, k) => {
      if (k in tokens) return esc(tokens[k]);
      if (k in fragments) return fragments[k];
      throw new Error(`Nieznany znacznik ${m}`);
    });
}

for (const file of readdirSync(join(here, "strony"))) {
  if (!file.endsWith(".html")) continue;
  const raw = readFileSync(join(here, "strony", file), "utf8");
  const match = raw.match(/^<!--META([\s\S]*?)-->\s*/);
  if (!match) throw new Error(`Brak META w ${file}`);
  const meta = JSON.parse(match[1]);
  const body = render(raw.slice(match[0].length));
  writeFileSync(join(pub, file), layout({ ...meta, body }));
}

const base = config.siteUrl.replace(/\/$/, "");
const hiddenPages = new Set(["koszyk.html", "zamowienie.html", "potwierdzenie.html", "404.html"]);
const pageList = readdirSync(pub).filter((f) => f.endsWith(".html") && !hiddenPages.has(f));
// W trybie demo cala strona jest ukryta przed wyszukiwarkami: to makieta z danymi zastepczymi.
const robots = config.demo
  ? "User-agent: *\nDisallow: /\n"
  : `User-agent: *\nAllow: /\nDisallow: /koszyk.html\nDisallow: /zamowienie.html\nDisallow: /potwierdzenie.html\n${base ? `Sitemap: ${base}/sitemap.xml\n` : ""}`;
writeFileSync(join(pub, "robots.txt"), robots);
if (base && !config.demo) {
  const urls = pageList.map((f) => `  <url><loc>${base}/${f === "index.html" ? "" : f}</loc></url>`).join("\n");
  writeFileSync(join(pub, "sitemap.xml"), `<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n${urls}\n</urlset>\n`);
}

console.log(`Gotowe: ${products.length} produktów, strony w public/`);
