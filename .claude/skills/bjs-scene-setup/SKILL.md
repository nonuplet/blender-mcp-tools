---
name: bjs-scene-setup
description: Babylon.js 向けアセットを作り始める前のシーン準備。現在のシーン（単位・fps・コレクション・既存オブジェクト）を調べ、EXPORT / WIP / REF コレクションを用意する。「Babylon 用にモデルを作りたい」「新しいアセットを作る」など、作業の最初に使う。
---

# シーンの準備

最初に `bjs-conventions` の SKILL.md を読み、規約を確認する。

## 1. シーンを調べる（読み取りのみ）

次の順で調べ、既存の構造と命名を把握する。シーンを推測で扱わない。

1. `get_objects_summary`: コレクション階層とオブジェクト一覧
2. `get_blendfile_summary_path_info`: ファイルのパスと保存状態（未保存なら、作業前に保存しておくようユーザーに伝える）
3. `scripts/inspect_scene.py`: 単位設定、fps、フレーム範囲、アクティブコレクション、規約から外れている点（`issues`）。読み取りのみなのでパラメータはない

## 2. 調査結果を報告する（確認ポイント）

次の内容をユーザーに報告し、進め方の了承を得る。

- 既存のオブジェクトとコレクション。作業で影響を受けるものがあるか
- `issues` に挙がった点（長さの単位がヤード・ポンド法、`scale_length` が 1 でない など）と、それを変えるかどうか
  - 単位系（Metric / Imperial）はスクリプトでは変更できない（hook が属性名 `system` を一律で deny にしているため）。ユーザーに **Scene Properties → Units → Unit System** を Metric にしてもらう
- これから作るコレクション（`EXPORT` / `WIP` / `REF`）。既に同名のものがあれば、それを使うか
- アニメーションを作る予定なら fps（Babylon 側でも同じ fps を前提にする。既定値の 24 か、30 / 60 にするか）

既存オブジェクトの移動・削除・名前変更は、ユーザーの指示がない限り行わない。

## 3. コレクションと単位を設定する

了承を得た内容で `scripts/setup_collections.py` のパラメータを決めて実行する。

- `SET_SCALE_LENGTH`: `scale_length` を 1.0 に戻すことをユーザーが了承した場合だけ `True` にする
- `FPS`: fps の変更をユーザーが了承した場合だけ数値を入れる（それ以外は `None`）
- `SET_ACTIVE`: 既定は `"EXPORT"`（以降、新しく作るオブジェクトはここに入る）

実行後、`get_objects_summary` でコレクションの構成を確かめて報告する。

## 次の工程

- 小物・プロップ → `bjs-prop`
- 背景・環境 → `bjs-environment`
