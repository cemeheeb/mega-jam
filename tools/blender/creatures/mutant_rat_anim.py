"""Mutant rat animations (run after mutant_rat_rig.py, in the live Blender): seven actions on the armature `root`.

30 fps, in place (the body never leaves the origin for good: the game moves the actor). Every frame is keyed on every
bone, so switching actions resets everything. The paws are driven by the IK control bones; the FBX export bakes
the result onto the deform bones.

- A_MutantRat_Walk (loop, 18 frames = 0.6 s): diagonal trot, stride 0.36 m, stance 60 %: 1.0 m/s on the spot.
  In the game: play rate = speed / 1.0 m/s.
- A_MutantRat_Aggro (loop, 48 frames = 1.6 s): crouched threat, hunched back, nose up, two snaps of the head,
  weight shifting, the tail lashing.
- A_MutantRat_Attack (24 frames = 0.8 s): pulls back, lunges 0.22 m forward with the front paws off the ground and
  bites at frame 12 (the moment of the hit), steps back.
- A_MutantRat_Hit (18 frames = 0.6 s): thrown back and to its left, head up, tail whips, settles.
- A_MutantRat_Idle (loop, 90 frames = 3 s): breathing (1 s), looking about, a short sniff, slow tail sway.
- A_MutantRat_Leap (42 frames = 1.4 s): ranged attack, a jump at the player's belly. Crouch (0-9), push-off (12),
  airborne 12-30 with the arc in the animation (pelvis up to +0.25 m, nose up, head at about 1.05 m), bite at frame 20
  (the moment of the hit), landing 30, settles by 42. Along the floor it stays in place: the game carries the actor
  forward over frames 12-30 (0.4-1.0 s).
- A_MutantRat_Death (60 frames = 2.0 s, not looped, hold the last frame): hit, the legs give way, rolls onto its left
  side (lands at frame 24), the hind legs stretched out, a spasm of the upper hind leg (35-50) with a slower shiver
  along the spine (34-58), a twitch of the front paw (54), still from 58. The body ends 0.2 m to its left of the origin.

Pose parameters are rotations about the axes of the world in degrees and offsets in metres (the rat faces -Y, its
left is +X). Pitch about +X: positive lowers the nose for the spine, neck and head, raises the tail, bends the paw
toes down. Yaw about +Z: positive turns the head to the rat's left and the tail to its right.
"""
import bpy
from math import sin, cos, pi, radians, exp, asin
from mathutils import Vector, Quaternion

FPS = 30
rig = bpy.data.objects['root']
pb = rig.pose.bones
REST = {b.name: b.bone.matrix_local.to_3x3() for b in pb}
PEL_REST = pb['pelvis'].bone.matrix_local.copy()
PAW_FLOOR = 0.05      # m, lowest height of a paw control (wrist, hock) when the paw is carried by the body
PAWS = ['hand_l', 'hand_r', 'foot_l', 'foot_r']
TAILS = [f'tail_{i + 1:02d}' for i in range(8)]
TIP = {'hand': 'ik_hand_tip', 'foot': 'ik_foot_ball'}                  # the IK control of the toes, child of the paw's
# limp paws: out from the shoulder / hip by 0.55 of the leg's reach, so the elbow and the knee stay bent
LIMB = {'hand': ('upperarm', 0.55 * (pb['upperarm_l'].bone.length + pb['lowerarm_l'].bone.length)),
        'foot': ('thigh', 0.55 * (pb['thigh_l'].bone.length + pb['calf_l'].bone.length))}
TAIL_FLOOR = [0.03, 0.028, 0.025, 0.022, 0.018, 0.015, 0.012, 0.01]    # m, the tail's half-thickness along it
HEAD_FLOOR = [0.085, 0.045]                                             # m, neck end (skull), snout tip, lying
DRAPE_MAX = radians(40)                                                 # per bone
TAIL_S = [sum(pb[n].bone.length for n in TAILS[:i + 1]) for i in range(8)]   # m, base -> the end of each tail bone
TAIL_BEND = 0.65      # m along the tail over which it comes down to the floor: an elastic arc, not a hinge


def tail_arc(z0):
    """Heights for the ends of the tail bones, draped: down from the base (z0) in a smooth arc that meets the floor
    tangentially TAIL_BEND along the tail (author, 15.11: the tail hung like a thread with a sharp angle)."""
    lift = max(0.0, z0 - TAIL_FLOOR[0])
    return [fl + lift * max(0.0, 1 - s / TAIL_BEND) ** 2 for fl, s in zip(TAIL_FLOOR, TAIL_S)]


