# SPDX-License-Identifier: GPL-2.0-or-later

"""プリファレンスと、並べ替え用の辞書の管理。"""

import csv
import os

import bpy
from bpy.app.translations import pgettext_iface as iface_
from bpy.app.translations import pgettext_rpt as rpt_
from bpy.props import BoolProperty, CollectionProperty, IntProperty, StringProperty
from bpy_extras.io_utils import ExportHelper, ImportHelper

ENTRY_SEP = "\n"


def get_prefs(context):
    addon = context.preferences.addons.get(__package__)
    return addon.preferences if addon is not None else None


def read_dictionary_csv(path):
    """CSV の1列目を辞書の行として読む。空行と # で始まる行は読み飛ばす。"""
    entries = []
    with open(path, encoding="utf-8-sig", newline="") as f:
        for row in csv.reader(f):
            if not row:
                continue
            cell = row[0].replace("\r", "").replace("\n", "").strip()
            if not cell or cell.startswith("#"):
                continue
            entries.append(cell)
    return entries


def _redraw_all(context):
    for window in context.window_manager.windows:
        for area in window.screen.areas:
            area.tag_redraw()


def _on_replace_panel_update(_self, context):
    _redraw_all(context)


class L0C_VGU_Dictionary(bpy.types.PropertyGroup):
    source_path: StringProperty(name="Source File", subtype='FILE_PATH')
    entries: StringProperty()

    def get_entries(self):
        return self.entries.split(ENTRY_SEP) if self.entries else []

    def set_entries(self, entries):
        self.entries = ENTRY_SEP.join(entries)


class L0C_VGU_UL_dictionaries(bpy.types.UIList):
    def draw_item(self, _context, layout, _data, item, _icon, _active_data, _active_propname, _index):
        row = layout.row()
        row.prop(item, "name", text="", emboss=False, icon='SORTALPHA')
        row.label(text=iface_("{count} lines").format(count=len(item.get_entries())), translate=False)


class L0C_VGU_Preferences(bpy.types.AddonPreferences):
    bl_idname = __package__

    replace_panel: BoolProperty(
        name="Replace Default Vertex Group Panel",
        description="Turn this off to restore the default panel",
        default=True,
        update=_on_replace_panel_update,
    )
    dictionaries: CollectionProperty(type=L0C_VGU_Dictionary)
    active_dictionary_index: IntProperty()

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "replace_panel")

        layout.separator()
        layout.label(text="Sorting Dictionaries")
        row = layout.row()
        row.template_list(
            "L0C_VGU_UL_dictionaries", "", self, "dictionaries",
            self, "active_dictionary_index", rows=4,
        )
        col = row.column(align=True)
        col.operator("l0c_vgu.dictionary_import", icon='ADD', text="")
        col.operator("l0c_vgu.dictionary_remove", icon='REMOVE', text="")
        col.separator()
        col.operator("l0c_vgu.dictionary_reload", icon='FILE_REFRESH', text="")
        col.operator("l0c_vgu.dictionary_export", icon='EXPORT', text="")

        dictionary = self.active_dictionary()
        if dictionary is not None:
            box = layout.box()
            box.prop(dictionary, "source_path")
            entries = dictionary.get_entries()
            col = box.column(align=True)
            for entry in entries[:10]:
                # 辞書の行はユーザーデータなので翻訳しない
                col.label(text=entry, translate=False)
            if len(entries) > 10:
                col.label(text=iface_("and {count} more lines").format(count=len(entries) - 10), translate=False)

    def active_dictionary(self):
        if 0 <= self.active_dictionary_index < len(self.dictionaries):
            return self.dictionaries[self.active_dictionary_index]
        return None


def _unique_dictionary_name(prefs, base):
    names = {d.name for d in prefs.dictionaries}
    if base not in names:
        return base
    i = 1
    while f"{base}.{i:03d}" in names:
        i += 1
    return f"{base}.{i:03d}"


