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


def tygrysie_oko(seed):
    rng = np.random.default_rng(seed)
    p = sphere_points()
    a = layer_axis(seed)
    b = np.cross(a, unit(seed, 1))
    b /= np.linalg.norm(b)
    c = np.cross(a, b)
    q = warp(p, 1.0, 0.14, seed, 3)
    t = np.tensordot(q, a, axes=1) * 0.085 + 0.5 + rng.random()
    table = band_table(rng, ["#8a5a1f", "#3d220c", "#b37e2c", "#26150a", "#6b4415", "#9c6c24"], count=48,
                       thin=(0.5, 1.1), thick=(1.4, 3.4), thick_p=0.42)
    col = bands(t, table, softness=0.022)
    fp = np.stack([np.tensordot(q, a, axes=1) * 130, np.tensordot(q, b, axes=1) * 4.0,
                   np.tensordot(q, c, axes=1) * 4.0], axis=-1)
    fibers = noise(fp, 1.0, seed + 2) * 0.55 + noise(fp, 2.4, seed + 3) * 0.45
    sheen = smooth(-0.6, 0.9, fbm(q, 2.4, seed + 4, 3))
    col = mix(col, np.broadcast_to(hex3("#d9a548"), col.shape), sheen * 0.14)
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


# ---------------------------------------------------------------- kamienie ze zdjec sklepu


def tone(seed, palettes):
    """Kazdy z trzech wariantow tekstury dostaje inny odcien, wiec koraliki w sznurze sie roznia."""
    return palettes[seed % len(palettes)]


def broad(col, h):
    return np.broadcast_to(hex3(h), col.shape)


def stops3(c):
    return [(0, c[0]), (0.5, c[1]), (1, c[2])]


def cloudy(seed, colors, freq=4.5, warp_amp=0.22, veil=None, veil_amt=0.0, rough0=0.3, grain_amt=0.05):
    p = sphere_points()
    q = warp(p, 1.5, warp_amp, seed, 3)
    n = fbm(q, freq, seed + 1, 5) * 0.5 + 0.5
    col = ramp(smooth(0.2, 0.8, n), stops3(colors))
    out = {}
    if veil:
        v = smooth(0.6, 1.7, fbm(q, freq * 1.7, seed + 3, 4))
        col = mix(col, broad(col, veil), v * veil_amt)
        out["cloud"] = v
    col = grain(col, p, seed, grain_amt, 55)
    rough = rough0 + 0.05 * smooth(-1, 1.5, fbm(p, 14, seed + 5, 3))
    out.update(color=col, rough=rough, p=p, q=q)
    return out


def done(d):
    d.pop("p", None)
    d.pop("q", None)
    return d


def amazonit_nieb(seed):
    p = sphere_points()
    a, b, c = basis(seed)
    q = warp(p, 1.2, 0.09, seed, 2)
    fp = np.stack([np.tensordot(q, a, axes=1) * 2.2, np.tensordot(q, b, axes=1) * 18,
                   np.tensordot(q, c, axes=1) * 18], axis=-1)
    st = fbm(fp, 1.0, seed + 1, 4) * 0.5 + 0.5
    col = ramp(st, [(0, "#4a9a9b"), (0.5, "#5cadab"), (1, "#86c9c0")])
    w = smooth(1.2, 1.7, fbm(fp, 1.3, seed + 3, 3))
    col = mix(col, broad(col, "#bfe4dc"), w * 0.16)
    col = grain(col, p, seed, 0.06, 60)
    return dict(color=col, rough=0.44 + 0.06 * smooth(-1, 1.5, fbm(p, 16, seed + 5, 3)))


def turmalin_rozowy(seed):
    c = tone(seed, [("#a69b94", "#bdb3ab", "#d4ccc4"), ("#7c6377", "#94798d", "#ad95a6"), ("#5b4453", "#735866", "#8d7080")])
    return done(cloudy(seed, c, freq=5, veil="#d8cfd0", veil_amt=0.3, rough0=0.45, grain_amt=0.08))