def wrot(name, axis, deg):
    if abs(deg) < 1e-6:
        return
    b = pb[name]
    ax = (REST[name].inverted() @ Vector(axis)).normalized()
    b.rotation_quaternion = Quaternion(ax, radians(deg)) @ b.rotation_quaternion


def wloc(name, d):
    pb[name].location = REST[name].inverted() @ Vector(d)


def apply(P):
    g = lambda k: P.get(k, 0.0)
    for b in pb:
        b.rotation_quaternion = (1, 0, 0, 0)
        b.location = (0, 0, 0)
    wloc('pelvis', (g('pel_x'), g('pel_y'), g('pel_z')))
    wrot('pelvis', (1, 0, 0), g('pel_pitch'))
    wrot('pelvis', (0, 1, 0), g('pel_roll'))
    wrot('pelvis', (0, 0, 1), g('pel_yaw'))
    for n in ('spine_01', 'spine_02', 'spine_03', 'neck', 'head'):
        wrot(n, (1, 0, 0), g(n + '_pitch'))
        wrot(n, (0, 0, 1), g(n + '_yaw'))
    wrot('head', (0, 1, 0), g('head_roll'))
    tp, ty = P.get('tail_pitch', [0] * 8), P.get('tail_yaw', [0] * 8)
    for i, n in enumerate(TAILS):
        wrot(n, (1, 0, 0), tp[i])
        wrot(n, (0, 0, 1), ty[i])
    for s in ('l', 'r'):
        wrot(f'scapula_{s}', (1, 0, 0), g(f'scapula_{s}_pitch'))
    # <paw>_follow (0..1): the paw target is carried by the pelvis (in the air) instead of staying on the floor
    body = PEL_REST @ pb['pelvis'].matrix_basis @ PEL_REST.inverted()
    body_q = body.to_quaternion()
    belly = body_q @ Vector((0, 0, -1))
    for p in PAWS:
        kind, s = p.split('_')
        ctl = f'ik_{kind}_{s}'
        k = g(p + '_follow')
        h = pb[ctl].bone.head_local
        off = Vector((g(p + '_dx'), g(p + '_dy'), g(p + '_dz')))
        d = k * (body @ h - h) + off
        lk = g(p + '_limp')
        joint, reach = LIMB[kind]
        st = g(p + '_stretch') * lk              # 0..1: the limp leg goes out straight and back along the body
        if lk:                                   # a limp paw lies on the floor out from the belly (dz: on top of others)
            out = (belly + body_q @ Vector((0, 1.6 * st, 0))).normalized()
            T = body @ pb[f'{joint}_{s}'].bone.head_local + out * reach * (1 + 0.6 * st) + off
            T.z = PAW_FLOOR + off.z
            d = d * (1 - lk) + (T - h) * lk
        d.z = max(d.z, min(0.0, PAW_FLOOR - h.z))         # a carried paw never goes under the floor
        wloc(ctl, d)
        wrot(ctl, (1, 0, 0), g(p + '_pitch'))
        if k:                                    # the paw turns with the body too (pitch, roll and yaw)
            R = REST[ctl].to_quaternion()
            pb[ctl].rotation_quaternion = (R.inverted() @ Quaternion().slerp(body_q, k) @ R) @ pb[ctl].rotation_quaternion
        if st:                                   # stretched, the ankle opens: the foot goes on along the leg, toes back
            R = REST[ctl].to_quaternion()
            Qw = R @ pb[ctl].rotation_quaternion @ R.inverted()
            v = Qw @ (pb[f'{TIP[kind]}_{s}'].bone.head_local - h)            # hock -> toes, as the paw is turned now
            leg = h + d - body @ pb[f'{joint}_{s}'].bone.head_local          # hip -> hock
            a = body_q @ Vector((1, 0, 0))                                    # the ankle's hinge, lying
            pv, pl = v - a * v.dot(a), leg - a * leg.dot(a)
            th = pv.angle(pl) * (1 if pv.cross(pl).dot(a) > 0 else -1)
            pb[ctl].rotation_quaternion = R.inverted() @ Quaternion(a, th * st) @ Qw @ R
    # tail_drape, head_drape (0..1): the tail, the neck and the head sink onto the floor, bone by bone
    if g('tail_drape'):
        base = body @ pb[TAILS[0]].bone.head_local
        chain(TAILS, body_q, base, tail_arc(base.z), g('tail_drape'), radians(60))
    if g('head_drape'):
        D, head = chain(['spine_01', 'spine_02', 'spine_03'], body_q, body @ pb['spine_01'].bone.head_local)
        chain(['neck', 'head'], D, head, HEAD_FLOOR, g('head_drape'))


