"""bjs-material: コードで模様の画像を生成し、マテリアルの Base Color につなぐ。

画像は .blend に pack する（pack しないと、保存して開き直したときに模様が消える）。
ファイルの読み込み・書き出しは行わない。
"""
import bpy
import random

# --- パラメータ ---
IMAGE_NAME = "T_Wood_Stripes"
SIZE = 512                   # 一辺のピクセル数（2 のべき乗にする）
PATTERN = "STRIPES"          # "CHECKER" / "STRIPES" / "GRADIENT" / "SOLID"
COLOR_A = "#A0703C"          # "#RRGGBB"（sRGB）
COLOR_B = "#8A5E30"          # "#RRGGBB"（sRGB）
CELLS = 8                    # CHECKER のマス数・STRIPES の本数
GRAIN = 0.05                 # ピクセルごとの明るさのばらつき（0〜1）
SEED = 0                     # GRAIN の乱数シード
INTERPOLATION = "Linear"     # "Linear" / "Closest"（ドット絵風）
MATERIAL = "M_Wood"          # 画像をつなぐマテリアル。None ならつながない
# --- ここまで ---


def hex_to_rgb(color):
    h = color.lstrip("#")
    if len(h) != 6:
        raise ValueError(f"カラーは #RRGGBB 形式にする: {color}")
    return [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]


if SIZE <= 0 or SIZE & (SIZE - 1):
    raise ValueError(f"SIZE は 2 のべき乗にする: {SIZE}")
if IMAGE_NAME in bpy.data.images:
    raise ValueError(f"画像 {IMAGE_NAME} は既にある。別の名前にする")
if PATTERN not in ("CHECKER", "STRIPES", "GRADIENT", "SOLID"):
    raise ValueError(f"PATTERN が不正: {PATTERN}")

a = hex_to_rgb(COLOR_A)
b = hex_to_rgb(COLOR_B)
rng = random.Random(SEED)

# バイト画像の pixels は sRGB の値をそのまま 0〜1 で書く
px = [0.0] * (SIZE * SIZE * 4)
for y in range(SIZE):
    v = y / (SIZE - 1)
    for x in range(SIZE):
        if PATTERN == "CHECKER":
            c = a if ((x * CELLS // SIZE) + (y * CELLS // SIZE)) % 2 == 0 else b
        elif PATTERN == "STRIPES":
            c = a if (y * CELLS // SIZE) % 2 == 0 else b
        elif PATTERN == "GRADIENT":
            c = [a[i] + (b[i] - a[i]) * v for i in range(3)]
        else:
            c = a
        k = 1.0 + (rng.random() * 2 - 1) * GRAIN if GRAIN else 1.0
        i = (y * SIZE + x) * 4
        px[i] = min(max(c[0] * k, 0.0), 1.0)
        px[i + 1] = min(max(c[1] * k, 0.0), 1.0)
        px[i + 2] = min(max(c[2] * k, 0.0), 1.0)
        px[i + 3] = 1.0

img = bpy.data.images.new(IMAGE_NAME, SIZE, SIZE, alpha=False)
img.pixels.foreach_set(px)
img.update()
img.pack()

connected = None
if MATERIAL is not None:
    mat = bpy.data.materials.get(MATERIAL)
    if mat is None:
        raise ValueError(f"マテリアルが見つからない: {MATERIAL}（画像 {IMAGE_NAME} は作成済み）")
    nodes = mat.node_tree.nodes
    bsdf = next((n for n in nodes if n.type == "BSDF_PRINCIPLED"), None)
    if bsdf is None:
        raise ValueError(f"{MATERIAL} に Principled BSDF がない（画像 {IMAGE_NAME} は作成済み）")
    tex = nodes.new("ShaderNodeTexImage")
    tex.image = img
    tex.interpolation = INTERPOLATION
    tex.location = (bsdf.location.x - 400, bsdf.location.y)
    base_in = bsdf.inputs["Base Color"]
    replaced = [l.from_node.name for l in base_in.links]
    mat.node_tree.links.new(tex.outputs["Color"], base_in)
    connected = {"material": MATERIAL, "replaced_links_from": replaced}

result = {
    "image": img.name,
    "size": list(img.size),
    "packed": img.packed_file is not None,
    "connected": connected,
}
