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

CORD_COLORS = {
    "silk_grafit": ("#34312f", 0.045),
    "silk_mech": ("#46523a", 0.045),
    "silk_glina": ("#8e5e3f", 0.045),
    "silk_piasek": ("#b5a385", 0.045),
    "silk_grafit_thick": ("#2f2d2c", 0.055),
    "silk_mech_thick": ("#4b5a3c", 0.055),
    "silk_glina_thick": ("#99623f", 0.055),
    "linen": ("#bdab8c", 0.05),
}


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
    "krzemien": dict(),
    "lapis": dict(),
    "tygrysie_oko": dict(aniso=0.75, spec=0.6),
    "obsydian": dict(spec=0.6),
    "amazonit": dict(sss=0.35, radius=(0.05, 0.08, 0.07)),
    "nefryt": dict(sss=0.75, radius=(0.05, 0.12, 0.07), spec=0.5),
    "kwarc": dict(trans=0.45, ior=1.54, absorb=None, sss=0.5, radius=(0.15, 0.08, 0.09)),
    "bursztyn_koniak": dict(trans=0.86, ior=1.54, absorb="#c2640f", absorb_d=0.9),
    "bursztyn_miod": dict(trans=0.86, ior=1.54, absorb="#e6a02a", absorb_d=0.6),
    "bursztyn_krolewski": dict(trans=0.3, ior=1.54, sss=0.7, radius=(0.2, 0.12, 0.05)),
    "dab_bagienny": dict(wood=True),
    "oliwka": dict(wood=True),
    "orzech": dict(wood=True),
}


def stone_mat(name, tex_i):
    mname = f"{name}_{tex_i}"
    m, nt, bsdf = new_mat(mname)
    if nt is None:
        return m
    spec = STONE[name]
    wood = spec.get("wood", False)
    attach_maps(nt, bsdf, mname, normal=wood, normal_strength=0.5)
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
    if not wood and not spec.get("trans"):
        bsdf.inputs["Coat Weight"].default_value = 0.35
        bsdf.inputs["Coat Roughness"].default_value = 0.06
    return m


def cord_mat(key):
    color, _ = CORD_COLORS[key]
    return fiber_mat(key, color, sheen="silk" in key)


def fiber_mat(name, color, sheen=False):
    m, nt, bsdf = new_mat(f"cord_{name}")
    if nt is None:
        return m
    # kolor nici razy jasnosc wlokna z tekstury
    tex = img_node(nt, "wlokno_color", "sRGB", (-700, 300))
    mul = nt.nodes.new("ShaderNodeMix")
    mul.data_type = "RGBA"
    mul.blend_type = "MULTIPLY"
    mul.inputs[0].default_value = 1.0
    mul.inputs[6].default_value = srgb(color)
    nt.links.new(tex.outputs["Color"], mul.inputs[7])
    nt.links.new(mul.outputs[2], bsdf.inputs["Base Color"])
    nm = img_node(nt, "wlokno_normal", "Non-Color", (-700, -300))
    n = nt.nodes.new("ShaderNodeNormalMap")
    n.inputs["Strength"].default_value = 0.8
    nt.links.new(nm.outputs["Color"], n.inputs["Color"])
    nt.links.new(n.outputs["Normal"], bsdf.inputs["Normal"])
    bsdf.inputs["Roughness"].default_value = 0.42 if sheen else 0.72
    bsdf.inputs["Sheen Weight"].default_value = 0.6 if sheen else 0.25
    return m


def leather_mat(tone):
    key = tone.lstrip("#")
    m, nt, bsdf = new_mat(f"skora_{key}")
    if nt is None:
        return m
    tex = img_node(nt, "skora_color", "sRGB", (-700, 300))
    mul = nt.nodes.new("ShaderNodeMix")
    mul.data_type = "RGBA"
    mul.blend_type = "MULTIPLY"
    mul.inputs[0].default_value = 1.0
    mul.inputs[6].default_value = srgb(tone)
    nt.links.new(tex.outputs["Color"], mul.inputs[7])
    nt.links.new(mul.outputs[2], bsdf.inputs["Base Color"])
    orm = img_node(nt, "skora_orm", "Non-Color", (-700, 0))
    sep = nt.nodes.new("ShaderNodeSeparateColor")
    nt.links.new(orm.outputs["Color"], sep.inputs[0])
    nt.links.new(sep.outputs[1], bsdf.inputs["Roughness"])
    nm = img_node(nt, "skora_normal", "Non-Color", (-700, -300))
    n = nt.nodes.new("ShaderNodeNormalMap")
    n.inputs["Strength"].default_value = 0.34
    nt.links.new(nm.outputs["Color"], n.inputs["Color"])
    nt.links.new(n.outputs["Normal"], bsdf.inputs["Normal"])
    return m


