# execute_blender_code の事前検査 hook（PreToolUse）

作成日: 2026-10-13
関連: [Blender MCP ツールの権限設定](blender-mcp-permissions.md)

`execute_blender_code` は ask にしていても、確認時にコードの中身を見落とすおそれがある。
多層防御として、Blender に送る前にコードを静的に検査する PreToolUse hook を設定している。

> **hook は見落とし防止の補助であり、安全性の保証ではない。** 静的検査では Python の動的な振る舞いを追い切れず、未知の抜け道は残りうる（[制限事項](#制限事項)）。最終的な防御線は `execute_blender_code` の確認プロンプトなので、承認時は必ずコードを読むこと。

- スクリプト: `.claude/hooks/check_blender_code.py`
- テスト: `tests/test_check_blender_code.py`
- 設定: `.claude/settings.json` の `hooks.PreToolUse`（matcher: `mcp__blender__execute_blender_code`）
- 実行環境: WSL 側の `python3`（Blender 組み込みの Python ではない）。コードは実行せず、`ast` で構文解析するだけ。

## 判定の流れ

| 判定 | 動作 |
|---|---|
| deny | ツール呼び出しをブロックし、理由を Claude に返す（ユーザーへの確認プロンプトも出ない） |
| ask | 理由を添えて確認プロンプトを出す |
| 該当なし | 何も出力せず、通常の permission ルール（`execute_blender_code` は ask）に従う |

次の場合はすべてブロックする（fail-closed）。
- コードの構文解析に失敗した場合は deny を返す。
- 検査中に例外（`MemoryError`, `RecursionError`, 不正な入力 JSON など）が起きた場合も、スクリプト内で捕捉して deny を返す。
- hook 自体が起動できない・タイムアウトした場合は、`settings.json` の `onFailure: "block"` によってブロックする。

## deny になるもの

| 分類 | 検出対象の例 |
|---|---|
| 許可リスト外の import | `os`, `sys`, `pathlib`, `shutil`, `subprocess`, `socket`, `urllib`, `requests`, `ctypes`, `importlib` など。許可しているのは `bpy`, `bmesh`, `mathutils`, `bpy_extras`, `gpu`, `math`, `random`, `colorsys`, `itertools`, `functools`, `collections`, `typing`, `dataclasses`, `enum`, `statistics`, `copy`, `json`, `re`, `time`, `string` のみ |
| 危険な組み込み関数 | `open`, `exec`, `eval`, `compile`, `__import__`, `breakpoint`, `input`, `__builtins__` |
| 内部実装へのアクセス | `_` で始まる属性すべて（`random._os`, `print.__self__`, `__subclasses__`, `__globals__` など）。`__name__`, `__qualname__`, `__class__`, `__doc__` のみ許可 |
| 許可モジュール経由の危険なモジュール | `json.codecs`, `typing.sys` など、`os`, `sys`, `codecs`, `io`, `subprocess`, `socket`, `shutil` などの名前を属性として参照するもの。属性としての `open`, `exec`, `eval`, `system`, `popen` も同様 |
| .blend の読み書き | `wm.save_mainfile`, `wm.save_as_mainfile`, `wm.open_mainfile`, `wm.revert_mainfile`, `wm.read_homefile`, `wm.read_factory_settings`, `wm.save_userpref` など |
| 他の .blend の取り込み | `wm.link`, `wm.append`, `bpy.data.libraries.load`, `wm.lib_reload`, `wm.lib_relocate` |
| 外部モデルの入出力 | `bpy.ops.import_scene.*`, `bpy.ops.export_scene.*`, `import_mesh` / `export_mesh`, `wm.obj_import` や `wm.grease_pencil_export_svg` など名前に import / export を含む `wm.*` |
| 外部ファイルの読み込み | 属性名 `load` / `reload` すべて（`bpy.data.images.load`, `texts.load`, `libraries.load`, `Image.reload`, `Library.reload` など。別名経由も含む）、`bpy_extras.image_utils.load_image`、`ops.image.open`、`ops.sound/clip/cachefile/font.open`、`image.import_as_mesh_planes`、`sequencer.*_strip_add` |
| ファイル書き出し | 属性名 `write` / `save` / `save_render` / `unpack` すべて、`ops.image.save*`、`ops.file.*`、`screen.screenshot`、`*.preset_add`、`io_utils.path_reference_copy`、`sound.mixdown` |
| レンダリング・ベイクの書き出し | キーワード `write_still` を持つ呼び出しすべて、`*.render(animation=True)`（`r = bpy.ops.render` の別名経由も含む）、コンポジターの File Output ノード（`CompositorNodeOutputFile`）、`ptcache.*`、`fluid.bake*` / `fluid.free*`、`object.bake*` / `ocean_bake` / `geometry_node_bake*` / `simulation_nodes_cache*` |
| スクリプト実行 | `ops.text.run_script`, `ops.script.*`, `Text.as_module`, `bpy.utils.execfile`、文字列を Python として評価する `wm.context_*`（`context_set_value` など） |
| ファイルの追加・削除を伴うプリファレンス操作 | `preferences.addon_install` / `addon_remove` / `theme_install` / `app_template_install` / `studiolight_install` / `studiolight_uninstall` / `keyconfig_import` / `keyconfig_export` / `copy_prev` |
| ネットワーク・外部アクセス | `ops.extensions.*`（エクステンションのダウンロード・インストール）、`wm.path_open`, `wm.url_open`, `wm.quit_blender` |
| すり抜け対策 | 文字列経由の参照（`getattr(bpy.ops.wm, 'save_mainfile')`、`__import__` などを含む文字列）、属性名を動的に指定した `getattr`、`getattr` / `globals` / `vars` などの間接利用（`functools.reduce(getattr, ...)`）、`bpy.ops` やオペレータモジュールの別名参照（`o = bpy.ops`、`w = bpy.ops.wm`、`from bpy import ops`、`from bpy.ops import wm`） |

## ask になるもの（理由付きで確認）

| 分類 | 検出対象の例 |
|---|---|
| プリファレンス・アドオン設定 | `preferences`（`bpy.ops.preferences.addon_enable` / `addon_disable`、`bpy.context.preferences` の読み書きなど。CLAUDE.md: 指示外の操作は要確認）。ファイルの追加・削除を伴う操作は deny。`addon_utils` は import 許可リストにないため deny になる |
| 継続的なコード実行 | `bpy.app.handlers`, `bpy.app.timers`, `bpy.app.driver_namespace` |
| 文字列が Python として評価される設定 | ドライバの `expression`、テキストブロックの `use_module` |
| 破壊的な変更 | `bpy.data.*.remove`, `ops.object.delete`, `ops.outliner.delete`, `ops.outliner.orphans_purge` |

## 検証結果（2026-10-13）

79 ケースを hook に直接入力して確認し、すべて期待どおりに判定された。

テストは `tests/test_check_blender_code.py` にある。hook を修正したら、プロジェクトルートで次のコマンドを実行して回帰がないか確認する（Blender には接続しない。失敗があれば終了コード 1）。

```sh
python3 -I tests/test_check_blender_code.py
```

- 通過: プリミティブ追加、bmesh でのメッシュ生成、マテリアル作成、モディファイア追加、書き出しなしの `render.render()`、`collection.objects.link` / `list.append`、定数での `getattr`、`object.mode_set`、`imgs = bpy.data.images` での反復、`r = scene.render` での設定変更、`re.compile`、`__class__.__name__` などの通常操作
- deny: 上の表の代表例、別名・`getattr`・`from bpy.ops import wm` 経由のすり抜け、`/code-review` で指摘された抜け道（下記）、`MemoryError` を起こす入力、不正な入力 JSON
- ask: アドオン有効化、プリファレンスの読み取り、オブジェクト削除、ハンドラ登録、ドライバ式の設定

`/code-review high`（2026-10-13）で指摘された次の抜け道は塞いだ。

- 許可モジュール経由: `random._os.system(...)`, `json.codecs.open(...)`, `print.__self__.open(...)`
- 別名・間接参照: `o = bpy.ops; o.wm.append(...)`, `functools.reduce(getattr, [...], bpy)`, `r = bpy.ops.render; r.render(write_still=True)`
- data コレクションの別名: `libs = bpy.data.libraries; libs.load(...)`
- 文字列内コードの評価: `bpy.ops.wm.context_set_value(value='__import__("os")...')`
- 検出漏れ: `bpy.ops.extensions.*`, `bpy.data.texts.load`, `Image.unpack`, `bpy.utils.execfile`, `screen.screenshot`, `wm.grease_pencil_export_svg`, File Output ノード, `preferences.addon_remove` / `addon_install`
- 例外時に deny を返さずに終了していた問題、`addon_utils` の ask パターンが使われず記述と食い違っていた問題

実際の `execute_blender_code` 呼び出しでも確認した（いずれも無害なコードで実施）。

| ケース | 送ったコード | 結果 |
|---|---|---|
| deny | `import os` | hook がブロックし、Blender には届かなかった |
| 該当なし | `len(bpy.data.objects)` を返すだけ | 通常の確認を経て実行された |
| ask | `bpy.context.preferences.view.ui_scale` を読むだけ | 確認を経て実行された。hook の理由は確認プロンプトには出ず、実行後に表示された（制限事項を参照） |

## 制限事項

- **静的検査なので、すべての抜け道は塞げない。** 名前とパターンの照合では、別名の連鎖、文字列の組み立て、Blender 内部で文字列を評価する機能などを完全には追跡できない。レビューで見つかった代表的な抜け道は塞いだが、未知の抜け道は残っている前提で扱う。最終的な防御線は `execute_blender_code` の確認プロンプトであり、hook は見落とし防止の補助と位置づける。
  - 根本的に塞ぐには「bpy の API のうち使ってよいものだけを許可する」方式が必要になるが、正当なコードの誤検出が大幅に増えるため採用していない。
- **ask の理由は確認プロンプトには表示されない。** `settings.json` の ask ルールと hook の ask が重なると、プロンプトにはルール側の定型文（「Permission rule mcp__blender__execute_blender_code requires confirmation」）だけが出る。
  - 事後に確認できるよう、ask 判定では `systemMessage` でも理由を出力している。これはツール実行後に「PreToolUse:mcp__blender__execute_blender_code says: ...」として表示される。
  - ask ルールを外して hook だけで確認する方法もあるが、hook が無効化されたときに確認なしで実行されうるため見送った（2026-10-13 ユーザー判断）。
  - deny 判定はこの影響を受けない。
- 一般的すぎる名前（`link`, `append` など）は、モジュール名とセットのとき（`wm.append` など）だけ検出する。そのため `w = <wm を別経路で取得>; w.append(...)` のような経路は検出できない可能性がある。
- 逆に `load`, `write`, `save`, `reload`, `unpack`, `open` は、どのオブジェクトの属性でも deny にしている。bpy 以外で同名のメソッドを正当に使うコードも止まる（安全側に倒している）。
- 文字列定数が危険な名前（`'save_mainfile'`, `'os'` など）と完全に一致する場合や、`__import__` などを含む場合は、正当な用途でも deny になる。コメントは検査対象外。
- コンポジターの File Output ノードは、作成時（型名の文字列）だけを検出する。シーンに既に File Output ノードがある状態で `render.render()` を実行すると、ファイルが書き出される。
- WSL 側の Python が Blender 組み込みの Python より古い場合、新しい構文を解析できずに deny になることがある（2026-10-13 時点では WSL 側が 3.14.7 なので問題なし）。
- 許可リストにないモジュールが正当に必要になった場合は、スクリプト内の `ALLOWED_MODULES` に追加する。
