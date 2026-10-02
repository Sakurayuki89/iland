"""Render the Island failed-catch showcase: approach, three gauge misses, a butterfly
flee, a puzzled cat, then the dusk-to-night firefly ending.

Run: "C:/Program Files/Blender Foundation/Blender 4.2/blender.exe" -b --factory-startup -P tools/blender_demo.py -- --out docs/img/devlog/previs.mp4
"""

import json
import math
import random
import sys
from pathlib import Path

import bpy
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
PX, FPS, FRAMES, W, H = 96.0, 24, 384, 20.0, 11.25


def argument(name, fallback):
    args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    return Path(args[args.index(name) + 1]).resolve() if name in args else Path(fallback).resolve()


OUT = argument("--out", ROOT / "docs/img/devlog/previs.mp4")


def f(seconds):
    return max(1, min(FRAMES, round(seconds * FPS) + 1))


def game_xy(x, y):
    return x / 48.0 - W / 2.0, H / 2.0 - y / 48.0


def depth(y, extra=0.0):
    """Lower game-screen feet are always in front."""
    return 0.08 + y * 0.004 + extra


def constant(data):
    animation = getattr(data, "animation_data", None)
    if animation and animation.action:
        for curve in animation.action.fcurves:
            for point in curve.keyframe_points:
                point.interpolation = "CONSTANT"


def linear(data):
    animation = getattr(data, "animation_data", None)
    if animation and animation.action:
        for curve in animation.action.fcurves:
            for point in curve.keyframe_points:
                point.interpolation = "LINEAR"


def configure_scene():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_EEVEE_NEXT"
    scene.render.resolution_x, scene.render.resolution_y = 1280, 720
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "FFMPEG"
    scene.render.ffmpeg.format, scene.render.ffmpeg.codec = "MPEG4", "H264"
    scene.render.ffmpeg.constant_rate_factor = "MEDIUM"
    scene.render.fps, scene.frame_start, scene.frame_end = FPS, 1, FRAMES
    scene.view_settings.view_transform, scene.view_settings.look = "Standard", "None"
    scene.world.color = (0.03, 0.05, 0.04)
    scene["tint_r"], scene["tint_g"], scene["tint_b"] = 1.0, 1.0, 1.0
    bpy.ops.object.camera_add(location=(0, 0, 20))
    camera = bpy.context.object
    camera.name, camera.data.type, camera.data.ortho_scale = "TopDownCamera", "ORTHO", W
    scene.camera = camera  # Default camera rotation looks straight down local -Z.

    group = bpy.data.node_groups.new("SceneTint", "ShaderNodeTree")
    group.interface.new_socket(name="Color", in_out="INPUT", socket_type="NodeSocketColor")
    group.interface.new_socket(name="Tint", in_out="INPUT", socket_type="NodeSocketColor")
    group.interface.new_socket(name="Color", in_out="OUTPUT", socket_type="NodeSocketColor")
    inp, mix, out = group.nodes.new("NodeGroupInput"), group.nodes.new("ShaderNodeMixRGB"), group.nodes.new("NodeGroupOutput")
    mix.blend_type, mix.inputs[0].default_value = "MULTIPLY", 1.0
    group.links.new(inp.outputs["Color"], mix.inputs[1]); group.links.new(inp.outputs["Tint"], mix.inputs[2]); group.links.new(mix.outputs[0], out.inputs["Color"])
    return scene, group


SCENE, TINT_GROUP = configure_scene()
IMAGES, CROPS = {}, {}


def image(path):
    key = str(Path(path).resolve())
    if key not in IMAGES:
        IMAGES[key] = bpy.data.images.load(key, check_existing=True)
        IMAGES[key].colorspace_settings.name = "sRGB"
    return IMAGES[key]


def tint_driver(socket, component):
    driver = socket.driver_add("default_value", component).driver
    driver.type = "SCRIPTED"
    var = driver.variables.new(); var.name = "scene"
    var.targets[0].id_type, var.targets[0].id = "SCENE", SCENE
    var.targets[0].data_path = '["tint_%s"]' % "rgb"[component]
    driver.expression = "scene"


