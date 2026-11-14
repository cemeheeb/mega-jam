"""Poses of the dead man (SourceArt/characters/dead-man/source/dead-man.blend), for laying bodies about the level.

Run in that blend (rig "rig" from Rigify, mesh "DeadMan"). Every pose becomes a one-frame action P_DeadMan_<Kind><N>,
marked as a pose asset (Pose Library), and is placed on its anchor so the game can put it anywhere:

- Floor*, Curl*: lying on the floor. Origin = the pelvis over the floor; any turn about Z is fine.
- Wall*: slumped against a wall. The wall is the plane y = 0 behind the body (the body is at y < 0, facing -Y),
  origin on the floor at the wall, under the pelvis. In the game: origin at the foot of a wall, +Y into the wall.
- Embed*: teleported into a wall. The wall's face is the plane y = 0, the wall is y > 0; what is in the wall is
  hidden by it. Walls are 30 cm thick (RunRoom.h, Wall), so on export the mesh is cut at y = EMBED_CUT.
- Table*, Console*: on the back on a table (top 0.78 m, 0.8 deep) or a console (1.0 m, 0.6 deep), only on the back:
  face down the hair looks like clay (the author, 15.11). The front edge of the top is the line y = 0 at its height,
  the top is 0 < y < depth; origin on the floor under the edge, under the pelvis. In the game: +Y into the furniture.

Limbs are posed in FK (Rigify IK_FK = 1), the head and the neck follow the torso. The ankle's + bend points the
toes (a lying foot falls that way). Then the arms fall under gravity onto the floor, the body, the wall or the top
(drop_arms), except in Embed*. Directions are given in the body's
own axes at rest: X its left, -Y its front, Z up. aim(bone, D, Z): the bone points along D, and the joint below it
folds towards Z (the elbow and the knee bend with +X turns of the forearm / the shin, towards their +Z).
"""
import bpy
from math import radians, atan2
from mathutils import Vector, Matrix, Quaternion
from mathutils.bvhtree import BVHTree
import numpy as np

rig = bpy.data.objects['rig']
ob = bpy.data.objects['DeadMan']
pb = rig.pose.bones
EMBED_CUT = 0.28          # m into the wall: the rest of the body is cut away on export
LIMBS = ('upper_arm_parent.L', 'upper_arm_parent.R', 'thigh_parent.L', 'thigh_parent.R')
CONTROLS = [b.name for b in pb if not b.name.startswith(('DEF-', 'ORG-', 'MCH-', 'VIS_'))]


def upd():
    bpy.context.view_layer.update()


def reset():
    for b in pb:
        b.location = (0, 0, 0)
        b.rotation_quaternion = (1, 0, 0, 0)
        b.rotation_euler = (0, 0, 0)
        b.scale = (1, 1, 1)
    for n in LIMBS:
        pb[n]['IK_FK'] = 1.0
    pb['torso']['head_follow'] = 1.0
    pb['torso']['neck_follow'] = 1.0
    upd()


def wmat(name):
    return rig.matrix_world @ pb[name].matrix


def delta(name):
    """World turn of a bone in the pose against its rest."""
    rest = (rig.matrix_world @ pb[name].bone.matrix_local).to_quaternion()
    return wmat(name).to_quaternion() @ rest.inverted()


def set_wmat(name, M):
    pb[name].matrix = rig.matrix_world.inverted() @ M
    upd()


def turn(name, axis, deg, frame='torso'):
    """Turns a control about an axis of the body (X left, Y back, Z up, carried by the frame bone), about its head.
    +X bends forward, +Y leans to the body's left, +Z turns to its left."""
    upd()
    a = (delta(frame) @ Vector(axis)).normalized()
    M = wmat(name)
    p = M.translation.copy()
    R = Quaternion(a, radians(deg)).to_matrix().to_4x4()
    set_wmat(name, Matrix.Translation(p) @ R @ Matrix.Translation(-p) @ M)


