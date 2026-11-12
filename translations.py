# SPDX-License-Identifier: GPL-2.0-or-later

"""UI の日本語訳。ソースの文字列は英語で書き、ここで ja_JP の訳を登録する。"""

import bpy

# 翻訳は (コンテキスト, 原文) の完全一致で引かれる。
# オペレーターの bl_label と layout.operator() の text は "Operator"、
# それ以外 (プロパティ、メニュー、ラベル、ツールチップ、レポート) は "*" で引かれる。
# Blender 本体の訳がある原文は本体の訳が優先される。
_JA_DEFAULT = {
    # state
    "Selected": "選択",
    "Include this group in batch operations and sorting": "このグループを一括操作と並べ替えの対象にします",

    # ui
    "Show Selected Only": "選択中のみ表示",
    "Show only checked groups": "チェックが入ったグループだけを表示します",
    "By Dictionary (Selected Only)": "辞書順 (選択中のみ)",
    "By Dictionary (All)": "辞書順 (全体)",
    "No dictionaries are registered. Register one in the Preferences.":
        "辞書が登録されていません。プリファレンスで登録してください。",
    "Sort": "並べ替え",
    "By Dictionary": "辞書順",
    "Batch Operations": "一括操作",
    "{count} Selected Groups": "選択中の {count} グループ",

    # prefs
    "Source File": "読み込み元",
    "{count} lines": "{count} 行",
    "and {count} more lines": "ほか {count} 行",
    "Replace Default Vertex Group Panel": "標準の頂点グループパネルを置き換える",
    "Turn this off to restore the default panel": "オフにすると標準のパネル表示に戻します",
    "Sorting Dictionaries": "並べ替え用の辞書",
    "Import a CSV file and register it as a sorting dictionary": "CSV を読み込んで並べ替え用の辞書として登録します",
    "Reload the dictionary from its source CSV file": "読み込み元の CSV から辞書を読み直します",
    "Remove the active dictionary from the list. The CSV file is not deleted":
        "選択中の辞書を登録から外します。CSV ファイルは削除しません",
    "Export the active dictionary to a CSV file": "選択中の辞書を CSV に書き出します",
    "Could not read the dictionary: {error}": "辞書を読み込めませんでした: {error}",
    "The dictionary has no valid lines.": "辞書に有効な行がありません。",
    "Registered dictionary \"{name}\" with {count} lines.": "辞書「{name}」を {count} 行で登録しました。",
    "Reloaded dictionary \"{name}\" with {count} lines.": "辞書「{name}」を {count} 行で読み直しました。",
    "Could not write the dictionary: {error}": "辞書を書き出せませんでした: {error}",
    "Exported dictionary \"{name}\".": "辞書「{name}」を書き出しました。",

    # ops_select
    "Change the checks of the vertex groups at once": "頂点グループのチェックをまとめて切り替えます",
    "Action": "操作",
    "Select All": "全選択",
    "Deselect All": "全解除",
    "Invert": "反転",
    "Check all groups": "すべてのグループにチェックを入れます",
    "Uncheck all groups": "すべてのグループのチェックを外します",
    "Invert the checks": "チェックの有無を反転します",
    "Set the groups from the active group to the last toggled group "
    "to the same check state as the last toggled group":
        "アクティブのグループから、最後にチェックを切り替えたグループまでを、"
        "そのグループと同じチェック状態にそろえます",
    "The start group was not found. Toggle a checkbox first, then run this again.":
        "起点のグループが見つかりません。チェックボックスを1つ切り替えてから実行してください。",
    "Side": "側",
    "Extend": "追加選択",
    "Add to the current selection instead of replacing it": "今の選択を残したまま追加します",
    "Select groups whose names end with .{side}, _{side_lower} and so on. "
    "Shift-click to add to the current selection":
        "名前が .{side} や _{side_lower} などで終わるグループを選択します。"
        "Shift+クリックで今の選択に追加します",
    "No groups found on the {side} side.": "{side} 側のグループはありませんでした。",
    "Vertex group \"{name}\" was not found.": "頂点グループ「{name}」が見つかりません。",

    # ops_sort
    "Selected Only": "選択中のみ",
    "All": "全体",
    "Sort only within the positions the selected groups occupy": "選択中のグループが今いる位置の中だけで並べ替えます",
    "Sort all groups": "すべてのグループを並べ替えます",
    "No groups are selected.": "グループが選択されていません。",
    "Direction": "方向",
    "To Top": "先頭へ",
    "Up": "上へ",
    "Down": "下へ",
    "To Bottom": "末尾へ",
    "Move the selected groups to the top": "選択中のグループを先頭へ移動します",
    "Move the selected groups up by one": "選択中のグループを1つ上へ移動します",
    "Move the selected groups down by one": "選択中のグループを1つ下へ移動します",
    "Move the selected groups to the bottom": "選択中のグループを末尾へ移動します",
    "Move the selected groups to the given position, keeping their relative order":
        "選択中のグループを、相対順を保ったまま指定した位置へ移動します",
    "Position": "位置",
    "Position of the first moved group. 1 is the top": "移動後に先頭のグループが来る位置です。1 が先頭です",
    "Method": "方法",
    "By Bone": "ボーン順",
    "Reverse": "逆順",
    "Empty Groups Last": "空グループを末尾へ",
    "Match the order of the armature's bones": "アーマチュアのボーンの並び順に合わせます",
    "Reverse the order": "並びを反転します",
    "Move groups with no assigned weights to the end": "ウェイトが割り当てられていないグループを末尾へ送ります",
    "Scope": "対象",
    "Treat Zero Weights as Empty": "ウェイト 0 も空とみなす",
    "Also treat groups that only have zero weights as empty": "ウェイトが 0 の割り当てしかないグループも空グループとして扱います",
    "Match the order of the armature's bones. Groups without a bone go to the end":
        "アーマチュアのボーンの並び順に合わせます。ボーンがないグループは末尾に置きます",
    "Applies to the selected groups": "選択中のグループが対象です",
    "Applies to all groups": "すべてのグループが対象です",
    "{method}. {scope}": "{method}。{scope}",
    "No Armature modifier target or parent armature was found.":
        "Armature モディファイアの対象か、親のアーマチュアが見つかりません。",
    "Sort by the line order of a dictionary registered in the Preferences. "
    "Groups not in the dictionary go to the end":
        "プリファレンスに登録した辞書の行順に並べ替えます。辞書にないグループは末尾に置きます",
    "Dictionary": "辞書",
    "Dictionary \"{name}\" is not registered.": "辞書「{name}」が登録されていません。",

    # order
    "The sorted name list does not match the current vertex groups.":
        "並べ替え後の名前一覧が現在の頂点グループと一致しません。",
    "Cannot sort because a vertex group name starts with \"{prefix}\".":
        "「{prefix}」で始まる頂点グループがあるため並べ替えできません。",
    "Failed to sort the vertex groups.": "頂点グループの並べ替えに失敗しました。",

    # ops_batch
    "Delete Selected Groups": "選択中のグループを削除",
    "Delete the selected vertex groups": "選択中の頂点グループを削除します",
    "Delete {count} vertex groups.": "{count} 個の頂点グループを削除します。",
    "Delete": "削除",
    "Deleted {count} vertex groups.": "{count} 個の頂点グループを削除しました。",
    "Lock": "ロック",
    "Unlock": "ロック解除",
    "Invert Lock": "ロック反転",
    "Lock the selected groups": "選択中のグループをロックします",
    "Unlock the selected groups": "選択中のグループのロックを解除します",
    "Invert the lock of each selected group": "選択中のグループのロックをそれぞれ反転します",
    "Rename the selected vertex groups at once": "選択中の頂点グループの名前をまとめて変更します",
    "Add Prefix": "接頭辞を追加",
    "Add Suffix": "接尾辞を追加",
    "Remove Prefix": "接頭辞を削除",
    "Remove Suffix": "接尾辞を削除",
    "Replace": "置換",
    "Flip L/R": "L/R を入れ替え",
    "Text": "文字列",
    "Find": "検索",
    "Replace With": "置換後",
    "Regular Expression": "正規表現",
    "Invalid regular expression: {error}": "正規表現が正しくありません: {error}",
    "Replacement failed: {error}": "置換に失敗しました: {error}",
    "No group names would change.": "名前が変わるグループはありませんでした。",
    "Renamed {count} vertex groups.": "{count} 個の頂点グループをリネームしました。",
    "Some groups would get an empty name.": "名前が空になるグループがあります。",
    "Names longer than {max} bytes: {names}": "名前が {max} バイトを超えます: {names}",
    "Names starting with \"{prefix}\" are not allowed.": "「{prefix}」で始まる名前は使えません。",
    "Duplicate names after renaming: {names}": "変更後の名前が重複します: {names}",
    "Create opposite-side groups from the selected L/R groups "
    "and place each one right after its source group":
        "選択中の L/R のグループから逆側のグループを作り、元のグループの直後に置きます",
    "Weights": "ウェイト",
    "Mirror on X Axis": "X 軸で反転してコピー",
    "Copy the weights of the source group mirrored on the X axis": "元のグループのウェイトを X 軸で反転してコピーします",
    "Empty Group": "空のグループ",
    "Create the group by name only without copying weights": "名前だけ作り、ウェイトはコピーしません",
    "Topology Mirror": "トポロジーミラー",
    "Find opposite vertices by mesh connectivity instead of position":
        "頂点の位置ではなくメッシュのつながりで反対側の頂点を探します",
    "Created {count} groups.": "{count} 個のグループを生成しました。",
    "Skipped because the opposite group exists: {names}": "逆側が既にあるためスキップ: {names}",
    "Skipped because there is no L/R suffix: {names}": "L/R のサフィックスがないためスキップ: {names}",
    "Could not copy \"{name}\".": "「{name}」をコピーできませんでした。",
    "Could not mirror the weights of \"{name}\".": "「{name}」のウェイトを反転できませんでした。",
    "Assign": "割り当て",
    "Remove": "除去",
    "Select": "選択",
    "Deselect": "選択解除",
    "Assign the selected vertices to all selected groups": "選択している頂点を、選択中のすべてのグループに割り当てます",
    "Remove the selected vertices from all selected groups": "選択している頂点を、選択中のすべてのグループから除去します",
    "Select the vertices that belong to the selected groups": "選択中のすべてのグループに属する頂点を選択します",
    "Deselect the vertices that belong to the selected groups": "選択中のすべてのグループに属する頂点の選択を解除します",
    "Run this in Edit Mode.": "編集モードで実行してください。",
    "Copy the selected groups with their weights to the other selected mesh objects":
        "選択中のグループをウェイトごと、ほかに選択しているメッシュオブジェクトへコピーします",
    "Mapping": "対応付け",
    "Vertex Index": "頂点インデックス",
    "Copy to the vertices with the same index. Objects with a different vertex count are skipped":
        "同じインデックスの頂点にコピーします。頂点数が違うオブジェクトはスキップします",
    "Nearest Vertex": "最近傍頂点",
    "Copy the weights of the nearest vertex in world space": "ワールド座標で最も近い頂点のウェイトをコピーします",
    "Max Distance": "最大距離",
    "Vertices farther than this are not copied to. 0 means no limit":
        "これより離れた頂点にはコピーしません。0 のときは距離を制限しません",
    "Existing Groups": "同名のグループ",
    "Overwrite": "置き換え",
    "Skip": "スキップ",
    "Clear the weights of the existing group before copying": "既存のグループのウェイトを消してからコピーします",
    "Leave existing groups unchanged": "既存のグループには何もしません",
    "Match Source Order": "並び順をコピー元にそろえる",
    "Order the copied groups in the target the same way as in the source":
        "コピー先で、コピー元にあるグループの並びをコピー元と同じ順にします",
    "Select the mesh objects to copy to.": "コピー先のメッシュオブジェクトを選択してください。",
    "Skipped due to a different vertex count: {names}": "頂点数が違うためスキップしました: {names}",
    "Copied to {count} objects.": "{count} 個のオブジェクトへコピーしました。",
}

