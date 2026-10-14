---
name: bjs-material
description: Babylon.js 向けに glTF へ正しく書き出せるマテリアル（PBR metallic-roughness）を Blender MCP で設定する手順。Principled BSDF の使える入力、頂点カラー、コードで生成するテクスチャ、ユーザーが読み込んだ画像の接続、透明（アルファモード）、両面表示、Babylon が対応する KHR 拡張を扱う。「マテリアルを付けて」「色を塗って」「質感を設定して」など、Babylon 用モデルの見た目を決めるときに使う。
---

# glTF 互換マテリアル

最初に `bjs-conventions` の SKILL.md を読む。

## 1. 方針を決める（確認ポイント）

作る前に、次の内容をユーザーに確認する。

- 色（16 進カラーなどで具体的に）、金属かどうか、ツヤ（roughness）
- 塗り分けの方法:
  - **マテリアルを分ける**: 単純。ただし Babylon では 1 マテリアルごとに子メッシュ（`Name_primitive0` …）に分かれ、描画回数が増える
  - **頂点カラー**: 1 マテリアルで塗り分けられる。ローポリ・フラットな見た目に向く
  - **生成テクスチャ**: チェッカー・縞・グラデーション・ざらつきなど、コードで作れる模様だけ
  - **ユーザーが用意した画像**: 生成で表現できない質感。ユーザーに Blender へ読み込んでもらう（下記）
- テクスチャを使う場合は、先に `bjs-uv` で UV を展開しておく
- 透明・発光・両面表示が必要か

## 2. 使える機能（glTF exporter が書き出すもの）

マテリアルは **Principled BSDF を Material Output に直結** した形にする。

| Principled BSDF の入力 | glTF | 備考 |
|---|---|---|
| Base Color | baseColor | 値、Image Texture、頂点カラー（Color Attribute ノード） |
| Metallic / Roughness | metallicRoughness | 値か Image Texture。テクスチャの場合は G = Roughness、B = Metallic |
| Normal | normalTexture | Normal Map ノード経由（タンジェント空間、+Y） |
| Emission Color / Strength | emissive | 合計が 1 を超えると KHR_materials_emissive_strength になる |
| Alpha | alpha | 下記「透明」を参照 |
| Coat Weight など | KHR_materials_clearcoat | ほかに transmission / sheen / specular / ior / volume / anisotropy も書き出せる |

書き出されないもの（使わない）:

- Noise / Voronoi / Wave など、Image Texture 以外のテクスチャノード（プロシージャル）
- Principled BSDF 以外のシェーダー（Diffuse BSDF など）。例外として、Emission と Add Shader の組み合わせ、unlit（カメラレイを混ぜる構成）は書き出せる
- マテリアルのアニメーション

プロシージャルな見た目を画像に焼き付けるベイクは hook で禁止されているため、模様は `make_generated_texture.py` で作れる範囲にする。それ以上の質感が必要な場合は、ユーザーに画像を用意して読み込んでもらう（「ユーザーが用意した画像を使う」）。

## 3. マテリアルを作る

`scripts/make_material.py` を使う。

| パラメータ | 内容 |
|---|---|
| `NAME` | マテリアル名（`M_` で始める） |
| `BASE_COLOR` | `"#RRGGBB"`（sRGB の 16 進）か、リニアの `(r, g, b)` |
| `METALLIC` / `ROUGHNESS` | 0〜1 |
| `EMISSION_COLOR` / `EMISSION_STRENGTH` | 発光。不要なら強さ 0 |
| `ALPHA` | 1 未満にすると透明（glTF の BLEND モード） |
| `DOUBLE_SIDED` | `True` で両面表示（Backface Culling を OFF にする） |
| `USE_VERTEX_COLOR` | `True` で、頂点カラーを Base Color に乗算する（下記） |
| `ASSIGN_TO` / `SLOT_INDEX` | 割り当てるオブジェクトと、マテリアルスロットの番号 |
| `OVERWRITE` | 同名のマテリアルがある場合に作り直すか。既定は `False`（エラーで止まる） |

- 同名のマテリアルを `OVERWRITE = True` で作り直すと、そのマテリアルを使っているほかのオブジェクトの見た目も変わる。結果の `users` を確認し、必要ならユーザーに伝える。
- マテリアルスロットがないオブジェクトに割り当てると、メッシュデータにスロットが追加される。リンク複製では、同じメッシュを共有するすべてのオブジェクトに反映される。
- 同じ質感のものには同じマテリアルを使い回す（Babylon での描画回数が減る）。

