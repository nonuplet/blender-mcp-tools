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
| `tests/` | hook のテスト |
| `notes/` | 設定の理由などのメモ |
| `tmp/` | 作業用の一時ファイル（git 管理外） |

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