def chain(names, D, head, floor=None, k=0.0, cap=DRAPE_MAX):
    """Walks a chain of bones in the pose (D: the world turn of its parent, head: where it starts). With floor, turns
    each bone, by up to cap x k, so that its end comes down to floor[i] above the floor."""
    down = Vector((0, 0, -1))
    for i, n in enumerate(names):
        b = pb[n]
        R = REST[n].to_quaternion()
        Qe = R @ b.rotation_quaternion @ R.inverted()          # the bone's own turn, in the axes of the armature
        v0 = b.bone.tail_local - b.bone.head_local
        if floor is not None:
            v = (D @ Qe) @ v0
            L = v.length
            el = asin(max(-1.0, min(1.0, v.z / L)))
            el_t = asin(max(-1.0, min(1.0, (floor[i] - head.z) / L)))
            th = min(cap, el - el_t)                               # positive turns the bone down
            th = th * k if th > 0 else th                          # under the floor it always comes up, fully
            a = v.cross(down)
            if a.length > 1e-6 and abs(th) > 1e-6:
                Qe = (D.inverted() @ Quaternion(a.normalized(), th) @ D) @ Qe
                b.rotation_quaternion = R.inverted() @ Qe @ R
        D = D @ Qe
        head = head + D @ v0
    return D, head


def smooth(u):
    u = max(0.0, min(1.0, u))
    return u * u * (3 - 2 * u)


def keyed(keys, f):
    """Pose-to-pose: keys = [(frame, {param: value})]; missing params are 0; smoothstep between neighbours."""
    for (f0, a), (f1, c) in zip(keys, keys[1:]):
        if f0 <= f <= f1:
            u = smooth((f - f0) / (f1 - f0))
            out = {}
            for k in set(a) | set(c):
                x, y = a.get(k, 0.0), c.get(k, 0.0)
                if isinstance(x, list) or isinstance(y, list):
                    x = x if isinstance(x, list) else [x] * 8
                    y = y if isinstance(y, list) else [y] * 8
                    out[k] = [p + (q - p) * u for p, q in zip(x, y)]
                else:
                    out[k] = x + (y - x) * u
            return out
    return dict(keys[-1][1])


# ---------------- walk ----------------
W_N, STRIDE, STANCE = 18, 0.36, 0.6
PHASE = {'hand_l': 0.0, 'foot_r': 0.05, 'hand_r': 0.5, 'foot_l': 0.55}     # diagonal pairs, front a little ahead
LIFT = {'hand': 0.09, 'foot': 0.07}
SHIFT = {'hand': 0.0, 'foot': -0.03}                                       # hind stride centred a bit forward


def walk(f):
    t = f / W_N
    P = {}
    for p, ph in PHASE.items():
        kind = p.split('_')[0]
        u = (t + ph) % 1.0
        if u < STANCE:
            v = u / STANCE
            y, z, pitch = -STRIDE / 2 + STRIDE * v, 0.0, 0.0
        else:
            v = (u - STANCE) / (1 - STANCE)
            y = STRIDE / 2 - STRIDE * smooth(v)
            z = LIFT[kind] * sin(pi * v)
            pitch = (45 if kind == 'hand' else 30) * sin(pi * v)
        P[p + '_dy'], P[p + '_dz'], P[p + '_pitch'] = y + SHIFT[kind], z, pitch
        if kind == 'hand':
            P[f'scapula_{p[-1]}_pitch'] = 10 * (y / (STRIDE / 2))           # shoulder follows the paw
    w = 2 * pi * t
    P.update(pel_z=-0.015 - 0.012 * cos(2 * w), pel_y=0.008 * sin(2 * w), pel_roll=3 * sin(w), pel_yaw=2 * sin(w),
             spine_02_yaw=-2 * sin(w), spine_03_yaw=-2 * sin(w), neck_pitch=2 * cos(2 * w), head_pitch=-3 + 2 * cos(2 * w),
             head_yaw=2 * sin(w))
    P['tail_pitch'] = [4, 1, 0, 0, 0, 0, 0, 0]
    P['tail_yaw'] = [(4 + 1.5 * i) * sin(w - 0.6 * i) for i in range(8)]
    return P


