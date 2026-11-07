# SPDX-License-Identifier: GPL-2.0-or-later

"""チェックボックスの選択操作。"""

import bpy
from bpy.props import BoolProperty, EnumProperty, StringProperty

from . import sides, state


class L0C_VGU_OT_select_all(bpy.types.Operator):
    bl_idname = "l0c_vgu.select_all"
    bl_label = "頂点グループの選択"
    bl_description = "頂点グループのチェックをまとめて切り替えます"
    bl_options = {'REGISTER', 'UNDO'}

    action: EnumProperty(
        name="操作",
        items=(
            ('SELECT', "全選択", "すべてのグループにチェックを入れます"),
            ('DESELECT', "全解除", "すべてのグループのチェックを外します"),
            ('INVERT', "反転", "チェックの有無を反転します"),
        ),
    )

    @classmethod
    def description(cls, _context, properties):
        return {
            'SELECT': "すべてのグループにチェックを入れます",
            'DESELECT': "すべてのグループのチェックを外します",
            'INVERT': "チェックの有無を反転します",
        }[properties.action]

    @classmethod
    def poll(cls, context):
        ob = state.mesh_object(context)
        return ob is not None and len(ob.vertex_groups) > 0

    def execute(self, context):
        ob = state.mesh_object(context)
        names = [vg.name for vg in ob.vertex_groups]
        if self.action == 'INVERT':
            selected = set(state.selected_names(ob))
            state.set_selected(ob, selected, False)
            state.set_selected(ob, [n for n in names if n not in selected], True)
        else:
            state.set_selected(ob, names, self.action == 'SELECT')
        return {'FINISHED'}


class L0C_VGU_OT_select_range(bpy.types.Operator):
    bl_idname = "l0c_vgu.select_range"
    bl_label = "範囲選択"
    bl_description = (
        "アクティブのグループから、最後にチェックを切り替えたグループまでを、"
        "そのグループと同じチェック状態にそろえます"
    )
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        ob = state.mesh_object(context)
        return ob is not None and ob.vertex_groups.active is not None

    def execute(self, context):
        ob = state.mesh_object(context)
        state.sync(ob)
        vgroups = ob.vertex_groups
        anchor = vgroups.get(ob.l0c_vgu.last_toggled)
        if anchor is None:
            self.report({'ERROR'}, "起点のグループが見つかりません。チェックボックスを1つ切り替えてから実行してください。")
            return {'CANCELLED'}

        value = ob.l0c_vgu.items[anchor.name].selected
        start, end = sorted((vgroups.active_index, anchor.index))
        state.set_selected(ob, [vgroups[i].name for i in range(start, end + 1)], value)
        return {'FINISHED'}


class L0C_VGU_OT_select_side(bpy.types.Operator):
    bl_idname = "l0c_vgu.select_side"
    bl_label = "L/R で選択"
    bl_options = {'REGISTER', 'UNDO'}

    side: EnumProperty(
        name="側",
        items=(
            ('L', "L", ""),
            ('R', "R", ""),
        ),
    )
    extend: BoolProperty(
        name="追加選択",
        description="今の選択を残したまま追加します",
        default=False,
    )

    @classmethod
    def description(cls, _context, properties):
        return (
            f"名前が .{properties.side} や _{properties.side.lower()} などで終わるグループを選択します。"
            "Shift+クリックで今の選択に追加します"
        )

    @classmethod
    def poll(cls, context):
        ob = state.mesh_object(context)
        return ob is not None and len(ob.vertex_groups) > 0

    def invoke(self, context, event):
        self.extend = event.shift
        return self.execute(context)

    def execute(self, context):
        ob = state.mesh_object(context)
        names = [vg.name for vg in ob.vertex_groups]
        matched = [n for n in names if sides.side_of(n) == self.side]
        if not self.extend:
            state.set_selected(ob, names, False)
        state.set_selected(ob, matched, True)
        if not matched:
            self.report({'INFO'}, f"{self.side} 側のグループはありませんでした。")
        return {'FINISHED'}


class L0C_VGU_OT_toggle(bpy.types.Operator):
    """選択状態がまだ同期されていないグループ用のチェックボックス"""

    bl_idname = "l0c_vgu.toggle"
    bl_label = "選択を切り替え"
    bl_description = "このグループを一括操作と並べ替えの対象にします"
    bl_options = {'REGISTER', 'UNDO', 'INTERNAL'}

    name: StringProperty()

    @classmethod
    def poll(cls, context):
        return state.mesh_object(context) is not None

    def execute(self, context):
        ob = state.mesh_object(context)
        state.sync(ob)
        item = ob.l0c_vgu.items.get(self.name)
        if item is None:
            self.report({'ERROR'}, f"頂点グループ「{self.name}」が見つかりません。")
            return {'CANCELLED'}
        item.selected = not item.selected
        return {'FINISHED'}


classes = (
    L0C_VGU_OT_select_all,
    L0C_VGU_OT_select_range,
    L0C_VGU_OT_select_side,
    L0C_VGU_OT_toggle,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