def sloneczny(seed):
    c = tone(seed, [("#a86c4e", "#bd8565", "#cf9f80"), ("#9a5f45", "#b07757", "#c48f70"), ("#b8805f", "#c99878", "#dab195")])
    d = cloudy(seed, c, freq=5.5, rough0=0.36, grain_amt=0.07)
    spark = smooth(1.75, 2.15, fbm(d["p"], 125, seed + 6, 2))
    d["color"] = mix(d["color"], broad(d["color"], "#f2c78e"), spark)
    d["metal"] = np.clip(spark, 0, 1)
    return done(d)


def chryzokola(seed):
    kind = seed % 3
    c = [("#15130f", "#241f1a", "#3a3229"), ("#1f6f6b", "#3a958c", "#6fbcae"), ("#8f9484", "#b3b5a2", "#d3d2bf")][kind]
    d = cloudy(seed, c, freq=6, warp_amp=0.3, rough0=0.18, grain_amt=0.06)
    vein = smooth(0.9, 0.99, 1 - np.abs(fbm(d["q"], 4.0, seed + 7, 4)))
    d["color"] = mix(d["color"], broad(d["color"], ["#3a958c", "#14211f", "#3a958c"][kind]), vein * 0.75)
    return done(d)


def turmalin(seed):
    c = tone(seed, [("#7f2238", "#a23a52", "#c25f74"), ("#b4586f", "#cf8595", "#e3aeb7"), ("#3f1622", "#5c2232", "#7a3346")])
    return done(cloudy(seed, c, freq=4, rough0=0.14))


def ksiezycowy(seed):
    return done(cloudy(seed, ("#dfe2e3", "#eceeee", "#f7f7f5"), freq=3.5, veil="#cfdbe6", veil_amt=0.35, rough0=0.2, grain_amt=0.02))


def kalcyt(seed):
    c = tone(seed, [("#e8cf97", "#f0dcae", "#f8edd0"), ("#e2c07e", "#ecd096", "#f4e2b8"), ("#f1e6c8", "#f7eed8", "#fff9ea")])
    return done(cloudy(seed, c, freq=3.5, veil="#fffdf4", veil_amt=0.45, rough0=0.3, grain_amt=0.03))


def kwarc_dymny(seed):
    c = tone(seed, [("#33271e", "#4a3a2d", "#63503f"), ("#281f18", "#3b2f25", "#524335"), ("#3d2f24", "#574636", "#725d4a")])
    return done(cloudy(seed, c, freq=3, rough0=0.15, grain_amt=0.03))


def ametyst_jasny(seed):
    c = tone(seed, [("#9a8390", "#ae97a3", "#c4b1b9"), ("#ad949b", "#bfa9ae", "#d4c4c7"), ("#7c6577", "#927b8b", "#aa95a2")])
    return done(cloudy(seed, c, freq=4, veil="#e0d4dc", veil_amt=0.2, rough0=0.18, grain_amt=0.04))


def ametyst_ciemny(seed):
    c = tone(seed, [("#2e1e55", "#463079", "#654a9c"), ("#3a2768", "#553b8a", "#7a5bab"), ("#241745", "#372660", "#503a80")])
    return done(cloudy(seed, c, freq=3.5, veil="#b7a3d6", veil_amt=0.3, rough0=0.1, grain_amt=0.03))


def fractures(d, seed, amount, color="#ffffff"):
    r = 1 - np.abs(fbm(d["q"], 3.4, seed + 9, 4))
    f = smooth(0.91, 0.995, r) * smooth(-0.3, 0.8, fbm(d["p"], 2.6, seed + 11, 2))
    d["color"] = mix(d["color"], broad(d["color"], color), f * amount)
    return d


def akwamaryn(seed):
    c = tone(seed, [("#86d0e2", "#a4dfec", "#c6ecf4"), ("#74c6dc", "#94d6e6", "#b8e6f0"), ("#9ad9e8", "#b8e6f0", "#d6f2f7")])
    return done(fractures(cloudy(seed, c, freq=3.2, rough0=0.05, grain_amt=0.02), seed, 0.7))


