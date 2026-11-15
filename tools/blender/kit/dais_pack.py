"""Bridge dais, step 3 (pipeline/kit.md): pack the metric UVs of BridgeDais into one atlas.

Run in the live Blender after dais_build.py: exec(open(<this file>).read()). Preliminary row layout per island
(2.0 m rows, 0.02 m gaps, then / 3.2: the dais is larger than the kits), then Pack Islands (Cardinal rotation, merge
overlapping, margin 0.004). Shared copies carry the island numbers of their master, so they move with it and stay one
island under Merge Overlapping.
"""
import bpy, bmesh

ob = bpy.data.objects['BridgeDais']
me = ob.data
bm = bmesh.new()
bm.from_mesh(me)
uvl = bm.loops.layers.uv['UVMap']
il = bm.faces.layers.int['island']
x = y = rowh = 0.0
isl = {}
for f in bm.faces:
    isl.setdefault(f[il], []).append(f)
for k, fs in sorted(isl.items()):
    us = [l[uvl].uv for f in fs for l in f.loops]
    mnx, mxx = min(u.x for u in us), max(u.x for u in us)
    mny, mxy = min(u.y for u in us), max(u.y for u in us)
    w, h = mxx - mnx, mxy - mny
    if x + w > 2.0:
        x = 0.0
        y += rowh + 0.02
        rowh = 0.0
    dx, dy = x - mnx, y - mny
    x += w + 0.02
    rowh = max(rowh, h)
    for f in fs:
        for l in f.loops:
            l[uvl].uv.x = (l[uvl].uv.x + dx) / 3.2
            l[uvl].uv.y = (l[uvl].uv.y + dy) / 3.2
print('preliminary rows height', round((y + rowh) / 3.2, 3))
bm.to_mesh(me)
bm.free()

bpy.ops.object.select_all(action='DESELECT')
ob.select_set(True)
bpy.context.view_layer.objects.active = ob
found = [(w, a) for w in bpy.context.window_manager.windows for a in w.screen.areas if a.type == 'VIEW_3D']
if found:
    win, area = found[0]
    old_type = None
else:
    win = bpy.context.window_manager.windows[0]
    area = min(win.screen.areas, key=lambda a: a.width * a.height)
    old_type, area.type = area.type, 'VIEW_3D'
try:
    reg = next(r for r in area.regions if r.type == 'WINDOW')
    with bpy.context.temp_override(window=win, area=area, region=reg):
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_all(action='SELECT')
        bpy.ops.uv.select_all(action='SELECT')
        print(bpy.ops.uv.pack_islands(udim_source='CLOSEST_UDIM', rotate=True, rotate_method='CARDINAL', scale=True,
                                      merge_overlap=True, margin_method='FRACTION', margin=0.004, shape_method='CONCAVE'))
        bpy.ops.mesh.select_all(action='DESELECT')
        bpy.ops.object.mode_set(mode='OBJECT')
finally:
    if old_type:
        area.type = old_type
bpy.ops.object.select_all(action='DESELECT')
