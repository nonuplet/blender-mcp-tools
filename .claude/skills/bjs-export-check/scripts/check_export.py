"""bjs-export-check: GLB 書き出し前の検査（読み取りのみ。シーンは変更しない）。

結果は errors（書き出すと問題になる）/ warnings（確認が必要）/ infos（参考）に分けて返す。
"""
import bpy
import bmesh
import re
from mathutils import Vector

# --- パラメータ ---
COLLECTION = "EXPORT"     # 検査するコレクション。None ならシーン内の表示中オブジェクトすべて
TRI_BUDGET_TOTAL = 50000  # 合計三角形数の目安
TRI_BUDGET_OBJECT = 10000 # 1 オブジェクトあたりの三角形数の目安
MAX_TEXTURE_SIZE = 2048   # テクスチャの一辺の上限の目安
# --- ここまで ---

errors, warnings, infos = [], [], []


def add(level, target, msg):
    level.append(f"[{target}] {msg}")


scene = bpy.context.scene
units = scene.unit_settings
# 単位系（unit_settings.system）は hook が属性名 system を deny にしているため、length_unit で判断する
if units.length_unit in {"MILES", "FEET", "INCHES", "THOU"}:
    add(warnings, "scene", f"長さの単位がヤード・ポンド法（{units.length_unit}）")
if abs(units.scale_length - 1.0) > 1e-6:
    add(warnings, "scene", f"scale_length が 1.0 ではない（{units.scale_length}）")

if COLLECTION is not None:
    coll = bpy.data.collections.get(COLLECTION)
    if coll is None:
        add(errors, "scene", f"コレクション {COLLECTION} がない")
        targets = []
    else:
        targets = list(coll.all_objects)
else:
    targets = [o for o in scene.objects if o.visible_get()]

if not targets:
    add(errors, "scene", "検査対象のオブジェクトがない")

SUPPORTED = {"MESH", "EMPTY", "ARMATURE", "LIGHT", "CAMERA"}
GOOD_SHADERS = {"BSDF_PRINCIPLED", "EMISSION", "ADD_SHADER", "MIX_SHADER"}
NAME_RE = re.compile(r"^[A-Za-z0-9_]+$")
AUTO_SUFFIX_RE = re.compile(r"\.\d{3}$")

depsgraph = bpy.context.evaluated_depsgraph_get()
total_tris = 0
materials = {}
objects_report = []

