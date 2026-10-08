# -*- coding: utf-8 -*-
"""把 Dify 工作流和仓库文档同步（提示词 + 代码 + 变量引用）。

为什么用脚本改而不是让你手粘：
    你手粘了三次，三次都出现了花括号损坏（{{{#...#}}），
    报告节点的 suspect 变量还被截断成了孤零零的 {{，直接失效。
    人做这种"精确替换"是不可靠的，交给脚本做，一次就对。

本脚本做四件事：
    1. 备份当前 graph
    2. 把 5 个 LLM 节点的**系统提示词**从 prompts/*.md 同步过去
    3. 把 5 个 LLM 节点的**用户提示词**重建，变量引用全部用
       正确的 {{#节点ID.变量名#}} 形式（不再有手粘残留）
    4. 把「匹配打分」代码节点的源码替换为 code/score_dify.py 的最新版

用法：
    python tools/sync_dify.py           # 演练：只打印将要改什么
    python tools/sync_dify.py --apply   # 真改（会先自动备份）
"""
import io
import json
import os
import re
import subprocess
import sys
import time
# --- 中文 Windows 兼容：输出被重定向时 stdout 会退化成 GBK，emoji 会抛 UnicodeEncodeError ---
try:
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
except Exception:
    pass


HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
PROMPTS = os.path.join(ROOT, 'prompts')
BACKUP_DIR = r'C:\agent'
APP_ID = '609ae322-2e00-47c5-bef6-ae9bd4c6aa39'

# md 文件名 -> 画布上的节点标题
NODES = [
    ('jd_parse.md', 'JD\u89e3\u6790'),                 # JD解析
    ('resume_parse.md', '\u7b80\u5386\u89e3\u6790'),   # 简历解析
    ('hard_check.md', '\u786c\u6027\u8981\u6c42\u5224\u65ad'),  # 硬性要求判断
    ('questions.md', '\u9762\u8bd5\u95ee\u9898\u751f\u6210'),   # 面试问题生成
    ('report.md', '\u62a5\u544a\u751f\u6210'),         # 报告生成
]

VAR = re.compile(r'\{\{\s*([^{}]+?)\s*\}\}')


def psql(sql, want_output=True):
    p = subprocess.run(['docker', 'exec', 'docker-db_postgres-1', 'psql', '-U', 'postgres',
                        '-d', 'dify', '-A', '-t', '-c', sql], capture_output=True)
    if p.returncode != 0:
        raise SystemExit('❌ 数据库连接失败：\n' + p.stderr.decode('utf-8', 'replace')[:400])
    return p.stdout.decode('utf-8', 'replace').strip()


def fetch_graph():
    raw = psql("select graph from workflows where app_id='%s' "
               "order by updated_at desc limit 1;" % APP_ID)
    return json.loads(raw)


def md_blocks(md_path):
    """取出 md 里 系统提示词 / 用户提示词 两个代码块。"""
    t = io.open(md_path, encoding='utf-8').read()
    out = {}
    for role in ('\u7cfb\u7edf\u63d0\u793a\u8bcd', '\u7528\u6237\u63d0\u793a\u8bcd'):
        m = re.search(r'^##\s*' + role + r'\s*$(.*?)^```\n(.*?)^```', t, re.M | re.S)
        if not m:
            raise SystemExit('❌ %s 找不到 %s 代码块' % (md_path, role))
        out[role] = m.group(2).rstrip('\n')
    return out


def clean_sys(text):
    """系统提示词：剥掉 markdown 强调符号，保证喂给模型的是干净文本。"""
    text = text.replace('**', '')
    return re.sub(r'`([^`]*)`', r'\1', text)


def build_resolver(graph):
    """把「节点标题 / 变量名」映射到「节点ID」。"""
    table = {}
    for n in graph['nodes']:
        d = n['data']
        title = d.get('title')
        if d.get('type') == 'start':
            table[title] = {v.get('variable'): n['id'] for v in (d.get('variables') or [])}
        elif d.get('type') == 'code':
            table[title] = {k: n['id'] for k in (d.get('outputs') or {})}
        elif d.get('type') == 'llm':
            table[title] = {k: n['id'] for k in
                            ('text', 'reasoning_content', 'usage', 'finish_reason')}
    return table


