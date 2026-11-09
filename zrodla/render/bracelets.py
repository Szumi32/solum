"""Modele i rendery bransoletek SOLUM (Blender + Cycles).

Dane: zrodla/dane/products.json. Jednostki sceny: 1 = 1 cm.

Uzycie:
  blender -b -P bracelets.py -- --out <folder> [--only slug[:wariant],...] [--shots hero,macro,top,detail]
                                [--samples 128] [--scale 1.0] [--glb] [--no-render]
"""
import argparse
import json
import math
import random
import sys
from pathlib import Path

import bpy
import bmesh
from mathutils import Matrix, Vector, noise as mnoise

HERE = Path(__file__).resolve().parent
TEX = HERE / "tex"
DATA = HERE.parent / "dane" / "products.json"

def srgb(h):
    h = h.lstrip("#")
    out = []
    for i in (0, 2, 4):
        c = int(h[i:i + 2], 16) / 255
        out.append(c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4)
    return (*out, 1.0)


# ------------------------------------------------------------------ materialy


_IMG = {}


def load_image(name, colorspace):
    key = name
    if key not in _IMG:
        img = bpy.data.images.load(str(TEX / f"{name}.png"), check_existing=True)
        img.colorspace_settings.name = colorspace
        _IMG[key] = img
    return _IMG[key]


def new_mat(name):
    m = bpy.data.materials.get(name)
    if m:
        return m, None, None
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    bsdf = nt.nodes["Principled BSDF"]
    return m, nt, bsdf


def img_node(nt, name, colorspace, loc):
    n = nt.nodes.new("ShaderNodeTexImage")
    n.image = load_image(name, colorspace)
    n.location = loc
    return n


def attach_maps(nt, bsdf, base, normal=False, normal_strength=1.0):
    col = img_node(nt, f"{base}_color", "sRGB", (-700, 300))
    nt.links.new(col.outputs["Color"], bsdf.inputs["Base Color"])
    orm = img_node(nt, f"{base}_orm", "Non-Color", (-700, 0))
    sep = nt.nodes.new("ShaderNodeSeparateColor")
    sep.location = (-400, 0)
    nt.links.new(orm.outputs["Color"], sep.inputs[0])
    nt.links.new(sep.outputs[1], bsdf.inputs["Roughness"])
    nt.links.new(sep.outputs[2], bsdf.inputs["Metallic"])
    if normal:
        nm = img_node(nt, f"{base}_normal", "Non-Color", (-700, -300))
        n = nt.nodes.new("ShaderNodeNormalMap")
        n.inputs["Strength"].default_value = normal_strength
        nt.links.new(nm.outputs["Color"], n.inputs["Color"])
        nt.links.new(n.outputs["Normal"], bsdf.inputs["Normal"])
    return col


STONE = {
    "amazonit_nieb": dict(frost=True, sss=0.25, radius=(0.05, 0.1, 0.1)),
    "turmalin_rozowy": dict(frost=True, sss=0.2, radius=(0.1, 0.08, 0.1)),
    "sloneczny": dict(frost=True),
    "lapis": dict(),
    "tygrysie_oko": dict(aniso=0.75),
    "chryzokola": dict(),
    "turmalin": dict(trans=0.25, ior=1.62),
    "obsydian": dict(),
    "ksiezycowy": dict(sss=0.8, radius=(0.2, 0.2, 0.25)),
    "kalcyt": dict(trans=0.15, sss=0.6, radius=(0.25, 0.18, 0.08)),
    "kwarc_dymny": dict(trans=0.75, ior=1.54, absorb="#4a3626", absorb_d=1.4),
    "ametyst_jasny": dict(trans=0.2, sss=0.4, radius=(0.14, 0.12, 0.14)),
    "ametyst_ciemny": dict(trans=0.35, ior=1.54, absorb="#5a3a90", absorb_d=0.8),
    "akwamaryn": dict(trans=0.8, ior=1.57, absorb="#9adcec", absorb_d=0.18),
    "labradoryt": dict(trans=0.45, ior=1.56),
    "rubin_zoisyt": dict(),
    "kwarc": dict(trans=0.45, ior=1.54, sss=0.5, radius=(0.15, 0.08, 0.09)),
    "jaspis": dict(),
    "agat": dict(),
    "serpentyn": dict(sss=0.35, radius=(0.12, 0.15, 0.06)),
    "krysztal": dict(trans=0.85, ior=1.54),
}


def stone_mat(name, tex_i):
    mname = f"{name}_{tex_i}"
    m, nt, bsdf = new_mat(mname)
    if nt is None:
        return m
    spec = STONE[name]
    attach_maps(nt, bsdf, mname)
    bsdf.inputs["IOR"].default_value = spec.get("ior", 1.55)
    if spec.get("trans"):
        bsdf.inputs["Transmission Weight"].default_value = spec["trans"]
    if spec.get("sss"):
        bsdf.inputs["Subsurface Weight"].default_value = spec["sss"]
        bsdf.inputs["Subsurface Radius"].default_value = spec.get("radius", (0.1, 0.1, 0.1))
        bsdf.inputs["Subsurface Scale"].default_value = 1.0
    if spec.get("aniso"):
        bsdf.inputs["Anisotropic"].default_value = spec["aniso"]
    if spec.get("absorb"):
        vol = nt.nodes.new("ShaderNodeVolumeAbsorption")
        vol.inputs["Color"].default_value = srgb(spec["absorb"])
        vol.inputs["Density"].default_value = spec.get("absorb_d", 0.5)
        nt.links.new(vol.outputs[0], nt.nodes["Material Output"].inputs["Volume"])
    if not spec.get("trans") and not spec.get("frost"):
        bsdf.inputs["Coat Weight"].default_value = 0.35
        bsdf.inputs["Coat Roughness"].default_value = 0.06
    return m


# ------------------------------------------------------------------ siatki


def obj_from_mesh(mesh, coll, mat=None, matrix=None, name=None):
    ob = bpy.data.objects.new(name or mesh.name, mesh)
    coll.objects.link(ob)
    if mat is not None:
        if not mesh.materials:
            mesh.materials.append(mat)
        else:
            ob.material_slots[0].link = "OBJECT"
            ob.material_slots[0].material = mat
    if matrix is not None:
        ob.matrix_world = matrix
    return ob


