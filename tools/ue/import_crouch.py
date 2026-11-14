"""Анимации приседа для героя: MM_Crouch_Idle и MM_Crouch_Walk в /Game/Characters/Mannequins/Anims/Crouch.

Источник — плагин движка MoverExamples (Engine/Plugins/Experimental/MoverExamples): там лежат анимации приседа
на том же скелете манекена UE5, но на своей копии скелета (/MoverExamples/.../SK_Mannequin). Скрипт копирует их
на скелет проекта через IK Retargeter (RunBatchRetarget). Плагин в проекте не включается: его включает только
этот запуск, ключом -EnablePlugins.

Запуск без окна; открытый редактор не мешает, скрипт только создаёт новые ассеты:

    "/Users/Shared/Epic Games/UE_5.8/Engine/Binaries/Mac/UnrealEditor-Cmd" "$PWD/MegaJam.uproject" \\
        -run=pythonscript -script="$PWD/tools/ue/import_crouch.py" -EnablePlugins=MoverExamples \\
        -unattended -nosplash -nullrhi -nosound -stdout -FullStdOutLogOutput

Готовые ассеты не перезаписывает: чтобы пересоздать, удалите их в редакторе. Строки результата — «Crouch:».
Ассеты берёт ARunDirector::UpdateCrouch по пути из кода.
"""

import unreal

SRC_DIR = "/MoverExamples/Characters/Mannequins/Animations/Manny"
SRC_MESH = "/MoverExamples/Characters/Mannequins/Meshes/SKM_Manny_Simple"
SRC_RIG = "/MoverExamples/Characters/Mannequins/Rigs/IK_Mannequin"
TMP_DIR = "/Game/Developers/cemeheeb/CrouchTmp"   # временные риг и ретаргетер, на диск не пишутся
DST_DIR = "/Game/Characters/Mannequins/Anims/Crouch"
DST_MESH = "/Game/Characters/Mannequins/Meshes/SKM_Manny_Simple"
DST_SKELETON = "/Game/Characters/Mannequins/Meshes/SK_Mannequin"
CHECK_BONES = ["pelvis", "spine_03", "head", "thigh_l", "calf_l", "foot_l", "thigh_r", "foot_r", "upperarm_l", "hand_r"]
ANIMS = [("MM_Unarmed_Crouch_Idle", "MM_Crouch_Idle"), ("MM_Unarmed_Crouch_Walk_Fwd", "MM_Crouch_Walk")]


def log(msg):
    unreal.log("Crouch: " + msg)


def pose(anim, bone, t):
    x = unreal.AnimationLibrary.get_bone_pose_for_time(anim, bone, t, False)
    v = x.translation
    return "(%.1f %.1f %.1f)" % (v.x, v.y, v.z)


def describe(anim, label):
    length = anim.get_editor_property("sequence_length")
    skel = anim.get_editor_property("skeleton")
    log("%s: %.2f s, skeleton %s, root motion %s, root lock %s" % (
        label, length, skel.get_path_name() if skel else None,
        anim.get_editor_property("enable_root_motion"), anim.get_editor_property("force_root_lock")))
    for t in (0.0, length * 0.5, length):
        log("   t=%.2f root %s pelvis %s" % (t, pose(anim, "root", t), pose(anim, "pelvis", t)))


def compare(src, dst):
    """Скелеты одинаковые, так что результат должен совпасть с источником кость в кость (корень заперт отдельно)."""
    length = src.get_editor_property("sequence_length")
    worst_pos, worst_rot = 0.0, 0.0
    for i in range(9):
        t = length * i / 8.0
        for bone in CHECK_BONES:
            a = unreal.AnimationLibrary.get_bone_pose_for_time(src, bone, t, False)
            b = unreal.AnimationLibrary.get_bone_pose_for_time(dst, bone, t, False)
            worst_pos = max(worst_pos, (a.translation - b.translation).length())
            worst_rot = max(worst_rot, abs(a.rotation.angular_distance(b.rotation)) * 57.2958)
    return worst_pos, worst_rot