def tile_wood_mat(name):
    m, nt, bsdf = new_mat(name)
    if nt is None:
        return m
    attach_maps(nt, bsdf, name, normal=False)
    bsdf.inputs["Coat Weight"].default_value = 0.2
    bsdf.inputs["Coat Roughness"].default_value = 0.25
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
    if shape in ("nugget", "pebble"):
        seg, rings = 96, 64
    bmesh.ops.create_uvsphere(bm, u_segments=seg, v_segments=rings, radius=1.0, calc_uvs=True)
    offs = Vector((variant * 7.1 + 3.3, variant * 3.7 + 1.1, variant * 5.3))
    for v in bm.verts:
        p = v.co.copy()
        if shape == "rondelle":
            p.z *= 0.72
        elif shape == "nugget":
            n1 = mnoise.noise(p * 0.75 + offs)
            n2 = mnoise.noise(p * 1.7 + offs * 1.7)
            s = 1 + 0.26 * n1 + 0.045 * n2
            p = Vector((p.x * s * (1.02 + 0.1 * math.sin(variant * 2.3)),
                        p.y * s * (0.9 + 0.1 * math.cos(variant * 1.3)), p.z * s * 0.84))
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


LAYERED = {"krzemien", "tygrysie_oko"}


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


def knot(coll, center, direction, cord_key, wrap_r, turns=6, length=0.95):
    """Przesuwny wezel makramy: naprzemienne petle tworza zwarta, plaska beczulke."""
    _, r = CORD_COLORS[cord_key]
    d = direction.normalized()
    up = Vector((0, 0, 1))
    side = d.cross(up).normalized()
    mat = cord_mat(cord_key)
    n = turns * 2
    step = length / n
    rw = max(wrap_r, r * 3.1)
    for i in range(n):
        k = (i + 0.5) / n
        c = center + d * ((k - 0.5) * length)
        taper = 0.82 + 0.18 * math.sin(k * math.pi)
        sgn = 1 if i % 2 == 0 else -1
        pts = []
        N = 26
        for j in range(N):
            a = j / N * 2 * math.pi
            w = rw * 1.34 * taper
            h = rw * 0.9 * taper
            lean = sgn * 0.42 * step * math.cos(a)
            pts.append(c + d * lean + side * (w * math.cos(a) + sgn * rw * 0.1) + up * (h * math.sin(a)))
        obj_from_mesh(tube_mesh("wezel", pts, r * 1.02, sides=6, uv_scale=2.0, closed=True), coll, mat)


def tail(coll, start, direction, cord_key, length, seed, end_bead_mat=None, end_d=0.32, z0=None):
    """Wolna koncowka nici z drobnym koralikiem lub wezelkiem."""
    rng = random.Random(seed)
    _, r = CORD_COLORS[cord_key]
    pts = []
    N = 26
    d = direction.normalized()
    side = Vector((-d.y, d.x, 0))
    bend = rng.uniform(-0.6, 0.6)
    curl = rng.uniform(0.3, 0.8) * (1 if rng.random() < 0.5 else -1)
    p = start.copy()
    for i in range(N + 1):
        k = i / N
        pts.append(p + d * (k * length) + side * (bend * k * k * length * 0.45 + curl * math.sin(k * 2.2) * 0.12))
        pts[-1].z = max(r, (z0 if z0 is not None else start.z) * (1 - k) ** 2 + r)
    me = tube_mesh("koncowka", pts, r, sides=6, uv_scale=2.0)
    obj_from_mesh(me, coll, cord_mat(cord_key))
    end = pts[-1]
    tang = (pts[-1] - pts[-2]).normalized()
    if end_bead_mat is not None:
        rad = end_d / 2
        pos = end + tang * rad * 0.7
        pos.z = rad
        obj_from_mesh(bead_mesh("round", 0), coll, end_bead_mat, aligned(pos, tang, rad, rng.uniform(0, 6.28), rng))
    else:
        rad = r * 2.2
        pos = end + tang * rad * 0.2
        pos.z = rad
        obj_from_mesh(bead_mesh("round", 0), coll, cord_mat(cord_key), aligned(pos, tang, rad, 0, rng))


