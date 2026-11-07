"""Ujecia sklepu: hero strony glownej, kafelki materialow i martwa natura pracowni.

Uzycie: blender -b -P scenes.py -- --out <folder> [--only nazwa,...] [--samples 160] [--scale 1.0]
"""
import argparse
import json
import math
import random
import sys
from pathlib import Path

import bpy
from mathutils import Matrix, Vector

sys.path.append(str(Path(__file__).resolve().parent))
import bracelets as b  # noqa: E402


def find_variant(products, slug, vid):
    for p in products:
        if p["slug"] == slug:
            for v in p["variants"]:
                if v["id"] == vid:
                    return v["model"]
    raise KeyError(f"{slug}:{vid}")


def place(coll, products, slug, vid, x, y, rot, seed):
    """Buduje bransoletke w osobnej kolekcji i przesuwa ja na miejsce."""
    sub = bpy.data.collections.new(f"{slug}-{vid}")
    coll.children.link(sub)
    spec = find_variant(products, slug, vid)
    info = b.BUILDERS[spec["type"]](sub, spec, seed)
    T = Matrix.Translation((x, y, 0)) @ Matrix.Rotation(math.radians(rot), 4, "Z")
    for ob in sub.objects:
        ob.matrix_world = T @ ob.matrix_world
    return info


def poisson(rng, w, h, radii):
    """Luzno rozsypane koraliki bez kolizji. Zwraca [(x, y, r), ...]."""
    out = []
    for r in radii:
        for _ in range(500):
            x, y = rng.uniform(-w / 2, w / 2), rng.uniform(-h / 2, h / 2)
            if all((x - a) ** 2 + (y - c) ** 2 > (r + e + 0.06) ** 2 for a, c, e in out):
                out.append((x, y, r))
                break
    return out


def scatter(coll, seed, mats, count, w, h, rmin, rmax, shape="round"):
    rng = random.Random(seed)
    radii = sorted((rng.uniform(rmin, rmax) for _ in range(count)), reverse=True)
    for i, (x, y, r) in enumerate(poisson(rng, w, h, radii)):
        mat = b.stone_mat(mats[i % len(mats)], rng.randrange(3))
        mesh = b.bead_mesh(shape, i % 5 if shape != "round" else i % 3)
        rot = Matrix.Rotation(rng.uniform(0, 6.28), 4, Vector((rng.gauss(0, 1), rng.gauss(0, 1), rng.gauss(0, 0.4))).normalized())
        if mats[i % len(mats)] in b.LAYERED and shape == "round":
            rot = b.layered_rot(rng)
        if shape != "round":
            rot = Matrix.Rotation(rng.uniform(0, 6.28), 4, "Z")
        lift = r * (0.82 if shape != "round" else 1.0)
        ob = b.obj_from_mesh(mesh, coll, mat, Matrix.Translation((x, y, lift)) @ rot @ Matrix.Scale(r, 4))
        ob.name = f"loose_{i}"


def coil(coll, cord_key, cx, cy, turns=7, r0=0.35, pitch=0.105):
    """Plaska cewka sznurka."""
    _, tr = b.CORD_COLORS[cord_key]
    pts = []
    N = int(turns * 40)
    for i in range(N + 1):
        a = i / 40 * 2 * math.pi
        rr = r0 + pitch * a / (2 * math.pi)
        pts.append(Vector((cx + rr * math.cos(a), cy + rr * math.sin(a), tr)))
    return pts


def scene_hero(coll, cam, products, sc):
    place(coll, products, "okruch", "koniak", -3.7, -1.7, 150, 21)
    place(coll, products, "lawica", "8mm", 4.2, -0.5, -28, 7)
    place(coll, products, "rzemien", "naturalna", -0.4, 7.4, -40, 12)
    sc.render.resolution_x, sc.render.resolution_y = 1800, 1400
    tgt = Vector((0.75, 0.7, 0.2))
    b.aim(cam, tgt + Vector((-2.2, -22.8, 19.6)), tgt, 66, fstop=6.3, focus=Vector((-1.8, -3.2, 0.4)))


def scene_kamien(coll, cam, products, sc):
    scatter(coll, 5, ["lapis", "krzemien", "nefryt", "amazonit", "obsydian", "kwarc", "tygrysie_oko", "krzemien"], 130, 10.5, 13, 0.3, 0.55)
    sc.render.resolution_x, sc.render.resolution_y = 1100, 1375
    tgt = Vector((0, 0, 0.3))
    b.aim(cam, tgt + Vector((-1, -9.5, 16.5)), tgt, 85, fstop=4.5, focus=tgt + Vector((0, -0.5, 0.2)))


def scene_bursztyn(coll, cam, products, sc):
    scatter(coll, 11, ["bursztyn_koniak", "bursztyn_miod", "bursztyn_krolewski", "bursztyn_koniak", "bursztyn_miod"], 90, 10.5, 13, 0.4, 0.68, shape="nugget")
    sc.render.resolution_x, sc.render.resolution_y = 1100, 1375
    tgt = Vector((0, 0, 0.3))
    b.aim(cam, tgt + Vector((-1, -9.5, 16.5)), tgt, 85, fstop=4.5, focus=tgt + Vector((0, -0.5, 0.2)))


