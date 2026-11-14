"""Clean renders of the wall column modules: input pictures for the author's burned versions (Nano Banana, Tripo).

    /Applications/Blender.app/Contents/MacOS/Blender -b --factory-startup --python-exit-code 1 \
        --python SourceArt/environment/common/wall-columns/source/render_wall_columns.py

One picture per module that stands on the walls in the game (build_rooms.py lining): the module alone, its face
(-Y in Blender, the side that looks into the room) turned 35 degrees to the camera, seen from slightly above, on
a plain light-grey background with a soft shadow. Cycles, 1024 x 1536. Writes source/renders/<Module>.png.
"""
import math
import os

import bpy
from mathutils import Vector

SRC = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(SRC, "renders")
MODULES = {   # name in Unreal (SM_WallColumn<name>) -> glb
    "Blank": "wall-column-blank.glb",
    "Drawers": "wall-column-drawers.glb",
    "Emergency": "wall-column-emergency.glb",
    "Locker": "wall-column-locker.glb",
    "LockerTwoDoors": "wall-column-locker-two-doors.glb",
    "Rack": "wall-column-rack.glb",
    "Shelf": "wall-column-shelf.glb",
    "Vent": "wall-column-vent.glb",
    "Header": "wall-column-header.glb",
}


def setup_scene():
    sc = bpy.context.scene
    for o in list(bpy.data.objects):     # the factory scene's cube, camera and light
        bpy.data.objects.remove(o, do_unlink=True)
    sc.render.engine = "CYCLES"
    prefs = bpy.context.preferences.addons["cycles"].preferences
    try:
        prefs.compute_device_type = "METAL"
        prefs.get_devices()
        for d in prefs.devices:
            d.use = True
        sc.cycles.device = "GPU"
    except (TypeError, AttributeError):
        pass
    sc.cycles.samples = 128
    sc.cycles.use_denoising = True
    sc.render.resolution_x, sc.render.resolution_y = 1024, 1536
    sc.render.film_transparent = False
    sc.view_settings.view_transform = "AgX"
    sc.view_settings.look = "AgX - Base Contrast"
    world = bpy.data.worlds.new("Studio")
    sc.world = world
    world.use_nodes = True
    bg = next(n for n in world.node_tree.nodes if n.type == "BACKGROUND")
    bg.inputs[0].default_value = (0.62, 0.62, 0.62, 1)
    bg.inputs[1].default_value = 0.6
    # shadow catcher floor: only the soft shadow under the module, the background stays plain
    bpy.ops.mesh.primitive_plane_add(size=30)
    floor = bpy.context.active_object
    floor.is_shadow_catcher = True
    # key light from the front left and above, a dimmer fill from the right
    for name, loc, energy, size in (("Key", (-3.5, -4.5, 5.0), 900, 3.0), ("Fill", (4.0, -3.0, 2.5), 250, 4.0),
                                    ("Rim", (1.5, 4.0, 4.5), 400, 2.0)):
        light = bpy.data.objects.new(name, bpy.data.lights.new(name, "AREA"))
        light.data.energy = energy
        light.data.size = size
        light.location = loc
        light.rotation_euler = (Vector((0, 0, 1.4)) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
        sc.collection.objects.link(light)
    cam = bpy.data.objects.new("Camera", bpy.data.cameras.new("Camera"))
    cam.data.lens = 60
    sc.collection.objects.link(cam)
    sc.camera = cam
    return sc, cam


def render(sc, cam, name, glb):
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=os.path.join(SRC, "singula", glb))
    new = [o for o in bpy.data.objects if o not in before]
    pts = [o.matrix_world @ Vector(c) for o in new if o.type == "MESH" for c in o.bound_box]
    lo = Vector([min(p[i] for p in pts) for i in range(3)])
    hi = Vector([max(p[i] for p in pts) for i in range(3)])
    center = (lo + hi) / 2
    size = hi - lo
    # face is -Y: camera in front, 35 degrees to the left, 12 degrees above the middle
    az, el = math.radians(-35), math.radians(12)
    cam.data.sensor_fit = "VERTICAL"
    fov_v = 2 * math.atan(cam.data.sensor_height / 2 / cam.data.lens)
    reach = max(size.z, size.x * 1.5, size.y * 1.5) * 0.5 / 0.84    # the module fills ~84 % of the frame height
    dist = reach / math.tan(fov_v / 2) + max(size.x, size.y) * 0.5
    d = Vector((math.sin(az) * math.cos(el), -math.cos(az) * math.cos(el), math.sin(el)))
    cam.location = center + d * dist
    cam.rotation_euler = (center - cam.location).to_track_quat("-Z", "Y").to_euler()
    sc.render.filepath = os.path.join(OUT, name + ".png")
    bpy.ops.render.render(write_still=True)
    print("rendered", name, "size_m", tuple(round(c, 3) for c in size))
    for o in new:
        bpy.data.objects.remove(o, do_unlink=True)


os.makedirs(OUT, exist_ok=True)
scene, camera = setup_scene()
for module, file in MODULES.items():
    render(scene, camera, module, file)
