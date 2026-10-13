#!/usr/bin/env python3
"""execute_blender_code に渡されるコードを静的検査する PreToolUse hook。

コードは実行せず、ast で構文解析してパターンを照合するだけ。
- deny: CLAUDE.md の禁止事項（ファイル書き込み・削除、外部ネットワーク、
        他の .blend / 3Dモデルの読み込み）に該当しうるもの
- ask : 実行自体は可能だが、ユーザーに注意を促したいもの（理由付きで確認）
該当なしの場合は何も出力せず、通常の permission ルール（ask）に任せる。
検査中に例外が起きた場合は deny を返す（fail-closed）。

静的検査なので完全な防御ではない。最終的な防御線は execute_blender_code の ask 確認。
"""
import ast
import json
import re
import sys

# import を許可するモジュール（トップレベル名）。これ以外は deny。
ALLOWED_MODULES = {
    "bpy", "bmesh", "mathutils", "bpy_extras", "gpu", "gpu_extras",
    "math", "random", "colorsys", "itertools", "functools", "collections",
    "typing", "dataclasses", "enum", "statistics", "copy", "json", "re",
    "time", "string",
}

# 呼び出し・参照を禁止する組み込み名
BLOCKED_NAMES = {
    "open": "ファイル操作 (open)",
    "exec": "動的コード実行 (exec)",
    "eval": "動的コード実行 (eval)",
    "compile": "動的コード実行 (compile)",
    "__import__": "動的 import (__import__)",
    "breakpoint": "デバッガ起動 (breakpoint)",
    "input": "標準入力待ち (input)",
    "__builtins__": "組み込み関数への直接アクセス (__builtins__)",
}

# 直接呼び出し以外の使い方（別名代入・関数への受け渡し）を禁止する組み込み名。
# functools.reduce(getattr, [...], bpy) のような間接参照を防ぐ。
INDIRECT_BLOCKED_NAMES = {"getattr", "setattr", "delattr", "globals", "locals", "vars"}

# 属性として参照されたら deny する名前（モジュール経由で組み込み関数に届くのを防ぐ）
BLOCKED_ATTR_NAMES = {"open", "exec", "eval", "system", "popen"}

# 許可モジュールが内部で import している危険なモジュール。
# json.codecs.open(...) や typing.sys.modules のような経由を防ぐ。
BLOCKED_MODULE_ATTRS = {
    "os", "sys", "codecs", "io", "subprocess", "socket", "shutil", "pathlib",
    "importlib", "builtins", "ctypes", "urllib", "http", "tempfile", "glob",
    "pickle", "marshal", "shelve", "zipfile", "tarfile", "ftplib", "smtplib",
    "webbrowser", "multiprocessing", "threading", "asyncio", "signal",
    "platform", "site", "runpy", "pty", "fcntl", "posix", "nt", "gc", "inspect",
}

# アンダースコアで始まる属性のうち、参照を許可するもの。
# これ以外の _xxx / __xxx__ は内部実装へのアクセス（random._os、print.__self__ など）として deny。
ALLOWED_PRIVATE_ATTRS = {"__name__", "__qualname__", "__class__", "__doc__"}

