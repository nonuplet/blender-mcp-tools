"""bjs-animation: オブジェクトのアクティブな Action を NLA トラックへ退避する（Push Down 相当）。

トラック名を既定から変えると、glTF の animation 名（Babylon の AnimationGroup 名）になる。
"""
import bpy

# --- パラメータ ---
OBJECTS = ["Door_A"]  # 退避するオブジェクト名のリスト
TRACK_NAME = None     # トラック名。None なら各オブジェクトの Action 名
# --- ここまで ---

pushed, skipped = [], []
for name in OBJECTS:
    ob = bpy.data.objects.get(name)
    ad = ob.animation_data if ob else None
    if ad is None or ad.action is None:
        skipped.append({"object": name, "reason": "アクティブな Action がない"})
        continue
    act = ad.action
    slot = ad.action_slot
    track = ad.nla_tracks.new()
    track.name = TRACK_NAME or act.name
    strip = track.strips.new(act.name, int(act.frame_range[0]), act)
    if slot is not None and strip.action_slot != slot:
        strip.action_slot = slot
    ad.action = None
    pushed.append({
        "object": name,
        "action": act.name,
        "track": track.name,
        "strip_frames": [strip.frame_start, strip.frame_end],
    })

result = {"pushed": pushed, "skipped": skipped}