def scene_drewno(coll, cam, products, sc):
    scatter(coll, 17, ["dab_bagienny", "oliwka", "orzech", "oliwka", "orzech"], 120, 10.5, 13, 0.32, 0.56)
    sc.render.resolution_x, sc.render.resolution_y = 1100, 1375
    tgt = Vector((0, 0, 0.3))
    b.aim(cam, tgt + Vector((-1, -9.5, 16.5)), tgt, 85, fstop=4.5, focus=tgt + Vector((0, -0.5, 0.2)))


def scene_skora(coll, cam, products, sc):
    place(coll, products, "rzemien", "koniak", -1.6, 2.0, 30, 31)
    place(coll, products, "wezel", "ciemna", 2.6, -3.0, 120, 33)
    pts = coil(coll, "linen", -3.3, -4.0, turns=9, r0=0.28)
    b.obj_from_mesh(b.tube_mesh("len", pts, b.CORD_COLORS["linen"][1], sides=8, uv_scale=2.0), coll, b.cord_mat("linen"))
    sc.render.resolution_x, sc.render.resolution_y = 1100, 1375
    tgt = Vector((0, -0.8, 0.3))
    b.aim(cam, tgt + Vector((-1.5, -13, 22)), tgt, 85, fstop=5.6, focus=tgt + Vector((0, -1.2, 0.3)))


def scene_pracownia(coll, cam, products, sc):
    """Bransoletka w trakcie nawlekania: cewka lnu, nic z koralikami i rozsypane kamienie."""
    rng = random.Random(4)
    cord = "linen"
    r = b.CORD_COLORS[cord][1]
    cx, cy = -6.1, 1.8
    pts = coil(coll, cord, cx, cy, turns=11, r0=0.3, pitch=0.106)
    last = pts[-1]
    # wyjscie z cewki w strone kadru
    ctrl = [last, Vector((-2.9, 2.2, r)), Vector((-0.8, 0.2, r)), Vector((2.0, -0.4, r)), Vector((4.3, 0.7, r)), Vector((6.4, 0.1, r))]
    path = []
    for i in range(len(ctrl) - 1):
        p0 = ctrl[max(i - 1, 0)]
        p1, p2 = ctrl[i], ctrl[i + 1]
        p3 = ctrl[min(i + 2, len(ctrl) - 1)]
        for k in range(30):
            t = k / 30
            path.append(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t + (-p0 + 3 * p1 - 3 * p2 + p3) * t ** 3))
    path.append(ctrl[-1])
    b.obj_from_mesh(b.tube_mesh("len", pts + path, r, sides=8, uv_scale=2.0), coll, b.cord_mat(cord))
    # koraliki juz nawleczone, od prawego konca
    d = 0.8
    s = 0.0
    lengths = [0.0]
    for i in range(1, len(path)):
        lengths.append(lengths[-1] + (path[i] - path[i - 1]).length)
    total = lengths[-1]
    placed = 0
    while placed < 9:
        target = total - 1.2 - placed * (d + 0.02)
        i = min(range(len(lengths)), key=lambda q: abs(lengths[q] - target))
        p = path[i]
        tang = path[min(i + 1, len(path) - 1)] - path[max(i - 1, 0)]
        m = b.aligned(Vector((p.x, p.y, d / 2)), tang, d / 2, 0, rng, free=True, layered=True)
        b.obj_from_mesh(b.bead_mesh("round", placed % 3), coll, b.stone_mat("krzemien", rng.randrange(3)), m)
        placed += 1
    # rozsypane kamienie czekajace na nawleczenie
    loose = [(-1.2, -3.6), (0.3, -4.7), (1.6, -3.2), (3.1, -4.3), (-2.8, -4.9), (4.6, -3.0), (2.4, -5.6), (-0.6, -6.1), (5.6, -5.0), (-3.9, -2.8), (6.8, -3.4)]
    for i, (x, y) in enumerate(loose):
        m = b.aligned(Vector((x, y, d / 2)), Vector((1, 0, 0)), d / 2, 0, rng, layered=True)
        b.obj_from_mesh(b.bead_mesh("round", i % 3), coll, b.stone_mat("krzemien", rng.randrange(3)), m)
    sc.render.resolution_x, sc.render.resolution_y = 1800, 1100
    tgt = Vector((0.1, -1.0, 0.2))
    b.aim(cam, tgt + Vector((0.5, -17, 21)), tgt, 62, fstop=7.1, focus=tgt + Vector((1.0, 0.6, 0.2)))


SCENES = {
    "dom-hero": scene_hero,
    "kamien": scene_kamien,
    "bursztyn": scene_bursztyn,
    "drewno": scene_drewno,
    "skora": scene_skora,
    "pracownia": scene_pracownia,
}


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--only", default="")
    ap.add_argument("--samples", type=int, default=160)
    ap.add_argument("--scale", type=float, default=1.0)
    args = ap.parse_args(argv)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    products = json.loads(b.DATA.read_text(encoding="utf-8"))
    sc, cam = b.setup_scene(args.samples, args.scale)
    wanted = [w for w in args.only.split(",") if w]
    for name, fn in SCENES.items():
        if wanted and name not in wanted:
            continue
        coll = bpy.data.collections.new(name)
        sc.collection.children.link(coll)
        fn(coll, cam, products, sc)
        sc.render.resolution_percentage = int(args.scale * 100)
        b.render_to(sc, out / f"{name}.png")
        print("RENDER", name, flush=True)
        for child in list(coll.children):
            b.clear_collection(child)
            bpy.data.collections.remove(child)
        b.clear_collection(coll)
        bpy.data.collections.remove(coll)


if __name__ == "__main__":
    main()
