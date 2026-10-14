"""bjs-uv: タイル状の模様向けに、実寸に合わせて UV を投影する。

面を次の 3 種類に分け、オブジェクトの座標（回転・スケール込み、位置は除く）から UV を計算する。
- キャップ: 最上部・最下部にある水平な面（上面・底面）。CAP_MODE で扱いを選ぶ
- 側面: 水平でない面。面取りなどの傾いた面も、属する側面と同じ投影になる
- 途中の水平な面（溝の壁など）: キャップにせず、位置が最も近い側面に含める（CAP_Z = "EXTREMES" のとき）
側面の投影:
- WRAP: 正面（-Y）→ 右（+X）→ 背面（+Y）→ 左（-X）の順にぐるりと 1 本の帯としてつなげる（箱形向け）
- BOX : 面ごとに、属する側の軸で投影する（角で模様がつながらないことがある）
外側から見て U が右向き・V が上向きになるようにそろえる（模様が鏡像にならない）。
UV は 0〜1 に詰めない（テクスチャの繰り返し REPEAT で敷き詰める前提）。
"""
import bpy
import bmesh

# --- パラメータ ---
OBJECTS = ["Crate_A"]      # 対象オブジェクト名のリスト
MODE = "WRAP"              # 側面の投影。"WRAP"（一周つなげる。箱形向け）/ "BOX"（面ごとに軸で投影）
METERS_PER_TILE = 0.6      # テクスチャ 1 枚（UV 0〜1）が何 m に相当するか
SIDE_ROTATE = 0            # 側面の模様の回転（0 / 90）。0 なら U が水平方向
OFFSET = (0.0, 0.0)        # 側面とキャップ（PROJECT）の UV のずらし量（タイル単位）
CAP_THRESHOLD = 0.9        # |法線の Z 成分| がこれ以上の面を「水平な面」とみなす（45 度の面取りは側面側になる）
CAP_Z = "EXTREMES"         # "EXTREMES": 最上部・最下部の水平な面だけをキャップにする / "ALL": 水平な面はすべてキャップ
CAP_MODE = "PROJECT"       # キャップの UV。"PROJECT": 上から投影 / "POINT": すべて CAP_POINT の 1 点（テクスチャの 1 色）
CAP_ROTATE = 0             # CAP_MODE = "PROJECT" のときの回転（0 / 90）。0 なら U が X 方向
CAP_POINT = (0.5, 0.5)     # CAP_MODE = "POINT" のときの UV 座標（テクスチャのどの色を使うか）
CAP_MATERIAL_INDEX = None  # 整数なら、キャップの面にそのマテリアルスロット番号を割り当てる（None なら変更しない）
Z_TOLERANCE = 0.001        # 最上部・最下部とみなす高さの許容差 [m]
UV_NAME = "UVMap"          # 書き込む UV マップ。なければ作り、あれば上書きする
# --- ここまで ---

if MODE not in ("WRAP", "BOX"):
    raise ValueError(f"MODE が不正: {MODE}")
if CAP_Z not in ("EXTREMES", "ALL"):
    raise ValueError(f"CAP_Z が不正: {CAP_Z}")
if CAP_MODE not in ("PROJECT", "POINT"):
    raise ValueError(f"CAP_MODE が不正: {CAP_MODE}")
if SIDE_ROTATE not in (0, 90) or CAP_ROTATE not in (0, 90):
    raise ValueError("SIDE_ROTATE / CAP_ROTATE は 0 か 90")
if METERS_PER_TILE <= 0:
    raise ValueError("METERS_PER_TILE は正の数")

if bpy.context.object is not None and bpy.context.object.mode != "OBJECT":
    bpy.ops.object.mode_set(mode="OBJECT")


def rotate(u, v, deg):
    return (u, v) if deg == 0 else (-v, u)


