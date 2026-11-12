# SPDX-License-Identifier: GPL-2.0-or-later

"""選択中のグループへの一括操作。"""

import re

import bpy
from bpy.app.translations import pgettext_iface as iface_
from bpy.app.translations import pgettext_rpt as rpt_
from bpy.app.translations import pgettext_tip as tip_
from bpy.props import BoolProperty, EnumProperty, FloatProperty, StringProperty
from mathutils import kdtree

from . import order, sides, state

# Blender の頂点グループ名は終端文字を含めて 64 バイトまで
MAX_NAME_BYTES = 63


def _require_selected(op, ob):
    names = state.selected_names(ob)
    if not names:
        op.report({'ERROR'}, rpt_("No groups are selected."))
    return names


class _MeshPoll:
    @classmethod
    def poll(cls, context):
        ob = state.mesh_object(context)
        return ob is not None and len(ob.vertex_groups) > 0


class L0C_VGU_OT_delete_selected(_MeshPoll, bpy.types.Operator):
    bl_idname = "l0c_vgu.delete_selected"
    bl_label = "Delete Selected Groups"
    bl_description = "Delete the selected vertex groups"
    bl_options = {'REGISTER', 'UNDO'}

    def invoke(self, context, event):
        count = len(state.selected_names(state.mesh_object(context)))
        if count == 0:
            self.report({'ERROR'}, rpt_("No groups are selected."))
            return {'CANCELLED'}
        return context.window_manager.invoke_confirm(
            self, event,
            title=iface_("Delete Selected Groups"),
            message=iface_("Delete {count} vertex groups.").format(count=count),
            confirm_text=iface_("Delete"),
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
        self.report({'INFO'}, rpt_("Deleted {count} vertex groups.").format(count=len(names)))
        return {'FINISHED'}


class L0C_VGU_OT_set_lock(_MeshPoll, bpy.types.Operator):
    bl_idname = "l0c_vgu.set_lock"
    bl_label = "Lock Selected Groups"
    bl_options = {'REGISTER', 'UNDO'}

    action: EnumProperty(
        name="Action",
        items=(
            ('LOCK', "Lock", ""),
            ('UNLOCK', "Unlock", ""),
            ('INVERT', "Invert Lock", ""),
        ),
    )

    @classmethod
    def description(cls, _context, properties):
        return tip_({
            'LOCK': "Lock the selected groups",
            'UNLOCK': "Unlock the selected groups",
            'INVERT': "Invert the lock of each selected group",
        }[properties.action])

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
    bl_label = "Rename Selected Groups"
    bl_description = "Rename the selected vertex groups at once"
    bl_options = {'REGISTER', 'UNDO'}

    mode: EnumProperty(
        name="Method",
        items=(
            ('ADD_PREFIX', "Add Prefix", ""),
            ('ADD_SUFFIX', "Add Suffix", ""),
            ('REMOVE_PREFIX', "Remove Prefix", ""),
            ('REMOVE_SUFFIX', "Remove Suffix", ""),
            ('REPLACE', "Replace", ""),
            ('FLIP', "Flip L/R", ""),
        ),
    )
    text: StringProperty(name="Text")
    find: StringProperty(name="Find")
    replace: StringProperty(name="Replace With")
    use_regex: BoolProperty(name="Regular Expression", default=False)

    def invoke(self, context, _event):
        if not state.selected_names(state.mesh_object(context)):
            self.report({'ERROR'}, rpt_("No groups are selected."))
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
                self.report({'ERROR'}, rpt_("Invalid regular expression: {error}").format(error=e))
                return {'CANCELLED'}

        try:
            renames = {name: self._new_name(name, regex) for name in names}
        except (re.error, IndexError) as e:
            # 置換後の文字列に存在しないグループ参照があるとき
            self.report({'ERROR'}, rpt_("Replacement failed: {error}").format(error=e))
            return {'CANCELLED'}
        renames = {old: new for old, new in renames.items() if old != new}
        if not renames:
            self.report({'INFO'}, rpt_("No group names would change."))
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
        self.report({'INFO'}, rpt_("Renamed {count} vertex groups.").format(count=len(renames)))
        return {'FINISHED'}

    @staticmethod
    def _validate(ob, renames):
        new_names = list(renames.values())
        if any(not n for n in new_names):
            return rpt_("Some groups would get an empty name.")
        too_long = [n for n in new_names if len(n.encode("utf-8")) > MAX_NAME_BYTES]
        if too_long:
            return rpt_("Names longer than {max} bytes: {names}").format(
                max=MAX_NAME_BYTES, names=", ".join(too_long),
            )
        if any(n.startswith(order.TEMP_PREFIX) for n in new_names):
            return rpt_("Names starting with \"{prefix}\" are not allowed.").format(prefix=order.TEMP_PREFIX)
        kept = {vg.name for vg in ob.vertex_groups if vg.name not in renames}
        seen = set()
        duplicates = []
        for n in new_names:
            if n in kept or n in seen:
                duplicates.append(n)
            seen.add(n)
        if duplicates:
            return rpt_("Duplicate names after renaming: {names}").format(
                names=", ".join(sorted(set(duplicates))),
            )
        return None


class L0C_VGU_OT_create_opposite(_MeshPoll, bpy.types.Operator):
    bl_idname = "l0c_vgu.create_opposite"
    bl_label = "Create Opposite Groups"
    bl_description = (
        "Create opposite-side groups from the selected L/R groups "
        "and place each one right after its source group"
    )
    bl_options = {'REGISTER', 'UNDO'}

    weight_mode: EnumProperty(
        name="Weights",
        items=(
            ('MIRROR', "Mirror on X Axis", "Copy the weights of the source group mirrored on the X axis"),
            ('EMPTY', "Empty Group", "Create the group by name only without copying weights"),
        ),
    )
    use_topology: BoolProperty(
        name="Topology Mirror",
        description="Find opposite vertices by mesh connectivity instead of position",
        default=False,
    )

    def invoke(self, context, _event):
        if not state.selected_names(state.mesh_object(context)):
            self.report({'ERROR'}, rpt_("No groups are selected."))
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

        messages = [rpt_("Created {count} groups.").format(count=len(created))]
        if existing:
            messages.append(
                rpt_("Skipped because the opposite group exists: {names}").format(names=", ".join(existing))
            )
        if no_side:
            messages.append(
                rpt_("Skipped because there is no L/R suffix: {names}").format(names=", ".join(no_side))
            )
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
                raise RuntimeError(rpt_("Could not copy \"{name}\".").format(name=source))
            copied = vgroups.active
            if 'FINISHED' not in bpy.ops.object.vertex_group_mirror(
                mirror_weights=True,
                flip_group_names=False,
                all_groups=False,
                use_topology=self.use_topology,
            ):
                raise RuntimeError(rpt_("Could not mirror the weights of \"{name}\".").format(name=source))
        copied.name = opposite


class L0C_VGU_OT_vertex_assign(_MeshPoll, bpy.types.Operator):
    bl_idname = "l0c_vgu.vertex_assign"
    bl_label = "Vertex Operations on Selected Groups"
    bl_options = {'REGISTER', 'UNDO'}

    action: EnumProperty(
        name="Action",
        items=(
            ('ASSIGN', "Assign", ""),
            ('REMOVE', "Remove", ""),
            ('SELECT', "Select", ""),
            ('DESELECT', "Deselect", ""),
        ),
    )

    @classmethod
    def description(cls, _context, properties):
        return tip_({
            'ASSIGN': "Assign the selected vertices to all selected groups",
            'REMOVE': "Remove the selected vertices from all selected groups",
            'SELECT': "Select the vertices that belong to the selected groups",
            'DESELECT': "Deselect the vertices that belong to the selected groups",
        }[properties.action])

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
                    self.report({'ERROR'}, rpt_("Run this in Edit Mode."))
                    return {'CANCELLED'}
                for name in names:
                    vgroups.active_index = vgroups[name].index
                    operator()
        finally:
            vgroups.active_index = active_index
        return {'FINISHED'}


class L0C_VGU_OT_copy_to_selected(_MeshPoll, bpy.types.Operator):
    bl_idname = "l0c_vgu.copy_to_selected"
    bl_label = "Copy to Other Objects"
    bl_description = "Copy the selected groups with their weights to the other selected mesh objects"
    bl_options = {'REGISTER', 'UNDO'}

    mapping: EnumProperty(
        name="Mapping",
        items=(
            ('INDEX', "Vertex Index",
             "Copy to the vertices with the same index. Objects with a different vertex count are skipped"),
            ('NEAREST', "Nearest Vertex", "Copy the weights of the nearest vertex in world space"),
        ),
    )
    max_distance: FloatProperty(
        name="Max Distance",
        description="Vertices farther than this are not copied to. 0 means no limit",
        default=0.0,
        min=0.0,
        subtype='DISTANCE',
    )
    conflict: EnumProperty(
        name="Existing Groups",
        items=(
            ('REPLACE', "Overwrite", "Clear the weights of the existing group before copying"),
            ('SKIP', "Skip", "Leave existing groups unchanged"),
        ),
    )
    match_order: BoolProperty(
        name="Match Source Order",
        description="Order the copied groups in the target the same way as in the source",
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
            self.report({'ERROR'}, rpt_("Select the mesh objects to copy to."))
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
            self.report(
                {'WARNING'},
                rpt_("Skipped due to a different vertex count: {names}").format(names=", ".join(skipped)),
            )
        else:
            self.report({'INFO'}, rpt_("Copied to {count} objects.").format(count=len(targets)))
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
