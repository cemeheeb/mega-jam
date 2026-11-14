"""Mutant rat (SourceArt/characters/mutant-rat): mesh from Tripo, quadruped skeleton, weights.

Run in the live Blender (MCP) on source/mutant-rat.blend: exec(open(<this file>).read()).
Order: this script, then mutant_rat_normals.py (fixes Tripo's normals), then mutant_rat_anim.py (animations).

Mesh: source/tripo/mutant_rat.fbx as is (only the colour texture from Tripo), scaled x2 so that the body is about
1.1 m from the nose to the base of the tail (asset.yml); the whole rat 2.0 m with the tail, 0.82 m high at the hump.
Facing -Y like every asset (+Y in Unreal), paws on z = 0, origin between the paws.

Skeleton (armature object `root`, as the hero's; deform bones in Unreal naming, measured on the Tripo mesh):
pelvis -> spine_01 -> spine_02 -> spine_03 -> neck -> head; pelvis -> tail_01..tail_08;
spine_03 -> scapula_l -> upperarm_l -> lowerarm_l -> hand_l; pelvis -> thigh_l -> calf_l -> foot_l -> ball_l; and _r.
Bone roll: the local X axis of every bone points along +X of the world, so a rotation about X is a bend in the
side view for the spine, the tail and the legs alike.
Control bones (not deforming, not exported): ik_hand_l (at the wrist) with its child ik_hand_tip_l (toes),
ik_foot_l (at the hock) with ik_foot_ball_l (ball of the foot); legs are 2-bone IK hinges plus a 1-bone IK for the paw,
so the paws stay on the floor while the body moves.
"""
import bpy, bmesh
from mathutils import Vector, Matrix, kdtree

SCALE = 2.0
TRIPO = 'ReferenceTripo'
MESH = 'MutantRat'
ARM = 'root'

# measured on the Tripo mesh (its units: the rat is 1.0 long), side +x; (x, y, z)
SPINE = [(0, 0.03, 0.235), (0, -0.05, 0.245), (0, -0.14, 0.255), (0, -0.23, 0.265), (0, -0.33, 0.27),
         (0, -0.40, 0.285), (0, -0.51, 0.27)]
SPINE_NAMES = ['pelvis', 'spine_01', 'spine_02', 'spine_03', 'neck', 'head']
TAIL = [(0, 0.035, 0.228), (0, 0.10, 0.195), (0, 0.16, 0.172), (0, 0.22, 0.160), (0, 0.28, 0.143), (0, 0.34, 0.133),
        (0, 0.40, 0.121), (0, 0.46, 0.111), (0, 0.505, 0.107)]
FRONT = [(0.045, -0.29, 0.33), (0.068, -0.31, 0.215), (0.075, -0.262, 0.12), (0.08, -0.322, 0.035), (0.085, -0.385, 0.012)]
FRONT_NAMES = ['scapula', 'upperarm', 'lowerarm', 'hand']
HIND = [(0.06, -0.02, 0.215), (0.075, -0.075, 0.125), (0.08, 0.028, 0.045), (0.083, -0.03, 0.012), (0.083, -0.05, 0.008)]
HIND_NAMES = ['thigh', 'calf', 'foot', 'ball']

V = lambda p, sx=1: Vector((p[0] * sx, p[1], p[2])) * SCALE


def clear(name):
    ob = bpy.data.objects.get(name)
    if ob:
        data = ob.data
        bpy.data.objects.remove(ob)
        if data and data.users == 0:
            (bpy.data.meshes if isinstance(data, bpy.types.Mesh) else bpy.data.armatures).remove(data)


col = bpy.data.collections.get('MutantRat') or bpy.data.collections.new('MutantRat')
if col.name not in bpy.context.scene.collection.children:
    bpy.context.scene.collection.children.link(col)

# ---------------- mesh ----------------
src = bpy.data.objects.get(TRIPO)
clear(MESH)
me = src.data.copy()
me.name = MESH + '.Mesh'
me.transform(Matrix.Scale(SCALE, 4))
ob = bpy.data.objects.new(MESH, me)
col.objects.link(ob)
src.hide_set(True)
src.hide_render = True

mat = bpy.data.materials.get(MESH) or bpy.data.materials.new(MESH)
mat.use_nodes = True
nt = mat.node_tree
for n in list(nt.nodes):
    nt.nodes.remove(n)
