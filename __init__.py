# SPDX-License-Identifier: GPL-2.0-or-later

from . import handlers, ops_batch, ops_select, ops_sort, prefs, state, translations, ui

# state を先に登録しないと、ほかのモジュールが Object.l0c_vgu を参照できない
_modules = (
    translations,
    state,
    prefs,
    ops_select,
    ops_sort,
    ops_batch,
    ui,
    handlers,
)


def register():
    for module in _modules:
        module.register()


def unregister():
    for module in reversed(_modules):
        module.unregister()
