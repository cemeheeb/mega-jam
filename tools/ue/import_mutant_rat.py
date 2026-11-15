"""Импорт крысы-мутанта в /Game/Characters/MutantRat: скелетный меш, скелет, семь анимаций, текстуры, материал.

Запуск без окна; открытый редактор не мешает (он сам увидит новые файлы):

    "/Users/Shared/Epic Games/UE_5.8/Engine/Binaries/Mac/UnrealEditor-Cmd" "$PWD/MegaJam.uproject" \\
        -run=pythonscript -script="$PWD/tools/ue/import_mutant_rat.py" \\
        -unattended -nosplash -nullrhi -nosound -stdout -FullStdOutLogOutput

Файлы готовит SourceArt/characters/mutant-rat/source/export_mutant_rat.py: SK_MutantRat.fbx в метрах — здесь
включён перевод единиц сцены, поэтому размер верный. Анимации из файла (по дублю на действие Blender)
переименовываются в A_MutantRat_<Имя>: Idle, Walk, Aggro, Attack, Leap, Hit, Death. Материал MI_MutantRat —
экземпляр M_Kit с T_MutantRat_BaseColor и ровной T_MutantRat_ORM. Готовое перезаписывается.
В игре крысу ставит ARunEnemy по путям из кода. Строки результата — «Rat:».
"""

import os

import unreal

SRC = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir()), "SourceArt", "characters", "mutant-rat")
DST = "/Game/Characters/MutantRat"
NAME = "SK_MutantRat"
ANIMS = ["Idle", "Walk", "Aggro", "Attack", "Leap", "Hit", "Death"]


def log(msg):
    unreal.log("Rat: " + msg)


def import_file(path, name, options=None):
    task = unreal.AssetImportTask()
    task.filename = path
    task.destination_path = DST
    task.destination_name = name
    task.automated = True
    task.replace_existing = True
    task.save = True
    if options:
        task.options = options
    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
    return list(task.get_editor_property("imported_object_paths"))


def main():
    lib = unreal.EditorAssetLibrary
    # текстуры и материал
    base = import_file(os.path.join(SRC, "T_MutantRat_BaseColor.png"), "T_MutantRat_BaseColor")
    orm = import_file(os.path.join(SRC, "T_MutantRat_ORM.png"), "T_MutantRat_ORM")
    t_orm = unreal.load_asset(DST + "/T_MutantRat_ORM")
    t_orm.set_editor_property("srgb", False)
    t_orm.set_editor_property("compression_settings", unreal.TextureCompressionSettings.TC_MASKS)
    lib.save_loaded_asset(t_orm, False)
    mi_path = DST + "/MI_MutantRat"
    mi = unreal.load_asset(mi_path) if lib.does_asset_exist(mi_path) else unreal.AssetToolsHelpers.get_asset_tools().create_asset(
        "MI_MutantRat", DST, unreal.MaterialInstanceConstant, unreal.MaterialInstanceConstantFactoryNew())
    unreal.MaterialEditingLibrary.set_material_instance_parent(mi, unreal.load_asset("/Game/Materials/M_Kit"))
    unreal.MaterialEditingLibrary.set_material_instance_texture_parameter_value(mi, "BaseColor", unreal.load_asset(DST + "/T_MutantRat_BaseColor"))
    unreal.MaterialEditingLibrary.set_material_instance_texture_parameter_value(mi, "ORM", t_orm)
    lib.save_loaded_asset(mi, False)
    log("textures %s %s, material %s" % (base, orm, mi_path))

    # меш, скелет и анимации одним файлом
    ui = unreal.FbxImportUI()
    ui.set_editor_property("automated_import_should_detect_type", False)
    ui.set_editor_property("mesh_type_to_import", unreal.FBXImportType.FBXIT_SKELETAL_MESH)
    ui.set_editor_property("import_mesh", True)
    ui.set_editor_property("import_as_skeletal", True)
    ui.set_editor_property("import_animations", True)
    ui.set_editor_property("import_materials", False)
    ui.set_editor_property("import_textures", False)
    ui.set_editor_property("create_physics_asset", False)
    sk = ui.get_editor_property("skeletal_mesh_import_data")
    sk.set_editor_property("convert_scene_unit", True)
    sk.set_editor_property("normal_import_method", unreal.FBXNormalImportMethod.FBXNIM_IMPORT_NORMALS)
    sk.set_editor_property("import_morph_targets", False)
    an = ui.get_editor_property("anim_sequence_import_data")
    an.set_editor_property("convert_scene_unit", True)
    an.set_editor_property("animation_length", unreal.FBXAnimationLengthImportType.FBXALIT_EXPORTED_TIME)
    made = import_file(os.path.join(SRC, NAME + ".fbx"), NAME, ui)
    log("imported %s" % made)

    mesh = unreal.load_asset(DST + "/" + NAME)
    # элементы массива приходят копиями: правим копию и кладём её обратно, иначе слот остаётся с материалом по умолчанию
    mats = list(mesh.get_editor_property("materials"))
    for i, m in enumerate(mats):
        m.set_editor_property("material_interface", mi)
        mats[i] = m
    mesh.set_editor_property("materials", mats)
    lib.save_loaded_asset(mesh, False)
    b = mesh.get_bounds()
    log("mesh bounds extent %.0f x %.0f x %.0f cm, materials %d" % (b.box_extent.x * 2, b.box_extent.y * 2, b.box_extent.z * 2, len(mats)))

    # анимации: имя ассета содержит имя действия Blender — привести к A_MutantRat_<Имя>
    reg = unreal.AssetRegistryHelpers.get_asset_registry()
    for a in reg.get_assets_by_path(DST, False):
        if str(a.asset_class_path.asset_name) != "AnimSequence":
            continue
        old = str(a.package_name)
        for n in ANIMS:
            want = "%s/A_MutantRat_%s" % (DST, n)
            if old.endswith("A_MutantRat_" + n) and old != want:
                if lib.does_asset_exist(want):
                    lib.delete_asset(want)
                lib.rename_asset(old, want)
                old = want
        seq = unreal.load_asset(old)
        log("anim %s: %.2f s" % (old, seq.get_play_length()))
    lib.save_directory(DST, False, False)


main()
