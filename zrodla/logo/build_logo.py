"""Generator logo SOLUM. Wszystkie litery powstaja z geometrii (luki, proste), bez fontow.

Uzycie: python build_logo.py <folder_wyjsciowy>
"""
import math
import sys
from pathlib import Path

H = 100.0      # wysokosc wersalik
OS = 1.6       # overshoot ksztaltow okraglych
W = 10.0       # grubosc kreski: litery jak nic, O jak kamien


def f(v):
    s = f"{v:.2f}".rstrip("0").rstrip(".")
    return "0" if s == "-0" else s


def letter_s(x, w=W):
    """S z dwoch lukow stycznych w srodku. Dolny brzuszek lekko wiekszy (korekta optyczna)."""
    y0 = -OS + w / 2
    y1 = H + OS - w / 2
    total = y1 - y0
    r1 = total / 2 * 0.475
    r2 = total / 2 - r1
    width = 2 * r2 + w
    cx = x + width / 2
    c1 = (cx, y0 + r1)
    c2 = (cx, y1 - r2)
    a = math.radians(24)
    b = math.radians(24)
    r1o, r1i = r1 + w / 2, r1 - w / 2
    r2o, r2i = r2 + w / 2, r2 - w / 2
    p1 = (c1[0] + r1o * math.cos(a), c1[1] - r1o * math.sin(a))
    join_low = (cx, c1[1] + r1o)
    t_in = (c2[0] - r2i * math.cos(b), c2[1] + r2i * math.sin(b))
    t_out = (c2[0] - r2o * math.cos(b), c2[1] + r2o * math.sin(b))
    join_up = (cx, c2[1] - r2o)
    p2 = (c1[0] + r1i * math.cos(a), c1[1] - r1i * math.sin(a))
    d = (
        f"M{f(p1[0])} {f(p1[1])}"
        f"A{f(r1o)} {f(r1o)} 0 1 0 {f(join_low[0])} {f(join_low[1])}"
        f"A{f(r2i)} {f(r2i)} 0 1 1 {f(t_in[0])} {f(t_in[1])}"
        f"L{f(t_out[0])} {f(t_out[1])}"
        f"A{f(r2o)} {f(r2o)} 0 1 0 {f(join_up[0])} {f(join_up[1])}"
        f"A{f(r1i)} {f(r1i)} 0 1 1 {f(p2[0])} {f(p2[1])}Z"
    )
    return d, x + width


def letter_l(x, w=W):
    foot = 54.0
    d = (
        f"M{f(x)} 0H{f(x + w)}V{f(H - w * 0.94)}H{f(x + foot)}V{f(H)}H{f(x)}Z"
    )
    return d, x + foot


def letter_u(x, w=W):
    width = 74.0
    R = width / 2
    r = R - w
    cy = H + OS - R
    d = (
        f"M{f(x)} 0H{f(x + w)}V{f(cy)}"
        f"A{f(r)} {f(r)} 0 0 0 {f(x + width - w)} {f(cy)}"
        f"V0H{f(x + width)}V{f(cy)}"
        f"A{f(R)} {f(R)} 0 0 1 {f(x)} {f(cy)}Z"
    )
    return d, x + width


def letter_m(x, w=W):
    width = 98.0
    x1 = x + width
    xm = x + width / 2
    a = w * 1.08              # szerokosc gornego ramienia
    b = w * 0.42              # polowa plaskiego dna wierzcholka
    T = w * 1.06              # grubosc pozioma przekatnej
    D = xm - x - a
    v = H * (T - b) / (D + T - b)
    s = (H - v) / D
    yl = H - s * (xm - b - x - w)
    pts = [
        (x, H), (x, 0), (x + a, 0), (xm, H - v), (x1 - a, 0), (x1, 0), (x1, H),
        (x1 - w, H), (x1 - w, yl), (xm + b, H), (xm - b, H), (x + w, yl), (x + w, H),
    ]
    d = "M" + "L".join(f"{f(p[0])} {f(p[1])}" for p in pts) + "Z"
    return d, x1


