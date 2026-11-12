# SPDX-License-Identifier: GPL-2.0-or-later

"""頂点グループパネルの描画と、標準パネルの差し替え。"""

import bpy
from bl_ui.properties_data_mesh import draw_attribute_warnings
from bpy.app.translations import pgettext_iface as iface_
from bpy.props import BoolProperty

from . import prefs, state

ORIGINAL_DRAW_QUALNAME = "DATA_PT_vertex_groups.draw"

_original_draw = None


class L0C_VGU_UL_vgroups(bpy.types.UIList):
    show_selected_only: BoolProperty(
        name="Show Selected Only",
        description="Show only checked groups",
        default=False,
    )

    def draw_item(self, _context, layout, data, item, icon, _active_data, _active_propname, _index):
        group_state = data.l0c_vgu.items.get(item.name)
        if group_state is not None:
            layout.prop(group_state, "selected", text="")
        else:
            # 追加直後で同期が済んでいないグループ。描画中はデータを書けないのでオペレーターで扱う
            op = layout.operator("l0c_vgu.toggle", text="", icon='CHECKBOX_DEHLT', emboss=False)
            op.name = item.name
        layout.prop(item, "name", text="", emboss=False, icon_value=icon)
        lock_icon = 'LOCKED' if item.lock_weight else 'UNLOCKED'
        layout.prop(item, "lock_weight", text="", icon=lock_icon, emboss=False)

    def draw_filter(self, _context, layout):
        row = layout.row(align=True)
        row.prop(self, "filter_name", text="")
        row.prop(self, "use_filter_invert", text="", icon='ARROW_LEFTRIGHT')
        row.prop(self, "show_selected_only", text="", icon='CHECKBOX_HLT')

    def filter_items(self, _context, data, propname):
        vgroups = getattr(data, propname)
        flags = bpy.types.UI_UL_list.filter_items_by_name(
            self.filter_name, self.bitflag_filter_item, vgroups, "name",
        )
        if not flags:
            flags = [self.bitflag_filter_item] * len(vgroups)
        if self.show_selected_only:
            items = data.l0c_vgu.items
            for i, vg in enumerate(vgroups):
                group_state = items.get(vg.name)
                if group_state is None or not group_state.selected:
                    flags[i] &= ~self.bitflag_filter_item
        return flags, []


class L0C_VGU_MT_dictionary_selected(bpy.types.Menu):
    bl_label = "By Dictionary (Selected Only)"

    def draw(self, context):
        _draw_dictionary_items(self.layout, context, 'SELECTED')


class L0C_VGU_MT_dictionary_all(bpy.types.Menu):
    bl_label = "By Dictionary (All)"

    def draw(self, context):
        _draw_dictionary_items(self.layout, context, 'ALL')


def _draw_dictionary_items(layout, context, scope):
    addon_prefs = prefs.get_prefs(context)
    if addon_prefs is None or not addon_prefs.dictionaries:
        layout.label(text="No dictionaries are registered. Register one in the Preferences.")
        return
    for dictionary in addon_prefs.dictionaries:
        # 辞書名はユーザーが付けた名前なので翻訳しない
        op = layout.operator("l0c_vgu.sort_dictionary", text=dictionary.name, translate=False)
        op.dictionary_name = dictionary.name
        op.scope = scope


class L0C_VGU_MT_sort(bpy.types.Menu):
    bl_label = "Sort"

    def draw(self, _context):
        layout = self.layout
        layout.operator("l0c_vgu.move_selected_to", text="Move Selected to Position...")

        for scope, label, dictionary_menu in (
            ('SELECTED', "Selected Only", "L0C_VGU_MT_dictionary_selected"),
            ('ALL', "All", "L0C_VGU_MT_dictionary_all"),
        ):
            layout.separator()
            layout.label(text=label)
            for method, text in (
                ('BONE', "By Bone"),
                ('REVERSE', "Reverse"),
                ('EMPTY_LAST', "Empty Groups Last"),
            ):
                op = layout.operator("l0c_vgu.sort", text=text)
                op.method = method
                op.scope = scope
            layout.menu(dictionary_menu, text="By Dictionary")

        layout.separator()
        layout.operator("object.vertex_group_sort", text="By Bone Hierarchy (All)").sort_type = 'BONE_HIERARCHY'


class L0C_VGU_MT_batch(bpy.types.Menu):
    bl_label = "Batch Operations"

    def draw(self, _context):
        layout = self.layout
        layout.operator("l0c_vgu.rename", text="Rename...", icon='SORTALPHA')
        layout.operator("l0c_vgu.create_opposite", text="Create Opposite Groups...", icon='MOD_MIRROR')
        layout.operator("l0c_vgu.copy_to_selected", text="Copy to Other Objects...", icon='COPYDOWN')
        layout.separator()
        layout.operator("l0c_vgu.set_lock", text="Lock", icon='LOCKED').action = 'LOCK'
        layout.operator("l0c_vgu.set_lock", text="Unlock", icon='UNLOCKED').action = 'UNLOCK'
        layout.operator("l0c_vgu.set_lock", text="Invert Lock", icon='ARROW_LEFTRIGHT').action = 'INVERT'
        layout.separator()
        layout.operator("l0c_vgu.delete_selected", text="Delete", icon='X')


