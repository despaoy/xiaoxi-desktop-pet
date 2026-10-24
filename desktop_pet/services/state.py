"""Persisted companion preferences without a Tk or renderer dependency."""


class AppState:
    def __init__(self, store):
        self.store = store

    @property
    def focused(self):
        return bool(self.store.get('focused', False))

    def set_focused(self, value):
        if self.focused != bool(value):
            self.store.set('focused', bool(value))

    @property
    def dnd(self):
        return bool(self.store.get('dnd', False))

    def set_dnd(self, value):
        if self.dnd != bool(value):
            self.store.set('dnd', bool(value))