_JA_OPERATOR = {
    # bl_label
    "Select Vertex Groups": "頂点グループの選択",
    "Select Range": "範囲選択",
    "Select by L/R": "L/R で選択",
    "Toggle Selection": "選択を切り替え",
    "Move Selected Groups": "選択中のグループを移動",
    "Move to Position": "指定位置へ移動",
    "Sort Vertex Groups": "頂点グループを並べ替え",
    "Sort by Dictionary": "辞書順に並べ替え",
    "Delete Selected Groups": "選択中のグループを削除",
    "Lock Selected Groups": "選択中のグループのロック",
    "Rename Selected Groups": "選択中のグループをリネーム",
    "Create Opposite Groups": "逆側のグループを生成",
    "Vertex Operations on Selected Groups": "選択中のグループの頂点操作",
    "Copy to Other Objects": "他オブジェクトへコピー",
    "Import Dictionary": "辞書を読み込む",
    "Reload Dictionary": "辞書を再読み込み",
    "Remove Dictionary": "辞書を削除",
    "Export Dictionary": "辞書を書き出す",

    # layout.operator() の text
    "Move Selected to Position...": "選択中を指定位置へ移動...",
    "By Bone": "ボーン順",
    "Reverse": "逆順",
    "Empty Groups Last": "空グループを末尾へ",
    "By Bone Hierarchy (All)": "ボーン階層順 (全体)",
    "Rename...": "リネーム...",
    "Create Opposite Groups...": "逆側のグループを生成...",
    "Copy to Other Objects...": "他オブジェクトへコピー...",
    "Lock": "ロック",
    "Unlock": "ロック解除",
    "Invert Lock": "ロック反転",
    "Delete": "削除",
    "Assign": "割り当て",
    "Remove": "除去",
    "Select": "選択",
    "Deselect": "選択解除",
    "Invert": "反転",
    "Range": "範囲",
}

translations_dict = {
    "ja_JP": {
        **{("*", msgid): text for msgid, text in _JA_DEFAULT.items()},
        **{("Operator", msgid): text for msgid, text in _JA_OPERATOR.items()},
    },
}


def register():
    bpy.app.translations.register(__package__, translations_dict)


def unregister():
    bpy.app.translations.unregister(__package__)
