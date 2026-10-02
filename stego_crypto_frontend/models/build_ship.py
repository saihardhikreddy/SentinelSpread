"""Build the SENTINEL ring ship in Blender and export it as a GLB for the web page.

Run:  blender --background --factory-startup --python models/build_ship.py -- <out.glb>

Blender frame: ring in the XY plane, axis +Z. Module i sits at angle i*30 deg, radius 9.
Module-local frame: X = tangent, Y = radially outward, Z = up (ring axis).
The glTF exporter converts to Y-up, so in three.js: up = +Y, outward = -Z (module-local).

Static geometry is merged into one mesh per material (few draw calls). Moving parts stay
separate objects: BayDoor (hinge at its origin) and Dish (mount at origin, opens along +Z).
Empties mark where the page attaches live effects: F_* (module frames) and A_* (anchors).
"""

import math
import os
import random
import sys

import bmesh
import bpy
from mathutils import Matrix, Vector

OUT = sys.argv[sys.argv.index("--") + 1] if "--" in sys.argv else "sentinel_ship.glb"
R = 9.0
SMOOTH_ANGLE = math.radians(34)
rng = random.Random(1907)

# ─── materials ───────────────────────────────────────────────────────────────
MATS = {
    "Hull":      dict(color=(0.86, 0.87, 0.88), metal=0.05, rough=0.42),
    "HullPanel": dict(color=(0.70, 0.72, 0.75), metal=0.10, rough=0.50),
    "HullWarm":  dict(color=(0.80, 0.80, 0.78), metal=0.05, rough=0.55),
    "Metal":     dict(color=(0.42, 0.45, 0.49), metal=0.85, rough=0.32),
    "Dark":      dict(color=(0.035, 0.04, 0.05), metal=0.40, rough=0.48),
    "Glass":     dict(color=(0.01, 0.02, 0.04), metal=0.90, rough=0.04),
    "Window":    dict(color=(0.02, 0.04, 0.08), metal=0.20, rough=0.20, emit=(0.30, 0.55, 1.0), emit_strength=1.6),
    "Radiator":  dict(color=(0.93, 0.94, 0.95), metal=0.0, rough=0.62),
    "Dish":      dict(color=(0.90, 0.91, 0.92), metal=0.02, rough=0.55),
    "Accent":    dict(color=(0.30, 0.52, 0.82), metal=0.25, rough=0.42),
    "Light":     dict(color=(0.03, 0.06, 0.1), metal=0.0, rough=0.4, emit=(0.55, 0.85, 1.0), emit_strength=6.0),
    "Solar":     dict(color=(0.025, 0.055, 0.16), metal=0.6, rough=0.22),
    "NavLight":  dict(color=(0.05, 0.08, 0.12), metal=0.0, rough=0.4, emit=(0.55, 0.85, 1.0), emit_strength=6.0),
}


