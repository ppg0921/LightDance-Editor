import asyncio
import os
from typing import Any, Dict, List, Optional, Set, cast

import bpy

from ....client import client
from ....properties.types import LightType, ObjectType
from ...actions.property.revision import update_rev_changes
from ...config import config
from ...models import DancersArrayPartsItem, PartType
from ...states import state
from ...utils.convert import rgb_to_float
from ...utils.ui import set_dopesheet_filter
from ..property.animation_data import (
    set_ctrl_keyframes_from_state,
    set_pos_keyframes_from_state,
)

asset_path = cast(
    str, bpy.context.preferences.filepaths.asset_libraries["User Library"].path
)
target_path = os.path.join(asset_path, "LightDance")


def set_bpy_props(obj: bpy.types.Object, **props: Any):
    for key, value in props.items():
        setattr(obj, key, value)


def parse_config(config_dict: Dict[str, Any]):
    stage_config = config_dict["Stage"]

    setattr(config, "stage_width", cast(float, stage_config["width"]))
    setattr(config, "stage_length", cast(float, stage_config["length"]))
    setattr(config, "stage_scale", cast(float, stage_config["scale"]))


async def fetch_data(reload: bool = False):
    """
    Fetch assets from editor-server
    param reload: Fetch assets again even they already exist is true, otherwise only fetch missing assets.
    """
    print("fetching data")
    use_draco = False

    if client.file_client:
        assets_load: Dict[str, Any] = await client.download_json("/data/load.json")

        try:
            url_set: Set[str] = set()
            for tag in ["Waveform", "Music", "LightPresets", "PosPresets"]:
                url_set.add(assets_load[tag])

            for key in assets_load["DancerMap"]:
                raw_url = assets_load["DancerMap"][key]["url"]
                if use_draco:
                    model_url = raw_url
                else:
                    model_url = "".join(raw_url.split(".draco"))
                    assets_load["DancerMap"][key]["url"] = model_url

                url_set.add(model_url)

            parse_config(assets_load["Config"])

            for url in url_set:
                file_path = os.path.normpath(target_path + url)
                file_dir = os.path.dirname(file_path)
                if os.path.isfile(file_path) and not reload:
                    continue

                if not os.path.exists(file_dir):
                    os.makedirs(file_dir)
                    print("created folder: ", file_dir)

                data = await client.download_binary(url)
                print("fetched file ", url, "from server")
                with open(file_path, "w+b") as file:
                    file.write(data)

        except Exception as e:
            print(e)

    else:
        raise Exception("File client is not initialized")

    return assets_load


async def import_model_to_asset(
    model_name: str, model_filepath: str, parts: List[DancersArrayPartsItem]
):
    """
    set dancer collection asset
    """
    bpy.ops.import_scene.gltf(
        filepath=model_filepath
    )  # here all parts of dancer is selected
    while True:
        model_objs = getattr(bpy.context, "selected_objects", None)
        if model_objs is None:
            await asyncio.sleep(0.1)
        else:
            break

    model_objs = cast(List[bpy.types.Object], model_objs)

    col = bpy.data.collections.new(model_name)
    for obj in model_objs:
        for old_col in obj.users_collection:
            old_col.objects.unlink(obj)
        col.objects.link(obj)

        # avoid part name conflict
        obj.name = f"{model_name}.{obj.name}"

    # Clean meshes
    sphere_mesh = find_first_mesh("Sphere")
    if sphere_mesh is not None:
        sphere_mesh.name = f"{model_name}.Sphere"

        for obj in model_objs:
            if obj.type == "EMPTY":
                continue
            if "Sphere" in obj.data.name and obj.data != sphere_mesh:
                old_mesh = cast(bpy.types.Mesh, obj.data)
                obj.data = sphere_mesh
                bpy.data.meshes.remove(old_mesh, do_unlink=True)

    human_mesh = find_first_mesh("human")
    if human_mesh is not None:
        human_mesh.name = f"{model_name}.Human"

    for obj in model_objs:
        if obj.type == "EMPTY":
            continue
        mesh = obj.data
        if "BezierCurve" in mesh.name and model_name not in mesh.name:
            mesh.name = f"{model_name}.{mesh.name}"

    col.asset_mark()
    for part in parts:
        part_objects = [
            part_obj for part_obj in model_objs if part_obj.name.find(part.name) >= 0
        ]
        if len(part_objects) == 0:
            print("Dancer part not found (maybe should reload asset)")

    bpy.ops.outliner.orphans_purge(do_recursive=True)
    print(f"Model: {model_name} imported")

    # for obj in col.all_objects:
    #     print(obj.name)


