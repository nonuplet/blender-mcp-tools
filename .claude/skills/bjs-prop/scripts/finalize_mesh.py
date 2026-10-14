"""bjs-prop / bjs-environment: 書き出しに向けてメッシュを仕上げる。

回転・スケールの適用、原点の移動、Smooth by Angle を行う。UV 展開は行わない（bjs-uv で行う）。
メッシュを共有しているオブジェクト（リンク複製）は、適用と原点の変更をスキップする。
"""
import bpy
import math
from mathutils import Matrix, Vector

# --- パラメータ ---
OBJECTS = ["Crate_A"]        # 対象オブジェクト名のリスト
APPLY_ROTATION_SCALE = True  # 回転・スケールを適用する（位置は残す）
ORIGIN = "BOTTOM_CENTER"     # "BOTTOM_CENTER" / "BOUNDS_CENTER" / None（変更しない）
AUTO_SMOOTH_ANGLE = 30       # Smooth by Angle の角度（度）。0 ならフラット、None なら変更しない
# --- ここまで ---

view_layer = bpy.context.view_layer
skipped = []
done = []


def select_only(objs):
    for o in view_layer.objects:
        o.select_set(False)
    for o in objs:
        o.select_set(True)
    if objs:
        view_layer.objects.active = objs[0]


if bpy.context.object is not None and bpy.context.object.mode != "OBJECT":
    bpy.ops.object.mode_set(mode="OBJECT")

meshes = []
for name in OBJECTS:
    ob = bpy.data.objects.get(name)
    if ob is None:
        skipped.append({"object": name, "reason": "見つからない"})
    elif ob.type != "MESH":
        skipped.append({"object": name, "reason": f"メッシュではない ({ob.type})"})
    elif ob.name not in view_layer.objects:
        skipped.append({"object": name, "reason": "ビューレイヤーにない（コレクションが除外されている）"})
    else:
        meshes.append(ob)

# メッシュを共有しているものは、形を変える処理の対象から外す
unique = []
for ob in meshes:
    if ob.data.users > 1:
        skipped.append({"object": ob.name,
                        "reason": f"メッシュ {ob.data.name} を {ob.data.users} 個のオブジェクトで共有しているため、適用と原点の変更をスキップ"})
    else:
        unique.append(ob)

# 回転・スケールの適用
if APPLY_ROTATION_SCALE and unique:
    select_only(unique)
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
    done.append("回転・スケールを適用")

# 原点の移動（メッシュをずらし、同じ量だけオブジェクトを動かす。子の位置は保つ）
if ORIGIN in ("BOTTOM_CENTER", "BOUNDS_CENTER"):
    for ob in unique:
        verts = ob.data.vertices
        if len(verts) == 0:
            continue
        lo = Vector((min(v.co.x for v in verts), min(v.co.y for v in verts), min(v.co.z for v in verts)))
        hi = Vector((max(v.co.x for v in verts), max(v.co.y for v in verts), max(v.co.z for v in verts)))
        pivot = (lo + hi) / 2
        if ORIGIN == "BOTTOM_CENTER":
            pivot.z = lo.z
        if pivot.length < 1e-7:
            continue
        ob.data.transform(Matrix.Translation(-pivot))
        ob.matrix_world = ob.matrix_world @ Matrix.Translation(pivot)
        for child in ob.children:
            child.matrix_parent_inverse = Matrix.Translation(-pivot) @ child.matrix_parent_inverse
    done.append(f"原点を {ORIGIN} に移動")
elif ORIGIN is not None:
    raise ValueError(f"ORIGIN が不正: {ORIGIN}")

# シェーディング
if AUTO_SMOOTH_ANGLE is not None and meshes:
    select_only(meshes)
    if AUTO_SMOOTH_ANGLE > 0:
        bpy.ops.object.shade_auto_smooth(angle=math.radians(AUTO_SMOOTH_ANGLE))
        done.append(f"Smooth by Angle ({AUTO_SMOOTH_ANGLE} 度)")
    else:
        bpy.ops.object.shade_flat()
        done.append("フラットシェード")

select_only(meshes)

# 結果
depsgraph = bpy.context.evaluated_depsgraph_get()
report = []
for ob in meshes:
    ob_eval = ob.evaluated_get(depsgraph)
    me = ob_eval.to_mesh()
    me.calc_loop_triangles()
    tris = len(me.loop_triangles)
    ob_eval.to_mesh_clear()
    report.append({
        "object": ob.name,
        "triangles": tris,
        "dimensions_m": [round(v, 4) for v in ob.dimensions],
        "location": [round(v, 4) for v in ob.matrix_world.translation],
        "uv_layers": [uv.name for uv in ob.data.uv_layers],
        "modifiers": [m.type for m in ob.modifiers],
    })

result = {"done": done, "skipped": skipped, "objects": report}
