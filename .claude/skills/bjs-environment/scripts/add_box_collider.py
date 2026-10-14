"""bjs-environment: 当たり判定用の箱メッシュ（<名前>_collider）を作る。

元オブジェクトのローカル座標系のバウンディングボックスと同じ大きさの箱を、元オブジェクトの子として作る。
カスタムプロパティ bjs_collider = True を付ける。同名の collider が既にあれば作らない。
"""
import bpy
import bmesh
from mathutils import Matrix, Vector

# --- パラメータ ---
SOURCES = ["Wall_Straight_2m_001"]  # 元オブジェクト名のリスト
SUFFIX = "_collider"
PADDING = 0.0                       # 各面を外側に広げる量 [m]
COLLECTION = "EXPORT"               # collider を入れるコレクション
# --- ここまで ---

coll = bpy.data.collections.get(COLLECTION)
if coll is None:
    raise ValueError(f"コレクションが見つからない: {COLLECTION}")

created, skipped = [], []
for name in SOURCES:
    src = bpy.data.objects.get(name)
    if src is None:
        skipped.append({"object": name, "reason": "見つからない"})
        continue
    col_name = name + SUFFIX
    if col_name in bpy.data.objects:
        skipped.append({"object": name, "reason": f"{col_name} が既にある"})
        continue

    corners = [Vector(c) for c in src.bound_box]
    lo = Vector((min(c.x for c in corners), min(c.y for c in corners), min(c.z for c in corners)))
    hi = Vector((max(c.x for c in corners), max(c.y for c in corners), max(c.z for c in corners)))
    center = (lo + hi) / 2
    size = (hi - lo) + Vector((PADDING * 2,) * 3)

    me = bpy.data.meshes.new(col_name)
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co = Vector((center.x + v.co.x * size.x, center.y + v.co.y * size.y, center.z + v.co.z * size.z))
    bm.to_mesh(me)
    bm.free()

    ob = bpy.data.objects.new(col_name, me)
    coll.objects.link(ob)
    ob.parent = src
    ob.matrix_parent_inverse = Matrix.Identity(4)
    ob.matrix_basis = Matrix.Identity(4)
    ob.display_type = "WIRE"  # Blender 上の表示だけ。書き出しには影響しない
    ob["bjs_collider"] = True
    ob["bjs_source"] = src.name
    created.append({"object": ob.name, "size_m": [round(v, 4) for v in size]})

result = {"created": created, "skipped": skipped}
