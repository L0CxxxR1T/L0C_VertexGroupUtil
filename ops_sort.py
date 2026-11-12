# SPDX-License-Identifier: GPL-2.0-or-later

"""選択中のグループの移動と並べ替え。"""

import bpy
from bpy.app.translations import pgettext_rpt as rpt_
from bpy.app.translations import pgettext_tip as tip_
from bpy.props import BoolProperty, EnumProperty, IntProperty, StringProperty

from . import order, prefs, state

SCOPE_ITEMS = (
    ('SELECTED', "Selected Only", "Sort only within the positions the selected groups occupy"),
    ('ALL', "All", "Sort all groups"),
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
            op.report({'ERROR'}, rpt_("No groups are selected."))
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
    bl_label = "Move Selected Groups"
    bl_options = {'REGISTER', 'UNDO'}

    direction: EnumProperty(
        name="Direction",
        items=(
            ('TOP', "To Top", ""),
            ('UP', "Up", ""),
            ('DOWN', "Down", ""),
            ('BOTTOM', "To Bottom", ""),
        ),
    )

    @classmethod
    def description(cls, _context, properties):
        return tip_({
            'TOP': "Move the selected groups to the top",
            'UP': "Move the selected groups up by one",
            'DOWN': "Move the selected groups down by one",
            'BOTTOM': "Move the selected groups to the bottom",
        }[properties.direction])

    def execute(self, context):
        ob = state.mesh_object(context)
        selected = set(state.selected_names(ob))
        if not selected:
            self.report({'ERROR'}, rpt_("No groups are selected."))
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
    bl_label = "Move to Position"
    bl_description = "Move the selected groups to the given position, keeping their relative order"
    bl_options = {'REGISTER', 'UNDO'}

    position: IntProperty(
        name="Position",
        description="Position of the first moved group. 1 is the top",
        default=1,
        min=1,
    )

    def invoke(self, context, _event):
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        ob = state.mesh_object(context)
        selected = set(state.selected_names(ob))
        if not selected:
            self.report({'ERROR'}, rpt_("No groups are selected."))
            return {'CANCELLED'}
        names = [vg.name for vg in ob.vertex_groups]
        return _apply(self, context, ob, order.move_to(names, selected, self.position - 1))


class L0C_VGU_OT_sort(_SelectedMeshPoll, bpy.types.Operator):
    bl_idname = "l0c_vgu.sort"
    bl_label = "Sort Vertex Groups"
    bl_options = {'REGISTER', 'UNDO'}

    method: EnumProperty(
        name="Method",
        items=(
            ('BONE', "By Bone", "Match the order of the armature's bones"),
            ('REVERSE', "Reverse", "Reverse the order"),
            ('EMPTY_LAST', "Empty Groups Last", "Move groups with no assigned weights to the end"),
        ),
    )
    scope: EnumProperty(name="Scope", items=SCOPE_ITEMS)
    zero_as_empty: BoolProperty(
        name="Treat Zero Weights as Empty",
        description="Also treat groups that only have zero weights as empty",
        default=False,
    )

    @classmethod
    def description(cls, _context, properties):
        method = {
            'BONE': "Match the order of the armature's bones. Groups without a bone go to the end",
            'REVERSE': "Reverse the order",
            'EMPTY_LAST': "Move groups with no assigned weights to the end",
        }[properties.method]
        scope = "Applies to the selected groups" if properties.scope == 'SELECTED' else "Applies to all groups"
        return tip_("{method}. {scope}").format(method=tip_(method), scope=tip_(scope))

    def execute(self, context):
        ob = state.mesh_object(context)

        if self.method == 'BONE':
            armature = order.find_armature(ob)
            if armature is None:
                self.report({'ERROR'}, rpt_("No Armature modifier target or parent armature was found."))
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
    bl_label = "Sort by Dictionary"
    bl_description = (
        "Sort by the line order of a dictionary registered in the Preferences. "
        "Groups not in the dictionary go to the end"
    )
    bl_options = {'REGISTER', 'UNDO'}

    dictionary_name: StringProperty(name="Dictionary")
    scope: EnumProperty(name="Scope", items=SCOPE_ITEMS)

    def execute(self, context):
        ob = state.mesh_object(context)
        addon_prefs = prefs.get_prefs(context)
        dictionary = addon_prefs.dictionaries.get(self.dictionary_name) if addon_prefs else None
        if dictionary is None:
            self.report({'ERROR'}, rpt_("Dictionary \"{name}\" is not registered.").format(name=self.dictionary_name))
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
