"""Proceduralne tekstury kamieni, drewna, skory i wlokien dla modeli SOLUM.

Kazda tekstura koralika to rownokatna mapa kuli liczona z szumu 3D, wiec nie ma
sciagniec na biegunach i kazdy koralik wyglada jak wyciety z bryly materialu.

Uzycie: python textures.py <folder_wyjsciowy> [nazwa_materialu ...]
"""
import sys
from multiprocessing import Pool
from pathlib import Path

import numpy as np
from PIL import Image
from scipy.ndimage import gaussian_filter, map_coordinates
from scipy.spatial import cKDTree

W, H = 1536, 768
VARIANTS = 3


def sphere_points(w=W, h=H):
    lon = (np.arange(w) + 0.5) / w * 2 * np.pi
    lat = (np.arange(h) + 0.5) / h * np.pi
    lon, lat = np.meshgrid(lon, lat)
    return np.stack([np.sin(lat) * np.cos(lon), np.sin(lat) * np.sin(lon), np.cos(lat)], axis=-1)


_VOL = {}


def lattice(seed):
    if seed not in _VOL:
        rng = np.random.default_rng(seed)
        v = gaussian_filter(rng.normal(size=(48, 48, 48)), 0.9, mode="wrap")
        _VOL[seed] = v / v.std()
    return _VOL[seed]


def noise(p, freq, seed):
    coords = np.moveaxis(p * freq + 13.37 * (seed % 7), -1, 0) * 1.0
    return map_coordinates(lattice(seed), coords, order=3, mode="grid-wrap", prefilter=False)


def fbm(p, freq, seed, octaves=4, gain=0.5):
    out = np.zeros(p.shape[:-1], dtype=np.float32)
    amp, tot = 1.0, 0.0
    for i in range(octaves):
        out += amp * noise(p, freq * 2.03**i, seed + i * 11)
        tot += amp
        amp *= gain
    return out / tot / 0.62


def warp(p, freq, amp, seed, octaves=3):
    d = np.stack([fbm(p, freq, seed + 100 + k * 17, octaves) for k in range(3)], axis=-1)
    return p + d * amp


def smooth(a, b, x):
    t = np.clip((x - a) / (b - a), 0, 1)
    return t * t * (3 - 2 * t)


def hex3(h):
    h = h.lstrip("#")
    return np.array([int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)], dtype=np.float32)


def to_linear(c):
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def to_srgb(c):
    c = np.clip(c, 0, 1)
    return np.where(c <= 0.0031308, c * 12.92, 1.055 * c ** (1 / 2.4) - 0.055)


def ramp(t, stops):
    """Rampa kolorow liczona liniowo. stops = [(pozycja, '#hex'), ...]"""
    xs = np.array([s[0] for s in stops])
    cs = to_linear(np.stack([hex3(s[1]) for s in stops]))
    t = np.clip(t, 0, 1)
    return to_srgb(np.stack([np.interp(t, xs, cs[:, i]) for i in range(3)], axis=-1))


def mix(a, b, m):
    m = np.asarray(m)[..., None] if np.ndim(m) == 2 else m
    return to_srgb(to_linear(a) * (1 - m) + to_linear(b) * m)


def unit(seed, k=0):
    rng = np.random.default_rng(seed * 31 + k)
    v = rng.normal(size=3)
    return v / np.linalg.norm(v)


def basis(seed):
    a = unit(seed)
    b = np.cross(a, unit(seed, 1))
    b /= np.linalg.norm(b)
    return a, b, np.cross(a, b)


def band_table(rng, palette, count=70, thin=(0.25, 1.0), thick=(0.8, 3.2), thick_p=0.35):
    """Losowa sekwencja pasm o roznej grubosci, jak warstwy w kamieniu."""
    widths = np.where(rng.random(count) < thick_p, rng.uniform(*thick, count), rng.uniform(*thin, count))
    edges = np.concatenate([[0], np.cumsum(widths)])
    idx = rng.integers(0, len(palette), count)
    for i in range(1, count):
        if idx[i] == idx[i - 1]:
            idx[i] = (idx[i] + 1) % len(palette)
    cols = np.stack([to_linear(hex3(palette[i])) for i in idx])
    return edges / edges[-1], cols


