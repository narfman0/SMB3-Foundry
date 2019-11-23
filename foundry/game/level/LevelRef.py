from typing import Optional

from PySide2.QtCore import SignalInstance, Signal, QObject

from foundry.game.level.Level import Level
from foundry.gui.UndoStack import UndoStack


class LevelRef(QObject):
    data_changed: SignalInstance = Signal()
    jumps_changed: SignalInstance = Signal()

    def __init__(self):
        super(LevelRef, self).__init__()
        self._internal_level: Optional[Level] = None

        self.undo_stack = UndoStack()

    def load_level(
        self, world: int, level: int, object_data_offset: int, enemy_data_offset: int, object_set_number: int
    ):
        self._internal_level = Level(world, level, object_data_offset, enemy_data_offset, object_set_number)

        self._internal_level.data_changed.connect(self.data_changed.emit)
        self._internal_level.jumps_changed.connect(self.jumps_changed.emit)

        self.undo_stack.clear(self._internal_level.to_bytes())

        self.data_changed.emit()

    @property
    def level(self):
        return self._internal_level

    @property
    def selected_objects(self):
        return [obj for obj in self._internal_level.get_all_objects() if obj.selected]

    @selected_objects.setter
    def selected_objects(self, selected_objects):
        if sorted(selected_objects) == self.selected_objects:
            return

        for obj in self._internal_level.get_all_objects():
            obj.selected = obj in selected_objects

        self.data_changed.emit()

    def __getattr__(self, item: str):
        try:
            return self.__dict__[item]
        except KeyError:
            if self._internal_level is None:
                return None
            else:
                return getattr(self._internal_level, item)

    def undo(self):
        self._internal_level.from_bytes(*self.undo_stack.undo())

        self.data_changed.emit()

    def redo(self):
        self.level.from_bytes(*self.undo_stack.redo())

        self.data_changed.emit()

    def save_level_state(self):
        self.undo_stack.save_level_state(self._internal_level.to_bytes())

    def __bool__(self):
        return self._internal_level is not None