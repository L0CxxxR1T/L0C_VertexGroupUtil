# SPDX-License-Identifier: GPL-2.0-or-later

"""選択中のグループの移動と並べ替え。"""

import bpy
from bpy.props import BoolProperty, EnumProperty, IntProperty, StringProperty

from . import order, prefs, state

SCOPE_ITEMS = (
    ('SELECTED', "選択中のみ", "選択中のグループが今いる位置の中だけで並べ替えます"),
    ('ALL', "全体", "すべてのグループを並べ替えます"),
)


def _apply(op, context, ob, desired):
    try:
        order.apply_order(context, ob, desired)
    except (ValueError, RuntimeError) as e:
        op.report({'ERROR'}, str(e))
        return {'CANCELLED'}
    return {'FINISHED'}


def _reorder_in_scope(op, context, ob, scope, reorder):
    names = [vg.name for vg in ob.vertex_groups]
    if scope == 'SELECTED':
        selected = set(state.selected_names(ob))
        if not selected:
            op.report({'ERROR'}, "グループが選択されていません。")
            return {'CANCELLED'}
        desired = order.reorder_slots(names, selected, reorder)
    else:
        desired = reorder(names)
    return _apply(op, context, ob, desired)


class _SelectedMeshPoll:
    @classmethod
    def poll(cls, context):
        ob = state.mesh_object(context)
        return ob is not None and len(ob.vertex_groups) > 0


class L0C_VGU_OT_move_selected(_SelectedMeshPoll, bpy.types.Operator):
    bl_idname = "l0c_vgu.move_selected"
    bl_label = "選択中のグループを移動"
    bl_options = {'REGISTER', 'UNDO'}

    direction: EnumProperty(
        name="方向",
        items=(
            ('TOP', "先頭へ", ""),
            ('UP', "上へ", ""),
            ('DOWN', "下へ", ""),
            ('BOTTOM', "末尾へ", ""),
        ),
    )

    @classmethod
    def description(cls, _context, properties):
        return {
            'TOP': "選択中のグループを先頭へ移動します",
            'UP': "選択中のグループを1つ上へ移動します",
            'DOWN': "選択中のグループを1つ下へ移動します",
            'BOTTOM': "選択中のグループを末尾へ移動します",
        }[properties.direction]

    def execute(self, context):
        ob = state.mesh_object(context)
        selected = set(state.selected_names(ob))
        if not selected:
            self.report({'ERROR'}, "グループが選択されていません。")
            return {'CANCELLED'}
        names = [vg.name for vg in ob.vertex_groups]
        if self.direction == 'UP':
            desired = order.move_up(names, selected)
        elif self.direction == 'DOWN':
            desired = order.move_down(names, selected)
        elif self.direction == 'TOP':
            desired = order.move_to(names, selected, 0)
        else:
            desired = order.move_to(names, selected, len(names))
        return _apply(self, context, ob, desired)


class L0C_VGU_OT_move_selected_to(_SelectedMeshPoll, bpy.types.Operator):
    bl_idname = "l0c_vgu.move_selected_to"
    bl_label = "指定位置へ移動"
    bl_description = "選択中のグループを、相対順を保ったまま指定した位置へ移動します"
    bl_options = {'REGISTER', 'UNDO'}

    position: IntProperty(
        name="位置",
        description="移動後に先頭のグループが来る位置です。1 が先頭です",
        default=1,
        min=1,
    )

    def invoke(self, context, _event):
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        ob = state.mesh_object(context)
        selected = set(state.selected_names(ob))
        if not selected:
            self.report({'ERROR'}, "グループが選択されていません。")
            return {'CANCELLED'}
        names = [vg.name for vg in ob.vertex_groups]
        return _apply(self, context, ob, order.move_to(names, selected, self.position - 1))


class L0C_VGU_OT_sort(_SelectedMeshPoll, bpy.types.Operator):
    bl_idname = "l0c_vgu.sort"
    bl_label = "頂点グループを並べ替え"
    bl_options = {'REGISTER', 'UNDO'}

    method: EnumProperty(
        name="方法",
        items=(
            ('BONE', "ボーン順", "アーマチュアのボーンの並び順に合わせます"),
            ('REVERSE', "逆順", "並びを反転します"),
            ('EMPTY_LAST', "空グループを末尾へ", "ウェイトが割り当てられていないグループを末尾へ送ります"),
        ),
    )
    scope: EnumProperty(name="対象", items=SCOPE_ITEMS)
    zero_as_empty: BoolProperty(
        name="ウェイト 0 も空とみなす",
        description="ウェイトが 0 の割り当てしかないグループも空グループとして扱います",
        default=False,
    )

    @classmethod
    def description(cls, _context, properties):
        method = {
            'BONE': "アーマチュアのボーンの並び順に合わせます。ボーンがないグループは末尾に置きます",
            'REVERSE': "並びを反転します",
            'EMPTY_LAST': "ウェイトが割り当てられていないグループを末尾へ送ります",
        }[properties.method]
        scope = "選択中のグループが対象です" if properties.scope == 'SELECTED' else "すべてのグループが対象です"
        return f"{method}。{scope}"

    def execute(self, context):
        ob = state.mesh_object(context)

        if self.method == 'BONE':
            armature = order.find_armature(ob)
            if armature is None:
                self.report({'ERROR'}, "Armature モディファイアの対象か、親のアーマチュアが見つかりません。")
                return {'CANCELLED'}
            bone_index = {bone.name: i for i, bone in enumerate(armature.data.bones)}

            def reorder(names):
                return order.sort_by_rank(names, bone_index.get)

        elif self.method == 'REVERSE':
            def reorder(names):
                return list(reversed(names))

        else:
            used = order.used_group_indices(ob, self.zero_as_empty)
            empty = {vg.name for vg in ob.vertex_groups if vg.index not in used}

            def reorder(names):
                return [n for n in names if n not in empty] + [n for n in names if n in empty]

        return _reorder_in_scope(self, context, ob, self.scope, reorder)


class L0C_VGU_OT_sort_dictionary(_SelectedMeshPoll, bpy.types.Operator):
    bl_idname = "l0c_vgu.sort_dictionary"
    bl_label = "辞書順に並べ替え"
    bl_description = "プリファレンスに登録した辞書の行順に並べ替えます。辞書にないグループは末尾に置きます"
    bl_options = {'REGISTER', 'UNDO'}

    dictionary_name: StringProperty(name="辞書")
    scope: EnumProperty(name="対象", items=SCOPE_ITEMS)

    def execute(self, context):
        ob = state.mesh_object(context)
        addon_prefs = prefs.get_prefs(context)
        dictionary = addon_prefs.dictionaries.get(self.dictionary_name) if addon_prefs else None
        if dictionary is None:
            self.report({'ERROR'}, f"辞書「{self.dictionary_name}」が登録されていません。")
            return {'CANCELLED'}
        rank = order.dictionary_rank(dictionary.get_entries())

        def reorder(names):
            return order.sort_by_rank(names, rank)

        return _reorder_in_scope(self, context, ob, self.scope, reorder)


classes = (
    L0C_VGU_OT_move_selected,
    L0C_VGU_OT_move_selected_to,
    L0C_VGU_OT_sort,
    L0C_VGU_OT_sort_dictionary,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