def threaded_ring(coll, seed, ring_r=2.85):
    return close_curve(ring_r, seed * 0.77)


def build_beads(coll, spec, seed, ring_r=2.85):
    rng = random.Random(seed)
    d = spec["d"]
    shape = spec.get("shape", "round")
    mats = spec["mats"]
    cord = spec["cord"]
    fn = threaded_ring(coll, seed, ring_r)
    table, total = arc_table(fn)
    knot_gap = 1.5
    usable = total - knot_gap
    beads = []
    s = 0.0
    idx = 0
    variable = shape in ("nugget", "pebble")
    while True:
        if variable:
            # od najwiekszych do mniejszych, potem z powrotem: kamienie ulozone jak na nitce
            k = abs((s / usable) * 2 - 1)
            dia = d * (1.22 - 0.42 * k) * rng.uniform(0.9, 1.1)
            gap = 0.03
        else:
            dia = d
            gap = 0.012
        if s + dia > usable:
            break
        beads.append((s + dia / 2, dia, idx))
        s += dia + gap
        idx += 1
    # rozciagnij rownomiernie, zeby nie zostawic luki
    if beads:
        slack = usable - s
        beads = [(b[0] + slack * (b[2] + 0.5) / len(beads), b[1], b[2]) for b in beads]
    thread_r = CORD_COLORS[cord][1]
    start_s = knot_gap / 2
    thread_pts = []
    for i in range(0, 220):
        ss = start_s + usable * i / 219
        t = t_at(table, ss)
        p2 = fn(t)
        thread_pts.append(Vector((p2.x, p2.y, d * 0.46)))
    obj_from_mesh(tube_mesh("nic", thread_pts, thread_r, sides=6, uv_scale=2.0), coll, cord_mat(cord))
    for s_i, dia, i in beads:
        ss = start_s + s_i
        t = t_at(table, ss)
        p2 = fn(t)
        p2b = fn(t + 0.01)
        tang = Vector((p2b.x - p2.x, p2b.y - p2.y, 0))
        stone = mats[i % len(mats)]
        mat = stone_mat(stone, rng.randrange(3))
        rad = dia / 2
        if shape == "round":
            # kuliste koraliki moga byc obrocone dowolnie, wiec kazdy ma inny wzor
            m = aligned(Vector((p2.x, p2.y, rad)), tang, rad, rng.uniform(0, 6.28), rng, free=True, layered=stone in LAYERED)
            mesh = bead_mesh("round", i % 3)
        else:
            mesh = bead_mesh(shape, i % 5)
            spin = rng.uniform(0, 6.28)
            sc = rad * 1.02
            z_lift = sc * 0.82
            m = Matrix.Translation(Vector((p2.x, p2.y, z_lift))) @ tang.normalized().to_track_quat("Y", "Z").to_matrix().to_4x4() @ Matrix.Rotation(spin * 0.15, 4, "Y") @ Matrix.Scale(sc, 4)
        obj_from_mesh(mesh, coll, mat, m)
    add_knot_section(coll, fn, table, total, d, cord, rng, spec)
    return {"radius": ring_r, "height": d, "bead": d}