def labradoryt(seed):
    c = tone(seed, [("#9aa09f", "#aab0af", "#bcc1c0"), ("#7f8584", "#919796", "#a5abaa"), ("#b2b7b5", "#c0c5c3", "#d0d4d2")])
    return done(cloudy(seed, c, freq=3.5, rough0=0.16, grain_amt=0.03))


def rubin_zoisyt(seed):
    kind = seed % 3
    c = [("#214f38", "#2f6b4c", "#4b8a66"), ("#101a15", "#1b2b22", "#2e4435"), ("#2c5a42", "#3b7355", "#568f6e")][kind]
    d = cloudy(seed, c, freq=6, warp_amp=0.28, rough0=0.16, grain_amt=0.06)
    fl = smooth(1.3, 1.9, fbm(d["p"], 20, seed + 3, 3))
    d["color"] = mix(d["color"], broad(d["color"], "#0a0f0c"), fl * 0.8)
    if kind == 2:
        m = smooth(0.55, 1.05, fbm(d["q"], 2.6, seed + 8, 4))
        d["color"] = mix(d["color"], broad(d["color"], "#7a2a54"), m * 0.9)
    return done(d)


def jaspis(seed):
    d = cloudy(seed, ("#d6ccb5", "#e2d9c5", "#ece5d5"), freq=4, rough0=0.3, grain_amt=0.05)
    spots = smooth(1.15, 1.45, fbm(d["q"], 13, seed + 4, 2))
    d["color"] = mix(d["color"], broad(d["color"], "#1e1a17"), spots * 0.95)
    brown = smooth(1.2, 1.5, fbm(d["q"], 9, seed + 6, 2))
    d["color"] = mix(d["color"], broad(d["color"], "#7a4a2a"), brown * 0.7)
    return done(d)


def agat(seed):
    rng = np.random.default_rng(seed)
    p = sphere_points()
    a = layer_axis(seed)
    q = warp(p, 1.3, 0.13, seed, 3)
    q = warp(q, 5.0, 0.018, seed + 40, 2)
    t = np.tensordot(q, a, axes=1) * 0.2 + 0.5 + rng.random()
    table = band_table(rng, ["#7b4a2a", "#a8744a", "#d8b98f", "#efe1c6", "#5a3522", "#c49a6c"],
                       count=64, thin=(0.2, 0.8), thick=(0.9, 2.6), thick_p=0.3)
    col = grain(bands(t, table, softness=0.0032), p, seed, 0.06)
    return dict(color=col, rough=0.16 + 0.05 * smooth(-1, 1.5, fbm(p, 16, seed + 9, 3)))


def serpentyn(seed):
    c = tone(seed, [("#a5b170", "#bcc68a", "#d6dcae"), ("#98a564", "#afba7e", "#cbd3a2"), ("#b2bc80", "#c7d09a", "#dfe5bc")])
    return done(cloudy(seed, c, freq=3.8, veil="#e9edc9", veil_amt=0.3, rough0=0.26, grain_amt=0.04))


def krysztal(seed):
    d = cloudy(seed, ("#eeeeea", "#f6f6f2", "#ffffff"), freq=3, rough0=0.05, grain_amt=0.01)
    return done(fractures(d, seed, 0.9))


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
    "tygrysie_oko": tygrysie_oko,
    "lapis": lapis,
    "obsydian": obsydian,
    "kwarc": kwarc,
    "amazonit_nieb": amazonit_nieb,
    "turmalin_rozowy": turmalin_rozowy,
    "sloneczny": sloneczny,
    "chryzokola": chryzokola,
    "turmalin": turmalin,
    "ksiezycowy": ksiezycowy,
    "kalcyt": kalcyt,
    "kwarc_dymny": kwarc_dymny,
    "ametyst_jasny": ametyst_jasny,
    "ametyst_ciemny": ametyst_ciemny,
    "akwamaryn": akwamaryn,
    "labradoryt": labradoryt,
    "rubin_zoisyt": rubin_zoisyt,
    "jaspis": jaspis,
    "agat": agat,
    "serpentyn": serpentyn,
    "krysztal": krysztal,
}
SINGLE = {}


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