### 頂点カラーで塗り分ける

1. 頂点カラー（Color Attribute）を bmesh などで面ごとに設定する（ドメインは `CORNER`、型は `BYTE_COLOR` を基本にする）
2. `USE_VERTEX_COLOR = True`、`BASE_COLOR = "#FFFFFF"` でマテリアルを作る（Base Color と頂点カラーの積が最終的な色になる）
3. 書き出し時の **Data → Mesh → Vertex Color → Use Vertex Color** は既定の **Material** のままでよい（マテリアルで使っている頂点カラーが書き出される）

### 生成テクスチャ

`scripts/make_generated_texture.py` で、コード生成した画像を作って Base Color につなぐ。

| `PATTERN` | 内容 |
|---|---|
| `CHECKER` | `CELLS` × `CELLS` の市松模様 |
| `STRIPES` | V 方向に `CELLS` 本の縞（板材など） |
| `GRADIENT` | 下（V=0）から上へ `COLOR_A` → `COLOR_B` |
| `SOLID` | `COLOR_A` の単色（`GRAIN` と組み合わせてざらつきを出す） |

- `GRAIN`（0〜1）で、ピクセルごとに明るさのばらつきを加えられる。
- 画像サイズ（`SIZE`）は 2 のべき乗（256 / 512 / 1024）にする。Web 向けでは 1024 以下が無難。
- `INTERPOLATION = "Closest"` でドット絵風になる（glTF のサンプラーでは NEAREST になる）。
- 画像は `.blend` に pack される。pack しないと、保存して開き直したときに模様が消える。
- UV が必要。先に `bjs-uv` で、模様の向き・縮尺・つながりを決めて展開しておく。
- 模様の 1 枚分（`SIZE`）が UV の 0〜1 に対応する。継ぎ目なく繰り返すには、`CHECKER` / `STRIPES` の `CELLS` を偶数にする。

### ユーザーが用意した画像を使う

生成テクスチャで表現できない質感が必要な場合は、**無理に生成せず**、ユーザーに画像を用意して Blender に読み込んでもらう（Claude は画像の読み込みも Web からの取得もできない）。

1. 必要な画像（用途、タイル状かどうか、推奨サイズ: 2 のべき乗で 1024 以下）をユーザーに伝え、Blender に読み込んでもらう（Image Editor の Image → Open など）
2. 読み込んだ画像の名前を確認する（`get_blendfile_summary_datablocks` などで確認できる）
3. `scripts/connect_image_texture.py` で、マテリアルの入力につなぐ

| パラメータ | 内容 |
|---|---|
| `IMAGE` | 読み込み済みの画像の名前 |
| `MATERIAL` | つなぐマテリアル |
| `INPUT` | `"Base Color"` / `"Normal"`（Normal Map ノードを経由し、色空間を Non-Color にする）/ `"Emission Color"` |
| `INTERPOLATION` / `EXTENSION` | 補間と、範囲外の扱い（タイル状なら `"REPEAT"`） |

- 外部ファイルを参照している画像も、GLB には埋め込まれる。`.blend` を別の場所へ移す場合は、ユーザーに File → External Data → Pack Resources を依頼する。
- Metallic / Roughness の画像は、glTF では 1 枚の画像の G（Roughness）と B（Metallic）にまとめる必要がある。必要になったら、つなぎ方をユーザーと相談する。

### 透明

glTF のアルファモードは、Alpha 入力につながっているノードから exporter が自動で決める。

| モード | 条件 | 用途 |
|---|---|---|
| OPAQUE | Alpha が常に 1 | 通常 |
| MASK | Alpha を Math（Round）で 0 か 1 にしている | 葉、金網などの切り抜き |
| BLEND | それ以外（Alpha が 1 未満） | ガラス、半透明の膜 |

BLEND は Babylon でも描画順の問題が起きやすい。必要な部分だけを別オブジェクト・別マテリアルにする。

### 両面表示

マテリアルの **Backface Culling** が OFF だと、glTF の doubleSided が true になる。板 1 枚の葉や布など、裏側も見えるものだけ `DOUBLE_SIDED = True` にする。

## 4. 確認する（確認ポイント）

`set_view.py` を `SHADING = "MATERIAL"`、`VIEW = "ISO"` で実行してスクリーンショットを撮り、ユーザーに見せる。Blender（EEVEE）と Babylon では見え方が少し違う（特に環境光と金属・ツヤ）ことも伝える。

## 次の工程

- 動かす場合 → `bjs-animation`
- 書き出す前 → `bjs-export-check`