def add_knot_section(coll, fn, table, total, d, cord, rng, spec, z=None):
    """Odcinek z przesuwnym wezlem w miejscu zamkniecia obwodu."""
    z = z if z is not None else max(d * 0.46, CORD_COLORS[cord][1] * 2)
    _, r = CORD_COLORS[cord]
    a = fn(t_at(table, total - 0.72))
    b = fn(t_at(table, 0.72))
    c = fn(0.0)
    cv = Vector((c.x, c.y, 0))
    pa = Vector((a.x, a.y, z))
    pb = Vector((b.x, b.y, z))
    # dwie zyly przechodzace przez wezel, kazda wychodzi w swoja strone
    outward = Vector((1, 0, 0))
    direction = Vector((0, 1, 0))
    kn_center = Vector((cv.x + 0.02, cv.y, max(z, r * 3.6)))
    lo = r * 3
    for sgn, start in ((1, pa), (-1, pb)):
        pts = []
        for i in range(24):
            k = i / 23
            q = start.lerp(kn_center + direction * (-sgn * -0.05) + outward * sgn * 0.035, k)
            q.z = z + (kn_center.z - z) * k
            pts.append(q)
        obj_from_mesh(tube_mesh("zyla", pts, r, sides=6, uv_scale=2.0), coll, cord_mat(cord))
    knot(coll, kn_center, direction, cord, wrap_r=r * 2.6)
    endmat = None
    mats = spec.get("mats")
    if mats:
        endmat = stone_mat(mats[-1], 0) if d < 1.0 else None
    tail(coll, kn_center + direction * 0.5, Vector((0.62, 0.72, 0)), cord, 1.25, rng.randrange(9999), endmat, z0=kn_center.z)
    tail(coll, kn_center - direction * 0.5, Vector((0.72, -0.62, 0)), cord, 1.45, rng.randrange(9999), endmat, z0=kn_center.z)


def braid_paths(center_fn, s0, s1, table, r_lat, r_up, pitch, z0, strands=3, step=0.035):
    """Tor pasm warkocza wokol srodkowej krzywej."""
    length = s1 - s0
    n = max(int(length / step), 8)
    out = [[] for _ in range(strands)]
    for i in range(n + 1):
        s = s0 + length * i / n
        t = t_at(table, s % table[-1][0])
        p = center_fn(t)
        q = center_fn(t + 0.005)
        tang = Vector((q.x - p.x, q.y - p.y, 0)).normalized()
        side = Vector((-tang.y, tang.x, 0))
        for k in range(strands):
            a = 2 * math.pi * (s / pitch + k / strands)
            lat = math.sin(a) * r_lat
            up = math.sin(2 * a) * r_up
            out[k].append(Vector((p.x, p.y, z0)) + side * lat + Vector((0, 0, up)))
    return out


def build_half(coll, spec, seed, ring_r=2.85):
    rng = random.Random(seed)
    d = spec["d"]
    cord = spec["cord"]
    fn = threaded_ring(coll, seed, ring_r)
    table, total = arc_table(fn)
    gap = 1.5
    usable = total - gap
    half = usable * 0.52
    # koraliki
    n = int(half / (d + 0.012))
    z = d * 0.46
    s0 = gap / 2
    thread = []
    for i in range(80):
        ss = s0 + half * i / 79
        p = fn(t_at(table, ss))
        thread.append(Vector((p.x, p.y, z)))
    obj_from_mesh(tube_mesh("nic", thread, CORD_COLORS[cord][1], sides=6, uv_scale=2.0), coll, cord_mat(cord))
    for i in range(n):
        ss = s0 + (i + 0.5) * half / n
        t = t_at(table, ss)
        p = fn(t)
        q = fn(t + 0.01)
        tang = Vector((q.x - p.x, q.y - p.y, 0))
        m = aligned(Vector((p.x, p.y, d / 2)), tang, d / 2, 0, rng, free=True, layered=spec["mats"][0] in LAYERED)
        obj_from_mesh(bead_mesh("round", i % 3), coll, stone_mat(spec["mats"][0], rng.randrange(3)), m)
    # plecionka
    braid_s0 = s0 + half
    braid_s1 = s0 + usable
    for k, path in enumerate(braid_paths(fn, braid_s0, braid_s1, table, 0.1, 0.05, 0.62, 0.16)):
        obj_from_mesh(tube_mesh("warkocz", path, 0.062, sides=8, uv_scale=1.6), coll, cord_mat(cord))
    add_knot_section(coll, fn, table, total, d * 0.7, cord, rng, spec)
    return {"radius": ring_r, "height": d}


