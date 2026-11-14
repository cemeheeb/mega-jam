# Выгрузка героя в Unreal: SK_Engineer.fbx и текстуры. Правила: pipeline/unreal.md.
# Запуск из SourceArt:
#   blender -b characters/engineer/source/engineer.blend --python characters/engineer/source/export_engineer.py
# В blend ничего не сохраняется. Файлы пишутся в папку над source/.
import os

import bpy
from mathutils import Matrix

SRC = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(SRC))  # characters/
OUT = os.environ.get("ENGINEER_EXPORT_DIR") or os.path.dirname(SRC)  # переопределение — для пробных выгрузок

ARMATURE = "root"  # имя объекта = корневая кость SK_Mannequin
MESHES = ["Engineer_Body", "Engineer_Head", "Engineer_TeethLower", "Engineer_TeethUpper", "Engineer_Tongue"]

# Однотонные ORM для материалов с картинкой цвета: R = AO, G = шероховатость, B = металл.
ORM = {"Engineer_Body": 0.85, "Engineer_Head": 0.85, "Engineer_Teeth": 0.45}


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
    # Зубы: 2048 -> 1024 средним по блокам 2 x 2 (во рту их почти не видно).
    src = bpy.data.images.load(os.path.join(ROOT, "engineer-teeth/source/tripo/engineer_teeth_albedo.jpg"))
    src.colorspace_settings.name = "Non-Color"
    w, h = src.size
    px = [0.0] * (w * h * 4)
    src.pixels.foreach_get(px)
    w2, h2 = w // 2, h // 2
    out = [1.0] * (w2 * h2 * 4)
    for y in range(h2):
        r0 = (2 * y) * w * 4
        r1 = (2 * y + 1) * w * 4
        for x in range(w2):
            i0 = r0 + 8 * x
            i1 = r1 + 8 * x
            o = (y * w2 + x) * 4
            for c in range(3):
                out[o + c] = (px[i0 + c] + px[i0 + 4 + c] + px[i1 + c] + px[i1 + 4 + c]) * 0.25
    bpy.data.images.remove(src)
    write_png("T_Engineer_Teeth_BaseColor", w2, h2, out)
    for mat, rough in ORM.items():
        write_png(f"T_{mat}_ORM", 4, 4, [1.0, rough, 0.0, 1.0] * 16)


def prepare_armature(arm):
    """Корень FBX — сам объект root с масштабом 1.

    Файл пишется сразу в сантиметрах: инструмент импорта MCP (SkeletalMeshTools.import_file) идёт
    через старый FbxFactory, у которого Convert Scene Unit выключен, и метровый FBX встаёт в 100 раз
    меньше (проверено 14.11.2026). Кости манекена уже в сантиметрах: их уменьшала пустышка Rig (0,01).
    Её убираем, меши увеличиваем в 100 раз, единица сцены 0,01 м — UnitScaleFactor в файле 1 (см).
    """
    assert abs(arm.matrix_world.to_scale().x - 0.01) < 1e-6, arm.matrix_world
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
        me.transform(Matrix.Scale(100.0, 4), shape_keys=True)  # метры -> сантиметры, см. prepare_armature
        # Один слой UV с одним именем на всех кусках: Unreal сводит их по номеру канала.
        if not me.uv_layers:
            me.uv_layers.new(name="UVMap")
        me.uv_layers[0].name = "UVMap"
        for i, slot in enumerate(me.materials):
            temps.setdefault(slot.name, temp_material(slot.name))
            me.materials[i] = temps[slot.name]
        # Triangulate из общих правил здесь не ставится: с любым включённым модификатором (кроме Armature)
        # экспортёр берёт вычисленный меш, а в нём нет форм лица (Blender #104714). Треугольники нужны
        # только для совпадения касательных с запечённой картой нормалей, а у героя её нет.
        others = [m.type for m in ob.modifiers if m.type != "ARMATURE" and (m.show_viewport or m.show_render)]
        assert not others, (n, others)

    path = os.path.join(OUT, "SK_Engineer.fbx")
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


main()
