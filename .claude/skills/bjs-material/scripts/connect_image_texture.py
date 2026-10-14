"""bjs-material: ユーザーが Blender に読み込んだ画像を、マテリアルの入力につなぐ。

画像の読み込み自体はユーザーが GUI で行う（Claude からのファイル読み込みは hook で禁止）。
このスクリプトは、既に bpy.data.images にある画像を参照するだけで、ファイルには触れない。
"""
import bpy

# --- パラメータ ---
IMAGE = "wood_planks.png"  # 読み込み済みの画像の名前（bpy.data.images の名前）
MATERIAL = "M_Crate_Wood"  # つなぐマテリアル
INPUT = "Base Color"       # "Base Color" / "Normal" / "Emission Color"
INTERPOLATION = "Linear"   # "Linear" / "Closest"
EXTENSION = "REPEAT"       # "REPEAT"（タイル）/ "EXTEND" / "CLIP"
# --- ここまで ---

if INPUT not in ("Base Color", "Normal", "Emission Color"):
    raise ValueError(f"INPUT が不正: {INPUT}")
img = bpy.data.images.get(IMAGE)
if img is None:
    raise ValueError(f"画像が見つからない: {IMAGE}（読み込み済みの画像: {[i.name for i in bpy.data.images]}）")
mat = bpy.data.materials.get(MATERIAL)
if mat is None:
    raise ValueError(f"マテリアルが見つからない: {MATERIAL}")
nodes = mat.node_tree.nodes
links = mat.node_tree.links
bsdf = next((n for n in nodes if n.type == "BSDF_PRINCIPLED"), None)
if bsdf is None:
    raise ValueError(f"{MATERIAL} に Principled BSDF がない")

notes = []
# 色以外のデータ（法線）は Non-Color で読む
if INPUT == "Normal" and img.colorspace_settings.name != "Non-Color":
    notes.append(f"画像 {IMAGE} の色空間を {img.colorspace_settings.name} → Non-Color に変更")
    img.colorspace_settings.name = "Non-Color"

tex = nodes.new("ShaderNodeTexImage")
tex.image = img
tex.interpolation = INTERPOLATION
tex.extension = EXTENSION
tex.location = (bsdf.location.x - 600, bsdf.location.y)

target = bsdf.inputs[INPUT]
replaced = [l.from_node.name for l in target.links]
if INPUT == "Normal":
    nmap = nodes.new("ShaderNodeNormalMap")
    nmap.location = (bsdf.location.x - 250, bsdf.location.y - 300)
    links.new(tex.outputs["Color"], nmap.inputs["Color"])
    links.new(nmap.outputs["Normal"], target)
    notes.append("ノーマルマップを使うので、書き出し時に Data → Mesh → Tangents を ON にする")
else:
    links.new(tex.outputs["Color"], target)
    if INPUT == "Emission Color" and bsdf.inputs["Emission Strength"].default_value == 0:
        notes.append("Emission Strength が 0 なので発光しない。強さを決める必要がある")

w, h = img.size
if w & (w - 1) or h & (h - 1):
    notes.append(f"画像サイズ {w}x{h} が 2 のべき乗ではない")
if img.packed_file is None:
    notes.append("画像は外部ファイルを参照している（.blend を移動する場合は、ユーザーに File → External Data → Pack Resources を依頼する）")

result = {
    "image": img.name,
    "size": [w, h],
    "colorspace": img.colorspace_settings.name,
    "material": MATERIAL,
    "target_input": INPUT,
    "replaced_links_from": replaced,
    "notes": notes,
}
