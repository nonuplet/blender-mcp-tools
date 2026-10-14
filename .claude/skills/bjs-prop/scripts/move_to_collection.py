"""bjs-prop / bjs-environment: オブジェクトを別のコレクションへ移す（WIP → EXPORT など）。

移動先にリンクしてから、移動元からアンリンクする（途中でどのコレクションにも属さない状態を作らない）。
"""
import bpy

# --- パラメータ ---
OBJECTS = ["Crate_A"]    # 移すオブジェクト名のリスト
FROM = "WIP"             # 移動元のコレクション。None なら移動先以外のすべてのコレクションから外す
TO = "EXPORT"            # 移動先のコレクション
INCLUDE_CHILDREN = True  # True なら子孫のオブジェクトも一緒に移す
# --- ここまで ---

dst = bpy.data.collections.get(TO)
if dst is None:
    raise ValueError(f"移動先のコレクションが見つからない: {TO}")
src = None
if FROM is not None:
    src = bpy.data.collections.get(FROM)
    if src is None:
        raise ValueError(f"移動元のコレクションが見つからない: {FROM}")

targets, missing = [], []
for name in OBJECTS:
    ob = bpy.data.objects.get(name)
    if ob is None:
        missing.append(name)
        continue
    targets.append(ob)
    if INCLUDE_CHILDREN:
        targets.extend(ob.children_recursive)

moved, seen = [], set()
for ob in targets:
    if ob.name in seen:
        continue
    seen.add(ob.name)
    if ob.name not in dst.objects:
        dst.objects.link(ob)
    sources = [src] if src is not None else [c for c in ob.users_collection if c != dst]
    for c in sources:
        if ob.name in c.objects:
            c.objects.unlink(ob)
    moved.append({"object": ob.name, "collections": [c.name for c in ob.users_collection]})

result = {"moved": moved, "missing": missing}