_BEADS = {}


def bead_mesh(shape, variant, seg=48, rings=32):
    """Jednostkowy koralik (promien 1). Te same siatki sa wspoldzielone, co zmniejsza plik GLB."""
    key = (shape, variant)
    if key in _BEADS:
        return _BEADS[key]
    me = bpy.data.meshes.new(f"bead_{shape}_{variant}")
    bm = bmesh.new()
    bm.loops.layers.uv.new("UVMap")
    if shape == "pebble":
        seg, rings = 96, 64
    bmesh.ops.create_uvsphere(bm, u_segments=seg, v_segments=rings, radius=1.0, calc_uvs=True)
    offs = Vector((variant * 7.1 + 3.3, variant * 3.7 + 1.1, variant * 5.3))
    for v in bm.verts:
        p = v.co.copy()
        if shape == "drop":
            # kropla: waska u gory, zaokraglona u dolu
            k = 1 - 0.8 * max(0.0, p.z) ** 1.4
            p = Vector((p.x * k, p.y * k, p.z * 1.7))
        elif shape == "pebble":
            n1 = mnoise.noise(p * 0.8 + offs)
            s = 1 + 0.24 * n1
            p = Vector((p.x * s * 1.08, p.y * s * (0.84 + 0.12 * math.sin(variant * 1.7)), p.z * s * 0.8))
        elif shape == "peg":
            e = 0.34
            rho = max(math.hypot(p.x, p.y), 1e-6)
            rho2 = rho ** e
            p = Vector((p.x / rho * rho2, p.y / rho * rho2, math.copysign(abs(p.z) ** e, p.z)))
        elif shape == "round":
            # bardzo delikatna niedoskonalosc, recznie szlifowany kamien nie jest idealna kula
            s = 1 + 0.008 * mnoise.noise(p * 1.4 + offs)
            p = p * s
        v.co = p
    for f in bm.faces:
        f.smooth = True
    bm.to_mesh(me)
    bm.free()
    _BEADS[key] = me
    return me


def tube_mesh(name, path, radius, sides=8, closed=False, uv_scale=1.0, profile=None, twist=0.0, up=None):
    """Rura po krzywej z transportem rownoleglym. profile = (a, b) daje przekroj eliptyczny."""
    pts = [Vector(p) for p in path]
    n = len(pts)
    tangents = []
    for i in range(n):
        if closed:
            t = pts[(i + 1) % n] - pts[(i - 1) % n]
        else:
            t = pts[min(i + 1, n - 1)] - pts[max(i - 1, 0)]
        tangents.append(t.normalized())
    ref = Vector(up) if up else (Vector((0, 0, 1)) if abs(tangents[0].z) < 0.9 else Vector((1, 0, 0)))
    normal = (ref - tangents[0] * ref.dot(tangents[0])).normalized()
    verts, faces, uvs = [], [], []
    length = 0.0
    rings = []
    for i in range(n):
        if i > 0:
            length += (pts[i] - pts[i - 1]).length
            rot = tangents[i - 1].rotation_difference(tangents[i])
            normal = rot @ normal
            normal = (normal - tangents[i] * normal.dot(tangents[i])).normalized()
        b = tangents[i].cross(normal)
        a_r, b_r = profile if profile else (radius, radius)
        ang0 = twist * length
        ring = []
        for s in range(sides + 1):
            a = 2 * math.pi * s / sides + ang0
            off = normal * (math.cos(a) * a_r) + b * (math.sin(a) * b_r)
            verts.append(pts[i] + off)
            ring.append(len(verts) - 1)
            uvs.append((s / sides * 0.5, length * uv_scale))
        rings.append(ring)
    last = n if closed else n - 1
    for i in range(last):
        r0, r1 = rings[i], rings[(i + 1) % n]
        for s in range(sides):
            faces.append((r0[s], r0[s + 1], r1[s + 1], r1[s]))
    if not closed:
        # zamkniete konce: bez nich w makro widac ciemne wnetrze rury
        for ring_ids, centre, flip in ((rings[0], pts[0], True), (rings[-1], pts[-1], False)):
            verts.append(centre)
            uvs.append((0.25, 0.0))
            c = len(verts) - 1
            for s in range(sides):
                f = (ring_ids[s + 1], ring_ids[s], c) if flip else (ring_ids[s], ring_ids[s + 1], c)
                faces.append(f)
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(v) for v in verts], [], faces)
    uvl = me.uv_layers.new(name="UVMap")
    for poly in me.polygons:
        poly.use_smooth = True
        for li in poly.loop_indices:
            uvl.data[li].uv = uvs[me.loops[li].vertex_index]
    me.update()
    return me


def close_curve(a, phase, loose=1.0):
    """Lekko nieregularny obrys, bo bransoletka odlozona na stol nie jest idealnym okregiem."""
    def fn(t):
        wob = 1 + loose * (0.018 * math.sin(2 * t + phase) + 0.01 * math.sin(3 * t + phase * 1.7))
        return Vector((a * wob * math.cos(t), a * wob * 0.965 * math.sin(t)))
    return fn


def arc_table(fn, steps=2000):
    out = [(0.0, 0.0)]
    prev = fn(0.0)
    total = 0.0
    for i in range(1, steps + 1):
        t = 2 * math.pi * i / steps
        p = fn(t)
        total += (p - prev).length
        out.append((total, t))
        prev = p
    return out, total


def t_at(table, s):
    lo, hi = 0, len(table) - 1
    while hi - lo > 1:
        m = (lo + hi) // 2
        if table[m][0] < s:
            lo = m
        else:
            hi = m
    a, b = table[lo], table[hi]
    k = (s - a[0]) / max(b[0] - a[0], 1e-9)
    return a[1] + (b[1] - a[1]) * k


LAYERED = {"tygrysie_oko", "agat"}


def layered_rot(rng):
    """Normalna warstw (lokalna os X) lezy prawie poziomo, wiec z gory widac pasma, a nie tarcze."""
    a = rng.uniform(0, 6.28)
    x = Vector((math.cos(a), math.sin(a), rng.uniform(-0.3, 0.3))).normalized()
    z = Vector((0, 0, 1))
    y = z.cross(x).normalized()
    z = x.cross(y).normalized()
    m = Matrix((x, y, z)).transposed().to_4x4()
    return m @ Matrix.Rotation(rng.uniform(0, 6.28), 4, "X")