def bands(t, table, softness=0.0016):
    edges, cols = table
    t = np.mod(t, 1.0)
    xs = np.repeat(edges, 2)
    xs[1::2] += softness
    xs = xs[1:-1]
    ys = np.repeat(cols, 2, axis=0)
    out = np.stack([np.interp(t, xs, ys[:, i]) for i in range(3)], axis=-1)
    return to_srgb(out)


# ---------------------------------------------------------------- kamienie


def grain(col, p, seed, amount=0.06, freq=38):
    """Drobne ziarno, bez ktorego kamien wyglada jak plastik."""
    g = fbm(p, freq, seed + 77, 2)
    return to_srgb(to_linear(col) * (1 + amount * g[..., None]))


def layer_axis(seed):
    """Normalna warstw blisko lokalnej osi X (lekkie odchylenie zalezne od ziarna)."""
    v = np.array([1.0, 0.0, 0.0]) + unit(seed, 5) * 0.28
    return v / np.linalg.norm(v)


def krzemien(seed):
    """Krzemien pasiasty: gesto ulozone, lekko faliste pasma szarosci, grafitu i kosci."""
    rng = np.random.default_rng(seed)
    p = sphere_points()
    a = layer_axis(seed)
    q = warp(p, 1.3, 0.13, seed, 3)
    q = warp(q, 5.0, 0.018, seed + 40, 2)
    t = np.tensordot(q, a, axes=1) * 0.2 + 0.5 + rng.random()
    table = band_table(rng, ["#e6e0d2", "#d3ccbc", "#a29c8f", "#6b665c", "#35312c", "#c4bdae", "#ece7db"],
                       count=64, thin=(0.2, 0.8), thick=(0.9, 2.6), thick_p=0.3)
    col = bands(t, table, softness=0.0032)
    tone = fbm(p, 6.5, seed + 7, 3)
    col = to_srgb(to_linear(col) * (1 + 0.1 * tone[..., None]))
    col = grain(col, p, seed, 0.07)
    rough = 0.17 + 0.05 * smooth(-1, 1.5, fbm(p, 16, seed + 9, 3))
    return dict(color=col, rough=rough)


def bursztyn(seed, tone="koniak"):
    p = sphere_points()
    q = warp(p, 1.2, 0.3, seed, 3)
    n = fbm(q, 1.9, seed + 1, 5) * 0.5 + 0.5
    n = smooth(0.12, 0.88, n)
    stops = {
        "koniak": [(0.0, "#a7500f"), (0.5, "#c26c17"), (1.0, "#dc8f26")],
        "miod": [(0.0, "#cf8519"), (0.5, "#e3a02a"), (1.0, "#f2c04d")],
        "krolewski": [(0.0, "#dcaa56"), (0.5, "#ebc885"), (1.0, "#f6e4bd")],
    }[tone]
    col = ramp(n, stops)
    veil = smooth(0.5, 1.5, fbm(q, 3.2, seed + 4, 5))
    col = mix(col, np.broadcast_to(hex3("#f5dca2"), col.shape), veil * (0.55 if tone == "krolewski" else 0.22))
    flecks = smooth(2.5, 2.8, fbm(p, 80, seed + 8, 2))
    col = mix(col, np.broadcast_to(hex3("#3a1c06"), col.shape), flecks * 0.5)
    rough = 0.07 + 0.04 * smooth(-1, 1.5, fbm(p, 12, seed + 2, 3))
    return dict(color=col, rough=rough, cloud=veil)


