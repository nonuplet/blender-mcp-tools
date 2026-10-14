"""bjs-scene-setup: EXPORT / WIP / REF コレクションを用意し、必要なら scale_length と fps を設定する。

既存のコレクションはそのまま使う（中身の移動・削除はしない）。
単位系（Metric / Imperial）は hook の制約（属性名 system が deny）で変更できないため、
必要な場合はユーザーに Scene Properties → Units で変更してもらう。
"""
import bpy

# --- パラメータ ---
COLLECTIONS = ["EXPORT", "WIP", "REF"]  # 作るコレクション（既存なら再利用）
HIDE_RENDER = ["REF"]                   # hide_render を有効にするコレクション
SET_ACTIVE = "EXPORT"                   # アクティブにするコレクション。None なら変更しない
SET_SCALE_LENGTH = False                # True: scale_length を 1.0 にする（ユーザーの了承がある場合だけ）
FPS = None                              # 例: 30。None なら変更しない（ユーザーの了承がある場合だけ）
# --- ここまで ---

scene = bpy.context.scene
view_layer = bpy.context.view_layer
changes = []

for name in COLLECTIONS:
    coll = bpy.data.collections.get(name)
    if coll is None:
        coll = bpy.data.collections.new(name)
        changes.append(f"コレクション {name} を作成")
    if name not in scene.collection.children:
        scene.collection.children.link(coll)
        changes.append(f"コレクション {name} をシーン直下にリンク")
    if name in HIDE_RENDER and not coll.hide_render:
        coll.hide_render = True
        changes.append(f"コレクション {name} の hide_render を有効化")

if SET_ACTIVE is not None:
    layer_coll = view_layer.layer_collection.children.get(SET_ACTIVE)
    if layer_coll is None:
        changes.append(f"アクティブにできない（シーン直下に {SET_ACTIVE} がない）")
    elif view_layer.active_layer_collection != layer_coll:
        view_layer.active_layer_collection = layer_coll
        changes.append(f"アクティブコレクションを {SET_ACTIVE} に変更")

if SET_SCALE_LENGTH:
    units = scene.unit_settings
    if abs(units.scale_length - 1.0) > 1e-6:
        changes.append(f"scale_length {units.scale_length} → 1.0")
        units.scale_length = 1.0

if FPS is not None and (scene.render.fps != FPS or scene.render.fps_base != 1.0):
    changes.append(f"fps {scene.render.fps / scene.render.fps_base:.3f} → {FPS}")
    scene.render.fps = FPS
    scene.render.fps_base = 1.0

result = {
    "changes": changes,
    "active_collection": view_layer.active_layer_collection.name,
}