def draw_panel(panel, context):
    layout = panel.layout
    ob = context.object
    vgroups = ob.vertex_groups
    group = vgroups.active

    row = layout.row()
    row.template_list(
        "L0C_VGU_UL_vgroups", "", ob, "vertex_groups", vgroups, "active_index",
        rows=7 if group else 3,
    )

    col = row.column(align=True)
    col.operator("object.vertex_group_add", icon='ADD', text="")
    props = col.operator("object.vertex_group_remove", icon='REMOVE', text="")
    props.all_unlocked = props.all = False
    col.separator()
    col.menu("MESH_MT_vertex_group_context_menu", icon='DOWNARROW_HLT', text="")
    if group:
        col.separator()
        col.operator("object.vertex_group_move", icon='TRIA_UP', text="").direction = 'UP'
        col.operator("object.vertex_group_move", icon='TRIA_DOWN', text="").direction = 'DOWN'

    selected_count = state.count_selected(ob) if vgroups else 0
    if vgroups:
        _draw_selection_tools(layout, ob, selected_count)

    show_assign = ob.mode == 'EDIT' or (ob.mode == 'WEIGHT_PAINT' and ob.data.use_paint_mask_vertex)
    if vgroups and show_assign:
        row = layout.row()
        sub = row.row(align=True)
        sub.operator("object.vertex_group_assign", text="Assign")
        sub.operator("object.vertex_group_remove_from", text="Remove")
        sub = row.row(align=True)
        sub.operator("object.vertex_group_select", text="Select")
        sub.operator("object.vertex_group_deselect", text="Deselect")

        if selected_count:
            col = layout.column(align=True)
            col.label(text=iface_("{count} Selected Groups").format(count=selected_count), translate=False)
            row = col.row()
            sub = row.row(align=True)
            sub.operator("l0c_vgu.vertex_assign", text="Assign").action = 'ASSIGN'
            sub.operator("l0c_vgu.vertex_assign", text="Remove").action = 'REMOVE'
            sub = row.row(align=True)
            sub.operator("l0c_vgu.vertex_assign", text="Select").action = 'SELECT'
            sub.operator("l0c_vgu.vertex_assign", text="Deselect").action = 'DESELECT'

        col = layout.column(align=True)
        col.separator()
        col.use_property_split = True
        col.use_property_decorate = False
        col.prop(context.tool_settings, "vertex_group_weight", text="Weight")
        col.prop(context.tool_settings, "use_auto_normalize", text="Auto Normalize")

    draw_attribute_warnings(context, layout, None)


def _draw_selection_tools(layout, ob, selected_count):
    row = layout.row()
    sub = row.row(align=True)
    sub.operator("l0c_vgu.select_all", text="", icon='CHECKBOX_HLT').action = 'SELECT'
    sub.operator("l0c_vgu.select_all", text="", icon='CHECKBOX_DEHLT').action = 'DESELECT'
    sub.operator("l0c_vgu.select_all", text="Invert").action = 'INVERT'
    sub.operator("l0c_vgu.select_range", text="Range")
    sub = row.row(align=True)
    sub.operator("l0c_vgu.select_side", text="L", translate=False).side = 'L'
    sub.operator("l0c_vgu.select_side", text="R", translate=False).side = 'R'
    sub = row.row()
    sub.alignment = 'RIGHT'
    sub.label(text=f"{selected_count} / {len(ob.vertex_groups)}", translate=False)

    row = layout.row()
    sub = row.row(align=True)
    sub.enabled = selected_count > 0
    sub.operator("l0c_vgu.move_selected", text="", icon='TRIA_UP_BAR').direction = 'TOP'
    sub.operator("l0c_vgu.move_selected", text="", icon='TRIA_UP').direction = 'UP'
    sub.operator("l0c_vgu.move_selected", text="", icon='TRIA_DOWN').direction = 'DOWN'
    sub.operator("l0c_vgu.move_selected", text="", icon='TRIA_DOWN_BAR').direction = 'BOTTOM'
    row.menu("L0C_VGU_MT_sort", icon='SORTSIZE')
    sub = row.row()
    sub.enabled = selected_count > 0
    sub.menu("L0C_VGU_MT_batch", icon='MODIFIER')


def _draw_override(panel, context):
    ob = context.object
    addon_prefs = prefs.get_prefs(context)
    enabled = addon_prefs is None or addon_prefs.replace_panel
    if enabled and ob is not None and ob.type == 'MESH':
        draw_panel(panel, context)
    else:
        _original_draw(panel, context)


def _install_override():
    """標準パネルの描画関数リストの先頭(元の draw)だけを入れ替え、ほかのアドオンの追加分は残す。"""
    global _original_draw
    draw_funcs = bpy.types.DATA_PT_vertex_groups._dyn_ui_initialize()
    for i, func in enumerate(draw_funcs):
        if getattr(func, "__qualname__", "") == ORIGINAL_DRAW_QUALNAME:
            _original_draw = func
            draw_funcs[i] = _draw_override
            return
    raise RuntimeError("Could not find the draw function of the default vertex group panel.")


def _uninstall_override():
    global _original_draw
    if _original_draw is None:
        return
    draw_funcs = bpy.types.DATA_PT_vertex_groups._dyn_ui_initialize()
    for i, func in enumerate(draw_funcs):
        if func is _draw_override:
            draw_funcs[i] = _original_draw
    _original_draw = None


classes = (
    L0C_VGU_UL_vgroups,
    L0C_VGU_MT_dictionary_selected,
    L0C_VGU_MT_dictionary_all,
    L0C_VGU_MT_sort,
    L0C_VGU_MT_batch,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    _install_override()


def unregister():
    _uninstall_override()
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
