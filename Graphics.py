import wx

from File import ROM
from Sprite import Block
from m3idefs import TO_THE_SKY, HORIZ_TO_GROUND, HORIZONTAL, TWO_ENDS, UNIFORM, END_ON_TOP_OR_LEFT, \
    END_ON_BOTTOM_OR_RIGHT, HORIZONTAL_2, ENDING, VERTICAL, DIAG_DOWN_LEFT, \
    DIAG_DOWN_RIGHT, DIAG_UP_RIGHT, PYRAMID_TO_GROUND, PYRAMID_2

SKY = 0
GROUND = 27

# todo ground mapping when the objects are actually drawing, rather then when they are created?

# todo what is this, and where should we put it?
OBJECT_SET_TO_ENDING = {
    0: 0,
    1: 0,
    2: 0,
    3: 0,
    7: 0,
    10: 0,
    13: 0,
    14: 0,  # Underground
    15: 0,
    16: 0,
    114: 0,
    4: 1,
    12: 1,
    5: 2,
    9: 2,
    11: 2,
    6: 3,
    8: 3,
}

# todo what is this, exactly?
ENDING_OBJECT_OFFSET = 0x1C8F9

# not all objects provide a block index for blank block
BLANK = -1


class LevelObject:
    # todo better way of saving this information?
    ground_map = []

    def __init__(self, data, object_set, object_definitions, palette_group, graphic_offset=None, common_offset=None):
        self.graphic_offset = graphic_offset
        self.common_offset = common_offset

        self.data = data

        self.object_set = object_set

        self.palette_group = palette_group

        # where to look for the graphic data?
        self.domain = (data[0] & 0b1110_0000) >> 5

        # position relative to the start of the level (top)
        self.y_position = data[0] & 0b0001_1111

        # position relative to the start of the level (left)
        self.x_position = data[1]

        # describes what object it is
        obj_index = data[2]

        self.is_single_block = obj_index <= 0x0F

        domain_offset = self.domain * 0x1F

        if self.is_single_block:
            self.type = obj_index + domain_offset
            self.length = 1
        else:
            self.length = obj_index & 0b0000_1111
            self.type = (obj_index >> 4) + domain_offset + 16 - 1

        self.secondary_length = 0

        object_data = object_definitions[self.type]

        self.width = object_data.bmp_width
        self.height = object_data.bmp_height
        self.orientation = object_data.orientation
        self.ending = object_data.ending
        self.description = object_data.description

        self.blocks = [int(block) for block in object_data.rom_object_design]

        self.block_cache = {}

        self.is_4byte = len(data) == 4

        if self.is_4byte:
            self.secondary_length = self.length
            self.length = data[3]

        self.rect = wx.Rect()

        self._render()

        self.selected = False

    def _render(self):
        if self.rect in LevelObject.ground_map:
            index = LevelObject.ground_map.index(self.rect)
        else:
            index = len(LevelObject.ground_map)

        base_x = self.x_position
        base_y = self.y_position

        new_width = self.width
        new_height = self.height

        blocks_to_draw = []

        if self.orientation == TO_THE_SKY:
            base_x = self.x_position
            base_y = SKY

            for _ in range(self.y_position):
                blocks_to_draw.extend(self.blocks[0:self.width])

            blocks_to_draw.extend(self.blocks[-self.width:])

        elif self.orientation in [DIAG_DOWN_LEFT, DIAG_DOWN_RIGHT, DIAG_UP_RIGHT]:
            if self.ending == UNIFORM:
                new_height = (self.length + 1) * self.height
                new_width = (self.length + 1) * self.width

                left = [BLANK]
                right = [BLANK]
                slopes = self.blocks

            elif self.ending == END_ON_TOP_OR_LEFT:
                new_height = (self.length + 1) * self.height
                new_width = (self.length + 1) * (self.width - 1)  # without fill block

                if self.orientation in [DIAG_DOWN_RIGHT, DIAG_UP_RIGHT]:
                    fill_block = self.blocks[0:1]
                    slopes = self.blocks[1:]

                    left = fill_block
                    right = [BLANK]
                else:
                    fill_block = self.blocks[-1:]
                    slopes = self.blocks[0:-1]

                    left = [BLANK]
                    right = fill_block
            elif self.ending == END_ON_BOTTOM_OR_RIGHT:
                new_height = (self.length + 1) * self.height
                new_width = (self.length + 1) * (self.width - 1)  # without fill block

                fill_block = self.blocks[1:]
                slopes = self.blocks[0:1]

                left = [BLANK]
                right = fill_block
            else:
                # todo other two ends not used with diagonals?
                print(self.description)
                self.rendered_blocks = []
                return

            rows = []

            if self.height > self.width:
                slope_width = self.width
            else:
                slope_width = len(slopes)

            for y in range(new_height):
                r = (y // self.height) * slope_width
                l = new_width - slope_width - r

                offset = y % self.height

                rows.append(l * left + slopes[offset:offset + slope_width] + r * right)

            if self.orientation in [DIAG_UP_RIGHT]:
                for row in rows:
                    row.reverse()

            if self.orientation in [DIAG_DOWN_RIGHT, DIAG_UP_RIGHT]:
                if not self.height > self.width:  # special case for 60 degree platform wire down right
                    rows.reverse()

            if self.orientation in [DIAG_UP_RIGHT]:
                base_y -= (new_height - 1)

            if self.orientation in [DIAG_DOWN_LEFT]:
                base_x -= (new_width - slope_width)

            for row in rows:
                blocks_to_draw.extend(row)

        elif self.orientation in [PYRAMID_TO_GROUND, PYRAMID_2]:
            # since pyramids grow horizontally in both directions when extending
            # we need to check for new ground every time it grows

            base_x += 1  # set the new base_x to the tip of the pyramid

            for y in range(base_y, GROUND):
                new_height = y - base_y
                new_width = 2 * new_height

                bottom_row = wx.Rect(base_x, y, new_width, 1)

                if any([bottom_row.Intersects(rect) and y == rect.GetTop() for rect in
                        LevelObject.ground_map[0:index]]):
                    break

            base_x = base_x - (new_width / 2)

            # todo indexes work for all objects? No, there are left and right fill blocks
            blank = self.blocks[0]
            left_slope = self.blocks[1]
            left_fill = self.blocks[2]
            right_fill = self.blocks[3]
            right_slope = self.blocks[4]

            for y in range(new_height):
                blank_blocks = (new_width // 2) - (y + 1)
                middle_blocks = y  # times two

                blocks_to_draw.extend(blank_blocks * [blank])

                blocks_to_draw.append(left_slope)
                blocks_to_draw.extend(middle_blocks * [left_fill] + middle_blocks * [right_fill])
                blocks_to_draw.append(right_slope)

                blocks_to_draw.extend(blank_blocks * [blank])

        elif self.orientation == ENDING:
            page_width = 16
            page_limit = page_width - self.x_position % page_width

            new_width = (page_width + page_limit)

            for y in range(SKY, GROUND - 1):
                blocks_to_draw.append(self.blocks[0])
                blocks_to_draw.extend([self.blocks[1]] * (new_width - 1))

            # ending graphics
            offset = ENDING_OBJECT_OFFSET + OBJECT_SET_TO_ENDING[self.object_set] * 0x60

            rom = ROM()

            for y in range(6):
                for x in range(page_width):
                    block_index = rom.get_byte(offset + y * page_width + x - 1)
                    blocks_to_draw[(y + 20) * new_width + x + page_limit] = block_index

            # Mushroom/Fire flower/Star is categorized as an enemy

        elif self.orientation == VERTICAL:
            new_height = self.length + 1
            new_width = self.width

            if self.ending == UNIFORM:
                for _ in range(new_height):
                    for x in range(self.width):
                        for y in range(self.height):
                            blocks_to_draw.append(self.blocks[x])

            elif self.ending == END_ON_TOP_OR_LEFT:
                # in case the drawn object is smaller than its actual size
                for y in range(min(self.height, new_height)):
                    offset = y * self.width
                    blocks_to_draw.extend(self.blocks[offset:offset + self.width])

                additional_rows = new_height - self.height

                # assume only the last row needs to repeat
                # todo true for giant blocks?
                if additional_rows > 0:
                    last_row = self.blocks[-self.width:]

                    for _ in range(additional_rows):
                        blocks_to_draw.extend(last_row)

            elif self.ending == END_ON_BOTTOM_OR_RIGHT:
                additional_rows = new_height - self.height

                # assume only the first row needs to repeat
                # todo true for giant blocks?
                if additional_rows > 0:
                    last_row = self.blocks[0:self.width]

                    for _ in range(additional_rows):
                        blocks_to_draw.extend(last_row)

                # in case the drawn object is smaller than its actual size
                for y in range(min(self.height, new_height)):
                    offset = y * self.width
                    blocks_to_draw.extend(self.blocks[offset:offset + self.width])

            elif self.ending == TWO_ENDS:
                # object exists on ships
                top_row = self.blocks[0:self.width]
                bottom_row = self.blocks[-self.width:]

                blocks_to_draw.extend(top_row)

                additional_rows = new_height - 2

                # repeat second to last row
                if additional_rows > 0:
                    for _ in range(additional_rows):
                        blocks_to_draw.extend(self.blocks[-2 * self.width:-self.width])

                if new_height > 1:
                    blocks_to_draw.extend(bottom_row)

        elif self.orientation in [HORIZONTAL, HORIZ_TO_GROUND, HORIZONTAL_2]:
            new_width = self.length + 1

            if self.orientation == HORIZ_TO_GROUND:

                # to the ground only, until it hits something
                for y in range(base_y, GROUND):
                    bottom_row = wx.Rect(base_x, y, new_width, 1)

                    if any([bottom_row.Intersects(rect) and y == rect.GetTop() for rect in LevelObject.ground_map[0:index]]):
                        new_height = y - base_y
                        break
                else:
                    # nothing underneath this object, extend to the ground
                    new_height = GROUND - base_y

                if self.is_single_block:
                    new_width = self.length

            elif self.orientation == HORIZONTAL_2 and self.ending == TWO_ENDS:
                # floating platforms seem to just be one shorter for some reason
                new_width -= 1
            else:
                new_height = self.height + self.secondary_length

            if self.ending == UNIFORM and not self.is_4byte:
                for y in range(new_height):
                    offset = (y % self.height) * self.width

                    for _ in range(0, new_width):
                        blocks_to_draw.extend(self.blocks[offset:offset + self.width])

                # in case of giant blocks
                new_width *= self.width

            elif self.ending == UNIFORM and self.is_4byte:
                # 4 byte objects
                top = self.blocks[0:1]
                bottom = self.blocks[-1:]

                new_height = self.height + self.secondary_length

                # ceilings are one shorter than normal
                if self.height > self.width:
                    new_height -= 1

                blocks_to_draw.extend(new_width * top)

                for _ in range(1, new_height):
                    blocks_to_draw.extend(new_width * bottom)

            elif self.ending == END_ON_TOP_OR_LEFT:
                for y in range(new_height):
                    offset = y * self.width

                    blocks_to_draw.append(self.blocks[offset])

                    for x in range(1, new_width):
                        blocks_to_draw.append(self.blocks[offset + 1])

            elif self.ending == END_ON_BOTTOM_OR_RIGHT:
                for y in range(new_height):
                    offset = y * self.width

                    for x in range(new_width - 1):
                        blocks_to_draw.append(self.blocks[offset])

                    blocks_to_draw.append(self.blocks[offset + self.width - 1])

            elif self.ending == TWO_ENDS:
                top_and_bottom_line = 2

                for y in range(self.height):
                    offset = y * self.width
                    left, *middle, right = self.blocks[offset:offset + self.width]

                    blocks_to_draw.append(left)
                    blocks_to_draw.extend(middle * (new_width - top_and_bottom_line))
                    blocks_to_draw.append(right)

                assert len(blocks_to_draw) % self.height == 0

                new_width = int(len(blocks_to_draw) / self.height)

                top_row = blocks_to_draw[0:new_width]
                bottom_row = blocks_to_draw[-new_width:]

                middle_blocks = blocks_to_draw[new_width:-new_width]

                assert len(middle_blocks) == new_width or len(middle_blocks) == 0

                new_rows = new_height - top_and_bottom_line

                if new_rows >= 0:
                    blocks_to_draw = top_row + middle_blocks * new_rows + bottom_row
            else:
                breakpoint()

        # for not yet implemented objects and single block objects
        if blocks_to_draw:
            self.rendered_blocks = blocks_to_draw
        else:
            self.rendered_blocks = self.blocks

        self.rendered_width = new_width
        self.rendered_height = new_height
        self.rendered_base_x = base_x
        self.rendered_base_y = base_y

        self.rect = wx.Rect(self.rendered_base_x, self.rendered_base_y,
                            self.rendered_width, self.rendered_height)

        LevelObject.ground_map.insert(index, self.rect)

    def draw(self, dc):
        for index, block_index in enumerate(self.rendered_blocks):
            if block_index == BLANK:
                continue

            x = self.rendered_base_x + index % self.rendered_width
            y = self.rendered_base_y + index // self.rendered_width

            self._draw_block(dc, block_index, x, y)

    def _draw_block(self, dc, block_index, x, y):
        if block_index not in self.block_cache:
            if block_index > 0xFF:
                rom_block_index = ROM().get_byte(block_index)  # block_index is an offset into the graphic memory
                block = Block(ROM(), self.object_set, rom_block_index, self.palette_group,
                              self.graphic_offset, self.common_offset)
            else:
                block = Block(ROM(), self.object_set, block_index, self.palette_group,
                              self.graphic_offset, self.common_offset)

            self.block_cache[block_index] = block

        self.block_cache[block_index].draw(dc, x * Block.WIDTH, y * Block.HEIGHT, zoom=1, selected=self.selected)

    def set_position(self, x, y):
        self.x_position = x
        self.y_position = y

        self._render()

    def set_domain(self, domain):
        self.domain = domain

        self._render()

    def __contains__(self, item):
        x, y = item

        return self.point_in(x, y)

    def point_in(self, x, y):
        return self.rect.Contains(x, y)


class EnemyObject:
    def __init__(self, data):
        self.type = data[0]
        self.x_position = data[1]
        self.y_position = data[2]