def material(name, img, opacity=1.0):
    mat = bpy.data.materials.new(name); mat.use_nodes = True
    if hasattr(mat, "surface_render_method"):
        mat.surface_render_method = "DITHERED"
    nodes, links = mat.node_tree.nodes, mat.node_tree.links; nodes.clear()
    output, mix = nodes.new("ShaderNodeOutputMaterial"), nodes.new("ShaderNodeMixShader")
    transparent, emission, tex = nodes.new("ShaderNodeBsdfTransparent"), nodes.new("ShaderNodeEmission"), nodes.new("ShaderNodeTexImage")
    tex.image = img
    tint = nodes.new("ShaderNodeGroup"); tint.node_tree, tint.name = TINT_GROUP, "SceneTint"
    for component in range(3): tint_driver(tint.inputs["Tint"], component)
    value = nodes.new("ShaderNodeValue"); value.name, value.outputs[0].default_value = "Opacity", opacity
    alpha = nodes.new("ShaderNodeMath"); alpha.operation = "MULTIPLY"
    links.new(tex.outputs["Color"], tint.inputs["Color"]); links.new(tint.outputs["Color"], emission.inputs["Color"])
    links.new(tex.outputs["Alpha"], alpha.inputs[0]); links.new(value.outputs[0], alpha.inputs[1]); links.new(alpha.outputs[0], mix.inputs[0])
    links.new(transparent.outputs[0], mix.inputs[1]); links.new(emission.outputs[0], mix.inputs[2]); links.new(mix.outputs[0], output.inputs["Surface"])
    return mat


def flat_material(name, color, opacity):
    img = bpy.data.images.new(name + "Color", 1, 1, alpha=True)
    img.pixels.foreach_set((*color, opacity))
    return material(name, img)


def plane(name, width, height, mat, location=(0, 0, 0), flip=False, uv_scale=(1, 1)):
    verts, faces = [(-width/2, -height/2, 0), (width/2, -height/2, 0), (width/2, height/2, 0), (-width/2, height/2, 0)], [(0, 1, 2, 3)]
    mesh = bpy.data.meshes.new(name + "Mesh"); mesh.from_pydata(verts, [], faces); mesh.uv_layers.new(name="UV")
    uvs = [(1, 0), (0, 0), (0, 1), (1, 1)] if flip else [(0, 0), (1, 0), (1, 1), (0, 1)]
    uvs = [(u * uv_scale[0], v * uv_scale[1]) for u, v in uvs]
    for loop, uv in zip(mesh.uv_layers[0].data, uvs): loop.uv = uv
    obj = bpy.data.objects.new(name, mesh); bpy.context.collection.objects.link(obj)
    obj.location = location
    obj.data.materials.append(mat)
    return obj


def image_plane(name, path, feet, world=None, origin=(.5, .95), extra=0.0, opacity=1.0):
    img = image(path); world = world or (img.size[0] / 2, img.size[1] / 2)
    width, height = world[0] / 48, world[1] / 48
    x, y = game_xy(*feet)
    return plane(name, width, height, material(name + "Mat", img, opacity), (x + (.5-origin[0])*width, y + (origin[1]-.5)*height, depth(feet[1], extra)))


def crop(atlas_path, frame_name, atlas):
    key = (str(atlas_path), frame_name)
    if key in CROPS: return CROPS[key]
    frame = atlas["frames"][frame_name]["frame"]; source = image(atlas_path)
    pixels = np.empty(source.size[0] * source.size[1] * 4, dtype=np.float32); source.pixels.foreach_get(pixels)
    pixels = pixels.reshape((source.size[1], source.size[0], 4)); y0 = source.size[1] - frame["y"] - frame["h"]
    img = bpy.data.images.new("Frame_" + frame_name, frame["w"], frame["h"], alpha=True)
    img.pixels.foreach_set(np.ascontiguousarray(pixels[y0:y0+frame["h"], frame["x"]:frame["x"]+frame["w"]]).reshape(-1)); img.pack()
    CROPS[key] = img; return img


