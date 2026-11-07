# SPDX-License-Identifier: GPL-2.0-or-later

"""エクステンションを有効にした Blender 上で実行する動作確認スクリプト。

テキストエディタで開いて実行するか、exec(open(path).read()) で読み込む。
一時的なオブジェクトだけを作り、終わったら削除する。
"""

import importlib

import bpy

PACKAGE = "bl_ext.user_default.l0c_vertex_group_util"
order = importlib.import_module(PACKAGE + ".order")
sides = importlib.import_module(PACKAGE + ".sides")
state = importlib.import_module(PACKAGE + ".state")
prefs_module = importlib.import_module(PACKAGE + ".prefs")

failures = []
created = []


def check(label, actual, expected):
    if actual != expected:
        failures.append(f"{label}: expected {expected!r}, got {actual!r}")


def names(ob):
    return [vg.name for vg in ob.vertex_groups]


def selected(ob):
    return state.selected_names(ob)


def make_mesh(name, group_names, offset=(0.0, 0.0, 0.0)):
    me = bpy.data.meshes.new(name)
    me.from_pydata([(0, 0, 0), (1, 0, 0), (0, 1, 0), (1, 1, 0)], [], [(0, 1, 3, 2)])
    ob = bpy.data.objects.new(name, me)
    ob.location = offset
    bpy.context.scene.collection.objects.link(ob)
    for i, n in enumerate(group_names):
        vg = ob.vertex_groups.new(name=n)
        vg.add([i % 4], (i + 1) / 100, 'REPLACE')
    created.append(ob)
    state.sync(ob)
    return ob


def run(ob, op, selected_objects=None, **kwargs):
    view_layer = bpy.context.view_layer
    view_layer.objects.active = ob
    with bpy.context.temp_override(
        object=ob, active_object=ob,
        selected_objects=selected_objects or [ob],
    ):
        return op('EXEC_DEFAULT', **kwargs)


def select(ob, group_names):
    state.set_selected(ob, names(ob), False)
    state.set_selected(ob, group_names, True)


def test_pure():
    base = ["a", "b", "c", "d", "e"]
    check("move_up", order.move_up(base, {"a", "c", "d"}), ["a", "c", "d", "b", "e"])
    check("move_down", order.move_down(base, {"b", "e"}), ["a", "c", "b", "d", "e"])
    check("move_to", order.move_to(base, {"d", "b"}, 1), ["a", "b", "d", "c", "e"])
    check("reorder_slots", order.reorder_slots(base, {"b", "d"}, lambda s: s[::-1]), ["a", "d", "c", "b", "e"])
    rank = order.dictionary_rank(["Hips", "Hair_*", "Spine", "Hair_02", "?ye"])
    check(
        "dictionary",
        order.sort_by_rank(["X", "Hair_10", "Eye", "Spine", "Hair_02", "Hips", "Hair_01"], rank),
        ["Hips", "Hair_10", "Hair_01", "Spine", "Hair_02", "Eye", "X"],
    )


def test_apply_order():
    ob = make_mesh("_vgu_apply", ["A", "B", "C", "D"])
    mod = ob.modifiers.new("mask", 'MASK')
    mod.vertex_group = "C"
    ob.vertex_groups.active_index = 1
    order.apply_order(bpy.context, ob, ["D", "C", "B", "A"])
    check("apply names", names(ob), ["D", "C", "B", "A"])
    check("apply active", ob.vertex_groups.active.name, "B")
    check("apply weight", round(ob.vertex_groups["C"].weight(2), 3), 0.03)
    check("apply modifier", mod.vertex_group, "C")


def test_sync():
    ob = make_mesh("_vgu_sync", ["A", "B", "C"])
    select(ob, ["B"])
    ob.vertex_groups["B"].name = "B2"
    state.sync(ob)
    check("rename follow", selected(ob), ["B2"])
    # 標準の移動操作は並べ替えなので、選択はグループ名に付いたままになる
    ob.vertex_groups.active_index = 1
    with bpy.context.temp_override(object=ob, active_object=ob):
        bpy.ops.object.vertex_group_move(direction='UP')
    state.sync(ob)
    check("reorder keep", selected(ob), ["B2"])
    ob.vertex_groups.new(name="D")
    ob.vertex_groups.remove(ob.vertex_groups["A"])
    state.sync(ob)
    check("items", sorted(i.name for i in ob.l0c_vgu.items), ["B2", "C", "D"])


def test_select_ops():
    ob = make_mesh("_vgu_select", ["A", "B", "C", "D", "E"])
    run(ob, bpy.ops.l0c_vgu.select_all, action='SELECT')
    check("select all", len(selected(ob)), 5)
    select(ob, ["A", "B"])
    run(ob, bpy.ops.l0c_vgu.select_all, action='INVERT')
    check("invert", selected(ob), ["C", "D", "E"])
    run(ob, bpy.ops.l0c_vgu.select_all, action='DESELECT')
    # ユーザーがチェックボックスを切り替えた操作を再現する
    ob.l0c_vgu.items["B"].selected = True
    ob.vertex_groups.active_index = 3
    run(ob, bpy.ops.l0c_vgu.select_range)
    check("range", selected(ob), ["B", "C", "D"])