# ---------------- aggro ----------------
A_N = 48
CROUCH = dict(pel_z=-0.07, pel_y=0.04, pel_pitch=-6, spine_02_pitch=4, spine_03_pitch=7, neck_pitch=2, head_pitch=-16,
              scapula_l_pitch=4, scapula_r_pitch=4)


def aggro(f):
    t = f / A_N
    w = 2 * pi * t
    snap = exp(-((t - 0.25) / 0.045) ** 2) + exp(-((t - 0.72) / 0.045) ** 2)
    P = dict(CROUCH)
    P['pel_z'] += 0.012 * sin(2 * w)
    P['pel_x'] = 0.02 * sin(w)
    P['pel_roll'] = 2.5 * sin(w)
    P['pel_y'] += -0.03 * snap
    P['neck_pitch'] += 6 * snap
    P['head_pitch'] += 12 * snap - 3 * sin(2 * w)
    P['head_yaw'] = 7 * sin(w + 0.8)
    P['neck_yaw'] = 4 * sin(w + 0.4)
    P['head_roll'] = 4 * sin(w)
    P['tail_pitch'] = [12, -2, -3, -2, -1, 0, 0, 0]
    P['tail_yaw'] = [(2.5 + 1.2 * i) * sin(2 * w - 0.55 * i) for i in range(8)]     # lashing, the tip within ~50°
    P['hand_r_dz'] = 0.03 * exp(-((t - 0.5) / 0.06) ** 2)                   # a nervous shuffle of one paw
    P['hand_r_pitch'] = 25 * exp(-((t - 0.5) / 0.06) ** 2)
    return P


# ---------------- attack ----------------
ATTACK = [
    (0, {}),
    (7, dict(pel_y=0.08, pel_z=-0.08, pel_pitch=-4, spine_03_pitch=5, neck_pitch=-10, head_pitch=-14,
             tail_pitch=[15, 0, 0, 0, 0, 0, 0, 0], scapula_l_pitch=6, scapula_r_pitch=6)),
    (10, dict(pel_y=-0.12, pel_z=0.0, spine_01_pitch=-3, spine_02_pitch=-3, spine_03_pitch=-2, neck_pitch=4,
              head_pitch=-4, hand_l_dy=-0.18, hand_l_dz=0.12, hand_l_pitch=30, hand_r_dy=-0.16, hand_r_dz=0.11,
              hand_r_pitch=30, scapula_l_pitch=-12, scapula_r_pitch=-12, tail_pitch=[6, 3, 0, 0, 0, 0, 0, 0],
              foot_l_dy=-0.04, foot_l_dz=0.036, foot_l_pitch=20, foot_r_dy=-0.04, foot_r_dz=0.036, foot_r_pitch=20)),
    # hind paws push off: the heels rise (the hock up, the toes turned down onto the floor) and slide 8 cm forward
    (12, dict(pel_y=-0.22, pel_z=0.01, spine_01_pitch=-2, spine_02_pitch=-1, spine_03_pitch=2, neck_pitch=12,
              head_pitch=20, hand_l_dy=-0.28, hand_l_dz=0.02, hand_r_dy=-0.26, hand_r_dz=0.02,
              scapula_l_pitch=-14, scapula_r_pitch=-14, tail_pitch=[-4, -3, 0, 0, 0, 0, 0, 0],
              foot_l_dy=-0.08, foot_l_dz=0.036, foot_l_pitch=20, foot_r_dy=-0.08, foot_r_dz=0.036, foot_r_pitch=20)),
    (14, dict(pel_y=-0.22, pel_z=-0.01, spine_03_pitch=3, neck_pitch=10, head_pitch=14, head_roll=8,
              hand_l_dy=-0.28, hand_r_dy=-0.26, scapula_l_pitch=-14, scapula_r_pitch=-14,
              foot_l_dy=-0.08, foot_r_dy=-0.08)),
    (18, dict(pel_y=-0.12, pel_z=-0.02, neck_pitch=2, head_pitch=-4, hand_l_dy=-0.14, hand_l_dz=0.06,
              hand_l_pitch=25, hand_r_dy=-0.26, scapula_l_pitch=-7, scapula_r_pitch=-12,
              foot_l_dy=-0.08, foot_r_dy=-0.03, foot_r_dz=0.05, foot_r_pitch=15)),
    (21, dict(pel_y=-0.04, hand_l_dy=0.0, hand_r_dy=-0.12, hand_r_dz=0.06, hand_r_pitch=25, scapula_r_pitch=-6,
              foot_l_dy=-0.03, foot_l_dz=0.05, foot_l_pitch=15)),
    (24, {}),
]

