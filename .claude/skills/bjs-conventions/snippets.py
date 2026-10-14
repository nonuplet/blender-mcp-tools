"""bjs-conventions: 生成コード（tmp/ に置くスクリプト）で使う、形に依存しない関数のスニペット集。

このファイル自体は実行しない。execute_blender_code はファイルを import できないので、
必要な関数をこのファイルから tmp/ のスクリプトへそのままコピーして使う（スクリプトは単体で完結させる）。
各関数は bpy / bmesh / mathutils 以外に依存しない。関数どうしの依存もない。
skill の scripts/ にある既存スクリプトは、これを使わずに単体で完結している。
"""
import bpy
import bmesh
from mathutils import Vector


def ensure_object_mode():
    """編集モードなどからオブジェクトモードに戻す。メッシュデータを直接書き換える前に呼ぶ。"""
    ob = bpy.context.object
    if ob is not None and ob.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")


def select_only(objs):
    """objs だけを選択し、先頭をアクティブにする（オペレーターを使う前に呼ぶ）。"""
    view_layer = bpy.context.view_layer
    for o in view_layer.objects:
        o.select_set(False)
    for o in objs:
        o.select_set(True)
    if objs:
        view_layer.objects.active = objs[0]


def evaluated_triangles(ob):
    """モディファイア適用後（書き出される形）の三角形数を返す。"""
    depsgraph = bpy.context.evaluated_depsgraph_get()
    ob_eval = ob.evaluated_get(depsgraph)
    me = ob_eval.to_mesh()
    me.calc_loop_triangles()
    count = len(me.loop_triangles)
    ob_eval.to_mesh_clear()
    return count


def world_bounds(objs):
    """objs 全体のワールド座標のバウンディングボックスを (最小, 最大) の Vector で返す。objs が空なら None。"""
    corners = [o.matrix_world @ Vector(c) for o in objs for c in o.bound_box]
    if not corners:
        return None
    lo = Vector((min(c.x for c in corners), min(c.y for c in corners), min(c.z for c in corners)))
    hi = Vector((max(c.x for c in corners), max(c.y for c in corners), max(c.z for c in corners)))
    return lo, hi


def hex_to_linear(color):
    """'#RRGGBB'（sRGB）をリニアの (r, g, b, 1) にする（Principled BSDF の色入力用）。"""
    h = color.lstrip("#")
    if len(h) != 6:
        raise ValueError(f"カラーは #RRGGBB 形式にする: {color}")
    srgb = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    lin = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in srgb]
    return (lin[0], lin[1], lin[2], 1.0)


def topology_counts(bm):
    """bmesh の健全性の件数を返す。閉じた形なら boundary_edges と nonmanifold_edges は 0 になるはず。

    詳しい位置まで知りたい場合は、bjs-prop の scripts/mesh_check.py を使う。
    """
    return {
        "loose_edges": sum(1 for e in bm.edges if len(e.link_faces) == 0),
        "boundary_edges": sum(1 for e in bm.edges if len(e.link_faces) == 1),
        "nonmanifold_edges": sum(1 for e in bm.edges if len(e.link_faces) > 2),
        "loose_verts": sum(1 for v in bm.verts if not v.link_edges),
        "degenerate_faces": sum(1 for f in bm.faces if f.calc_area() < 1e-10),
    }