def build_strand(coll, spec, seed, ring_r=2.85):
    rng = random.Random(seed)
    cord = spec["cord"]
    d = spec["d"]
    fn = close_curve(ring_r, seed * 0.77, loose=3.2)
    table, total = arc_table(fn)
    gap = 1.5
    usable = total - gap
    r = CORD_COLORS[cord][1]
    z = max(r, d * 0.46)
    s0 = gap / 2
    pts = []
    for i in range(240):
        ss = s0 + usable * i / 239
        p = fn(t_at(table, ss))
        pts.append(Vector((p.x, p.y, z)))
    obj_from_mesh(tube_mesh("nic", pts, r, sides=8, uv_scale=2.0, twist=4.0), coll, cord_mat(cord))
    count = spec.get("count", 5)
    places = [0.14, 0.29, 0.5, 0.71, 0.86][:count]
    for i, k in enumerate(places):
        ss = s0 + usable * k
        t = t_at(table, ss)
        p = fn(t)
        q = fn(t + 0.01)
        tang = Vector((q.x - p.x, q.y - p.y, 0))
        m = aligned(Vector((p.x, p.y, d / 2)), tang, d / 2, 0, rng, free=True, layered=spec["mats"][0] in LAYERED)
        obj_from_mesh(bead_mesh("round", i % 3), coll, stone_mat(spec["mats"][0], rng.randrange(3)), m)
    add_knot_section(coll, fn, table, total, d, cord, rng, spec, z=z)
    return {"radius": ring_r, "height": d}


def build_braid_stone(coll, spec, seed, ring_r=2.85):
    rng = random.Random(seed)
    cord = spec["cord"]
    d = spec["d"]
    fn = threaded_ring(coll, seed, ring_r)
    table, total = arc_table(fn)
    gap = 1.5
    usable = total - gap
    s0 = gap / 2
    mid = s0 + usable / 2
    # plecionka po obu stronach kamienia
    for a, b in ((s0, mid - d * 0.42), (mid + d * 0.42, s0 + usable)):
        for path in braid_paths(fn, a, b, table, 0.13, 0.065, 0.74, 0.2):
            obj_from_mesh(tube_mesh("warkocz", path, 0.08, sides=8, uv_scale=1.6), coll, cord_mat(cord))
    t = t_at(table, mid)
    p = fn(t)
    q = fn(t + 0.01)
    tang = Vector((q.x - p.x, q.y - p.y, 0))
    m = aligned(Vector((p.x, p.y, d / 2)), tang, d / 2, 0, rng, free=True)
    obj_from_mesh(bead_mesh("round", 1), coll, stone_mat(spec["mats"][0], rng.randrange(3)), m)
    add_knot_section(coll, fn, table, total, 0.5, cord, rng, {"mats": None})
    return {"radius": ring_r, "height": d}


