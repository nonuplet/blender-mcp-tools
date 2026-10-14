"""bjs-environment: オブジェクトにカスタムプロパティ（Babylon の metadata.gltf.extras になる）を付ける。

書き出し時に Include → Custom Properties を ON にすると glTF の extras になる。
"""
import bpy

# --- パラメータ ---
TAGS = {  # オブジェクト名: {キー: 値}。値は文字列・数値・真偽値
    "Door_A": {"bjs_role": "door", "bjs_interactive": True},
}
# --- ここまで ---

applied, missing = [], []
for name, props in TAGS.items():
    ob = bpy.data.objects.get(name)
    if ob is None:
        missing.append(name)
        continue
    for key, value in props.items():
        if not isinstance(value, (str, int, float, bool)):
            raise ValueError(f"{name}.{key}: 値は文字列・数値・真偽値にする")
        ob[key] = value
    applied.append({"object": name, "properties": {k: ob[k] for k in props}})

result = {"applied": applied, "missing": missing}
