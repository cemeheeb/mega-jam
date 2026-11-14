"""Mutant rat: consistent outward normals for the Tripo fur (SourceArt/characters/mutant-rat).

Run in the live Blender (MCP) on source/mutant-rat.blend after mutant_rat_rig.py (it needs the weights) and before
mutant_rat_texture.py: exec(open(<this file>).read()).

Why. Tripo's mesh comes with custom normals that disagree with the faces: 11 % of the face corners have a normal
pointing to the other side of their face, and a third of the faces are wound inwards. A face seen from its back
gets its normal flipped by the renderer (Blender and Unreal alike), so those fur flaps come out almost black: the
dark patches on the author's screenshot of 15.11.

What.
0. Tripo cuts each flap out of the skin, so the skin has a slit or a hole under every flap and the dark inside of the
   model shows through it. The skin is the biggest region of faces joined across two-face edges; each chain of its
   open edges (fur zone only, so the mouth stays open) is closed along the flap's attachment (edges shared by 3+
   faces) or straight across, and filled. A fill takes one colour from the skin beside it (all its corners on one
   texel), and the texture script does not paint it (face attribute fur_fill = 1).
1. An outward direction for every vertex: away from its bones, blended by its skin weights (the weights are smooth,
   so the field is smooth across the joints).
2. Faces get one winding across every edge shared by two faces; each region joined that way is turned as a whole
   to face along the outward field (vote by area). In the solid zones (head front, paws, growths, eyes, ears,
   whiskers) each face is turned to agree with Tripo's own normals instead.
3. Fur normals: the outward field itself, as on fur cards, so the fur shades as one soft volume and no flap goes
   dark. The solid zones keep Tripo's normals (its snout is cut into stepped pieces that only its own normals hide);
   the two blend over a short band.
4. Sheets seen from both sides (fur flaps, ears, whiskers, single tufts) get a back twin (copies of the vertices,
   reversed, same UVs and weights; face attribute fur_twin = 1). Fur twins carry the same outward normals, ear and
   whisker twins the normals of their own side, so the material culls back faces (Two Sided off) and no side ever
   shows a flipped normal. The closed skin and the closed parts (eyes, growths) get no twins.
"""
import bpy, bmesh, numpy as np, collections

MESH, ARM = 'MutantRat', 'root'
HEAD_Y, PAW_Z = -0.78, 0.10      # solid zones (rig scale: the rat faces -Y, paws on z = 0)
BAND = 0.06                      # m, blend between fur and solid normals
TWIN_DOT = 0.85                  # fur faces whose normal is further than this from the outward field get a twin


def smooth01(x):
    x = np.clip(x, 0, 1)
    return x * x * (3 - 2 * x)


ob = bpy.data.objects[MESH]
me = ob.data
rig = bpy.data.objects[ARM]
names = [g.name for g in ob.vertex_groups]
bones = {b.name: (np.array(b.head_local), np.array(b.tail_local)) for b in rig.data.bones if b.use_deform}

bm = bmesh.new()
bm.from_mesh(me)
tw = bm.faces.layers.int.get('fur_twin') or bm.faces.layers.int.new('fur_twin')   # marks the twins (step 4)
fl = bm.faces.layers.int.get('fur_fill') or bm.faces.layers.int.new('fur_fill')   # and the fills (step 0);
uvl = bm.loops.layers.uv.active                   # a new layer invalidates face references, so they are made first
bm.verts.ensure_lookup_table()
dl = bm.verts.layers.deform.active
cn = np.empty(len(me.loops) * 3, np.float32)     # Tripo's own normals, kept for the solid zones (step 3)
me.corner_normals.foreach_get('vector', cn)
cn = cn.reshape(-1, 3)
bm.faces.ensure_lookup_table()
tripo = {f: {l.vert: cn[me.polygons[f.index].loop_start + i] for i, l in enumerate(f.loops)} for f in bm.faces}


def outward(v):
    p = np.array(v.co)
    acc = np.zeros(3)
    for gi, w in v[dl].items():
        a, c = bones[names[gi]]
        ab = c - a
        t = np.clip((p - a) @ ab / (ab @ ab), 0, 1)
        d = p - (a + ab * t)
        n = np.linalg.norm(d)
        if n > 1e-6:
            acc += w * d / n
    n = np.linalg.norm(acc)
    return acc / n if n > 1e-6 else np.array([0.0, 0.0, 1.0])


