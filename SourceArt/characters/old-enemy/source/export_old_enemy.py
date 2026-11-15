# Выгрузка старика в Unreal: SK_OldEnemy.fbx на скелете манекена и текстуры. Правила: pipeline/unreal.md.
# Запуск из SourceArt:
#   blender -b characters/old-enemy/source/old-enemy.blend --python characters/old-enemy/source/export_old_enemy.py
# В blend ничего не сохраняется. Файлы пишутся в папку над source/.
# Сделано по образцу героя (characters/engineer/source/export_engineer.py): тот же скелет root, те же настройки FBX.
import os

import bpy
from mathutils import Matrix

SRC = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(SRC))  # characters/
OUT = os.environ.get("OLD_ENEMY_EXPORT_DIR") or os.path.dirname(SRC)  # переопределение — для пробных выгрузок

ARMATURE = "root"  # имя объекта = корневая кость SK_Mannequin
MESHES = ["OldEnemy_Body", "OldEnemy_Head"]

# Цвет — jpg Tripo как есть, в PNG. Остальных карт Tripo в архивах не было.
BASECOLOR = {
    "OldEnemy_Body": "old-enemy-body/source/tripo/man_old_enemy.fbm/man_old_enemy_basecolor.jpg",
    "OldEnemy_Head": "old-enemy-head/source/tripo/man_old_enemy_head.fbm/man_old_enemy_head_basecolor.jpg",
}
ROUGH = 0.85  # однотонный ORM: шероховатость кожи и ткани, как у героя


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
    for mat, rel in BASECOLOR.items():
        src = bpy.data.images.load(os.path.join(ROOT, rel))
        src.colorspace_settings.name = "Non-Color"
        w, h = src.size
        px = [0.0] * (w * h * 4)
        src.pixels.foreach_get(px)
        bpy.data.images.remove(src)
        write_png(f"T_{mat}_BaseColor", w, h, px)
        write_png(f"T_{mat}_ORM", 4, 4, [1.0, ROUGH, 0.0, 1.0] * 16)


def prepare_armature(arm):
    """Корень FBX — сам объект root с масштабом 1; файл сразу в сантиметрах (см. export_engineer.py)."""
    assert abs(arm.matrix_world.to_scale().x - 0.01) < 1e-6, arm.matrix_world
    assert all(tuple(round(x, 6) for x in pb.rotation_quaternion) == (1, 0, 0, 0) and pb.location.length < 1e-6
               for pb in arm.pose.bones), "в риге стоит поза: выгружается только поза покоя"
    arm.parent = None
    arm.matrix_world = Matrix.Identity(4)
    arm.hide_set(False)
    arm.hide_viewport = False
    arm.data.pose_position = "REST"
    bpy.context.scene.unit_settings.scale_length = 0.01


def temp_material(name):
    mat = bpy.data.materials.new("MI_" + name)
    mat.use_nodes = True
    return mat


def main():
    textures()

    arm = bpy.data.objects[ARMATURE]
    prepare_armature(arm)

    bpy.ops.object.select_all(action="DESELECT")
    arm.select_set(True)
    temps = {}
    for n in MESHES:
        ob = bpy.data.objects[n]
        ob.hide_set(False)
        ob.hide_viewport = False
        ob.select_set(True)
        assert ob.matrix_world == Matrix.Identity(4), n
        me = ob.data
        me.transform(Matrix.Scale(100.0, 4))  # метры -> сантиметры
        me.uv_layers[0].name = "UVMap"
        for i, slot in enumerate(me.materials):
            temps.setdefault(slot.name, temp_material(slot.name))
            me.materials[i] = temps[slot.name]
        others = [m.type for m in ob.modifiers if m.type != "ARMATURE" and (m.show_viewport or m.show_render)]
        assert not others, (n, others)
        bones = {b.name for b in arm.data.bones}
        stray = [g.name for g in ob.vertex_groups if g.name not in bones]
        assert not stray, (n, stray)

    path = os.path.join(OUT, "SK_OldEnemy.fbx")
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
        use_armature_deform_only=False,
        armature_nodetype="NULL",
        bake_anim=False,
        path_mode="STRIP",
        embed_textures=False,
        colors_type="NONE",
    )
    print("wrote", path, os.path.getsize(path), "bytes")
    print("bones", len(arm.data.bones), "+ root node", ARMATURE)
    print("materials", sorted(m.name for m in temps.values()))
    for n in MESHES:
        me = bpy.data.objects[n].data
        print(n, len(me.vertices), "verts", sum(len(p.vertices) - 2 for p in me.polygons), "tris")


main()