for ob in targets:
    name = ob.name
    if not NAME_RE.match(name):
        level = infos if AUTO_SUFFIX_RE.search(name) and NAME_RE.match(AUTO_SUFFIX_RE.sub("", name)) else warnings
        add(level, name, "名前に英数字・アンダースコア以外の文字がある（.001 などの自動連番を含む）")
    if ob.type not in SUPPORTED:
        add(warnings, name, f"{ob.type} はそのままでは意図どおりに書き出されない可能性がある。メッシュへの変換を検討")
    if not ob.visible_get():
        add(infos, name, "非表示（Include → Visible Objects を ON にすると書き出されない）")
    if ob.type == "LIGHT":
        add(infos, name, "ライト。Include → Punctual Lights を ON にした場合だけ書き出される（照明は原則 Babylon 側で置く）")
    if ob.type == "CAMERA":
        add(infos, name, "カメラ。Include → Cameras を ON にした場合だけ書き出される")

    # トランスフォーム
    if any(s < 0 for s in ob.scale):
        add(errors, name, f"負のスケール {tuple(round(s, 3) for s in ob.scale)}（法線が反転する）")
    elif ob.type == "MESH" and any(abs(s - 1.0) > 1e-4 for s in ob.scale):
        add(warnings, name, f"スケールが未適用 {tuple(round(s, 3) for s in ob.scale)}（finalize_mesh.py で適用を推奨）")

    if ob.type != "MESH":
        continue

    entry = {"object": name}
    me = ob.data
    if me.users > 1:
        add(infos, name, f"メッシュ {me.name} を {me.users} 個のオブジェクトで共有（Babylon ではインスタンスになる）")

    # モディファイア適用後のメッシュで数える（Apply Modifiers ON の前提）
    ob_eval = ob.evaluated_get(depsgraph)
    em = ob_eval.to_mesh()
    em.calc_loop_triangles()
    tris = len(em.loop_triangles)
    bm = bmesh.new()
    bm.from_mesh(em)
    ob_eval.to_mesh_clear()

    nonmanifold = sum(1 for e in bm.edges if len(e.link_faces) > 2)
    boundary = sum(1 for e in bm.edges if e.is_boundary)
    loose_verts = sum(1 for v in bm.verts if not v.link_edges)
    loose_edges = sum(1 for e in bm.edges if not e.link_faces)
    degenerate = sum(1 for f in bm.faces if f.calc_area() < 1e-10)
    ngons = sum(1 for f in bm.faces if len(f.verts) > 4)
    bm.free()

    total_tris += tris
    entry["triangles"] = tris
    if tris > TRI_BUDGET_OBJECT:
        add(warnings, name, f"三角形数 {tris} が目安 {TRI_BUDGET_OBJECT} を超えている")
    if nonmanifold:
        add(warnings, name, f"3 面以上が接する辺が {nonmanifold} 本（非多様体）")
    if boundary:
        add(infos, name, f"開いた辺（穴・板の縁）が {boundary} 本。板ポリなら問題ない")
    if loose_verts or loose_edges:
        add(warnings, name, f"孤立した頂点 {loose_verts} 個・辺 {loose_edges} 本（書き出されないか線として出る）")
    if degenerate:
        add(warnings, name, f"面積がほぼ 0 の面が {degenerate} 枚")
    if ngons:
        add(infos, name, f"5 角形以上の面が {ngons} 枚（書き出し時に三角形化される。シェーディングを確認）")

    # モディファイア
    mods = [m.type for m in ob.modifiers if m.show_viewport]
    if mods:
        entry["modifiers"] = mods
        add(infos, name, f"モディファイア {mods}（Data → Mesh → Apply Modifiers を ON にすること）")

    # 寸法と原点
    corners = [ob.matrix_world @ Vector(c) for c in ob.bound_box]
    lo = Vector((min(c.x for c in corners), min(c.y for c in corners), min(c.z for c in corners)))
    hi = Vector((max(c.x for c in corners), max(c.y for c in corners), max(c.z for c in corners)))
    entry["size_m"] = [round(v, 4) for v in (hi - lo)]
    origin = ob.matrix_world.translation
    bottom_center = Vector(((lo.x + hi.x) / 2, (lo.y + hi.y) / 2, lo.z))
    entry["origin_offset_from_bottom_center"] = [round(v, 4) for v in (origin - bottom_center)]

    # UV とマテリアル
    entry["uv_layers"] = len(me.uv_layers)
    slots = ob.material_slots
    if len(slots) == 0:
        add(infos, name, "マテリアルなし（Babylon ではデフォルトのマテリアルになる）")
    if len(slots) > 1:
        add(infos, name, f"マテリアル {len(slots)} 個（Babylon では {name}_primitive0 … の子メッシュに分かれる）")
    for i, slot in enumerate(slots):
        if slot.material is None:
            add(warnings, name, f"マテリアルスロット {i} が空")
        else:
            materials.setdefault(slot.material.name, []).append(name)
    objects_report.append(entry)

