"""Render the Island gameplay showcase.

Run: "C:/Program Files/Blender Foundation/Blender 4.2/blender.exe" -b --factory-startup -P tools/blender_demo.py -- --out docs/img/showcase/previs.mp4
"""

import json
import math
import sys
from pathlib import Path

import bpy
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
PX, FPS, FRAMES, W, H = 96.0, 24, 288, 20.0, 11.25


def argument(name, fallback):
    args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    return Path(args[args.index(name) + 1]).resolve() if name in args else Path(fallback).resolve()


OUT = argument("--out", ROOT / "docs/img/showcase/previs.mp4")


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


def show_frame(objects, frame_name, frame):
    for key, obj in objects.items(): key_hide(obj, frame, key != (frame_name, False))


def ground():
    for name, asset, size, loc, z in (("Grass", "grass.png", (W, H), (0, 0), 0), ("DirtPath", "dirt.png", (W, 2.7), (.1, -3.7), .001)):
        mat = material(name+"Mat", image(ROOT / "assets/tiles/ground" / asset))
        next(node for node in mat.node_tree.nodes if node.type == "TEX_IMAGE").extension = "REPEAT"
        plane(name, *size, mat, (*loc, z), uv_scale=(size[0] / 4, size[1] / 4))


def environment():
    manifest = json.loads((ROOT / "assets/env/manifest.json").read_text(encoding="utf-8"))
    layout = [("buildings/tent",(215,205)),("buildings/cabin",(790,210)),("props/bulletin_board",(610,190)),("buildings/campfire",(720,400)),("props/lantern_post",(665,365)),("trees/oak",(85,205)),("trees/oak",(900,310)),("trees/pine",(115,455)),("plants/bush",(155,335)),("plants/bush",(865,175)),("flowers/cosmos",(505,275)),("flowers/cosmos",(550,300)),("flowers/daisy",(570,250)),("flowers/tulip",(485,320)),("flowers/wildflowers",(455,245)),("flowers/wildflowers",(595,310)),("flowers/wildflowers",(375,205)),("props/bench",(390,430))]
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
    for frame_name in ("down_surprised", "down_net_up", "down_net_down", "down_joy"):
        cats[(frame_name, False)] = atlas_plane("Cat_" + frame_name, ROOT / "assets/sprites/cat_base.png", cat_atlas, frame_name, cat)
    bug_atlas = json.loads((ROOT / "assets/insects/insect_butterfly.json").read_text(encoding="utf-8")); bug_anims = json.loads((ROOT / "assets/insects/insect_butterfly.anims.json").read_text(encoding="utf-8"))
    bug = new_rig("ButterflyFeet"); bugs, bug_actions = animated_sprite("Butterfly", ROOT / "assets/insects/insect_butterfly.png", bug_atlas, bug_anims, bug)
    shadow = plane("ButterflyShadow", .44, .15, flat_material("ShadowMat", (.07,.12,.08), .36), (0,0,.1))

    exclaim, ring, needle = ui("Exclaim","assets/fx/emote_exclaim.png",(542,305),.75), ui("AimRing","assets/ui/hud/ring.png",(548,370)), ui("AimNeedle","assets/ui/hud/ring_needle.png",(548,370),1,2.01)
    for obj in (exclaim,ring,needle): visible_between(obj, f(4.5), f(5.5))
    needle.rotation_euler[2] = -.7; needle.keyframe_insert(data_path="rotation_euler",frame=f(4.5)); needle.rotation_euler[2] = .8; needle.keyframe_insert(data_path="rotation_euler",frame=f(5.5))
    for index, (asset,dx,dy) in enumerate((("sparkle.png",0,0),("star_small.png",35,-22),("petal.png",-35,20),("petal.png",28,27))):
        obj = ui("Burst"+str(index),"assets/fx/"+asset,(560+dx,370+dy),.65); visible_between(obj,f(5.55),f(6.55))
        for frame,scale,alpha in ((f(5.55),.25,1),(f(6.55),1.7,0)):
            obj.scale = (scale,scale,1); obj.keyframe_insert(data_path="scale",frame=frame); opacity(obj,frame,alpha)

    card_rig = new_rig("WordCard"); card, word = ui("WordCardPanel","assets/ui/panels/word_card.png",(548,190),1.15), ui("WordButterfly","assets/words/butterfly.png",(548,190),.6,2.01)
    card.parent = card_rig; word.parent = card_rig
    for obj in (card,word): visible_between(obj,f(6.5),f(9.95)); opacity(obj,f(9.5),1); opacity(obj,f(9.95),0)
    for frame,scale in ((f(6.5),.1),(f(6.8),1.18),(f(7.05),1),(f(9.5),1),(f(9.95),.82)):
        card_rig.scale = (scale,scale,1); card_rig.keyframe_insert(data_path="scale",frame=frame)

    for name, center, scale in (("LanternGlow",(665,316),1.3),("FireGlow",(720,374),1.15)):
        glow = ui(name,"assets/fx/weather/light_glow.png",center,scale); visible_between(glow,f(10),FRAMES); opacity(glow,f(10),0); opacity(glow,f(12),.9)
    for index,(x,y) in enumerate(((520,330),(600,250),(790,320),(445,390))):
        fly = ui("Firefly"+str(index),"assets/insects/icons/firefly.png",(x,y),.34); visible_between(fly,f(10.1+index*.12),FRAMES); opacity(fly,f(10),0); opacity(fly,f(11.1+index*.12),.95)

    for frame in range(1,FRAMES+1):
        second = (frame-1)/FPS
        if second < 1.5: cx,cy,action = 285,378,"idle_down"
        elif second < 4.5: cx,cy,action = 285+(second-1.5)/3*260,378,"walk_right"
        elif second < 5.5: cx,cy,action = 545,378,"down_surprised"
        elif second < 6: cx,cy,action = 545,378,"down_net_up"
        elif second < 6.5: cx,cy,action = 545,378,"down_net_down"
        elif second < 8.5: cx,cy,action = 545,378,"down_joy"
        else: cx,cy,action = 545,378,"idle_down"
        key_rig(cat,frame,cx,cy)
        if action in cat_actions: show(cats,cat_actions[action],frame)
        else: show_frame(cats,action,frame)
        bx,by = 430+min(second,5.9)/5.9*155,333+math.sin(second*3.3)*18
        key_rig(bug,frame,bx,by); show(bugs,bug_actions["walk_right"],frame); key_hide(bug,frame,second>=6.05)
        shadow.location = (*game_xy(bx,by+24),depth(by+24,.02)); shadow.keyframe_insert(data_path="location",frame=frame); key_hide(shadow,frame,second>=6.05)
    for item in [cat,bug,*cats.values(),*bugs.values()]: constant(item)
    for second,tint in ((0,(1,1,1)),(10,(1,1,1)),(11,(.85,.62,.42)),(12,(.45,.5,.8))):
        for channel,value in zip("rgb",tint): SCENE["tint_"+channel] = value; SCENE.keyframe_insert(data_path='["tint_'+channel+'"]',frame=f(second))

    OUT.parent.mkdir(parents=True,exist_ok=True); SCENE.render.filepath = str(OUT); bpy.ops.render.render(animation=True)
    for target,frame in ((OUT.with_name(f"{OUT.stem}_poster.jpg"),f(6)),(OUT.with_name(f"{OUT.stem}_day.jpg"),f(2)),(OUT.with_name(f"{OUT.stem}_night.jpg"),f(11.5))):
        SCENE.frame_set(frame); SCENE.render.image_settings.file_format, SCENE.render.image_settings.color_mode, SCENE.render.image_settings.quality = "JPEG","RGB",92; SCENE.render.filepath = str(target); bpy.ops.render.render(write_still=True)
    for output in (OUT,OUT.with_name(f"{OUT.stem}_poster.jpg"),OUT.with_name(f"{OUT.stem}_day.jpg"),OUT.with_name(f"{OUT.stem}_night.jpg")): print("created:",output)


if __name__ == "__main__": main()