def build_leather_band(coll, spec, seed, ring_r=3.0):
    """Pas skory stojacy na krawedzi, z zakladka, szwem i drewnianym kolkiem."""
    rng = random.Random(seed)
    leather = leather_mat(spec["tone"])
    width = 1.2
    thick = 0.26
    total_angle = 2 * math.pi + 0.95
    steps = 260
    verts, faces, uvs = [], [], []
    prof = 16  # punkty przekroju
    length = 0.0
    prev = None
    centers = []
    for i in range(steps + 1):
        k = i / steps
        a = k * total_angle - 0.45
        rr = ring_r + thick * 1.05 * max(0, (a - (2 * math.pi - 0.45)) / 0.95) ** 0.6 if a > 2 * math.pi - 0.45 else ring_r
        rr *= 1 + 0.012 * math.sin(2 * a + seed)
        p = Vector((rr * math.cos(a), rr * math.sin(a), 0))
        if prev is not None:
            length += (p - prev).length
        prev = p
        rad = Vector((math.cos(a), math.sin(a), 0))
        # czubki pasa sa zaokraglone
        tip = min(k * total_angle * ring_r / 0.75, (1 - k) * total_angle * ring_r / 0.75, 1.0)
        w = width * (0.42 + 0.58 * math.sin(tip * math.pi / 2)) if tip < 1 else width
        centers.append((p, rad, w, length))
        for j in range(prof):
            b = j / prof * 2 * math.pi
            # zaokraglony prostokat (superelipsa)
            cb, sb = math.cos(b), math.sin(b)
            ex = 0.42
            x = math.copysign(abs(cb) ** ex, cb) * thick / 2
            z = math.copysign(abs(sb) ** ex, sb) * w / 2
            verts.append(tuple(p + rad * x + Vector((0, 0, z + width / 2))))
            uvs.append((j / prof * 1.25, length * 0.42))
    for i in range(steps):
        for j in range(prof):
            j2 = (j + 1) % prof
            faces.append((i * prof + j, i * prof + j2, (i + 1) * prof + j2, (i + 1) * prof + j))
    me = bpy.data.meshes.new("pas_skory")
    me.from_pydata(verts, [], faces)
    uvl = me.uv_layers.new(name="UVMap")
    for poly in me.polygons:
        poly.use_smooth = True
        for li in poly.loop_indices:
            uvl.data[li].uv = uvs[me.loops[li].vertex_index]
    me.update()
    obj_from_mesh(me, coll, leather)
    # sciegi na zewnetrznej scianie, wzdluz obu krawedzi
    thread_mesh = bead_mesh("round", 0)
    linen = cord_mat("linen")
    stitch_len = 0.26
    s = 0.6
    i = 0
    end_len = centers[-1][3]
    while s < end_len - 0.6:
        # znajdz punkt po dlugosci
        c = min(centers, key=lambda q: abs(q[3] - s))
        p, rad, w, _ = c
        tang = Vector((-rad.y, rad.x, 0))
        for z in (width / 2 - w / 2 + 0.11, width / 2 + w / 2 - 0.11):
            pos = p + rad * (thick / 2 + 0.002) + Vector((0, 0, z))
            m = Matrix.Translation(pos) @ tang.to_track_quat("Z", "Y").to_matrix().to_4x4() @ Matrix.Diagonal((0.034, 0.034, stitch_len / 2 * 0.86, 1))
            obj_from_mesh(thread_mesh, coll, linen, m)
        s += stitch_len
        i += 1
    # kolek z drewna oliwnego i petelka
    a = 2 * math.pi - 0.45 + 0.3
    c = Vector((math.cos(a), math.sin(a), 0))
    pos = c * (ring_r + thick * 1.55) + Vector((0, 0, width / 2))
    toggle = bead_mesh("peg", 1)
    m = Matrix.Translation(pos) @ Matrix.Diagonal((0.2, 0.2, 0.92, 1))
    obj_from_mesh(toggle, coll, stone_mat("oliwka", 0), m)
    tang = Vector((-c.y, c.x, 0))
    loop = []
    for i in range(41):
        k = i / 40
        ang = k * 2 * math.pi
        loop.append(pos + c * (0.28 * math.cos(ang) - 0.02) + tang * (0.28 * math.sin(ang)))
    obj_from_mesh(tube_mesh("petla", loop, 0.05, sides=6, uv_scale=2.0, closed=True), coll, linen)
    return {"radius": ring_r + thick, "height": width, "standing": True}


def build_leather_braid(coll, spec, seed, ring_r=2.85):
    rng = random.Random(seed)
    leather = leather_mat(spec["tone"])
    fn = threaded_ring(coll, seed, ring_r)
    table, total = arc_table(fn)
    gap = 1.0
    s0, s1 = gap / 2, total - gap / 2
    for path in braid_paths(fn, s0, s1, table, 0.2, 0.09, 1.25, 0.3, step=0.03):
        me = tube_mesh("warkocz", path, 0.1, sides=10, uv_scale=0.5, profile=(0.075, 0.14))
        obj_from_mesh(me, coll, leather)
    # zapiecie: koralik z orzecha i petla ze skory
    a = fn(t_at(table, s1))
    b = fn(t_at(table, s0))
    bead_pos = Vector((a.x, a.y - 0.1, 0.46))
    m = Matrix.Translation(bead_pos) @ Matrix.Scale(0.44, 4)
    obj_from_mesh(bead_mesh("round", 2), coll, stone_mat("orzech", 1), m)
    loop = []
    cen = Vector((b.x, b.y - 0.62, 0.2))
    for i in range(49):
        ang = i / 48 * 2 * math.pi
        loop.append(cen + Vector((0.3 * math.cos(ang), 0.58 * math.sin(ang), 0.02 * math.sin(ang * 2))))
    obj_from_mesh(tube_mesh("petla", loop, 0.06, sides=8, uv_scale=1.0, closed=True, profile=(0.05, 0.085)), coll, leather)
    # owijka na koncu plecionki
    for pos in (a, b):
        wrap = []
        for i in range(60):
            k = i / 59
            ang = k * 5 * 2 * math.pi
            wrap.append(Vector((pos.x + 0.21 * math.cos(ang), pos.y + (k - 0.5) * 0.3, 0.3 + 0.21 * math.sin(ang))))
        obj_from_mesh(tube_mesh("owijka", wrap, 0.05, sides=6, uv_scale=1.0), coll, cord_mat("linen"))
    return {"radius": ring_r, "height": 0.6}