def tygrysie_oko(seed):
    rng = np.random.default_rng(seed)
    p = sphere_points()
    a = layer_axis(seed)
    b = np.cross(a, unit(seed, 1))
    b /= np.linalg.norm(b)
    c = np.cross(a, b)
    q = warp(p, 1.0, 0.14, seed, 3)
    t = np.tensordot(q, a, axes=1) * 0.085 + 0.5 + rng.random()
    table = band_table(rng, ["#a06c26", "#5e3911", "#c48d34", "#3f250c", "#83551b", "#b07a2a"], count=48,
                       thin=(0.5, 1.1), thick=(1.4, 3.4), thick_p=0.42)
    col = bands(t, table, softness=0.022)
    fp = np.stack([np.tensordot(q, a, axes=1) * 130, np.tensordot(q, b, axes=1) * 4.0,
                   np.tensordot(q, c, axes=1) * 4.0], axis=-1)
    fibers = noise(fp, 1.0, seed + 2) * 0.55 + noise(fp, 2.4, seed + 3) * 0.45
    sheen = smooth(-0.6, 0.9, fbm(q, 2.4, seed + 4, 3))
    col = mix(col, np.broadcast_to(hex3("#e6b655"), col.shape), sheen * 0.42)
    col = to_srgb(to_linear(col) * (1 + 0.2 * np.clip(fibers, -1.4, 1.4)[..., None]))
    rough = 0.19 + 0.03 * fibers
    return dict(color=col, rough=np.clip(rough, 0.12, 0.35))


def lapis(seed):
    p = sphere_points()
    q = warp(p, 1.6, 0.2, seed, 3)
    n = fbm(q, 8.0, seed + 1, 5) * 0.5 + 0.5
    col = ramp(n, [(0, "#11205f"), (0.5, "#16277a"), (1, "#20389a")])
    patch = smooth(1.25, 1.75, fbm(warp(p, 3.0, 0.1, seed + 30, 2), 3.2, seed + 3, 5))
    col = mix(col, np.broadcast_to(hex3("#b9bdd0"), col.shape), patch * 0.72)
    mottling = smooth(1.1, 2.0, fbm(q, 22, seed + 5, 3))
    col = mix(col, np.broadcast_to(hex3("#7f8dcb"), col.shape), mottling * 0.22)
    pyr = smooth(1.95, 2.25, fbm(p, 110, seed + 6, 2)) * smooth(-0.6, 0.6, fbm(p, 4.5, seed + 7, 2))
    col = mix(col, np.broadcast_to(hex3("#e3bf5a"), col.shape), pyr)
    col = grain(col, p, seed, 0.06, 70)
    rough = 0.2 + 0.05 * smooth(-1, 1.5, fbm(p, 18, seed + 8, 2)) + 0.05 * patch
    return dict(color=col, rough=rough, metal=np.clip(pyr, 0, 1))


def nefryt(seed):
    p = sphere_points()
    q = warp(p, 1.6, 0.22, seed, 3)
    n = fbm(q, 8.0, seed + 1, 6) * 0.5 + 0.5
    col = ramp(smooth(0.2, 0.8, n), [(0, "#17301f"), (0.5, "#234733"), (1, "#3c6a4d")])
    fl = smooth(1.85, 2.3, fbm(p, 34, seed + 3, 3))
    col = mix(col, np.broadcast_to(hex3("#0b120e"), col.shape), fl * 0.8)
    cl = smooth(1.3, 2.0, fbm(q, 9, seed + 4, 3))
    col = mix(col, np.broadcast_to(hex3("#86a783"), col.shape), cl * 0.16)
    col = grain(col, p, seed, 0.06, 50)
    rough = 0.24 + 0.05 * smooth(-1, 1.5, fbm(p, 12, seed + 5, 3))
    return dict(color=col, rough=rough)


def obsydian(seed):
    p = sphere_points()
    a, _, _ = basis(seed)
    q = warp(p, 1.0, 0.1, seed, 3)
    t = np.tensordot(q, a, axes=1) * 5
    n = (np.sin(t * 5) * 0.5 + 0.5) * 0.25 + 0.3 * (fbm(q, 7, seed + 2, 3) * 0.5 + 0.5)
    col = ramp(n, [(0, "#08080a"), (0.5, "#101012"), (1, "#1d1c20")])
    rough = 0.055 + 0.015 * smooth(-1, 1.5, fbm(p, 9, seed + 3, 2))
    return dict(color=col, rough=rough)