# 名前自体が危険を示す属性名。別名経由（w = bpy.ops.wm; w.save_mainfile()）でも検出するため、
# チェーンのどの位置に現れても deny する。
DANGEROUS_ATTRS = {
    # .blend・プリファレンス
    "save_mainfile": ".blend の保存",
    "save_as_mainfile": ".blend の保存",
    "save_homefile": "スタートアップファイルの保存",
    "save_userpref": "プリファレンスの保存",
    "open_mainfile": ".blend の読み込み",
    "revert_mainfile": ".blend の再読み込み",
    "recover_last_session": ".blend の復元",
    "recover_auto_save": ".blend の復元",
    "read_homefile": "スタートアップファイルの読み込み（シーン破棄）",
    "read_factory_settings": "初期設定の読み込み（シーン破棄）",
    "read_userpref": "プリファレンスの読み込み",
    "lib_reload": "外部ライブラリの再読み込み",
    "lib_relocate": "外部ライブラリの差し替え",
    "quit_blender": "Blender の終了",
    # 外部ファイルの読み込み・書き出し
    "load": "外部ファイルの読み込み (bpy.data.*.load など)",
    "write": "ファイルの書き出し (bpy.data.libraries.write など)",
    "reload": "外部ファイルの再読み込み (Image.reload / Library.reload など)",
    "load_image": "外部画像の読み込み (bpy_extras.image_utils.load_image)",
    "path_reference_copy": "ファイルのコピー (bpy_extras.io_utils.path_reference_copy)",
    "save_render": "画像ファイルの書き出し",
    "unpack": "パック済みファイルのディスク書き出し",
    "unpack_all": "パック済みファイルのディスク書き出し",
    "unpack_item": "パック済みファイルのディスク書き出し",
    "screenshot": "スクリーンショットのファイル書き出し",
    "screenshot_area": "スクリーンショットのファイル書き出し",
    "import_as_mesh_planes": "外部画像の読み込み",
    "preset_add": "プリセットファイルの書き出し",
    "mixdown": "音声ファイルの書き出し",
    # スクリプト実行
    "run_script": "スクリプト実行",
    "python_file_run": "外部 Python ファイルの実行",
    "execfile": "外部 Python ファイルの実行 (bpy.utils.execfile)",
    "as_module": "テキストブロックのコード実行",
    # ファイルの追加・削除を伴うプリファレンス操作
    "addon_install": "アドオンのインストール（ファイル書き込み）",
    "addon_remove": "アドオンの削除（ファイル削除）",
    "theme_install": "テーマのインストール（ファイル書き込み）",
    "app_template_install": "アプリテンプレートのインストール（ファイル書き込み）",
    "studiolight_install": "スタジオライトのインストール（ファイル書き込み）",
    "studiolight_uninstall": "スタジオライトの削除（ファイル削除）",
    "keyconfig_import": "キーマップの読み込み",
    "keyconfig_export": "キーマップの書き出し",
    "copy_prev": "旧バージョン設定のコピー（ファイル書き込み）",
    # 外部アクセス
    "path_open": "外部ファイル・フォルダを開く",
    "url_open": "外部 URL を開く",
    "url_open_preset": "外部 URL を開く",
}

# 文字列として現れたら deny するもの（ノード型名など）
DANGEROUS_STRINGS = {
    "CompositorNodeOutputFile": "レンダリング時のファイル書き出しノード (File Output)",
}

# 属性チェーン全体（例: bpy.ops.wm.append）に適用する deny パターン。
# link / append / save など一般的な名前は、モジュール名とセットのときだけ検出する。
DENY_PATTERNS = [
    (r"\bwm\.(link|append)\b", "他の .blend からのリンク・アペンド (bpy.ops.wm.link/append)"),
    (r"\bwm\.\w*(import|export)", "外部ファイルの入出力 (bpy.ops.wm.*import*/*export*)"),
    (r"\bwm\.context_\w+", "文字列を Python として評価する操作 (bpy.ops.wm.context_*)"),
    (r"\b(import|export)_(scene|mesh|curve|anim|image)\b",
     "外部モデルの入出力 (bpy.ops.import_*/export_*)"),
    (r"\bops\.file\.\w+", "ファイル操作 (bpy.ops.file.*: pack/unpack など)"),
    (r"\bops\.extensions\.\w+", "エクステンションのダウンロード・インストール (bpy.ops.extensions.*)"),
    (r"\bops\.image\.(save\w*|open|replace|external_edit|pack)\b",
     "画像ファイルの読み書き (bpy.ops.image.*)"),
    (r"\.save$", "画像ファイルの書き出し (Image.save)"),
    (r"\bops\.text\.(save\w*|open)\b", "テキストのファイル入出力 (bpy.ops.text.*)"),
    (r"\bops\.script\.\w+", "スクリプト実行 (bpy.ops.script.*)"),
    (r"\bops\.(sound|clip|cachefile|font)\.open\w*\b", "外部ファイルの読み込み (bpy.ops.*.open)"),
    (r"\bsequencer\.\w+_strip_add\b", "外部メディアの読み込み (bpy.ops.sequencer.*_strip_add)"),
    (r"\bptcache\.(bake|free)\w*\b", "キャッシュのディスク書き出し・削除 (bpy.ops.ptcache.*)"),
    (r"\bops\.fluid\.(bake|free)\w*\b", "流体キャッシュのディスク書き出し・削除 (bpy.ops.fluid.*)"),
    (r"\bops\.object\.(bake\w*|ocean_bake|geometry_node_bake\w*|simulation_nodes_cache\w*)\b",
     "ベイク・キャッシュのディスク書き出し (bpy.ops.object.*bake*)"),
]