def atlas_plane(name, path, atlas, frame_name, parent, flip=False):
    info = atlas["frames"][frame_name]; rect, src, pivot, size = info["frame"], info["spriteSourceSize"], info["pivot"], info["sourceSize"]
    raw_x = (src["x"] + rect["w"]/2 - pivot["x"]*size["w"]) / PX
    raw_y = (pivot["y"]*size["h"] - (src["y"] + rect["h"]/2)) / PX
    obj = plane(name, rect["w"]/PX, rect["h"]/PX, material(name+"Mat", crop(path, frame_name, atlas)), ((-raw_x) if flip else raw_x, raw_y, 0), flip)
    obj.parent = parent; return obj


def new_rig(name):
    obj = bpy.data.objects.new(name, None); bpy.context.collection.objects.link(obj); return obj


def key_rig(obj, frame, x, y):
    obj.location = (*game_xy(x, y), depth(y, .01)); obj.keyframe_insert(data_path="location", frame=frame)


def key_hide(obj, frame, value):
    obj.hide_render = value; obj.keyframe_insert(data_path="hide_render", frame=frame)


def opacity(obj, frame, value):
    socket = obj.data.materials[0].node_tree.nodes["Opacity"].outputs[0]; socket.default_value = value; socket.keyframe_insert(data_path="default_value", frame=frame)


def visible_between(obj, start, end):
    for frame, value in ((1, True), (start, False), (end+1, True)): key_hide(obj, frame, value)


def animated_sprite(name, path, atlas, animations, rig):
    objects = {}
    for action in animations["anims"]:
        for item in action["frames"]:
            key = (item["frame"], action.get("flipX", False))
            if key not in objects: objects[key] = atlas_plane(name + "_" + item["frame"] + ("_flip" if key[1] else ""), path, atlas, item["frame"], rig, key[1])
    return objects, {action["key"]: action for action in animations["anims"]}


def show(objects, action, frame):
    index = int((frame-1) / FPS * action["frameRate"]) % len(action["frames"])
    selected = (action["frames"][index]["frame"], action.get("flipX", False))
    for key, obj in objects.items(): key_hide(obj, frame, key != selected)


def show_frame(objects, frame_name, frame, flip=False):
    for key, obj in objects.items(): key_hide(obj, frame, key != (frame_name, flip))


def smoothstep(value):
    value = max(0.0, min(1.0, value)); return value * value * (3.0 - 2.0 * value)


def key_ui(obj, frame, x, y, extra=2.0):
    obj.location = (*game_xy(x, y), depth(y, extra)); obj.keyframe_insert(data_path="location", frame=frame)


def irregular_flight():
    """Seeded little flight phrases; each post-dart phrase gets a new home."""
    rng, phrases = random.Random(7), []
    for start, end, home in ((0.0, 4.2, (470, 320)), (4.45, 6.4, (565, 230)), (6.65, 8.6, (500, 290)), (8.85, 9.9, (540, 370))):
        at, previous = start, home
        while at < end:
            duration = rng.uniform(.35, .7)
            target = (home[0] + rng.uniform(-45, 45), home[1] + rng.uniform(-45, 45))
            if rng.random() < .27: target, duration = previous, rng.uniform(.2, .3)  # a brief hover
            phrases.append((at, min(end, at + duration), previous, target))
            at, previous = at + duration, target
    return phrases


FLIGHT = irregular_flight()


def flutter(second):
    for index, (start, end, first, last) in enumerate(FLIGHT):
        if start <= second <= end:
            amount = smoothstep((second - start) / max(.001, end - start))
            x, y = first[0] + (last[0] - first[0]) * amount, first[1] + (last[1] - first[1]) * amount
            return x, y + math.sin(second * 14) * 4, last[0] - first[0]
        if end <= second and index + 1 < len(FLIGHT):
            next_start, _, next_first, _ = FLIGHT[index + 1]
            if second < next_start:
                amount = (second - end) / max(.001, next_start - end)
                amount = 1 - (1 - amount) ** 3
                x, y = last[0] + (next_first[0] - last[0]) * amount, last[1] + (next_first[1] - last[1]) * amount
                return x, y + math.sin(second * 14) * 4, next_first[0] - last[0]
    if second >= 9.9:
        return 540, 370, 1
    raise RuntimeError("Flight phrases do not cover this time")