def bend(name, deg):
    """Turn about the bone's own X: the elbow, the knee, the wrist, the ankle fold with +."""
    upd()
    M = wmat(name)
    a = M.to_3x3().col[0].normalized()
    p = M.translation.copy()
    set_wmat(name, Matrix.Translation(p) @ Quaternion(a, radians(deg)).to_matrix().to_4x4() @ Matrix.Translation(-p) @ M)


def twist(name, deg):
    upd()
    M = wmat(name)
    a = M.to_3x3().col[1].normalized()
    p = M.translation.copy()
    set_wmat(name, Matrix.Translation(p) @ Quaternion(a, radians(deg)).to_matrix().to_4x4() @ Matrix.Translation(-p) @ M)


def aim(name, D, Z, frame):
    upd()
    R = delta(frame)
    y = (R @ Vector(D)).normalized()
    z = R @ Vector(Z)
    z = (z - y * z.dot(y)).normalized()
    x = y.cross(z)
    M = wmat(name)
    rot = Matrix((x, y, z)).transposed().to_4x4()
    set_wmat(name, Matrix.Translation(M.translation) @ rot)


def arm(s, D, Z, elbow=10, wrist=0, hand_twist=0, frame='chest'):
    """s: 'L' or 'R'. D, Z in the body's axes as they are (no mirroring): the left arm goes out along +X."""
    aim(f'upper_arm_fk.{s}', D, Z, frame)
    bend(f'forearm_fk.{s}', elbow)
    bend(f'hand_fk.{s}', wrist)
    if hand_twist:
        twist(f'hand_fk.{s}', hand_twist)


def leg(s, D, Z=(0, 1, 0), knee=5, ankle=0, frame='hips'):
    aim(f'thigh_fk.{s}', D, Z, frame)
    bend(f'shin_fk.{s}', knee)
    bend(f'foot_fk.{s}', ankle)


def body_points():
    dg = bpy.context.evaluated_depsgraph_get()
    e = ob.evaluated_get(dg)
    m = e.to_mesh()
    co = np.empty(len(m.vertices) * 3)
    m.vertices.foreach_get('co', co)
    e.to_mesh_clear()
    co = co.reshape(-1, 3)
    M = np.array(ob.matrix_world)
    return co @ M[:3, :3].T + M[:3, 3]


_groups = {g.index: g.name for g in ob.vertex_groups}
_dom = np.array([_groups[max(v.groups, key=lambda g: g.weight).group] for v in ob.data.vertices])
CORE = np.isin(_dom, ['DEF-spine', 'DEF-spine.001', 'DEF-spine.002', 'DEF-spine.003', 'DEF-spine.005', 'DEF-spine.006',
                      'DEF-pelvis.L', 'DEF-pelvis.R', 'DEF-thigh.L', 'DEF-thigh.R', 'DEF-shoulder.L', 'DEF-shoulder.R',
                      'DEF-breast.L', 'DEF-breast.R'])
SINK = 0.025              # m: arms and legs may go this far into the floor, the trunk and the head lie on it


LIMB_BONES = {f'{k}.{s}': np.isin(_dom, [f'DEF-{b}.{s}{x}' for b in bones for x in ('', '.001')])
              for s in ('L', 'R') for k, bones in (('arm', ('upper_arm', 'forearm', 'hand')),
                                                  ('leg', ('thigh', 'shin', 'foot', 'toe')))}
LIMB_ROOT = {'arm': 'upper_arm_fk', 'leg': 'thigh_fk'}