# ---------------- hit ----------------
HIT = [
    (0, {}),
    (3, dict(pel_y=0.07, pel_z=0.01, pel_roll=7, pel_yaw=-5, spine_02_yaw=6, spine_03_yaw=8, spine_03_pitch=-4,
             neck_pitch=-16, neck_yaw=12, head_pitch=-18, head_yaw=10, head_roll=-10,
             hand_l_dz=0.04, hand_l_pitch=20, tail_pitch=[18, 4, 0, 0, 0, 0, 0, 0],
             tail_yaw=[6, 10, 14, 16, 18, 18, 18, 18])),
    (8, dict(pel_y=0.03, pel_z=-0.02, pel_roll=-3, pel_yaw=2, spine_03_yaw=-3, neck_pitch=4, neck_yaw=-4, head_pitch=6,
             head_yaw=-5, tail_yaw=[-3, -5, -8, -10, -12, -12, -12, -12])),
    (13, dict(pel_y=0.01, pel_roll=1, head_pitch=-2, tail_yaw=[1, 2, 3, 4, 4, 4, 4, 4])),
    (18, {}),
]


# ---------------- idle ----------------
I_N = 90


def idle(f):
    t = f / I_N
    w = 2 * pi * t
    sniff = exp(-((t - 0.45) / 0.07) ** 2)                                  # a short sniff, nose up
    P = dict(pel_z=-0.006 + 0.004 * sin(3 * w), pel_x=0.006 * sin(w), pel_roll=1.2 * sin(w),
             spine_02_pitch=1.2 * sin(3 * w), spine_03_pitch=1.0 * sin(3 * w + 0.4),       # breathing, 1 s
             neck_yaw=5 * sin(w), head_yaw=9 * sin(w + 0.3), neck_pitch=-2 * sin(2 * w),
             head_pitch=-2 + 2 * sin(2 * w + 1) - 6 * sniff + 2.5 * sniff * sin(2 * pi * 14 * t),
             head_roll=2 * sin(w + 0.5))
    P['tail_pitch'] = [3, 1, 0, 0, 0, 0, 0, 0]
    P['tail_yaw'] = [(1.5 + 0.6 * i) * sin(w - 0.5 * i) for i in range(8)]
    return P


# ---------------- leap ----------------
# Ranged attack: a jump at the player's belly. In place along the floor (the game carries the actor forward over the
# airborne frames 12-30), but the arc is in the animation: the pelvis rises 0.25 m and pitches the nose up, so the
# head comes to about 1.05 m, the height of a man's belly. Bite (the moment of the hit) at frame 20.
AIR_FRONT = dict(hand_l_follow=1, hand_r_follow=1)
AIR_HIND = dict(foot_l_follow=1, foot_r_follow=1)


def paws(kind, **kw):
    return {f'{kind}_{s}_{k}': v for s in ('l', 'r') for k, v in kw.items()}