def aligned(pos, tangent, scale, spin, rng, free=False, tilt=0.0, layered=False):
    if layered:
        rot = layered_rot(rng)
    elif free:
        rot = Matrix.Rotation(rng.uniform(0, 6.28), 4, Vector((rng.gauss(0, 1), rng.gauss(0, 1), rng.gauss(0, 1))).normalized())
    else:
        z = tangent.normalized()
        rot = z.to_track_quat("Z", "Y").to_matrix().to_4x4() @ Matrix.Rotation(spin, 4, "Z")
    if isinstance(scale, (int, float)):
        s = Matrix.Scale(scale, 4)
    else:
        s = Matrix.Diagonal((*scale, 1))
    return Matrix.Translation(pos) @ rot @ s


# ------------------------------------------------------------------ metal i koraliki fasetowane


def metal_mat(name, color, rough):
    m, nt, bsdf = new_mat(name)
    if nt is None:
        return m
    bsdf.inputs["Base Color"].default_value = srgb(color)
    bsdf.inputs["Metallic"].default_value = 1.0
    bsdf.inputs["Roughness"].default_value = rough
    return m


def gold():
    return metal_mat("zloto", "#d9b56c", 0.24)


def steel():
    return metal_mat("stal", "#b6b0a4", 0.3)


def spherical_uv(bm):
    """Mapowanie kuliste liczone dla kazdej scianki osobno, bez smug na szwie tekstury."""
    uv = bm.loops.layers.uv.active or bm.loops.layers.uv.new("UVMap")
    for f in bm.faces:
        us = []
        for l in f.loops:
            n = l.vert.co.normalized()
            u = (math.atan2(n.y, n.x) / (2 * math.pi)) % 1.0
            v = math.acos(max(-1.0, min(1.0, n.z))) / math.pi
            us.append(u)
            l[uv].uv = (u, 1.0 - v)
        if max(us) - min(us) > 0.5:
            for l in f.loops:
                if l[uv].uv.x < 0.5:
                    l[uv].uv.x += 1.0


FACET_RINGS = {
    # (promien, wysokosc) kolejnych rzedow scianek; rondel jest spłaszczony wzdluz osi otworu
    "rondel": (14, [(0.46, 0.66), (0.88, 0.38), (1.0, 0.0), (0.88, -0.38), (0.46, -0.66)]),
    "kulka": (12, [(0.5, 0.86), (0.93, 0.36), (0.93, -0.36), (0.5, -0.86)]),
}


def facet_mesh(shape, variant):
    """Koralik szlifowany: scianki przesuniete co rzad i plaskie cieniowanie, jak na zdjeciach produktow."""
    key = ("facet", shape, variant)
    if key in _BEADS:
        return _BEADS[key]
    rng = random.Random(variant * 97 + len(shape))
    me = bpy.data.meshes.new(f"facet_{shape}_{variant}")
    bm = bmesh.new()
    bm.loops.layers.uv.new("UVMap")
    if shape == "kostka":
        c = 0.68
        pts = []
        for sx in (-1, 1):
            for sy in (-1, 1):
                for sz in (-1, 1):
                    pts += [(sx, sy, sz * c), (sx, sy * c, sz), (sx * c, sy, sz)]
        verts = [bm.verts.new([q + rng.uniform(-0.055, 0.055) for q in p]) for p in pts]
        bmesh.ops.convex_hull(bm, input=verts)
        bmesh.ops.dissolve_limit(bm, angle_limit=0.02, verts=bm.verts[:], edges=bm.edges[:])
    else:
        seg, profile = FACET_RINGS[shape]
        rings = []
        for i, (r, z) in enumerate(profile):
            ring = []
            for j in range(seg):
                a = (j + 0.5 * (i % 2)) / seg * 2 * math.pi
                rr = r * (1 + rng.uniform(-0.018, 0.018))
                ring.append(bm.verts.new((rr * math.cos(a), rr * math.sin(a), z + rng.uniform(-0.012, 0.012))))
            rings.append(ring)
        for i in range(len(rings) - 1):
            a, b = rings[i], rings[i + 1]
            for j in range(seg):
                j2 = (j + 1) % seg
                if i % 2 == 0:
                    bm.faces.new((a[j], a[j2], b[j]))
                    bm.faces.new((b[j], a[j2], b[j2]))
                else:
                    bm.faces.new((b[j], b[j2], a[j]))
                    bm.faces.new((a[j], b[j2], a[j2]))
        bm.faces.new(rings[0])
        bm.faces.new(rings[-1])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    for f in bm.faces:
        f.smooth = False
    spherical_uv(bm)
    bm.to_mesh(me)
    bm.free()
    _BEADS[key] = me
    return me


def link_mesh(L, W, r):
    key = ("link", L, W, r)
    if key in _BEADS:
        return _BEADS[key]
    s = (L - W) / 2
    R = W / 2
    pts = []
    for i in range(10):
        a = math.pi * i / 9
        pts.append((R * math.cos(a), 0, s + R * math.sin(a)))
    for i in range(10):
        a = math.pi + math.pi * i / 9
        pts.append((R * math.cos(a), 0, -s + R * math.sin(a)))
    me = tube_mesh("ogniwo", pts, r, sides=6, closed=True)
    _BEADS[key] = me
    return me


def chain(coll, path, mat, L=0.27, W=0.18, r=0.024):
    """Lancuszek po krzywej: co drugie ogniwo lezy, co drugie stoi. Wszystkie dziela jedna siatke."""
    pts = [Vector(p) for p in path]
    acc = [0.0]
    for a, b in zip(pts, pts[1:]):
        acc.append(acc[-1] + (b - a).length)
    step = L * 0.72
    me = link_mesh(L, W, r)
    i = 0
    for k in range(int(acc[-1] / step)):
        target = (k + 0.5) * step
        while acc[i + 1] < target:
            i += 1
        f = (target - acc[i]) / max(acc[i + 1] - acc[i], 1e-9)
        pos = pts[i].lerp(pts[i + 1], f)
        tang = (pts[i + 1] - pts[i]).normalized()
        standing = k % 2 == 1
        z = max(pos.z, (W / 2 + r) if standing else r)
        rot = tang.to_track_quat("Z", "Y").to_matrix().to_4x4() @ Matrix.Rotation(math.pi / 2 if standing else 0, 4, "Z")
        obj_from_mesh(me, coll, mat, Matrix.Translation((pos.x, pos.y, z)) @ rot)
    return pts[-1], (pts[-1] - pts[-2]).normalized()


