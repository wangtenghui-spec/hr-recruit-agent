# ============================================================================
# 节点③ 匹配打分 · Dify 代码节点版 v4（三态关键词匹配 + 语义硬性判断 + 容错）
#
# 用法：整段复制到 Dify 的「代码」节点（从本文件第一行复制到最后一行）
#   输入变量（均声明为 String）：jd_json、resume_json、hard_check_json
#       - hard_check_json：接「硬性要求判断」LLM 节点的 text 输出；
#         该节点还没建好时，把这一项留空（或先写死成空字符串），脚本会自动回退字符串匹配
#   输出变量：score(Number)、level(String)、matched(Array[String])、
#            missing(Array[String])、suspect(Array[String])、risk(Array[String])、
#            detail(String)
# 只依赖标准库 json / re，无需安装任何包。
#
# 版本演进：
#   v2  并列写法容错（"人力资源/心理学"拆成多个候选词）+ 软性词过滤
#   v3  hard_score 优先用「硬性要求判断」节点的语义判断结果，拿不到就回退字符串匹配；
#       detail 增加 hard_mode / hard_items；档位加边界缓冲
#   v4  **关键词改为三态判定**：命中 / 疑似 / 未命中
#       - 命中：字面子串匹配成功 → 计分
#       - 疑似：汉字关键词的字符二元组重叠率 >= 0.6 → **不计分**，单独列出交人工确认
#         解决中文动宾倒装导致的漏判，例如
#           JD「面试安排」 vs 简历「协助安排面试」
#           JD「数据整理」 vs 简历「整理候选人数据 800 余条」
#       - 未命中：真的没有证据
#       设计取舍：**宁可分数保守，也不要假阳性抬高分数**；疑似的情况用独立通道
#       交给人工，做到"分数不虚高"与"信息不丢失"同时满足
#
# ⚠️ 本文件故意不使用模块 docstring（三引号），全部改用 # 注释：
#    粘贴时若丢了注释行不会导致语法错误，但丢了三引号会直接 SyntaxError。
# ============================================================================
import json
import re

# 无法从简历文本中验证的软性特质词（可按需增删）
SOFT_TRAITS = [
    '细心', '责任心', '负责', '耐心', '踏实', '积极', '主动', '乐观', '沟通', '表达',
    '性格', '态度', '抗压', '亲和力', '学习能力', '团队', '协作', '精神', '意识',
    '素养', '上进心', '认真', '敬业', '诚信', '吃苦',
]


def _strip_reasoning(t):
    """去掉混进 text 的推理块：<think>...</think> 以及 <!--dify-deepseek-reasoning--> 之后到 JSON 之前的文字。"""
    t = re.sub(r'<think>.*?</think>', '', t, flags=re.S | re.I)
    t = re.sub(r'<thinking>.*?</thinking>', '', t, flags=re.S | re.I)
    # Dify 的 DeepSeek 插件可能把推理内容放在这个标记之后（没有闭合标签）
    t = re.sub(r'<!--\s*dify-deepseek-reasoning\s*-->.*?(?=\n\s*[\{\[]|\Z)', '', t, flags=re.S)
    return t


def _extract_json(t):
    """括号配平扫描，取出第一个完整的 JSON 对象（比贪婪正则安全得多）。"""
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
    """把模型输出的文本安全解析成 dict（容忍推理块、```json 包裹与前后废话）。"""
    if isinstance(s, (dict, list)):
        return s
    t = _strip_reasoning(str(s or '').strip())
    t = re.sub(r'^```(?:json)?|```$', '', t.strip(), flags=re.M).strip()
    try:
        return json.loads(t)
    except Exception:
        return _extract_json(t)


def _variants(word):
    """把并列写法拆成多个候选词：'人力资源/心理学/管理学专业' -> 三个候选。"""
    parts = re.split(r'[/、，,;；]|或', str(word))
    out = [p.strip() for p in parts if len(p.strip()) >= 2]
    return out or [str(word).strip()]


def _is_soft(word):
    """整条都由软性特质词构成时，判定为无法验证，不参与计分。"""
    parts = [p for p in re.split(r'[与和、及/]', str(word)) if p]
    if not parts:
        return False
    return all(any(s in p for s in SOFT_TRAITS) for p in parts)


def _truthy(v):
    """把模型的 true/false（可能是字符串）统一成布尔。"""
    if isinstance(v, bool):
        return v
    return str(v).strip().lower() in ('true', 'yes', '1', '是', '满足', '符合')


def _strict_hit(word, text):
    """严格命中：关键词（或其并列变体）原样出现在简历文本里。"""
    return any(v.lower() in text for v in _variants(word))


def _bigrams(s):
    """把字符串切成字符二元组集合（先去掉空白）。"""
    s = re.sub(r'\s+', '', str(s))
    if len(s) < 2:
        return set()
    return {s[i:i + 2] for i in range(len(s) - 1)}


def _cjk_only(s):
    """是否全为汉字。"""
    return bool(s) and all('\u4e00' <= c <= '\u9fff' for c in str(s))


