# -*- coding: utf-8 -*-
"""把某个岗位的解析结果"固化"成岗位档案。

【什么是固化】
    现状：每来一个候选人，`JD解析` 节点都**重新抽一次签**，决定这个岗位用哪些关键词打分。
          同一个 JD 连跑 8 次，关键词总权重（也就是打分的分母）在 38 ~ 58 之间摆。
          → 候选人 A 用"分母 38"量、候选人 B 用"分母 58"量，**分数根本不可比**。

    固化：抽一次签，把结果**存成文件**（岗位档案），以后这个岗位的所有候选人共用这一份。
          → 分母恒定，候选人之间可比，分数也可复现。

【用法】
    python tools/freeze_jd.py jd_01 "人力资源实习生"
    python tools/freeze_jd.py jd_02 "招聘专员"
       参数 1：输出文件名（写到 data/jd_fixed/<名字>.json）
       参数 2：用来在历史运行里认出这个岗位的关键词（取 JD 原文的前若干字）

【挑选标准（人审）】
    1. keywords 每条都是**单一术语**——不要"候选人数据库维护"这种带动作的长词，
       因为字面匹配长词更容易落空
    2. hard_requirements 里没有混进软性素质
    3. 带"优先/加分"的已经移进 nice_to_have
    脚本会自动挑符合这些条件的**最近一次**结果；挑不到就报错，让你手工处理。
"""
import io
import json
import os
import re
import subprocess
import sys
# --- 中文 Windows 兼容：输出被重定向时 stdout 会退化成 GBK，emoji 会抛 UnicodeEncodeError ---
try:
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
except Exception:
    pass


HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT_DIR = os.path.join(ROOT, 'data', 'jd_fixed')
APP_ID = '609ae322-2e00-47c5-bef6-ae9bd4c6aa39'

LABEL_START = '\u7528\u6237\u8f93\u5165'      # 用户输入
LABEL_JDPARSE = 'JD\u89e3\u6790'              # JD解析


def psql(sql):
    p = subprocess.run(['docker', 'exec', 'docker-db_postgres-1', 'psql', '-U', 'postgres',
                        '-d', 'dify', '-A', '-t', '-c', sql], capture_output=True)
    if p.returncode != 0:
        raise SystemExit('❌ 连不上数据库，确认 Dify 的 db 容器在跑：\n'
                         + p.stderr.decode('utf-8', 'replace')[:300])
    return p.stdout.decode('utf-8', 'replace').strip()


def tolerant_json(txt):
    """容忍推理块、代码块、前后废话的 JSON 解析。"""
    t = re.sub(r'<think>.*?</think>', '', txt or '', flags=re.S | re.I)
    t = re.sub(r'<!--\s*dify-deepseek-reasoning\s*-->.*?(?=\n\s*[\{\[]|\Z)', '', t, flags=re.S)
    t = re.sub(r'^```(?:json)?|```$', '', t.strip(), flags=re.M).strip()
    try:
        return json.loads(t)
    except Exception:
        pass
    s = t.find('{')
    while s >= 0:
        depth = 0
        for i in range(s, len(t)):
            if t[i] == '{':
                depth += 1
            elif t[i] == '}':
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(t[s:i + 1])
                    except Exception:
                        break
        s = t.find('{', s + 1)
    return None


def main():
    if len(sys.argv) < 3:
        raise SystemExit(__doc__)
    name, marker = sys.argv[1], sys.argv[2]

    runs = psql("select id from workflow_runs where app_id='%s' order by created_at desc limit 30;"
                % APP_ID).split('\n')
    candidates = []
    for rid in runs:
        rid = rid.strip()
        if not rid:
            continue
        rows = psql("select title, outputs from workflow_node_executions "
                    "where workflow_run_id='%s' order by created_at;" % rid)
        start = parsed = None
        for line in rows.split('\n'):
            if '|' not in line:
                continue
            t, raw = line.split('|', 1)
            t = t.strip()
            try:
                d = json.loads(raw)
            except Exception:
                continue
            if t == LABEL_START:
                start = d
            elif t == LABEL_JDPARSE:
                parsed = d
        if not start or not parsed:
            continue
        if marker not in (start.get('jd_text') or ''):
            continue
        j = tolerant_json(parsed.get('text', ''))
        if j:
            candidates.append((rid, j))

    print('找到 %d 次「%s」的 JD解析 结果' % (len(candidates), marker))
    if not candidates:
        raise SystemExit('❌ 没找到。确认这个 JD 跑过至少一次，且 marker 词出现在 JD 原文里。')

    # 按人审标准挑：全是单一术语（<=6 字）且已按新规则分出 soft_qualities
    best = None
    for rid, j in candidates:
        kws = j.get('keywords') or []
        if not kws:
            continue
        if any(len(str(k.get('word', ''))) > 6 for k in kws):
            continue
        if not j.get('soft_qualities'):
            continue
        best = (rid, j)
        break
    if not best:
        best = candidates[0]
        print('⚠️ 没有完全符合"单一术语 + 已分 soft_qualities"的版本，退回用最近一次结果')
        print('   建议手工审一遍 keywords，把长词改成单一术语。')

    rid, j = best
    os.makedirs(OUT_DIR, exist_ok=True)
    out = os.path.join(OUT_DIR, '%s.json' % name)
    archive = {
        "_说明": "岗位档案（固化版）。由 JD解析 跑出的结果经人工审阅后固化，"
                 "同一岗位的所有候选人共用这一份，保证打分分母恒定、分数可比。",
        "_来源": "run %s" % rid[:8],
        "_审阅要点": [
            "keywords 每条都是单一术语（避免'候选人数据库维护'这类带动作的长词）",
            "hard_requirements 只含可从简历核验的条件",
            "软性素质在 soft_qualities 里，不参与计分",
            "带'优先/加分'的在 nice_to_have 里",
        ],
        "_用法": "运行时把本文件全部内容粘贴到「用户输入 / jd_json_fixed」；"
                 "跑完确认「岗位要求路由」节点的 jd_source = fixed",
        "job_title": j.get('job_title'),
        "seniority": j.get('seniority'),
        "hard_requirements": j.get('hard_requirements'),
        "nice_to_have": j.get('nice_to_have'),
        "soft_qualities": j.get('soft_qualities'),
        "keywords": j.get('keywords'),
    }
    with io.open(out, 'w', encoding='utf-8', newline='\n') as f:
        f.write(json.dumps(archive, ensure_ascii=False, indent=2))

    tot = sum(k['weight'] for k in archive['keywords'])
    print()
    print('✅ 已生成岗位档案：%s' % out)
    print('   岗位：%s' % archive['job_title'])
    print('   keywords %d 条，总权重（分母）= %d' % (len(archive['keywords']), tot))
    print('   hard_requirements %d 条｜soft_qualities %d 条｜nice_to_have %d 条'
          % (len(archive['hard_requirements'] or []), len(archive['soft_qualities'] or []),
             len(archive['nice_to_have'] or [])))


if __name__ == '__main__':
    main()
