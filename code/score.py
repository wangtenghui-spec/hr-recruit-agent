# ============================================================================
# 节点③ 匹配打分 · 扣子(Coze)代码节点版 v2（与 score_dify.py 逻辑一致）
#
# 扣子代码节点配置：
#   输入参数：jd_json(String)、resume_json(String)
#   输出参数：score(Number)、level(String)、matched(Array[String])、
#            missing(Array[String])、risk(Array[String])、detail(String)
# 只用标准库 json / re。
#
# v2 新增：关键词并列写法容错 + 软性形容词过滤（与提示词 v3 构成双保险）。
#
# ⚠️ 本文件故意不用模块 docstring（三引号），全部改用 # 注释：
#    粘贴丢注释行不会报错，丢三引号会直接 SyntaxError。
# ============================================================================
import json
import re

SOFT_TRAITS = [
    '细心', '责任心', '负责', '耐心', '踏实', '积极', '主动', '乐观', '沟通', '表达',
    '性格', '态度', '抗压', '亲和力', '学习能力', '团队', '协作', '精神', '意识',
    '素养', '上进心', '认真', '敬业', '诚信', '吃苦',
]


def _strip_reasoning(t):
    """去掉混进 text 的推理块（<think>...</think> 与 Dify 的推理标记）。"""
    t = re.sub(r'<think>.*?</think>', '', t, flags=re.S | re.I)
    t = re.sub(r'<thinking>.*?</thinking>', '', t, flags=re.S | re.I)
    t = re.sub(r'<!--\s*dify-deepseek-reasoning\s*-->.*?(?=\n\s*[\{\[]|\Z)', '', t, flags=re.S)
    return t


def _extract_json(t):
    """括号配平扫描，取出第一个完整的 JSON 对象（比贪婪正则安全）。"""
    start = t.find('{')
    while start >= 0:
        depth, in_str, esc = 0, False, False
        for i in range(start, len(t)):
            c = t[i]
            if in_str:
                if esc:
                    esc = False
                elif c == '\\':
                    esc = True
                elif c == '"':
                    in_str = False
            else:
                if c == '"':
                    in_str = True
                elif c == '{':
                    depth += 1
                elif c == '}':
                    depth -= 1
                    if depth == 0:
                        try:
                            return json.loads(t[start:i + 1])
                        except Exception:
                            break
        start = t.find('{', start + 1)
    return {}


def _load(s):
    if isinstance(s, (dict, list)):
        return s
    t = _strip_reasoning(str(s or '').strip())
    t = re.sub(r'^```(?:json)?|```$', '', t.strip(), flags=re.M).strip()
    try:
        return json.loads(t)
    except Exception:
        return _extract_json(t)


def _variants(word):
    parts = re.split(r'[/、，,;；]|或', str(word))
    out = [p.strip() for p in parts if len(p.strip()) >= 2]
    return out or [str(word).strip()]


def _is_soft(word):
    parts = [p for p in re.split(r'[与和、及/]', str(word)) if p]
    if not parts:
        return False
    return all(any(s in p for p in SOFT_TRAITS) for p in parts)


async def main(args: Args) -> Output:
    params = args.params
    jd = _load(params.get('jd_json', ''))
    cv = _load(params.get('resume_json', ''))
    text = json.dumps(cv, ensure_ascii=False).lower()

    kws = jd.get('keywords') or []
    matched, missing, excluded, got, total = [], [], [], 0, 0
    for k in kws:
        word = (k.get('word') if isinstance(k, dict) else str(k)) or ''
        w = (k.get('weight', 3) if isinstance(k, dict) else 3)
        if not word:
            continue
        if _is_soft(word):
            excluded.append(word)
            continue
        total += w
        if any(v.lower() in text for v in _variants(word)):
            got += w
            matched.append(word)
        else:
            missing.append(word)
    kw_score = round(got / total * 100) if total else 60

    hard = jd.get('hard_requirements') or []
    hit = 0
    for h in hard:
        toks = [t for t in re.split(r'[，,、；;/\s]+', str(h)) if len(t) >= 2]
        if toks and any(t.lower() in text for t in toks):
            hit += 1
    hard_score = round(hit / len(hard) * 100) if hard else 60

    exp_score = 100 if (cv.get('experiences') or cv.get('projects')) else 40
    score = round(hard_score * 0.5 + kw_score * 0.3 + exp_score * 0.2)
    level = '推荐进入面试' if score >= 75 else ('待定，需人工复核' if score >= 60 else '暂不推荐')

    risk = []
    if not cv.get('experiences'):
        risk.append('简历未体现实习/工作经历')
    if hard and hard_score < 50:
        risk.append('硬性要求命中率偏低，需人工核实学历/专业/必备技能')
    if len(missing) >= 5:
        risk.append('缺失关键词较多，需核实技能真实性')

    ret: Output = {
        'score': score,
        'level': level,
        'matched': matched,
        'missing': missing,
        'risk': risk,
        'detail': json.dumps({'hard_score': hard_score, 'keyword_score': kw_score,
                              'experience_score': exp_score, 'weight': '5:3:2',
                              'excluded_soft': excluded}, ensure_ascii=False),
    }
    return ret
