"""bjs-uv: UV 展開の前に、形を変えるモディファイア（Bevel など）を適用して面を確定する。

適用するモディファイアは名前で明示する（ユーザーの了承を得たものだけ）。
適用すると元に戻しにくい。メッシュを共有しているオブジェクトはスキップする。
"""
import bpy

# --- パラメータ ---
APPLY = {  # オブジェクト名: [適用するモディファイア名]（スタックの上から順に適用する）
    "Crate_A": ["Bevel"],
}
# --- ここまで ---

view_layer = bpy.context.view_layer
if bpy.context.object is not None and bpy.context.object.mode != "OBJECT":
    bpy.ops.object.mode_set(mode="OBJECT")

applied, skipped = [], []
for name, mod_names in APPLY.items():
    ob = bpy.data.objects.get(name)
    if ob is None or ob.type != "MESH":
        skipped.append({"object": name, "reason": "見つからないか、メッシュではない"})
        continue
    if ob.data.users > 1:
        skipped.append({"object": name, "reason": f"メッシュ {ob.data.name} を {ob.data.users} 個のオブジェクトで共有している"})
        continue
    for o in view_layer.objects:
        o.select_set(False)
    ob.select_set(True)
    view_layer.objects.active = ob
    # スタックの順序どおりに適用する
    order = [m.name for m in ob.modifiers if m.name in mod_names]
    missing = [m for m in mod_names if m not in order]
    for m in missing:
        skipped.append({"object": name, "modifier": m, "reason": "モディファイアが見つからない"})
    for m in order:
        bpy.ops.object.modifier_apply(modifier=m)
        applied.append({"object": name, "modifier": m})

report = []
for name in APPLY:
    ob = bpy.data.objects.get(name)
    if ob is None or ob.type != "MESH":
        continue
    me = ob.data
    me.calc_loop_triangles()
    report.append({
        "object": name,
        "faces": len(me.polygons),
        "triangles_base": len(me.loop_triangles),
        "remaining_modifiers": [m.type for m in ob.modifiers],
    })

result = {"applied": applied, "skipped": skipped, "objects": report}
