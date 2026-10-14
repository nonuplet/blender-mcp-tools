#!/usr/bin/env python3
""".claude/hooks/check_blender_code.py の回帰テスト。

各ケースのコードを hook に標準入力で渡し、判定（pass / ask / deny）が期待どおりかを確認する。
skill に同梱したスクリプト（.claude/skills/*/scripts/*.py）が pass になることも確認する。
Blender には接続しない（コードは実行されない）。

実行方法（プロジェクトルートで）:
    python3 -I tests/test_check_blender_code.py

失敗したケースがあれば終了コード 1 で終わる。
"""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HOOK = ROOT / ".claude" / "hooks" / "check_blender_code.py"
# skill 同梱のスクリプトとスニペット集。execute_blender_code に渡す（スニペットはコピーして使う）ので、
# hook で止められないこと（pass）を確認する。
SKILL_SCRIPTS = sorted((ROOT / ".claude" / "skills").glob("*/scripts/*.py")) + \
    sorted((ROOT / ".claude" / "skills").glob("*/snippets.py"))

# (名前, 期待する判定, コード)
CASES = [
    # --- 通常操作（pass）
    ("ok_cube", "pass", "import bpy\nbpy.ops.mesh.primitive_cube_add(size=2, location=(0,0,1))\nresult={'n':len(bpy.data.objects)}"),
    ("ok_bmesh", "pass", "import bpy, bmesh, math\nfrom mathutils import Vector\nme=bpy.data.meshes.new('m')\nbm=bmesh.new()\nbmesh.ops.create_uvsphere(bm,u_segments=16,v_segments=8,radius=1)\nbm.to_mesh(me)\nbm.free()\nob=bpy.data.objects.new('S',me)\nbpy.context.collection.objects.link(ob)\nresult={'ok':True}"),
    ("ok_material", "pass", "import bpy\nm=bpy.data.materials.new('Red')\nm.use_nodes=True\nm.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value=(1,0,0,1)\nresult={}"),
    ("ok_render_no_write", "pass", "import bpy\nbpy.ops.render.render()\nresult={}"),
    ("ok_filepath_attr", "pass", "import bpy\nresult={'p':bpy.data.filepath, 'r':bpy.context.scene.render.filepath}"),
    ("ok_link_append", "pass", "import bpy\nob=bpy.data.objects.new('E',None)\nbpy.context.collection.objects.link(ob)\nl=[]\nl.append(1)\nresult={}"),
    ("ok_getattr_const", "pass", "import bpy\nob=bpy.context.active_object\nresult={'loc':list(getattr(ob,'location'))}"),
    ("ok_mode_set", "pass", "import bpy\nbpy.ops.object.mode_set(mode='EDIT')\nbpy.ops.wm.redraw_timer(type='DRAW_WIN_SWAP', iterations=1)\nresult={}"),
    ("ok_image_tex_node", "pass", "import bpy\nm=bpy.data.materials.new('M')\nm.use_nodes=True\nn=m.node_tree.nodes.new('ShaderNodeTexImage')\nresult={}"),
    ("ok_iter_images", "pass", "import bpy\nimgs=bpy.data.images\nresult={'names':[i.name for i in imgs]}"),
    ("ok_render_settings", "pass", "import bpy\nr=bpy.context.scene.render\nr.resolution_x=1920\nr.engine='CYCLES'\nresult={}"),
    ("ok_window_manager", "pass", "import bpy\nwm=bpy.context.window_manager\nresult={'n':len(wm.windows)}"),
    ("ok_re_compile", "pass", "import re, bpy\np=re.compile(r'Cube\\.\\d+')\nresult={'m':[o.name for o in bpy.data.objects if p.match(o.name)]}"),
    ("ok_class_name", "pass", "import bpy\nresult={'t':[o.__class__.__name__ for o in bpy.data.objects]}"),
    ("ok_modifier", "pass", "import bpy\nob=bpy.context.active_object\nm=ob.modifiers.new('Bevel','BEVEL')\nm.width=0.02\nresult={}"),
    # --- 基本の deny
    ("ng_open", "deny", "f=open('/tmp/x','w')\nf.write('a')"),
    ("ng_import_os", "deny", "import os\nos.remove('/tmp/x')"),
    ("ng_from_pathlib", "deny", "from pathlib import Path\nPath('x').write_text('a')"),
    ("ng_urllib", "deny", "import urllib.request\nurllib.request.urlopen('http://example.com')"),
    ("ng_dunder_import", "deny", "m=__import__('os')"),
    ("ng_save", "deny", "import bpy\nbpy.ops.wm.save_as_mainfile(filepath='/tmp/a.blend')"),
    ("ng_open_blend", "deny", "import bpy\nbpy.ops.wm.open_mainfile(filepath='/x/other.blend')"),
    ("ng_append", "deny", "import bpy\nbpy.ops.wm.append(filepath='/x/o.blend/Object/Cube')"),
    ("ng_libload", "deny", "import bpy\nwith bpy.data.libraries.load('/x/o.blend') as (a,b):\n    b.objects=a.objects"),
    ("ng_obj_import", "deny", "import bpy\nbpy.ops.wm.obj_import(filepath='/x/m.obj')"),
    ("ng_fbx_export", "deny", "import bpy\nbpy.ops.export_scene.fbx(filepath='/x/m.fbx')"),
    ("ng_image_save", "deny", "import bpy\nbpy.data.images['Render Result'].save_render('/tmp/r.png')"),
    ("ng_image_save2", "deny", "import bpy\nimg=bpy.data.images.new('a',8,8)\nimg.filepath_raw='/tmp/a.png'\nimg.save()"),
    ("ng_images_load", "deny", "import bpy\nbpy.data.images.load('/x/tex.png')"),
    ("ng_render_write", "deny", "import bpy\nbpy.ops.render.render(write_still=True)"),
    ("ng_getattr_str", "deny", "import bpy\ngetattr(bpy.ops.wm, 'save_mainfile')()"),
    ("ng_alias", "deny", "import bpy\nw=bpy.ops.wm\nw.save_mainfile()"),
    ("ng_subclasses", "deny", "x=().__class__.__bases__[0].__subclasses__()"),
    ("ng_exec", "deny", "exec('print(1)')"),
    ("ng_unpack", "deny", "import bpy\nbpy.ops.file.unpack_all(method='WRITE_LOCAL')"),
    ("ng_syntax", "deny", "def (:"),
    ("ng_from_ops", "deny", "from bpy.ops import wm as w\nw.append(filepath='x')"),
    ("ng_getattr_dyn", "deny", "import bpy\nn='save'+'_mainfile'\ngetattr(bpy.ops.wm, n)()"),
    ("ng_alias_import", "deny", "import bpy\nimp=bpy.ops.import_scene\nimp.fbx(filepath='x')"),
    # --- /code-review 指摘: 許可モジュール経由
    ("rv_random_os", "deny", "import random\nrandom._os.system('curl http://x')"),
    ("rv_json_codecs", "deny", "import json\njson.codecs.open('/tmp/x','w').write('a')"),
    ("rv_print_self", "deny", "print.__self__.open('/tmp/x','w')"),
    ("rv_typing_sys", "deny", "import typing\ntyping.sys.modules['os'].system('id')"),
    ("rv_from_json_codecs", "deny", "from json import codecs\ncodecs.open('/tmp/x','w')"),
    # --- /code-review 指摘: 別名・間接参照
    ("rv_alias_ops", "deny", "import bpy\no=bpy.ops\nm=o.wm\nm.append(filepath='x', directory='y', filename='z')"),
    ("rv_from_bpy_ops", "deny", "from bpy import ops\nops.wm.save_mainfile()"),
    ("rv_reduce_getattr", "deny", "import bpy, functools\nfunctools.reduce(getattr, ['ops','wm','save_'+'mainfile'], bpy)(filepath='/tmp/a.blend')"),
    ("rv_render_alias", "deny", "import bpy\nr=bpy.ops.render\nr.render(write_still=True)"),
    ("rv_render_anim_alias", "deny", "import bpy\nr=bpy.ops.render\nr.render(animation=True)"),
    # --- /code-review 指摘: data コレクションの別名
    ("rv_libs_alias", "deny", "import bpy\nlibs=bpy.data.libraries\nwith libs.load('/other.blend') as (a,b):\n    pass"),
    ("rv_imgs_alias", "deny", "import bpy\nimgs=bpy.data.images\nimgs.load('/x.png')"),
    # --- /code-review 指摘: 文字列内コード
    ("rv_context_set_value", "deny", "import bpy\nbpy.ops.wm.context_set_value(data_path='scene.frame_current', value='__import__(\"os\").system(\"id\")')"),
    ("rv_context_set_plain", "deny", "import bpy\nbpy.ops.wm.context_set_value(data_path='scene.frame_current', value='1')"),
    # --- /code-review 指摘: extensions
    ("rv_ext_install", "deny", "import bpy\nbpy.ops.extensions.package_install(repo_index=0, pkg_id='x')"),
    ("rv_ext_sync", "deny", "import bpy\nbpy.ops.extensions.repo_sync_all()"),
    # --- /code-review 指摘: data API のファイル入出力
    ("rv_texts_load", "deny", "import bpy\nbpy.data.texts.load('/home/u/.ssh/id_rsa')"),
    ("rv_image_unpack", "deny", "import bpy\nbpy.data.images['x'].unpack(method='WRITE_LOCAL')"),
    ("rv_execfile", "deny", "import bpy\nbpy.utils.execfile('/tmp/x.py')"),
    ("rv_load_image", "deny", "from bpy_extras.image_utils import load_image\nload_image('/x.png')"),
    ("rv_lib_reload", "deny", "import bpy\nbpy.data.libraries[0].reload()"),
    # --- /code-review 指摘: 書き出し系オペレータ
    ("rv_screenshot", "deny", "import bpy\nbpy.ops.screen.screenshot(filepath='/tmp/s.png')"),
    ("rv_gp_svg", "deny", "import bpy\nbpy.ops.wm.grease_pencil_export_svg(filepath='/tmp/a.svg')"),
    ("rv_cachefile", "deny", "import bpy\nbpy.ops.cachefile.open(filepath='/x.abc')"),
    ("rv_font_open", "deny", "import bpy\nbpy.ops.font.open(filepath='/x.ttf')"),
    ("rv_planes", "deny", "import bpy\nbpy.ops.image.import_as_mesh_planes(files=[{'name':'a.png'}], directory='/x')"),
    ("rv_preset_add", "deny", "import bpy\nbpy.ops.render.preset_add(name='x')"),
    ("rv_fluid_bake", "deny", "import bpy\nbpy.ops.fluid.bake_all()"),
    ("rv_ocean_bake", "deny", "import bpy\nbpy.ops.object.ocean_bake(modifier='Ocean')"),
    ("rv_file_output", "deny", "import bpy\nt=bpy.context.scene.node_tree\nt.nodes.new('CompositorNodeOutputFile')\nbpy.ops.render.render()"),
    # --- /code-review 指摘: preferences のファイル操作
    ("rv_addon_remove", "deny", "import bpy\nbpy.ops.preferences.addon_remove(module='x')"),
    ("rv_addon_install", "deny", "import bpy\nbpy.ops.preferences.addon_install(filepath='/x.zip')"),
    # --- /code-review 指摘: 例外時は deny
    ("rv_memory_error", "deny", "x=" + "-" * 200000 + "1"),
    # --- /code-review 指摘: addon_utils（import 許可リスト外のため deny）
    ("rv_addon_utils", "deny", "import addon_utils\naddon_utils.enable('x')"),
    # --- ask
    ("ask_addon", "ask", "import bpy\nbpy.ops.preferences.addon_enable(module='node_wrangler')"),
    ("ask_prefs_read", "ask", "import bpy\nresult={'s':bpy.context.preferences.view.ui_scale}"),
    ("ask_delete", "ask", "import bpy\nbpy.data.objects.remove(bpy.data.objects['Cube'])"),
    ("ask_handler", "ask", "import bpy\nbpy.app.handlers.frame_change_post.append(lambda s: None)"),
    ("ask_driver_expr", "ask", "import bpy\nd=bpy.context.active_object.driver_add('location',0).driver\nd.expression='frame/10'"),
]