def kwarc(seed):
    p = sphere_points()
    q = warp(p, 1.6, 0.25, seed, 3)
    n = fbm(q, 4.0, seed + 1, 5) * 0.5 + 0.5
    col = ramp(n, [(0, "#e2a2ad"), (0.45, "#ecb6bd"), (0.75, "#f3ccd0"), (1, "#f9e2e0")])
    cl = smooth(0.6, 1.7, fbm(q, 7.0, seed + 3, 4))
    col = mix(col, np.broadcast_to(hex3("#fff5f0"), col.shape), cl * 0.42)
    rough = 0.1 + 0.05 * smooth(-1, 1.5, fbm(p, 12, seed + 4, 2))
    return dict(color=col, rough=rough, cloud=cl)


def amazonit(seed):
    p = sphere_points()
    a, b, c = basis(seed)
    q = warp(p, 1.2, 0.09, seed, 2)
    fp = np.stack([np.tensordot(q, a, axes=1) * 2.2, np.tensordot(q, b, axes=1) * 20,
                   np.tensordot(q, c, axes=1) * 20], axis=-1)
    st = fbm(fp, 1.0, seed + 1, 4) * 0.5 + 0.5
    col = ramp(st, [(0, "#468f86"), (0.42, "#62ab9f"), (0.72, "#84c4b6"), (1, "#b4dccf")])
    w = smooth(1.15, 1.6, fbm(fp, 1.3, seed + 3, 3))
    col = mix(col, np.broadcast_to(hex3("#efeadf"), col.shape), w * 0.75)
    col = grain(col, p, seed, 0.05, 50)
    rough = 0.26 + 0.07 * smooth(-1, 1.5, fbm(p, 16, seed + 5, 3))
    return dict(color=col, rough=rough)


# ---------------------------------------------------------------- drewno lite


def wood_solid(seed, stops, pore, rough0, ring_freq=16.0, warp_amp=0.06, pore_amt=0.7, streak=None):
    """Drewno jako bryla: prawie rownolegle sloje oraz podluzne pory wzdluz wlokien."""
    p = sphere_points()
    a, b, c = basis(seed)
    q = warp(p, 1.1, warp_amp, seed, 3)
    u = np.tensordot(q, b, axes=1) + 2.3
    v = np.tensordot(q, c, axes=1) + 1.2
    w = np.tensordot(q, a, axes=1)
    r = np.sqrt(u * u + v * v)
    r = r + 0.012 * fbm(np.stack([u * 4, v * 4, w * 1.1], -1), 1.0, seed + 2, 3)
    rings = (r * ring_freq) % 1.0
    rings = rings ** 1.7 + 0.14 * fbm(np.stack([u * 9, v * 9, w * 1.2], -1), 1.0, seed + 3, 3)
    col = ramp(rings, stops)
    fp = np.stack([u * 70, v * 70, w * 3.0], -1)
    pores = smooth(0.75, 1.6, fbm(fp, 1.0, seed + 4, 3))
    col = mix(col, np.broadcast_to(hex3(pore), col.shape), pores * pore_amt)
    if streak is not None:
        lines = np.abs(np.sin((r * ring_freq * 1.35) * np.pi))
        group = smooth(0.1, 1.0, fbm(np.stack([u * 2.6, v * 2.6, w * 0.7], -1), 1.0, seed + 8, 3))
        col = mix(col, np.broadcast_to(hex3(streak), col.shape), smooth(0.8, 0.99, lines) * group * 0.72)
    fine = fbm(np.stack([u * 150, v * 150, w * 6], -1), 1.0, seed + 5, 2)
    col = to_srgb(to_linear(col) * (1 + 0.12 * fine[..., None]))
    height = 1 - pores * 0.9
    rough = rough0 + 0.1 * pores
    return dict(color=col, rough=rough, height=height, normal_strength=0.32)


def dab_bagienny(seed):
    return wood_solid(seed, [(0, "#3a2e25"), (0.5, "#2a211b"), (1, "#17120f")], "#4f4338", 0.42,
                      ring_freq=20, pore_amt=0.5)