# マテリアル
uses_image = set()
uses_vertex_color = set()
for mat_name, users in materials.items():
    mat = bpy.data.materials[mat_name]
    tree = mat.node_tree
    if tree is None:
        add(warnings, mat_name, "ノードツリーがない")
        continue
    outputs = [n for n in tree.nodes if n.type == "OUTPUT_MATERIAL" and n.is_active_output]
    if not outputs or not outputs[0].inputs["Surface"].links:
        add(errors, mat_name, "Material Output の Surface に何もつながっていない")
    else:
        shader = outputs[0].inputs["Surface"].links[0].from_node
        if shader.type not in GOOD_SHADERS:
            add(warnings, mat_name, f"Material Output に {shader.type} がつながっている（Principled BSDF 以外は正しく書き出されない）")
    for n in tree.nodes:
        if n.type.startswith("TEX_") and n.type not in ("TEX_IMAGE", "TEX_COORD"):
            add(warnings, mat_name, f"{n.type} ノードは書き出されない（プロシージャルテクスチャ）")
        if n.type == "VERTEX_COLOR":
            uses_vertex_color.update(users)
        if n.type == "TEX_IMAGE":
            img = n.image
            if img is None:
                add(errors, mat_name, f"Image Texture ノード {n.name} に画像がない")
                continue
            uses_image.update(users)
            w, h = img.size
            if w == 0 or h == 0:
                add(errors, mat_name, f"画像 {img.name} のピクセルデータがない（欠落ファイルの可能性）")
            if w & (w - 1) or h & (h - 1):
                add(warnings, mat_name, f"画像 {img.name} のサイズ {w}x{h} が 2 のべき乗ではない")
            if max(w, h) > MAX_TEXTURE_SIZE:
                add(warnings, mat_name, f"画像 {img.name} のサイズ {w}x{h} が目安 {MAX_TEXTURE_SIZE} を超えている")
            if img.source == "GENERATED" and img.packed_file is None:
                add(warnings, mat_name, f"生成画像 {img.name} が pack されていない（保存して開き直すと模様が消える）")
    if not mat.use_backface_culling:
        add(infos, mat_name, "両面表示（doubleSided）。不要なら Backface Culling を ON に")
    bsdf = next((n for n in tree.nodes if n.type == "BSDF_PRINCIPLED"), None)
    if bsdf is not None:
        alpha = bsdf.inputs["Alpha"]
        if alpha.links or alpha.default_value < 1.0:
            add(infos, mat_name, "透明あり（MASK か BLEND になる。BLEND は描画順の問題に注意）")
        if bsdf.inputs["Emission Strength"].default_value > 1.0:
            add(infos, mat_name, "発光の強さが 1 超（KHR_materials_emissive_strength。Babylon は対応）")

for ob in targets:
    if ob.name in uses_image and ob.type == "MESH" and len(ob.data.uv_layers) == 0:
        add(errors, ob.name, "画像テクスチャを使っているが UV がない")
    if ob.name in uses_vertex_color and ob.type == "MESH" and len(ob.data.color_attributes) == 0:
        add(errors, ob.name, "マテリアルで頂点カラーを使っているが、メッシュに頂点カラーがない")

# アニメーション
exported_actions = set()
anim_report = []
for ob in targets:
    owners = [("object", ob)]
    if ob.type == "MESH" and ob.data.shape_keys is not None:
        owners.append(("shape_keys", ob.data.shape_keys))
    for kind, owner in owners:
        ad = owner.animation_data
        if ad is None:
            continue
        if ad.action is not None:
            exported_actions.add(ad.action.name)
            anim_report.append({"object": ob.name, "kind": kind, "active_action": ad.action.name,
                                "slot": ad.action_slot.identifier if ad.action_slot else None})
        for track in ad.nla_tracks:
            for strip in track.strips:
                if strip.action is not None:
                    exported_actions.add(strip.action.name)
                    anim_report.append({"object": ob.name, "kind": kind, "nla_track": track.name,
                                        "action": strip.action.name, "muted": track.mute})

for act in bpy.data.actions:
    if act.name not in exported_actions:
        add(warnings, act.name, "対象オブジェクトのアクティブな Action にも NLA にもない（Animation Mode = Actions では書き出されない）")
    elif not NAME_RE.match(act.name):
        add(warnings, act.name, "Action 名に英数字・アンダースコア以外の文字がある（AnimationGroup 名になる）")

if total_tris > TRI_BUDGET_TOTAL:
    add(warnings, "scene", f"合計三角形数 {total_tris} が目安 {TRI_BUDGET_TOTAL} を超えている")

result = {
    "summary": {
        "collection": COLLECTION,
        "objects": len(targets),
        "meshes": len(objects_report),
        "triangles_total": total_tris,
        "materials": len(materials),
        "actions_exported": sorted(exported_actions),
        "fps": round(scene.render.fps / scene.render.fps_base, 3),
        "errors": len(errors),
        "warnings": len(warnings),
    },
    "errors": errors,
    "warnings": warnings,
    "infos": infos,
    "objects": objects_report,
    "animations": anim_report,
}