def find_first_mesh(mesh_name: str) -> Optional[bpy.types.Mesh]:
    data_meshes = cast(Dict[str, bpy.types.Mesh], bpy.data.meshes)
    mesh = data_meshes.get(mesh_name)

    if mesh is None:
        candidates = [name for name in data_meshes.keys() if name.find(mesh_name) == 0]
        if len(candidates) == 0:
            return None

        numbers = [int(name.split(".")[-1]) for name in candidates]
        mesh = data_meshes[candidates[numbers.index(min(numbers))]]

    return mesh


async def setup_objects(assets_load: Dict[str, Any]):
    """
    clear all objects in viewport
    """
    data_objects = cast(Dict[str, bpy.types.Object], bpy.data.objects)

    for old_obj in data_objects.values():
        if old_obj.visible_get() and not hasattr(old_obj, "ld_dancer_name"):
            bpy.data.objects.remove(old_obj)

    """
    set dancer objects
    """
    data_objects = cast(Dict[str, bpy.types.Object], bpy.data.objects)

    if check_local_object_list():
        print("local objects detected")
        return
    else:
        for old_obj in data_objects.values():
            if old_obj.visible_get():
                bpy.data.objects.remove(old_obj)

    dancer_array = state.dancers_array
    for dancer in dancer_array:
        dancer_name = dancer.name
        dancer_index = dancer_name.split("_")[0]
        dancer_load = assets_load["DancerMap"][dancer_name]
        if dancer_name in bpy.context.scene.objects.keys():
            continue

        model_file: str = dancer_load["url"]
        model_filepath = os.path.normpath(target_path + model_file)
        model_name: str = dancer_load["modelName"]

        if model_name not in bpy.data.collections.keys():
            await import_model_to_asset(model_name, model_filepath, dancer.parts)

        data_objects = cast(Dict[str, bpy.types.Object], bpy.data.objects)
        dancer_asset = cast(bpy.types.Collection, bpy.data.collections[model_name])
        dancer_asset_objects = {
            cast(str, obj.name): obj
            for obj in cast(List[bpy.types.Object], dancer_asset.all_objects)
        }

        asset_dancer_obj = dancer_asset_objects.get(f"{model_name}.{model_name}")
        if asset_dancer_obj is None:
            print(f"Dancer {dancer_name} not found in asset")
            continue

        dancer_obj = cast(bpy.types.Object, asset_dancer_obj.copy())
        set_bpy_props(
            dancer_obj,
            name=dancer_name,
            empty_display_size=0,
            ld_dancer_name=dancer.name,
            ld_model_name=model_name,
            ld_object_type=ObjectType.DANCER.value,
        )
        bpy.context.scene.collection.objects.link(dancer_obj)

        asset_human_obj = dancer_asset_objects.get(f"{model_name}.Human")
        if asset_human_obj is None:
            print(f"Human not found in dancer {dancer_name}")
            continue

        human_obj = cast(bpy.types.Object, asset_human_obj.copy())
        set_bpy_props(
            human_obj,
            name=f"{dancer_index}_Human",
            parent=dancer_obj,
            color=(0, 0, 0, 1),
            ld_object_type=ObjectType.HUMAN.value,
            ld_dancer_name=dancer.name,
            ld_model_name=model_name,
        )
        bpy.context.scene.collection.objects.link(human_obj)

        for part_item in dancer.parts:
            asset_part_obj_name = f"{model_name}.{part_item.name}"
            asset_part_obj = dancer_asset_objects.get(asset_part_obj_name)
            if asset_part_obj is None:
                print(f"Object {asset_part_obj_name} not found in dancer {dancer_name}")
                continue

            part_obj = cast(bpy.types.Object, asset_part_obj.copy())
            part_obj_name = f"{dancer_index}_{part_item.name}"

            if part_item.type.value == "LED":
                set_bpy_props(
                    part_obj,
                    name=part_obj_name,
                    parent=dancer_obj,
                    empty_display_size=0,
                    ld_object_type=ObjectType.LIGHT.value,
                    ld_light_type=LightType.LED.value,
                    ld_part_name=part_item.name,
                    ld_dancer_name=dancer.name,
                    ld_model_name=model_name,
                )
                bpy.context.scene.collection.objects.link(part_obj)

                length = part_item.length
                if length is None:
                    print(
                        f"LED part {part_item.name} length not found in dancer {dancer_name}"
                    )
                    continue

                for position in range(length):
                    asset_sub_obj_name = f"{asset_part_obj_name}.{position:03}"
                    asset_led_obj = dancer_asset_objects.get(asset_sub_obj_name)
                    if asset_led_obj is None:
                        print(
                            f"LED part {part_item.name} position {position} not found in dancer {dancer_name}"
                        )
                        continue

                    led_obj = cast(bpy.types.Object, asset_led_obj.copy())
                    sub_obj_name = f"{part_obj_name}.{position:03}"

                    set_bpy_props(
                        led_obj,
                        name=sub_obj_name,
                        parent=part_obj,
                        color=(0, 0, 0, 1),
                        ld_object_type=ObjectType.LIGHT.value,
                        ld_light_type=LightType.LED_BULB.value,
                        ld_part_name=part_item.name,
                        ld_dancer_name=dancer.name,
                        ld_model_name=model_name,
                        ld_led_pos=position,
                    )
                    bpy.context.scene.collection.objects.link(led_obj)

            elif part_item.type.value == "FIBER":
                set_bpy_props(
                    part_obj,
                    name=part_obj_name,
                    parent=dancer_obj,
                    color=(0, 0, 0, 1),
                    ld_object_type=ObjectType.LIGHT.value,
                    ld_light_type=LightType.FIBER.value,
                    ld_part_name=part_item.name,
                    ld_dancer_name=dancer.name,
                    ld_model_name=model_name,
                )
                bpy.context.scene.collection.objects.link(part_obj)


