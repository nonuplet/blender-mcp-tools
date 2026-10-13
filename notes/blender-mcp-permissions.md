# Blender MCP ツールの権限設定（allow / ask / deny）

対象: Blender Lab版 Blender MCP（`.mcp.json` の `blender` サーバ）
設定ファイル: `.claude/settings.json` の `permissions`
作成日: 2026-10-13

## 分類方針

CLAUDE.md のルールに沿って分類した。

- **allow**: 読み取り専用で、シーンにもファイルシステムにも副作用がないもの
- **ask**: シーンや UI の状態を変更しうるもの、または任意コードを実行するもの
- **deny**: CLAUDE.md の禁止事項に該当するもの
  - ファイルシステムへの書き込み・削除
  - 外部ネットワークアクセス
  - 他の Blender プロジェクトファイル・3Dモデルの読み込み

Claude Code の permission ルールはツール単位でしか指定できず、引数（例: `allow_edits`）単位では絞れない。
そのため、引数次第で副作用が出るツールは ask に置いている。
また MCP ツールの部分一致ワイルドカード（`*_for_cli` など）は挙動が確実ではないため、ツール名はすべて明示的に列挙している。

## allow（13件）

| ツール | 内容 | 許可理由 |
|---|---|---|
| `search_api_docs` | 同梱の Python API ドキュメントを全文検索 | ローカルに同梱された RST を読むだけ |
| `search_manual_docs` | 同梱のユーザーマニュアルを全文検索 | 同上 |
| `get_python_api_docs` | 識別子を指定して API ドキュメントを取得 | 同上 |
| `get_objects_summary` | コレクション階層とオブジェクトの一覧 | 現在のシーンを読み取るだけ |
| `get_object_detail_summary` | オブジェクト1件の詳細（transform, modifier, material など） | 同上 |
| `get_blendfile_summary_datablocks` | 開いている .blend のデータブロック数、ワークスペース、レンダーエンジン | 同上 |
| `get_blendfile_summary_missing_files` | 欠落している外部ファイル参照の一覧 | 同上（参照の有無を調べるだけで、読み込みはしない） |
| `get_blendfile_summary_of_linked_libraries` | リンク中のライブラリのツリー | 同上 |
| `get_blendfile_summary_path_info` | 現在のファイルのパス、保存状態、バックアップ | 同上 |
| `get_blendfile_summary_usage_guess` | ファイルの用途を推定 | 同上 |
| `get_screenshot_of_window_as_image` | Blender ウィンドウ全体のスクリーンショット | 読み取りのみ。生成結果の検証に必要 |
| `get_screenshot_of_area_as_image` | エリア単位のスクリーンショット | 同上 |
| `get_screenshot_of_window_as_json` | レイアウト、アクティブオブジェクト、選択状態を JSON で取得 | 同上 |

## ask（5件）

| ツール | 内容 | 確認が必要な理由 |
|---|---|---|
| `execute_blender_code` | 接続中の Blender で任意の Python コードを実行 | モデル生成の主な手段なので禁止はできない。ただしファイル書き込みやネットワークアクセスも技術的には可能なため、毎回内容を確認する。加えて PreToolUse hook で事前検査する（[blender-code-hook.md](blender-code-hook.md)） |
| `jump_to_tab_by_name` | ワークスペースのタブを切り替える | データは変更しないが UI の状態が変わる |
| `jump_to_tab_by_space_type` | 指定したエディタ種別のワークスペースへ切り替える | `allow_edits=True` だとワークスペースを新規作成する |
| `jump_to_view3d_object_by_name` | 3D ビューポートを指定オブジェクトにフォーカスする | `allow_edits=True` だと非表示オブジェクトの表示化やコレクションの有効化を行う |
| `jump_to_view3d_object_data_by_name` | データブロック名でオブジェクトにフォーカスする | 同上 |

## deny（8件）

| ツール | 内容 | 禁止理由 |
|---|---|---|
| `render_thumbnail_to_path` | 任意のパスにサムネイル画像をレンダリング出力する | ファイルシステムへの書き込みに該当する。検証はスクリーンショット系ツールで代わりに行える |
| `render_viewport_to_path` | 任意のパスにレンダリング画像を出力する | 同上 |
| `execute_blender_code_for_cli` | 任意の .blend を background Blender で開いて任意のコードを実行する | 他のプロジェクトファイルの読み込みに該当する。さらに任意コードの実行も伴う |
| `get_blendfile_summary_datablocks_for_cli` | 任意の .blend を開いてデータブロックの概要を取得する | 他のプロジェクトファイルの読み込みに該当する |
| `get_blendfile_summary_missing_files_for_cli` | 任意の .blend を開いて欠落ファイルを調べる | 同上 |
| `get_blendfile_summary_of_linked_libraries_for_cli` | 任意の .blend を開いてリンク中のライブラリを調べる | 同上 |
| `get_blendfile_summary_path_info_for_cli` | 任意の .blend を開いてパス情報を取得する | 同上 |
| `get_blendfile_summary_usage_guess_for_cli` | 任意の .blend を開いて用途を推定する | 同上 |

## その他の変更点

- 以前の設定にあった `mcp__blender__get_scene_info` は、このサーバに存在しないツール名（別実装の名残と思われる）だったため削除した。
- MCP 以外のルール（`Edit(.claude/**)` / `Edit(CLAUDE.md)` は ask、`Edit(.mcp.json)` は deny）はそのまま残している。
- Bash での `python` / `python3` の実行を ask に追加した（2026-10-13）。スクリプトの実行は基本的に MCP 経由で行うため。
  - deny にしなかったのは、hook（`.claude/hooks/check_blender_code.py`）の修正後に `python3` でテストを実行できるようにするため。deny は allow より優先されるので、テスト用の例外を作れない。
  - hook と Blender MCP サーバーは Claude Code 本体が起動するので、このルールの影響を受けない。
  - ルールはコマンドの先頭一致なので、`/usr/sbin/python3 ...` や `uv run python ...` などは対象外になりうる。完全な遮断ではない。
- `/tmp` 以下へのファイル作成・編集（`Edit(//tmp/**)`）を deny に追加した（2026-10-13）。作業用のスクリプトは、ユーザーが内容を確認できるようプロジェクト内の `tmp/`（`.gitignore` 済み）に置くため。ルール自体は CLAUDE.md に記載している。
  - このルールが止めるのは Write / Edit ツールによる書き込みだけ。Bash のリダイレクト（`cat > /tmp/x` など）は対象外なので、CLAUDE.md のルールで運用する。

## PreToolUse hook による事前検査

`execute_blender_code` は ask に加えて、PreToolUse hook（`.claude/hooks/check_blender_code.py`）でコードを事前に静的検査している。
検出対象・判定の流れ・制限事項は [blender-code-hook.md](blender-code-hook.md) を参照。