def disc(cx, cy, r):
    return (
        f"M{f(cx - r)} {f(cy)}"
        f"A{f(r)} {f(r)} 0 1 1 {f(cx + r)} {f(cy)}"
        f"A{f(r)} {f(r)} 0 1 1 {f(cx - r)} {f(cy)}Z"
    )


def ring(cx, cy, R, r):
    return disc(cx, cy, R) + disc(cx, cy, r)


def strata_disc(cx, cy, r, layers, gap, tilt_deg):
    """Dysk pociety na warstwy. layers = udzialy wysokosci od gory do dolu."""
    t = math.radians(tilt_deg)
    cos_t, sin_t = math.cos(t), math.sin(t)

    def rot(px, py):
        return (cx + px * cos_t - py * sin_t, cy + px * sin_t + py * cos_t)

    total = sum(layers)
    usable = 2 * r - gap * (len(layers) - 1)
    y = -r
    out = []
    for i, share in enumerate(layers):
        h = usable * share / total
        top, bottom = y, y + h
        x_top = math.sqrt(max(r * r - top * top, 0))
        x_bot = math.sqrt(max(r * r - bottom * bottom, 0))
        a1 = rot(-x_top, top)
        a2 = rot(x_top, top)
        a3 = rot(x_bot, bottom)
        a4 = rot(-x_bot, bottom)
        parts = [f"M{f(a1[0])} {f(a1[1])}"]
        if i > 0:
            parts.append(f"L{f(a2[0])} {f(a2[1])}")
        else:
            a2 = rot(0, -r)
            parts = [f"M{f(a2[0])} {f(a2[1])}"]
        # prawa krawedz wzdluz okregu
        large = 0
        parts.append(f"A{f(r)} {f(r)} 0 {large} 1 {f(a3[0])} {f(a3[1])}")
        if i < len(layers) - 1:
            parts.append(f"L{f(a4[0])} {f(a4[1])}")
        else:
            a3b = rot(0, r)
            parts.append(f"A{f(r)} {f(r)} 0 0 1 {f(a3b[0])} {f(a3b[1])}")
            parts.append(f"A{f(r)} {f(r)} 0 0 1 {f(a4[0])} {f(a4[1])}")
        if i > 0:
            parts.append(f"A{f(r)} {f(r)} 0 0 1 {f(a1[0])} {f(a1[1])}")
        else:
            parts.append(f"A{f(r)} {f(r)} 0 0 1 {f(a2[0])} {f(a2[1])}")
        parts.append("Z")
        out.append("".join(parts))
        y = bottom + gap
    return "".join(out)


def curved_strata(cx, cy, r, layers, gap, rc):
    """Dysk pociety lukami o promieniu rc, jak pasma w krzemieniu."""
    total = sum(layers)
    usable = 2 * r - gap * (len(layers) - 1)
    bounds = []
    y = -r
    for share in layers[:-1]:
        y += usable * share / total
        bounds.append((y, y + gap))
        y += gap

    def hit(yb):
        c = yb - rc
        py = (r * r - rc * rc + c * c) / (2 * c)
        return math.sqrt(max(r * r - py * py, 0)), py

    def P(px, py):
        return f"{f(cx + px)} {f(cy + py)}"

    out = []
    n = len(layers)
    for i in range(n):
        if i == 0:
            xb, yb = hit(bounds[0][0])
            large = 1 if yb > 0 else 0
            out.append(f"M{P(-xb, yb)}A{f(r)} {f(r)} 0 {large} 1 {P(xb, yb)}A{f(rc)} {f(rc)} 0 0 1 {P(-xb, yb)}Z")
        elif i == n - 1:
            xt, yt = hit(bounds[-1][1])
            large = 1 if yt < 0 else 0
            out.append(f"M{P(-xt, yt)}A{f(rc)} {f(rc)} 0 0 0 {P(xt, yt)}A{f(r)} {f(r)} 0 {large} 1 {P(-xt, yt)}Z")
        else:
            xt, yt = hit(bounds[i - 1][1])
            xb, yb = hit(bounds[i][0])
            out.append(
                f"M{P(-xt, yt)}A{f(rc)} {f(rc)} 0 0 0 {P(xt, yt)}A{f(r)} {f(r)} 0 0 1 {P(xb, yb)}"
                f"A{f(rc)} {f(rc)} 0 0 1 {P(-xb, yb)}A{f(r)} {f(r)} 0 0 1 {P(-xt, yt)}Z"
            )
    return "".join(out)


