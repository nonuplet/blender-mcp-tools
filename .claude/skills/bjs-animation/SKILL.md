---
name: bjs-animation
description: Babylon.js 向けのアニメーション（ドアの開閉、回転、上下動などのオブジェクトアニメーション、シェイプキー、簡易リグ）を Blender MCP で作り、glTF の AnimationGroup として書き出せる形に整える手順。Action の命名、NLA への Push Down、ループ、複数オブジェクトをまとめて 1 つのアニメーションにする方法を扱う。「回転させて」「開閉アニメーションを付けて」など、Babylon 用モデルを動かすときに使う。
---

# アニメーション

最初に `bjs-conventions` の SKILL.md を読む。キャラクターのリグ・スキニングは対象外（機械の関節程度の簡易リグまで）。

## Blender と Babylon の対応

| Blender | glTF | Babylon.js |
|---|---|---|
| Action（1 動作） | animation | AnimationGroup（名前 = Action 名） |
| NLA トラック名（既定の名前から変えた場合） | animation 名を上書き | AnimationGroup 名 |
| 同じ Action を使う複数のオブジェクト（スロット違い） | 1 つの animation | 1 つの AnimationGroup |
| オブジェクトの位置・回転・スケール | translation / rotation / scale | 各ノードのアニメーション |
| シェイプキーの値 | weights（morph target） | MorphTarget の influence |
| ポーズボーン | joints | Skeleton |

- 書き出されるのは、上の表のトランスフォーム・シェイプキー・ボーンだけ。マテリアル、ライト、物理などのアニメーションは書き出されない。
- 書き出し時の Animation Mode が既定の **Actions** のとき、書き出されるのはオブジェクトのアクティブな Action と、NLA トラックに退避（Push Down / Stash）した Action だけ。どこにも割り当てていない Action は書き出されない。
- Babylon のローダーは、既定で最初の AnimationGroup を自動再生する。自動再生させたくない場合は、Babylon 側でローダーの `animationStartMode` を NONE にする。
- 再生は Babylon 側で `scene.getAnimationGroupByName("Door_Open").start(loop)` のように行う。

## 1. 仕様を決める（確認ポイント）

- どのオブジェクトを、どう動かすか（動作ごとに Action 名を決める。例: `Door_Open`, `Door_Close`, `Fan_Spin`）
- 長さ（秒）と fps（シーンの fps を `bjs-scene-setup` で確認済みのはず）
- ループするか、1 回だけか
- 動き方（等速 = LINEAR、加減速 = BEZIER、パッと切り替え = CONSTANT）
- 原点（回転の中心）が動きに合っているか。ドアなら蝶番側、回転体なら回転軸上。合っていなければ、先に `finalize_mesh.py` の `ORIGIN` か手作業で原点を調整する

## 2. トランスフォームのアニメーションを作る

`scripts/make_transform_action.py` で、1 オブジェクトに 1 つの Action を作る。

| パラメータ | 内容 |
|---|---|
| `OBJECT` | 動かすオブジェクト |
| `ACTION_NAME` | Action 名 = Babylon の AnimationGroup 名 |
| `KEYS` | `{"frame": 1, "location": (x, y, z), "rotation_euler": (度, 度, 度), "scale": (x, y, z)}` のリスト。必要なキーだけ書く |
| `INTERPOLATION` | `"LINEAR"` / `"BEZIER"` / `"CONSTANT"` |
| `CYCLIC` | ループ用の目印（Action の Cyclic を ON にする。実際のループ再生は Babylon 側で指定する） |
| `ADD_TO_EXISTING_ACTION` | `True` にすると、既存の Action `ACTION_NAME` にこのオブジェクト用のスロットを追加する（下記） |

### 複数のオブジェクトを 1 つの AnimationGroup にまとめる

例: ドア本体と取っ手を、まとめて `Door_Open` として再生したい場合。

Blender 4.4 以降は、1 つの Action に複数のスロット（オブジェクトごとのチャンネルの組）を持たせられる。glTF exporter は既定（Merge Animation = Action）で、**同じ Action を使っているオブジェクトの動きを 1 つの animation にまとめる**。

1. 1 つ目のオブジェクトで、通常どおり Action を作る
2. 2 つ目以降のオブジェクトで、同じ `ACTION_NAME` を指定し、`ADD_TO_EXISTING_ACTION = True` で実行する

（Blender 4.3 までの「NLA トラック名をそろえてまとめる」方法は、4.4 以降は書き出し時に Merge Animation を NLA Track Name に変えないと効かない。）

- 回転は度で書く。オブジェクトの回転モードはオイラー（XYZ など）である必要がある。
- オブジェクトにすでにアクティブな Action がある場合は止まる。先に下の手順 3 で NLA へ退避する。
- ループでは最初と最後のキーが同じ姿勢になる（例: 0 度と 360 度）。継ぎ目で 1 フレーム止まって見える場合は、最後のキーを 1 フレーム後ろにずらすなどの調整をユーザーに提案する。

シェイプキーやボーンのアニメーションは、`execute_blender_code` で直接キーを打つ（シェイプキーは `key_blocks["名前"].value` を設定して `keyframe_insert("value", frame=...)`。Action はメッシュの Shape Key データ側に作られる）。

作成後、フレームを動かして（`scene.frame_set(n)`）主要なフレームのスクリーンショットを撮り、ユーザーに見せる。

**確認ポイント**: 動きの了承を得る。

## 3. NLA へ退避する

1 つのオブジェクトに複数の Action（例: 開く・閉じる）を持たせる場合や、ほかの Action を作る前に、`scripts/push_down_action.py` でアクティブな Action を NLA トラックへ退避する。

- トラック名は既定で Action 名になる。トラック名を変えると、glTF の animation 名（= AnimationGroup 名）はトラック名になる。
- 1 つの Action を複数のオブジェクトで共有している場合は、その全オブジェクトを `OBJECTS` に入れて退避する。
- 退避すると、オブジェクトのアクティブな Action は空になる。

## 4. 確認する

`bjs-export-check` の検査で、Action が書き出し対象になっているか（どこにも割り当てられていない Action がないか）を確認する。書き出し時の設定（Animation Mode = Actions など）は `bjs-export-check` のチェックリストにある。