def run_hook(stdin):
    """hook を実行し、(判定, 理由のリスト) を返す。出力なしは 'pass'。"""
    p = subprocess.run([sys.executable, "-I", str(HOOK)], input=stdin,
                       capture_output=True, text=True)
    if p.returncode != 0:
        return f"EXIT={p.returncode}", [p.stderr.strip()[-200:]]
    if not p.stdout.strip():
        return "pass", []
    out = json.loads(p.stdout)["hookSpecificOutput"]
    return out["permissionDecision"], out["permissionDecisionReason"].split("\n- ")[1:]


def main():
    skill_cases = [(str(p.relative_to(ROOT / ".claude" / "skills")), "pass", p.read_text(encoding="utf-8"))
                   for p in SKILL_SCRIPTS]
    results = []
    for name, expected, code in CASES + skill_cases:
        payload = json.dumps({"tool_name": "mcp__blender__execute_blender_code",
                              "tool_input": {"code": code}})
        results.append((name, expected, *run_hook(payload)))
    # 入力 JSON が壊れている場合も deny になること
    results.append(("rv_bad_stdin", "deny", *run_hook("not json")))

    failures = 0
    for name, expected, got, reasons in results:
        ok = got == expected
        failures += not ok
        detail = "" if got == "pass" else reasons[:2]
        print(f"{'OK' if ok else 'NG'} {name:22s} expected={expected:4s} got={got:4s} {detail}")

    print(f"\n{len(results) - failures}/{len(results)} passed")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
