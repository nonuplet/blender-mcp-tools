"""bjs-conventions: 確認用スクリーンショットのため、3D ビューの視点を切り替える。

変更するのは UI（ビューの向き・ズーム・シェーディング）だけで、シーンのデータは変更しない。
最後にウィンドウを再描画させる。
実行後に get_screenshot_of_area_as_image(area_ui_type="VIEW_3D") で撮影する。
"""
import bpy
import math
from mathutils import Euler, Vector

# --- パラメータ ---
VIEW = "ISO"           # "ISO" / "FRONT" / "BACK" / "RIGHT" / "LEFT" / "TOP"
TARGETS = None         # 画面に収めるオブジェクト名のリスト。None なら COLLECTION を使う
COLLECTION = "EXPORT"  # TARGETS が None のとき画面に収めるコレクション。None ならシーン内の表示中オブジェクトすべて
SHADING = "SOLID"      # "SOLID" / "MATERIAL"
MARGIN = 1.3           # 余白の倍率（大きくすると引きになる）
# --- ここまで ---

# ビューの回転（度）。単位行列が上面図で、X 軸 90 度で正面図（-Y 側から見る）になる。
ROTATIONS = {
    "TOP": (0, 0, 0),
    "FRONT": (90, 0, 0),
    "BACK": (90, 0, 180),
    "RIGHT": (90, 0, 90),
    "LEFT": (90, 0, -90),
    "ISO": (60, 0, 45),
}

if VIEW not in ROTATIONS:
    raise ValueError(f"VIEW は {list(ROTATIONS)} のいずれか: {VIEW}")

# 対象オブジェクト
if TARGETS is not None:
    objs = [bpy.data.objects[n] for n in TARGETS if n in bpy.data.objects]
elif COLLECTION is not None and COLLECTION in bpy.data.collections:
    objs = list(bpy.data.collections[COLLECTION].all_objects)
else:
    objs = list(bpy.context.scene.objects)
objs = [o for o in objs if o.visible_get() and o.type not in {"CAMERA", "LIGHT"}]

# ワールド座標のバウンディングボックス
corners = [o.matrix_world @ Vector(c) for o in objs for c in o.bound_box]
if corners:
    lo = Vector((min(c.x for c in corners), min(c.y for c in corners), min(c.z for c in corners)))
    hi = Vector((max(c.x for c in corners), max(c.y for c in corners), max(c.z for c in corners)))
else:
    lo, hi = Vector((-1, -1, -1)), Vector((1, 1, 1))
center = (lo + hi) / 2
radius = max((hi - lo).length / 2, 0.05)

# いちばん大きい 3D ビューを使う
area = None
for window in bpy.context.window_manager.windows:
    for a in window.screen.areas:
        if a.type == "VIEW_3D" and (area is None or a.width * a.height > area.width * area.height):
            area = a
if area is None:
    raise RuntimeError("3D ビューが見つからない")

space = area.spaces.active
r3d = space.region_3d
rx, ry, rz = (math.radians(v) for v in ROTATIONS[VIEW])
r3d.view_rotation = Euler((rx, ry, rz)).to_quaternion()
r3d.view_perspective = "PERSP" if VIEW == "ISO" else "ORTHO"
r3d.view_location = center
r3d.view_distance = radius * 2.0 * MARGIN
space.shading.type = SHADING
area.tag_redraw()
# MATERIAL 表示に切り替えた直後は、EEVEE のシェーダーコンパイル待ちで描画が更新されないことがあるため、再描画させる
bpy.ops.wm.redraw_timer(type="DRAW_WIN_SWAP", iterations=3)

result = {
    "view": VIEW,
    "shading": SHADING,
    "objects": [o.name for o in objs],
    "bounds_min": [round(v, 4) for v in lo],
    "bounds_max": [round(v, 4) for v in hi],
    "size": [round(v, 4) for v in (hi - lo)],
}
