# SPDX-License-Identifier: GPL-2.0-or-later

"""選択中のグループへの一括操作。"""

import re

import bpy
from bpy.props import BoolProperty, EnumProperty, FloatProperty, StringProperty
from mathutils import kdtree

from . import order, sides, state

# Blender の頂点グループ名は終端文字を含めて 64 バイトまで
MAX_NAME_BYTES = 63


def _require_selected(op, ob):
    names = state.selected_names(ob)
    if not names:
        op.report({'ERROR'}, "グループが選択されていません。")
    return names


class _MeshPoll:
    @classmethod
    def poll(cls, context):
        ob = state.mesh_object(context)
        return ob is not None and len(ob.vertex_groups) > 0


class L0C_VGU_OT_delete_selected(_MeshPoll, bpy.types.Operator):
    bl_idname = "l0c_vgu.delete_selected"
    bl_label = "選択中のグループを削除"
    bl_description = "選択中の頂点グループを削除します"
    bl_options = {'REGISTER', 'UNDO'}

    def invoke(self, context, event):
        count = len(state.selected_names(state.mesh_object(context)))
        if count == 0:
            self.report({'ERROR'}, "グループが選択されていません。")
            return {'CANCELLED'}
        return context.window_manager.invoke_confirm(
            self, event,
            title="選択中のグループを削除",
            message=f"{count} 個の頂点グループを削除します。",
            confirm_text="削除",
            icon='WARNING',
        )

    def execute(self, context):
        ob = state.mesh_object(context)
        names = _require_selected(self, ob)
        if not names:
            return {'CANCELLED'}
        for name in names:
            ob.vertex_groups.remove(ob.vertex_groups[name])
        state.sync(ob)
        self.report({'INFO'}, f"{len(names)} 個の頂点グループを削除しました。")
        return {'FINISHED'}


class L0C_VGU_OT_set_lock(_MeshPoll, bpy.types.Operator):
    bl_idname = "l0c_vgu.set_lock"
    bl_label = "選択中のグループのロック"
    bl_options = {'REGISTER', 'UNDO'}

    action: EnumProperty(
        name="操作",
        items=(
            ('LOCK', "ロック", ""),
            ('UNLOCK', "ロック解除", ""),
            ('INVERT', "ロック反転", ""),
        ),
    )

    @classmethod
    def description(cls, _context, properties):
        return {
            'LOCK': "選択中のグループをロックします",
            'UNLOCK': "選択中のグループのロックを解除します",
            'INVERT': "選択中のグループのロックをそれぞれ反転します",
        }[properties.action]

    def execute(self, context):
        ob = state.mesh_object(context)
        names = _require_selected(self, ob)
        if not names:
            return {'CANCELLED'}
        for name in names:
            vg = ob.vertex_groups[name]
            if self.action == 'INVERT':
                vg.lock_weight = not vg.lock_weight
            else:
                vg.lock_weight = self.action == 'LOCK'
        return {'FINISHED'}