def test_sort_ops():
    ob = make_mesh("_vgu_sort", ["A", "B", "C", "D", "E"])
    select(ob, ["B", "D"])
    run(ob, bpy.ops.l0c_vgu.move_selected, direction='TOP')
    check("move top", names(ob), ["B", "D", "A", "C", "E"])
    run(ob, bpy.ops.l0c_vgu.move_selected, direction='DOWN')
    check("move down", names(ob), ["A", "B", "D", "C", "E"])
    run(ob, bpy.ops.l0c_vgu.move_selected_to, position=4)
    check("move to", names(ob), ["A", "C", "E", "B", "D"])
    run(ob, bpy.ops.l0c_vgu.sort, method='REVERSE', scope='SELECTED')
    check("reverse selected", names(ob), ["A", "C", "E", "D", "B"])
    run(ob, bpy.ops.l0c_vgu.sort, method='REVERSE', scope='ALL')
    check("reverse all", names(ob), ["B", "D", "E", "C", "A"])

    arm_data = bpy.data.armatures.new("_vgu_arm")
    arm = bpy.data.objects.new("_vgu_arm", arm_data)
    bpy.context.scene.collection.objects.link(arm)
    created.append(arm)
    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.mode_set(mode='EDIT')
    for n in ("C", "A", "E"):
        bone = arm_data.edit_bones.new(n)
        bone.tail = (0, 0, 1)
    bpy.ops.object.mode_set(mode='OBJECT')
    ob.modifiers.new("arm", 'ARMATURE').object = arm
    run(ob, bpy.ops.l0c_vgu.sort, method='BONE', scope='ALL')
    check("bone", names(ob), ["C", "A", "E", "B", "D"])

    for vg in ob.vertex_groups:
        if vg.name in {"A", "E"}:
            vg.remove([0, 1, 2, 3])
    run(ob, bpy.ops.l0c_vgu.sort, method='EMPTY_LAST', scope='ALL')
    check("empty last", names(ob), ["C", "B", "D", "A", "E"])

    addon_prefs = prefs_module.get_prefs(bpy.context)
    dictionary = addon_prefs.dictionaries.add()
    dictionary.name = "_vgu_test_dict"
    dictionary.set_entries(["E", "D", "?"])
    try:
        run(ob, bpy.ops.l0c_vgu.sort_dictionary, dictionary_name="_vgu_test_dict", scope='ALL')
        check("dictionary op", names(ob), ["E", "D", "C", "B", "A"])
    finally:
        addon_prefs.dictionaries.remove(addon_prefs.dictionaries.find("_vgu_test_dict"))


def test_batch_ops():
    ob = make_mesh("_vgu_batch", ["Arm.L", "Arm.R", "Leg.L", "Body"])
    select(ob, ["Arm.L", "Arm.R"])
    run(ob, bpy.ops.l0c_vgu.rename, mode='FLIP')
    check("flip names", names(ob), ["Arm.R", "Arm.L", "Leg.L", "Body"])
    check("flip selection", selected(ob), ["Arm.R", "Arm.L"])
    check("flip weight", round(ob.vertex_groups["Arm.R"].weight(0), 3), 0.01)

    select(ob, ["Leg.L"])
    # bpy.ops はエラー報告を RuntimeError として送出する
    try:
        run(ob, bpy.ops.l0c_vgu.rename, mode='REPLACE', find="Leg", replace="Arm")
        failures.append("rename conflict: should fail")
    except RuntimeError as e:
        check("rename conflict", "重複" in str(e), True)
    check("rename conflict names", names(ob), ["Arm.R", "Arm.L", "Leg.L", "Body"])

    select(ob, ["Leg.L", "Body"])
    run(ob, bpy.ops.l0c_vgu.set_lock, action='LOCK')
    check("lock", [vg.lock_weight for vg in ob.vertex_groups], [False, False, True, True])
    run(ob, bpy.ops.l0c_vgu.set_lock, action='INVERT')
    check("lock invert", [vg.lock_weight for vg in ob.vertex_groups], [False, False, False, False])

    run(ob, bpy.ops.l0c_vgu.delete_selected)
    check("delete", names(ob), ["Arm.R", "Arm.L"])

    bpy.context.view_layer.objects.active = ob
    bpy.ops.object.mode_set(mode='EDIT')
    try:
        bpy.ops.mesh.select_all(action='SELECT')
        select(ob, ["Arm.R", "Arm.L"])
        run(ob, bpy.ops.l0c_vgu.vertex_assign, action='ASSIGN')
        order.apply_order(bpy.context, ob, ["Arm.L", "Arm.R"])
    finally:
        bpy.ops.object.mode_set(mode='OBJECT')
    check("edit mode order", names(ob), ["Arm.L", "Arm.R"])
    check("assign", [round(ob.vertex_groups["Arm.L"].weight(i), 3) for i in range(4)],
          [round(bpy.context.scene.tool_settings.vertex_group_weight, 3)] * 4)


