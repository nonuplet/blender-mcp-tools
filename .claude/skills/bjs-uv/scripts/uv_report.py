"""bjs-uv: UV の状態を調べる（読み取りのみ。シーンは変更しない）。

面ごとに「UV 上の面積」と「実際の面積」を比べ、密度（1 m あたりの UV 長さ）のずれで歪みを見る。
基準は EXPECTED_UV_PER_METER（指定がなければ、面積で重み付けした中央値）。
ほかに、島（アイランド）の数、裏返った UV、潰れた UV（面積付き）、0〜1 の範囲外の割合を返す。
島どうしの重なりは調べない（タイル状の模様では重なりは問題にならない）。
"""
import bpy
import bmesh

# --- パラメータ ---
OBJECTS = ["Crate_A"]          # 対象オブジェクト名のリスト
UV_NAME = None                 # 調べる UV マップ。None ならアクティブな UV マップ
USE_EVALUATED = True           # True: モディファイア適用後（書き出される形）で調べる
EXPECTED_UV_PER_METER = None   # 期待する密度（タイル状の模様なら 1 / METERS_PER_TILE）。None なら面積重み付きの中央値
DEVIATION = 0.25               # 密度が基準から何割ずれた面を「歪んでいる」と数えるか
# --- ここまで ---


def uv_signed_area(uvs):
    s = 0.0
    for i in range(len(uvs)):
        x1, y1 = uvs[i]
        x2, y2 = uvs[(i + 1) % len(uvs)]
        s += x1 * y2 - x2 * y1
    return s / 2


def same(a, b, eps=1e-5):
    return abs(a[0] - b[0]) < eps and abs(a[1] - b[1]) < eps


depsgraph = bpy.context.evaluated_depsgraph_get()
report, skipped = [], []
for name in OBJECTS:
    ob = bpy.data.objects.get(name)
    if ob is None or ob.type != "MESH":
        skipped.append({"object": name, "reason": "見つからないか、メッシュではない"})
        continue
    if USE_EVALUATED:
        ob_eval = ob.evaluated_get(depsgraph)
        me = ob_eval.to_mesh()
    else:
        me = ob.data
    bm = bmesh.new()
    bm.from_mesh(me)
    if USE_EVALUATED:
        ob_eval.to_mesh_clear()
    bm.transform(ob.matrix_world)

    layer_name = UV_NAME or (ob.data.uv_layers.active.name if ob.data.uv_layers.active else None)
    uv_layer = bm.loops.layers.uv.get(layer_name) if layer_name else None
    if uv_layer is None:
        skipped.append({"object": name, "reason": f"UV マップがない（{layer_name}）"})
        bm.free()
        continue

    samples = []  # (密度, 実面積, 中心)
    flipped = collapsed = 0
    collapsed_area = total_area = 0.0
    loops_total = loops_outside = 0
    face_uv = {}
    for f in bm.faces:
        uvs = [tuple(l[uv_layer].uv) for l in f.loops]
        face_uv[f] = {l.vert: uvs[i] for i, l in enumerate(f.loops)}
        loops_total += len(uvs)
        loops_outside += sum(1 for u, v in uvs if u < 0 or u > 1 or v < 0 or v > 1)
        area = f.calc_area()
        if area < 1e-10:
            continue
        total_area += area
        a = uv_signed_area(uvs)
        if abs(a) < 1e-12:
            collapsed += 1
            collapsed_area += area
            continue
        if a < 0:
            flipped += 1
        samples.append(((abs(a) / area) ** 0.5, area, f.calc_center_median()))

    # 島: 辺を共有する 2 面で、その辺の両端の UV が一致していれば同じ島
    parent = {f: f for f in bm.faces}

    def find(f):
        while parent[f] is not f:
            parent[f] = parent[parent[f]]
            f = parent[f]
        return f

    for e in bm.edges:
        if len(e.link_faces) != 2:
            continue
        f1, f2 = e.link_faces
        if all(same(face_uv[f1][v], face_uv[f2][v]) for v in e.verts):
            parent[find(f1)] = find(f2)
    islands = len({find(f) for f in bm.faces})
    bm.free()

    entry = {
        "object": name,
        "uv_map": layer_name,
        "evaluated": USE_EVALUATED,
        "faces": len(face_uv),
        "islands": islands,
        "flipped_faces": flipped,
        "collapsed_faces": collapsed,
        "collapsed_area_ratio": round(collapsed_area / total_area, 4) if total_area else 0,
        "loops_outside_0_1": round(loops_outside / loops_total, 3) if loops_total else 0,
    }
    if samples:
        # 面積で重み付けした中央値（小さな面が多くても基準がずれにくい）
        ordered = sorted(samples, key=lambda s: s[0])
        half, acc, weighted_median = sum(s[1] for s in ordered) / 2, 0.0, ordered[-1][0]
        for d, area, _ in ordered:
            acc += area
            if acc >= half:
                weighted_median = d
                break
        ref = EXPECTED_UV_PER_METER or weighted_median
        off = [(d, area, c) for d, area, c in samples if abs(d - ref) > ref * DEVIATION]
        entry.update({
            "uv_per_meter_reference": round(ref, 4),
            "uv_per_meter_weighted_median": round(weighted_median, 4),
            "uv_per_meter_min": round(ordered[0][0], 4),
            "uv_per_meter_max": round(ordered[-1][0], 4),
            "distorted_faces": len(off),
            "distorted_area_ratio": round(sum(a for _, a, _ in off) / total_area, 4),
            "distorted_samples": [{"uv_per_meter": round(d, 3), "center": [round(x, 3) for x in c]}
                                  for d, _, c in off[:6]],
        })
    report.append(entry)

result = {"objects": report, "skipped": skipped}