class L0C_VGU_OT_rename(_MeshPoll, bpy.types.Operator):
    bl_idname = "l0c_vgu.rename"
    bl_label = "選択中のグループをリネーム"
    bl_description = "選択中の頂点グループの名前をまとめて変更します"
    bl_options = {'REGISTER', 'UNDO'}

    mode: EnumProperty(
        name="方法",
        items=(
            ('ADD_PREFIX', "接頭辞を追加", ""),
            ('ADD_SUFFIX', "接尾辞を追加", ""),
            ('REMOVE_PREFIX', "接頭辞を削除", ""),
            ('REMOVE_SUFFIX', "接尾辞を削除", ""),
            ('REPLACE', "置換", ""),
            ('FLIP', "L/R を入れ替え", ""),
        ),
    )
    text: StringProperty(name="文字列")
    find: StringProperty(name="検索")
    replace: StringProperty(name="置換後")
    use_regex: BoolProperty(name="正規表現", default=False)

    def invoke(self, context, _event):
        if not state.selected_names(state.mesh_object(context)):
            self.report({'ERROR'}, "グループが選択されていません。")
            return {'CANCELLED'}
        return context.window_manager.invoke_props_dialog(self, width=320)

    def draw(self, _context):
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False
        layout.prop(self, "mode")
        if self.mode in {'ADD_PREFIX', 'ADD_SUFFIX', 'REMOVE_PREFIX', 'REMOVE_SUFFIX'}:
            layout.prop(self, "text")
        elif self.mode == 'REPLACE':
            layout.prop(self, "find")
            layout.prop(self, "replace")
            layout.prop(self, "use_regex")

    def _new_name(self, name, regex):
        if self.mode == 'ADD_PREFIX':
            return self.text + name
        if self.mode == 'ADD_SUFFIX':
            return name + self.text
        if self.mode == 'REMOVE_PREFIX':
            return name[len(self.text):] if self.text and name.startswith(self.text) else name
        if self.mode == 'REMOVE_SUFFIX':
            return name[:-len(self.text)] if self.text and name.endswith(self.text) else name
        if self.mode == 'REPLACE':
            if regex is not None:
                return regex.sub(self.replace, name)
            return name.replace(self.find, self.replace) if self.find else name
        return bpy.utils.flip_name(name)

    def execute(self, context):
        ob = state.mesh_object(context)
        names = _require_selected(self, ob)
        if not names:
            return {'CANCELLED'}

        regex = None
        if self.mode == 'REPLACE' and self.use_regex and self.find:
            try:
                regex = re.compile(self.find)
            except re.error as e:
                self.report({'ERROR'}, f"正規表現が正しくありません: {e}")
                return {'CANCELLED'}

        try:
            renames = {name: self._new_name(name, regex) for name in names}
        except (re.error, IndexError) as e:
            # 置換後の文字列に存在しないグループ参照があるとき
            self.report({'ERROR'}, f"置換に失敗しました: {e}")
            return {'CANCELLED'}
        renames = {old: new for old, new in renames.items() if old != new}
        if not renames:
            self.report({'INFO'}, "名前が変わるグループはありませんでした。")
            return {'CANCELLED'}

        error = self._validate(ob, renames)
        if error:
            self.report({'ERROR'}, error)
            return {'CANCELLED'}

        # L と R の入れ替えのように名前が循環するときに備え、一時名を経由する
        vgroups = ob.vertex_groups
        with state.suspend_sync():
            for i, old in enumerate(renames):
                vgroups[old].name = f"{order.TEMP_PREFIX}{i:05d}"
            for i, new in enumerate(renames.values()):
                vgroups[f"{order.TEMP_PREFIX}{i:05d}"].name = new

            state.rename_items(ob.l0c_vgu, renames)
            if ob.l0c_vgu.last_toggled in renames:
                ob.l0c_vgu.last_toggled = renames[ob.l0c_vgu.last_toggled]
            state.update_snapshot(ob)
        self.report({'INFO'}, f"{len(renames)} 個の頂点グループをリネームしました。")
        return {'FINISHED'}

    @staticmethod
    def _validate(ob, renames):
        new_names = list(renames.values())
        if any(not n for n in new_names):
            return "名前が空になるグループがあります。"
        too_long = [n for n in new_names if len(n.encode("utf-8")) > MAX_NAME_BYTES]
        if too_long:
            return f"名前が {MAX_NAME_BYTES} バイトを超えます: {', '.join(too_long)}"
        if any(n.startswith(order.TEMP_PREFIX) for n in new_names):
            return f"「{order.TEMP_PREFIX}」で始まる名前は使えません。"
        kept = {vg.name for vg in ob.vertex_groups if vg.name not in renames}
        seen = set()
        duplicates = []
        for n in new_names:
            if n in kept or n in seen:
                duplicates.append(n)
            seen.add(n)
        if duplicates:
            return f"変更後の名前が重複します: {', '.join(sorted(set(duplicates)))}"
        return None