# 値として取り出す（別名に代入する・関数に渡す）と上記パターンをすり抜けられるもの。
# チェーンの末尾がこれで終わる参照は deny。
RISKY_AS_VALUE = [
    (re.compile(r"(^|\.)ops$"), "bpy.ops の別名参照"),
    (re.compile(r"(^|\.)(wm|file|script|ptcache|fluid|sequencer|extensions|cachefile|"
                r"import_\w+|export_\w+)$"),
     "オペレータモジュールの別名参照"),
    (re.compile(r"\bops\.(image|text|sound|clip|font|preferences|object)$"),
     "オペレータモジュールの別名参照"),
]

# 属性チェーン全体に適用する ask パターン（理由を添えて確認を求める）
ASK_PATTERNS = [
    (r"\bpreferences\b", "プリファレンス・アドオン設定の変更 (CLAUDE.md: 指示外の操作は要確認)"),
    (r"\bapp\.(handlers|timers|driver_namespace)\b",
     "ハンドラ・タイマー・ドライバ関数の登録（継続的にコードが実行される）"),
    (r"\.(expression|use_module)$", "文字列が Python として評価される設定（ドライバ式・テキストのモジュール登録）"),
    (r"\b(data\.\w+\.remove|object\.delete|outliner\.(delete|orphans_purge))\b",
     "オブジェクト・データの削除（破壊的変更）"),
]

# レンダリングでファイル出力を伴うキーワード引数
RENDER_WRITE_KEYWORDS = {"write_still", "animation"}


def dotted_name(node):
    """Attribute / Name のチェーンを 'a.b.c' 形式にする。途中に呼び出しや添字があれば
    そこを '_' に置き換える（例: images['x'].save -> '_.save'）。"""
    parts = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    parts.append(node.id if isinstance(node, ast.Name) else "_")
    return ".".join(reversed(parts))