class L0C_VGU_OT_dictionary_import(bpy.types.Operator, ImportHelper):
    bl_idname = "l0c_vgu.dictionary_import"
    bl_label = "Import Dictionary"
    bl_description = "Import a CSV file and register it as a sorting dictionary"

    filename_ext = ".csv"
    filter_glob: StringProperty(default="*.csv;*.txt", options={'HIDDEN'})

    def execute(self, context):
        prefs = get_prefs(context)
        try:
            entries = read_dictionary_csv(self.filepath)
        except (OSError, UnicodeDecodeError, csv.Error) as e:
            self.report({'ERROR'}, rpt_("Could not read the dictionary: {error}").format(error=e))
            return {'CANCELLED'}
        if not entries:
            self.report({'ERROR'}, rpt_("The dictionary has no valid lines."))
            return {'CANCELLED'}

        dictionary = prefs.dictionaries.add()
        base = os.path.splitext(os.path.basename(self.filepath))[0]
        dictionary.name = _unique_dictionary_name(prefs, base)
        dictionary.source_path = self.filepath
        dictionary.set_entries(entries)
        prefs.active_dictionary_index = len(prefs.dictionaries) - 1
        context.preferences.is_dirty = True
        self.report({'INFO'}, rpt_("Registered dictionary \"{name}\" with {count} lines.").format(
            name=dictionary.name, count=len(entries),
        ))
        return {'FINISHED'}


class L0C_VGU_OT_dictionary_reload(bpy.types.Operator):
    bl_idname = "l0c_vgu.dictionary_reload"
    bl_label = "Reload Dictionary"
    bl_description = "Reload the dictionary from its source CSV file"

    @classmethod
    def poll(cls, context):
        prefs = get_prefs(context)
        return prefs is not None and prefs.active_dictionary() is not None

    def execute(self, context):
        prefs = get_prefs(context)
        dictionary = prefs.active_dictionary()
        path = bpy.path.abspath(dictionary.source_path)
        try:
            entries = read_dictionary_csv(path)
        except (OSError, UnicodeDecodeError, csv.Error) as e:
            self.report({'ERROR'}, rpt_("Could not read the dictionary: {error}").format(error=e))
            return {'CANCELLED'}
        if not entries:
            self.report({'ERROR'}, rpt_("The dictionary has no valid lines."))
            return {'CANCELLED'}
        dictionary.set_entries(entries)
        context.preferences.is_dirty = True
        self.report({'INFO'}, rpt_("Reloaded dictionary \"{name}\" with {count} lines.").format(
            name=dictionary.name, count=len(entries),
        ))
        return {'FINISHED'}


class L0C_VGU_OT_dictionary_remove(bpy.types.Operator):
    bl_idname = "l0c_vgu.dictionary_remove"
    bl_label = "Remove Dictionary"
    bl_description = "Remove the active dictionary from the list. The CSV file is not deleted"

    @classmethod
    def poll(cls, context):
        prefs = get_prefs(context)
        return prefs is not None and prefs.active_dictionary() is not None

    def execute(self, context):
        prefs = get_prefs(context)
        prefs.dictionaries.remove(prefs.active_dictionary_index)
        prefs.active_dictionary_index = min(prefs.active_dictionary_index, len(prefs.dictionaries) - 1)
        context.preferences.is_dirty = True
        return {'FINISHED'}


class L0C_VGU_OT_dictionary_export(bpy.types.Operator, ExportHelper):
    bl_idname = "l0c_vgu.dictionary_export"
    bl_label = "Export Dictionary"
    bl_description = "Export the active dictionary to a CSV file"

    filename_ext = ".csv"
    filter_glob: StringProperty(default="*.csv", options={'HIDDEN'})

    @classmethod
    def poll(cls, context):
        prefs = get_prefs(context)
        return prefs is not None and prefs.active_dictionary() is not None

    def execute(self, context):
        dictionary = get_prefs(context).active_dictionary()
        try:
            with open(self.filepath, "w", encoding="utf-8", newline="") as f:
                writer = csv.writer(f)
                for entry in dictionary.get_entries():
                    writer.writerow([entry])
        except OSError as e:
            self.report({'ERROR'}, rpt_("Could not write the dictionary: {error}").format(error=e))
            return {'CANCELLED'}
        self.report({'INFO'}, rpt_("Exported dictionary \"{name}\".").format(name=dictionary.name))
        return {'FINISHED'}


classes = (
    L0C_VGU_Dictionary,
    L0C_VGU_UL_dictionaries,
    L0C_VGU_Preferences,
    L0C_VGU_OT_dictionary_import,
    L0C_VGU_OT_dictionary_reload,
    L0C_VGU_OT_dictionary_remove,
    L0C_VGU_OT_dictionary_export,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
