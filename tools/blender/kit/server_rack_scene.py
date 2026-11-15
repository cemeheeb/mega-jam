"""Background scene for the server rack (pipeline/kit.md steps 1-2): the Tripo mesh as a hidden ReferenceTripo in
collection Source, the model from server_rack_build.py, the blend saved to source/server-rack.blend.

blender -b --factory-startup --python tools/blender/kit/server_rack_scene.py [-- <folder for review renders>]
"""
import bpy, sys, math, os
from mathutils import Vector

ROOT = '/Users/cemeheeb/Projects/ludum-dare'
DIR = ROOT + '/SourceArt/environment/computer/server-rack/source'
argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []

bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
sc.unit_settings.system = 'METRIC'
sc.unit_settings.scale_length = 1.0

# Tripo mesh: 1.0 Tripo unit = 2 m (server_rack_build.py), front at -Y as it comes from the fbx
src = bpy.data.collections.new('Source')
sc.collection.children.link(src)
bpy.ops.import_scene.fbx(filepath=DIR + '/tripo/server-rack.fbx')
ref = [o for o in sc.objects if o.type == 'MESH'][0]
for c in list(ref.users_collection):
    c.objects.unlink(ref)
src.objects.link(ref)
ref.name = 'ReferenceTripo'
ref.scale = (2.0, 2.0, 2.0)
ref.location = (0.0, -0.008, 0.0)      # the body of the Tripo mesh sits 4 mm (x 2) behind the middle
src.hide_render = True

exec(open(ROOT + '/tools/blender/kit/server_rack_build.py').read(), {'__name__': 'server_rack_build'})
ob = bpy.data.objects['ServerRack']

# checks: edges with three faces, degenerate faces
import bmesh
bm = bmesh.new()
bm.from_mesh(ob.data)
e3 = sum(1 for e in bm.edges if len(e.link_faces) > 2)
deg = sum(1 for f in bm.faces if f.calc_area() < 1e-9)
print('CHECK edges with >2 faces', e3, 'degenerate faces', deg)
bm.free()

ref.hide_set(True)
bpy.ops.wm.save_as_mainfile(filepath=DIR + '/server-rack.blend', compress=True)
print('SAVED', DIR + '/server-rack.blend')

if argv:
    out = argv[0]
    os.makedirs(out, exist_ok=True)
    eng = [e.identifier for e in bpy.types.RenderSettings.bl_rna.properties['engine'].enum_items]
    sc.render.engine = 'BLENDER_EEVEE_NEXT' if 'BLENDER_EEVEE_NEXT' in eng else 'BLENDER_EEVEE'
    sc.render.resolution_x, sc.render.resolution_y = 1100, 1100
    w = bpy.data.worlds.new('Review')
    sc.world = w
    w.use_nodes = True
    w.node_tree.nodes['Background'].inputs[0].default_value = (0.75, 0.75, 0.75, 1)
    w.node_tree.nodes['Background'].inputs[1].default_value = 0.9
    sun = bpy.data.objects.new('Sun', bpy.data.lights.new('Sun', 'SUN'))
    sun.data.energy = 3.0
    sun.rotation_euler = (math.radians(50), 0, math.radians(-35))
    sc.collection.objects.link(sun)
    cam = bpy.data.objects.new('Cam', bpy.data.cameras.new('Cam'))
    sc.collection.objects.link(cam)
    sc.camera = cam
    cam.data.type = 'ORTHO'

    def shot(name, c, d, scale):
        d = Vector(d).normalized()
        cam.data.ortho_scale = scale
        cam.location = Vector(c) + d * 6
        cam.rotation_euler = (-d).to_track_quat('-Z', 'Y').to_euler()
        sc.render.filepath = f'{out}/{name}.png'
        bpy.ops.render.render(write_still=True)

    shot('model_34', (0, 0, 1.0), (0.8, -1, 0.45), 2.9)
    shot('model_front', (0, 0, 1.0), (0, -1, 0), 2.3)
    shot('model_side', (0, 0, 1.0), (1, 0, 0), 2.3)
    shot('model_back34', (0, 0, 1.0), (-0.8, 1, 0.45), 2.9)
    shot('model_drawer', (0.46, -0.4, 1.25), (0.7, -1, 0.35), 0.7)
    shot('model_bottom', (0.85, -0.2, 0.15), (1, -0.8, 0.15), 0.8)
    # side by side with the Tripo mesh
    src.hide_render = False
    ref.hide_set(False)
    ref.location = (2.2, -0.008, 0.0)
    shot('compare_34', (1.1, 0, 1.0), (0.6, -1, 0.35), 4.6)
    print('RENDERED')