class Checker:
    def __init__(self):
        self.denies = []
        self.asks = []

    def deny(self, msg, node):
        self.denies.append(f"{msg} [line {getattr(node, 'lineno', '?')}]")

    def ask(self, msg, node):
        self.asks.append(f"{msg} [line {getattr(node, 'lineno', '?')}]")

    def check_chain(self, name, node, as_value):
        """属性チェーン name を検査する。as_value は、チェーン末尾のオブジェクトを
        そのまま値として取り出しているか（別名代入・引数渡しなど）。"""
        segments = name.split(".")
        for seg in segments[1:]:
            if seg.startswith("_") and seg not in ALLOWED_PRIVATE_ATTRS:
                self.deny(f"内部属性へのアクセス ({seg}): {name}", node)
            if seg in BLOCKED_MODULE_ATTRS:
                self.deny(f"危険なモジュールへの間接アクセス ({seg}): {name}", node)
            if seg in BLOCKED_ATTR_NAMES:
                self.deny(f"危険な関数の属性参照 ({seg}): {name}", node)
        for seg in segments:
            if seg in DANGEROUS_ATTRS:
                self.deny(f"{DANGEROUS_ATTRS[seg]} ({seg}): {name}", node)
        for pat, msg in DENY_PATTERNS:
            if re.search(pat, name):
                self.deny(f"{msg}: {name}", node)
        if as_value:
            for pat, msg in RISKY_AS_VALUE:
                if pat.search(name):
                    self.deny(f"{msg}: {name}", node)
        for pat, msg in ASK_PATTERNS:
            if re.search(pat, name):
                self.ask(f"{msg}: {name}", node)

    def check_string(self, s, node):
        for d in BLOCKED_NAMES.keys() | {"__subclasses__", "__globals__", "__self__"}:
            if d.startswith("__") and d in s:
                self.deny(f"文字列中の危険な名前: '{d}'", node)
        if s in BLOCKED_NAMES or s in BLOCKED_MODULE_ATTRS:
            self.deny(f"文字列経由の危険な名前参照: '{s}'", node)
        if s in DANGEROUS_ATTRS:
            self.deny(f"文字列経由の参照 - {DANGEROUS_ATTRS[s]}: '{s}'", node)
        if s in DANGEROUS_STRINGS:
            self.deny(f"{DANGEROUS_STRINGS[s]}: '{s}'", node)

    def run(self, code):
        try:
            tree = ast.parse(code)
        except SyntaxError as e:
            self.deny(f"構文解析に失敗したため安全のためブロック ({e.msg})", e)
            return

        parents = {}
        for node in ast.walk(tree):
            for child in ast.iter_child_nodes(node):
                parents[child] = node

        for node in ast.walk(tree):
            parent = parents.get(node)
            is_call_func = isinstance(parent, ast.Call) and parent.func is node

            # import の許可リスト
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.split(".")[0] not in ALLOWED_MODULES:
                        self.deny(f"許可されていないモジュールの import: {alias.name}", node)
                    else:
                        self.check_chain(alias.name, node, as_value=True)

            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                if node.level or module.split(".")[0] not in ALLOWED_MODULES:
                    self.deny(f"許可されていないモジュールの import: {module}", node)
                else:
                    # from bpy import ops / from json import codecs などもチェーンとして検査
                    for alias in node.names:
                        self.check_chain(f"{module}.{alias.name}", node, as_value=True)

            # 禁止された組み込み名
            elif isinstance(node, ast.Name):
                if node.id in BLOCKED_NAMES:
                    self.deny(BLOCKED_NAMES[node.id], node)
                elif node.id in INDIRECT_BLOCKED_NAMES and not is_call_func:
                    self.deny(f"{node.id} の間接利用（別名代入・関数への受け渡し）", node)

            # 属性チェーン（チェーンの一番外側だけを検査し、重複を避ける）
            elif isinstance(node, ast.Attribute) and not isinstance(parent, ast.Attribute):
                self.check_chain(dotted_name(node), node, as_value=not is_call_func)

            # 文字列定数
            elif isinstance(node, ast.Constant) and isinstance(node.value, str):
                self.check_string(node.value, node)

            if isinstance(node, ast.Call):
                fname = dotted_name(node.func)

                # getattr(obj, 'name') は obj.name として検査。名前が定数でなければ deny。
                if fname in ("getattr", "setattr", "delattr", "hasattr") and len(node.args) >= 2:
                    attr = node.args[1]
                    if isinstance(attr, ast.Constant) and isinstance(attr.value, str):
                        self.check_chain(f"{dotted_name(node.args[0])}.{attr.value}",
                                         node, as_value=True)
                    else:
                        self.deny(f"属性名を動的に指定した {fname}", node)

                # レンダリング結果のファイル出力。r = bpy.ops.render; r.render(...) の別名も対象。
                for kw in node.keywords:
                    if kw.arg == "write_still" or (
                            re.search(r"(^|\.)(render|opengl)$", fname)
                            and (kw.arg in RENDER_WRITE_KEYWORDS or kw.arg is None)):
                        self.deny(f"レンダリング結果のファイル出力: "
                                  f"{fname}({kw.arg or '**kwargs'}=...)", node)


def emit(decision, reasons):
    header = ("execute_blender_code をブロックしました (CLAUDE.md の禁止事項に該当する可能性):"
              if decision == "deny" else
              "execute_blender_code に注意が必要な操作が含まれています:")
    message = header + "\n- " + "\n- ".join(reasons)
    output = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": decision,
            "permissionDecisionReason": message,
        }
    }
    # settings.json の ask ルールと重なると確認プロンプトにはルール側の文言が表示され、
    # permissionDecisionReason が見えないため、ユーザー向けに systemMessage でも表示する。
    if decision == "ask":
        output["systemMessage"] = message
    print(json.dumps(output, ensure_ascii=False))


def main():
    payload = json.load(sys.stdin)
    code = (payload.get("tool_input") or {}).get("code")
    if not isinstance(code, str):
        emit("deny", ["tool_input.code が文字列ではないため検査できません"])
        return

    checker = Checker()
    checker.run(code)
    denies = list(dict.fromkeys(checker.denies))
    asks = list(dict.fromkeys(checker.asks))
    if denies:
        emit("deny", denies)
    elif asks:
        emit("ask", asks)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:  # MemoryError / RecursionError / JSONDecodeError なども含む
        emit("deny", [f"検査中にエラーが発生したため安全のためブロック ({type(e).__name__})"])