def settle(limb, floor=0.0):
    """Drops (or lifts) a limb about its shoulder / hip, round a level axis across it, until it rests on the floor
    (or on a top at that height)."""
    kind, s = limb.split('.')
    root = f'{LIMB_ROOT[kind]}.{s}'
    m = LIMB_BONES[limb]

    def low():
        return body_points()[m, 2].min() - floor

    for _ in range(4):
        z0 = low()
        if abs(z0) < 0.004:
            return
        upd()
        M = wmat(root)
        d = M.to_3x3().col[1]
        a = Vector((d.x, d.y, 0)).cross(Vector((0, 0, 1)))
        if a.length < 1e-3:
            return
        a.normalize()
        p = M.translation.copy()
        rot = lambda deg: Matrix.Translation(p) @ Quaternion(a, radians(deg)).to_matrix().to_4x4() @ Matrix.Translation(-p)
        set_wmat(root, rot(3) @ M)
        z1 = low()
        set_wmat(root, M)
        if abs(z1 - z0) < 1e-4:
            return
        deg = max(-25.0, min(25.0, 3 * (0.0 - z0) / (z1 - z0)))
        set_wmat(root, rot(deg) @ M)


def place(kind, pel=None, rest=()):
    """Moves the torso so that the pose sits on its anchor (see the docstring): the trunk lies on the floor unless
    a limb would go deeper than SINK into it. pel: where the pelvis goes, (x, y, z), None for 'as the anchor says'.
    rest: limbs that lie on the floor ('arm.L', 'leg.R', ...): they are settled onto it, then the trunk again."""
    for it in range(8):
        upd()
        co = body_points()
        p = wmat('hips').translation
        dz = -np.percentile(co[CORE, 2], 0.5)
        lim = co[~CORE, 2].min()
        if lim + dz < -SINK:
            dz = -SINK - lim
        d = Vector((-p.x, -p.y, dz))
        if kind == 'wall':
            d.y = -np.percentile(co[:, 1], 99.7)
        if pel:
            for i, v in enumerate(pel):
                if v is not None:
                    d[i] = v - p[i]
        set_wmat('torso', Matrix.Translation(d) @ wmat('torso'))
        if it < 7:
            for limb in rest:
                settle(limb)


TABLE = (0.78, 0.80)      # top and depth, m: tables in build_rooms.py (top 0.75 + 0.03, 0.8 deep)
CONSOLE = (1.00, 0.60)    # consoles there: tops 0.95-1.01, 0.6 deep
ARMS = LIMB_BONES['arm.L'] | LIMB_BONES['arm.R']
TRUNK = CORE & ~np.isin(_dom, ['DEF-thigh.L', 'DEF-thigh.R'])     # what lines up with the edge, not a leg thrown out


def place_top(top, edge=None, hips=None, legs=()):
    """Lays the body (already on its back) on a top: the trunk over the top lies on it, the front edge is y = 0.
    edge: where the trunk's nearest point to the edge goes (min y; < 0 hangs over the edge);
    hips: or where the hip joints go (y). legs: the ones that lie on the top, settled onto it. The arms are left
    to drop_arms."""
    H, D = top
    for it in range(8):
        upd()
        co = body_points()
        p = wmat('hips').translation
        d = Vector((-p.x, 0, 0))
        if hips is not None:
            d.y = hips - (wmat('thigh_fk.L').translation.y + wmat('thigh_fk.R').translation.y) / 2
        else:
            d.y = edge - co[TRUNK, 1].min()
        y = co[:, 1] + d.y
        on = (y > 0.02) & (y < D)
        d.z = H - np.percentile(co[CORE & on, 2], 0.5)
        lie = on & ~CORE & ~ARMS & (co[:, 2] + d.z > H - 0.25)     # legs lying on the top, not hanging under it
        if lie.any() and co[lie, 2].min() + d.z < H - SINK:
            d.z = H - SINK - co[lie, 2].min()
        set_wmat('torso', Matrix.Translation(d) @ wmat('torso'))
        if it < 7:
            for limb in legs:
                settle(limb, H)


# ---------------- gravity on the arms ----------------
# A dead arm does not stay up: after the pose is placed, each arm falls joint by joint (the shoulder, the elbow,
# the wrist) towards where gravity would take it, until it meets the floor, the body or the wall behind.
# The elbow keeps to its natural range; an elbow a pose has bent the wrong way is left so.