LEAP = [
    (0, {}),
    (9, dict(pel_z=-0.09, pel_y=0.06, pel_pitch=-3, spine_02_pitch=5, spine_03_pitch=6, neck_pitch=-8, head_pitch=-14,
             scapula_l_pitch=8, scapula_r_pitch=8, tail_pitch=[16, 2, 0, 0, 0, 0, 0, 0])),
    (12, dict(pel_z=0.04, pel_y=-0.04, pel_pitch=-14, spine_01_pitch=-3, spine_02_pitch=-3, spine_03_pitch=-3,
              neck_pitch=-6, head_pitch=-10, scapula_l_pitch=-12, scapula_r_pitch=-12,
              **paws('hand', follow=0.6, dy=-0.05, dz=0.12, pitch=35), **paws('foot', dy=-0.04, dz=0.04, pitch=25),
              tail_pitch=[6, 2, 0, 0, 0, 0, 0, 0])),
    (15, dict(pel_z=0.20, pel_y=-0.02, pel_pitch=-18, spine_01_pitch=-3, spine_02_pitch=-3, spine_03_pitch=-3,
              neck_pitch=-6, head_pitch=-8, scapula_l_pitch=-16, scapula_r_pitch=-16,
              **paws('hand', follow=1, dy=-0.10, dz=0.10, pitch=55), **paws('foot', follow=1, dy=0.20, dz=0.08, pitch=80),
              tail_pitch=[12, 5, 2, 0, 0, 0, 0, 0])),
    (20, dict(pel_z=0.25, pel_pitch=-14, neck_pitch=4, head_pitch=8, head_roll=6, scapula_l_pitch=-18,
              scapula_r_pitch=-18, **paws('hand', follow=1, dy=-0.20, dz=0.08, pitch=75),
              **paws('foot', follow=1, dy=0.18, dz=0.06, pitch=70), tail_pitch=[10, 4, 1, 0, 0, 0, 0, 0])),
    (23, dict(pel_z=0.22, pel_pitch=-10, neck_pitch=4, head_pitch=12, head_roll=-6, scapula_l_pitch=-16,
              scapula_r_pitch=-16, **paws('hand', follow=1, dy=-0.20, dz=0.04, pitch=70),
              **paws('foot', follow=1, dy=0.12, dz=0.0, pitch=40), tail_pitch=[7, 3, 0, 0, 0, 0, 0, 0])),
    (27, dict(pel_z=0.08, pel_pitch=-2, scapula_l_pitch=-6, scapula_r_pitch=-6,
              **paws('hand', follow=1, dy=-0.10, dz=-0.04, pitch=20),
              **paws('foot', follow=1, dy=0.04, dz=-0.02, pitch=10), tail_pitch=[4, 0, 0, 0, 0, 0, 0, 0])),
    (30, dict(pel_z=-0.06, pel_pitch=3, spine_03_pitch=4, neck_pitch=4, head_pitch=4, scapula_l_pitch=6,
              scapula_r_pitch=6, tail_pitch=[10, 2, 0, 0, 0, 0, 0, 0])),
    (34, dict(pel_z=-0.08, pel_y=0.02, spine_03_pitch=3, head_pitch=-6, scapula_l_pitch=5, scapula_r_pitch=5,
              tail_pitch=[12, 3, 0, 0, 0, 0, 0, 0])),
    (42, {}),
]


# ---------------- death ----------------
# Hit, the legs give way, it rolls onto its left side (+X down), goes limp: the legs, the tail and the head fall to the
# floor (limp / drape), the hind legs stretched out; a spasm of the upper hind leg with a slower shiver along the
# spine, a twitch of the front paw, still. Not looped: the last frame is the pose to hold. Lying, the body's pitch axis is the floor's normal, so
# tail_pitch curls the tail along the floor.
LIMP = lambda k: {**paws('hand', follow=k, limp=k), **paws('foot', follow=k, limp=k)}
# lying dead the hind legs are stretched out straight and back (author, 15.11). The rat's flank is not upright (the
# belly is wider than the back), so it lies flat on it rolled past 90 degrees, back a little down; at 90 the body
# leaned on its belly edge and the hips hung 0.2 m over the floor (author's screenshot of 15.11). The lower front leg
# goes forward and out, not under the chest.
DEAD = dict(pel_roll=112, pel_z=-0.25, pel_x=0.20, spine_02_pitch=4, spine_03_pitch=6, neck_pitch=14, head_pitch=10,
            **LIMP(1), **paws('foot', stretch=1), hand_r_dz=0.05, foot_r_dz=0.05, hand_r_dy=-0.05,
            hand_l_dy=-0.2, hand_l_dx=-0.1,
            tail_drape=1, head_drape=1, tail_pitch=[4, 5, 6, 6, 6, 5, 4, 3])
