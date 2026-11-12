# SPDX-License-Identifier: GPL-2.0-or-later

"""チェックボックスの選択操作。"""

import bpy
from bpy.app.translations import pgettext_rpt as rpt_
from bpy.app.translations import pgettext_tip as tip_
from bpy.props import BoolProperty, EnumProperty, StringProperty

from . import sides, state


class L0C_VGU_OT_select_all(bpy.types.Operator):
    bl_idname = "l0c_vgu.select_all"
    bl_label = "Select Vertex Groups"
    bl_description = "Change the checks of the vertex groups at once"
    bl_options = {'REGISTER', 'UNDO'}

    action: EnumProperty(
        name="Action",
        items=(
            ('SELECT', "Select All", "Check all groups"),
            ('DESELECT', "Deselect All", "Uncheck all groups"),
            ('INVERT', "Invert", "Invert the checks"),
        ),
    )

    @classmethod
    def description(cls, _context, properties):
        return tip_({
            'SELECT': "Check all groups",
            'DESELECT': "Uncheck all groups",
            'INVERT': "Invert the checks",
        }[properties.action])

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
    bl_label = "Select Range"
    bl_description = (
        "Set the groups from the active group to the last toggled group "
        "to the same check state as the last toggled group"
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
            self.report({'ERROR'}, rpt_("The start group was not found. Toggle a checkbox first, then run this again."))
            return {'CANCELLED'}

        value = ob.l0c_vgu.items[anchor.name].selected
        start, end = sorted((vgroups.active_index, anchor.index))
        state.set_selected(ob, [vgroups[i].name for i in range(start, end + 1)], value)
        return {'FINISHED'}


class L0C_VGU_OT_select_side(bpy.types.Operator):
    bl_idname = "l0c_vgu.select_side"
    bl_label = "Select by L/R"
    bl_options = {'REGISTER', 'UNDO'}

    side: EnumProperty(
        name="Side",
        items=(
            ('L', "L", ""),
            ('R', "R", ""),
        ),
    )
    extend: BoolProperty(
        name="Extend",
        description="Add to the current selection instead of replacing it",
        default=False,
    )

    @classmethod
    def description(cls, _context, properties):
        return tip_(
            "Select groups whose names end with .{side}, _{side_lower} and so on. "
            "Shift-click to add to the current selection"
        ).format(side=properties.side, side_lower=properties.side.lower())

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
            self.report({'INFO'}, rpt_("No groups found on the {side} side.").format(side=self.side))
        return {'FINISHED'}


class L0C_VGU_OT_toggle(bpy.types.Operator):
    """選択状態がまだ同期されていないグループ用のチェックボックス"""

    bl_idname = "l0c_vgu.toggle"
    bl_label = "Toggle Selection"
    bl_description = "Include this group in batch operations and sorting"
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
            self.report({'ERROR'}, rpt_("Vertex group \"{name}\" was not found.").format(name=self.name))
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