out = nt.nodes.new('ShaderNodeOutputMaterial')
bsdf = nt.nodes.new('ShaderNodeBsdfPrincipled')
tex = nt.nodes.new('ShaderNodeTexImage')
img = bpy.data.images.load('//tripo/mutant_rat_basecolor.jpg', check_existing=True)
tex.image = img
nt.links.new(tex.outputs['Color'], bsdf.inputs['Base Color'])
bsdf.inputs['Roughness'].default_value = 0.85
nt.links.new(bsdf.outputs['BSDF'], out.inputs['Surface'])
out.location, bsdf.location, tex.location = (300, 0), (0, 0), (-400, 0)
me.materials.clear()
me.materials.append(mat)
if me.uv_layers:
    me.uv_layers[0].name = 'UVMap'

# ---------------- armature ----------------
clear(ARM)
arm = bpy.data.armatures.new(ARM)
rig = bpy.data.objects.new(ARM, arm)
col.objects.link(rig)
arm.display_type = 'STICK'
rig.show_in_front = True
bpy.context.view_layer.objects.active = rig
for o in bpy.context.selected_objects:
    o.select_set(False)
rig.select_set(True)
bpy.ops.object.mode_set(mode='EDIT')
eb = arm.edit_bones
X = Vector((1, 0, 0))


def bone(name, head, tail, parent=None, deform=True, connect=False):
    b = eb.new(name)
    b.head, b.tail = head, tail
    b.align_roll(X.cross((tail - head).normalized()))     # local X along world +X
    if parent:
        b.parent = eb[parent]
        b.use_connect = connect
    b.use_deform = deform
    return b


for i, n in enumerate(SPINE_NAMES):
    bone(n, V(SPINE[i]), V(SPINE[i + 1]), SPINE_NAMES[i - 1] if i else None, connect=i > 1)
for i in range(len(TAIL) - 1):
    bone(f'tail_{i + 1:02d}', V(TAIL[i]), V(TAIL[i + 1]), f'tail_{i:02d}' if i else 'pelvis', connect=i > 0)
for s, sx in (('l', 1), ('r', -1)):
    for i, n in enumerate(FRONT_NAMES):
        bone(f'{n}_{s}', V(FRONT[i], sx), V(FRONT[i + 1], sx), f'{FRONT_NAMES[i - 1]}_{s}' if i else 'spine_03', connect=i > 0)
    for i, n in enumerate(HIND_NAMES):
        bone(f'{n}_{s}', V(HIND[i], sx), V(HIND[i + 1], sx), f'{HIND_NAMES[i - 1]}_{s}' if i else 'pelvis', connect=i > 0)
    up = Vector((0, 0, 0.06))
    bone(f'ik_hand_{s}', V(FRONT[3], sx), V(FRONT[3], sx) + up, deform=False)
    bone(f'ik_hand_tip_{s}', V(FRONT[4], sx), V(FRONT[4], sx) + up * 0.5, f'ik_hand_{s}', deform=False)
    bone(f'ik_foot_{s}', V(HIND[2], sx), V(HIND[2], sx) + up, deform=False)
    bone(f'ik_foot_ball_{s}', V(HIND[3], sx), V(HIND[3], sx) + up * 0.5, f'ik_foot_{s}', deform=False)
bpy.ops.object.mode_set(mode='POSE')

pb = rig.pose.bones
for b in pb:
    b.rotation_mode = 'QUATERNION'


def ik(owner, target, chain):
    c = pb[owner].constraints.new('IK')
    c.target, c.subtarget, c.chain_count = rig, target, chain
    c.use_stretch = False
    return c


for s in ('l', 'r'):
    ik(f'lowerarm_{s}', f'ik_hand_{s}', 2)
    ik(f'hand_{s}', f'ik_hand_tip_{s}', 1)
    ik(f'calf_{s}', f'ik_foot_{s}', 2)
    ik(f'foot_{s}', f'ik_foot_ball_{s}', 1)
    for n in (f'upperarm_{s}', f'lowerarm_{s}', f'hand_{s}', f'thigh_{s}', f'calf_{s}', f'foot_{s}'):
        pb[n].lock_ik_y = True                          # no twist
        pb[n].lock_ik_z = n.startswith(('lowerarm', 'calf'))   # elbows, knees: hinges; shoulder, hip, paws swing out
        pb[n].ik_stretch = 0