def gauge_bar():
    """One UI rig with shared rail/marker and four independently sized hit zones."""
    rig = new_rig("GaugeRig")
    border = plane("GaugeBorder", 156/48, 24/48, flat_material("GaugeBorderMat", (.98, .93, .82), 1), (0, 0, 0))
    track = plane("GaugeTrack", 150/48, 18/48, flat_material("GaugeTrackMat", (.36, .24, .16), 1), (0, 0, .01))
    marker = plane("GaugeMarker", 4/48, 26/48, flat_material("GaugeMarkerMat", (1, 1, 1), 1), (0, 0, .04))
    flash = plane("GaugeMissFlash", 150/48, 18/48, flat_material("GaugeMissFlashMat", (.9, .3, .25), 0), (0, 0, .03))
    for obj in (border, track, marker, flash): obj.parent = rig
    zones = []
    for index, (fraction, center) in enumerate(((.34, -20), (.26, 23), (.20, -12), (.15, 30))):
        zone = plane("GaugeHitZone" + str(index + 1), 150*fraction/48, 14/48, flat_material("GaugeHitMat" + str(index + 1), (.45, .78, .36), 1), (center/48, 0, .02))
        zone.parent = rig; zones.append(zone)
    return rig, border, track, marker, flash, zones


def ground():
    for name, asset, size, loc, z in (("Grass", "grass.png", (W, H), (0, 0), 0), ("DirtPath", "dirt.png", (W, 2.7), (.1, -3.7), .001)):
        mat = material(name+"Mat", image(ROOT / "assets/tiles/ground" / asset))
        next(node for node in mat.node_tree.nodes if node.type == "TEX_IMAGE").extension = "REPEAT"
        plane(name, *size, mat, (*loc, z), uv_scale=(size[0] / 4, size[1] / 4))


def environment():
    manifest = json.loads((ROOT / "assets/env/manifest.json").read_text(encoding="utf-8"))
    layout = [("buildings/tent",(215,205)),("buildings/cabin",(790,210)),("props/bulletin_board",(610,190)),("buildings/campfire",(720,400)),("props/lantern_post",(665,365)),("trees/oak",(85,205)),("trees/oak",(900,310)),("trees/pine",(115,455)),("plants/bush",(155,335)),("plants/bush",(865,175)),("flowers/cosmos",(505,275)),("flowers/cosmos",(550,300)),("flowers/daisy",(570,250)),("flowers/tulip",(485,320)),("flowers/wildflowers",(455,245)),("flowers/wildflowers",(595,310)),("flowers/wildflowers",(375,205)),("props/bench",(390,505))]
    for number, (asset_id, feet) in enumerate(layout):
        spec = manifest[asset_id]
        image_plane(asset_id.replace("/", "_") + str(number), ROOT / "assets" / spec["file"], feet, spec["world"], spec["origin"])


def ui(name, asset, center, scale=1.0, extra=2.0):
    img = image(ROOT / asset)
    return image_plane(name, ROOT / asset, center, (img.size[0]/2*scale, img.size[1]/2*scale), (.5,.5), extra)