report, skipped = [], []
for name in OBJECTS:
    ob = bpy.data.objects.get(name)
    if ob is None or ob.type != "MESH":
        skipped.append({"object": name, "reason": "見つからないか、メッシュではない"})
        continue
    me = ob.data
    m3 = ob.matrix_world.to_3x3()
    n3 = m3.inverted_safe().transposed()

    bm = bmesh.new()
    bm.from_mesh(me)
    pos = {v: m3 @ v.co for v in bm.verts}
    xs = [p.x for p in pos.values()]
    ys = [p.y for p in pos.values()]
    zs = [p.z for p in pos.values()]
    xmin, xmax, ymin, ymax, zmin, zmax = min(xs), max(xs), min(ys), max(ys), min(zs), max(zs)
    width, depth = xmax - xmin, ymax - ymin

    def nearest_side(c):
        """面の中心の位置から、最も近い側面を返す。"""
        d = {"front": c.y - ymin, "back": ymax - c.y, "left": c.x - xmin, "right": xmax - c.x}
        return min(d, key=d.get)

    uv_layer = bm.loops.layers.uv.get(UV_NAME) or bm.loops.layers.uv.new(UV_NAME)
    counts = {"cap_top": 0, "cap_bottom": 0, "ledge": 0,
              "front": 0, "right": 0, "back": 0, "left": 0}

    for f in bm.faces:
        n = n3 @ f.normal
        horizontal = False
        if n.length > 1e-8:
            n.normalize()
            horizontal = abs(n.z) >= CAP_THRESHOLD
        zs_f = [pos[v].z for v in f.verts]

        cap = None
        if horizontal:
            if CAP_Z == "ALL":
                cap = "cap_top" if n.z > 0 else "cap_bottom"
            elif n.z > 0 and min(zs_f) >= zmax - Z_TOLERANCE:
                cap = "cap_top"
            elif n.z < 0 and max(zs_f) <= zmin + Z_TOLERANCE:
                cap = "cap_bottom"

        if cap is not None:
            counts[cap] += 1
            if CAP_MATERIAL_INDEX is not None:
                f.material_index = CAP_MATERIAL_INDEX
            for loop in f.loops:
                if CAP_MODE == "POINT":
                    loop[uv_layer].uv = CAP_POINT
                    continue
                p = pos[loop.vert]
                u, v = (p.x, p.y) if cap == "cap_top" else (p.x, -p.y)
                u, v = rotate(u, v, CAP_ROTATE)
                loop[uv_layer].uv = (u / METERS_PER_TILE + OFFSET[0], v / METERS_PER_TILE + OFFSET[1])
            continue

        # 側面: 傾いた面は法線の水平成分で、水平な面（途中の高さ）や法線が定まらない面は位置で、どの側かを決める
        if horizontal or n.length < 1e-8 or (abs(n.x) < 1e-6 and abs(n.y) < 1e-6):
            side = nearest_side(f.calc_center_median())
            if horizontal:
                counts["ledge"] += 1
        elif abs(n.x) >= abs(n.y):
            side = "right" if n.x > 0 else "left"
        else:
            side = "back" if n.y > 0 else "front"
        counts[side] += 1

        for loop in f.loops:
            p = pos[loop.vert]
            if MODE == "WRAP":
                if side == "front":
                    u = p.x - xmin
                elif side == "right":
                    u = width + (p.y - ymin)
                elif side == "back":
                    u = width + depth + (xmax - p.x)
                else:
                    u = 2 * width + depth + (ymax - p.y)
            else:
                u = {"front": p.x, "right": p.y, "back": -p.x, "left": -p.y}[side]
            u, v = rotate(u, p.z - zmin, SIDE_ROTATE)
            loop[uv_layer].uv = (u / METERS_PER_TILE + OFFSET[0], v / METERS_PER_TILE + OFFSET[1])

    bm.to_mesh(me)
    bm.free()
    layer = me.uv_layers[UV_NAME]
    me.uv_layers.active = layer
    layer.active_render = True
    me.update()

    notes = []
    if counts["cap_top"] == 0 and counts["cap_bottom"] == 0:
        notes.append("キャップ（最上部・最下部の水平な面）が見つからなかった")
    if counts["ledge"]:
        notes.append(f"途中の高さの水平な面 {counts['ledge']} 枚を側面に含めた（投影方向と平行なので UV が線状に潰れ、その高さの模様の色が伸びる）")
    if CAP_MATERIAL_INDEX is not None and CAP_MATERIAL_INDEX >= len(ob.material_slots):
        notes.append(f"マテリアルスロット {CAP_MATERIAL_INDEX} がまだない（bjs-material で SLOT_INDEX = {CAP_MATERIAL_INDEX} のマテリアルを割り当てる）")
    if len(me.uv_layers) > 1:
        notes.append(f"UV マップが {len(me.uv_layers)} 個ある（{[l.name for l in me.uv_layers]}）。不要なものは整理を検討")
    if me.users > 1:
        notes.append(f"メッシュ {me.name} を {me.users} 個のオブジェクトで共有している（すべてに反映）")
    geo_mods = [m.name for m in ob.modifiers if m.type != "NODES" and m.show_viewport]
    if geo_mods:
        notes.append(f"未適用のモディファイア {geo_mods} がある（形を変えるものなら、その部分の UV は補間になる）")
    report.append({
        "object": name,
        "mode": MODE,
        "faces_by_group": counts,
        "perimeter_m": round(2 * (width + depth), 4),
        "tiles_around": round(2 * (width + depth) / METERS_PER_TILE, 3),
        "notes": notes,
    })

result = {"objects": report, "skipped": skipped}
