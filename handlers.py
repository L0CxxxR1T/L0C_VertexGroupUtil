# SPDX-License-Identifier: GPL-2.0-or-later

"""標準の操作で頂点グループが変わったときに、選択状態を追従させる。"""

import bpy
from bpy.app.handlers import persistent

from . import state

_msgbus_owner = object()


def _sync_all():
    for ob in bpy.data.objects:
        if ob.type == 'MESH' and (ob.vertex_groups or ob.l0c_vgu.items):
            state.sync(ob)


def _on_vgroup_name_changed():
    # msgbus はどのオブジェクトの名前が変わったかを渡さないので、すべてを照合する
    _sync_all()


def _subscribe():
    bpy.msgbus.clear_by_owner(_msgbus_owner)
    bpy.msgbus.subscribe_rna(
        key=(bpy.types.VertexGroup, "name"),
        owner=_msgbus_owner,
        args=(),
        notify=_on_vgroup_name_changed,
    )


@persistent
def _on_load_post(_filepath):
    # ファイルを開くと msgbus の購読が消えるので登録し直す
    _subscribe()
    _sync_all()


@persistent
def _on_undo_redo_post(_scene, _undo_name=None):
    _subscribe()


@persistent
def _on_depsgraph_update_post(_scene, depsgraph):
    # 頂点グループの追加と削除を拾う
    for update in depsgraph.updates:
        id_data = update.id
        if isinstance(id_data, bpy.types.Object) and id_data.type == 'MESH':
            state.sync(id_data.original)


_app_handlers = (
    (bpy.app.handlers.load_post, _on_load_post),
    (bpy.app.handlers.undo_post, _on_undo_redo_post),
    (bpy.app.handlers.redo_post, _on_undo_redo_post),
    (bpy.app.handlers.depsgraph_update_post, _on_depsgraph_update_post),
)


def register():
    for handler_list, func in _app_handlers:
        if func not in handler_list:
            handler_list.append(func)
    _subscribe()


def unregister():
    bpy.msgbus.clear_by_owner(_msgbus_owner)
    for handler_list, func in _app_handlers:
        if func in handler_list:
            handler_list.remove(func)