def ring_at(coll, pos, mat, R=0.14, wire=0.03):
    pts = [(pos.x + R * math.cos(i / 24 * 6.2832), pos.y + R * math.sin(i / 24 * 6.2832), max(pos.z, wire)) for i in range(24)]
    return obj_from_mesh(tube_mesh("kolko", pts, wire, sides=6, closed=True), coll, mat)


def arc_path(p0, d0, length, bend, z0, z1=0.03, n=44):
    pts = []
    a0 = math.atan2(d0.y, d0.x)
    p = Vector((p0.x, p0.y, 0))
    ds = length / n
    for i in range(n + 1):
        k = i / n
        z = z1 + (z0 - z1) * max(0.0, 1 - k * 5) ** 2
        pts.append((p.x, p.y, z))
        a = a0 + bend * k + 0.12 * math.sin(k * 7)
        p = p + Vector((math.cos(a), math.sin(a), 0)) * ds
    return pts


def lobster(coll, pos, d, mat):
    """Karabinczyk: wydluzona petla, dzwigienka i kolko."""
    side = Vector((-d.y, d.x, 0))
    a, b = 0.31, 0.185
    z = 0.06
    pts = []
    for i in range(48):
        t = i / 48 * 6.2832
        u = a * math.cos(t)
        v = b * math.sin(t) * (1 - 0.3 * math.cos(t))
        q = pos + d * u + side * v
        pts.append((q.x, q.y, z))
    obj_from_mesh(tube_mesh("karabinczyk", pts, 0.05, sides=8, closed=True, profile=(0.04, 0.056)), coll, mat)
    lever = pos - d * 0.04 + side * 0.23
    m = Matrix.Translation((lever.x, lever.y, z)) @ d.to_track_quat("Z", "Y").to_matrix().to_4x4() @ Matrix.Diagonal((0.035, 0.035, 0.1, 1))
    obj_from_mesh(bead_mesh("peg", 0), coll, mat, m)
    ring_at(coll, Vector((pos.x, pos.y, 0)) - d * (a + 0.1) + Vector((0, 0, 0.03)), mat, R=0.1, wire=0.024)


def at(fn, table, s):
    t = t_at(table, s % table[-1][0])
    p = fn(t)
    q = fn(t + 0.01)
    return Vector((p.x, p.y, 0)), Vector((q.x - p.x, q.y - p.y, 0)).normalized()


def closure(coll, fn, table, total, s0, z, mat, length=3.6, bend=-1.4):
    """Zapiecie jak na zdjeciach: karabinczyk z jednej strony, lancuszek z kropla z drugiej."""
    a, ta = at(fn, table, s0)
    b, tb = at(fn, table, total - s0)
    out = Vector((1, 0, 0))
    da = (out * 0.9 + ta * 0.35).normalized()
    db = (out * 0.9 - tb * 0.35).normalized()
    ring_at(coll, a + da * 0.12 + Vector((0, 0, min(z, 0.2))), mat, R=0.12)
    lobster(coll, a + da * 0.56, da, mat)
    ring_at(coll, b + db * 0.12 + Vector((0, 0, min(z, 0.2))), mat, R=0.12)
    end, tang = chain(coll, arc_path(b + db * 0.2, db, length, bend, min(z, 0.2)), mat)
    m = Matrix.Translation((end.x + tang.x * 0.18, end.y + tang.y * 0.18, 0.09)) @ tang.to_track_quat("Z", "Y").to_matrix().to_4x4() @ Matrix.Scale(0.075, 4)
    obj_from_mesh(bead_mesh("drop", 0), coll, mat, m)
    return a + da, b + db


def build_rondel(coll, spec, seed, ring_r=2.85):
    rng = random.Random(seed)
    w = spec.get("w", 0.82)
    t = w * 0.66
    ball = 0.125
    fn = close_curve(ring_r, seed * 0.77)
    table, total = arc_table(fn)
    gap = 1.7
    usable = total - gap
    s0 = gap / 2
    n = int(usable / (t + 2 * ball * 0.92))
    pitch = usable / n
    G = gold()
    for i in range(n):
        s = s0 + (i + 0.5) * pitch
        pos, tang = at(fn, table, s)
        ww = w * rng.uniform(0.96, 1.04)
        m = aligned(Vector((pos.x, pos.y, ww / 2)), tang, ww / 2, rng.uniform(0, 6.28), rng)
        obj_from_mesh(facet_mesh("rondel", i % 5), coll, stone_mat(spec["mat"], rng.randrange(3)), m)
        if i < n - 1:
            p2, _ = at(fn, table, s + pitch / 2)
            obj_from_mesh(bead_mesh("round", 0), coll, G, Matrix.Translation((p2.x, p2.y, w / 2)) @ Matrix.Scale(ball, 4))
    closure(coll, fn, table, total, s0, w / 2, G)
    return {"radius": ring_r, "height": w, "bead": w, "detail_at": (ring_r + 0.9, -0.2), "detail_k": 1.0}


def build_drobne(coll, spec, seed, ring_r=2.75):
    rng = random.Random(seed)
    d = spec.get("d", 0.5)
    fn = close_curve(ring_r, seed * 0.77)
    table, total = arc_table(fn)
    G = gold()
    hr, hh = 0.2, 0.05
    per = 7
    d_step = d * 0.9
    cycle = per * d_step + 2 * hh
    cycles = int(total / cycle)
    scale = total / (cycles * cycle)
    s = 0.0
    for c in range(cycles):
        for i in range(per):
            s += d_step * scale / 2
            pos, tang = at(fn, table, s)
            m = aligned(Vector((pos.x, pos.y, d / 2)), tang, d / 2, rng.uniform(0, 6.28), rng, layered=False)
            obj_from_mesh(facet_mesh("kulka", (c * per + i) % 5), coll, stone_mat(spec["mat"], rng.randrange(3)), m)
            s += d_step * scale / 2
        s += hh * scale
        pos, tang = at(fn, table, s)
        m = aligned(Vector((pos.x, pos.y, d / 2)), tang, (hr, hr, hh), 0, rng)
        obj_from_mesh(bead_mesh("peg", 0), coll, G, m)
        s += hh * scale
    p, _ = at(fn, table, total * 0.62)
    return {"radius": ring_r, "height": d, "bead": 0.62, "detail_at": (p.x, p.y), "detail_k": 0.55}