def svg(paths, vb, fill="#000", evenodd=False, title="SOLUM"):
    rule = ' fill-rule="evenodd"' if evenodd else ""
    x, y, w, h = vb
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{f(x)} {f(y)} {f(w)} {f(h)}" role="img" '
        f'aria-label="{title}"><title>{title}</title><path fill="{fill}"{rule} d="{paths}"/></svg>\n'
    )


def wordmark(o_builder, track=14.0, w=W):
    x = 0.0
    parts = []
    d, x = letter_s(x, w)
    parts.append(d)
    x += track + 2
    d, x = o_builder(x)
    parts.append(d)
    x += track + 2
    d, x = letter_l(x, w)
    parts.append(d)
    x += track - 6        # L ma otwarta prawa strone
    d, x = letter_u(x, w)
    parts.append(d)
    x += track + 3
    d, x = letter_m(x, w)
    parts.append(d)
    return "".join(parts), x


def square_vb(w_extent, pad=0.0):
    return (-pad, 50 - w_extent / 2 - pad, w_extent + 2 * pad, w_extent + 2 * pad)


def lower_um(x, xh=64.0, w=W):
    """Male u i m jedna linia: prawy trzon u jest lewym trzonem m."""
    ru = 21.0
    R = ru
    r = ru - w
    y0 = 100 - xh
    cy = 100 + OS - R
    a = x + 2 * R
    d = (
        f"M{f(x)} {f(y0)}H{f(x + w)}V{f(cy)}"
        f"A{f(r)} {f(r)} 0 0 0 {f(x + w + 2 * r)} {f(cy)}V{f(y0)}H{f(a)}V100H{f(a - w)}"
        f"V{f(cy + R - w * 0.2)}A{f(R)} {f(R)} 0 0 1 {f(x)} {f(cy)}Z"
    )
    # dwa luki m nad wspolnym trzonem
    ar = 19.5
    ca = y0 - OS + ar
    b = a - w
    x2 = b + 2 * ar
    x3 = x2 - w + 2 * ar
    d += (
        f"M{f(b)} {f(ca)}A{f(ar)} {f(ar)} 0 0 1 {f(x2)} {f(ca)}V100H{f(x2 - w)}V{f(ca)}"
        f"A{f(ar - w)} {f(ar - w)} 0 0 0 {f(b + w)} {f(ca)}Z"
        f"M{f(x2 - w)} {f(ca)}A{f(ar)} {f(ar)} 0 0 1 {f(x3)} {f(ca)}V100H{f(x3 - w)}V{f(ca)}"
        f"A{f(ar - w)} {f(ar - w)} 0 0 0 {f(x2)} {f(ca)}Z"
    )
    return d, x3


def lower_s(x, xh=64.0, w=W):
    y0 = 100 - xh - OS + w / 2
    y1 = 100 + OS - w / 2
    total = y1 - y0
    r1 = total / 2 * 0.48
    r2 = total / 2 - r1
    width = 2 * r2 + w
    cx = x + width / 2
    c1 = (cx, y0 + r1)
    c2 = (cx, y1 - r2)
    a = math.radians(20)
    r1o, r1i, r2o, r2i = r1 + w / 2, r1 - w / 2, r2 + w / 2, r2 - w / 2
    p1 = (c1[0] + r1o * math.cos(a), c1[1] - r1o * math.sin(a))
    jl = (cx, c1[1] + r1o)
    ti = (c2[0] - r2i * math.cos(a), c2[1] + r2i * math.sin(a))
    to = (c2[0] - r2o * math.cos(a), c2[1] + r2o * math.sin(a))
    ju = (cx, c2[1] - r2o)
    p2 = (c1[0] + r1i * math.cos(a), c1[1] - r1i * math.sin(a))
    d = (
        f"M{f(p1[0])} {f(p1[1])}A{f(r1o)} {f(r1o)} 0 1 0 {f(jl[0])} {f(jl[1])}"
        f"A{f(r2i)} {f(r2i)} 0 1 1 {f(ti[0])} {f(ti[1])}L{f(to[0])} {f(to[1])}"
        f"A{f(r2o)} {f(r2o)} 0 1 0 {f(ju[0])} {f(ju[1])}"
        f"A{f(r1i)} {f(r1i)} 0 1 1 {f(p2[0])} {f(p2[1])}Z"
    )
    return d, x + width