def setup_floor():
    data_objects = cast(Dict[str, bpy.types.Object], bpy.data.objects)

    # Create floor
    stage_scale: float = getattr(config, "stage_scale")
    stage_width: float = getattr(config, "stage_width") * stage_scale
    stage_length: float = getattr(config, "stage_length") * stage_scale
    stage_stroke = 0.02
    stage_color = (*rgb_to_float((38, 123, 216)), 1)

    edge_locations = [
        (0, stage_width / 2, 0),
        (0, -stage_width / 2, 0),
        (stage_length / 2, 0, 0),
        (-stage_length / 2, 0, 0),
    ]
    edge_scales = [
        (stage_length + stage_stroke, stage_stroke, stage_stroke),
        (stage_length + stage_stroke, stage_stroke, stage_stroke),
        (stage_stroke, stage_width + stage_stroke, stage_stroke),
        (stage_stroke, stage_width + stage_stroke, stage_stroke),
    ]

    for i in range(4):
        name = f"FloorEdge{i}"
        if data_objects.get(name) is not None:
            bpy.data.objects.remove(data_objects[name])

        bpy.ops.mesh.primitive_cube_add(size=1)
        edge_obj = bpy.context.object
        edge_obj.name = f"FloorEdge{i}"
        edge_obj.location = edge_locations[i]
        edge_obj.scale = edge_scales[i]
        edge_obj.color = cast(bpy.types.bpy_prop_array, stage_color)
        edge_obj.hide_select = True

    for obj in cast(List[bpy.types.Object], bpy.context.view_layer.objects.selected):
        obj.select_set(False)


