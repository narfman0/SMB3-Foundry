from bisect import bisect_right
from typing import List, Union, Optional, Tuple

from PySide2.QtCore import Signal, QSize
from PySide2.QtGui import QPaintEvent, QPainter, QPen, QColor, QMouseEvent, Qt, QBrush
from PySide2.QtWidgets import QWidget

from foundry.game.gfx.drawable.Block import Block
from foundry.game.gfx.objects.EnemyItem import EnemyObject
from foundry.game.gfx.objects.LevelObject import SCREEN_WIDTH, SCREEN_HEIGHT, LevelObject
from foundry.game.level.Level import Level
from foundry.game.level.WorldMap import WorldMap
from foundry.gui.ContextMenu import ContextMenu
from foundry.gui.SelectionSquare import SelectionSquare
from foundry.gui.UndoStack import UndoStack

HIGHEST_ZOOM_LEVEL = 8  # on linux, at least
LOWEST_ZOOM_LEVEL = 1 / 16  # on linux, but makes sense with 16x16 blocks

# mouse modes

MODE_FREE = 0
MODE_DRAG = 1
MODE_RESIZE = 2


class LevelView(QWidget):
    # list of jumps
    jumps_created = Signal(list)

    # selected indexes, selected objects
    objects_updated = Signal(list, list)

    selection_changed = Signal()

    def __init__(self, parent: QWidget, context_menu: ContextMenu):
        super(LevelView, self).__init__(parent)

        self.level: Level = None
        self.undo_stack = UndoStack(self)

        self.context_menu = context_menu

        self.grid_lines = False
        self.jumps = False

        self.grid_pen = QPen(QColor(0x80, 0x80, 0x80, 0x80), width=1)
        self.screen_pen = QPen(QColor(0xFF, 0x00, 0x00, 0xFF), width=1)

        self.zoom = 1
        self.block_length = Block.SIDE_LENGTH * self.zoom

        self.changed = False

        self.transparency = True

        self.selection_square = SelectionSquare()

        self.mouse_mode = MODE_FREE

        self.last_mouse_position = 0, 0

        self.drag_start_point = 0, 0

        self.dragging_happened = True

        self.resize_mouse_start_x = 0
        self.resize_obj_start_point = 0, 0

        self.resizing_happened = False

    def mousePressEvent(self, event: QMouseEvent):
        pressed_button = event.button()

        if pressed_button == Qt.LeftButton:
            self.on_left_mouse_button_down(event)
        elif pressed_button == Qt.RightButton:
            self.on_right_mouse_button_down(event)
        else:
            super(LevelView, self).mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent):
        if self.mouse_mode == MODE_DRAG:
            self.dragging(event)
        elif self.mouse_mode == MODE_RESIZE:
            previously_selected_objects = self.level.selected_objects

            self.resizing(event)

            self.level.selected_objects = previously_selected_objects
        elif self.selection_square.active:
            self.set_selection_end(event.pos())
        else:
            super(LevelView, self).mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent):
        released_button = event.button()

        if released_button == Qt.LeftButton:
            self.on_left_mouse_button_up(event)
        elif released_button == Qt.RightButton:
            self.on_right_mouse_button_up(event)
        else:
            super(LevelView, self).mouseReleaseEvent(event)

    def sizeHint(self) -> QSize:
        if self.level is None:
            return super(LevelView, self).sizeHint()
        else:
            width, height = self.level.size

            return QSize(width * self.block_length, height * self.block_length)

    def update(self):
        self.setMinimumSize(self.sizeHint())

        super(LevelView, self).update()

    def on_right_mouse_button_down(self, event: QMouseEvent):
        if self.mouse_mode == MODE_DRAG:
            return

        x, y = event.pos().toTuple()
        level_x, level_y = self.to_level_point(x, y)

        self.last_mouse_position = level_x, level_y

        if self.select_objects_on_click(event):
            self.mouse_mode = MODE_RESIZE

            self.resize_mouse_start_x = level_x

            obj = self.object_at(x, y)

            if obj is not None:
                self.resize_obj_start_point = obj.x_position, obj.y_position

    def resizing(self, event: QMouseEvent):
        self.resizing_happened = True

        if isinstance(self.level, WorldMap):
            return

        x, y = event.pos().toTuple()

        level_x, level_y = self.to_level_point(x, y)

        dx = level_x - self.resize_obj_start_point[0]
        dy = level_y - self.resize_obj_start_point[1]

        self.last_mouse_position = level_x, level_y

        selected_objects = self.get_selected_objects()

        for obj in selected_objects:
            obj.resize_by(dx, dy)

            self.level.changed = True

        self.update()

    def on_right_mouse_button_up(self, event):
        if self.resizing_happened:
            x, y = event.pos().toTuple()

            resize_end_x, _ = self.to_level_point(x, y)

            if self.resize_mouse_start_x != resize_end_x:
                self.stop_resize(event)
        else:
            if self.get_selected_objects():
                menu = self.context_menu.as_object_menu()
            else:
                menu = self.context_menu.as_background_menu()

            self.context_menu.set_position(event.pos())

            menu.popup(event.pos())

        self.resizing_happened = False
        self.mouse_mode = MODE_FREE

    def stop_resize(self, _):
        if self.resizing_happened:
            self.save_level_state()

        self.resizing_happened = False
        self.mouse_mode = MODE_FREE

    def on_left_mouse_button_down(self, event: QMouseEvent):
        if self.mouse_mode == MODE_RESIZE:
            return

        if self.select_objects_on_click(event):
            x, y = event.pos().toTuple()

            obj = self.object_at(x, y)

            if obj is not None:
                self.drag_start_point = obj.x_position, obj.y_position
        else:
            self.start_selection_square(event.pos())

    def dragging(self, event: QMouseEvent):
        self.dragging_happened = True

        x, y = event.pos().toTuple()

        level_x, level_y = self.to_level_point(x, y)

        dx = level_x - self.last_mouse_position[0]
        dy = level_y - self.last_mouse_position[1]

        self.last_mouse_position = level_x, level_y

        selected_objects = self.get_selected_objects()

        for obj in selected_objects:
            obj.move_by(dx, dy)

            self.level.changed = True

        self.update()

    def on_left_mouse_button_up(self, event: QMouseEvent):
        if self.mouse_mode == MODE_DRAG and self.dragging_happened:
            x, y = event.pos().toTuple()

            obj = self.object_at(x, y)

            if obj is not None:
                drag_end_point = obj.x_position, obj.y_position

                if self.drag_start_point != drag_end_point:
                    self.stop_drag()
                else:
                    self.dragging_happened = False
        else:
            self.stop_selection_square()

        self.mouse_mode = MODE_FREE

    def stop_drag(self):
        if self.dragging_happened:
            self.save_level_state()

        self.dragging_happened = False

    def select_objects_on_click(self, event: QMouseEvent) -> bool:
        x, y = event.pos().toTuple()
        level_x, level_y = self.to_level_point(x, y)

        self.last_mouse_position = level_x, level_y

        clicked_object = self.object_at(x, y)

        clicked_on_background = clicked_object is None

        if clicked_on_background:
            self.select_object(None)
        else:
            self.mouse_mode = MODE_DRAG

            selected_objects = self.get_selected_objects()

            nothing_selected = not selected_objects

            if nothing_selected or clicked_object not in selected_objects:
                self.select_object(clicked_object)

        return not clicked_on_background

    def undo(self):
        self.level.from_bytes(*self.undo_stack.undo())

        self.update()

    def redo(self):
        self.level.from_bytes(*self.undo_stack.redo())

        self.update()

    def save_level_state(self):
        self.undo_stack.save_state(self.level.to_bytes())

    def set_zoom(self, zoom):
        if not (LOWEST_ZOOM_LEVEL <= zoom <= HIGHEST_ZOOM_LEVEL):
            return

        self.zoom = zoom
        self.block_length = int(Block.SIDE_LENGTH * self.zoom)

        self.update()

    def zoom_out(self):
        self.set_zoom(self.zoom / 2)

    def zoom_in(self):
        self.set_zoom(self.zoom * 2)

    def start_selection_square(self, position):
        self.selection_square.start(position)

    def set_selection_end(self, position):
        if not self.selection_square.is_active():
            return

        self.selection_square.set_current_end(position)

        sel_rect = self.selection_square.get_adjusted_rect(self.block_length, self.block_length)

        touched_objects = [obj for obj in self.level.get_all_objects() if sel_rect.intersects(obj.get_rect())]

        if touched_objects != self.level.selected_objects:
            self._set_selected_objects(touched_objects)

            self.selection_changed.emit()

        self.update()

    def stop_selection_square(self):
        self.selection_square.stop()

        self.update()

    def select_object(self, obj=None):
        if obj is not None:
            self.select_objects([obj])
        else:
            self.select_objects([])

    def select_objects(self, objects):
        self._set_selected_objects(objects)

        self.update()

    def _set_selected_objects(self, objects):
        self.level.selected_objects = objects

    def get_selected_objects(self) -> List[Union[LevelObject, EnemyObject]]:
        return self.level.selected_objects

    def remove_selected_objects(self):
        for obj in self.level.selected_objects:
            self.level.remove_object(obj)

    def was_changed(self) -> bool:
        if self.level is None:
            return False
        else:
            return self.level.changed

    def level_safe_to_save(self) -> Tuple[bool, str, str]:
        is_safe = True
        reason = ""
        additional_info = ""

        if self.level.too_many_level_objects():
            level = self.cuts_into_other_objects()

            is_safe = False
            reason = "Too many level objects."

            if level:
                additional_info = f"Would overwrite data of '{level}'."
            else:
                additional_info = (
                    "It wouldn't overwrite another level, " "but it might still overwrite other important data."
                )

        elif self.level.too_many_enemies_or_items():
            level = self.cuts_into_other_enemies()

            is_safe = False
            reason = "Too many enemies or items."

            if level:
                additional_info = f"Would probably overwrite enemy/item data of '{level}'."
            else:
                additional_info = (
                    "It wouldn't overwrite enemy/item data of another level, "
                    "but it might still overwrite other important data."
                )

        return is_safe, reason, additional_info

    def cuts_into_other_enemies(self) -> str:
        if self.level is None:
            raise TypeError("Level is None")

        enemies_end = self.level.enemies_end

        levels_by_enemy_offset = sorted(Level.offsets, key=lambda level: level.enemy_offset)

        level_index = bisect_right([level.enemy_offset for level in levels_by_enemy_offset], enemies_end) - 1

        found_level = levels_by_enemy_offset[level_index]

        if found_level.enemy_offset == self.level.enemy_offset:
            return ""
        else:
            return f"World {found_level.game_world} - {found_level.name}"

    def cuts_into_other_objects(self) -> str:
        if self.level is None:
            raise TypeError("Level is None")

        end_of_level_objects = self.level.objects_end

        level_index = (
            bisect_right(
                [level.rom_level_offset - Level.HEADER_LENGTH for level in Level.sorted_offsets], end_of_level_objects
            )
            - 1
        )

        found_level = Level.sorted_offsets[level_index]

        if found_level.rom_level_offset == self.level.object_offset:
            return ""
        else:
            return f"World {found_level.game_world} - {found_level.name}"

    def load_level(
        self, world: int, level: int, object_data_offset: int, enemy_data_offset: int, object_set_number: int
    ):
        if world == 0:
            self.level = WorldMap(level)
        else:
            self.level = Level(world, level, object_data_offset, enemy_data_offset, object_set_number)

            self.objects_updated.emit()

        self.undo_stack.clear(self.level.to_bytes())

        print(f"Drawing {self.level.name}")

    def add_jump(self):
        self.level.add_jump()

        self.objects_updated.emit()

    def from_m3l(self, data: bytearray):
        self.level.from_m3l(data)

        self.objects_updated.emit()

        self.undo_stack.clear(self.level.to_bytes())

    def object_at(self, x: int, y: int) -> Optional[Union[LevelObject, EnemyObject]]:
        level_x, level_y = self.to_level_point(x, y)

        return self.level.object_at(level_x, level_y)

    def to_level_point(self, screen_x: int, screen_y: int) -> Tuple[int, int]:
        level_x = screen_x // self.block_length
        level_y = screen_y // self.block_length

        return level_x, level_y

    def to_screen_point(self, level_x: int, level_y: int) -> Tuple[int, int]:
        screen_x = level_x * self.block_length
        screen_y = level_y * self.block_length

        return screen_x, screen_y

    def index_of(self, obj: Union[LevelObject, EnemyObject]) -> int:
        return self.level.index_of(obj)

    def get_object(self, index: int) -> Union[LevelObject, EnemyObject]:
        return self.level.get_object(index)

    def create_object_at(self, x: int, y: int, domain: int = 0, object_index: int = 0):
        level_x, level_y = self.to_level_point(x, y)

        self.level.create_object_at(level_x, level_y, domain, object_index)

        self.update()

    def create_enemy_at(self, x: int, y: int):
        level_x, level_y = self.to_level_point(x, y)

        self.level.create_enemy_at(level_x, level_y)

    def add_object(self, domain: int, obj_index: int, x: int, y: int, length: int, index: int):
        level_x, level_y = self.to_level_point(x, y)

        self.level.add_object(domain, obj_index, level_x, level_y, length, index)

    def add_enemy(self, enemy_index: int, x: int, y: int, index: int):
        level_x, level_y = self.to_level_point(x, y)

        self.level.add_enemy(enemy_index, level_x, level_y, index)

    def replace_object(self, obj: LevelObject, domain: int, obj_index: int, length: int):
        self.remove_object(obj)

        x, y = obj.get_position()

        self.level.add_object(domain, obj_index, x, y, length, obj.index_in_level)

    def replace_enemy(self, enemy: EnemyObject, enemy_index: int):
        index_in_level = self.level.index_of(enemy)

        self.remove_object(enemy)

        x, y = enemy.get_position()

        self.level.add_enemy(enemy_index, x, y, index_in_level)

    def remove_object(self, obj):
        self.level.remove_object(obj)

    def remove_jump(self, index: int):
        del self.level.jumps[index]
        self.object_updated.emit()
        self.update()

    def paste_objects_at(
        self,
        paste_data: Tuple[List[Union[LevelObject, EnemyObject]], Tuple[int, int]],
        x: Optional[int] = None,
        y: Optional[int] = None,
    ):
        if x is None or y is None:
            level_x, level_y = self.last_mouse_position
        else:
            level_x, level_y = self.to_level_point(x, y)

        objects, origin = paste_data

        ori_x, ori_y = origin

        pasted_objects = []

        for obj in objects:
            obj_x, obj_y = obj.get_position()

            offset_x, offset_y = obj_x - ori_x, obj_y - ori_y

            try:
                pasted_objects.append(self.level.paste_object_at(level_x + offset_x, level_y + offset_y, obj))
            except ValueError:
                print("Tried pasting outside of level.")

        self.select_objects(pasted_objects)

    def get_object_names(self):
        return self.level.get_object_names()

    def make_screenshot(self):
        if self.level is None:
            return

        return self.grab()

    def paintEvent(self, event: QPaintEvent):
        painter = QPainter(self)

        if self.level is None:
            return

        self.level.draw(painter, self.block_length, self.transparency)

        if self.grid_lines:
            panel_width, panel_height = self.size().toTuple()

            painter.setPen(self.grid_pen)

            for x in range(0, panel_width, self.block_length):
                painter.drawLine(x, 0, x, panel_height)
            for y in range(0, panel_height, self.block_length):
                painter.drawLine(0, y, panel_width, y)

            painter.setPen(self.screen_pen)

            if self.level.is_vertical:
                for y in range(0, panel_height, self.block_length * SCREEN_HEIGHT):
                    painter.drawLine(0, y, panel_width, y)
            else:
                for x in range(0, panel_width, self.block_length * SCREEN_WIDTH):
                    painter.drawLine(x, 0, x, panel_height)

        if self.jumps:
            for jump in self.level.jumps:
                painter.setBrush(QBrush(QColor(0xFF, 0x00, 0x00), Qt.FDiagPattern))

                screen = jump.screen_index

                if self.level.is_vertical:
                    painter.drawRect(
                        0,
                        self.block_length * SCREEN_WIDTH * screen,
                        self.block_length * SCREEN_WIDTH,
                        self.block_length * SCREEN_HEIGHT,
                    )
                else:
                    painter.drawRect(
                        self.block_length * SCREEN_WIDTH * screen,
                        0,
                        self.block_length * SCREEN_WIDTH,
                        self.block_length * 27,
                    )

        self.selection_square.draw(painter)

        return
