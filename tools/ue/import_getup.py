"""Анимация подъёма с пола для вступительной сцены: MM_GetUp в /Game/Characters/Mannequins/Anims/GetUp.

Источник — анимация Mixamo «Getting Up» (автор скачал 16.11: FBX Binary, With Skin, 30 кадров/с): человек лежит
ничком, головой вперёд, и встаёт; кончает стоя в 60 см позади места, где лежал таз. Скрипт импортирует
FBX во временную папку (на диск она не пишется), собирает для скелета Mixamo и для манекена проекта IK-риги
(автоопределение цепочек), переносит анимацию на скелет проекта через IK Retargeter и сохраняет только результат.
Сделано по образцу import_crouch.py. Запуск без окна:

    "/Users/Shared/Epic Games/UE_5.8/Engine/Binaries/Mac/UnrealEditor-Cmd" "$PWD/MegaJam.uproject" \\
        -run=pythonscript -script="$PWD/tools/ue/import_getup.py" -GetUpFbx=<путь к FBX без пробелов> \\
        -unattended -nosplash -nullrhi -nosound -stdout -FullStdOutLogOutput

Строки результата — «GetUp:». Готовый ассет не перезаписывает: чтобы пересоздать, удалите его.
Mixamo — чужой ассет: упомянуть в списке при сдаче (DESIGN.md, раздел 11).
"""
import unreal

TMP_DIR = "/Game/Developers/cemeheeb/GetUpTmp"
DST_DIR = "/Game/Characters/Mannequins/Anims/GetUp"
DST_NAME = "MM_GetUp"
DST_MESH = "/Game/Characters/Mannequins/Meshes/SKM_Manny_Simple"
DST_SKELETON = "/Game/Characters/Mannequins/Meshes/SK_Mannequin"


def log(msg):
    unreal.log("GetUp: " + msg)


def pose(anim, bone, t):
    v = unreal.AnimationLibrary.get_bone_pose_for_time(anim, bone, t, False).translation
    return "(%.1f %.1f %.1f)" % (v.x, v.y, v.z)


def import_fbx(path):
    ui = unreal.FbxImportUI()
    ui.set_editor_property("import_mesh", True)
    ui.set_editor_property("import_as_skeletal", True)
    ui.set_editor_property("import_animations", True)
    ui.set_editor_property("import_materials", False)
    ui.set_editor_property("import_textures", False)
    ui.set_editor_property("create_physics_asset", False)
    ui.set_editor_property("mesh_type_to_import", unreal.FBXImportType.FBXIT_SKELETAL_MESH)
    task = unreal.AssetImportTask()
    task.set_editor_property("filename", path)
    task.set_editor_property("destination_path", TMP_DIR)
    task.set_editor_property("automated", True)
    task.set_editor_property("save", False)
    task.set_editor_property("replace_existing", True)
    task.set_editor_property("options", ui)
    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
    mesh = anim = None
    for p in task.get_editor_property("imported_object_paths"):
        a = unreal.load_asset(p)
        log("imported %s (%s)" % (p, type(a).__name__))
        if isinstance(a, unreal.SkeletalMesh):
            mesh = a
        elif isinstance(a, unreal.AnimSequence):
            anim = a
    if not anim:
        for d in unreal.AssetRegistryHelpers.get_asset_registry().get_assets_by_path(TMP_DIR, True):
            a = d.get_asset()
            if isinstance(a, unreal.AnimSequence):
                anim = a
            elif isinstance(a, unreal.SkeletalMesh) and not mesh:
                mesh = a
    return mesh, anim


def rig_for(name, mesh):
    rig = unreal.AssetToolsHelpers.get_asset_tools().create_asset(name, TMP_DIR, unreal.IKRigDefinition, unreal.IKRigDefinitionFactory())
    rc = unreal.IKRigController.get_controller(rig)
    rc.set_skeletal_mesh(mesh)
    rc.apply_auto_generated_retarget_definition()
    log("%s: root %s, chains %s" % (name, rc.get_retarget_root(), [str(c.chain_name) for c in rc.get_retarget_chains()]))
    return rig


