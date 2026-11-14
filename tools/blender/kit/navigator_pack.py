"""Navigator console, step 3 (pipeline/kit.md): pack the metric UVs of the collection into one atlas.

Run in the live Blender after navigator_build.py. Preliminary row layout per island (2.0 m rows, 0.02 m gaps,
then / 2.2), then Pack Islands (Cardinal rotation, merge overlapping, margin 0.004). The left monitor's islands are
put exactly onto the right monitor's ones, so Merge Overlapping keeps them one island; only its own screen island
gets a place of its own.
"""
import bpy, bmesh

col = bpy.data.collections['NavigatorConsole']
obs = [col.objects[n] for n in ('NavigatorConsole', 'NavigatorMonitorRight', 'NavigatorMonitorLeft')]
x = y = rowh = 0.0
offsets = {}            # right monitor: island -> (dx, dy), reused for the left one


def place(w, h):
    global x, y, rowh
    if x + w > 2.0:
        x = 0.0
        y += rowh + 0.02
        rowh = 0.0
    p = (x, y)
    x += w + 0.02
    rowh = max(rowh, h)
    return p


for o in obs:
    me = o.data
    bm = bmesh.new()
    bm.from_mesh(me)
    uvl = bm.loops.layers.uv['UVMap']
    il = bm.faces.layers.int['island']
    isl = {}
    for f in bm.faces:
        isl.setdefault(f[il], []).append(f)
    for k, fs in sorted(isl.items()):
        us = [l[uvl].uv for f in fs for l in f.loops]
        mnx, mxx = min(u.x for u in us), max(u.x for u in us)
        mny, mxy = min(u.y for u in us), max(u.y for u in us)
        if o.name == 'NavigatorMonitorLeft' and k in offsets:
            dx, dy = offsets[k]
        else:
            px, py = place(mxx - mnx, mxy - mny)
            dx, dy = px - mnx, py - mny
            if o.name == 'NavigatorMonitorRight':
                offsets[k] = (dx, dy)
        for f in fs:
            for l in f.loops:
                l[uvl].uv.x += dx
                l[uvl].uv.y += dy
    bm.to_mesh(me)
    bm.free()
for o in obs:
    for l in o.data.uv_layers['UVMap'].data:
        l.uv = (l.uv[0] / 2.2, l.uv[1] / 2.2)

bpy.ops.object.select_all(action='DESELECT')
for o in obs:
    o.select_set(True)
bpy.context.view_layer.objects.active = obs[0]
# the operator wants a 3D view: any window's; if the author's workspace has none, the smallest area turns into one
# for the time of the pack and back
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