bpy.ops.object.mode_set(mode='OBJECT')

# ---------------- weights ----------------
# Bone heat fails on this mesh (130 loose parts, open fur sheets: "failed to find solution"), so the weights are
# computed here: distance from the vertex to each bone segment divided by the bone's radius (body thick, legs and tail
# thin), w = (d / r)^-6, the four strongest kept (paws only from their own chain, see below); bones of
# one side never weigh the other side; then smoothed along the mesh edges so that the joints bend softly.
RADIUS = {'pelvis': 0.24, 'spine_01': 0.25, 'spine_02': 0.25, 'spine_03': 0.24, 'neck': 0.17, 'head': 0.12,
          'scapula': 0.09, 'upperarm': 0.07, 'lowerarm': 0.045, 'hand': 0.035,
          'thigh': 0.10, 'calf': 0.055, 'foot': 0.035, 'ball': 0.025}
TAIL_R = [0.06, 0.045, 0.035, 0.028, 0.022, 0.018, 0.014, 0.011]
SMOOTH = 4

ob.parent = rig
mod = ob.modifiers.new('Armature', 'ARMATURE')
mod.object = rig
deform = [b for b in arm.bones if b.use_deform]
segs = []
for b in deform:
    base = b.name[:-2] if b.name[-2:] in ('_l', '_r') else b.name
    r = TAIL_R[int(b.name[5:]) - 1] if b.name.startswith('tail_') else RADIUS[base]
    side = 1 if b.name.endswith('_l') else -1 if b.name.endswith('_r') else 0
    segs.append((b.name, b.head_local.copy(), b.tail_local.copy(), r, side))


def seg_dist(p, a, c):
    ab = c - a
    t = max(0.0, min(1.0, (p - a).dot(ab) / ab.length_squared))
    return (p - (a + ab * t)).length


# a vertex nearest (plain distance) to a paw bone takes weights only from the bones up to two links from it:
# otherwise the thick body bones reach the far claw tips (their radius beats the thin paw bones') and the claws stretch
# to the spine (author's screenshot of 15.11). Shoulders and hips keep all bones, so they still blend into the body.
DISTAL = ('hand', 'foot', 'ball')
link = {b.name: set() for b in deform}            # the bone tree, both ways; neighbours = up to two links away
for b in deform:
    if b.parent and b.parent.name in link:
        link[b.name].add(b.parent.name)
        link[b.parent.name].add(b.name)
near = {}
for n in link:
    one = link[n]
    near[n] = {n} | one | set().union(*(link[m] for m in one))
W = []
for v in me.vertices:
    p = v.co
    cand = [(seg_dist(p, a, c), name, r, side) for name, a, c, r, side in segs if not (side and p.x * side < -0.01)]
    nearest = min(cand)[1]
    allowed = near[nearest] if nearest[:-2] in DISTAL else None
    ws = [((d / r + 1e-3) ** -6, name) for d, name, r, side in cand if allowed is None or name in allowed]
    ws.sort(reverse=True)
    ws = ws[:4]
    tot = sum(w for w, n in ws)
    W.append({n: w / tot for w, n in ws})

bm = bmesh.new()
bm.from_mesh(me)
bm.verts.ensure_lookup_table()
nbr = [[e.other_vert(v).index for e in v.link_edges] for v in bm.verts]
bm.free()
for _ in range(SMOOTH):
    new = []
    for i, w in enumerate(W):
        if not nbr[i]:
            new.append(w)
            continue
        acc = {k: 0.5 * x for k, x in w.items()}
        f = 0.5 / len(nbr[i])
        for j in nbr[i]:
            for k, x in W[j].items():
                acc[k] = acc.get(k, 0.0) + f * x
        top = sorted(acc.items(), key=lambda kv: -kv[1])[:4]
        tot = sum(x for k, x in top)
        new.append({k: x / tot for k, x in top})
    W = new

for name, *_ in segs:
    ob.vertex_groups.new(name=name)
for i, w in enumerate(W):
    for k, x in w.items():
        if x > 1e-3:
            ob.vertex_groups[k].add([i], x, 'REPLACE')
print('vertices', len(me.vertices), 'weighted', sum(1 for w in W if w))
print('bones', len(arm.bones), 'deform', sum(1 for b in arm.bones if b.use_deform))
print('mesh dims m', tuple(round(d, 3) for d in ob.dimensions))