def main():
    path = None
    for token in unreal.SystemLibrary.get_command_line().split():
        if token.lower().startswith("-getupfbx="):
            path = token.split("=", 1)[1].strip('"')
    dst_path = "%s/%s" % (DST_DIR, DST_NAME)
    if unreal.EditorAssetLibrary.does_asset_exist(dst_path):
        log("%s exists, skipped" % dst_path)
        return
    if not path:
        log("FAILED: no -GetUpFbx=")
        return
    src_mesh, src_anim = import_fbx(path)
    dst_mesh = unreal.load_asset(DST_MESH)
    if not (src_mesh and src_anim and dst_mesh):
        log("FAILED: mesh %s anim %s target %s" % (src_mesh, src_anim, dst_mesh))
        return
    length = src_anim.get_editor_property("sequence_length")
    log("source %s: %.2f s" % (src_anim.get_name(), length))
    src_rig, dst_rig = rig_for("IK_GetUpSrc", src_mesh), rig_for("IK_GetUpDst", dst_mesh)
    rtg = unreal.AssetToolsHelpers.get_asset_tools().create_asset("RTG_GetUpTmp", TMP_DIR, unreal.IKRetargeter, unreal.IKRetargetFactory())
    c = unreal.IKRetargeterController.get_controller(rtg)
    c.set_ik_rig(unreal.RetargetSourceOrTarget.SOURCE, src_rig)
    c.set_ik_rig(unreal.RetargetSourceOrTarget.TARGET, dst_rig)
    c.set_preview_mesh(unreal.RetargetSourceOrTarget.SOURCE, src_mesh)
    c.set_preview_mesh(unreal.RetargetSourceOrTarget.TARGET, dst_mesh)
    if c.get_num_retarget_ops() == 0:
        c.add_default_ops()
    c.assign_ik_rig_to_all_ops(unreal.RetargetSourceOrTarget.SOURCE, src_rig)
    c.assign_ik_rig_to_all_ops(unreal.RetargetSourceOrTarget.TARGET, dst_rig)
    c.auto_map_chains(unreal.AutoMapChainType.FUZZY, True)
    # Mixamo стоит в T-позе, манекен — в A-позе: позу переноса цели выровнять по источнику
    try:
        c.auto_align_all_bones(unreal.RetargetSourceOrTarget.TARGET, unreal.RetargetAutoAlignMethod.CHAIN_TO_CHAIN)
        log("target retarget pose aligned to source")
    except Exception as e:  # noqa: BLE001 — имя метода зависит от версии движка
        log("auto align skipped: %s" % e)
    # Только прямой перенос костей. С операцией Root Motion высота и шаг уходили в кость root, и ножная IK блюпринта
    # анимации героя (ABP_Unarmed) скрещивала ему ноги и подвешивала в воздухе; без выравнивания позы руки вставали криво
    for i in reversed(range(c.get_num_retarget_ops())):
        if str(c.get_op_name(i)) in ("Run IK Rig", "Root Motion"):
            log("remove op %s: %s" % (c.get_op_name(i), c.remove_retarget_op(i)))
    ops = [str(c.get_op_name(i)) for i in range(c.get_num_retarget_ops())]
    log("ops %s" % ops)
    for i in range(len(ops)):
        c.run_op_initial_setup(i)

    src_path = src_anim.get_path_name().split(".")[0]
    inputs = unreal.IKRetargetBatchOperationInputs()
    inputs.set_editor_property("assets_to_retarget", [unreal.EditorAssetLibrary.find_asset_data(src_path)])
    inputs.set_editor_property("source_mesh", src_mesh)
    inputs.set_editor_property("target_mesh", dst_mesh)
    inputs.set_editor_property("ik_retarget_asset", rtg)
    inputs.set_editor_property("search", src_anim.get_name())
    inputs.set_editor_property("replace", DST_NAME)
    inputs.set_editor_property("target_path", DST_DIR)
    inputs.set_editor_property("use_source_path", False)
    inputs.set_editor_property("include_referenced_assets", False)
    out = unreal.IKRetargetBatchOperation.run_batch_retarget(inputs)
    log("retarget -> %s" % [str(a.package_name) for a in out])
    anim = unreal.load_asset(dst_path)
    if not anim:
        log("FAILED: %s was not created" % dst_path)
        return
    skel = anim.get_editor_property("skeleton")
    if not skel or skel.get_path_name().split(".")[0] != DST_SKELETON:
        log("FAILED: result is on skeleton %s" % (skel.get_path_name() if skel else None))
        return
    # сцена играет её монтажом; смещение конца от начала (60 см) сцена гасит сама (RunIntro)
    anim.set_editor_property("enable_root_motion", False)
    anim.set_editor_property("force_root_lock", False)   # высота и шаг записаны в корень: запереть — он встанет «в пол»
    n = anim.get_editor_property("sequence_length")
    for t in (0.0, n * 0.25, n * 0.5, n * 0.75, n):
        log("   t=%.2f root %s pelvis %s head %s foot_l %s" % (t, pose(anim, "root", t), pose(anim, "pelvis", t), pose(anim, "head", t), pose(anim, "foot_l", t)))
    unreal.EditorAssetLibrary.save_loaded_asset(anim, False)
    log("saved %s, %.2f s" % (dst_path, n))


main()