def build_kostki(coll, spec, seed, ring_r=2.8):
    rng = random.Random(seed)
    e = spec.get("s", 0.6)
    fn = close_curve(ring_r, seed * 0.77)
    table, total = arc_table(fn)
    n = int(total / (e * 1.02))
    pitch = total / n
    for i in range(n):
        pos, tang = at(fn, table, (i + 0.5) * pitch)
        k = e / 2
        sc = (k * rng.uniform(0.95, 1.06), k * rng.uniform(0.95, 1.06), k * rng.uniform(0.92, 1.0))
        spin = rng.choice((0.0, 0.25, -0.25, 0.5)) + rng.uniform(-0.18, 0.18)
        m = aligned(Vector((pos.x, pos.y, e * 0.56)), tang, sc, spin, rng)
        obj_from_mesh(facet_mesh("kostka", i % 4), coll, stone_mat(spec["mat"], rng.randrange(3)), m)
    p, _ = at(fn, table, total * 0.62)
    return {"radius": ring_r, "height": e, "bead": e, "detail_at": (p.x, p.y), "detail_k": 0.6}


def chaikin(pts, n=2):
    for _ in range(n):
        out = []
        for i, a in enumerate(pts):
            b = pts[(i + 1) % len(pts)]
            out.append((a[0] * 0.75 + b[0] * 0.25, a[1] * 0.75 + b[1] * 0.25))
            out.append((a[0] * 0.25 + b[0] * 0.75, a[1] * 0.25 + b[1] * 0.75))
        pts = out
    return pts


HAMSA = [(0, -0.82), (0.26, -0.80), (0.44, -0.62), (0.50, -0.34), (0.56, -0.10), (0.70, 0.10), (0.76, 0.34), (0.70, 0.46),
         (0.60, 0.40), (0.50, 0.18), (0.44, 0.12), (0.43, 0.52), (0.38, 0.70), (0.29, 0.72), (0.24, 0.56), (0.22, 0.20),
         (0.18, 0.20), (0.17, 0.70), (0.11, 0.88), (0, 0.92)]


def hamsa_mesh():
    key = ("hamsa",)
    if key in _BEADS:
        return _BEADS[key]
    half = HAMSA
    outline = chaikin(half + [(-x, y) for x, y in reversed(half[1:-1])], 2)
    me = bpy.data.meshes.new("hamsa")
    bm = bmesh.new()
    verts = [bm.verts.new((x, y, 0)) for x, y in outline]
    face = bm.faces.new(verts)
    res = bmesh.ops.extrude_face_region(bm, geom=[face])
    moved = [g for g in res["geom"] if isinstance(g, bmesh.types.BMVert)]
    bmesh.ops.translate(bm, verts=moved, vec=(0, 0, 0.07))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    bm.to_mesh(me)
    bm.free()
    _BEADS[key] = me
    return me


def charm_hamsa(coll, pos, d, mat):
    angle = math.atan2(d.y, d.x) - math.pi / 2
    R = Matrix.Rotation(angle, 4, "Z")
    base = Matrix.Translation((pos.x, pos.y, 0.012)) @ R @ Matrix.Scale(0.68, 4)
    obj_from_mesh(hamsa_mesh(), coll, mat, base @ Matrix.Translation((0, 0.86, 0)))
    centre = pos + d * 0.42
    ring_at(coll, Vector((centre.x, centre.y, 0.07)), mat, R=0.11, wire=0.02)
    m = Matrix.Translation((centre.x, centre.y, 0.07)) @ Matrix.Diagonal((0.07, 0.07, 0.035, 1))
    obj_from_mesh(bead_mesh("round", 1), coll, stone_mat("lapis", 0), m)


def charm_kwiat(coll, pos, d, mat):
    centre = pos + d * 0.62
    crystal = stone_mat("krysztal", 0)
    m = Matrix.Translation((centre.x, centre.y, 0.06)) @ Matrix.Diagonal((0.2, 0.2, 0.05, 1))
    obj_from_mesh(bead_mesh("peg", 0), coll, mat, m)
    obj_from_mesh(bead_mesh("round", 1), coll, crystal, Matrix.Translation((centre.x, centre.y, 0.12)) @ Matrix.Diagonal((0.12, 0.12, 0.08, 1)))
    for i in range(6):
        a = i / 6 * 6.2832 + 0.26
        q = centre + Vector((math.cos(a), math.sin(a), 0)) * 0.36
        obj_from_mesh(bead_mesh("round", 2), coll, mat, Matrix.Translation((q.x, q.y, 0.05)) @ Matrix.Diagonal((0.2, 0.2, 0.05, 1)))
        obj_from_mesh(bead_mesh("round", 1), coll, crystal, Matrix.Translation((q.x, q.y, 0.1)) @ Matrix.Diagonal((0.09, 0.09, 0.06, 1)))


def build_zawieszka(coll, spec, seed, ring_r=2.75):
    rng = random.Random(seed)
    w = 0.62
    t = w * 0.66
    fn = close_curve(ring_r, seed * 0.77)
    table, total = arc_table(fn)
    gap = 1.7
    usable = total - gap
    s0 = gap / 2
    n = int(usable / (t * 1.02))
    pitch = usable / n
    G = gold()
    for i in range(n):
        pos, tang = at(fn, table, s0 + (i + 0.5) * pitch)
        ww = w * rng.uniform(0.96, 1.04)
        m = aligned(Vector((pos.x, pos.y, ww / 2)), tang, ww / 2, rng.uniform(0, 6.28), rng)
        obj_from_mesh(facet_mesh("rondel", i % 5), coll, stone_mat(spec["mat"], rng.randrange(3)), m)
    closure(coll, fn, table, total, s0, w / 2, G, length=2.3, bend=-1.5)
    b, tb = at(fn, table, total - s0)
    d = (Vector((1, 0, 0)) + tb * 0.12).normalized()
    start = b + d * 0.42
    ring_at(coll, start + Vector((0, 0, 0.03)), G, R=0.12)
    (charm_hamsa if spec.get("charm") == "hamsa" else charm_kwiat)(coll, start + d * 0.16, d, G)
    return {"radius": ring_r, "height": w, "bead": w, "detail_at": (ring_r + 0.9, -0.3), "detail_k": 0.82}


