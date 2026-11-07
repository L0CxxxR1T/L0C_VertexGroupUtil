# SPDX-License-Identifier: GPL-2.0-or-later

"""L/R サフィックスの判定と、逆側の名前の生成。"""

import re

# 「.L」「_r」のようなサフィックス。複製で付く「.001」のような連番が後ろにあってもよい
_SIDE_SUFFIX = re.compile(r"^(?P<base>.+?)(?P<sep>[._])(?P<side>[LlRr])(?P<number>\.\d+)?$")

_OPPOSITE = {"L": "R", "R": "L", "l": "r", "r": "l"}


def side_of(name):
    """サフィックスから 'L' か 'R' を返す。サフィックスがなければ None を返す。"""
    match = _SIDE_SUFFIX.match(name)
    return match["side"].upper() if match else None


def opposite_name(name):
    """区切り文字と大文字小文字を保ったまま L と R を入れ替えた名前を返す。"""
    match = _SIDE_SUFFIX.match(name)
    if match is None:
        return None
    return f"{match['base']}{match['sep']}{_OPPOSITE[match['side']]}{match['number'] or ''}"