LAYERS = [19, 29, 52]
GAP = 3.6
RC = 3.1          # promien luku pasm w krotnosciach promienia dysku


def strata_o(x):
    R = H / 2 + OS
    return curved_strata(x + R, H / 2, R, LAYERS, GAP, R * RC), x + 2 * R


def main(out):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    R = H / 2 + OS
    T = 25.0

    # A: litery jak nic, O jak przekroj pasiastego kamienia
    d_a, end_a = wordmark(strata_o, track=T)
    (out / "a-lockup.svg").write_text(svg(d_a, (-4, -6, end_a + 8, 112)))
    sym_a = curved_strata(128, 128, 116, LAYERS, GAP * 2.3, 116 * RC)
    (out / "a-symbol.svg").write_text(svg(sym_a, (0, 0, 256, 256)))
    small_a = curved_strata(128, 128, 120, [36, 64], 26, 120 * RC)
    (out / "a-symbol-small.svg").write_text(svg(small_a, (0, 0, 256, 256)))

    # B: male litery, u i m prowadzone jedna linia
    x = 0.0
    parts = []
    d, x = lower_s(x)
    parts.append(d)
    x += 15
    ro = 34.0
    parts.append(ring(x + ro, 100 + OS - ro, ro, ro - W))
    x += 2 * ro + 15
    parts.append(f"M{f(x)} 0H{f(x + W)}V100H{f(x)}Z")
    x += W + 15
    d, x = lower_um(x)
    parts.append(d)
    (out / "b-lockup.svg").write_text(svg("".join(parts), (-4, -6, x + 8, 112), evenodd=True))
    ds, _ = lower_um(40, xh=100, w=26) if False else (ring(128, 128, 110, 84), 0)
    (out / "b-symbol.svg").write_text(svg(ds, (0, 0, 256, 256), evenodd=True))

    # C: O jako obrecz z jednym kamieniem (kamien odsuniety od obreczy szczelina)
    def o_c(x):
        cx = x + R
        rr = R - W / 2
        a = math.radians(45)
        ring_d = ring(cx, H / 2, R, R - W)
        return ring_d, x + 2 * R

    d_c, end_c = wordmark(o_c, track=T)
    rr = R - W / 2
    a = math.radians(45)
    # kamien rysowany osobna sciezka, zeby evenodd nie wycinal zakladki
    cx_o = 0
    (out / "c-lockup.svg").write_text(
        svg(d_c, (-4, -12, end_c + 8, 118), evenodd=True).replace(
            "</svg>",
            f'<path d="{disc(_c_center(), H / 2 - rr * math.sin(a), 11)}"/></svg>',
        )
    )
    (out / "c-symbol.svg").write_text(
        svg(ring(128, 136, 100, 80), (0, 0, 256, 256), evenodd=True).replace(
            "</svg>", f'<path d="{disc(128 + 90 * math.cos(a), 136 - 90 * math.sin(a), 30)}"/></svg>'
        )
    )


def _c_center():
    # polozenie kamienia w wordmarku C: srodek O + r*cos45
    R = H / 2 + OS
    _, end_s = letter_s(0.0)
    return end_s + 25.0 + 2 + R + (R - W / 2) * math.cos(math.radians(45))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "koncepcje")
