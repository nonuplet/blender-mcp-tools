"""bjs-environment: モジュールのリンク複製（メッシュデータを共有する複製）を並べる。

Babylon ではインスタンスとして読み込まれる。元のオブジェクトの子は複製しない。
"""
import bpy
import math

# --- パラメータ ---
SOURCE = "Floor_2m"   # 複製元のオブジェクト名
PLACEMENTS = [        # (位置 (x, y, z) [m], Z 軸の回転 [度])
    ((0, 0, 0), 0),
    ((2, 0, 0), 0),
]
NAME_PREFIX = None    # 複製の名前の接頭辞。None なら SOURCE と同じ（例: Floor_2m_001）
COLLECTION = "EXPORT" # 複製を入れるコレクション
# --- ここまで ---

src = bpy.data.objects.get(SOURCE)
if src is None:
    raise ValueError(f"複製元が見つからない: {SOURCE}")
coll = bpy.data.collections.get(COLLECTION)
if coll is None:
    raise ValueError(f"コレクションが見つからない: {COLLECTION}")

prefix = NAME_PREFIX or SOURCE
created = []
for i, (loc, rot_z) in enumerate(PLACEMENTS, start=1):
    dup = src.copy()  # data は共有される（リンク複製）
    dup.name = f"{prefix}_{i:03d}"
    dup.parent = None
    dup.location = loc
    dup.rotation_euler.z = src.rotation_euler.z + math.radians(rot_z)
    coll.objects.link(dup)
    created.append(dup.name)

renamed = [n for n in created if not n.startswith(f"{prefix}_")]

result = {
    "source": src.name,
    "mesh": src.data.name if src.data else None,
    "mesh_users": src.data.users if src.data else None,
    "created": created,
    "has_children_not_copied": [c.name for c in src.children],
    "name_conflicts": renamed,
}
