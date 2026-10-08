# -*- coding: utf-8 -*-
"""「岗位要求路由」代码节点的回归测试。

它保证两件事：
    1. 填了「固化好的岗位解析结果」时，**逐字使用**，不让上游波动污染分母
    2. 没填 / 填了垃圾时，自动回退用 JD解析 的结果，流程不中断

用法（在 hr-recruit-agent 目录下）：
    python tests/test_router.py
"""
import importlib.util
import json
import os
import sys
# --- 中文 Windows 兼容：输出被重定向时 stdout 会退化成 GBK，emoji 会抛 UnicodeEncodeError ---
try:
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
except Exception:
    pass


HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
spec = importlib.util.spec_from_file_location(
    "jd_router", os.path.join(ROOT, 'code', 'jd_router.py'))
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

FAIL = []


def check(name, cond, extra=''):
    print(('  ✅ ' if cond else '  ❌ ') + name + (('   → ' + str(extra)) if extra else ''))
    if not cond:
        FAIL.append(name)


parsed = json.dumps({"job_title": "招聘专员",
                     "keywords": [{"word": "简历筛选", "weight": 5}]}, ensure_ascii=False)
fixed = json.dumps({"job_title": "招聘专员",
                    "keywords": [{"word": "简历筛选", "weight": 5},
                                 {"word": "人才寻访", "weight": 5}]}, ensure_ascii=False)

print('=' * 74)
print('岗位要求路由：固化优先、解析兜底')
print('=' * 74)

cases = [
    ('没填固化值 → 用解析结果', '', parsed, 'parsed'),
    ('填了合法固化值 → 用固化值', fixed, parsed, 'fixed'),
    ('固化值有废话 + 代码块包裹 → 仍识别', '结果：\n```json\n' + fixed + '\n```\n以上。', parsed, 'fixed'),
    ('固化值是垃圾文本 → 回退', '抱歉我无法解析', parsed, 'parsed'),
    ('固化值是空 JSON 对象 → 回退', '{}', parsed, 'parsed'),
    ('固化值只有 keywords → 可用', '{"keywords":[{"word":"X","weight":5}]}', parsed, 'fixed'),
    ('两个都空 → 返回空，不报错', '', '', 'parsed'),
]
for name, f, p, want in cases:
    out = m.main(f, p)
    check(name, out['jd_source'] == want, out['jd_source'])

print()
print('=' * 74)
print('固化值必须逐字保留（这是"分母恒定"的前提）')
print('=' * 74)
o1 = m.main(fixed, parsed)
o2 = m.main(fixed, parsed)
check('同一固化值跑两次结果一致', o1 == o2)
check('关键词表被逐字保留',
      json.loads(o1['jd_json'])['keywords'] == json.loads(fixed)['keywords'],
      json.loads(o1['jd_json'])['keywords'])

print()
print('=' * 74)
if FAIL:
    print('❌ 有 %d 项失败：%s' % (len(FAIL), FAIL))
    sys.exit(1)
print('全部通过 ✅')
sys.exit(0)