# loose parts: the body is the biggest; others with more than 12 vertices are solid (growths, eyes, ears, whiskers)
part = {}
for v in bm.verts:
    if v in part:
        continue
    st, comp = [v], [v]
    part[v] = v.index
    while st:
        x = st.pop()
        for e in x.link_edges:
            y = e.other_vert(x)
            if y not in part:
                part[y] = v.index
                st.append(y)
                comp.append(y)
size = collections.Counter(part.values())
body = size.most_common(1)[0][0]


def fur_mask(v):
    if part[v] != body and size[part[v]] > 12:
        return 0.0
    y, z = v.co.y, v.co.z
    return float(smooth01((y - HEAD_Y) / BAND) * smooth01((z - PAW_Z) / BAND))


# 0. close the skin under the flaps
reg = {}
for f0 in bm.faces:
    if f0 in reg:
        continue
    reg[f0] = f0.index
    st = [f0]
    while st:
        f = st.pop()
        for e in f.edges:
            if len(e.link_faces) == 2:
                g = e.link_faces[1] if e.link_faces[0] == f else e.link_faces[0]
                if g not in reg:
                    reg[g] = f0.index
                    st.append(g)
skin = collections.Counter(reg.values()).most_common(1)[0][0]
sk = [e for e in bm.edges if e.is_boundary and reg[e.link_faces[0]] == skin and min(map(fur_mask, e.verts)) > 0.5]
adj = collections.defaultdict(list)
for e in sk:
    for v in e.verts:
        adj[v].append(e)
used = set()


def walk(v, e):
    chain = [v]
    while True:
        used.add(e)
        v = e.other_vert(v)
        chain.append(v)
        if len(adj[v]) != 2:
            return chain
        e = adj[v][1] if adj[v][0] == e else adj[v][0]
        if e in used:
            return chain


chains = [walk(v, e) for v in list(adj) if len(adj[v]) != 2 for e in adj[v] if e not in used]
chains += [walk(e.verts[0], e) for e in sk if e not in used]


def hinge_path(a, b, depth=8):
    prev, front = {a: None}, [a]
    for _ in range(depth):
        nxt = []
        for v in front:
            for e in v.link_edges:
                if len(e.link_faces) < 3:
                    continue
                w = e.other_vert(v)
                if w in prev:
                    continue
                prev[w] = v
                if w == b:
                    path = [b]
                    while prev[path[-1]] is not None:
                        path.append(prev[path[-1]])
                    return path[::-1]
                nxt.append(w)
        front = nxt
    return None


fills = 0
for ch in chains:
    if ch[0] == ch[-1]:
        poly = ch[:-1]
    else:
        path = hinge_path(ch[-1], ch[0])
        if path:
            poly = ch + path[1:-1]
        elif (ch[0].co - ch[-1].co).length < 0.04:
            poly = ch
        else:
            continue
    if len(poly) < 3 or len(set(poly)) != len(poly):
        continue
    e0 = next(e for e in ch[0].link_edges if e.other_vert(ch[0]) == ch[1])
    sf = e0.link_faces[0]                          # skin face at the cut: the fill takes its colour
    l0 = next(l for l in sf.loops if l.vert == ch[0])
    c = sum((l[uvl].uv for l in sf.loops), l0[uvl].uv * 0) / len(sf.loops)
    uv = l0[uvl].uv.lerp(c, 0.3)
    try:
        f = bm.faces.new(poly)
    except ValueError:
        continue
    tris = bmesh.ops.triangulate(bm, faces=[f], quad_method='BEAUTY', ngon_method='BEAUTY')['faces']
    for t in tris:
        t[fl] = 1
        for l in t.loops:
            l[uvl].uv = uv
    fills += 1
bm.faces.ensure_lookup_table()
print('skin open edges', len(sk), 'chains', len(chains), 'filled', fills)


# 1-2. orient faces: consistent winding across every edge shared by two faces (so a thin closed sheet such as an ear
# keeps its two sides apart), then each such region as a whole faces along the outward field (area-weighted vote)
out = {v: outward(v) for v in bm.verts}
bm.faces.ensure_lookup_table()
state = {}
flip = []
for f0 in bm.faces:
    if f0 in state:
        continue
    state[f0] = False
    region, st = [f0], [f0]
    while st:
        f = st.pop()
        for l in f.loops:
            e = l.edge
            if len(e.link_faces) != 2:
                continue
            g = e.link_faces[1] if e.link_faces[0] == f else e.link_faces[0]
            if g in state:
                continue
            lg = next(x for x in g.loops if x.edge == e)
            state[g] = state[f] ^ (lg.vert == l.vert)      # same start vertex = opposite winding
            region.append(g)
            st.append(g)
    vote = sum(f.calc_area() * np.dot(np.array(f.normal), sum(out[v] for v in f.verts)) * (-1 if state[f] else 1)
               for f in region)
    for f in region:
        if state[f] != (vote < 0):
            flip.append(f)