def resolve_user_prompt(md_text, resolver):
    """把 {{节点标题 / 变量名}} 换成真正的 {{#节点ID.变量名#}}。"""
    missing = []

    def rep(m):
        spec = m.group(1).strip()
        if '/' not in spec:
            missing.append(spec)
            return m.group(0)
        title, var = [x.strip() for x in spec.split('/', 1)]
        nid = (resolver.get(title) or {}).get(var)
        if not nid:
            missing.append('%s / %s' % (title, var))
            return m.group(0)
        return '{{#%s.%s#}}' % (nid, var)

    out = VAR.sub(rep, md_text)
    return out, missing


def main():
    apply = '--apply' in sys.argv
    graph = fetch_graph()
    resolver = build_resolver(graph)

    print('=' * 84)
    print('画布上的节点与可用变量')
    print('=' * 84)
    for title, vars_ in resolver.items():
        print('  %-12s %s' % (title, list(vars_.keys())))

    nodes = {n['data'].get('title'): n for n in graph['nodes']}

    print()
    print('=' * 84)
    print('将要做的改动（演练模式，不会写入）' if not apply else '正在应用改动…')
    print('=' * 84)

    changed = []

    for md_name, title in NODES:
        node = nodes.get(title)
        if not node:
            print('  ⚠️ 画布上找不到节点「%s」，跳过' % title)
            continue
        blocks = md_blocks(os.path.join(PROMPTS, md_name))
        new_sys = clean_sys(blocks['\u7cfb\u7edf\u63d0\u793a\u8bcd'])
        new_user, miss = resolve_user_prompt(blocks['\u7528\u6237\u63d0\u793a\u8bcd'], resolver)

        old = {p['role']: p.get('text', '') for p in node['data'].get('prompt_template') or []}
        old_sys, old_user = old.get('system', ''), old.get('user', '')
        nrefs = len(re.findall(r'\{\{#[0-9a-zA-Z_]+\.[a-zA-Z0-9_]+#\}\}', new_user))

        print()
        print('  【%s】' % title)
        print('    系统提示词：%d 字 → %d 字 %s'
              % (len(old_sys), len(new_sys), '（有变化）' if old_sys != new_sys else '（无变化）'))
        print('    用户提示词：%d 字 → %d 字，变量引用 %d 个 %s'
              % (len(old_user), len(new_user), nrefs,
                 '（有变化）' if old_user != new_user else '（无变化）'))
        if miss:
            print('    ⚠️ 这些变量解析不到节点ID：%s' % miss)
        # 检查旧文本里的损坏引用
        bad = len(re.findall(r'\{\{\{', old_user)) + len(re.findall(r'\}\}\}', old_user))
        trunc = len(re.findall(r'\{\{(?![^\n]{0,80}#\}\})', old_user))
        if bad or trunc:
            print('    🔧 旧文本里发现损坏引用：多余花括号 %d 处、可能截断 %d 处'
                  % (bad, trunc))

        changed.append((node, new_sys, new_user))

    # 代码节点
    code_node = next((n for n in graph['nodes'] if n['data'].get('type') == 'code'
                      and n['data'].get('title') == '\u5339\u914d\u6253\u5206'), None)
    new_code = io.open(os.path.join(ROOT, 'code', 'score_dify.py'), encoding='utf-8').read()
    if code_node:
        old_code = code_node['data'].get('code', '')
        print()
        print('  【匹配打分（代码）】')
        print('    代码：%d 行 → %d 行 %s'
              % (len(old_code.splitlines()), len(new_code.splitlines()),
                 '（有变化）' if old_code != new_code else '（无变化）'))
        # 关键自检：粘进去的文件必须真的是打分代码，不能是别的文件
        SIG = 'def main(jd_json'
        if SIG not in old_code:
            print('    🚨 当前节点里的代码没有 "%s" —— 说明粘错文件了！' % SIG)
            print('       当前前 3 行：%s' % old_code.splitlines()[:3])
        if SIG not in new_code:
            raise SystemExit('❌ 要写入的 score_dify.py 里没有 %s，拒绝执行' % SIG)
        print('        写入前自检：新代码含 "%s" ✅' % SIG)

    if not apply:
        print()
        print('=' * 84)
        print('演练结束，没有写入任何东西。确认无误后运行：')
        print('    python tools\\sync_dify.py --apply')
        print('=' * 84)
        return

    # ---- 真正写入 ----
    os.makedirs(BACKUP_DIR, exist_ok=True)
    backup = os.path.join(BACKUP_DIR,
                          'backup-workflow-graph-%s.json' % time.strftime('%Y%m%d-%H%M%S'))
    with io.open(backup, 'w', encoding='utf-8', newline='\n') as f:
        f.write(json.dumps(graph, ensure_ascii=False, indent=1))
    print('\n已备份原图 → %s' % backup)

    for node, new_sys, new_user in changed:
        for p in node['data'].get('prompt_template') or []:
            if p['role'] == 'system':
                p['text'] = new_sys
            elif p['role'] == 'user':
                p['text'] = new_user

    if code_node:
        code_node['data']['code'] = new_code

    compact = json.dumps(graph, ensure_ascii=False, separators=(',', ':'))
    sql = ("UPDATE workflows SET graph = $g$%s$g$, updated_at = now() "
           "WHERE app_id = '%s' AND version = 'draft';" % (compact, APP_ID))
    tmp = os.path.join(BACKUP_DIR, '_sync.sql')
    with io.open(tmp, 'w', encoding='utf-8', newline='\n') as f:
        f.write(sql)
    p = subprocess.run(['docker', 'exec', '-i', 'docker-db_postgres-1',
                        'psql', '-U', 'postgres', '-d', 'dify'],
                       stdin=io.open(tmp, 'rb'), capture_output=True)
    print(p.stdout.decode('utf-8', 'replace').strip())
    if p.returncode != 0:
        raise SystemExit('❌ 写入失败：' + p.stderr.decode('utf-8', 'replace')[:400])

    # 读回验证
    g2 = fetch_graph()
    n2 = {n['data'].get('title'): n for n in g2['nodes']}
    print()
    print('=' * 84)
    print('写回验证')
    print('=' * 84)
    okall = True
    for md_name, title in NODES:
        node = n2.get(title)
        if not node:
            continue
        blocks = md_blocks(os.path.join(PROMPTS, md_name))
        want_sys = clean_sys(blocks['\u7cfb\u7edf\u63d0\u793a\u8bcd'])
        got_sys = next((p['text'] for p in node['data']['prompt_template']
                        if p['role'] == 'system'), '')
        got_user = next((p['text'] for p in node['data']['prompt_template']
                         if p['role'] == 'user'), '')
        bad = len(re.findall(r'\{\{\{|\}\}\}', got_user))
        nref = len(re.findall(r'\{\{#[0-9a-zA-Z_]+\.[a-zA-Z0-9_]+#\}\}', got_user))
        ok = (got_sys == want_sys) and bad == 0
        okall = okall and ok
        print('  %-12s 系统词%s ｜ 用户词变量 %d 个 ｜ 损坏引用 %d 处  %s'
              % (title, '✅' if got_sys == want_sys else '❌', nref, bad, '✅' if ok else '❌'))
    if code_node:
        got_code = n2['\u5339\u914d\u6253\u5206']['data']['code']
        print('  %-12s %d 行  %s' % ('匹配打分', len(got_code.splitlines()),
                                     '✅' if got_code == new_code else '❌'))
        okall = okall and got_code == new_code
    print()
    print('全部同步成功 ✅' if okall else '❌ 有项目没同步上')


if __name__ == '__main__':
    main()