def keychain_head(coll, top, d, mat):
    """Karabinczyk z krętlikiem, lezacy plasko. Idzie od punktu top w kierunku d."""
    side = Vector((-d.y, d.x, 0))
    wire = 0.115
    ring_at(coll, top + d * 0.3 + Vector((0, 0, 0.06)), mat, R=0.33, wire=0.06)
    swivel = top + d * 0.92
    m = Matrix.Translation((swivel.x, swivel.y, 0.2)) @ d.to_track_quat("Z", "Y").to_matrix().to_4x4() @ Matrix.Diagonal((0.2, 0.2, 0.3, 1))
    obj_from_mesh(bead_mesh("peg", 0), coll, mat, m)
    base = top + d * 1.24
    length, width = 2.1, 0.5
    pts = []
    for i in range(60):
        t = i / 60 * 6.2832
        u = (1 - math.cos(t)) / 2 * length
        v = math.sin(t) * width * (1 - 0.18 * u / length)
        q = base + d * u + side * v
        pts.append((q.x, q.y, wire))
    obj_from_mesh(tube_mesh("hak", pts, wire, sides=8, closed=True), coll, mat)
    gate = base + d * (length * 0.5) - side * (width * 0.72)
    m = Matrix.Translation((gate.x, gate.y, wire)) @ (d - side * 0.1).normalized().to_track_quat("Z", "Y").to_matrix().to_4x4() @ Matrix.Diagonal((0.05, 0.05, length * 0.42, 1))
    obj_from_mesh(bead_mesh("peg", 1), coll, mat, m)
    return base + d * length


def build_brelok(coll, spec, seed, pendant=True):
    rng = random.Random(seed)
    tilt = math.radians(12)
    R = Matrix.Rotation(tilt, 3, "Z")
    d_bead = 0.72
    y_top, y_end = 2.4, -3.2 if pendant else -4.0
    pts = []
    for i in range(80):
        y = y_top + (y_end - y_top) * i / 79
        pts.append(R @ Vector((0.42 * math.sin(y * 0.8), y, 0)))
    acc = [0.0]
    for a, b in zip(pts, pts[1:]):
        acc.append(acc[-1] + (b - a).length)
    S = steel()
    n = int(acc[-1] / (d_bead * 1.08))
    pitch = acc[-1] / n
    beads = spec["beads"]
    j = 0
    mid = None
    for i in range(n):
        target = (i + 0.5) * pitch
        while acc[j + 1] < target:
            j += 1
        p = pts[j]
        tang = (pts[j + 1] - pts[j]).normalized()
        name = beads[i % len(beads)]
        m = aligned(Vector((p.x, p.y, d_bead / 2)), tang, d_bead / 2, 0, rng, free=True, layered=name in LAYERED)
        obj_from_mesh(bead_mesh("round", i % 3), coll, stone_mat(name, rng.randrange(3)), m)
        if i == n // 2:
            mid = Vector((p.x, p.y, d_bead / 2))
        if i % 2 == 0 and i < n - 1:
            s2 = target + pitch / 2
            k = j
            while acc[k + 1] < s2:
                k += 1
            q = pts[k]
            m2 = aligned(Vector((q.x, q.y, d_bead / 2)), tang, (0.2, 0.2, 0.035), 0, rng)
            obj_from_mesh(bead_mesh("peg", 0), coll, S, m2)
    down = (pts[-1] - pts[-2]).normalized()
    end = pts[-1]
    if pendant:
        bail = end + down * 0.14
        m = Matrix.Translation((bail.x, bail.y, 0.45)) @ down.to_track_quat("Z", "Y").to_matrix().to_4x4() @ Matrix.Diagonal((0.16, 0.16, 0.16, 1))
        obj_from_mesh(bead_mesh("peg", 0), coll, S, m)
        c = end + down * 1.2
        rot = down.to_track_quat("Y", "Z").to_matrix().to_4x4()
        name = spec["pendant"]
        m = Matrix.Translation((c.x, c.y, 0.5)) @ rot @ Matrix.Diagonal((0.72, 1.0, 0.6, 1))
        obj_from_mesh(bead_mesh("pebble", rng.randrange(4)), coll, stone_mat(name, rng.randrange(3)), m)
        bottom = end + down * 2.25
    else:
        m = Matrix.Translation((end.x + down.x * 0.16, end.y + down.y * 0.16, 0.14)) @ (-down).to_track_quat("Z", "Y").to_matrix().to_4x4() @ Matrix.Scale(0.14, 4)
        obj_from_mesh(bead_mesh("drop", 0), coll, S, m)
        bottom = end + down * 0.5
    up = (pts[0] - pts[1]).normalized()
    start = pts[0]
    _, _ = chain(coll, [(start.x, start.y, 0.35), tuple(start + up * 0.25 + Vector((0, 0, 0.1))), tuple(start + up * 0.6 + Vector((0, 0, 0.06)))], S, L=0.36, W=0.24, r=0.035)
    head_top = start + up * 0.62
    tip = keychain_head(coll, head_top, up, S)
    centre = (tip + bottom) / 2
    length = (tip - bottom).length
    return {"kind": "keychain", "length": length, "center": (centre.x, centre.y), "mid": tuple(mid), "hook": tuple(head_top + up * 1.0)}


def build_brelok_koraliki(coll, spec, seed):
    return build_brelok(coll, spec, seed, pendant=False)


BUILDERS = {
    "rondel": build_rondel,
    "drobne": build_drobne,
    "kostki": build_kostki,
    "zawieszka": build_zawieszka,
    "brelok": build_brelok,
    "brelok_koraliki": build_brelok_koraliki,
}