def main():
    ground(); environment()
    cat_atlas = json.loads((ROOT / "assets/sprites/cat_base.json").read_text(encoding="utf-8")); cat_anims = json.loads((ROOT / "assets/sprites/cat_base.anims.json").read_text(encoding="utf-8"))
    cat = new_rig("CatFeet"); cats, cat_actions = animated_sprite("Cat", ROOT / "assets/sprites/cat_base.png", cat_atlas, cat_anims, cat)
    # One-shot poses live in the atlas but are intentionally absent from loop data.
    for frame_name in ("down_surprised", "down_net_up", "down_net_down", "left_net_up", "left_net_down"):
        cats[(frame_name, False)] = atlas_plane("Cat_" + frame_name, ROOT / "assets/sprites/cat_base.png", cat_atlas, frame_name, cat)
    for frame_name in ("left_net_up", "left_net_down"):
        cats[(frame_name, True)] = atlas_plane("Cat_" + frame_name + "_flip", ROOT / "assets/sprites/cat_base.png", cat_atlas, frame_name, cat, True)
    bug_atlas = json.loads((ROOT / "assets/insects/insect_butterfly.json").read_text(encoding="utf-8")); bug_anims = json.loads((ROOT / "assets/insects/insect_butterfly.anims.json").read_text(encoding="utf-8"))
    bug = new_rig("ButterflyFeet"); bugs, bug_actions = animated_sprite("Butterfly", ROOT / "assets/insects/insect_butterfly.png", bug_atlas, bug_anims, bug)
    shadow = plane("ButterflyShadow", .44, .15, flat_material("ShadowMat", (.07,.12,.08), .36), (0,0,.1))

    exclaim = ui("Exclaim", "assets/fx/emote_exclaim.png", (385, 290), .75)
    question = ui("Question", "assets/fx/emote_question.png", (385, 280), .75)
    visible_between(exclaim, f(2.4), f(3.0)); visible_between(question, f(11.1), f(12.6))
    sweats = []
    for index, second in enumerate((4.2, 6.4, 8.6)):
        sweat = ui("Sweat" + str(index + 1), "assets/fx/sweat.png", (400, 300), .55)
        visible_between(sweat, f(second), f(second + .36)); opacity(sweat, f(second), 1); opacity(sweat, f(second + .36), 0)
        sweats.append(sweat)

    gauge, border, track, marker, flash, zones = gauge_bar()
    gauge_parts = (border, track, marker, flash, *zones)
    attempts = ((3.0, .34, 1.0, -20, 16, False), (5.2, .26, .8, 23, -10, False), (7.4, .20, .65, -12, 9, False), (9.6, .15, .5, 30, -4, True))
    for index, (start, fraction, period, center, miss, flees) in enumerate(attempts):
        tap, end = start + 1.2, (10.2 if flees else start + 1.5)
        fade = 9.9 if flees else tap
        for obj in (border, track, marker, zones[index]):
            visible_between(obj, f(start), f(end)); opacity(obj, f(start), 1); opacity(obj, f(fade), 1); opacity(obj, f(end), 0)
        if not flees: visible_between(flash, f(tap), f(tap + .25)); opacity(flash, f(tap), .82); opacity(flash, f(tap + .25), 0)

    dusts = []
    for index, (when, x, y) in enumerate(((9.92, 520, 372), (10.04, 590, 300), (10.16, 675, 215), (10.28, 765, 125))):
        dust = ui("FleeDust" + str(index + 1), "assets/fx/dust.png", (x, y), .34)
        visible_between(dust, f(when), f(when + .34)); key_ui(dust, f(when), x, y)
        for frame, scale, alpha in ((f(when), .35, .85), (f(when + .34), 1.35, 0)):
            dust.scale = (scale, scale, 1); dust.keyframe_insert(data_path="scale", frame=frame); opacity(dust, frame, alpha)
        dusts.append(dust)

    for name, center, scale in (("LanternGlow",(665,316),1.3),("FireGlow",(720,374),1.15)):
        glow = ui(name,"assets/fx/weather/light_glow.png",center,scale); visible_between(glow,f(12.6),FRAMES); opacity(glow,f(12.6),0); opacity(glow,f(14.4),.9)
    for index,(x,y) in enumerate(((520,330),(600,250),(790,320),(445,390))):
        fly = ui("Firefly"+str(index),"assets/insects/icons/firefly.png",(x,y),.34); visible_between(fly,f(12.7+index*.12),FRAMES); opacity(fly,f(12.6),0); opacity(fly,f(13.7+index*.12),.95)

    for frame in range(1,FRAMES+1):
        second = (frame-1)/FPS
        if second < 1.5: cx, cy, action, flip = 250, 378, "idle_down", False
        elif second < 3.0: cx, cy, action, flip = 250 + (second-1.5)/1.5*150, 378, "walk_right", False
        elif second < 4.2: cx, cy, action, flip = 400, 378, "left_net_up", True
        elif second < 4.5: cx, cy, action, flip = 400, 378, "left_net_down", True
        elif second < 5.2: cx, cy, action, flip = 400 + (second-4.5)/.7*70, 378 + (second-4.5)/.7*-78, "walk_up", False
        elif second < 6.4: cx, cy, action, flip = 470, 300, "left_net_up", True
        elif second < 6.7: cx, cy, action, flip = 470, 300, "left_net_down", True
        elif second < 7.4: cx, cy, action, flip = 470 + (second-6.7)/.7*-80, 300 + (second-6.7)/.7*-10, "walk_left", False
        elif second < 8.6: cx, cy, action, flip = 390, 290, "left_net_up", True
        elif second < 8.9: cx, cy, action, flip = 390, 290, "left_net_down", True
        elif second < 9.6: cx, cy, action, flip = 390 + (second-8.9)/.7*50, 290 + (second-8.9)/.7*40, "walk_right", False
        elif second < 9.9: cx, cy, action, flip = 440, 330, "left_net_up", True
        elif second < 11.1: cx, cy, action, flip = 440, 330, "down_surprised", False
        else: cx, cy, action, flip = 440, 330, "idle_down", False
        key_rig(cat,frame,cx,cy)
        if action in cat_actions: show(cats,cat_actions[action],frame)
        else: show_frame(cats,action,frame,flip)
        key_ui(exclaim, frame, cx, cy-88); key_ui(question, frame, cx, cy-92)
        for sweat in sweats: key_ui(sweat, frame, cx+28, cy-78)
        gauge_drop = 20 * smoothstep((second - 9.9) / .3) if 9.9 <= second <= 10.2 else 0
        key_ui(gauge, frame, cx, cy-150-gauge_drop)
        active = next((item for item in attempts if item[0] <= second < (10.2 if item[5] else item[0] + 1.5)), None)
        if active:
            start, fraction, period, center, miss, flees = active
            position = -72 + 144 * (1 - abs(((second-start) / (period/2)) % 2 - 1)) if flees or second < start + 1.2 else miss
            marker.location.x = position / 48; marker.keyframe_insert(data_path="location", frame=frame)
        if second < 9.9:
            bx, by, dx = flutter(second); bug_action = "walk_right" if dx >= 0 else "walk_left"
        elif second < 10.4:
            start_x, start_y, _ = flutter(9.9); amount = smoothstep((second-9.9)/.5)
            bx, by = start_x + (1040-start_x)*amount, start_y + (-75-start_y)*amount - math.sin(amount*math.pi)*75
            bug_action = "flee_right" if second < 10.12 else "flee_up"
        else: bx, by, bug_action = 1040, -75, "flee_up"
        key_rig(bug,frame,bx,by); show(bugs,bug_actions[bug_action],frame); key_hide(bug,frame,second >= 10.4)
        shadow.location = (*game_xy(bx,by+24),depth(by+24,.02)); shadow.keyframe_insert(data_path="location",frame=frame); key_hide(shadow,frame,second >= 10.4)
    for item in [cat, bug, gauge, shadow, exclaim, question, *cats.values(), *bugs.values(), *sweats, *gauge_parts]: constant(item)
    for second,tint in ((0,(1,1,1)),(12.6,(1,1,1)),(13.5,(.85,.62,.42)),(15,(.45,.5,.8))):
        for channel,value in zip("rgb",tint): SCENE["tint_"+channel] = value; SCENE.keyframe_insert(data_path='["tint_'+channel+'"]',frame=f(second))
    linear(SCENE)

    OUT.parent.mkdir(parents=True,exist_ok=True); SCENE.render.filepath = str(OUT); bpy.ops.render.render(animation=True)
    for target,frame in ((OUT.with_name(f"{OUT.stem}_poster.jpg"),f(8)),(OUT.with_name(f"{OUT.stem}_day.jpg"),f(2)),(OUT.with_name(f"{OUT.stem}_night.jpg"),f(15))):
        SCENE.frame_set(frame); SCENE.render.image_settings.file_format, SCENE.render.image_settings.color_mode, SCENE.render.image_settings.quality = "JPEG","RGB",92; SCENE.render.filepath = str(target); bpy.ops.render.render(write_still=True)
    for output in (OUT,OUT.with_name(f"{OUT.stem}_poster.jpg"),OUT.with_name(f"{OUT.stem}_day.jpg"),OUT.with_name(f"{OUT.stem}_night.jpg")): print("created:",output)


if __name__ == "__main__": main()
