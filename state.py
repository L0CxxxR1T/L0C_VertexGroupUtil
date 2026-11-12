# SPDX-License-Identifier: GPL-2.0-or-later

"""チェックボックスの選択状態を Object に保存し、頂点グループの一覧と同期する。"""

from contextlib import contextmanager

import bpy
from bpy.props import BoolProperty, CollectionProperty, PointerProperty, StringProperty

# 頂点グループ名に含まれない区切り文字
SNAPSHOT_SEP = "\x1f"

_suppress_toggle_record = False
_sync_suspend_depth = 0


@contextmanager
def suspend_sync():
    """一時名へのリネーム中に同期が走ると、一時名をリネームとして取り込んでしまうので止める。"""
    global _sync_suspend_depth
    _sync_suspend_depth += 1
    try:
        yield
    finally:
        _sync_suspend_depth -= 1


def _on_selected_update(self, _context):
    # 範囲選択の起点にするため、ユーザーが最後に切り替えたグループを覚える
    if _suppress_toggle_record:
        return
    self.id_data.l0c_vgu.last_toggled = self.name


class L0C_VGU_GroupState(bpy.types.PropertyGroup):
    # name は頂点グループ名と同じ値を持つ
    selected: BoolProperty(
        name="Selected",
        description="Include this group in batch operations and sorting",
        update=_on_selected_update,
    )


class L0C_VGU_ObjectState(bpy.types.PropertyGroup):
    items: CollectionProperty(type=L0C_VGU_GroupState)
    # インデックス順のグループ名。リネームの検知に使う
    names_snapshot: StringProperty()
    last_toggled: StringProperty()


def mesh_object(context):
    """オペレーターの対象にする、編集可能なメッシュオブジェクトを返す。"""
    ob = context.object
    if ob is None or ob.type != 'MESH' or not ob.is_editable:
        return None
    return ob


def sync(ob):
    """選択状態を現在の頂点グループ一覧に合わせる。描画中には呼ばないこと。"""
    if _sync_suspend_depth or ob is None or ob.type != 'MESH' or not ob.is_editable:
        return
    state = ob.l0c_vgu
    names = [vg.name for vg in ob.vertex_groups]
    joined = SNAPSHOT_SEP.join(names)
    if joined == state.names_snapshot and len(state.items) == len(names):
        return

    snapshot = state.names_snapshot.split(SNAPSHOT_SEP) if state.names_snapshot else []
    if len(snapshot) == len(names):
        # 並べ替えと区別するため、旧名も新名も相手側に存在しないものだけをリネームとみなす
        old_set, new_set = set(snapshot), set(names)
        renames = {
            old: new for old, new in zip(snapshot, names)
            if old != new and old not in new_set and new not in old_set
        }
        rename_items(state, renames)
        if state.last_toggled in renames:
            state.last_toggled = renames[state.last_toggled]

    current = set(names)
    seen = set()
    for i in reversed(range(len(state.items))):
        name = state.items[i].name
        if name not in current or name in seen:
            state.items.remove(i)
        else:
            seen.add(name)
    for name in names:
        if name not in seen:
            state.items.add().name = name

    state.names_snapshot = joined


def rename_items(state, renames):
    if not renames:
        return
    # 入れ替え(L と R の交換など)に対応するため、先に対象を確定してから書き換える
    targets = [(item, renames[item.name]) for item in state.items if item.name in renames]
    for item, new_name in targets:
        item.name = new_name


def update_snapshot(ob):
    ob.l0c_vgu.names_snapshot = SNAPSHOT_SEP.join(vg.name for vg in ob.vertex_groups)


def selected_names(ob):
    """選択中のグループ名を頂点グループの並び順で返す。"""
    sync(ob)
    items = ob.l0c_vgu.items
    result = []
    for vg in ob.vertex_groups:
        item = items.get(vg.name)
        if item is not None and item.selected:
            result.append(vg.name)
    return result


def set_selected(ob, names, value):
    """指定したグループの選択状態をまとめて変える。範囲選択の起点は更新しない。"""
    global _suppress_toggle_record
    sync(ob)
    items = ob.l0c_vgu.items
    _suppress_toggle_record = True
    try:
        for name in names:
            item = items.get(name)
            if item is not None and item.selected != value:
                item.selected = value
    finally:
        _suppress_toggle_record = False


def count_selected(ob):
    """描画用の選択数。描画中でも呼べるようにデータは書き換えない。"""
    items = ob.l0c_vgu.items
    vgroups = ob.vertex_groups
    return sum(1 for item in items if item.selected and vgroups.get(item.name) is not None)


classes = (
    L0C_VGU_GroupState,
    L0C_VGU_ObjectState,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Object.l0c_vgu = PointerProperty(type=L0C_VGU_ObjectState)


def unregister():
    del bpy.types.Object.l0c_vgu
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
