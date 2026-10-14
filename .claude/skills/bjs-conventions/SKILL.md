---
name: bjs-conventions
description: Babylon.js 向け 3D アセットを Blender MCP で作るときの共通規約（単位・座標系・コレクション構成・命名・確認用スクリーンショットの撮り方・スクリプトの使い方）。bjs-scene-setup / bjs-prop / bjs-environment / bjs-uv / bjs-material / bjs-animation / bjs-export-check の各 skill から最初に参照する。Babylon.js 用のモデル作成を始めるとき、規約を確認したいときに使う。
---

# Babylon.js 向けアセットの共通規約

ほかの `bjs-*` skill はすべてこの規約を前提にしている。

## 作業の流れ

1. `bjs-scene-setup`: シーンの調査とコレクションの準備
2. `bjs-prop`（小物）または `bjs-environment`（背景・環境）: 形状の生成
3. `bjs-uv`: UV 展開（テクスチャを使う場合だけ）
4. `bjs-material`: glTF に書き出せるマテリアルの設定
5. `bjs-animation`: アニメーションの設定（必要な場合だけ）
6. `bjs-export-check`: 書き出し前の検査と、手動書き出しの設定チェックリスト
7. **ユーザーが** Blender の GUI で GLB を書き出す（Claude は書き出さない）

## 守ること（CLAUDE.md・hook より）

- **生成・変更のたびにスクリーンショットを撮ってユーザーに確認し、そこで止まる。** 返事を待たずに次の工程へ進まない。自己判断でデザインを手直ししない。
- GLB / glTF の書き出し、`.blend` の保存、画像の読み込み、ベイクは hook で禁止されている。これらが必要になったら、ユーザーへの手作業の依頼として伝える。
- Claude が作れるテクスチャは、数値・頂点カラー・コードで生成した画像（`bpy.data.images.new` + `pixels`）だけ。それ以上の質感が必要な場合は、無理に生成せず、ユーザーに画像を用意して Blender に読み込んでもらう。
- オブジェクトの削除は hook で ask になる。消す前に、対象をユーザーに示して確認する。

## 同梱スクリプトの使い方

各 skill の `scripts/*.py` は `execute_blender_code` に渡すためのコード。

1. Read でスクリプトを読む
2. 冒頭の `# --- パラメータ ---` から `# --- ここまで ---` の間だけを書き換える（それ以外は変えない）
3. 書き換えたパラメータの値をユーザーに示してから、全文を `execute_blender_code` に渡す
4. 戻り値（`result`）を要約して報告する

スクリプトは hook の検査を通る書き方にしてある。パラメータ以外を変更すると、hook に止められることがある（`tests/test_check_blender_code.py` で同梱スクリプトが通ることを確認している）。

## 生成コードを書くとき（スニペット集）

形状の生成など、同梱スクリプトにない処理は、`tmp/` にスクリプトを書いてから `execute_blender_code` で実行する（CLAUDE.md）。

- 形に依存しない処理は、`snippets.py` の関数を**そのままコピーして**使う（`execute_blender_code` はファイルを import できないため）。`tmp/` のスクリプトは単体で完結させる。

| 関数 | 用途 |
|---|---|
| `ensure_object_mode()` | オブジェクトモードに戻す。メッシュデータを直接書き換える前に呼ぶ |
| `select_only(objs)` | 指定したオブジェクトだけを選択・アクティブにする（オペレーターの前に呼ぶ） |
| `evaluated_triangles(ob)` | モディファイア適用後の三角形数 |
| `world_bounds(objs)` | ワールド座標のバウンディングボックス |
| `hex_to_linear(color)` | `#RRGGBB`（sRGB）をリニアの色にする |
| `topology_counts(bm)` | bmesh の健全性の件数（孤立した辺、開いた縁、非多様体、孤立した頂点、面積 0 の面） |

- 生成・修正のあとは、`bjs-prop` の `scripts/mesh_check.py` でメッシュの健全性を確認する。
- 同梱スクリプトにしたほうがよい処理（形に依存せず、何度も使うもの）に気付いたら、ユーザーに提案する。

## 単位とスケール

- 1 Blender unit = 1 m = 1 Babylon.js unit。シーンの単位はメートル法・`scale_length = 1.0` にする。
- 実寸で作る（例: ドア 2.0 m、机の高さ 0.72 m、手のひらに載る小物 0.05〜0.15 m）。
- 書き出す前にオブジェクトの回転とスケールを適用する（`bjs-prop` の `finalize_mesh.py`）。負のスケールは法線が反転するので使わない。