class L0C_VGU_OT_create_opposite(_MeshPoll, bpy.types.Operator):
    bl_idname = "l0c_vgu.create_opposite"
    bl_label = "逆側のグループを生成"
    bl_description = "選択中の L/R のグループから逆側のグループを作り、元のグループの直後に置きます"
    bl_options = {'REGISTER', 'UNDO'}

    weight_mode: EnumProperty(
        name="ウェイト",
        items=(
            ('MIRROR', "X 軸で反転してコピー", "元のグループのウェイトを X 軸で反転してコピーします"),
            ('EMPTY', "空のグループ", "名前だけ作り、ウェイトはコピーしません"),
        ),
    )
    use_topology: BoolProperty(
        name="トポロジーミラー",
        description="頂点の位置ではなくメッシュのつながりで反対側の頂点を探します",
        default=False,
    )

    def invoke(self, context, _event):
        if not state.selected_names(state.mesh_object(context)):
            self.report({'ERROR'}, "グループが選択されていません。")
            return {'CANCELLED'}
        return context.window_manager.invoke_props_dialog(self, width=320)

    def draw(self, _context):
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False
        layout.prop(self, "weight_mode")
        if self.weight_mode == 'MIRROR':
            layout.prop(self, "use_topology")

    def execute(self, context):
        ob = state.mesh_object(context)
        names = _require_selected(self, ob)
        if not names:
            return {'CANCELLED'}

        vgroups = ob.vertex_groups
        jobs = []
        no_side = []
        existing = []
        for name in names:
            opposite = sides.opposite_name(name)
            if opposite is None:
                no_side.append(name)
            elif vgroups.get(opposite) is not None:
                existing.append(opposite)
            else:
                jobs.append((name, opposite))

        active = vgroups.active
        active_name = active.name if active is not None else None
        created = {}
        try:
            for source, opposite in jobs:
                self._create(context, ob, source, opposite)
                created[source] = opposite
        except RuntimeError as e:
            self.report({'ERROR'}, str(e))
            return {'CANCELLED'}
        finally:
            if active_name is not None and vgroups.get(active_name) is not None:
                vgroups.active_index = vgroups[active_name].index

        if created:
            new_names = set(created.values())
            desired = []
            for name in (vg.name for vg in vgroups):
                if name in new_names:
                    continue
                desired.append(name)
                if name in created:
                    desired.append(created[name])
            try:
                order.apply_order(context, ob, desired)
            except (ValueError, RuntimeError) as e:
                self.report({'ERROR'}, str(e))
                return {'CANCELLED'}
        state.sync(ob)

        messages = [f"{len(created)} 個のグループを生成しました。"]
        if existing:
            messages.append(f"逆側が既にあるためスキップ: {', '.join(existing)}")
        if no_side:
            messages.append(f"L/R のサフィックスがないためスキップ: {', '.join(no_side)}")
        self.report({'WARNING'} if existing or no_side else {'INFO'}, " ".join(messages))
        return {'FINISHED'}

    def _create(self, context, ob, source, opposite):
        vgroups = ob.vertex_groups
        if self.weight_mode == 'EMPTY':
            vgroups.new(name=opposite)
            return

        vgroups.active_index = vgroups[source].index
        with context.temp_override(object=ob, active_object=ob):
            if 'FINISHED' not in bpy.ops.object.vertex_group_copy():
                raise RuntimeError(f"「{source}」をコピーできませんでした。")
            copied = vgroups.active
            if 'FINISHED' not in bpy.ops.object.vertex_group_mirror(
                mirror_weights=True,
                flip_group_names=False,
                all_groups=False,
                use_topology=self.use_topology,
            ):
                raise RuntimeError(f"「{source}」のウェイトを反転できませんでした。")
        copied.name = opposite


class L0C_VGU_OT_vertex_assign(_MeshPoll, bpy.types.Operator):
    bl_idname = "l0c_vgu.vertex_assign"
    bl_label = "選択中のグループの頂点操作"
    bl_options = {'REGISTER', 'UNDO'}

    action: EnumProperty(
        name="操作",
        items=(
            ('ASSIGN', "割り当て", ""),
            ('REMOVE', "除去", ""),
            ('SELECT', "選択", ""),
            ('DESELECT', "選択解除", ""),
        ),
    )

    @classmethod
    def description(cls, _context, properties):
        return {
            'ASSIGN': "選択している頂点を、選択中のすべてのグループに割り当てます",
            'REMOVE': "選択している頂点を、選択中のすべてのグループから除去します",
            'SELECT': "選択中のすべてのグループに属する頂点を選択します",
            'DESELECT': "選択中のすべてのグループに属する頂点の選択を解除します",
        }[properties.action]

    def execute(self, context):
        ob = state.mesh_object(context)
        names = _require_selected(self, ob)
        if not names:
            return {'CANCELLED'}

        operator = {
            'ASSIGN': bpy.ops.object.vertex_group_assign,
            'REMOVE': bpy.ops.object.vertex_group_remove_from,
            'SELECT': bpy.ops.object.vertex_group_select,
            'DESELECT': bpy.ops.object.vertex_group_deselect,
        }[self.action]

        vgroups = ob.vertex_groups
        active_index = vgroups.active_index
        try:
            with context.temp_override(object=ob, active_object=ob):
                if not operator.poll():
                    self.report({'ERROR'}, "編集モードで実行してください。")
                    return {'CANCELLED'}
                for name in names:
                    vgroups.active_index = vgroups[name].index
                    operator()
        finally:
            vgroups.active_index = active_index
        return {'FINISHED'}


