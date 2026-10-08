# -*- coding: utf-8 -*-
# ★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★
# ★ 这是【回归测试】，**不要粘到 Dify 的任何节点里**！                        ★
# ★ 要粘进 Dify 的是 code/score_dify.py。区分办法：那个文件的第一行是        ★
# ★     ★ 这是【打分代码】…                                                  ★
# ★ 而本文件的第一行是 ★ 这是【回归测试】…                                    ★
# ★ 本文件只在命令行跑：                                                     ★
# ★     python tests\test_score.py                                          ★
# ★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★
"""打分代码的回归测试（v2 → v7 的所有关键行为）。

为什么要放进仓库：
    每次改打分逻辑，都必须确认**之前修好的 bug 没有被改回来**。
    这个文件就是"防回归"的保险——改完代码先跑它，全绿了再粘到 Dify。

用法（在 hr-recruit-agent 目录下）：
    python tests/test_score.py
退出码：0 = 全部通过，1 = 有失败
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
    "score_dify", os.path.join(ROOT, 'code', 'score_dify.py'))
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

FAIL = []


def check(name, cond, extra=''):
    print(('  ✅ ' if cond else '  ❌ ') + name + (('   → ' + str(extra)) if extra else ''))
    if not cond:
        FAIL.append(name)


def level_of(s):
    """与 score_dify.py 里的分档保持一致（改了阈值这里也要改）。"""
    if s >= 72:
        return '推荐进入面试'
    if s >= 64:
        return '推荐进入面试（边界情况，建议人工复核）'
    if s >= 52:
        return '待定，需人工复核'
    if s >= 44:
        return '待定（边界情况，建议人工复核）'
    return '暂不推荐'


def cv_of(**kw):
    base = {"name": "测试", "education": {"degree": "本科"},
            "experiences": [{"company": "某公司", "role": "实习生",
                             "period": "2025.07-2025.12", "highlights": ["完成日常工作"]}],
            "projects": [], "skills": [], "certificates": [], "self_evaluation": ""}
    base.update(kw)
    return json.dumps(base, ensure_ascii=False)


def jd_of(hards, kws):
    return json.dumps({"hard_requirements": hards,
                       "keywords": [{"word": w, "weight": x} for w, x in kws]},
                      ensure_ascii=False)


def hc_of(pairs):
    return json.dumps({"items": [{"requirement": r, "satisfied": s, "evidence": ""}
                                 for r, s in pairs]}, ensure_ascii=False)


print('=' * 78)
print('一、v2：并列写法容错（拆成多个候选词，任一命中即算）')
print('=' * 78)
cv = cv_of(experiences=[{"company": "A", "role": "实习生",
                         "highlights": ["参与心理学方向的人才测评项目"]}],
           skills=["心理学"])
r = m.main(jd_of(["大专及以上在读"], [("人力资源/心理学/管理学专业", 5), ("沟通表达", 3)]), cv, '')
d = json.loads(r['detail'])
check('并列词任一命中（经历里有证据）→ 命中', '人力资源/心理学/管理学专业' in r['matched'], r['matched'])
check('软性词被排除出计分', '沟通表达' in d['excluded_soft'], d['excluded_soft'])

print()
print('=' * 78)
print('二、v3：hard_score 优先用语义判断，失败自动回退')
print('=' * 78)
cv2 = cv_of(skills=["Excel"])
jd3 = jd_of(["大专及以上在读", "熟练使用 Excel"], [("Excel", 5)])
r = m.main(jd3, cv2, hc_of([("大专及以上在读", True), ("熟练使用 Excel", True)]))
d = json.loads(r['detail'])
check('有判断结果 → hard_mode = model', d['hard_mode'] == 'model', d['hard_mode'])
check('全满足 → hard_score = 100', d['hard_score'] == 100, d['hard_score'])
for junk in ['', '  ', '抱歉我无法判断', '{"items":[]}', '{"items":[{"requirement"']:
    dd = json.loads(m.main(jd3, cv2, junk)['detail'])
    check('垃圾输入 %-16r 自动回退' % junk[:14], dd['hard_mode'] == 'string')

print()
print('=' * 78)
print('三、v4 + v7：关键词三态 + 证据分级')
print('=' * 78)
cv3 = cv_of(experiences=[{"company": "A", "role": "招聘实习生",
                          "highlights": ["协助安排面试，整理候选人数据 800 余条"]}],
            skills=["面试安排", "数据整理", "Photoshop"])
r = m.main(jd_of(["大专及以上在读"],
                 [("面试安排", 5), ("数据整理", 5), ("双选会", 5), ("Photoshop", 5)]), cv3, '')
d = json.loads(r['detail'])
check('「面试安排」经历里写过 → 强证据，计分命中', '面试安排' in r['matched'], r['matched'])
check('「数据整理」经历里写过 → 强证据，计分命中', '数据整理' in r['matched'], r['matched'])
check('「双选会」两处都没有 → 未命中', '双选会' in r['missing'], r['missing'])
check('「Photoshop」只在技能清单 → 弱证据，不计分',
      'Photoshop' in r['suspect'] and 'Photoshop' not in r['matched'], r['suspect'])
check('弱证据命中不计分 → keyword_score = 50（2/4 条）', d['keyword_score'] == 50, d['keyword_score'])

print()
print('=' * 78)
print('四、v7：关键词堆砌不能刷分（Day 5 实测漏洞）')
print('=' * 78)
stuffed = cv_of(
    skills=["招聘", "简历筛选", "面试邀约", "面试安排", "候选人沟通", "人才寻访", "Mapping",
            "cold call", "人才库维护", "招聘渠道运营", "校园招聘", "社会招聘", "RPO", "猎头",
            "薪酬谈判", "员工关系", "绩效考核", "SAP", "Workday", "Excel", "SQL", "Python"],
    experiences=[{"company": "某公司", "role": "实习生", "period": "2025.07-2025.08",
                  "highlights": ["完成领导交办的其他工作"]}],
    self_evaluation="学习能力强，能快速上手各类工作。")
kw = [("招聘渠道", 5), ("人才寻访", 4), ("简历筛选", 4), ("cold call", 3),
      ("人才地图", 3), ("RPO", 3)]
r = m.main(jd_of(["本科及以上学历"], kw), stuffed, hc_of([("本科及以上学历", True)]))
d = json.loads(r['detail'])
check('堆砌的技能词全部降级为"仅声明"、不计分', d['keyword_score'] == 0, d['keyword_score'])
check('堆砌项被完整列进 weak_only', len(d['weak_only']) >= 2, d['weak_only'])
check('给出"疑似关键词堆砌"的专门风险提示',
      any('疑似关键词堆砌' in x for x in r['risk']), r['risk'])

# 对照组：同样的词，但经历里真的做过 → 应该计分
real = cv_of(experiences=[{"company": "某公司", "role": "招聘实习生",
                           "highlights": ["通过招聘渠道主动人才寻访，负责简历筛选与 cold call"]}],
             skills=["招聘渠道", "人才寻访", "简历筛选", "cold call"])
r2 = m.main(jd_of(["本科及以上学历"], kw), real, hc_of([("本科及以上学历", True)]))
d2 = json.loads(r2['detail'])
check('对照组（经历里真做过）→ 正常计分', d2['keyword_score'] > 0, d2['keyword_score'])
check('对照组没有"技能堆砌"警告',
      not any('疑似关键词堆砌' in x for x in r2['risk']), r2['risk'])

print()
print('=' * 78)
print('五、v5：软性素质不参与 hard_score')
print('=' * 78)
r5 = m.main(jd_of(["本科及以上学历", "具备较强的沟通能力", "目标导向"], []),
            cv2, hc_of([("本科及以上学历", True), ("具备较强的沟通能力", True),
                        ("目标导向", False)]))
d5 = json.loads(r5['detail'])
check('2 条软性被剔除', len(d5['excluded_soft_hard']) == 2, d5['excluded_soft_hard'])
check('计分只剩 1 条', d5['scored_hard_count'] == 1, d5['scored_hard_count'])
check('hard_score = 100（不被软性稀释）', d5['hard_score'] == 100, d5['hard_score'])

print()
print('=' * 78)
print('六、v6：意愿/可用性条件改为"面试确认项"')
print('=' * 78)
r6 = m.main(jd_of(["大专及以上在读", "每周可到岗 4 天以上", "实习期不少于 3 个月", "熟练使用 Excel"],
                  [("Excel", 5)]),
            cv2, hc_of([("大专及以上在读", True), ("每周可到岗 4 天以上", False),
                        ("实习期不少于 3 个月", False), ("熟练使用 Excel", True)]))
d6 = json.loads(r6['detail'])
check('2 条进"面试确认项"', len(d6['to_confirm']) == 2, d6['to_confirm'])
check('计分只剩 2 条', d6['scored_hard_count'] == 2, d6['scored_hard_count'])
check('hard_score = 100', d6['hard_score'] == 100, d6['hard_score'])
check('risk 明确要求面试确认', any('必须在面试中确认' in x for x in r6['risk']))
check('"1年以上经验"没被误判为可用性条件', not m._is_to_confirm('1年以上招聘相关经验'))
check('"能接受出差"被正确归为可用性条件', m._is_to_confirm('能接受出差'))

print()
print('=' * 78)
print('七、分档阈值（4 个已知锚点）')
print('=' * 78)
for s, want in [(84, '推荐进入面试'), (72, '推荐进入面试'),
                (64, '推荐进入面试（边界情况，建议人工复核）'),
                (52, '待定，需人工复核'), (48, '待定（边界情况，建议人工复核）'),
                (20, '暂不推荐'), (8, '暂不推荐')]:
    check('%3d 分 → %s' % (s, want), level_of(s) == want, level_of(s))

print()
print('=' * 78)
print('八、确定性：同一输入跑 3 次结果必须完全一致')
print('=' * 78)
outs = {json.dumps(m.main(jd3, cv2, hc_of([("大专及以上在读", True), ("熟练使用 Excel", True)])),
                   ensure_ascii=False, sort_keys=True) for _ in range(3)}
check('3 次结果完全一致', len(outs) == 1, '不同结果数 = %d' % len(outs))

print()
print('=' * 78)
print('九、v8：数据不足时必须"拒绝评分"，不能造出虚假分数')
print('=' * 78)
EMPTY_JD = json.dumps({"job_title": "未说明", "hard_requirements": [], "keywords": []},
                      ensure_ascii=False)
EMPTY_CV = json.dumps({"name": "未说明", "education": {"degree": "未说明"},
                       "experiences": [], "skills": []}, ensure_ascii=False)
r9 = m.main(EMPTY_JD, EMPTY_CV, '{"items":[]}')
d9 = json.loads(r9['detail'])
check('空数据 → level = 数据不足，无法评分', r9['level'] == '数据不足，无法评分', r9['level'])
check('空数据 → score = 0（不是 56 那种"看起来正常"的分）', r9['score'] == 0, r9['score'])
check('空数据 → detail.data_ok = False', d9.get('data_ok') is False)
check('风险提示里点明"可能是填了文件路径"',
      any('文件路径' in x for x in r9['risk']), r9['risk'][0][:60])
# 只有 JD 空、简历正常 → 也要拒绝
r9b = m.main(EMPTY_JD, cv2, '')
check('只有 JD 空 → 同样拒绝评分', r9b['level'] == '数据不足，无法评分', r9b['level'])
# 正常输入不受影响
r9c = m.main(jd3, cv2, hc_of([("大专及以上在读", True), ("熟练使用 Excel", True)]))
check('正常输入不受影响', r9c['level'] != '数据不足，无法评分', r9c['level'])

print()
print('=' * 78)
if FAIL:
    print('❌ 有 %d 项失败：' % len(FAIL))
    for x in FAIL:
        print('   -', x)
    sys.exit(1)
print('全部通过 ✅')
sys.exit(0)
