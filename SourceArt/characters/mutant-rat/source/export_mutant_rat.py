"""Крыса-мутант в Unreal: SK_MutantRat.fbx (меш, скелет, семь анимаций) и текстуры. Правила: pipeline/unreal.md.

    /Applications/Blender.app/Contents/MacOS/Blender -b SourceArt/characters/mutant-rat/source/mutant-rat.blend \
        --python-exit-code 1 --python SourceArt/characters/mutant-rat/source/export_mutant_rat.py

В blend ничего не сохраняется. Пишет в папку карточки:
  SK_MutantRat.fbx            арматура root (только деформирующие кости: управляющие ik_* в игру не идут), меш
                              MutantRat, все действия A_MutantRat_* запечены на кости покадрово (30 кадров/с)
  T_MutantRat_BaseColor.png   цвет Tripo как есть
  T_MutantRat_ORM.png         ровный 4 x 4: шероховатость 0,85, металла нет
Файл в метрах: импорт tools/ue/import_mutant_rat.py включает перевод единиц сцены, поэтому в Unreal крыса
своего размера (2 м с хвостом). Лицо крысы — −Y Blender, в Unreal это +Y.
"""
import os

import bpy
import numpy as np

SRC = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.dirname(SRC)


def textures():
    src = bpy.data.images.load(os.path.join(SRC, "tripo", "mutant_rat_basecolor.jpg"))
    src.colorspace_settings.name = "Non-Color"
    w, h = src.size
    px = np.empty(w * h * 4, np.float32)
    src.pixels.foreach_get(px)
    im = bpy.data.images.new("base", w, h, alpha=False, is_data=True)
    im.pixels.foreach_set(px)
    im.filepath_raw = os.path.join(OUT, "T_MutantRat_BaseColor.png")
    im.file_format = "PNG"
    im.save()
    orm = bpy.data.images.new("orm", 4, 4, alpha=False, is_data=True)
    orm.pixels.foreach_set(np.tile(np.array([1.0, 0.85, 0.0, 1.0], np.float32), 16))
    orm.filepath_raw = os.path.join(OUT, "T_MutantRat_ORM.png")
    orm.file_format = "PNG"
    orm.save()
    print("textures", w, "x", h)


def main():
    textures()
    arm = bpy.data.objects["root"]
    mesh = bpy.data.objects["MutantRat"]
    for o in bpy.data.objects:
        o.hide_set(False)
        o.hide_viewport = False
        o.select_set(o in (arm, mesh))
    bpy.context.view_layer.objects.active = arm
    mat = bpy.data.materials.new("MI_MutantRat")
    used = sorted({p.material_index for p in mesh.data.polygons})
    print("material slots used", used, [s.name for s in mesh.data.materials])
    for i in range(len(mesh.data.materials)):
        mesh.data.materials[i] = mat
    mesh.data.uv_layers[0].name = "UVMap"
    acts = sorted(a.name for a in bpy.data.actions if a.name.startswith("A_MutantRat_"))
    print("actions", acts)
    path = os.path.join(OUT, "SK_MutantRat.fbx")
    bpy.ops.export_scene.fbx(
        filepath=path,
        use_selection=True,
        object_types={"ARMATURE", "MESH"},
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
        primary_bone_axis="Y",
        secondary_bone_axis="X",
        use_armature_deform_only=True,
        armature_nodetype="NULL",
        bake_anim=True,
        bake_anim_use_all_bones=True,
        bake_anim_use_nla_strips=False,
        bake_anim_use_all_actions=True,
        bake_anim_force_startend_keying=True,
        bake_anim_step=1.0,
        bake_anim_simplify_factor=0.0,
        path_mode="STRIP",
        embed_textures=False,
        colors_type="NONE",
    )
    print("wrote", path, os.path.getsize(path), "bytes; deform bones", sum(1 for b in arm.data.bones if b.use_deform))


main()