def _loose_hit(word, text_bg, threshold=0.6):
    """语序容错匹配：汉字关键词的字符二元组重叠率 >= 阈值，算"疑似命中"。

    解决中文动宾倒装导致的漏判，例如：
        JD 关键词「面试安排」  vs  简历原文「协助安排面试」
        JD 关键词「数据整理」  vs  简历原文「整理候选人数据 800 余条」
    这类情况字面子串匹配必然失败，但语义上就是命中的。

    只对**纯汉字、长度 >= 3** 的关键词启用；英文/含数字的关键词不放宽，
    避免 "Excel" 在 "Excellent" 里被误判这类假阳性。

    注意：疑似命中**不计入分数**（见 main 里的用法），只作为人工复核线索。
    """
    for v in _variants(word):
        v = re.sub(r'\s+', '', v)
        if len(v) < 3 or not _cjk_only(v):
            continue
        vb = _bigrams(v)
        if vb and len(vb & text_bg) / len(vb) >= threshold:
            return True
    return False


def main(jd_json: str, resume_json: str, hard_check_json: str = '') -> dict:
    jd = _load(jd_json)
    cv = _load(resume_json)
    text = json.dumps(cv, ensure_ascii=False).lower()

    # 1) 关键词加权覆盖率（三态判定：命中 / 疑似 / 未命中）
    #    命中   —— 计分
    #    疑似   —— **不计分**，只列出来交人工确认（宁可分数保守，也不要假阳性抬高分数）
    #    未命中 —— 真的没有证据
    kws = jd.get('keywords') or []
    matched, missing, suspect, excluded, got, total = [], [], [], [], 0, 0
    text_bg = _bigrams(text)          # 整份简历的二元组，循环外算一次
    for k in kws:
        word = (k.get('word') if isinstance(k, dict) else str(k)) or ''
        w = (k.get('weight', 3) if isinstance(k, dict) else 3)
        if not word:
            continue
        if _is_soft(word):
            excluded.append(word)
            continue
        total += w
        if _strict_hit(word, text):
            got += w
            matched.append(word)
        elif _loose_hit(word, text_bg):
            suspect.append(word)
        else:
            missing.append(word)
    kw_score = round(got / total * 100) if total else 60

    # 2) 硬性要求命中率
    #    优先用「硬性要求判断」节点的语义判断结果（能识别"本科"满足"大专及以上"等包含关系）；
    #    该输入为空或解析失败时，自动回退到字符串匹配，保证流程不中断。
    hard = jd.get('hard_requirements') or []
    hard_score, hard_mode, hard_detail = None, 'string', []
    hc = _load(hard_check_json)
    if isinstance(hc, dict):
        items = [i for i in (hc.get('items') or []) if isinstance(i, dict)
                 and ('requirement' in i) and ('satisfied' in i)]
        if items:
            ok = sum(1 for i in items if _truthy(i.get('satisfied')))
            hard_score = round(ok / len(items) * 100)
            hard_mode = 'model'
            hard_detail = [{'requirement': i.get('requirement'),
                            'satisfied': _truthy(i.get('satisfied')),
                            'evidence': i.get('evidence', '')} for i in items]
    if hard_score is None:
        hit = 0
        for h in hard:
            toks = [t for t in re.split(r'[，,、；;/\s]+', str(h)) if len(t) >= 2]
            if toks and any(t.lower() in text for t in toks):
                hit += 1
        hard_score = round(hit / len(hard) * 100) if hard else 60

    # 3) 经历厚度
    exp_score = 100 if (cv.get('experiences') or cv.get('projects')) else 40

    # 4) 加权总分（改这里即可调整口径，面试可讲"权重可调"）
    score = round(hard_score * 0.5 + kw_score * 0.3 + exp_score * 0.2)

    # 5) 分档（含边界缓冲：档位附近标注需人工复核，避免上游小波动导致跳档）
    if score >= 77:
        level = '推荐进入面试'
    elif score >= 73:
        level = '推荐进入面试（边界情况，建议人工复核）'
    elif score >= 65:
        level = '待定，需人工复核'
    elif score >= 55:
        level = '待定（边界情况，建议人工复核）'
    else:
        level = '暂不推荐'

    risk = []
    if not cv.get('experiences'):
        risk.append('简历未体现实习/工作经历')
    if hard and hard_score < 50:
        risk.append('硬性要求命中率偏低，需人工核实学历/专业/必备技能')
    if len(missing) >= 5:
        risk.append('缺失关键词较多，需核实技能真实性')
    if hard_mode == 'string' and hard:
        risk.append('硬性要求为字符串匹配结果，建议接入语义判断后复核')
    if suspect:
        risk.append('有 %d 个关键词疑似命中（表述相近但用词不同），'
                    '未计入分数，需人工确认：%s'
                    % (len(suspect), '、'.join(suspect)))

    detail = json.dumps({'hard_score': hard_score, 'keyword_score': kw_score,
                         'experience_score': exp_score, 'weight': '5:3:2',
                         'hard_mode': hard_mode, 'excluded_soft': excluded,
                         'hard_items': hard_detail, 'suspect': suspect,
                         'suspect_note': '疑似命中不计分（避免假阳性抬高分数），仅供人工复核'},
                        ensure_ascii=False)

    return {'score': score, 'level': level, 'matched': matched,
            'missing': missing, 'suspect': suspect, 'risk': risk, 'detail': detail}
