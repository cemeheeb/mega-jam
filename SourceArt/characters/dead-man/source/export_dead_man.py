# Выгрузка мертвеца в Unreal: каждая поза — статичный меш SM_DeadMan_<Поза>.fbx, плюс текстуры.
# Правила: pipeline/unreal.md. Запуск из SourceArt:
#   blender -b -y characters/dead-man/source/dead-man.blend --python characters/dead-man/source/export_dead_man.py
# (-y: драйверы рига Rigify). В blend ничего не сохраняется. Файлы пишутся в папку над source/.
#
# Тела на уровне неподвижны, поэтому в игру идут не скелет с анимациями, а готовые позы: меш в позе берётся
# из рига (действия P_DeadMan_*, tools/blender/characters/dead_man_poses.py) в осях опоры позы — начало
# координат меша и есть точка, которую игра ставит на пол, к стене или к краю стола (asset.yml).
# Позы Embed обрезаются в стене на глубине EMBED_CUT: стена 30 см, дальше начинается соседняя комната.
import os

import bmesh
import bpy
from mathutils import Matrix

SRC = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(SRC))  # characters/
OUT = os.environ.get("DEADMAN_EXPORT_DIR") or os.path.dirname(SRC)

EMBED_CUT = 0.28   # м в стену (+Y Blender), как в dead_man_poses.py
ROUGH = 0.85       # однотонный ORM: шероховатость кожи и ткани, как у героя
MATS = {"DeadMan_Body": "MI_DeadMan_Body", "DeadMan_Head": "MI_DeadMan_Head"}


def write_png(name, w, h, rgb_flat):
    """PNG 8 бит RGB, без пересчёта цвета (Non-Color)."""
    img = bpy.data.images.new(name, w, h, alpha=False, float_buffer=False)
    img.colorspace_settings.name = "Non-Color"
    img.pixels.foreach_set(rgb_flat)
    img.filepath_raw = os.path.join(OUT, name + ".png")
    img.file_format = "PNG"
    img.save()
    bpy.data.images.remove(img)
    print("wrote", name + ".png", w, "x", h)


def textures():
    # Цвет тела — уже готовый T_DeadMan_Body_BaseColor.png (кожа рук выровнена по голове, dead_man_skin.py).
    assert os.path.exists(os.path.join(OUT, "T_DeadMan_Body_BaseColor.png"))
    # Цвет головы — jpg Tripo как есть, в PNG.
    src = bpy.data.images.load(os.path.join(ROOT, "dead-man-head/source/tripo/dead_man_head.fbm/dead_man_head_basecolor.jpg"))
    src.colorspace_settings.name = "Non-Color"
    w, h = src.size
    px = [0.0] * (w * h * 4)
    src.pixels.foreach_get(px)
    bpy.data.images.remove(src)
    write_png("T_DeadMan_Head_BaseColor", w, h, px)
    for mat in MATS:
        write_png(f"T_{mat}_ORM", 4, 4, [1.0, ROUGH, 0.0, 1.0] * 16)


def posed_mesh(rig, body, action, cut):
    rig.animation_data.action = action
    bpy.context.scene.frame_set(0)
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(body.evaluated_get(dg), preserve_all_data_layers=True, depsgraph=dg)
    if cut:
        bm = bmesh.new()
        bm.from_mesh(me)
        geom = bm.verts[:] + bm.edges[:] + bm.faces[:]
        bmesh.ops.bisect_plane(bm, geom=geom, plane_co=(0, EMBED_CUT, 0), plane_no=(0, 1, 0), clear_outer=True)
        bm.to_mesh(me)
        bm.free()
    return me


def main():
    textures()
    rig = bpy.data.objects["rig"]
    body = bpy.data.objects["DeadMan"]
    assert body.matrix_world == Matrix.Identity(4) and rig.matrix_world == Matrix.Identity(4)
    temps = {}
    for name in MATS.values():
        temps[name] = bpy.data.materials.new(name)

    bpy.context.scene.unit_settings.scale_length = 0.01   # файл сразу в сантиметрах (pipeline/unreal.md)
    poses = sorted((a for a in bpy.data.actions if a.name.startswith("P_DeadMan_")), key=lambda a: a.name)
    assert len(poses) == 15, [a.name for a in poses]
    for act in poses:
        pose = act.name[len("P_DeadMan_"):]
        me = posed_mesh(rig, body, act, pose.startswith("Embed"))
        me.transform(Matrix.Scale(100.0, 4))
        for i, slot in enumerate(me.materials):
            me.materials[i] = temps[MATS[slot.name]]
        if me.uv_layers:
            me.uv_layers[0].name = "UVMap"
        ob = bpy.data.objects.new(f"SM_DeadMan_{pose}", me)
        bpy.context.scene.collection.objects.link(ob)
        bpy.ops.object.select_all(action="DESELECT")
        ob.select_set(True)
        bpy.context.view_layer.objects.active = ob
        path = os.path.join(OUT, f"SM_DeadMan_{pose}.fbx")
        bpy.ops.export_scene.fbx(
            filepath=path,
            use_selection=True,
            object_types={"MESH"},
            apply_unit_scale=True,
            apply_scale_options="FBX_SCALE_UNITS",
            axis_forward="-Z",
            axis_up="Y",
            bake_space_transform=False,
            use_mesh_modifiers=True,
            mesh_smooth_type="FACE",
            use_triangles=False,
            use_tspace=False,
            use_custom_props=False,
            add_leaf_bones=False,
            bake_anim=False,
            path_mode="STRIP",
            embed_textures=False,
            colors_type="NONE",
        )
        xs, ys, zs = zip(*(v.co for v in me.vertices))
        print(f"wrote SM_DeadMan_{pose}.fbx {os.path.getsize(path)} bytes, {len(me.vertices)} verts, "
              f"{sum(len(p.vertices) - 2 for p in me.polygons)} tris, cm x {min(xs):.0f}..{max(xs):.0f} "
              f"y {min(ys):.0f}..{max(ys):.0f} z {min(zs):.0f}..{max(zs):.0f} (Blender axes)")
        bpy.data.objects.remove(ob)
        bpy.data.meshes.remove(me)


main()