def oliwka(seed):
    return wood_solid(seed, [(0, "#d6ba85"), (0.5, "#cdaf78"), (1, "#bb9a62")], "#8d6b42", 0.36,
                      ring_freq=8, warp_amp=0.075, pore_amt=0.16, streak="#4d351e")


def orzech(seed):
    return wood_solid(seed, [(0, "#8a6242"), (0.5, "#6b4830"), (1, "#42291a")], "#2c1b10", 0.4,
                      ring_freq=15, pore_amt=0.55)


def wood_tile(seed, stops, pore, streak=None, size=(3072, 512)):
    """Pasek drewna gietego: uslojenie biegnie wzdluz obwodu, tekstura zamknieta w poziomie."""
    w, h = size
    u = (np.arange(w) + 0.5) / w * 2 * np.pi
    v = (np.arange(h) + 0.5) / h
    u, v = np.meshgrid(u, v)
    R = 1.7
    p = np.stack([np.cos(u) * R, np.sin(u) * R, v * 2.2], -1)
    wob = fbm(p, 0.55, seed, 3)
    t = v * 24 + wob * 1.05
    a = t % 1.0
    rings = smooth(0.0, 0.72, a) * (1 - smooth(0.82, 1.0, a))
    rings = rings * 0.62 + 0.38 * (fbm(p, 2.2, seed + 1, 4) * 0.5 + 0.5)
    col = ramp(rings, stops)
    fp = np.stack([np.cos(u) * 5.5, np.sin(u) * 5.5, v * 150], -1)
    pores = smooth(0.7, 1.6, fbm(fp, 1.0, seed + 3, 3))
    col = mix(col, np.broadcast_to(hex3(pore), col.shape), pores * 0.5)
    if streak is not None:
        lines = np.abs(np.sin((v * 4.4 + wob * 1.3) * np.pi))
        group = smooth(-0.1, 0.8, fbm(p, 1.3, seed + 6, 2))
        col = mix(col, np.broadcast_to(hex3(streak), col.shape), smooth(0.9, 0.995, lines) * group * 0.8)
    fine = fbm(np.stack([np.cos(u) * 14, np.sin(u) * 14, v * 320], -1), 1.0, seed + 5, 2)
    col = to_srgb(to_linear(col) * (1 + 0.1 * fine[..., None]))
    return dict(color=col, rough=0.32 + 0.1 * pores, height=1 - pores * 0.9, normal_strength=0.7)


def giety_orzech(seed):
    return wood_tile(seed, [(0, "#7c563a"), (0.5, "#64432c"), (1, "#452c1b")], "#2c1b10")


def giety_oliwka(seed):
    return wood_tile(seed, [(0, "#d9bd87"), (0.5, "#c9aa72"), (1, "#a98651")], "#8c6a41", streak="#402a16")


def giety_dab(seed):
    return wood_tile(seed, [(0, "#d5b488"), (0.5, "#c19c6b"), (1, "#a07c4e")], "#7a5a36")


# ---------------------------------------------------------------- skora i wlokna


def worley_edges(size, cells, seed):
    rng = np.random.default_rng(seed)
    pts = rng.random((cells, 2))
    tile = np.concatenate([pts + np.array([i, j]) for i in (-1, 0, 1) for j in (-1, 0, 1)])
    tree = cKDTree(tile)
    g = (np.arange(size) + 0.5) / size
    gx, gy = np.meshgrid(g, g)
    d, _ = tree.query(np.stack([gx.ravel(), gy.ravel()], -1), k=2, workers=-1)
    return (d[:, 1] - d[:, 0]).reshape(size, size) * np.sqrt(cells)


def skora(seed, size=1024):
    e = worley_edges(size, 5200, seed)
    e2 = worley_edges(size, 1400, seed + 1)
    height = smooth(0.02, 0.32, e) * 0.72 + smooth(0.02, 0.28, e2) * 0.28
    height = gaussian_filter(height, 0.7, mode="wrap")
    # kolor to odcien szarosci mnozony przez barwe w materiale
    rng = np.random.default_rng(seed + 2)
    tone = gaussian_filter(rng.normal(size=(size, size)), 26, mode="wrap")
    tone = tone / tone.std()
    shade = 0.9 + 0.022 * tone + 0.09 * (height - 0.5)
    col = np.stack([shade] * 3, -1)
    rough = 0.38 + 0.2 * (1 - height)
    return dict(color=np.clip(col, 0, 1), rough=rough, height=height)


