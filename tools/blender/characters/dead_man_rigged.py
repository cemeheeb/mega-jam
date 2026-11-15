"""Мертвец на скелете манекена Unreal: SK_DeadManRig.fbx (автор, 16.11: для вступительной сцены у зеркала —
«мертвеца продублировать для этой сцены и навешать на него риг манекена, чтобы в зеркале отражение не было статичным»).

    /Applications/Blender.app/Contents/MacOS/Blender -b SourceArt/characters/old-enemy/source/old-enemy.blend \
        --python tools/blender/characters/dead_man_rigged.py

Запускается в сцене старика: в ней уже есть скелет манекена (объект root под пустышкой Rig 0,01) в позе покоя под
А-позу моделей Tripo и старик с готовыми весами. Мертвец (объект DeadMan из dead-man.blend, поза покоя) той же
породы: рост и разворот рук почти те же, поэтому веса переносятся со старика по ближайшей поверхности, не больше
четырёх костей на вершину. Ничего в blend не сохраняется. Пишет SourceArt/characters/dead-man/SK_DeadManRig.fbx
теми же настройками, что export_old_enemy.py. Статичные позы мертвеца (dead_man_poses.py) это не трогает.
Импорт — tools/ue/import_dead_man_rig.py.
"""
import os

import bpy
from mathutils import Matrix

ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))), "SourceArt", "characters")
DEAD = os.path.join(ROOT, "dead-man", "source", "dead-man.blend")
OUT = os.path.join(ROOT, "dead-man", "SK_DeadManRig.fbx")


def activate(ob):
    bpy.ops.object.select_all(action="DESELECT")
    ob.hide_set(False)
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob


def main():
    scene = bpy.context.scene
    arm = bpy.data.objects["root"]

    # мертвец в позе покоя: без своего рига и его групп
    with bpy.data.libraries.load(DEAD) as (src, dst):
        dst.objects = ["DeadMan"]
    dead = dst.objects[0]
    scene.collection.objects.link(dead)
    dead.parent = None
    dead.matrix_world = Matrix.Identity(4)
    for m in list(dead.modifiers):
        dead.modifiers.remove(m)
    dead.vertex_groups.clear()

    # источник весов: тело и голова старика одним мешем
    parts = []
    for n in ("OldEnemy_Body", "OldEnemy_Head"):
        c = bpy.data.objects[n].copy()
        c.data = c.data.copy()
        scene.collection.objects.link(c)
        parts.append(c)
    bpy.ops.object.select_all(action="DESELECT")
    for c in parts:
        c.select_set(True)
    bpy.context.view_layer.objects.active = parts[0]
    bpy.ops.object.join()
    source = bpy.context.view_layer.objects.active
    for m in list(source.modifiers):
        source.modifiers.remove(m)

    # рост: макушка мертвеца — на высоту макушки старика, от пола
    top = lambda ob: max((ob.matrix_world @ v.co).z for v in ob.data.vertices)
    k = top(source) / top(dead)
    dead.data.transform(Matrix.Scale(k, 4))
    print(f"## рост мертвеца x{k:.3f}: {top(dead):.3f} м")

    activate(dead)
    mod = dead.modifiers.new("Weights", "DATA_TRANSFER")
    mod.object = source
    mod.use_vert_data = True
    mod.data_types_verts = {"VGROUP_WEIGHTS"}
    mod.vert_mapping = "POLYINTERP_NEAREST"
    mod.layers_vgroup_select_src = "ALL"
    mod.layers_vgroup_select_dst = "NAME"
    bpy.ops.object.datalayout_transfer(modifier=mod.name)
    bpy.ops.object.modifier_apply(modifier=mod.name)
    bpy.ops.object.vertex_group_limit_total(group_select_mode="ALL", limit=4)
    bpy.ops.object.vertex_group_normalize_all(group_select_mode="ALL", lock_active=False)
    bones = {b.name for b in arm.data.bones}
    for g in [g for g in dead.vertex_groups if g.name not in bones]:
        dead.vertex_groups.remove(g)
    used = sum(1 for v in dead.data.vertices if v.groups)
    print(f"## веса: {len(dead.vertex_groups)} групп, вершин с весами {used} из {len(dead.data.vertices)}")
    assert used == len(dead.data.vertices)
    a = dead.modifiers.new("Armature", "ARMATURE")
    a.object = arm
    bpy.data.objects.remove(source, do_unlink=True)

    # выгрузка — как у старика (export_old_enemy.py): корень FBX — объект root, файл в сантиметрах
    assert abs(arm.matrix_world.to_scale().x - 0.01) < 1e-6
    arm.parent = None
    arm.matrix_world = Matrix.Identity(4)
    arm.hide_set(False)
    arm.hide_viewport = False
    arm.data.pose_position = "REST"
    scene.unit_settings.scale_length = 0.01
    dead.data.transform(Matrix.Scale(100.0, 4))
    dead.data.uv_layers[0].name = "UVMap"
    for i, slot in enumerate(dead.data.materials):
        mat = bpy.data.materials.new("MI_" + slot.name)     # имя слота в Unreal: MI_DeadMan_Body, MI_DeadMan_Head
        dead.data.materials[i] = mat
    dead.name = "DeadManRig"
    bpy.ops.object.select_all(action="DESELECT")
    arm.select_set(True)
    dead.select_set(True)
    bpy.context.view_layer.objects.active = arm
    bpy.ops.export_scene.fbx(
        filepath=OUT, use_selection=True, object_types={"ARMATURE", "MESH"},
        apply_unit_scale=True, apply_scale_options="FBX_SCALE_UNITS", axis_forward="-Z", axis_up="Y",
        bake_space_transform=False, use_mesh_modifiers=True, mesh_smooth_type="FACE", use_triangles=False,
        use_tspace=False, use_custom_props=False, add_leaf_bones=False, primary_bone_axis="Y", secondary_bone_axis="X",
        use_armature_deform_only=False, armature_nodetype="NULL", bake_anim=False, path_mode="STRIP",
        embed_textures=False, colors_type="NONE")
    print("## wrote", OUT, os.path.getsize(OUT), "bytes;", len(dead.data.vertices), "verts;",
          "materials", [m.name for m in dead.data.materials])


main()
