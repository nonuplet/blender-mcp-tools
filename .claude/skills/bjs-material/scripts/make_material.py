"""bjs-material: glTF に書き出せる Principled BSDF のマテリアルを作り、オブジェクトに割り当てる。

同名のマテリアルがある場合は、OVERWRITE = True のときだけノードを作り直す。
"""
import bpy

# --- パラメータ ---
NAME = "M_Wood"
BASE_COLOR = "#A0703C"      # "#RRGGBB"（sRGB）か、リニアの (r, g, b)
METALLIC = 0.0
ROUGHNESS = 0.6
EMISSION_COLOR = "#000000"  # "#RRGGBB" か、リニアの (r, g, b)
EMISSION_STRENGTH = 0.0     # 0 なら発光しない
ALPHA = 1.0                 # 1 未満で半透明（glTF の BLEND）
DOUBLE_SIDED = False        # True で両面表示（Backface Culling を OFF）
USE_VERTEX_COLOR = False    # True で頂点カラーを Base Color に乗算する
VERTEX_COLOR_NAME = ""      # 使う頂点カラーの名前。"" ならメッシュの既定の頂点カラー
ASSIGN_TO = ["Crate_A"]     # 割り当てるオブジェクト名のリスト（空なら割り当てない）
SLOT_INDEX = 0              # 割り当てるマテリアルスロット（スロットがなければ追加する）
OVERWRITE = False           # 同名のマテリアルがある場合に作り直すか
# --- ここまで ---


def to_linear(color):
    """'#RRGGBB'（sRGB）か (r, g, b)（リニア）を、リニアの (r, g, b, 1) にする。"""
    if isinstance(color, str):
        h = color.lstrip("#")
        if len(h) != 6:
            raise ValueError(f"カラーは #RRGGBB 形式にする: {color}")
        srgb = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
        lin = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in srgb]
    else:
        lin = list(color)[:3]
    return (lin[0], lin[1], lin[2], 1.0)


def socket(sockets, name, type_=None):
    for s in sockets:
        if s.name == name and (type_ is None or s.type == type_):
            return s
    raise KeyError(f"ソケットが見つからない: {name}")


notes = []
mat = bpy.data.materials.get(NAME)
if mat is not None and not OVERWRITE:
    raise ValueError(f"マテリアル {NAME} は既にある（users={mat.users}）。作り直す場合は OVERWRITE = True")
if mat is None:
    mat = bpy.data.materials.new(NAME)
else:
    notes.append(f"既存のマテリアル {NAME} を作り直した（users={mat.users}）")

nodes = mat.node_tree.nodes
links = mat.node_tree.links
nodes.clear()

out = nodes.new("ShaderNodeOutputMaterial")
out.location = (300, 0)
bsdf = nodes.new("ShaderNodeBsdfPrincipled")
bsdf.location = (0, 0)
links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])

base = to_linear(BASE_COLOR)
bsdf.inputs["Base Color"].default_value = base
bsdf.inputs["Metallic"].default_value = METALLIC
bsdf.inputs["Roughness"].default_value = ROUGHNESS
bsdf.inputs["Emission Color"].default_value = to_linear(EMISSION_COLOR)
bsdf.inputs["Emission Strength"].default_value = EMISSION_STRENGTH
bsdf.inputs["Alpha"].default_value = ALPHA

if USE_VERTEX_COLOR:
    vc = nodes.new("ShaderNodeVertexColor")
    vc.location = (-500, 100)
    vc.layer_name = VERTEX_COLOR_NAME
    if base[:3] == (1.0, 1.0, 1.0):
        links.new(vc.outputs["Color"], bsdf.inputs["Base Color"])
    else:
        mix = nodes.new("ShaderNodeMix")
        mix.location = (-250, 100)
        mix.data_type = "RGBA"
        mix.blend_type = "MULTIPLY"
        socket(mix.inputs, "Factor", "VALUE").default_value = 1.0
        links.new(vc.outputs["Color"], socket(mix.inputs, "A", "RGBA"))
        socket(mix.inputs, "B", "RGBA").default_value = base
        links.new(socket(mix.outputs, "Result", "RGBA"), bsdf.inputs["Base Color"])

mat.use_backface_culling = not DOUBLE_SIDED
mat.surface_render_method = "BLENDED" if ALPHA < 1.0 else "DITHERED"
# ソリッド表示での色
mat.diffuse_color = base
mat.metallic = METALLIC
mat.roughness = ROUGHNESS

assigned, missing = [], []
for name in ASSIGN_TO:
    ob = bpy.data.objects.get(name)
    if ob is None or ob.type != "MESH":
        missing.append(name)
        continue
    if SLOT_INDEX < len(ob.material_slots):
        ob.material_slots[SLOT_INDEX].material = mat
    else:
        ob.data.materials.append(mat)
        notes.append(f"{name}: マテリアルスロットを追加（メッシュ {ob.data.name} を共有するオブジェクトすべてに反映）")
    assigned.append(name)

result = {
    "material": mat.name,
    "users": mat.users,
    "base_color_linear": [round(c, 4) for c in base],
    "alpha_mode": "BLEND" if ALPHA < 1.0 else "OPAQUE",
    "double_sided": DOUBLE_SIDED,
    "vertex_color": USE_VERTEX_COLOR,
    "assigned": assigned,
    "missing": missing,
    "notes": notes,
}