def make_retargeter(src_mesh, dst_mesh):
    tools = unreal.AssetToolsHelpers.get_asset_tools()
    rig = unreal.load_asset(SRC_RIG)
    chains = len(unreal.IKRigController.get_controller(rig).get_retarget_chains()) if rig else 0
    log("plugin IK rig %s, %d chains" % (rig.get_path_name() if rig else None, chains))
    if chains == 0:
        rig = tools.create_asset("IK_CrouchTmp", TMP_DIR, unreal.IKRigDefinition, unreal.IKRigDefinitionFactory())
        rc = unreal.IKRigController.get_controller(rig)
        rc.set_skeletal_mesh(src_mesh)
        rc.apply_auto_generated_retarget_definition()
        log("temporary IK rig, %d chains" % len(rc.get_retarget_chains()))
    rtg = tools.create_asset("RTG_CrouchTmp", TMP_DIR, unreal.IKRetargeter, unreal.IKRetargetFactory())
    c = unreal.IKRetargeterController.get_controller(rtg)
    c.set_ik_rig(unreal.RetargetSourceOrTarget.SOURCE, rig)
    c.set_ik_rig(unreal.RetargetSourceOrTarget.TARGET, rig)
    c.set_preview_mesh(unreal.RetargetSourceOrTarget.SOURCE, src_mesh)
    c.set_preview_mesh(unreal.RetargetSourceOrTarget.TARGET, dst_mesh)
    if c.get_num_retarget_ops() == 0:
        c.add_default_ops()
    c.assign_ik_rig_to_all_ops(unreal.RetargetSourceOrTarget.SOURCE, rig)
    c.assign_ik_rig_to_all_ops(unreal.RetargetSourceOrTarget.TARGET, rig)
    c.auto_map_chains(unreal.AutoMapChainType.EXACT, True)
    ops = [str(c.get_op_name(i)) for i in range(c.get_num_retarget_ops())]
    log("temporary retargeter ops %s" % ops)
    # Шаг вперёд в источнике записан в корень (540 см за цикл). Без костей корня у операции Root Motion корень
    # результата стоит, а таз уезжает вперёд — на месте такая анимация не играется. Кости ставим явно.
    for i in range(len(ops)):
        c.run_op_initial_setup(i)
        oc = c.get_op_controller(i)
        if hasattr(oc, "set_source_root_bone"):
            log("root motion op before: source %s, target %s, pelvis %s" % (
                oc.get_source_root_bone(), oc.get_target_root_bone(), oc.get_target_pelvis_bone()))
            oc.set_source_root_bone("root")
            oc.set_target_root_bone("root")
            oc.set_target_pelvis_bone("pelvis")
    return rtg


def main():
    ar = unreal.AssetRegistryHelpers.get_asset_registry()
    ar.scan_paths_synchronous(["/MoverExamples/Characters/Mannequins", "/Game/Characters/Mannequins"], True)
    src_mesh = unreal.load_asset(SRC_MESH)
    dst_mesh = unreal.load_asset(DST_MESH)
    if not (src_mesh and dst_mesh):
        log("FAILED: missing source mesh %s or target mesh %s" % (src_mesh, dst_mesh))
        return
    rtg = make_retargeter(src_mesh, dst_mesh)
    for src_name, dst_name in ANIMS:
        dst_path = "%s/%s" % (DST_DIR, dst_name)
        if unreal.EditorAssetLibrary.does_asset_exist(dst_path):
            log("%s exists, skipped" % dst_path)
            continue
        src_path = "%s/%s" % (SRC_DIR, src_name)
        src = unreal.load_asset(src_path)
        describe(src, "source " + src_name)
        inputs = unreal.IKRetargetBatchOperationInputs()
        inputs.set_editor_property("assets_to_retarget", [unreal.EditorAssetLibrary.find_asset_data(src_path)])
        inputs.set_editor_property("source_mesh", src_mesh)
        inputs.set_editor_property("target_mesh", dst_mesh)
        inputs.set_editor_property("ik_retarget_asset", rtg)
        inputs.set_editor_property("search", src_name)
        inputs.set_editor_property("replace", dst_name)
        inputs.set_editor_property("target_path", DST_DIR)
        inputs.set_editor_property("use_source_path", False)
        inputs.set_editor_property("include_referenced_assets", False)
        out = unreal.IKRetargetBatchOperation.run_batch_retarget(inputs)
        log("retarget %s -> %s" % (src_name, [str(a.package_name) for a in out]))
        anim = unreal.load_asset(dst_path)
        if not anim:
            log("FAILED: %s was not created" % dst_path)
            continue
        skel = anim.get_editor_property("skeleton")
        if not skel or skel.get_path_name().split(".")[0] != DST_SKELETON:
            log("FAILED: %s is on skeleton %s" % (dst_path, skel.get_path_name() if skel else None))
            continue
        worst_pos, worst_rot = compare(src, anim)
        log("difference from source: up to %.2f cm, %.2f deg" % (worst_pos, worst_rot))
        if worst_pos > 2.0 or worst_rot > 3.0:
            log("FAILED: %s differs from source, not saved" % dst_path)
            continue
        # герой играет её напрямую (PlayAnimation), без движения от анимации: корень держим на месте
        anim.set_editor_property("enable_root_motion", False)
        anim.set_editor_property("force_root_lock", True)
        describe(anim, "result " + dst_name)
        unreal.EditorAssetLibrary.save_loaded_asset(anim, False)
        log("saved %s" % dst_path)


main()