# ------------------------------------------------------------------ scena


def stone_surface_mat():
    m = bpy.data.materials.new("wapien")
    m.use_nodes = True
    nt = m.node_tree
    b = nt.nodes["Principled BSDF"]
    tc = nt.nodes.new("ShaderNodeTexCoord")
    big = nt.nodes.new("ShaderNodeTexNoise")
    big.inputs["Scale"].default_value = 0.16
    big.inputs["Detail"].default_value = 7
    big.inputs["Roughness"].default_value = 0.55
    fine = nt.nodes.new("ShaderNodeTexNoise")
    fine.inputs["Scale"].default_value = 3.4
    fine.inputs["Detail"].default_value = 8
    fine.inputs["Roughness"].default_value = 0.6
    pore = nt.nodes.new("ShaderNodeTexVoronoi")
    pore.inputs["Scale"].default_value = 3.1
    pore.feature = "F1"
    nt.links.new(tc.outputs["Object"], big.inputs["Vector"])
    nt.links.new(tc.outputs["Object"], fine.inputs["Vector"])
    nt.links.new(tc.outputs["Object"], pore.inputs["Vector"])
    cr = nt.nodes.new("ShaderNodeValToRGB")
    cr.color_ramp.elements[0].position = 0.34
    cr.color_ramp.elements[0].color = srgb("#c9c3b5")
    cr.color_ramp.elements[1].position = 0.68
    cr.color_ramp.elements[1].color = srgb("#e6e1d6")
    nt.links.new(big.outputs["Fac"], cr.inputs["Fac"])
    mix = nt.nodes.new("ShaderNodeMixRGB")
    mix.blend_type = "MULTIPLY"
    mix.inputs[0].default_value = 0.42
    nt.links.new(cr.outputs[0], mix.inputs[1])
    fr = nt.nodes.new("ShaderNodeValToRGB")
    fr.color_ramp.elements[0].position = 0.36
    fr.color_ramp.elements[0].color = (0.74, 0.72, 0.68, 1)
    fr.color_ramp.elements[1].position = 0.62
    fr.color_ramp.elements[1].color = (1, 1, 1, 1)
    nt.links.new(fine.outputs["Fac"], fr.inputs["Fac"])
    nt.links.new(fr.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], b.inputs["Base Color"])
    b.inputs["Roughness"].default_value = 0.72
    bp = nt.nodes.new("ShaderNodeBump")
    bp.inputs["Strength"].default_value = 0.22
    bp.inputs["Distance"].default_value = 0.012
    pr = nt.nodes.new("ShaderNodeValToRGB")
    pr.color_ramp.elements[0].position = 0.02
    pr.color_ramp.elements[0].color = (0, 0, 0, 1)
    pr.color_ramp.elements[1].position = 0.075
    pr.color_ramp.elements[1].color = (1, 1, 1, 1)
    nt.links.new(pore.outputs["Distance"], pr.inputs["Fac"])
    mh = nt.nodes.new("ShaderNodeMath")
    mh.operation = "MULTIPLY"
    nt.links.new(pr.outputs[0], mh.inputs[0])
    nt.links.new(fine.outputs["Fac"], mh.inputs[1])
    nt.links.new(mh.outputs[0], bp.inputs["Height"])
    nt.links.new(bp.outputs[0], b.inputs["Normal"])
    return m


def setup_scene(samples, scale):
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    prefs = bpy.context.preferences.addons["cycles"].preferences
    prefs.compute_device_type = "OPTIX"
    prefs.get_devices()
    for d in prefs.devices:
        d.use = d.type == "OPTIX"
    sc.cycles.device = "GPU"
    sc.cycles.samples = samples
    sc.cycles.use_adaptive_sampling = True
    sc.cycles.adaptive_threshold = 0.012
    sc.cycles.use_denoising = True
    sc.cycles.denoiser = "OPENIMAGEDENOISE"
    sc.cycles.denoising_input_passes = "RGB_ALBEDO_NORMAL"
    sc.cycles.denoising_prefilter = "ACCURATE"
    sc.cycles.max_bounces = 14
    sc.cycles.transmission_bounces = 12
    sc.cycles.volume_bounces = 2
    sc.cycles.caustics_refractive = False
    sc.cycles.caustics_reflective = False
    sc.cycles.blur_glossy = 0.6
    sc.cycles.sample_clamp_indirect = 8
    sc.cycles.use_auto_tile = False
    sc.render.resolution_x = int(1200 * scale)
    sc.render.resolution_y = int(1500 * scale)
    sc.render.film_transparent = False
    sc.render.image_settings.file_format = "PNG"
    sc.render.image_settings.color_mode = "RGB"
    sc.view_settings.view_transform = "AgX"
    sc.view_settings.look = "AgX - Medium High Contrast"
    sc.view_settings.exposure = 0.78
    sc.unit_settings.system = "NONE"

    bpy.ops.wm.read_factory_settings if False else None
    for ob in list(bpy.data.objects):
        bpy.data.objects.remove(ob)

    world = bpy.data.worlds.new("studio")
    world.use_nodes = True
    bg = world.node_tree.nodes["Background"]
    bg.inputs["Color"].default_value = srgb("#f4efe6")
    bg.inputs["Strength"].default_value = 0.42
    sc.world = world

    stage = bpy.data.collections.new("stage")
    sc.collection.children.link(stage)

    # blat z wapienia
    me = bpy.data.meshes.new("blat")
    S = 400
    me.from_pydata([(-S, -S, 0), (S, -S, 0), (S, S, 0), (-S, S, 0)], [], [(0, 1, 2, 3)])
    me.update()
    floor = bpy.data.objects.new("blat", me)
    stage.objects.link(floor)
    floor.data.materials.append(stone_surface_mat())

    # okno po lewej u gory: duze, miekkie swiatlo
    key = bpy.data.lights.new("okno", "AREA")
    key.shape = "RECTANGLE"
    key.size = 44
    key.size_y = 70
    key.energy = 92000
    key.color = (1.0, 0.965, 0.91)
    key_ob = bpy.data.objects.new("okno", key)
    stage.objects.link(key_ob)
    key_ob.location = (-46, 26, 58)
    key_ob.rotation_euler = Vector((46, -26, -58)).to_track_quat("-Z", "Y").to_euler()

    fill = bpy.data.lights.new("wypelnienie", "AREA")
    fill.size = 70
    fill.energy = 5200
    fill.color = (0.96, 0.97, 1.0)
    fill_ob = bpy.data.objects.new("wypelnienie", fill)
    stage.objects.link(fill_ob)
    fill_ob.location = (52, -30, 40)
    fill_ob.rotation_euler = Vector((-52, 30, -40)).to_track_quat("-Z", "Y").to_euler()

    cam_data = bpy.data.cameras.new("kamera")
    cam = bpy.data.objects.new("kamera", cam_data)
    stage.objects.link(cam)
    sc.camera = cam
    return sc, cam