def test_sides():
    check("side names", [sides.side_of(n) for n in ["Arm.L", "arm_r", "Hair.l.001", "Leg_R", "Body", "L", "ArmL", "Arm-L"]],
          ["L", "R", "L", "R", None, None, None, None])
    check("opposite names", [sides.opposite_name(n) for n in ["Arm.L", "arm_r", "Hair.l.001", "Body"]],
          ["Arm.R", "arm_l", "Hair.r.001", None])

    ob = make_mesh("_vgu_sides", ["Arm.L", "Arm.R", "leg_l", "Body", "Hand_R"])
    select(ob, ["Body"])
    run(ob, bpy.ops.l0c_vgu.select_side, side='L')
    check("select L", selected(ob), ["Arm.L", "leg_l"])
    run(ob, bpy.ops.l0c_vgu.select_side, side='R', extend=True)
    check("extend R", selected(ob), ["Arm.L", "Arm.R", "leg_l", "Hand_R"])


def test_create_opposite():
    me = bpy.data.meshes.new("_vgu_mirror")
    me.from_pydata([(-1, 0, 0), (1, 0, 0), (0, 1, 0)], [], [(0, 1, 2)])
    ob = bpy.data.objects.new("_vgu_mirror", me)
    bpy.context.scene.collection.objects.link(ob)
    created.append(ob)
    for n in ["Arm.L", "Arm.R", "leg_l", "Body", "Hand_R"]:
        ob.vertex_groups.new(name=n)
    ob.vertex_groups["leg_l"].add([1], 0.7, 'REPLACE')
    ob.vertex_groups["Hand_R"].add([0], 0.4, 'REPLACE')
    ob.vertex_groups.active_index = 3
    state.sync(ob)

    select(ob, ["Arm.L", "leg_l", "Body", "Hand_R"])
    try:
        run(ob, bpy.ops.l0c_vgu.create_opposite, weight_mode='MIRROR')
    except RuntimeError as e:
        # スキップを WARNING で報告するので、ERROR 以外は例外にならない
        failures.append(f"create opposite: {e}")
    check("opposite order", names(ob), ["Arm.L", "Arm.R", "leg_l", "leg_r", "Body", "Hand_R", "Hand_L"])
    check("opposite active", ob.vertex_groups.active.name, "Body")
    check("opposite mirrored", round(ob.vertex_groups["leg_r"].weight(0), 3), 0.7)
    check("opposite mirrored 2", round(ob.vertex_groups["Hand_L"].weight(1), 3), 0.4)
    check("opposite source kept", round(ob.vertex_groups["leg_l"].weight(1), 3), 0.7)

    select(ob, ["Body", "Arm.L"])
    ob.vertex_groups.remove(ob.vertex_groups["Arm.R"])
    run(ob, bpy.ops.l0c_vgu.create_opposite, weight_mode='EMPTY')
    check("opposite empty", names(ob)[:2], ["Arm.L", "Arm.R"])


def test_copy():
    src = make_mesh("_vgu_src", ["A", "B", "C"])
    dst = make_mesh("_vgu_dst", ["C", "X", "A"], offset=(0.0, 0.0, 0.0))
    far = make_mesh("_vgu_far", [], offset=(10.0, 0.0, 0.0))
    select(src, ["A", "C"])
    run(src, bpy.ops.l0c_vgu.copy_to_selected, selected_objects=[src, dst],
        mapping='INDEX', conflict='REPLACE', match_order=True)
    check("copy order", names(dst), ["A", "X", "C"])
    check("copy weight", round(dst.vertex_groups["C"].weight(2), 3), 0.03)

    run(src, bpy.ops.l0c_vgu.copy_to_selected, selected_objects=[src, far],
        mapping='NEAREST', max_distance=1.0, conflict='REPLACE')
    check("nearest limited", [vg.name for vg in far.vertex_groups], ["A", "C"])
    try:
        far.vertex_groups["A"].weight(0)
        failures.append("nearest limited: vertex 0 should not be assigned")
    except RuntimeError:
        pass


try:
    if bpy.context.object is not None and bpy.context.object.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')
    for test in (test_pure, test_apply_order, test_sync, test_select_ops, test_sort_ops, test_batch_ops,
                 test_sides, test_create_opposite, test_copy):
        try:
            test()
        except Exception as e:
            import traceback
            failures.append(f"{test.__name__}: {type(e).__name__}: {e}\n{traceback.format_exc()}")
finally:
    for ob in created:
        data = ob.data
        bpy.data.objects.remove(ob)
        if data is not None and data.users == 0:
            if isinstance(data, bpy.types.Mesh):
                bpy.data.meshes.remove(data)
            else:
                bpy.data.armatures.remove(data)

print("FAILURES:" if failures else "ALL PASSED")
for f in failures:
    print(" -", f)