def make_material(name, color, metal, rough, emit=None, emit_strength=0.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    p = m.node_tree.nodes.get("Principled BSDF")
    p.inputs["Base Color"].default_value = (*color, 1.0)
    p.inputs["Metallic"].default_value = metal
    p.inputs["Roughness"].default_value = rough
    if emit:
        p.inputs["Emission Color"].default_value = (*emit, 1.0)
        p.inputs["Emission Strength"].default_value = emit_strength
    return m


# ─── geometry builder: one bmesh per material, primitives placed by matrix ───
class Builder:
    """Each primitive is built in its own temporary bmesh, transformed there, then appended to
    the per-material bmesh. (Index slicing on a shared bmesh is unsafe: bevel frees verts and
    BMesh reuses the slots, so "verts after n0" can include older geometry.)"""

    def __init__(self):
        self.bms = {}

    def bm(self, mat):
        if mat not in self.bms:
            self.bms[mat] = bmesh.new()
        return self.bms[mat]

    def commit(self, mat, tmp, M=None):
        if M is not None:
            bmesh.ops.transform(tmp, matrix=M, verts=tmp.verts[:])
        me = bpy.data.meshes.new("_tmp")
        tmp.to_mesh(me)
        tmp.free()
        self.bm(mat).from_mesh(me)
        bpy.data.meshes.remove(me)

    def box(self, mat, M, sx, sy, sz, bevel=0.0, seg=1):
        t = bmesh.new()
        bmesh.ops.create_cube(t, size=1.0)
        bmesh.ops.scale(t, vec=(sx, sy, sz), verts=t.verts[:])
        if bevel > 0:
            bmesh.ops.bevel(t, geom=t.edges[:], offset=min(bevel, min(sx, sy, sz) * 0.45), segments=seg,
                            profile=0.5, affect="EDGES", clamp_overlap=True)
        self.commit(mat, t, M)

    def cyl(self, mat, M, r, depth, segs=20, r2=None, caps=True):
        """Cylinder/cone along local Z, centred at the origin of M."""
        t = bmesh.new()
        bmesh.ops.create_cone(t, cap_ends=caps, cap_tris=False, segments=segs,
                              radius1=r, radius2=r if r2 is None else r2, depth=depth)
        self.commit(mat, t, M)

    def rod(self, mat, a, b, r, segs=8):
        a, b = Vector(a), Vector(b)
        d = b - a
        if d.length < 1e-6:
            return
        rot = d.normalized().to_track_quat("Z", "Y").to_matrix().to_4x4()
        self.cyl(mat, Matrix.Translation((a + b) / 2) @ rot, r, d.length, segs)

    def sphere(self, mat, M, r, u=20, v=12):
        t = bmesh.new()
        bmesh.ops.create_uvsphere(t, u_segments=u, v_segments=v, radius=r)
        self.commit(mat, t, M)

    def lathe(self, mat, M, profile, segs=32):
        """Revolve [(radius, z), ...] around local Z (radius 0 is nudged off the axis)."""
        t = bmesh.new()
        vs = [t.verts.new((max(r, 0.002), 0.0, z)) for r, z in profile]
        es = [t.edges.new((vs[i], vs[i + 1])) for i in range(len(vs) - 1)]
        bmesh.ops.spin(t, geom=vs + es, cent=(0, 0, 0), axis=(0, 0, 1), dvec=(0, 0, 0),
                       angle=math.tau, steps=segs, use_merge=True, use_duplicate=False)
        self.commit(mat, t, M)

    def tube(self, mat, points, r, sides=6):
        """Swept tube through a polyline (used for the helix antenna)."""
        t = bmesh.new()
        rings = []
        for i, p in enumerate(points):
            p = Vector(p)
            tan = (Vector(points[min(i + 1, len(points) - 1)]) - Vector(points[max(i - 1, 0)])).normalized()
            n = tan.orthogonal().normalized()
            bnorm = tan.cross(n)
            rings.append([t.verts.new(p + (n * math.cos(a) + bnorm * math.sin(a)) * r)
                          for a in (k / sides * math.tau for k in range(sides))])
        for a, b in zip(rings, rings[1:]):
            for k in range(sides):
                t.faces.new((a[k], a[(k + 1) % sides], b[(k + 1) % sides], b[k]))
        self.commit(mat, t)

    def to_object(self, name, collection, origin=Matrix()):
        objs = []
        for mat, bm in self.bms.items():
            bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
            for f in bm.faces:
                f.smooth = True
            for e in bm.edges:                       # crease only where the surface really turns
                if len(e.link_faces) == 2:
                    e.smooth = e.calc_face_angle(0.0) < SMOOTH_ANGLE
            me = bpy.data.meshes.new(f"{name}_{mat}")
            bm.to_mesh(me)
            bm.free()
            me.materials.append(bpy.data.materials[mat])
            ob = bpy.data.objects.new(f"{name}_{mat}" if len(self.bms) > 1 else name, me)
            collection.objects.link(ob)
            objs.append(ob)
        self.bms = {}
        return objs


def T(x, y, z):
    return Matrix.Translation((x, y, z))


def Rz(a):
    return Matrix.Rotation(a, 4, "Z")


def Rx(a):
    return Matrix.Rotation(a, 4, "X")


def Ry(a):
    return Matrix.Rotation(a, 4, "Y")


def module_matrix(i):
    th = math.radians(i * 30)
    return T(R * math.cos(th), R * math.sin(th), 0) @ Rz(th - math.pi / 2)


def empty(name, M, collection):
    e = bpy.data.objects.new(name, None)
    e.empty_display_size = 0.3
    e.matrix_world = M
    collection.objects.link(e)
    return e


# ─── shared module dressing ───────────────────────────────────────────────────
def rcs_quad(B, M):
    B.box("Metal", M, 0.18, 0.18, 0.16, 0.02)
    for d in ((1, 0, 0), (-1, 0, 0), (0, 0, 1), (0, 1, 0)):
        v = Vector(d)
        rot = v.to_track_quat("Z", "Y").to_matrix().to_4x4()
        B.cyl("Dark", M @ Matrix.Translation(v * 0.13) @ rot, 0.025, 0.08, 10, r2=0.045)


def greebles(B, M, w, d, n, z):
    """Small boxes and cylinders scattered on a deck (z = deck height)."""
    for _ in range(n):
        x, y = rng.uniform(-w / 2 + 0.15, w / 2 - 0.15), rng.uniform(-d / 2 + 0.15, d / 2 - 0.15)
        k = rng.random()
        mat = rng.choice(["HullPanel", "Metal", "Dark", "Hull"])
        if k < 0.55:
            sx, sy, sz = rng.uniform(0.08, 0.38), rng.uniform(0.08, 0.3), rng.uniform(0.04, 0.16)
            B.box(mat, M @ T(x, y, z + sz / 2) @ Rz(rng.choice([0, math.pi / 2])), sx, sy, sz, 0.012)
        elif k < 0.85:
            r, h = rng.uniform(0.04, 0.12), rng.uniform(0.05, 0.22)
            B.cyl(mat, M @ T(x, y, z + h / 2), r, h, 14)
        else:
            B.rod("Metal", M @ T(x, y, z) @ Vector((0, 0, 0)), M @ T(x, y, z + rng.uniform(0.3, 0.7)) @ Vector((0, 0, 0)), 0.012, 5)


def handrail(B, M, a, b, standoff=0.06):
    a, b = Vector(a), Vector(b)
    pa, pb = M @ a, M @ b
    B.rod("Metal", pa, pb, 0.018, 6)
    steps = max(2, int((b - a).length / 0.45))
    out = (M.to_3x3() @ Vector((0, 1, 0))).normalized()
    for k in range(steps + 1):
        p = pa.lerp(pb, k / steps)
        B.rod("Metal", p, p - out * standoff, 0.012, 5)


def module_shell(B, M, w=2.5, d=1.9, h=1.5, windows=True, plates=True):
    B.box("Hull", M, w, d, h, 0.08, 2)
    # raised plates on the outer face and the top deck
    if plates:
        for cx in (-0.78, 0, 0.78):
            for cz in (-0.33, 0.33):
                if windows and cz > 0 and cx == 0:
                    continue
                B.box(rng.choice(["HullPanel", "HullWarm", "Hull"]), M @ T(cx, d / 2 + 0.012, cz), 0.7, 0.03, 0.56, 0.012)
        for cx in (-0.6, 0.6):
            for cy in (-0.42, 0.42):
                B.box("HullPanel", M @ T(cx, cy, h / 2 + 0.012), 1.08, 0.74, 0.025, 0.01)
    if windows:
        B.box("Metal", M @ T(0, d / 2 + 0.02, 0.33), 2.0, 0.025, 0.3, 0.01)
        for k in range(7):
            B.box("Window", M @ T(-0.84 + k * 0.28, d / 2 + 0.035, 0.33), 0.2, 0.02, 0.16, 0.008)
    # end collars where corridors attach
    for sx in (-1, 1):
        cm = M @ T(sx * (w / 2 + 0.05), 0, 0) @ Ry(math.pi / 2)
        B.cyl("Metal", cm, 0.5, 0.12, 28)
        B.cyl("Dark", M @ T(sx * (w / 2 + 0.14), 0, 0) @ Ry(math.pi / 2), 0.42, 0.1, 28)
    # frame bands
    for sz in (-1, 1):
        B.box("Metal", M @ T(0, 0, sz * (h / 2 - 0.02)), w + 0.04, d + 0.04, 0.05, 0.01)
    handrail(B, M, (-w / 2 + 0.2, d / 2 + 0.07, -h / 2 + 0.18), (w / 2 - 0.2, d / 2 + 0.07, -h / 2 + 0.18))
    for sx in (-1, 1):
        for sz in (-1, 1):
            rcs_quad(B, M @ T(sx * (w / 2 - 0.15), d / 2 - 0.1, sz * (h / 2 + 0.1)))
    greebles(B, M, w - 0.3, d - 0.3, 9, h / 2 + 0.02)
    seams(B, M, w, d, h)
    for sx in (-1, 1):            # vent grilles on the side faces, above the collars
        for k in range(6):
            B.box("Dark", M @ T(sx * (w / 2 + 0.006), -0.35 + k * 0.14, h / 2 - 0.22), 0.012, 0.09, 0.06, 0.0)
    for sx in (-1, 1):            # nav lights on the outer top corners
        B.sphere("NavLight", M @ T(sx * (w / 2 - 0.06), d / 2 - 0.06, h / 2 + 0.04), 0.035, 10, 6)
    B.box("Light", M @ T(0, d / 2 + 0.012, -h / 2 + 0.13), w - 0.55, 0.012, 0.03, 0.0)                  # running-light strip
    B.box("Accent", M @ T(-w / 2 + 0.42, d / 2 + 0.014, -0.08), 0.28, 0.02, h - 0.55, 0.008)           # painted identity stripe
    for sx in (-1, 1):
        B.box("Light", M @ T(sx * (w / 2 + 0.008), -d / 2 + 0.2, h / 2 - 0.1), 0.012, 0.22, 0.03, 0.0)
    # inner-face plumbing
    for k in range(3):
        z = -0.4 + k * 0.4
        B.rod("Dark", M @ Vector((-w / 2 + 0.2, -d / 2 - 0.06, z)), M @ Vector((w / 2 - 0.2, -d / 2 - 0.06, z)), 0.035, 8)


def seams(B, M, w, d, h, step=0.42):
    """Thin dark groove lines on the outer, inner and roof faces: cheap, dense panel detail."""
    for face_y in (d / 2 + 0.004, -d / 2 - 0.004):
        x = -w / 2 + step
        while x < w / 2 - 0.1:
            B.box("Dark", M @ T(x, face_y, 0), 0.012, 0.006, h - 0.12, 0.0)
            x += step
        B.box("Dark", M @ T(0, face_y, 0.02), w - 0.12, 0.006, 0.012, 0.0)
    x = -w / 2 + step
    while x < w / 2 - 0.1:
        B.box("Dark", M @ T(x, 0, h / 2 + 0.004), 0.012, d - 0.12, 0.006, 0.0)
        x += step


def pressure_hab(B, M):
    """Cylindrical pressurised module (axis along the ring tangent) with domed ends."""
    B.cyl("Hull", M @ Ry(math.pi / 2), 0.86, 2.3, 40)
    for s_ in (-1, 1):
        dome = [(0.86, 0.0), (0.8, 0.18), (0.62, 0.36), (0.42, 0.46)]
        B.lathe("HullWarm", M @ T(s_ * 1.15, 0, 0) @ Ry(s_ * math.pi / 2), dome, 40)
        B.cyl("Metal", M @ T(s_ * 1.62, 0, 0) @ Ry(math.pi / 2), 0.46, 0.14, 28)
        B.cyl("Dark", M @ T(s_ * 1.72, 0, 0) @ Ry(math.pi / 2), 0.4, 0.1, 28)
    for k in range(5):            # circumferential bands
        B.cyl("Metal" if k % 2 == 0 else "HullPanel", M @ T(-0.92 + k * 0.46, 0, 0) @ Ry(math.pi / 2), 0.885, 0.05, 40)
    for k in range(4):            # longitudinal stringers
        a = k / 4 * math.tau + math.pi / 4
        B.box("HullPanel", M @ T(0, math.cos(a) * 0.87, math.sin(a) * 0.87) @ Rx(a), 2.2, 0.02, 0.1, 0.0)
    for k in range(4):            # portholes facing outward
        x = -0.75 + k * 0.5
        B.cyl("Metal", M @ T(x, 0.86, 0.15) @ Rx(-math.pi / 2), 0.13, 0.04, 20)
        B.cyl("Window", M @ T(x, 0.885, 0.15) @ Rx(-math.pi / 2), 0.09, 0.02, 20)
    handrail(B, M, (-1.0, 0.95, -0.45), (1.0, 0.95, -0.45))
    handrail(B, M, (-1.0, 0.8, 0.6), (1.0, 0.8, 0.6))
    for s_ in (-1, 1):
        rcs_quad(B, M @ T(s_ * 0.9, 0.55, 0.75))
        B.sphere("NavLight", M @ T(s_ * 1.0, 0.0, 0.9), 0.035, 10, 6)
    B.box("Radiator", M @ T(0, -0.2, 1.05), 1.6, 0.9, 0.03, 0.01)
    for k in range(6):
        B.box("Metal", M @ T(-0.65 + k * 0.26, -0.2, 1.08), 0.02, 0.9, 0.02, 0.0)
    B.rod("Metal", M @ Vector((0, -0.2, 0.86)), M @ Vector((0, -0.2, 1.04)), 0.05, 8)


def solar_wing(B, root, tip, side):
    """Truss boom with two solar blankets either side, ISS-style."""
    root, tip = Vector(root), Vector(tip)
    truss(B, root, tip, r=0.16, bay=0.45)
    d = (tip - root)
    L = d.length
    rot = d.normalized().to_track_quat("Z", "X").to_matrix().to_4x4()
    for s_ in (-1, 1):
        for seg in range(2):
            c = root.lerp(tip, 0.3 + seg * 0.37)
            M = Matrix.Translation(c) @ rot @ T(s_ * 0.95, 0, 0)
            B.box("Solar", M, 1.3, 0.025, L * 0.34, 0.0)
            for k in range(7):    # cell grid
                B.box("Metal", M @ T(-0.65 + k * 1.3 / 6, 0.016, 0), 0.008, 0.006, L * 0.34, 0.0)
            n = 14
            for k in range(n + 1):
                B.box("Metal", M @ T(0, 0.016, -L * 0.17 + k * L * 0.34 / n), 1.3, 0.006, 0.008, 0.0)
            for e in (-1, 1):     # frame
                B.box("Metal", M @ T(e * 0.66, 0, 0), 0.03, 0.04, L * 0.345, 0.0)


# ─── modules ──────────────────────────────────────────────────────────────────
def solar_joints(B, root, tip):
    """Rotary joint at the root and hinge barrels along the boom."""
    root, tip = Vector(root), Vector(tip)
    d = (tip - root).normalized()
    rot = d.to_track_quat("Z", "Y").to_matrix().to_4x4()
    B.cyl("Metal", Matrix.Translation(root + d * 0.3) @ rot, 0.34, 0.5, 32)
    B.cyl("Accent", Matrix.Translation(root + d * 0.3) @ rot, 0.355, 0.1, 32)
    for k in range(1, 5):
        B.cyl("Metal", Matrix.Translation(root.lerp(tip, k / 5)) @ rot, 0.22, 0.1, 20)


def habitat(B, M):
    module_shell(B, M)
    if rng.random() < 0.6:   # small dish or sensor pod on the roof
        B.cyl("Metal", M @ T(0.5, -0.2, 0.92), 0.08, 0.2, 12)
        B.lathe("Dish", M @ T(0.5, -0.2, 1.05), [(0.0, 0.0), (0.12, 0.01), (0.24, 0.05), (0.3, 0.09)], 20)


def engine_block(B, M):
    module_shell(B, M, windows=False)
    for sx in (-0.7, 0, 0.7):
        bell = [(0.12, 0.0), (0.16, -0.05), (0.22, -0.18), (0.3, -0.36), (0.34, -0.48)]
        B.lathe("Dark", M @ T(sx, -0.1, -0.78), bell, 24)
        B.cyl("Metal", M @ T(sx, -0.1, -0.76), 0.14, 0.06, 18)
    for sx in (-0.55, 0.55):
        B.sphere("Hull", M @ T(sx, 0.1, 0.95), 0.36, 24, 14)
        B.cyl("Metal", M @ T(sx, 0.1, 0.95), 0.37, 0.04, 24)


def command_module(B, M, coll):
    w, d, h = 3.0, 2.1, 1.8
    module_shell(B, M, w, d, h, windows=False, plates=False)
    # canopy on the roof, angled windows looking outward
    B.box("Hull", M @ T(-0.45, 0.35, h / 2 + 0.22), 1.6, 1.0, 0.42, 0.1, 2)
    for k in range(4):
        B.box("Window", M @ T(-1.0 + k * 0.37, 0.86, h / 2 + 0.28) @ Rx(-0.5), 0.3, 0.02, 0.22, 0.01)
    # outer face: plate region (left) and the cipher-core bay (right)
    B.box("HullPanel", M @ T(-0.75, d / 2 + 0.012, -0.25), 1.2, 0.025, 0.7, 0.012)
    bay = M @ T(0.7, d / 2, -0.25)
    bw, bh, bd = 0.95, 0.95, 0.42
    B.box("Metal", bay @ T(-bw / 2, bd / 2, 0), 0.05, bd, bh + 0.05, 0.01)
    B.box("Metal", bay @ T(bw / 2, bd / 2, 0), 0.05, bd, bh + 0.05, 0.01)
    B.box("Metal", bay @ T(0, bd / 2, bh / 2), bw + 0.05, bd, 0.05, 0.01)
    B.box("Metal", bay @ T(0, bd / 2, -bh / 2), bw + 0.05, bd, 0.05, 0.01)
    B.box("Dark", bay @ T(0, 0.02, 0), bw, 0.02, bh, 0.0)
    for k in range(4):   # interior rails
        B.box("Metal", bay @ T(-0.3 + k * 0.2, 0.06, 0), 0.025, 0.06, bh - 0.1, 0.0)
    for sx in (-1, 1):
        for sz in (-1, 1):
            B.box("Metal", M @ T(sx * (w / 2 - 0.3), d / 2 + 0.06, sz * 0.62), 0.22, 0.08, 0.12, 0.02)
    empty("A_core", bay @ T(0, bd / 2, 0), coll)
    empty("A_plate", M @ T(-0.75, d / 2 + 0.03, -0.25), coll)
    empty("F_command", M, coll)

    # the door: its own object, hinge on the left edge of the bay opening
    D = Builder()
    D.box("HullPanel", T(bw / 2, 0.025, 0), bw - 0.02, 0.05, bh - 0.02, 0.012)
    for zz in (-0.3, 0, 0.3):
        D.box("Metal", T(bw / 2, 0.055, zz), 0.78, 0.012, 0.025, 0.0)
    D.box("Metal", T(bw - 0.12, 0.07, 0), 0.06, 0.04, 0.18, 0.01)
    door = D.to_object("BayDoor", coll)
    hinge_world = bay @ T(-bw / 2, bd, 0)
    for ob in door:
        ob.matrix_world = hinge_world
    return door


def imaging_module(B, M, coll):
    module_shell(B, M)
    lens = M @ T(0.4, 1.0, -0.15) @ Rx(-math.pi / 2)    # local Z → module outward
    B.cyl("Hull", lens @ T(0, 0, 0.35), 0.4, 0.7, 32)
    B.cyl("Metal", lens @ T(0, 0, 0.72), 0.43, 0.06, 32)
    B.lathe("Dark", lens @ T(0, 0, 0.75), [(0.4, 0.0), (0.44, 0.2), (0.48, 0.45)], 32)
    B.cyl("Glass", lens @ T(0, 0, 0.73), 0.33, 0.02, 32)
    for k in range(3):
        B.cyl("Metal", lens @ T(0, 0, 0.12 + k * 0.18), 0.41, 0.025, 32)
    empty("A_lens", M @ T(0.4, 1.75, -0.15), coll)
    empty("F_imaging", M, coll)


def comms_module(B, M, coll):
    module_shell(B, M)
    base = M @ T(0, 0.2, 0.76)
    B.cyl("Metal", base @ T(0, 0, 0.03), 0.42, 0.06, 32)
    pts = []
    for k in range(281):
        t = k / 280
        a = t * math.tau * 7
        pts.append((base @ T(math.cos(a) * 0.17, math.sin(a) * 0.17, 0.06 + t * 1.4)) @ Vector((0, 0, 0)))
    B.tube("Metal", pts, 0.014, 6)
    B.rod("Hull", base @ Vector((0, 0, 0.06)), base @ Vector((0, 0, 1.55)), 0.03, 8)
    for sx, sy in ((-1, -1), (1, -1), (-1, 1), (1, 1)):
        a = M @ Vector((sx * 1.1, sy * 0.8, 0.76))
        b = M @ Vector((sx * 1.75, sy * 1.35, 2.0))
        B.rod("Radiator", a, b, 0.013, 5)
    empty("A_comms", base @ T(0, 0, 0.75), coll)
    empty("F_comms", M, coll)


def lander(B, M, coll):
    # wedge-nosed craft docked radially: build a lofted hull from two trapezoids
    t = bmesh.new()
    rear = [(-1.3, -0.7), (1.3, -0.7), (1.05, 0.6), (-1.05, 0.6)]
    front = [(-0.9, -0.55), (0.9, -0.55), (0.55, 0.35), (-0.55, 0.35)]
    vr = [t.verts.new((x, -0.9, z)) for x, z in rear]
    vf = [t.verts.new((x, 2.4, z)) for x, z in front]
    t.faces.new(vr[::-1])
    t.faces.new(vf)
    for k in range(4):
        t.faces.new((vr[k], vr[(k + 1) % 4], vf[(k + 1) % 4], vf[k]))
    bmesh.ops.bevel(t, geom=t.edges[:], offset=0.06, segments=2, profile=0.5, affect="EDGES", clamp_overlap=True)
    B.commit("Hull", t, M @ T(0, 0.3, 0))
    for k in range(5):
        B.box("Window", M @ T(-0.5 + k * 0.25, 2.62, 0.18) @ Rx(-0.35), 0.18, 0.02, 0.12, 0.008)
    for sx in (-1, 1):
        B.box("HullPanel", M @ T(sx * 1.25, 0.6, -0.2) @ Ry(sx * 0.25), 0.12, 1.8, 0.7, 0.03)
        B.lathe("Dark", M @ T(sx * 0.7, -0.75, -0.3) @ Rx(math.pi / 2), [(0.1, 0.0), (0.16, -0.1), (0.24, -0.3)], 20)
    B.cyl("Metal", M @ T(0, -0.85, 0) @ Rx(math.pi / 2), 0.5, 0.2, 28)
    greebles(B, M @ T(0, 0.8, 0.0), 1.6, 2.0, 7, 0.62)
    empty("A_lander", M @ T(0, 1.2, 0.8), coll)


# ─── ring structure ───────────────────────────────────────────────────────────
def corridor(B, i):
    th0 = math.radians(i * 30 + 9.5)
    th1 = math.radians((i + 1) * 30 - 9.5)
    a = Vector((R * math.cos(th0), R * math.sin(th0), 0))
    b = Vector((R * math.cos(th1), R * math.sin(th1), 0))
    B.rod("Hull", a, b, 0.32, 32)
    d = (b - a)
    n = int(d.length / 0.32)
    rot = d.normalized().to_track_quat("Z", "Y").to_matrix().to_4x4()
    for k in range(1, n):
        p = a.lerp(b, k / n)
        B.cyl("Metal" if k % 3 == 0 else "HullPanel", Matrix.Translation(p) @ rot, 0.345, 0.05, 24)
    for p in (a, b):
        B.cyl("Metal", Matrix.Translation(p) @ rot, 0.42, 0.14, 24)
    for k in range(2, n, 4):
        B.cyl("Light", Matrix.Translation(a.lerp(b, k / n)) @ rot, 0.352, 0.03, 24)
    up = Vector((0, 0, 1))
    side = d.normalized().cross(up)
    B.rod("Dark", a + side * 0.36 + up * 0.18, b + side * 0.36 + up * 0.18, 0.045, 8)
    B.rod("Dark", a - side * 0.36 - up * 0.12, b - side * 0.36 - up * 0.12, 0.03, 8)


def truss(B, a, b, r=0.24, bay=0.55):
    a, b = Vector(a), Vector(b)
    d = (b - a)
    rot = d.normalized().to_track_quat("Z", "Y").to_matrix()
    offs = [rot @ Vector((math.cos(k * math.tau / 3) * r, math.sin(k * math.tau / 3) * r, 0)) for k in range(3)]
    for o in offs:
        B.rod("Metal", a + o, b + o, 0.03, 6)
    n = max(1, int(d.length / bay))
    for k in range(n + 1):
        p = a.lerp(b, k / n)
        for j in range(3):
            B.rod("Metal", p + offs[j], p + offs[(j + 1) % 3], 0.016, 5)
        if k < n:
            q = a.lerp(b, (k + 1) / n)
            for j in range(3):
                B.rod("Metal", p + offs[j], q + offs[(j + 1) % 3], 0.014, 5)


def hub(B, coll):
    B.cyl("Hull", T(0, 0, 0), 1.4, 3.2, 64)
    for z in (-1.2, 0.0, 1.2):
        B.cyl("Metal", T(0, 0, z), 1.46, 0.1, 64)
    for z in (-0.6, 0.6):                          # lit bands between the structural rings
        B.cyl("Light", T(0, 0, z), 1.425, 0.035, 64)
    for k in range(16):                            # panel plates around the drum
        a = k / 16 * math.tau
        for z in (-0.6, 0.6):
            B.box(rng.choice(["HullPanel", "HullWarm", "Accent" if k % 8 == 0 else "Hull"]), T(math.cos(a) * 1.41, math.sin(a) * 1.41, z) @ Rz(a), 0.03, 0.46, 0.95, 0.01)
    for k in range(8):                             # docking hatches
        a = k / 8 * math.tau + math.pi / 8
        for z in (-1.0, 1.0):
            hatch = T(math.cos(a) * 1.46, math.sin(a) * 1.46, z) @ Rz(a) @ Ry(math.pi / 2)
            B.cyl("Metal", hatch, 0.17, 0.06, 20)
            B.cyl("Dark", hatch @ T(0, 0, 0.03), 0.12, 0.02, 20)
    B.lathe("Hull", T(0, 0, 1.6), [(1.4, 0.0), (1.2, 0.35), (0.9, 0.7)], 64)
    B.cyl("Metal", T(0, 0, 2.4), 0.9, 0.2, 48)
    for k in range(6):                             # sensor cluster on the cap
        a = k / 6 * math.tau
        B.sphere("Dark", T(math.cos(a) * 0.62, math.sin(a) * 0.62, 2.52), 0.07, 12, 8)
    B.lathe("Hull", T(0, 0, -1.6), [(1.4, 0.0), (1.2, -0.35), (1.0, -0.6)], 64)
    B.cyl("Metal", T(0, 0, -2.45), 0.82, 0.5, 48)
    B.cyl("Dark", T(0, 0, -2.75), 0.86, 0.12, 48)
    for k in range(3):
        a = k / 3 * math.tau
        B.box("Metal", T(math.cos(a) * 0.7, math.sin(a) * 0.7, -2.85) @ Rz(a), 0.25, 0.12, 0.2, 0.02)
    for k in range(4):                             # tanks between the spokes, strapped
        a = (k + 0.5) / 4 * math.tau + math.radians(30)
        p = T(math.cos(a) * 2.05, math.sin(a) * 2.05, 0)
        B.sphere("Hull", p, 0.5, 40, 22)
        for off in (-0.2, 0.0, 0.2):
            B.cyl("Metal", p @ T(0, 0, off), 0.512, 0.04, 40)
        B.rod("Metal", (math.cos(a) * 1.4, math.sin(a) * 1.4, 0.0), (math.cos(a) * 1.6, math.sin(a) * 1.6, 0.0), 0.06, 8)
    # tall mast: the dish is aimed sideways at the home world, so its tilted bowl needs the room
    B.cyl("Metal", T(0, 0, 3.7), 0.15, 2.6, 24)
    B.cyl("Accent", T(0, 0, 2.62), 0.2, 0.12, 24)
    truss(B, (0, 0, 2.5), (0, 0, 4.9), r=0.2, bay=0.4)
    B.cyl("Metal", T(0, 0, 5.0), 0.3, 0.2, 28)
    for sx in (-1, 1):                             # small trim antennas beside the mast
        B.rod("Metal", (sx * 0.5, 0.0, 2.55), (sx * 0.7, 0.0, 3.9), 0.014, 6)
        B.sphere("Metal", T(sx * 0.7, 0.0, 3.92), 0.05, 12, 8)
    empty("A_dish", T(0, 0, 5.4), coll)


def dish(coll):
    """Dish assembly in its own frame: mount at the origin, opening toward +Z."""
    D = Builder()
    f, Rd = 0.75, 1.6
    prof = [(Rd * k / 24, (Rd * k / 24) ** 2 / (4 * f)) for k in range(25)]
    D.lathe("Dish", T(0, 0, 0.3), prof, 96)
    back = [(r, z - 0.05) for r, z in prof]
    D.lathe("HullPanel", T(0, 0, 0.3), back[::-1], 96)
    zr = Rd * Rd / (4 * f) + 0.3
    D.lathe("Metal", T(0, 0, 0), [(Rd, zr - 0.03), (Rd + 0.05, zr), (Rd, zr + 0.03)], 64)
    for k in range(12):           # back ribs
        a = k / 12 * math.tau
        D.rod("Metal", (math.cos(a) * 0.2, math.sin(a) * 0.2, 0.25), (math.cos(a) * Rd, math.sin(a) * Rd, zr - 0.06), 0.022, 5)
    focus = Vector((0, 0, 0.3 + f))
    for k in range(4):
        a = k / 4 * math.tau + 0.4
        D.rod("Metal", (math.cos(a) * Rd * 0.92, math.sin(a) * Rd * 0.92, zr - 0.02), focus + Vector((0, 0, 0.1)), 0.016, 6)
    D.lathe("Dark", T(0, 0, 0.3 + f - 0.12), [(0.04, 0.0), (0.09, 0.08), (0.13, 0.24)], 20)
    D.cyl("Dish", T(0, 0, 0.3 + f + 0.2), 0.22, 0.03, 24)
    D.cyl("Metal", T(0, 0, 0.12), 0.18, 0.3, 20)
    for s in (-1, 1):             # gimbal yoke
        D.box("Metal", T(s * 0.32, 0, -0.05), 0.08, 0.16, 0.45, 0.02)
    D.cyl("Metal", T(0, 0, -0.25) @ Ry(math.pi / 2), 0.08, 0.72, 14)
    objs = D.to_object("Dish", coll)
    return objs


def world_tree(obj, matrix=None):
    """BVH tree of an object's mesh in world space (BVHTree.FromObject ignores the transform)."""
    from mathutils.bvhtree import BVHTree
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.transform(matrix if matrix is not None else obj.matrix_world)
    bmesh.ops.triangulate(bm, faces=bm.faces)
    tree = BVHTree.FromBMesh(bm)
    bm.free()
    return tree


def analyze(dish_objs, mount):
    """Report unexpected overlaps between parts, and between the dish (at many aim directions) and everything."""
    base = {}
    for ob in bpy.data.objects:
        if ob.type != "MESH" or ob in dish_objs:
            continue
        head, _, last = ob.name.rpartition("_")
        key = head if last in MATS else ob.name
        base.setdefault(key, []).append(world_tree(ob))
    allowed = set()
    for i in range(12):
        allowed.add(frozenset((f"mod{i}", f"cor{i}")))
        allowed.add(frozenset((f"mod{(i + 1) % 12}", f"cor{i}")))
    for i in (1, 4, 7, 10):
        for other in ("hub", f"mod{i}", f"cor{i}", f"cor{i - 1}"):
            allowed.add(frozenset((f"spoke{i}", other)))
    for s_ in (-1, 1):
        allowed.add(frozenset((f"wing{s_}", "hub")))
    names = sorted(base)
    print("[analyze] part-vs-part overlaps (triangle pairs):")
    found = 0
    for ai in range(len(names)):
        for bi in range(ai + 1, len(names)):
            a, b = names[ai], names[bi]
            if frozenset((a, b)) in allowed:
                continue
            n = sum(len(ta.overlap(tb)) for ta in base[a] for tb in base[b])
            if n:
                found += 1
                print(f"   {a:8s} x {b:8s}: {n}")
    if not found:
        print("   none")
    print("[analyze] dish at aim directions (tilt from the mast axis, azimuth) vs the rest:")
    pivot = mount.to_translation()
    worst = []
    total = 0
    for tilt in (30, 55, 80, 100, 120, 150):
        for az in range(0, 360, 30):
            total += 1
            rot = Matrix.Rotation(math.radians(az), 4, "Z") @ Matrix.Rotation(math.radians(tilt), 4, "X")
            M = Matrix.Translation(pivot) @ rot @ Matrix.Translation(-pivot) @ mount
            hit = {}
            for ob in dish_objs:
                tree = world_tree(ob, M)
                for name, trees in base.items():
                    n = sum(len(tree.overlap(t)) for t in trees)
                    if n:
                        hit[name] = hit.get(name, 0) + n
            if hit:
                worst.append((tilt, az, hit))
    for tilt, az, hit in worst[:12]:
        print(f"   tilt {tilt:3d} az {az:3d}: {hit}")
    print(f"   {len(worst)} of {total} orientations collide")


ANALYZE = bool(os.environ.get("SS_ANALYZE"))


def main():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    for name, spec in MATS.items():
        make_material(name, **spec)
    coll = bpy.context.scene.collection
    shared = Builder()
    parts = {}

    def part(name):
        """One shared builder for the export; a builder per part when measuring overlaps."""
        if not ANALYZE:
            return shared
        parts[name] = Builder()
        return parts[name]

    for i in range(12):
        M = module_matrix(i)
        Bm = part(f"mod{i}")
        if i == 0:
            command_module(Bm, M, coll)
        elif i == 3:
            imaging_module(Bm, M, coll)
        elif i == 6:
            comms_module(Bm, M, coll)
        elif i == 9:
            lander(Bm, M, coll)
        elif i % 3 == 2:
            engine_block(Bm, M)
        elif i in (4, 10):
            pressure_hab(Bm, M)
        else:
            habitat(Bm, M)
        corridor(part(f"cor{i}"), i)
    for i in (1, 4, 7, 10):
        th = math.radians(i * 30)
        d = Vector((math.cos(th), math.sin(th), 0))
        truss(part(f"spoke{i}"), d * 1.45 + Vector((0, 0, 0.4)), d * (R - 1.0) + Vector((0, 0, 0.1)))
    hub(part("hub"), coll)
    for s_ in (-1, 1):
        Bw = part(f"wing{s_}")
        root, tip = (0.0, s_ * 1.45, -0.9), (0.0, s_ * 7.6, -1.5)
        solar_wing(Bw, root, tip, s_)
        solar_joints(Bw, root, tip)
    if not ANALYZE:
        shared.to_object("Ship", coll)
    else:
        for name, bld in parts.items():
            bld.to_object(name, coll)

    dish_objs = dish(coll)
    mount = bpy.data.objects["A_dish"].matrix_world
    for ob in dish_objs:
        ob.matrix_world = mount
    if ANALYZE:
        analyze(dish_objs, mount)
        return
    if len(dish_objs) > 1:          # parent the per-material dish meshes under one node
        root = empty("Dish", mount, coll)
        for ob in dish_objs:
            ob.parent = root
            ob.matrix_parent_inverse = root.matrix_world.inverted()
    door = [o for o in bpy.data.objects if o.name.startswith("BayDoor")]
    if len(door) > 1:
        root = empty("BayDoor", door[0].matrix_world.copy(), coll)
        for ob in door:
            ob.parent = root
            ob.matrix_parent_inverse = root.matrix_world.inverted()

    tris = sum(len(p.vertices) - 2 for o in bpy.data.objects if o.type == "MESH" for p in o.data.polygons)
    print(f"[ship] objects={len(bpy.data.objects)} triangles≈{tris}")
    bpy.ops.export_scene.gltf(filepath=OUT, export_format="GLB", export_yup=True, export_apply=True,
                              use_selection=False, export_materials="EXPORT")
    print(f"[ship] wrote {OUT}")


main()