def aim(cam, loc, target, lens, fstop=None, focus=None, roll=0.0):
    cam.location = Vector(loc)
    d = Vector(target) - Vector(loc)
    q = d.to_track_quat("-Z", "Y")
    cam.rotation_euler = (q.to_matrix().to_4x4() @ Matrix.Rotation(roll, 4, "Z")).to_euler()
    cam.data.lens = lens
    cam.data.sensor_width = 36
    cam.data.dof.use_dof = fstop is not None
    if fstop is not None:
        cam.data.dof.aperture_fstop = fstop
        cam.data.dof.focus_distance = (Vector(focus or target) - Vector(loc)).length


def shot_camera(cam, shot, info):
    if info.get("kind") == "keychain":
        L = info["length"]
        c = Vector((info["center"][0], info["center"][1], 0.3))
        if shot == "hero":
            el, az = math.radians(50), math.radians(-80)
            dist = L * 2.3
            aim(cam, c + Vector((math.cos(az) * math.cos(el), math.sin(az) * math.cos(el), math.sin(el))) * dist, c, 82, fstop=11, focus=c)
        elif shot == "top":
            aim(cam, c + Vector((0, -0.01, L * 2.95)), c, 82)
        elif shot == "macro":
            p = Vector(info["mid"])
            aim(cam, p + Vector((0.5, -4.6, 5.0)), p, 105, fstop=4.0, focus=p)
        else:
            p = Vector((info["hook"][0], info["hook"][1], 0.15))
            aim(cam, p + Vector((1.6, -5.0, 7.0)) * 1.4, p, 105, fstop=5.6, focus=p)
        return
    r = info["radius"]
    h = info["height"]
    bead = info.get("bead", 0.8)
    if shot == "hero":
        dist = r * 8.5
        el, az = math.radians(46), math.radians(-74)
        tgt = Vector((0.62, 0.0, h * 0.3))
        loc = tgt + Vector((math.cos(az) * math.cos(el), math.sin(az) * math.cos(el), math.sin(el))) * dist
        aim(cam, loc, tgt, 82, fstop=8, focus=(0.2, -r * 0.5, h * 0.5))
    elif shot == "top":
        tgt = Vector((0.6, 0, 0))
        aim(cam, tgt + Vector((0, -0.01, r * 8.7)), tgt, 82)
    elif shot == "macro":
        ang = math.radians(-105)
        p = Vector((math.cos(ang) * r, math.sin(ang) * r, h * 0.45))
        k = max(0.62, (bead / 0.8) ** 0.8)
        aim(cam, p + Vector((0.5, -4.6, 5.0)) * k, p, 105, fstop=4.0, focus=p + Vector((0, -h * 0.3, h * 0.2)))
    else:
        x, y = info["detail_at"]
        p = Vector((x, y, 0.2))
        aim(cam, p + Vector((3.5, -5.8, 6.0)) * info.get("detail_k", 1.0), p, 105, fstop=4.5, focus=p)


def render_to(sc, path):
    sc.render.filepath = str(Path(path).resolve())
    bpy.ops.render.render(write_still=True)


def clear_collection(coll):
    for ob in list(coll.objects):
        bpy.data.objects.remove(ob)


def export_glb(coll, path):
    bpy.ops.object.select_all(action="DESELECT")
    for ob in coll.objects:
        ob.select_set(True)
    bpy.ops.export_scene.gltf(
        filepath=str(path),
        export_format="GLB",
        use_selection=True,
        export_image_format="WEBP",
        export_image_quality=78,
        export_apply=False,
        export_yup=True,
        export_materials="EXPORT",
        export_cameras=False,
        export_lights=False,
    )


def parse():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--only", default="")
    ap.add_argument("--shots", default="hero,macro")
    ap.add_argument("--samples", type=int, default=128)
    ap.add_argument("--scale", type=float, default=1.0)
    ap.add_argument("--glb", action="store_true")
    ap.add_argument("--no-render", action="store_true")
    ap.add_argument("--skip-existing", action="store_true")
    ap.add_argument("--all-shots", action="store_true", help="kadry top i detail takze dla wariantow innych niz domyslny")
    return ap.parse_args(argv)


def main():
    args = parse()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    products = json.loads(DATA.read_text(encoding="utf-8"))
    wanted = [w for w in args.only.split(",") if w]
    sc, cam = setup_scene(args.samples, args.scale)
    item = bpy.data.collections.new("bransoletka")
    sc.collection.children.link(item)
    for pi, prod in enumerate(products):
        for vi, var in enumerate(prod["variants"]):
            tag = f"{prod['slug']}:{var['id']}"
            if wanted and not any(tag == w or prod["slug"] == w for w in wanted):
                continue
            clear_collection(item)
            spec = var["model"]
            seed = pi * 100 + vi + 7
            info = BUILDERS[spec["type"]](item, spec, seed)
            base = out / prod["slug"]
            base.mkdir(exist_ok=True)
            is_default = vi == 0
            if not args.no_render:
                for shot in args.shots.split(","):
                    if shot in ("top", "detail") and not is_default and not args.all_shots:
                        continue
                    target = base / f"{var['id']}-{shot}.png"
                    if args.skip_existing and target.exists():
                        continue
                    shot_camera(cam, shot, info)
                    render_to(sc, target)
                    print("RENDER", target, flush=True)
            if args.glb:
                export_glb(item, (base / f"{var['id']}.glb").resolve())
                print("GLB", base / f"{var['id']}.glb", flush=True)


if __name__ == "__main__":
    main()