class L0C_VGU_OT_copy_to_selected(_MeshPoll, bpy.types.Operator):
    bl_idname = "l0c_vgu.copy_to_selected"
    bl_label = "他オブジェクトへコピー"
    bl_description = "選択中のグループをウェイトごと、ほかに選択しているメッシュオブジェクトへコピーします"
    bl_options = {'REGISTER', 'UNDO'}

    mapping: EnumProperty(
        name="対応付け",
        items=(
            ('INDEX', "頂点インデックス", "同じインデックスの頂点にコピーします。頂点数が違うオブジェクトはスキップします"),
            ('NEAREST', "最近傍頂点", "ワールド座標で最も近い頂点のウェイトをコピーします"),
        ),
    )
    max_distance: FloatProperty(
        name="最大距離",
        description="これより離れた頂点にはコピーしません。0 のときは距離を制限しません",
        default=0.0,
        min=0.0,
        subtype='DISTANCE',
    )
    conflict: EnumProperty(
        name="同名のグループ",
        items=(
            ('REPLACE', "置き換え", "既存のグループのウェイトを消してからコピーします"),
            ('SKIP', "スキップ", "既存のグループには何もしません"),
        ),
    )
    match_order: BoolProperty(
        name="並び順をコピー元にそろえる",
        description="コピー先で、コピー元にあるグループの並びをコピー元と同じ順にします",
        default=False,
    )

    @classmethod
    def poll(cls, context):
        return super().poll(context) and context.mode == 'OBJECT'

    def invoke(self, context, _event):
        return context.window_manager.invoke_props_dialog(self, width=360)

    def draw(self, _context):
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False
        layout.prop(self, "mapping")
        if self.mapping == 'NEAREST':
            layout.prop(self, "max_distance")
        layout.prop(self, "conflict")
        layout.prop(self, "match_order")

    def execute(self, context):
        source = state.mesh_object(context)
        names = _require_selected(self, source)
        if not names:
            return {'CANCELLED'}
        targets = [
            o for o in context.selected_objects
            if o is not source and o.type == 'MESH' and o.is_editable
        ]
        if not targets:
            self.report({'ERROR'}, "コピー先のメッシュオブジェクトを選択してください。")
            return {'CANCELLED'}

        weights = self._read_weights(source, names)
        tree = self._build_tree(source) if self.mapping == 'NEAREST' else None

        skipped = []
        for target in targets:
            if self.mapping == 'INDEX':
                if len(target.data.vertices) != len(source.data.vertices):
                    skipped.append(target.name)
                    continue
                vertex_map = None
            else:
                vertex_map = self._nearest_map(source, target, tree)
            try:
                self._write(context, target, names, weights, vertex_map)
            except (ValueError, RuntimeError) as e:
                self.report({'ERROR'}, f"{target.name}: {e}")
                return {'CANCELLED'}

        if skipped:
            self.report({'WARNING'}, f"頂点数が違うためスキップしました: {', '.join(skipped)}")
        else:
            self.report({'INFO'}, f"{len(targets)} 個のオブジェクトへコピーしました。")
        return {'FINISHED'}

    @staticmethod
    def _read_weights(source, names):
        index_to_name = {source.vertex_groups[n].index: n for n in names}
        weights = {n: {} for n in names}
        for v in source.data.vertices:
            for elem in v.groups:
                name = index_to_name.get(elem.group)
                if name is not None:
                    weights[name][v.index] = elem.weight
        return weights

    @staticmethod
    def _build_tree(source):
        vertices = source.data.vertices
        tree = kdtree.KDTree(len(vertices))
        matrix = source.matrix_world
        for v in vertices:
            tree.insert(matrix @ v.co, v.index)
        tree.balance()
        return tree

    def _nearest_map(self, source, target, tree):
        """コピー先の頂点インデックスから、コピー元の頂点インデックスへの対応を返す。"""
        result = {}
        matrix = target.matrix_world
        for v in target.data.vertices:
            _co, index, dist = tree.find(matrix @ v.co)
            if index is None:
                continue
            if self.max_distance > 0.0 and dist > self.max_distance:
                continue
            result[v.index] = index
        return result

    def _write(self, context, target, names, weights, vertex_map):
        vgroups = target.vertex_groups
        all_indices = list(range(len(target.data.vertices)))
        state.sync(target)
        for name in names:
            vg = vgroups.get(name)
            if vg is not None:
                if self.conflict == 'SKIP':
                    continue
                vg.remove(all_indices)
            else:
                vg = vgroups.new(name=name)

            source_weights = weights[name]
            if vertex_map is None:
                for index, weight in source_weights.items():
                    vg.add((index,), weight, 'REPLACE')
            else:
                for target_index, source_index in vertex_map.items():
                    weight = source_weights.get(source_index)
                    if weight is not None:
                        vg.add((target_index,), weight, 'REPLACE')

        if self.match_order:
            source_order = {n: i for i, n in enumerate(names)}
            current = [vg.name for vg in vgroups]
            desired = order.reorder_slots(
                current, set(source_order),
                lambda subset: sorted(subset, key=source_order.__getitem__),
            )
            order.apply_order(context, target, desired)
        state.sync(target)


classes = (
    L0C_VGU_OT_delete_selected,
    L0C_VGU_OT_set_lock,
    L0C_VGU_OT_rename,
    L0C_VGU_OT_create_opposite,
    L0C_VGU_OT_vertex_assign,
    L0C_VGU_OT_copy_to_selected,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
