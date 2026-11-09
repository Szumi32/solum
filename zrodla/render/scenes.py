"""Ujecia sklepu: hero strony glownej, kafelki serii i stol pracowni.

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


def find_model(products, slug):
    for p in products:
        if p["slug"] == slug:
            return p["variants"][0]["model"]
    raise KeyError(slug)


def place(coll, products, slug, x, y, rot, seed):
    """Buduje produkt w osobnej kolekcji i przesuwa go na miejsce."""
    sub = bpy.data.collections.new(slug)
    coll.children.link(sub)
    spec = find_model(products, slug)
    info = b.BUILDERS[spec["type"]](sub, spec, seed)
    T = Matrix.Translation((x, y, 0)) @ Matrix.Rotation(math.radians(rot), 4, "Z")
    for ob in sub.objects:
        ob.matrix_world = T @ ob.matrix_world
    return info


def poisson(rng, w, h, radii):
    """Luzno rozsypane koraliki bez kolizji. Zwraca [(x, y, r), ...]."""
    out = []
    for r in radii:
        for _ in range(600):
            x, y = rng.uniform(-w / 2, w / 2), rng.uniform(-h / 2, h / 2)
            if all((x - a) ** 2 + (y - c) ** 2 > (r + e + 0.05) ** 2 for a, c, e in out):
                out.append((x, y, r))
                break
    return out


def scatter(coll, seed, mats, count, w, h, rmin, rmax, shape, balls=0):
    rng = random.Random(seed)
    radii = [rng.uniform(rmin, rmax) for _ in range(count)] + [0.1] * balls
    radii.sort(reverse=True)
    G = b.gold()
    k = 0
    for x, y, r in poisson(rng, w, h, radii):
        if r == 0.1:
            b.obj_from_mesh(b.bead_mesh("round", 0), coll, G, Matrix.Translation((x, y, r)) @ Matrix.Scale(r, 4))
            continue
        mat = b.stone_mat(mats[k % len(mats)], rng.randrange(3))
        k += 1
        axis = Vector((rng.gauss(0, 1), rng.gauss(0, 1), rng.gauss(0, 0.45))).normalized()
        rot = axis.to_track_quat("Z", "Y").to_matrix().to_4x4() @ Matrix.Rotation(rng.uniform(0, 6.28), 4, "Z")
        lift = r * (1.0 if shape != "kostka" else 1.15)
        b.obj_from_mesh(b.facet_mesh(shape, k % 4), coll, mat, Matrix.Translation((x, y, lift)) @ rot @ Matrix.Scale(r, 4))


def tile(sc, cam, dist=1.0):
    sc.render.resolution_x, sc.render.resolution_y = 1100, 1375
    tgt = Vector((0, 0, 0.3))
    b.aim(cam, tgt + Vector((-1, -9.5, 16.5)) * dist, tgt, 85, fstop=4.5, focus=tgt + Vector((0, -0.5, 0.2)))


def scene_hero(coll, cam, products, sc):
    place(coll, products, "blue-amazonit", -3.4, -1.7, -100, 21)
    place(coll, products, "tygrysie-oko", 4.0, -1.2, 0, 7)
    place(coll, products, "brelok-rose-quartz", 0.6, 6.6, 76, 12)
    sc.render.resolution_x, sc.render.resolution_y = 1800, 1400
    tgt = Vector((0.5, 1.1, 0.2))
    b.aim(cam, tgt + Vector((-2.2, -22.8, 19.6)), tgt, 66, fstop=6.3, focus=Vector((-2.0, -3.4, 0.4)))


def scene_fasetowane(coll, cam, products, sc):
    scatter(coll, 5, ["amazonit_nieb", "turmalin_rozowy", "sloneczny", "lapis", "amazonit_nieb"], 120, 10.5, 13, 0.4, 0.5, "rondel", balls=110)
    tile(sc, cam)


def scene_drobne(coll, cam, products, sc):
    scatter(coll, 11, ["tygrysie_oko", "chryzokola", "turmalin", "obsydian", "ksiezycowy"], 260, 7.5, 9.5, 0.22, 0.27, "kulka", balls=40)
    tile(sc, cam, 0.68)


def scene_kostki(coll, cam, products, sc):
    scatter(coll, 17, ["kalcyt", "kwarc_dymny", "ametyst_jasny", "akwamaryn", "labradoryt"], 180, 10.5, 13, 0.28, 0.33, "kostka")
    tile(sc, cam)


def scene_zawieszki(coll, cam, products, sc):
    info = place(coll, products, "rubin-w-zoisycie", -1.8, 0.0, 0, 31)
    place(coll, products, "onyks-hamsa", -3.4, -6.6, 12, 33)
    sc.render.resolution_x, sc.render.resolution_y = 1100, 1375
    tgt = Vector((0.9, -2.1, 0.2))
    b.aim(cam, tgt + Vector((1.2, -8.4, 13)), tgt, 85, fstop=6.3, focus=tgt + Vector((0.4, 0.6, 0.1)))


def scene_breloki(coll, cam, products, sc):
    place(coll, products, "brelok-tygrysie-oko", -3.2, 0.2, -4, 41)
    place(coll, products, "brelok-rose-quartz", 0.2, -0.6, 6, 42)
    place(coll, products, "brelok-ametyst", 3.6, 0.4, 2, 43)
    sc.render.resolution_x, sc.render.resolution_y = 1100, 1375
    tgt = Vector((0.2, 0.2, 0.3))
    b.aim(cam, tgt + Vector((-0.8, -13.8, 27.5)), tgt, 85, fstop=8)


def scene_pracownia(coll, cam, products, sc):
    """Bransoletka w trakcie nawlekania: nic, nawleczone rondle i rozsypane koraliki."""
    rng = random.Random(4)
    G = b.gold()
    thread = b.metal_mat("nic", "#3a3631", 0.5)
    w = 0.9
    ctrl = [Vector((-9.5, 1.9, w / 2)), Vector((-5.5, 2.4, w / 2)), Vector((-1.8, 0.3, w / 2)), Vector((2.0, -0.4, w / 2)), Vector((5.0, 0.9, w / 2)), Vector((7.4, 0.2, w / 2))]
    path = []
    for i in range(len(ctrl) - 1):
        p0 = ctrl[max(i - 1, 0)]
        p1, p2 = ctrl[i], ctrl[i + 1]
        p3 = ctrl[min(i + 2, len(ctrl) - 1)]
        for k in range(30):
            t = k / 30
            path.append(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t + (-p0 + 3 * p1 - 3 * p2 + p3) * t ** 3))
    path.append(ctrl[-1])
    b.obj_from_mesh(b.tube_mesh("nic", path, 0.02, sides=6), coll, thread)
    acc = [0.0]
    for a, c in zip(path, path[1:]):
        acc.append(acc[-1] + (c - a).length)
    pitch = w * 0.66 + 0.19
    for n in range(13):
        target = acc[-1] - 0.9 - n * pitch
        i = min(range(len(acc)), key=lambda q: abs(acc[q] - target))
        p = path[i]
        tang = path[min(i + 1, len(path) - 1)] - path[max(i - 1, 0)]
        m = b.aligned(Vector((p.x, p.y, w / 2)), tang, w / 2, rng.uniform(0, 6.28), rng)
        b.obj_from_mesh(b.facet_mesh("rondel", n % 5), coll, b.stone_mat("amazonit_nieb", rng.randrange(3)), m)
        j = min(range(len(acc)), key=lambda q: abs(acc[q] - (target - pitch / 2)))
        q = path[j]
        b.obj_from_mesh(b.bead_mesh("round", 0), coll, G, Matrix.Translation((q.x, q.y, w / 2)) @ Matrix.Scale(0.105, 4))
    loose = poisson(rng, 17, 5.2, [0.45] * 16 + [0.1] * 34)
    for k, (x, y, r) in enumerate(loose):
        y2 = y - 4.3
        if r == 0.1:
            b.obj_from_mesh(b.bead_mesh("round", 0), coll, G, Matrix.Translation((x, y2, r)) @ Matrix.Scale(r, 4))
        else:
            axis = Vector((rng.gauss(0, 1), rng.gauss(0, 1), rng.gauss(0, 0.4))).normalized()
            rot = axis.to_track_quat("Z", "Y").to_matrix().to_4x4()
            b.obj_from_mesh(b.facet_mesh("rondel", k % 5), coll, b.stone_mat("amazonit_nieb", rng.randrange(3)), Matrix.Translation((x, y2, r)) @ rot @ Matrix.Scale(r, 4))
    sc.render.resolution_x, sc.render.resolution_y = 1800, 1100
    tgt = Vector((0.1, -1.0, 0.2))
    b.aim(cam, tgt + Vector((0.5, -17, 21)), tgt, 62, fstop=7.1, focus=tgt + Vector((1.0, 0.6, 0.2)))


SCENES = {
    "dom-hero": scene_hero,
    "fasetowane": scene_fasetowane,
    "drobne": scene_drobne,
    "kostki": scene_kostki,
    "zawieszki": scene_zawieszki,
    "breloki": scene_breloki,
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
    out = Path(args.out).resolve()
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