bmesh.ops.reverse_faces(bm, faces=flip, flip_multires=False)
bm.normal_update()
# solid zones (head front, paws, growths, eyes, ears, whiskers) keep Tripo's normals, so each face there is turned to
# agree with them instead (Tripo's snout is cut into stepped pieces that only its own normals hide)
solid_flip = [f for f in bm.faces if f in tripo and np.mean([fur_mask(v) for v in f.verts]) < 0.5
              and np.dot(np.array(f.normal), sum(tripo[f].values())) < 0]
bmesh.ops.reverse_faces(bm, faces=solid_flip, flip_multires=False)
bm.normal_update()

# 4. back twins for every sheet that can be seen from both sides: the small loose parts (ears, whiskers, single
# tufts), body faces at an open or a shared (3+ faces) edge, i.e. the fur flaps, and body faces that stand off the
# skin. The closed skin and the big closed parts (eyes, growths) get none: their back is never seen.
sheet_vert = set()
for e in bm.edges:
    if len(e.link_faces) != 2:
        sheet_vert.update(e.verts)
twin_src = []
for f in bm.faces:
    if f[fl]:                                     # fills face out; their back is inside the body
        continue
    pv = part[f.verts[0]]
    if pv != body:
        if size[pv] <= 100:
            twin_src.append(f)
        continue
    o = sum(out[v] for v in f.verts)
    o /= np.linalg.norm(o)
    if any(v in sheet_vert for v in f.verts) or np.dot(np.array(f.normal), o) < TWIN_DOT:
        twin_src.append(f)
dup = bmesh.ops.duplicate(bm, geom=twin_src)
twins = [g for g in dup['geom'] if isinstance(g, bmesh.types.BMFace)]
bmesh.ops.reverse_faces(bm, faces=twins, flip_multires=False)
for f in twins:
    f[tw] = 1
copies = {g for g in dup['geom'] if isinstance(g, bmesh.types.BMVert)}
twin_set = set(twins)
vmap = {}
for a, b in dup['vert_map'].items():         # source <-> copy (the map may hold both directions)
    vs, vd = (b, a) if a in copies else (a, b)
    out[vd] = out[vs]
    part[vd] = part[vs]
    vmap[vs] = vd
for a, b in dup['face_map'].items():         # a twin shows the other side: Tripo's normals reversed
    fs, fd = (b, a) if a in twin_set else (a, b)
    if fs in tripo and fd not in tripo:
        tripo[fd] = {vmap[v]: -n for v, n in tripo[fs].items()}
bm.normal_update()
print('flipped', len(flip), 'solid flipped', len(solid_flip), 'twins', len(twins), 'faces', len(bm.faces))

# 3. normals per face corner: fur = outward field; solid = Tripo's own (fills: averaged from their faces); blended
geo = {}
for v in bm.verts:
    n = np.zeros(3)
    for f in v.link_faces:
        n += np.array(f.normal) * f.calc_area()
    k = np.linalg.norm(n)
    geo[v] = n / k if k > 1e-9 else out[v]
ln = []
for f in bm.faces:                                # bm.to_mesh keeps this order of faces and corners
    tn = tripo.get(f, {})
    for l in f.loops:
        v = l.vert
        m = fur_mask(v)
        base = tn.get(v)
        n = m * out[v] + (1 - m) * (np.array(base) if base is not None else geo[v])
        k = np.linalg.norm(n)
        ln.append(tuple(n / k) if k > 1e-9 else tuple(out[v]))
bm.to_mesh(me)
bm.free()
me.update()
for p in me.polygons:
    p.use_smooth = True
me.normals_split_custom_set(ln)
me.update()
me.materials[0].use_backface_culling = True       # the twins show the back sides (Two Sided off in Unreal)
print('vertices', len(me.vertices), 'faces', len(me.polygons), 'triangles', sum(len(p.vertices) - 2 for p in me.polygons))