# a spasm of the upper hind leg: jerks of three frames each, dying down (author: «резкую судорогу», then slower)
JERK = lambda k: dict(DEAD, foot_r_stretch=1 - 0.16 * k, foot_r_dz=0.05 + 0.012 * k)     # 5x smaller (author, 15.11)
DEATH = [
    (0, {}),
    (4, dict(pel_y=0.06, pel_z=0.01, neck_pitch=-14, head_pitch=-16, head_yaw=8, hand_l_dz=0.03, hand_l_pitch=20,
             tail_pitch=[18, 4, 0, 0, 0, 0, 0, 0])),
    # the legs give way: elbows and knees fold, the head sags
    (10, dict(pel_z=-0.10, pel_roll=5, pel_x=0.02, tail_drape=0.01, spine_02_pitch=4, spine_03_pitch=10, neck_pitch=16, head_pitch=18,
              scapula_l_pitch=12, scapula_r_pitch=12, hand_l_dz=0.03, hand_r_dz=0.02,
              tail_pitch=[2, -2, -2, -2, -1, 0, 0, 0])),
    # it tips over its left paws; the legs start to go limp
    (14, dict(pel_z=-0.09, pel_roll=25, pel_x=0.06, spine_03_pitch=10, neck_pitch=16, head_pitch=18,
              **LIMP(0.3), hand_l_dz=0.08, foot_l_dz=0.08, tail_drape=0.2, head_drape=0.15,
              tail_pitch=[2, 0, 0, 0, 0, 0, 0, 0])),
    (18, dict(pel_z=-0.10, pel_roll=65, pel_x=0.12, spine_03_pitch=8, neck_pitch=16, head_pitch=14,
              **LIMP(0.7), tail_drape=0.5, head_drape=0.4, tail_pitch=[2, 2, 2, 2, 2, 2, 2, 2])),
    (23, dict(DEAD, pel_z=-0.26, pel_roll=113, head_drape=0.8)),               # lands
    (26, dict(DEAD, pel_z=-0.235, pel_roll=108, head_drape=0.7, tail_drape=0.8,  # small bounce, limbs flop after
              hand_l_dz=0.03, foot_l_dz=0.03, hand_r_dz=0.09, foot_r_dz=0.09)),
    (30, dict(DEAD)),
    (33, dict(DEAD)),
    (35, JERK(1.0)),                                                            # spasm of the upper hind leg
    (38, JERK(0.15)),
    (41, JERK(0.8)),
    (44, JERK(0.1)),
    (47, JERK(0.45)),
    (50, dict(DEAD)),
    (54, dict(DEAD, hand_r_dy=-0.04, hand_r_pitch=-15)),                        # last twitch of the front paw
    (57, dict(DEAD)),
    (60, dict(DEAD)),
]
# and a slower shiver runs along the spine (author, 15.11): the spine bones curl and uncurl a little, each a bit after
# the one behind it, dying down
SHIVER = (34, 24, 12, 1.5)        # start frame, length, period in frames, degrees per spine bone at the strongest


def death(f):
    P = keyed(DEATH, f)
    start, length, period, amp = SHIVER
    u = f - start
    if 0 < u < length:
        env = min(1.0, u / 3) * (1 - u / length) ** 2
        for i, n in enumerate(('spine_01', 'spine_02', 'spine_03', 'neck')):
            P[n + '_pitch'] = P.get(n + '_pitch', 0.0) + amp * env * sin(2 * pi * (u - 1.5 * i) / period)
    return P


def make(name, n, fn, loop):
    act = bpy.data.actions.get(name)
    if act:
        bpy.data.actions.remove(act)
    act = bpy.data.actions.new(name)
    act.use_fake_user = True
    rig.animation_data_create()
    rig.animation_data.action = act
    for f in range(n + 1):
        apply(fn(f % n if loop else f))
        for b in pb:
            b.keyframe_insert('rotation_quaternion', frame=f, group=b.name)
            b.keyframe_insert('location', frame=f, group=b.name)
    act.use_frame_range = True
    act.frame_start, act.frame_end = 0, n
    act.use_cyclic = loop
    return act


sc = bpy.context.scene
sc.render.fps = FPS
make('A_MutantRat_Hit', 18, lambda f: keyed(HIT, f), False)
make('A_MutantRat_Attack', 24, lambda f: keyed(ATTACK, f), False)
make('A_MutantRat_Aggro', A_N, aggro, True)
make('A_MutantRat_Walk', W_N, walk, True)
make('A_MutantRat_Leap', 42, lambda f: keyed(LEAP, f), False)
make('A_MutantRat_Death', 60, death, False)
act = make('A_MutantRat_Idle', I_N, idle, True)
sc.frame_start, sc.frame_end = 0, I_N
sc.frame_set(0)
print([(a.name, int(a.frame_start), int(a.frame_end), a.use_cyclic) for a in bpy.data.actions if a.name.startswith('A_MutantRat')])
