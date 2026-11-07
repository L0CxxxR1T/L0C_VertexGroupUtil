# SPDX-License-Identifier: GPL-2.0-or-later

"""並び順の計算と、計算した並びを頂点グループへ反映する処理。"""

import re

import bpy

from . import state

TEMP_PREFIX = "__l0cvgu_tmp_"


# ▼ 並び順の計算 (名前のリストだけを扱う) ▼

def move_up(names, selected):
    result = list(names)
    for i in range(1, len(result)):
        if result[i] in selected and result[i - 1] not in selected:
            result[i - 1], result[i] = result[i], result[i - 1]
    return result


def move_down(names, selected):
    result = list(names)
    for i in range(len(result) - 2, -1, -1):
        if result[i] in selected and result[i + 1] not in selected:
            result[i], result[i + 1] = result[i + 1], result[i]
    return result


def move_to(names, selected, position):
    """選択中のグループを相対順を保ったまま position (0 始まり) から並べる。"""
    block = [n for n in names if n in selected]
    rest = [n for n in names if n not in selected]
    position = max(0, min(position, len(rest)))
    return rest[:position] + block + rest[position:]


def reorder_slots(names, targets, reorder):
    """targets のグループが今いる位置の中だけで並びを入れ替える。ほかのグループは動かさない。"""
    slots = [i for i, n in enumerate(names) if n in targets]
    new_subset = reorder([names[i] for i in slots])
    result = list(names)
    for slot, name in zip(slots, new_subset):
        result[slot] = name
    return result


def sort_by_rank(names, rank):
    """rank(name) の昇順に並べる。None を返したグループは元の相対順のまま末尾に置く。"""
    ranks = {n: rank(n) for n in names}
    return sorted(names, key=lambda n: (ranks[n] is None, ranks[n] or 0))


def _wildcard_to_regex(pattern):
    # 仕様で使える記号は * と ? だけなので、fnmatch の [] は使わない
    escaped = re.escape(pattern).replace(r"\*", ".*").replace(r"\?", ".")
    return re.compile(escaped)


def is_wildcard(entry):
    return "*" in entry or "?" in entry


def dictionary_rank(entries):
    """辞書の行番号を返す関数を作る。完全一致を優先し、なければワイルドカードを上から照合する。"""
    exact = {}
    patterns = []
    for i, entry in enumerate(entries):
        if is_wildcard(entry):
            patterns.append((i, _wildcard_to_regex(entry)))
        else:
            exact.setdefault(entry, i)

    def rank(name):
        index = exact.get(name)
        if index is not None:
            return index
        for index, regex in patterns:
            if regex.fullmatch(name):
                return index
        return None

    return rank


# ▼ 頂点グループへの反映 ▼

def apply_order(context, ob, desired):
    """頂点グループを desired の名前順に並べ替える。"""
    vgroups = ob.vertex_groups
    current = [vg.name for vg in vgroups]
    if current == desired:
        return
    if sorted(current) != sorted(desired):
        raise ValueError("並べ替え後の名前一覧が現在の頂点グループと一致しません。")
    if any(n.startswith(TEMP_PREFIX) for n in current):
        raise RuntimeError(f"「{TEMP_PREFIX}」で始まる頂点グループがあるため並べ替えできません。")

    active = vgroups.active
    active_name = active.name if active is not None else None
    position = {name: i for i, name in enumerate(desired)}

    # 任意の位置へ動かす API は1段ずつの移動しかなく遅いので、
    # 目標の順番を表す一時名を付けて名前ソートし、元の名前に戻す
    with state.suspend_sync():
        try:
            for vg in vgroups:
                vg.name = f"{TEMP_PREFIX}{position[vg.name]:05d}"
            with context.temp_override(object=ob, active_object=ob):
                result = bpy.ops.object.vertex_group_sort(sort_type='NAME')
            if 'FINISHED' not in result:
                raise RuntimeError("頂点グループの並べ替えに失敗しました。")
        finally:
            for vg in vgroups:
                if vg.name.startswith(TEMP_PREFIX):
                    vg.name = desired[int(vg.name[len(TEMP_PREFIX):])]
            state.update_snapshot(ob)

    if active_name is not None:
        vgroups.active_index = vgroups[active_name].index


def used_group_indices(ob, zero_as_empty):
    """ウェイトが割り当てられている頂点グループのインデックスを返す。"""
    if ob.mode == 'EDIT':
        ob.update_from_editmode()
    used = set()
    for v in ob.data.vertices:
        for elem in v.groups:
            if zero_as_empty and elem.weight <= 0.0:
                continue
            used.add(elem.group)
    return used


def find_armature(ob):
    """Armature モディファイアの対象を優先し、なければ親のアーマチュアを返す。"""
    for mod in ob.modifiers:
        if mod.type == 'ARMATURE' and mod.object is not None:
            return mod.object
    if ob.parent is not None and ob.parent.type == 'ARMATURE':
        return ob.parent
    return None