def wlokno(seed, size=512):
    """Drobne skosne wlokna do sznurkow, tekstura powtarzalna."""
    rng = np.random.default_rng(seed)
    n = rng.normal(size=(size, size))
    a = gaussian_filter(n, (0.7, 7.0), mode="wrap")
    a /= a.std()
    b = gaussian_filter(rng.normal(size=(size, size)), (0.5, 3.0), mode="wrap")
    b /= b.std()
    height = np.clip(0.5 + 0.2 * a + 0.1 * b, 0, 1)
    shade = np.clip(0.82 + 0.12 * a + 0.06 * b, 0, 1)
    return dict(color=np.stack([shade] * 3, -1), rough=0.65 + 0.2 * (1 - height), height=height)


# ---------------------------------------------------------------- zapis


def normal_from_height(h, strength):
    dy, dx = np.gradient(h)
    n = np.stack([-dx * strength, dy * strength, np.ones_like(h)], -1)
    n /= np.linalg.norm(n, axis=-1, keepdims=True)
    return n * 0.5 + 0.5


def save(name, data, out):
    out = Path(out)
    col8 = (np.clip(data["color"], 0, 1) * 255 + 0.5).astype(np.uint8)
    Image.fromarray(col8, "RGB").save(out / f"{name}_color.png", optimize=False)
    rough = np.clip(data["rough"], 0, 1)
    metal = np.clip(data.get("metal", np.zeros_like(rough)), 0, 1)
    # glTF ORM: G = roughness, B = metallic
    orm = np.stack([np.ones_like(rough), rough, metal], -1)
    Image.fromarray((orm * 255 + 0.5).astype(np.uint8), "RGB").save(out / f"{name}_orm.png")
    if "cloud" in data:
        Image.fromarray((np.clip(data["cloud"], 0, 1) * 255 + 0.5).astype(np.uint8), "L").save(out / f"{name}_cloud.png")
    if "height" in data:
        strength = data.get("normal_strength", 2.2)
        nm = normal_from_height(data["height"], strength * data["height"].shape[0] / 256)
        Image.fromarray((nm * 255 + 0.5).astype(np.uint8), "RGB").save(out / f"{name}_normal.png")


SOLID = {
    "krzemien": krzemien,
    "bursztyn_koniak": lambda s: bursztyn(s, "koniak"),
    "bursztyn_miod": lambda s: bursztyn(s, "miod"),
    "bursztyn_krolewski": lambda s: bursztyn(s, "krolewski"),
    "tygrysie_oko": tygrysie_oko,
    "lapis": lapis,
    "nefryt": nefryt,
    "obsydian": obsydian,
    "kwarc": kwarc,
    "amazonit": amazonit,
    "dab_bagienny": dab_bagienny,
    "oliwka": oliwka,
    "orzech": orzech,
}
SINGLE = {
    "giety_orzech": giety_orzech,
    "giety_oliwka": giety_oliwka,
    "giety_dab": giety_dab,
    "skora": skora,
    "wlokno": wlokno,
}


def job(args):
    name, seed, suffix, out = args
    fn = SOLID.get(name) or SINGLE[name]
    save(f"{name}{suffix}", fn(seed), out)
    return f"{name}{suffix}"


def main():
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    only = set(sys.argv[2:])
    jobs = []
    for i, (name, fn) in enumerate(SOLID.items()):
        if only and name not in only:
            continue
        for v in range(VARIANTS):
            jobs.append((name, 1000 + i * 37 + v * 211, f"_{v}", str(out)))
    for i, (name, fn) in enumerate(SINGLE.items()):
        if only and name not in only:
            continue
        jobs.append((name, 5000 + i * 53, "", str(out)))
    with Pool(10) as pool:
        for done in pool.imap_unordered(job, jobs):
            print("ok", done, flush=True)


if __name__ == "__main__":
    main()
