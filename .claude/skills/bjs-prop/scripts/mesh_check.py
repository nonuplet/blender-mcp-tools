"""bjs-prop: メッシュの健全性を調べる（読み取りのみ。シーンは変更しない）。

形状を生成・修正したあとに使う。次の件数と、問題箇所の位置（ワールド座標）のサンプルを返す。
- 面を持たない辺（孤立した辺）/ 1 面だけの辺（開いた縁）/ 3 面以上が接する辺（非多様体）
- 孤立した頂点 / 面積がほぼ 0 の面 / 5 角形以上の面
閉じた形（箱など）なら、1 面だけの辺と 3 面以上が接する辺は 0 になるはず。
"""
import bpy
import bmesh

# --- パラメータ ---
OBJECTS = ["Crate_A"]   # 対象オブジェクト名のリスト
USE_EVALUATED = False   # False: 元のメッシュ / True: モディファイア適用後（書き出される形）
MAX_SAMPLES = 8         # 問題ごとに返す位置のサンプル数
# --- ここまで ---


def pt(v):
    return [round(c, 4) for c in v]


depsgraph = bpy.context.evaluated_depsgraph_get()
report, skipped = [], []
for name in OBJECTS:
    ob = bpy.data.objects.get(name)
    if ob is None or ob.type != "MESH":
        skipped.append({"object": name, "reason": "見つからないか、メッシュではない"})
        continue
    bm = bmesh.new()
    if USE_EVALUATED:
        ob_eval = ob.evaluated_get(depsgraph)
        bm.from_mesh(ob_eval.to_mesh())
        ob_eval.to_mesh_clear()
    elif ob.mode == "EDIT":
        skipped.append({"object": name, "reason": "編集モード中（元のメッシュが最新でない可能性がある。オブジェクトモードで実行する）"})
        bm.free()
        continue
    else:
        bm.from_mesh(ob.data)
    bm.transform(ob.matrix_world)

    loose_edges = [e for e in bm.edges if len(e.link_faces) == 0]
    boundary = [e for e in bm.edges if len(e.link_faces) == 1]
    nonmanifold = [e for e in bm.edges if len(e.link_faces) > 2]
    loose_verts = [v for v in bm.verts if not v.link_edges]
    degenerate = [f for f in bm.faces if f.calc_area() < 1e-10]
    ngons = [f for f in bm.faces if len(f.verts) > 4]
    tris = sum(len(f.verts) - 2 for f in bm.faces)

    def edge_samples(edges):
        return [pt((e.verts[0].co + e.verts[1].co) / 2) for e in edges[:MAX_SAMPLES]]

    def face_samples(faces):
        return [pt(f.calc_center_median()) for f in faces[:MAX_SAMPLES]]

    report.append({
        "object": name,
        "evaluated": USE_EVALUATED,
        "verts": len(bm.verts),
        "edges": len(bm.edges),
        "faces": len(bm.faces),
        "triangles": tris,
        "closed": not boundary and not nonmanifold and not loose_edges,
        "counts": {
            "loose_edges": len(loose_edges),
            "boundary_edges": len(boundary),
            "nonmanifold_edges": len(nonmanifold),
            "loose_verts": len(loose_verts),
            "degenerate_faces": len(degenerate),
            "ngons": len(ngons),
        },
        "samples": {
            "loose_edges": edge_samples(loose_edges),
            "boundary_edges": edge_samples(boundary),
            "nonmanifold_edges": edge_samples(nonmanifold),
            "loose_verts": [pt(v.co) for v in loose_verts[:MAX_SAMPLES]],
            "degenerate_faces": face_samples(degenerate),
        },
    })
    bm.free()

result = {"objects": report, "skipped": skipped}
