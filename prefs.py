# SPDX-License-Identifier: GPL-2.0-or-later

"""プリファレンスと、並べ替え用の辞書の管理。"""

import csv
import os

import bpy
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
    source_path: StringProperty(name="読み込み元", subtype='FILE_PATH')
    entries: StringProperty()

    def get_entries(self):
        return self.entries.split(ENTRY_SEP) if self.entries else []

    def set_entries(self, entries):
        self.entries = ENTRY_SEP.join(entries)


class L0C_VGU_UL_dictionaries(bpy.types.UIList):
    def draw_item(self, _context, layout, _data, item, _icon, _active_data, _active_propname, _index):
        row = layout.row()
        row.prop(item, "name", text="", emboss=False, icon='SORTALPHA')
        row.label(text=f"{len(item.get_entries())} 行")


class L0C_VGU_Preferences(bpy.types.AddonPreferences):
    bl_idname = __package__

    replace_panel: BoolProperty(
        name="標準の頂点グループパネルを置き換える",
        description="オフにすると標準のパネル表示に戻します",
        default=True,
        update=_on_replace_panel_update,
    )
    dictionaries: CollectionProperty(type=L0C_VGU_Dictionary)
    active_dictionary_index: IntProperty()

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "replace_panel")

        layout.separator()
        layout.label(text="並べ替え用の辞書")
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
                col.label(text=entry)
            if len(entries) > 10:
                col.label(text=f"ほか {len(entries) - 10} 行")

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
    bl_label = "辞書を読み込む"
    bl_description = "CSV を読み込んで並べ替え用の辞書として登録します"

    filename_ext = ".csv"
    filter_glob: StringProperty(default="*.csv;*.txt", options={'HIDDEN'})

    def execute(self, context):
        prefs = get_prefs(context)
        try:
            entries = read_dictionary_csv(self.filepath)
        except (OSError, UnicodeDecodeError, csv.Error) as e:
            self.report({'ERROR'}, f"辞書を読み込めませんでした: {e}")
            return {'CANCELLED'}
        if not entries:
            self.report({'ERROR'}, "辞書に有効な行がありません。")
            return {'CANCELLED'}

        dictionary = prefs.dictionaries.add()
        base = os.path.splitext(os.path.basename(self.filepath))[0]
        dictionary.name = _unique_dictionary_name(prefs, base)
        dictionary.source_path = self.filepath
        dictionary.set_entries(entries)
        prefs.active_dictionary_index = len(prefs.dictionaries) - 1
        context.preferences.is_dirty = True
        self.report({'INFO'}, f"辞書「{dictionary.name}」を {len(entries)} 行で登録しました。")
        return {'FINISHED'}


class L0C_VGU_OT_dictionary_reload(bpy.types.Operator):
    bl_idname = "l0c_vgu.dictionary_reload"
    bl_label = "辞書を再読み込み"
    bl_description = "読み込み元の CSV から辞書を読み直します"

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
            self.report({'ERROR'}, f"辞書を読み込めませんでした: {e}")
            return {'CANCELLED'}
        if not entries:
            self.report({'ERROR'}, "辞書に有効な行がありません。")
            return {'CANCELLED'}
        dictionary.set_entries(entries)
        context.preferences.is_dirty = True
        self.report({'INFO'}, f"辞書「{dictionary.name}」を {len(entries)} 行で読み直しました。")
        return {'FINISHED'}


class L0C_VGU_OT_dictionary_remove(bpy.types.Operator):
    bl_idname = "l0c_vgu.dictionary_remove"
    bl_label = "辞書を削除"
    bl_description = "選択中の辞書を登録から外します。CSV ファイルは削除しません"

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
    bl_label = "辞書を書き出す"
    bl_description = "選択中の辞書を CSV に書き出します"

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
            self.report({'ERROR'}, f"辞書を書き出せませんでした: {e}")
            return {'CANCELLED'}
        self.report({'INFO'}, f"辞書「{dictionary.name}」を書き出しました。")
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
