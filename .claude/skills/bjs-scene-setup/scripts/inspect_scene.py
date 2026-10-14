"""bjs-scene-setup: Babylon.js 向けの作業前に、シーンの設定を調べる（読み取りのみ）。

パラメータはない。
単位系（unit_settings.system）は、hook が属性名 system を一律で deny にしているため参照しない。
代わりに表示単位（length_unit）でヤード・ポンド法かどうかを判断する。
"""
import bpy
from collections import Counter

IMPERIAL_UNITS = {"MILES", "FEET", "INCHES", "THOU"}

scene = bpy.context.scene
units = scene.unit_settings
view_layer = bpy.context.view_layer


def walk(coll):
    return {
        "name": coll.name,
        "objects": len(coll.objects),
        "hide_render": coll.hide_render,
        "children": [walk(c) for c in coll.children],
    }


issues = []
if units.length_unit in IMPERIAL_UNITS:
    issues.append(f"長さの単位がヤード・ポンド法: {units.length_unit}（Scene Properties → Units で Metric にしてもらう）")
if abs(units.scale_length - 1.0) > 1e-6:
    issues.append(f"scale_length が 1.0 ではない: {units.scale_length}")
for name in ("EXPORT", "WIP", "REF"):
    if name not in bpy.data.collections:
        issues.append(f"コレクション {name} がない")
    elif name not in scene.collection.children:
        issues.append(f"コレクション {name} はあるが、シーン直下にリンクされていない")

fps = scene.render.fps / scene.render.fps_base

result = {
    "scene": scene.name,
    "units": {
        "scale_length": units.scale_length,
        "length_unit": units.length_unit,
    },
    "fps": round(fps, 3),
    "frame_range": [scene.frame_start, scene.frame_end],
    "active_collection": view_layer.active_layer_collection.name,
    "object_count": len(scene.objects),
    "object_types": dict(Counter(o.type for o in scene.objects)),
    "collections": walk(scene.collection),
    "actions": len(bpy.data.actions),
    "materials": len(bpy.data.materials),
    "issues": issues,
}
