# blender-mcp-tools

Claude Code から Blender MCP（Blender Lab 版）を経由して Blender を操作し、3D モデルの生成と検証を行うためのリポジトリです。

## 必要なもの

- Blender 5.1～ (Blender Lab版のMCPアドオンが、5.1以降でないと動かないため)
- python3 (hookで使用、ない場合 `execute_blender_code` がブロックされるため注意)
- uv (Blender MCPの起動に必要)
- Blender MCP アドオン (Blender Lab の [Extensions リポジトリ](https://docs.blender.org/manual/en/latest/editors/preferences/extensions.html#repositories) `https://lab.blender.org/` から入れる)

MCP サーバー本体は `.mcp.json` の設定により uvx で git から自動取得されるため、手動で clone する必要はありません。

## バージョン

MCP サーバーは `.mcp.json` でタグ（現在 `v1.0.3`）を固定しています。
Blender 側アドオンのバージョンと揃えてください。更新時は `.mcp.json` の `@v1.0.3` を書き換えます。

## 注意点

`execute_blender_code` については、 PreToolUse である程度チェックが走る仕様になっています。
詳細は [blender-code-hook.md](notes/blender-code-hook.md) を確認してください。

ただしここで行われるブロックは完全なものではなく、 `execute_blender_code` の実行は ask にしています。

そのため、**実行前に、必ずスクリプトをチェックするようにしてください**。

## 構成

| パス | 内容 |
|---|---|
| `CLAUDE.md` | Claude Code 向けのルール |
| `.mcp.json` | Blender MCP サーバーの起動設定（uvx で git から取得、タグ固定） |
| `.env.example` | 接続先（HOST / PORT）のテンプレート。`.env` にコピーして使う（`.env` は git 管理外） |
| `.claude/settings.json` | ツールの権限設定と hook の登録 |
| `.claude/hooks/check_blender_code.py` | `execute_blender_code` のコードを事前検査する hook |
| `.claude/skills/bjs-*/` | Babylon.js 向けアセット制作の skill（下記） |
| `tests/` | hook のテスト（skill 同梱スクリプトが hook を通ることも確認） |
| `notes/` | 設定の理由などのメモ |
| `tmp/` | 作業用の一時ファイル（git 管理外） |

## Babylon.js 向けの skill

Web（Babylon.js）で使う 3D アセットを作るための skill です。`/bjs-scene-setup` のように呼び出すか、「Babylon 用に木箱を作って」のように依頼すると使われます。

| skill | 内容 |
|---|---|
| `bjs-conventions` | 共通規約（単位・座標系・コレクション・命名・確認用スクリーンショット）。ほかの skill から参照 |
| `bjs-scene-setup` | シーンの調査と `EXPORT` / `WIP` / `REF` コレクションの準備 |
| `bjs-prop` | 小物・プロップの生成と仕上げ（原点・トランスフォーム・スムーズ） |
| `bjs-environment` | 背景・環境の組み立て（リンク複製、当たり判定用メッシュ、タグ付け） |
| `bjs-uv` | UV 展開（テクスチャの種類に応じた方針決め、モディファイアの適用確認、実寸投影、歪みの検査） |
| `bjs-material` | glTF に書き出せるマテリアル（PBR、頂点カラー、コード生成テクスチャ、ユーザーが読み込んだ画像、透明） |
| `bjs-animation` | アニメーション（Action = Babylon の AnimationGroup、NLA への退避） |
| `bjs-export-check` | 書き出し前の検査と、手動書き出しの設定チェックリスト |

- **GLB の書き出しは手動です。** hook がファイル書き込みを禁止しているため、Claude は書き出し前の検査と設定の案内までを行い、書き出しは Blender の GUI で行います。
- 各 skill の `scripts/*.py` は `execute_blender_code` に渡すコードです。Claude は冒頭のパラメータ部分だけを書き換えて実行します。
- Claude が作れるテクスチャは、数値・頂点カラー・コードで生成した画像だけです（画像の読み込みとベイクは hook で禁止）。それ以上の質感が必要な場合は、ユーザーが画像を Blender に読み込み、Claude がマテリアルにつなぎます。
- 単位系（Metric / Imperial）は、hook が属性名 `system` を一律で禁止しているためスクリプトでは変更できません。必要な場合は GUI で変更します。

## 安全対策

- [notes/blender-mcp-permissions.md](notes/blender-mcp-permissions.md): MCP ツールの権限設定
- [notes/blender-code-hook.md](notes/blender-code-hook.md): コードの事前検査 hook

## テスト

```sh
python3 -I tests/test_check_blender_code.py
```

## 免責事項

このツール一式を使用したことによって、何かが発生しても、一切責任を負いません。
あくまで自己責任で使用してください。