def setup_render():
    """
    clean render settings
    """
    bpy.context.scene.render.fps = 1000
    bpy.context.scene.render.fps_base = 1.0

    bpy.context.scene.render.use_simplify = True
    bpy.context.scene.render.simplify_subdivision = 0
    bpy.context.scene.render.simplify_volumes = 0
    bpy.context.scene.render.simplify_shadows = 0
    bpy.context.scene.render.simplify_child_particles_render = 0
    bpy.context.scene.eevee.gi_diffuse_bounces = 0


def setup_music(assets_load: Dict[str, Any]):
    """
    set music
    """
    scene = bpy.context.scene
    if not scene.sequence_editor:
        scene.sequence_editor_create()
    music_filepath = os.path.normpath(target_path + assets_load["Music"])
    if scene.sequence_editor.sequences:
        sequence = cast(bpy.types.SoundSequence, scene.sequence_editor.sequences[0])
        scene.sequence_editor.sequences.remove(sequence)

    strip = scene.sequence_editor.sequences.new_sound(
        "music", filepath=music_filepath, channel=1, frame_start=0
    )

    # set frame range
    bpy.context.scene.frame_start = 0
    bpy.context.scene.frame_end = bpy.context.scene.sequence_editor.sequences[
        0
    ].frame_duration

    # set retiming
    duration = strip.frame_duration

    strip.select = True
    bpy.context.scene.sequence_editor.active_strip = strip

    bpy.ops.sequencer.retiming_reset()
    bpy.ops.sequencer.retiming_key_add()
    bpy.ops.sequencer.retiming_key_add(timeline_frame=duration)
    bpy.ops.sequencer.retiming_segment_speed_set()

    bpy.context.window_manager["ld_play_speed"] = 1.0


# WARNING: This function will crash for now
def close_area(screen: bpy.types.Screen, area_ui_type: str):
    try:
        area = next(
            area
            for area in cast(List[bpy.types.Area], screen.areas)
            if area.ui_type == area_ui_type
        )

        ctx = cast(Dict[str, Any], bpy.context.copy())
        ctx["screen"] = screen
        ctx["area"] = area
        ctx["region"] = area.regions[-1]

        with bpy.context.temp_override(**ctx):
            bpy.ops.screen.area_close()

    except StopIteration:
        pass


def split_area(
    screen: bpy.types.Screen, area_ui_type: str, direction: str, factor: float
):
    try:
        area = next(
            area
            for area in cast(List[bpy.types.Area], screen.areas)
            if area.ui_type == area_ui_type
        )

        ctx = cast(Dict[str, Any], bpy.context.copy())
        ctx["screen"] = screen
        ctx["area"] = area
        ctx["region"] = area.regions[-1]

        with bpy.context.temp_override(**ctx):
            bpy.ops.screen.area_split(direction=direction, factor=factor)

    except StopIteration:
        pass


def get_area(
    screen: bpy.types.Screen, area_ui_type: str, sort_by: str = "x", index: int = 0
) -> Optional[bpy.types.Area]:
    areas = [
        area
        for area in cast(List[bpy.types.Area], screen.areas)
        if area.ui_type == area_ui_type
    ]

    if sort_by == "x":
        areas.sort(key=lambda area: area.x)
    elif sort_by == "y":
        areas.sort(key=lambda area: area.y)

    if index < 0 or index >= len(areas):
        return None

    return areas[index]