## 座標系

- Blender は Z-up の右手系。glTF exporter の **+Y Up**（既定で ON）で、glTF の Y-up に変換される。
- Blender の **-Y 方向（フロントビューで見えている面）** が、glTF の +Z（glTF の慣習でいう前方）になる。モデルの正面は Blender の -Y 側に向けて作る。
- Babylon.js は左手系。glTF ローダーは `__root__` ノードを作り、その回転・スケールで右手系から左手系へ変換する。
  - `__root__` の transform を変更・リセットしないこと（向きや左右が反転する）。
  - Babylon 側で `scene.useRightHandedSystem = true` にすると、この変換は行われない。
- Babylon でカメラをどこに置くと正面が見えるかは、アプリのカメラ設定によって変わる。Babylon Sandbox で一度確かめておく。

## コレクション構成

| コレクション | 用途 | 書き出し |
|---|---|---|
| `EXPORT` | 書き出すオブジェクトだけを入れる | 対象（Include → Active Collection） |
| `WIP` | 作業中・試作 | 対象外 |
| `REF` | 寸法確認用の人型ボックスなどの参照物 | 対象外（`hide_render`） |

新しく作るオブジェクトは、原則として `EXPORT` に入れる。試作は `WIP` に入れ、ユーザーの了承を得てから `EXPORT` へ移す。

## 命名規約

Babylon では、Blender のオブジェクト名がそのまま glTF のノード名になり、`scene.getMeshByName()` / `getTransformNodeByName()` で使う名前になる。

- 英数字とアンダースコアだけを使う（日本語・空白・記号は使わない）。`PascalCase_Variant` 形式（例: `Crate_A`, `Wall_Straight_2m`）。
- `.001` などの自動連番が付いたまま書き出さない。
- 接尾辞の規約:

| 接尾辞 | 意味 |
|---|---|
| `_collider` | 当たり判定用の簡易メッシュ。Babylon 側で `isVisible = false` にする |
| `_LOD1`, `_LOD2` | 詳細度違い（Babylon の `addLODLevel` で使う） |
| `_root` | 複数パーツをまとめる Empty |

- マテリアル名は `M_` から始める（例: `M_Wood_Dark`）。
- Action 名はそのまま Babylon の AnimationGroup 名になる（例: `Door_Open`, `Fan_Spin`）。
- 1 つのメッシュに複数のマテリアルを割り当てると、Babylon では `Name_primitive0`, `Name_primitive1` … の子メッシュに分かれる。名前で取得するコードを書く場合は注意する。

## カスタムプロパティ（Babylon へのメタデータ）

オブジェクトのカスタムプロパティは、書き出し時に **Include → Custom Properties** を ON にすると glTF の `extras` になる。Babylon では `node.metadata.gltf.extras` から読める。

- キーは `bjs_` で始める（例: `bjs_collider`, `bjs_role`, `bjs_interactive`）。
- 値は文字列・数値・真偽値にする。

## 確認用スクリーンショット

`scripts/set_view.py` で 3D ビューの視点を切り替えてから、`get_screenshot_of_area_as_image`（`area_ui_type="VIEW_3D"`）で撮る。このスクリプトが変えるのは UI（ビューの向き・ズーム・シェーディング）だけで、シーンのデータは変更しない。最後に再描画もさせる。

MATERIAL 表示に切り替えた直後は、画面左上に「Compiling EEVEE engine shaders」と出て、オブジェクトが描画されないことがある。その場合は、少し時間をおいて `set_view.py` を再実行してから撮り直す。

- 形状の確認: `ISO` と `FRONT`、必要なら `RIGHT` / `TOP`。シェーディングは `SOLID`。
- マテリアルの確認: `ISO` で、シェーディングは `MATERIAL`。
- 撮った画像をユーザーに見せ、確認ポイントで止まる。

## Babylon 側の主な挙動（参考）

Babylon.js のバージョンによって変わることがある。Babylon Sandbox で確認するのが確実。

- 同じメッシュデータを共有するオブジェクト（リンク複製）は、Babylon でインスタンスとして読み込まれる（ローダーの `createInstances` が既定で有効）。
- アニメーションは AnimationGroup として読み込まれる。既定では最初の 1 つが自動で再生される（ローダーの `animationStartMode`）。
- Draco で圧縮した GLB を読むには、Babylon 側で Draco デコーダーが必要になる。
