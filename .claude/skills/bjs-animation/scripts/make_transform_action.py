"""bjs-animation: オブジェクトの位置・回転・スケールのキーフレームで Action を作る。

Action 名は Babylon の AnimationGroup 名になる。
ADD_TO_EXISTING_ACTION = True なら、既存の Action にこのオブジェクト用のスロットを追加する
（複数のオブジェクトの動きを 1 つの AnimationGroup にまとめる）。
オブジェクトにすでにアクティブな Action がある場合は止まる（先に push_down_action.py で NLA へ退避する）。
"""
import bpy
import math

# --- パラメータ ---
OBJECT = "Fan_Blade"
ACTION_NAME = "Fan_Spin"
KEYS = [  # frame は必須。location [m] / rotation_euler [度] / scale は必要なものだけ書く
    {"frame": 1, "rotation_euler": (0, 0, 0)},
    {"frame": 60, "rotation_euler": (0, 0, 360)},
]
INTERPOLATION = "LINEAR"        # "LINEAR" / "BEZIER" / "CONSTANT"
CYCLIC = True                   # ループ用の目印（Action の Cyclic を ON にする）
ADD_TO_EXISTING_ACTION = False  # True: 既存の Action ACTION_NAME にこのオブジェクトのスロットを追加する
# --- ここまで ---

ALLOWED = {"frame", "location", "rotation_euler", "scale"}

ob = bpy.data.objects.get(OBJECT)
if ob is None:
    raise ValueError(f"オブジェクトが見つからない: {OBJECT}")
existing = bpy.data.actions.get(ACTION_NAME)
if existing is not None and not ADD_TO_EXISTING_ACTION:
    raise ValueError(f"Action {ACTION_NAME} は既にある。スロットを追加する場合は ADD_TO_EXISTING_ACTION = True")
if existing is None and ADD_TO_EXISTING_ACTION:
    raise ValueError(f"スロットを追加する Action {ACTION_NAME} がない")
if ob.rotation_mode in ("QUATERNION", "AXIS_ANGLE"):
    raise ValueError(f"回転モードがオイラーではない: {ob.rotation_mode}")
for k in KEYS:
    if "frame" not in k or not set(k) <= ALLOWED:
        raise ValueError(f"KEYS の形式が不正: {k}")

ad = ob.animation_data or ob.animation_data_create()
if ad.action is not None:
    raise ValueError(f"{OBJECT} にはアクティブな Action {ad.action.name} がある。先に NLA へ退避する")

if existing is None:
    act = bpy.data.actions.new(ACTION_NAME)
    ad.action = act
else:
    act = existing
    if any(s.identifier == "OB" + ob.name for s in act.slots):
        raise ValueError(f"Action {ACTION_NAME} には {OBJECT} 用のスロットが既にある")
    new_slot = act.slots.new(id_type="OBJECT", name=ob.name)
    ad.action = act
    ad.action_slot = new_slot

for k in sorted(KEYS, key=lambda k: k["frame"]):
    f = k["frame"]
    if "location" in k:
        ob.location = k["location"]
        ob.keyframe_insert("location", frame=f)
    if "rotation_euler" in k:
        ob.rotation_euler = [math.radians(d) for d in k["rotation_euler"]]
        ob.keyframe_insert("rotation_euler", frame=f)
    if "scale" in k:
        ob.scale = k["scale"]
        ob.keyframe_insert("scale", frame=f)

# 補間の設定（Blender 4.4 以降のレイヤー付き Action: layers → strips → channelbag → fcurves）
slot = ad.action_slot
fcurves = 0
for layer in act.layers:
    for strip in layer.strips:
        if strip.type != "KEYFRAME":
            continue
        bag = strip.channelbag(slot)
        if bag is None:
            continue
        for fc in bag.fcurves:
            fcurves += 1
            for kp in fc.keyframe_points:
                kp.interpolation = INTERPOLATION

frames = [k["frame"] for k in KEYS]
if existing is not None and act.use_frame_range:
    frames += [act.frame_start, act.frame_end]
act.use_frame_range = True
act.frame_start = min(frames)
act.frame_end = max(frames)
act.use_cyclic = CYCLIC
bpy.context.scene.frame_set(int(min(frames)))

result = {
    "object": ob.name,
    "action": act.name,
    "slot": slot.identifier if slot else None,
    "action_slots": [s.identifier for s in act.slots],
    "fcurves": fcurves,
    "frame_range": [act.frame_start, act.frame_end],
    "cyclic": act.use_cyclic,
}