FLOOR_TOL = 0.015          # m an arm may go into the floor (or the wall) as it falls
BODY_TOL = 0.012           # m into the body before it counts as a hit
STEP = radians(3)
ELBOW = (radians(0), radians(150))
WRIST = radians(70)        # the hand may fall this far either way from the pose
ARM_CHAIN = (              # control, bones that move with it, bones that may hit, skip points this near the joint
    ('upper_arm_fk', ('upper_arm', 'forearm', 'hand'), ('upper_arm', 'forearm'), 0.10),
    ('forearm_fk', ('forearm', 'hand'), ('forearm',), 0.05),
    ('hand_fk', ('hand',), ('hand',), 0.03),
)

_lv = np.empty(len(ob.data.loops), int)
ob.data.loops.foreach_get('vertex_index', _lv)
_ls = np.empty(len(ob.data.polygons), int)
ob.data.polygons.foreach_get('loop_start', _ls)
_polys = [tuple(p.vertices) for p in ob.data.polygons]


def _arm_mask(s, bones):
    return np.isin(_dom, [f'DEF-{b}.{s}{x}' for b in bones for x in ('', '.001')])


def _collider(co, skip):
    """The body without the falling arm, as a BVH tree."""
    bad = np.maximum.reduceat(skip[_lv].astype(np.int8), _ls) > 0
    return BVHTree.FromPolygons(co.tolist(), [_polys[i] for i in np.nonzero(~bad)[0]])


_SUP = {'wall': False, 'top': None}       # what the arms fall onto besides the floor and the body (drop_arms)


def _hits(P, bvh, stop=None):
    n = int((P[:, 2] < -FLOOR_TOL).sum())
    if _SUP['wall']:
        n += int((P[:, 1] > FLOOR_TOL).sum())
    if _SUP['top']:
        H, D = _SUP['top']
        n += int(((P[:, 1] > FLOOR_TOL) & (P[:, 1] < D) & (P[:, 2] < H - FLOOR_TOL)).sum())
    for p in P:
        if stop is not None and n > stop:
            break
        v = Vector(p)
        loc, nor, _, dist = bvh.find_nearest(v, 0.06)
        if loc is not None and dist > BODY_TOL and (v - loc).dot(nor) < 0:
            n += 1
    return n