def build_bangle(coll, spec, seed, ring_r=3.2):
    width = 1.5
    thick = 0.42
    steps = 256
    prof = 28
    verts, faces, uvs = [], [], []
    for i in range(steps + 1):
        a = i / steps * 2 * math.pi
        rad = Vector((math.cos(a), math.sin(a), 0))
        for j in range(prof + 1):
            b = j / prof * 2 * math.pi
            cb, sb = math.cos(b), math.sin(b)
            # przekroj D: lekko wypukly na zewnatrz, plaski od strony reki
            x = (0.62 * cb if cb < 0 else cb) * thick / 2
            z = math.copysign(abs(sb) ** 0.78, sb) * width / 2
            p = rad * (ring_r + x) + Vector((0, 0, z + width / 2))
            verts.append(tuple(p))
            uvs.append((i / steps, j / prof))
    for i in range(steps):
        for j in range(prof):
            r = prof + 1
            faces.append((i * r + j, (i + 1) * r + j, (i + 1) * r + j + 1, i * r + j + 1))
    me = bpy.data.meshes.new("obrecz")
    me.from_pydata(verts, [], faces)
    uvl = me.uv_layers.new(name="UVMap")
    for poly in me.polygons:
        poly.use_smooth = True
        for li in poly.loop_indices:
            uvl.data[li].uv = uvs[me.loops[li].vertex_index]
    me.update()
    obj_from_mesh(me, coll, tile_wood_mat(spec["mat"]))
    return {"radius": ring_r + thick / 2, "height": width, "standing": True}


BUILDERS = {
    "beads": build_beads,
    "half": build_half,
    "strand": build_strand,
    "braid_stone": build_braid_stone,
    "leather_band": build_leather_band,
    "leather_braid": build_leather_braid,
    "bangle": build_bangle,
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
    r = info["radius"]
    h = info["height"]
    standing = info.get("standing", False)
    bead = info.get("bead", 0.8)
    if shot == "hero":
        dist = r * (8.5 if not standing else 7.6)
        el = math.radians(46 if not standing else 30)
        az = math.radians(-74)
        tgt = Vector((0.62 if not standing else 0.0, 0.0, h * 0.3))
        loc = tgt + Vector((math.cos(az) * math.cos(el), math.sin(az) * math.cos(el), math.sin(el))) * dist
        aim(cam, loc, tgt, 82, fstop=8, focus=(0.2, -r * 0.5, h * 0.5))
    elif shot == "top":
        tgt = Vector((0.6 if not standing else 0.0, 0, 0))
        aim(cam, tgt + Vector((0, -0.01, r * 8.7)), tgt, 82, fstop=None)
    elif shot == "macro":
        ang = math.radians(-105)
        p = Vector((math.cos(ang) * r, math.sin(ang) * r, h * 0.45))
        k = max(0.75, (bead / 0.8) ** 0.8)
        dv = Vector((0.5, -4.6, 5.0)) * k * (1.3 if standing else 1.0)
        aim(cam, p + dv, p, 105, fstop=4.0, focus=p + Vector((0, -h * 0.3, h * 0.2)))
    elif shot == "detail":
        if standing:
            p = Vector((math.cos(-0.15) * r, math.sin(-0.15) * r, h * 0.5))
            loc = p + Vector((8.2, -5.6, 4.6))
        else:
            p = Vector((r * 1.04, 0.0, 0.25))
            loc = p + Vector((3.5, -5.8, 6.0))
        aim(cam, loc, p, 105, fstop=4.5, focus=p)


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
