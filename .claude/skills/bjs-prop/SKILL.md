---
name: bjs-prop
description: Babylon.js 向けの小物・プロップ（家具、アイテム、UI 用の 3D アイコンなど、単体の静的なローポリモデル）を Blender MCP で生成する手順。プリミティブ／bmesh での形状生成、ポリゴン数の目安、原点・トランスフォーム・スムーズシェーディングの仕上げを扱う（UV 展開は bjs-uv）。「木箱を作って」「Babylon 用に椅子のモデルを」など、単体のモデルを作るときに使う。
---

# 小物・プロップの生成

最初に `bjs-conventions` の SKILL.md を読む。シーンの準備がまだなら `bjs-scene-setup` を先に行う。

## 1. 仕様を決める（確認ポイント）

作り始める前に、次の内容をユーザーに確認する。指示にないものは推測で決めず、案を出して選んでもらう。

- 何を作るか、実寸（幅 × 奥行き × 高さ、m）
- テイスト（ローポリ／フラットシェード、角を丸めた柔らかい形、リアル寄り など）
- ポリゴン数の目安（下の表を参考に提案する）
- オブジェクト名（`PascalCase_Variant`、例: `Crate_A`）
- 正面の向き（既定は Blender の -Y 側）

ポリゴン数（三角形数）の目安。Web 向けの一般的な値で、プロジェクトに合わせて調整する。

| 用途 | 三角形数 |
|---|---|
| 背景に多数置く小物 | 〜500 |
| 一般的なプロップ | 500〜3,000 |
| 画面の主役になるプロップ | 3,000〜10,000 |

## 2. 形状を生成する

- まず `WIP` コレクションに作る（アクティブコレクションが `EXPORT` の場合は、生成コード内で `WIP` にリンクする）。
- 生成方法の使い分け:
  - 箱・円柱などの組み合わせ: `bpy.ops.mesh.primitive_*_add`
  - 細かい形状の制御: `bmesh`（`bmesh.ops.create_cube` / `extrude_face_region` / `bevel` など）
  - 角の丸み: Bevel モディファイア（`segments` は 1〜3。ポリゴン数が増えるので注意）
- パーツが複数ある場合は、次のどちらかにする。
  - 1 つのメッシュに結合する（描画が軽い。Babylon で個別に動かさないパーツ向け）
  - Empty（`<Name>_root`）の子にする（Babylon で個別に動かす・表示を切り替えるパーツ向け）
- 原点は最後に整えるので、生成中は気にしなくてよい。
- 生成コードは `tmp/` に書き、形に依存しない処理は `bjs-conventions` の `snippets.py` の関数をコピーして使う。
- `bmesh.ops.extrude_face_region` は、押し出し元の面を残す。押し出した面を移動したら、元の面を `bmesh.ops.delete(bm, geom=faces, context="FACES")` で消す（`FACES_ONLY` だと、その面にしか使われていない辺が孤立して残る）。

生成したら、まず `scripts/mesh_check.py` でメッシュの健全性を確認する。閉じた形なら `closed` が `True`、`counts` の `boundary_edges` / `nonmanifold_edges` / `loose_edges` / `degenerate_faces` が 0 になるはず。問題があれば `samples` の位置を手がかりに直す。モディファイア（Bevel など）を付けた場合は、`USE_EVALUATED = True` でも確認する。

続けて `bjs-conventions` の `scripts/set_view.py`（`COLLECTION="WIP"`、`ISO` と `FRONT`）でスクリーンショットを撮り、ユーザーに見せる。

**確認ポイント**: 形・寸法・ポリゴン数を報告し、了承を得るまで次へ進まない。修正を指示されたら、指示された箇所だけを直す。

## 3. 仕上げる

`scripts/finalize_mesh.py` で、書き出しに向けて次の処理を行う。

| パラメータ | 内容 | 既定値 |
|---|---|---|
| `OBJECTS` | 対象オブジェクト名のリスト | 必須 |
| `APPLY_ROTATION_SCALE` | 回転・スケールを適用（位置は残す） | `True` |
| `ORIGIN` | 原点の位置。`"BOTTOM_CENTER"`（底面中心。床に置く物）／`"BOUNDS_CENTER"`（中心。浮かせる・回す物）／`None` | `"BOTTOM_CENTER"` |
| `AUTO_SMOOTH_ANGLE` | Smooth by Angle の角度（度）。`0` でフラットシェード、`None` で変更しない | `30` |

UV 展開はここでは行わない。テクスチャを使う場合は、マテリアルの前に `bjs-uv` で行う。

- メッシュを他のオブジェクトと共有している（リンク複製）オブジェクトは、回転・スケールの適用と原点の変更をスキップする（ほかのオブジェクトの形まで変わるため）。スキップしたものは `skipped` に出る。
- Smooth by Angle はモディファイアとして追加される。書き出し時に **Apply Modifiers** を ON にしないと反映されない（`bjs-export-check` のチェックリストに含まれている）。

実行後にスクリーンショットを撮り、結果（`objects` の三角形数・寸法、`skipped`）を報告する。

## 4. EXPORT へ移す（確認ポイント）

ユーザーの了承を得てから、`scripts/move_to_collection.py`（`FROM = "WIP"`、`TO = "EXPORT"`）で、完成したオブジェクトを移す。移動先にリンクしてから移動元からアンリンクする。`INCLUDE_CHILDREN = True`（既定）なら子のオブジェクトも一緒に移る。

## 次の工程

- テクスチャを使う → `bjs-uv` の後に `bjs-material`
- 単色・頂点カラーだけ → `bjs-material`
- 動かす場合 → `bjs-animation`
- 書き出す前 → `bjs-export-check`