def setup_display():
    screen = bpy.context.screen

    """
    Setup layout
    """
    # split_area(screen, "VIEW_3D", "HORIZONTAL", 0.3)
    # timeline_area = get_area(screen, "VIEW_3D", "y", 0)
    # if timeline_area is None:
    #     return
    # timeline_area.ui_type = "TIMELINE"
    #
    # split_area(screen, "VIEW_3D", "VERTICAL", 0.8)
    # outliner_area = get_area(screen, "VIEW_3D", "x", 1)
    # if outliner_area is None:
    #     return
    # outliner_area.ui_type = "OUTLINER"

    """
    3d viewport
    """
    view_3d_area = get_area(screen, "VIEW_3D")
    if view_3d_area is None:
        return

    view_3d_area.show_menus = False

    space = cast(bpy.types.SpaceView3D, view_3d_area.spaces.active)

    space.overlay.show_relationship_lines = False
    space.overlay.show_cursor = False
    space.overlay.show_bones = False
    space.overlay.show_motion_paths = False
    space.overlay.show_object_origins = False
    space.overlay.show_extras = False
    # space.overlay.show_floor = False

    space.shading.background_type = "VIEWPORT"
    space.shading.background_color = (0, 0, 0)
    space.shading.color_type = "OBJECT"
    space.shading.light = "FLAT"
    # space.shading.light = "STUDIO"
    # space.shading.studio_light = "paint.sl"

    space.show_region_ui = True
    # space.show_region_header = False
    space.show_region_toolbar = False
    space.show_region_tool_header = False

    """
    scene
    """
    bpy.context.scene.tool_settings.use_keyframe_insert_auto = False
    bpy.context.scene.show_keys_from_selected_only = False
    bpy.context.scene.sync_mode = "AUDIO_SYNC"

    """
    timeline
    """
    timeline = get_area(screen, "TIMELINE")
    if timeline is None:
        return

    timeline.show_menus = False

    space = cast(bpy.types.SpaceDopeSheetEditor, timeline.spaces.active)

    space.show_seconds = False

    space.show_region_ui = True
    # space.show_region_header = False
    space.show_region_channels = False

    set_dopesheet_filter("control_frame")  # follow default editor

    """
    Outliner
    """
    outliner = get_area(screen, "OUTLINER")
    if outliner is None:
        return

    outliner.show_menus = False

    space = cast(bpy.types.SpaceOutliner, outliner.spaces.active)

    space.filter_state = "SELECTABLE"
    space.use_filter_collection = False
    space.use_filter_object_content = False
    space.use_sort_alpha = True

    space.show_restrict_column_hide = False
    space.show_restrict_column_enable = False
    space.show_restrict_column_select = False
    space.show_restrict_column_viewport = False
    space.show_restrict_column_render = False
    space.show_restrict_column_holdout = False
    space.show_restrict_column_indirect_only = False


def clear_animation_data():
    data_objects = cast(List[bpy.types.Object], bpy.data.objects)
    for obj in data_objects:
        obj.animation_data_clear()

    setattr(bpy.context.scene, "ld_anidata", False)
    bpy.context.scene.animation_data_clear()
    bpy.context.window_manager.animation_data_clear()


def setup_animation_data():
    if not getattr(bpy.context.scene, "ld_anidata"):
        set_pos_keyframes_from_state()
        set_ctrl_keyframes_from_state()
        setattr(bpy.context.scene, "ld_anidata", True)
    else:
        print("local animation data detected")
        try:
            update_rev_changes(state.pos_map, state.control_map)
        except:
            clear_animation_data()
            set_pos_keyframes_from_state()
            set_ctrl_keyframes_from_state()
            setattr(bpy.context.scene, "ld_anidata", True)


def check_local_object_list():
    data_objects = cast(Dict[str, bpy.types.Object], bpy.data.objects)

    for dancer_item in state.dancers_array:
        dancer_name = dancer_item.name
        if dancer_name not in bpy.data.objects.keys():
            return False

        dancer_parts = dancer_item.parts
        dancer_index = dancer_name.split("_")[0]
        for part_item in dancer_parts:
            part_name = part_item.name
            part_type = part_item.type
            part_obj_name = f"{dancer_index}_{part_name}"

            match part_type:
                case PartType.LED:
                    part_parent = data_objects.get(part_obj_name)
                    if part_parent is None:
                        return False

                    if len(part_parent.children) != part_item.length:
                        return False

                case PartType.FIBER:
                    if part_obj_name not in data_objects.keys():
                        return False

    return True


async def load_data() -> None:
    state.assets_path = target_path

    state.init_message = "Fetching data"
    assets_load = await fetch_data()

    setup_render()
    setup_display()

    state.init_message = "Setting up objects"
    await setup_objects(assets_load)
    setup_floor()

    state.init_message = "Setting up music"
    setup_music(assets_load)

    state.init_message = "Setting up animation"
    setup_animation_data()

    print("Data loaded")
