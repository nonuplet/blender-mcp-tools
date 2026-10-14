---
name: bjs-export-check
description: Babylon.js 向けアセットを GLB に書き出す前の検査と、手動書き出しの手順。シーンを変更せずに、スケール・非多様体・UV・書き出されないノード・ポリゴン数・テクスチャサイズ・名前・Action を検査し、glTF exporter の推奨設定チェックリストと Babylon Sandbox での確認手順を示す。「書き出したい」「GLB にして」「エクスポート前にチェックして」など、モデルが完成したときに使う。
---

# 書き出し前の検査と手動書き出し

最初に `bjs-conventions` の SKILL.md を読む。

**GLB の書き出しは Claude が行わない**（`export_scene.*` は hook で禁止されている）。この skill の役割は、検査と、ユーザーが GUI で書き出すための案内まで。

## 1. 検査する

`scripts/check_export.py` を実行する。シーンを変更しない読み取り専用の検査。

| パラメータ | 内容 | 既定値 |
|---|---|---|
| `COLLECTION` | 検査するコレクション（`None` なら表示中のオブジェクトすべて） | `"EXPORT"` |
| `TRI_BUDGET_TOTAL` / `TRI_BUDGET_OBJECT` | 三角形数の目安（全体／1 オブジェクト） | 50,000 / 10,000 |
| `MAX_TEXTURE_SIZE` | テクスチャの一辺の上限の目安 | 2048 |

検査する主な項目:

- シーン: 単位、fps
- オブジェクト: 名前（英数字とアンダースコアだけか、`.001` が付いていないか）、種類、負のスケール、スケールの未適用、非表示
- メッシュ（モディファイア適用後）: 三角形数、非多様体の辺、孤立した頂点・辺、面積 0 の面、5 角形以上の面、モディファイアの有無、寸法と原点の位置
- マテリアル: 出力の接続、Principled BSDF 以外のシェーダー、書き出されないテクスチャノード、画像のサイズ（2 のべき乗か、大きすぎないか）、pack されていない生成画像、UV と頂点カラーの有無、両面表示、透明、発光
- アニメーション: 書き出される Action（アクティブなものと NLA にあるもの）、どこにも割り当てられていない Action

## 2. 結果を報告する（確認ポイント）

結果を次の形でユーザーに報告する。

- `errors`: 書き出すと問題になるもの。直し方を提案する
- `warnings`: 確認が必要なもの。直すかどうかをユーザーに聞く
- `infos`: 参考情報。要点だけ伝える
- 概要: オブジェクト数、合計三角形数、マテリアル数、書き出される Action

**検査結果をもとに、自己判断で修正しない。** 直す項目と直し方をユーザーと決めてから、該当する skill（`bjs-prop` / `bjs-material` / `bjs-animation`）の手順で直し、もう一度検査する。

## 3. 手動書き出しのチェックリスト

`errors` がなくなったら、次のチェックリストをユーザーに示す。項目名は Blender 5.x の glTF 2.0 exporter のもの。

**書き出す前に**

- [ ] アウトライナーで `EXPORT` コレクションをクリックして、アクティブにする
- [ ] オブジェクトモードにする

**File → Export → glTF 2.0 (.glb/.gltf)**

| 項目 | 設定 | 補足 |
|---|---|---|
| Format | glTF Binary (.glb) | 1 ファイルにまとまる |
| Include → Limit to → Active Collection | ON | `EXPORT` の中だけを書き出す |
| Include → Limit to → Include Nested Collections | 必要なら ON | `EXPORT` の下にコレクションを作った場合 |
| Include → Data → Custom Properties | タグを使っているなら ON | Babylon の `metadata.gltf.extras` になる |
| Include → Data → Cameras | OFF | カメラは Babylon 側で作る |
| Include → Data → Punctual Lights | OFF（Blender のライトを使う場合だけ ON） | |
| Transform → +Y Up | ON（既定） | |
| Data → Mesh → Apply Modifiers | **ON** | Smooth by Angle・Bevel などを反映するため |
| Data → Mesh → UVs / Normals | ON（既定） | |
| Data → Mesh → Tangents | OFF（ノーマルマップを使う場合だけ ON） | |
| Data → Mesh → Vertex Color → Use Vertex Color | Material（既定） | |
| Data → Material → Materials | Export（既定） | |
| Data → Material → Images | Automatic（PNG）。小さくしたい場合は WebP | WebP を選ぶと PNG/JPEG の予備は作られない |
| Data → Shape Keys | シェイプキーを使っている場合 ON | |
| Data → Compression | OFF（サイズを小さくしたい場合だけ ON） | ON にすると Babylon 側で Draco デコーダーが必要 |
| Animation | アニメーションがあれば ON | |
| Animation → Animation mode | Actions（既定） | |
| Animation → Bake & Merge → Merge Animation | Action（既定） | 同じ Action を使うオブジェクトが 1 つの AnimationGroup になる |

- 保存先とファイル名はユーザーが決める（Web プロジェクトのアセット置き場など）。ファイル名は英小文字・数字・ハイフンにしておくと URL で扱いやすい（例: `crate-a.glb`）。
- 同じアセットを何度も書き出す場合は、コレクションの **Exporters**（Collection プロパティ → Exporters → glTF 2.0）に一度設定しておくと、次回からはボタン 1 つで書き出せる（Include の項目はない）。
- **Remember Export Settings** を ON にすると、設定が `.blend` に保存される。

## 4. Babylon で確認する

ユーザーに、書き出した GLB を Babylon.js Sandbox（ブラウザで開くビューアー）にドラッグ＆ドロップして、次の点を確かめてもらう。

- [ ] 大きさ（Inspector でメッシュのバウンディングボックスを見る。1 unit = 1 m）
- [ ] 向き（正面がどちらを向いているか）
- [ ] マテリアルの色・ツヤ・透明・両面表示
- [ ] 当たり判定用の `_collider` が見えている（Babylon 側で非表示にする前提なので、Sandbox では見えていてよい）
- [ ] アニメーション（下部のバーで AnimationGroup を切り替えて再生する）
- [ ] カスタムプロパティ（Inspector でノードを選び、metadata に `gltf.extras` があるか）

問題があれば内容を聞き、該当する skill に戻る。