def _fall(s, ctrl, bones, hit_bones, near, lim):
    """Turns one joint of the arm towards gravity until it meets something. lim: allowed turn (lo, hi), rad."""
    name = f'{ctrl}.{s}'
    upd()
    co = body_points()
    bvh = _collider(co, LIMB_BONES['arm.' + s])
    M = wmat(name)
    p = np.array(M.translation)
    mass = co[_arm_mask(s, bones)]
    P = co[_arm_mask(s, hit_bones)]
    P = P[np.linalg.norm(P - p, axis=1) > near][::3]
    if len(P) < 10:
        return 0.0
    r = Vector(mass.mean(0) - p)
    g = Vector((0, 0, -1))
    if ctrl == 'upper_arm_fk':                                  # a ball joint: straight towards down
        a = r.cross(g)
        if a.length < 1e-4:
            return 0.0
        a.normalize()
        th = r.angle(g)
    else:                                                       # a hinge about the bone's X
        a = M.to_3x3().col[0].normalized()
        rp, gp = r - a * r.dot(a), g - a * g.dot(a)
        if gp.length < 0.2 or rp.length < 1e-4:
            return 0.0
        th = atan2(a.dot(rp.cross(gp)), rp.dot(gp))
    lo, hi = lim if lim else (-th if th < 0 else 0.0, th if th > 0 else 0.0)

    def turned(t):
        R = np.array(Quaternion(a, t).to_matrix())
        return (P - p) @ R.T + p

    start = 0.0
    base = _hits(P, bvh)
    if ctrl == 'hand_fk' and base > max(3, len(P) // 50):       # the hand is pushed into something: lift it out
        best = (base, 0.0)
        t = lo
        while t <= hi + 1e-6:
            h = _hits(turned(t), bvh, stop=best[0])
            if h < best[0] or (h == best[0] and abs(t) < abs(best[1])):
                best = (h, t)
            t += STEP
        start, base = best[1], best[0]
    tol = base + max(3, len(P) // 50)
    end = max(lo, min(hi, th))
    sign = 1.0 if end > start else -1.0
    t = start
    while abs(end - t) > 1e-6:
        nt = t + sign * min(STEP, abs(end - t))
        if _hits(turned(nt), bvh, stop=tol) > tol:
            break
        t = nt
    if abs(t) > 1e-6:
        pv = Vector(p)
        set_wmat(name, Matrix.Translation(pv) @ Quaternion(a, t).to_matrix().to_4x4() @ Matrix.Translation(-pv) @ M)
    return t


def drop_arms(wall=False, top=None):
    _SUP['wall'], _SUP['top'] = wall, top
    for s in ('L', 'R'):
        wrist = 0.0
        for _ in range(3):
            moved = False
            for ctrl, bones, hit_bones, near in ARM_CHAIN:
                lim = None
                if ctrl == 'forearm_fk':
                    q = pb[f'forearm_fk.{s}'].matrix_basis.to_quaternion()
                    e = 2 * atan2(q.x, q.w)
                    if not ELBOW[0] - 1e-3 <= e <= ELBOW[1] + 1e-3:
                        continue
                    lim = (ELBOW[0] - e, ELBOW[1] - e)
                elif ctrl == 'hand_fk':
                    lim = (-WRIST - wrist, WRIST - wrist)
                t = _fall(s, ctrl, bones, hit_bones, near, lim)
                if ctrl == 'hand_fk':
                    wrist += t
                moved |= abs(t) > radians(0.5)
            if not moved:
                break


def key(name):
    act = bpy.data.actions.get(name)
    if act:
        bpy.data.actions.remove(act)
    act = bpy.data.actions.new(name)
    act.use_fake_user = True
    rig.animation_data_create()
    rig.animation_data.action = act
    for n in CONTROLS:
        b = pb[n]
        b.keyframe_insert('location', frame=0, group=n)
        b.keyframe_insert('rotation_quaternion' if b.rotation_mode == 'QUATERNION' else 'rotation_euler', frame=0, group=n)
        b.keyframe_insert('scale', frame=0, group=n)
    for n in LIMBS:
        pb[n].keyframe_insert('["IK_FK"]', frame=0, group=n)
    pb['torso'].keyframe_insert('["head_follow"]', frame=0, group='torso')
    pb['torso'].keyframe_insert('["neck_follow"]', frame=0, group='torso')
    act.use_frame_range = True
    act.frame_start, act.frame_end = 0, 1
    try:
        act.asset_mark()
        act.asset_generate_preview()
    except Exception:
        pass
    return act


def lay(face):
    """Turns the whole body from standing: 'back', 'front' (face down), 'left' (on its left side), 'right'."""
    a = {'back': ((1, 0, 0), -90), 'front': ((1, 0, 0), 90), 'left': ((0, 1, 0), 90), 'right': ((0, 1, 0), -90)}[face]
    turn('torso', a[0], a[1], 'root')


# ---------------- the poses ----------------
# body axes: X its left, -Y its front, +Y its back, Z towards its head. Lying on the back the floor is +Y,
# face down it is -Y, on the left side it is +X.

def floor1():          # on the back, sprawled, the head fallen to the side
    lay('back')
    turn('head', (0, 0, 1), 45)
    turn('chest', (0, 0, 1), 10)
    arm('L', (1, 0.2, 0.35), (0, 0, -1), elbow=40, wrist=15)
    arm('R', (-1, 0.2, -0.4), (0, 0, 1), elbow=20)
    leg('L', (0.3, -0.1, -1), (0, 1, 0), knee=25, ankle=35)
    leg('R', (-0.08, 0.05, -1), (0, 1, 0), knee=5, ankle=40)
    place('floor', rest=('arm.L', 'arm.R', 'leg.L', 'leg.R'))


def floor2():          # face down, the cheek on the floor, one arm up by the head, one leg drawn up to the side
    lay('front')
    turn('head', (0, 0, 1), -75)
    arm('L', (0.65, -0.15, 0.75), (-0.75, 0, 0.65), elbow=80, wrist=20)
    arm('R', (-0.25, -0.1, -1), (0, 1, 0), elbow=5, hand_twist=90)
    leg('L', (0.7, -0.15, -0.7), (-0.7, 0, -0.7), knee=80, ankle=20)
    leg('R', (-0.08, 0, -1), (0, 1, 0), knee=5, ankle=30)
    place('floor', rest=('arm.L', 'arm.R', 'leg.L', 'leg.R'))


def floor3():          # on the left side: the lower arm out along the floor, the upper arm and leg fallen forward
    lay('left')
    turn('head', (0, 1, 0), 20)
    arm('L', (0, -1, 0.35), (0, 0, 1), elbow=20, wrist=10)
    arm('R', (0.4, -0.8, -0.3), (0, 0, 1), elbow=30, wrist=20)
    leg('L', (0.05, -0.05, -1), (0, 1, 0), knee=15, ankle=30)
    leg('R', (0.5, -0.8, -0.4), (0, 1, 0), knee=70, ankle=30)
    place('floor', rest=('arm.L', 'arm.R', 'leg.L', 'leg.R'))


def wall1():           # sitting against the wall, legs out, chin on the chest, arms limp
    turn('torso', (1, 0, 0), -15, 'root')
    turn('chest', (1, 0, 0), 25)
    turn('neck', (1, 0, 0), 30)
    turn('head', (1, 0, 0), 25)
    turn('head', (0, 0, 1), 10)
    leg('L', (0.15, -1, -0.12), (0, 0, -1), knee=8, ankle=25)
    leg('R', (-0.2, -1, -0.15), (0, 0, -1), knee=12, ankle=30)
    arm('L', (0.35, 0.1, -1), (0, -1, 0), elbow=15, wrist=20)
    arm('R', (-0.3, -0.1, -1), (0, -1, 0), elbow=30, wrist=10)
    place('wall', rest=('leg.L', 'leg.R'))


def wall2():           # sitting, one knee up with the arm over it, the head on the shoulder
    turn('torso', (1, 0, 0), -10, 'root')
    turn('chest', (1, 0, 0), 15)
    turn('neck', (0, 1, 0), 20)
    turn('head', (0, 1, 0), 30)
    turn('head', (1, 0, 0), 25)
    turn('head', (0, 0, 1), 15)
    leg('L', (0.15, -0.6, 0.6), (0, 0.6, -1), knee=125, ankle=-5)
    leg('R', (-0.2, -1, -0.15), (0, 0, -1), knee=10, ankle=30)
    arm('L', (0.25, -0.3, -1), (0, -1, 0), elbow=80, wrist=40)
    arm('R', (-0.3, 0, -1), (0, -1, 0), elbow=20, wrist=10)
    place('wall', rest=('leg.L', 'leg.R'))


def wall3():           # slid down sideways along the wall
    turn('torso', (0, 1, 0), -35, 'root')
    turn('torso', (1, 0, 0), -10, 'root')
    turn('chest', (0, 1, 0), -15)
    turn('neck', (0, 1, 0), -20)
    turn('head', (0, 1, 0), -15)
    turn('head', (1, 0, 0), 20)
    leg('L', (0.45, -0.9, 0.05), (0, 0, -1), knee=60, ankle=20)
    leg('R', (0.15, -0.95, 0.0), (0, 0, -1), knee=70, ankle=20)
    arm('R', (-0.4, 0, -1), (0, -1, 0), elbow=30, wrist=10)
    arm('L', (0.1, -0.4, -1), (-1, -0.5, 0), elbow=70, wrist=10)
    place('wall', rest=('leg.L', 'leg.R'))


def curl1():           # on the left side, knees to the chest, arms round the knees
    lay('left')
    turn('chest', (1, 0, 0), 30)
    turn('hips', (1, 0, 0), 10)
    turn('neck', (1, 0, 0), 30)
    turn('head', (1, 0, 0), 20)
    leg('L', (0.12, -1, 0.35), (0, -0.33, -1), knee=120, ankle=20)
    leg('R', (-0.05, -1, 0.45), (0, -0.4, -1), knee=125, ankle=25)
    arm('L', (-0.05, -0.8, -0.6), (-1, 0, 0.2), elbow=100, wrist=10)
    arm('R', (-0.3, -0.7, -0.5), (1, 0, 0.3), elbow=105, wrist=10)
    place('floor')


def curl2():           # on the right side, the hands at the face, knees half up
    lay('right')
    turn('chest', (1, 0, 0), 20)
    turn('neck', (1, 0, 0), 25)
    turn('head', (1, 0, 0), 15)
    leg('L', (0.05, -0.9, 0.0), (0, -0.2, -1), knee=90, ankle=15)
    leg('R', (0, -0.7, -0.5), (0, -0.6, -1), knee=80, ankle=10)
    arm('L', (0.15, -0.9, -0.3), (0, 0, 1), elbow=140, wrist=20)
    arm('R', (0.05, -0.9, -0.4), (0, 0, 1), elbow=135, wrist=20)
    place('floor')


def curl3():           # collapsed kneeling, folded forward, the face on the floor, arms back along the legs
    turn('torso', (1, 0, 0), 100, 'root')
    turn('chest', (1, 0, 0), 35)
    turn('neck', (1, 0, 0), -15)
    turn('head', (0, 0, 1), 60)
    leg('L', (0.12, 0.1, -1), (0, 1, 0), knee=100, ankle=40, frame='root')
    leg('R', (-0.12, 0.1, -1), (0, 1, 0), knee=100, ankle=40, frame='root')
    arm('L', (0.25, 0.7, -0.6), (0, 0, 1), elbow=10, hand_twist=90, frame='root')
    arm('R', (-0.25, 0.7, -0.6), (0, 0, 1), elbow=10, hand_twist=-90, frame='root')
    place('floor')


def embed1():          # out of the wall from the waist, hanging down limp, about 1 m up
    turn('torso', (1, 0, 0), 90, 'root')          # face down, the head out of the wall (-Y)
    turn('chest', (1, 0, 0), 45)
    turn('neck', (1, 0, 0), 30)
    turn('head', (1, 0, 0), 20)
    arm('L', (0.2, 0, -1), (0, -1, 0), elbow=15, wrist=10, frame='root')
    arm('R', (-0.15, -0.1, -1), (0, -1, 0), elbow=25, wrist=15, frame='root')
    leg('L', (0.05, 0, -1), knee=5)
    leg('R', (-0.05, 0, -1), knee=5)
    place('embed', pel=(0, 0.12, 1.0))


def embed2():          # only the legs out of the wall, on the floor; the body is in the wall
    turn('torso', (1, 0, 0), -90, 'root')         # on the back, the head into the wall (+Y)
    leg('L', (0.25, -0.1, -1), (0, 1, 0), knee=25, ankle=35)
    leg('R', (-0.15, 0.05, -1), (0, 1, 0), knee=8, ankle=40)
    arm('L', (0.9, 0.1, 0.3), (0, 0, 1), elbow=10)    # arms in the wall too
    arm('R', (-0.9, 0.1, 0.3), (0, 0, 1), elbow=10)
    place('embed', pel=(0, 0.06, None), rest=('leg.L', 'leg.R'))


def embed3():          # standing in the wall, only the face and one reaching hand come out of it
    turn('chest', (1, 0, 0), 28)
    turn('neck', (1, 0, 0), 15)
    turn('head', (1, 0, 0), 20)
    turn('head', (0, 0, 1), -15)
    arm('R', (-0.15, -1, -0.15), (0, 0, 1), elbow=15, wrist=-30)
    arm('L', (0.3, 0, -1), (0, -1, 0), elbow=10)
    leg('L', (0.05, -0.05, -1), knee=5)
    leg('R', (-0.05, 0, -1), knee=8)
    place('embed', pel=(0, 0.19, None))


def table1():          # on the back across a table, pushed back from sitting on its edge: the legs hang down over it
    lay('back')                                   # the head into the table (+Y), the feet out over the edge
    turn('head', (0, 0, 1), 25)
    turn('chest', (0, 0, 1), -8)
    arm('L', (1, -0.15, 0.25), (0, 0, 1), elbow=35, wrist=10)
    arm('R', (-1, -0.15, 0.55), (0, 0, 1), elbow=60, wrist=20)
    leg('L', (0.12, -0.45, -1), (0, 1, 0), knee=12, ankle=25, frame='root')
    leg('R', (-0.2, -0.6, -1), (0, 1, 0), knee=22, ankle=30, frame='root')
    place_top(TABLE, hips=-0.02)
    return dict(top=TABLE)


def table2():          # on the back along a table, the near arm and leg hanging over its front edge
    lay('back')
    turn('torso', (0, 0, 1), 90, 'root')          # the head to -X, the body's right side to the edge (-Y)
    turn('head', (0, 0, 1), -35)
    arm('R', (-1, -0.2, -0.15), (0, 1, 0), elbow=20, wrist=10)
    arm('L', (0.35, -0.5, -1), (0, 0, 1), elbow=70, wrist=15)
    leg('R', (-0.7, -0.1, -0.7), (0, 1, 0), knee=85, ankle=30)
    leg('L', (0.08, -0.05, -1), (0, 1, 0), knee=10, ankle=35)
    place_top(TABLE, edge=-0.03, legs=('leg.L',))
    return dict(top=TABLE)


def console1():        # on the back along a console, the head turned to the room, an arm hanging down its front
    lay('back')
    turn('torso', (0, 0, 1), -90, 'root')         # the head to +X, the body's left side to the edge (-Y)
    turn('head', (0, 0, 1), 40)
    arm('L', (1, -0.2, -0.15), (0, 1, 0), elbow=15, wrist=10)
    arm('R', (0.3, -0.6, -1), (0, 0, 1), elbow=95, wrist=10)
    leg('L', (0.1, -0.15, -1), (0, 1, 0), knee=25, ankle=35)
    leg('R', (-0.06, -0.05, -1), (0, 1, 0), knee=5, ankle=40)
    place_top(CONSOLE, edge=-0.03, legs=('leg.L', 'leg.R'))
    return dict(top=CONSOLE)


POSES = [('Floor1', floor1), ('Floor2', floor2), ('Floor3', floor3),
         ('Wall1', wall1), ('Wall2', wall2), ('Wall3', wall3),
         ('Curl1', curl1), ('Curl2', curl2), ('Curl3', curl3),
         ('Embed1', embed1), ('Embed2', embed2), ('Embed3', embed3),
         ('Table1', table1), ('Table2', table2), ('Console1', console1)]


def build(only=None):
    out = []
    for name, fn in POSES:
        if only and name not in only:
            continue
        reset()
        support = fn() or {}
        if not name.startswith('Embed'):         # in the wall the body is held by it; elsewhere the arms fall
            drop_arms(wall=name.startswith('Wall'), **support)
        out.append(key('P_DeadMan_' + name))
    return out


if __name__ == '__main__':
    build()
    reset()
    rig.animation_data.action = None
