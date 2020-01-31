import pytest

from smb3parse.levels import WORLD_MAP_HEIGHT, WORLD_MAP_SCREEN_WIDTH
from smb3parse.levels.world_map import (
    WorldMap,
    _get_special_enterable_tiles,
    get_all_world_maps,
    list_world_map_addresses,
)
from smb3parse.objects.object_set import WORLD_MAP_OBJECT_SET

world_map_addresses = [0x185BA, 0x1864B, 0x1876C, 0x1891D, 0x18A3E, 0x18B5F, 0x18D10, 0x18E31, 0x19072]
world_map_screen_counts = [1, 2, 3, 2, 2, 3, 2, 4, 1]
world_1_addresses = [
    0x1FB9B,
    0x20F43,
    0x1EE22,
    0x2351A,
    0x1AA5A,
    0x233C1,
    0x2A976,
    0x2EDD0,
    0x1FCAC,
    0x1FA62,
    0x27A43,
    0x1FE61,
    0x2788D,
    0x1FD81,
    0x2AA43,
    0x2FA1B,
    0x21404,
    0x2141E,
    0x2A850,
    0x2EC42,
    0x2FC2E,
    0x2FCD1,
]


TILE_BOWSER_CASTLE = 0xCC  # TILE_BOWSERCASTLELL


@pytest.fixture
def world_1(rom):
    return WorldMap.from_world_number(rom, 1)


@pytest.fixture
def world_8(rom):
    return WorldMap.from_world_number(rom, 8)


def test_list_world_map_addresses(rom):
    assert world_map_addresses == list_world_map_addresses(rom)


def test_list_all_world_maps_address(rom):
    for world_map, world_map_address in zip(get_all_world_maps(rom), world_map_addresses):
        assert world_map.layout_address == world_map_address


def test_list_all_world_maps_object_set(rom):
    for world_map in get_all_world_maps(rom):
        assert world_map.object_set.number == WORLD_MAP_OBJECT_SET


def test_list_all_world_maps_height(rom):
    for world_map in get_all_world_maps(rom):
        assert world_map.height == WORLD_MAP_HEIGHT


def test_list_all_world_maps_screen_counts(rom):
    for world_map, screen_count in zip(get_all_world_maps(rom), world_map_screen_counts):
        assert world_map.screen_count == screen_count


def test_list_all_world_maps_width(rom):
    for world_map, screen_count in zip(get_all_world_maps(rom), world_map_screen_counts):
        assert world_map.width == screen_count * WORLD_MAP_SCREEN_WIDTH


@pytest.mark.parametrize(
    "row, column, level_address, enemy_address, object_set",
    [
        (0, 4, 0x1FB92, 0xC537, 0x1),
        (0, 8, 0x20F3A, 0xC6BA, 0x3),
        (0, 10, 0x1EE19, 0xC2FE, 0x01),
        (2, 10, 0x23511, 0xCC43, 0x4),
        (8, 4, 0x1AA51, 0xC93B, 0xE),
    ],
)
def test_get_level_at_position(world_1, row, column, level_address, enemy_address, object_set):
    level_tile = world_1.level_for_position(1, row, column)

    assert level_tile == (level_address, enemy_address, object_set)


def test_get_level_on_screen_2(rom):
    level_2_4 = (0x29C88, 0xD26F, 0x9)

    world_2 = WorldMap.from_world_number(rom, 2)

    assert world_2.level_for_position(2, 0, 2) == level_2_4


def test_get_level_on_screen_4(world_8):
    assert world_8.level_for_position(4, 5, 12) == (0x2BC3D, 0xD5DD, 0x2)


def test_tile_not_enterable(world_1):
    tile_at_0_0 = world_1._map_tile_for_position(1, 0, 0)

    assert not world_1._is_enterable(tile_at_0_0)


def test_tile_is_enterable(world_1):
    level_1_1 = world_1._map_tile_for_position(1, 0, 4)

    assert world_1._is_enterable(level_1_1)


def test_spade_bonus_is_enterable(world_1):
    spade_bonus_level = world_1._map_tile_for_position(1, 4, 8)

    assert world_1._is_enterable(spade_bonus_level)


def test_castle_is_enterable(world_1):
    castle_level = world_1._map_tile_for_position(1, 6, 12)

    assert world_1._is_enterable(castle_level)


def test_level_count_world_1(world_1):
    assert world_1.level_count_s1 == 0x15
    assert world_1.level_count_s2 == 0x00
    assert world_1.level_count_s3 == 0x00
    assert world_1.level_count_s4 == 0x00


def test_level_count_world_8(world_8):
    assert world_8.level_count_s1 == 0x08
    assert world_8.level_count_s2 == 0x0A
    assert world_8.level_count_s3 == 0x11
    assert world_8.level_count_s4 == 0x06


def test_get_tile(world_1):
    level_1_tile, level_2_tile, level_3_tile, level_4_tile = range(0x03, 0x03 + 4)

    assert world_1._map_tile_for_position(1, 0, 4) == level_1_tile
    assert world_1._map_tile_for_position(1, 0, 8) == level_2_tile
    assert world_1._map_tile_for_position(1, 0, 10) == level_3_tile
    assert world_1._map_tile_for_position(1, 2, 10) == level_4_tile


def test_get_tile_second_screen(rom):
    tile_level_4 = 0x06

    world_2 = WorldMap.from_world_number(rom, 2)

    assert world_2._map_tile_for_position(2, 0, 2) == tile_level_4


def test_get_tile_fourth_screen(world_8):
    bowser_castle = TILE_BOWSER_CASTLE

    assert world_8._map_tile_for_position(4, 5, 12) == bowser_castle


def test_special_enterable_tiles(rom):
    first_special_tile = 0x50  # TILE_TOADHOUSE

    last_special_tile = TILE_BOWSER_CASTLE

    special_enterable_tiles = _get_special_enterable_tiles(rom)

    assert special_enterable_tiles.find(first_special_tile) == 0
    assert special_enterable_tiles.rfind(last_special_tile) == len(special_enterable_tiles) - 1
