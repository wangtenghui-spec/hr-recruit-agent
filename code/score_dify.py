# ★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★
# ★ 这是【打分代码】。整段复制（第一行到最后一行）粘到 Dify 的「匹配打分」代码节点。  ★
# ★ 不要粘 tests/test_score.py —— 那是回归测试，在命令行跑，粘进来会让节点直接报错。 ★
# ★ 粘之前的自检：文件里必须有 "def main(jd_json" 这一行。                        ★
# ★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★
# ============================================================================
# 节点③ 匹配打分 · Dify 代码节点版 v7（只对"能从简历核验"的条件计分）
#
# 用法：整段复制到 Dify 的「代码」节点（从本文件第一行复制到最后一行）
#   输入变量（均声明为 String）：jd_json、resume_json、hard_check_json
#       - hard_check_json：接「硬性要求判断」LLM 节点的 text 输出；
#         该节点还没建好时，把这一项留空，脚本会自动回退字符串匹配
#   输出变量：score(Number)、level(String)、matched(Array[String])、
#            missing(Array[String])、suspect(Array[String])、risk(Array[String])、
#            detail(String)
# 只依赖标准库 json / re，无需安装任何包。
#
# 版本演进：
#   v2  并列写法容错 + 软性词过滤（只作用于 keywords）
#   v3  hard_score 优先用「硬性要求判断」的语义判断结果，拿不到就回退字符串匹配；
#       detail 增加 hard_mode / hard_items；档位加边界缓冲
#   v4  关键词改为**三态判定**：命中 / 疑似 / 未命中
#       - 疑似 = 汉字关键词字符二元组重叠率 ≥ 0.6 → **不计分**，单独列出交人工确认
#         解决中文动宾倒装漏判：JD「面试安排」vs 简历「协助安排面试」
#   v5  把"软性素质"从 **hard_score** 里也剔除（原来只过滤 keywords，不一致）
#       实测：jd_02 的 14 条硬性要求里有 5 条是软性素质，
#       导致一个专业完全对口的候选人 hard_score 只有 5/14 = 36
#   v6  再把"意愿 / 可用性"类条件（每周到岗天数、实习期时长、能否出差…）也剔除出计分
#       原因为：这类条件**简历里几乎永远不会写**，参与计分等于给每个候选人固定扣分，
#       既不公平也压缩了分数区间。改为列入"面试确认项"（detail.to_confirm）。
#       实测：jd_01+cv_01 原本被 2 条这类条件压掉 22 分（78 → 100）
#
# 核心原则（v4~v6 一以贯之）：
#   **只对"能从简历里客观核验"的条件计分。**
#   核验不到的东西（软性素质、意愿/可用性）不计分，但要**显式列出来**交人工，
#   做到"分数不虚高、信息不丢失"。
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
    # v5 补充：Day 5 实测发现 jd_02 有 5 条软性要求混进了 hard_requirements
    '说服', '目标导向', '业绩压力', '压力', '时间管理', '执行力', '自驱',
    '稳定性', '逻辑思维', '应变', '情商', '服务意识',
]

# 出现这些字样时，说明该条**可能**是客观可核验的硬门槛，不做软性剔除（避免误杀）
HARD_MARKERS = [
    '学历', '专业', '经验', '年限', '证书', '证', '级', '年',
    'Excel', 'Word', 'PPT', 'SQL', 'Python', 'SAP', '软件', '工具', '系统',
    '英语', '日语', '本科', '专科', '硕士', '博士', '在读',
]

# "意愿 / 可用性"类条件：问的是候选人**未来能投入什么**，
# 简历里几乎永远不会写（谁会写"我每周只能来 3 天"），属于面试必问项，不是简历筛选项。
# 让它们参与计分 = 给每一个候选人都固定扣分，既不公平也没有区分度。
TO_CONFIRM_MARKERS = [
    '到岗', '出勤', '每周', '天/周', '天每周',
    '实习期', '可实习', '实习时长', '实习时间', '可连续实习',
    '出差', '加班', '驻场', '外派', '轮班', '倒班',
    '薪资', '期望薪', '到职', '入职时间', '可入职',
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


def _is_soft_hard(req):
    """判断一条**硬性要求**是否其实是"软性素质"。

    为什么要把它们从 hard_score 里剔除：
        简历里几乎永远拿不到"沟通能力强""目标导向""抗压能力"这类证据，
        让它们参与计分会导致**每一个候选人**都在这几条上必然失分，
        分母被稀释、分数失去区分度。

    实测证据（Day 5，jd_02 + cv_08）：
        jd_02 的 hard_requirements 有 14 条，其中 5 条是软性素质，
        一个专业完全对口的候选人只拿到 hard_score = 5/14 = 36。

    保护机制：条目里出现 HARD_MARKERS（学历/专业/经验/证书/工具名等）时**不剔除**，
    避免把"1年以上招聘相关经验"这种真硬门槛误杀。
    """
    s = str(req)
    if any(m in s for m in HARD_MARKERS):
        return False
    return any(t in s for t in SOFT_TRAITS)


def _is_to_confirm(req):
    """判断一条硬性要求是否是"意愿/可用性"类条件（面试确认项，不是简历筛选项）。

    为什么不计分：
        "每周可到岗 4 天以上""实习期不少于 3 个月""能接受出差"这类条件，
        简历里几乎**永远不会写**（没人会写"我每周只能来 3 天"）。
        让它们参与计分，等于给**每一个候选人**都固定扣分——
        既不公平，也把分数区间压缩了，失去区分度。

    实测证据（Day 5，jd_01 + cv_01）：
        jd_01 的 9 条硬性要求里有 2 条是这类（每周到岗、实习期），
        简历里必然"未提及"→ 必然判 false → hard_score 被系统性压低。

    处理方式：剔除出计分，单独列入"面试确认项"，并在报告里作为必须确认的风险提示。
    """
    s = str(req)
    return any(m in s for m in TO_CONFIRM_MARKERS)


def _split_evidence(cv):
    """把简历拆成两个"证据区"，用于 v7 的证据分级。

    强证据区（strong）—— 候选人**实际做过**什么：
        experiences 的公司/岗位/highlights、projects 的名称/角色/技术/highlights
    弱证据区（weak）—— 候选人**声称自己会**什么：
        skills、certificates、self_evaluation

    为什么要分：
        Day 5 实测发现，关键词堆砌的简历（cv_07 赵磊，技能清单列了 30+ 项，
        实习描述只有"完成领导交办的其他工作"）能刷到 **72 分 / 推荐进入面试**——
        因为字面匹配把它"声称会"的词全算成了命中。
        **"声称会" ≠ "做过"**，简历筛选取的是后者。

    返回 (strong_text, weak_text)，均为小写。
    """
    strong = []
    for e in (cv.get('experiences') or []):
        if isinstance(e, dict):
            strong += [str(e.get('company', '')), str(e.get('role', '')),
                       str(e.get('period', ''))]
            strong += [str(h) for h in (e.get('highlights') or [])]
        else:
            strong.append(str(e))
    for p in (cv.get('projects') or []):
        if isinstance(p, dict):
            strong += [str(p.get('name', '')), str(p.get('role', ''))]
            strong += [str(x) for x in (p.get('tech') or [])]
            strong += [str(h) for h in (p.get('highlights') or [])]
        else:
            strong.append(str(p))

    weak = [str(x) for x in (cv.get('skills') or [])]
    weak += [str(x) for x in (cv.get('certificates') or [])]
    weak.append(str(cv.get('self_evaluation', '')))

    return (json.dumps(strong, ensure_ascii=False).lower(),
            json.dumps(weak, ensure_ascii=False).lower())


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

    # 0) 数据可用性前置检查（v8）
    #    背景：Day 5 实测发现，当输入框里填的是**文件路径**而不是文件内容时，
    #    JD解析 和 简历解析 都会返回"未说明 + 空数组"，
    #    而下面那些 `else 60` 的中性兜底默认值会让总分变成一个**看起来很正常**的 56 分
    #    （档位"待定，需人工复核"）——**系统什么都没读到，却给出了一个像模像样的评估**。
    #    这是最危险的一类错误：静默失败 + 貌似合理的输出。
    #    所以：数据不足时**直接短路返回**，给出一个不可能被误认成"评估结论"的档位。
    jd_ok = bool(jd.get('keywords') or jd.get('hard_requirements'))
    edu = cv.get('education') or {}
    degree = str(edu.get('degree') or '').strip()
    cv_ok = bool(cv.get('experiences') or cv.get('projects') or cv.get('skills')
                 or (degree and degree != '未说明'))
    if not jd_ok or not cv_ok:
        miss = []
        if not jd_ok:
            miss.append('岗位要求（JD）')
        if not cv_ok:
            miss.append('简历')
        tip = ('⚠️ 数据不足，无法评分：%s 的解析结果为空，系统没有读到有效内容。'
               '最常见的原因是**把文件路径当内容填进了输入框**'
               '（例如填了 "data\\jd\\jd_01.txt"）——'
               '正确做法是打开那个文件、复制**里面的文字**再粘贴。'
               '也可能是输入框本身留空了。请检查 jd_text / resume_text / jd_json_fixed 三个输入。'
               % '、'.join(miss))
        detail = json.dumps({'data_ok': False, 'missing_inputs': miss,
                             'jd_ok': jd_ok, 'cv_ok': cv_ok,
                             'note': '解析结果为空，未进行打分（避免用兜底默认值造出虚假分数）'},
                            ensure_ascii=False)
        return {'score': 0, 'level': '数据不足，无法评分',
                'matched': [], 'missing': [], 'suspect': [],
                'risk': [tip], 'detail': detail}

    # 1) 关键词加权覆盖率（三态判定 + v7 证据分级）
    #    命中     —— **强证据区**（实习/项目里实际做过）有字面或语序容错命中 → 计分
    #    仅声明   —— 只在**弱证据区**（技能清单/自我评价/"声称会"）命中 → **不计分**
    #                （防关键词堆砌刷分："声称会" ≠ "做过"）
    #    未命中   —— 两处都没有证据
    strong, weak = _split_evidence(cv)
    strong_bg = _bigrams(strong)
    weak_bg = _bigrams(weak)
    kws = jd.get('keywords') or []
    matched, missing, suspect, weak_only, excluded, got, total = [], [], [], [], [], 0, 0
    for k in kws:
        word = (k.get('word') if isinstance(k, dict) else str(k)) or ''
        w = (k.get('weight', 3) if isinstance(k, dict) else 3)
        if not word:
            continue
        if _is_soft(word):
            excluded.append(word)
            continue
        total += w
        if _strict_hit(word, strong) or _loose_hit(word, strong_bg):
            got += w
            matched.append(word)
        elif _strict_hit(word, weak) or _loose_hit(word, weak_bg):
            weak_only.append(word)
            suspect.append(word)
        else:
            missing.append(word)
    kw_score = round(got / total * 100) if total else 60

    # 2) 硬性要求命中率
    #    优先用「硬性要求判断」节点的语义判断结果（能识别"本科"满足"大专及以上"等包含关系）；
    #    该输入为空或解析失败时，自动回退到字符串匹配，保证流程不中断。
    #
    #    v5：先把"软性素质"从硬性要求里剔除，不参与计分。
    #        实测（jd_02 + cv_08）：14 条里有 5 条是软性素质，导致一个专业完全对口的人
    #        只拿到 hard_score = 5/14 = 36。剔除后分母回到 9，分数恢复区分度。
    hard = jd.get('hard_requirements') or []
    soft_hard = [h for h in hard if _is_soft_hard(h)]
    to_confirm = [h for h in hard if _is_to_confirm(h) and not _is_soft_hard(h)]
    scored_hard = [h for h in hard if not _is_soft_hard(h) and not _is_to_confirm(h)]

    hard_score, hard_mode, hard_detail = None, 'string', []
    hc = _load(hard_check_json)
    if isinstance(hc, dict):
        items = [i for i in (hc.get('items') or []) if isinstance(i, dict)
                 and ('requirement' in i) and ('satisfied' in i)]
        # 双保险：即使提示词没拦住，软性素质与"意愿/可用性"条件也绝不进入计分
        kept = [i for i in items
                if not _is_soft_hard(i.get('requirement'))
                and not _is_to_confirm(i.get('requirement'))]
        if kept:
            ok = sum(1 for i in kept if _truthy(i.get('satisfied')))
            hard_score = round(ok / len(kept) * 100)
            hard_mode = 'model'
            hard_detail = [{'requirement': i.get('requirement'),
                            'satisfied': _truthy(i.get('satisfied')),
                            'evidence': i.get('evidence', '')} for i in kept]
    if hard_score is None:
        hit = 0
        for h in scored_hard:
            toks = [t for t in re.split(r'[，,、；;/\s]+', str(h)) if len(t) >= 2]
            if toks and any(t.lower() in text for t in toks):
                hit += 1
        hard_score = round(hit / len(scored_hard) * 100) if scored_hard else 60

    # 3) 经历厚度
    exp_score = 100 if (cv.get('experiences') or cv.get('projects')) else 40

    # 4) 加权总分（改这里即可调整口径，面试可讲"权重可调"）
    score = round(hard_score * 0.5 + kw_score * 0.3 + exp_score * 0.2)

    # 5) 分档
    #    v6 阈值说明：软性素质与"意愿/可用性"条件不再计分之后，分数刻度整体上移，
    #    原来的 55/65/73/77 已不适用。下面这组是用 4 个已知锚点重新标定的：
    #      jd_01+cv_01 完全匹配       → 84 分，应「推荐进入面试」
    #      jd_02+cv_08 资历不足应届生  → 48 分，应「待定」
    #      jd_01+cv_10 完全无关       → 20 分，应「暂不推荐」
    #      jd_01+cv_03 信息残缺       →  8 分，应「暂不推荐」
    #    ⚠️ 这是**初版标定**，跑完 20 组评测后要再用真实数据校准一次。
    if score >= 72:
        level = '推荐进入面试'
    elif score >= 64:
        level = '推荐进入面试（边界情况，建议人工复核）'
    elif score >= 52:
        level = '待定，需人工复核'
    elif score >= 44:
        level = '待定（边界情况，建议人工复核）'
    else:
        level = '暂不推荐'

    risk = []
    if not cv.get('experiences'):
        risk.append('简历未体现实习/工作经历')
    if hard_score < 50:
        risk.append('硬性要求命中率偏低，需人工核实学历/专业/必备技能')
    if len(missing) >= 5:
        risk.append('缺失关键词较多，需核实技能真实性')
    if hard_mode == 'string' and hard:
        risk.append('硬性要求为字符串匹配结果，建议接入语义判断后复核')
    if suspect:
        risk.append('有 %d 个关键词只出现在技能清单/自我评价里、**实习或项目经历中没有佐证**，'
                    '未计入分数，需人工确认是"做过但没写"还是"只列了名"：%s'
                    % (len(suspect), '、'.join(suspect)))
    if len(weak_only) >= 3 and len(cv.get('skills') or []) >= 15:
        risk.append('技能清单共 %d 项、其中 %d 项在经历中无佐证，**疑似关键词堆砌**，'
                    '建议要求候选人逐项举例后再评估'
                    % (len(cv.get('skills') or []), len(weak_only)))
    if soft_hard:
        risk.append('有 %d 条"软性素质"类要求已从硬性要求中剔除、不参与计分，'
                    '建议在面试中考察：%s'
                    % (len(soft_hard), '、'.join(soft_hard)))
    if to_confirm:
        risk.append('有 %d 条"意愿/可用性"条件简历中不会有证据，已改为面试确认项、不参与计分，'
                    '**必须在面试中确认**：%s'
                    % (len(to_confirm), '、'.join(to_confirm)))

    detail = json.dumps({'hard_score': hard_score, 'keyword_score': kw_score,
                         'experience_score': exp_score, 'weight': '5:3:2',
                         'hard_mode': hard_mode, 'excluded_soft': excluded,
                         'hard_items': hard_detail, 'suspect': suspect,
                         'suspect_note': '疑似命中不计分（避免假阳性抬高分数），仅供人工复核',
                         'weak_only': weak_only,
                         'weak_only_note': '只在技能清单/自我评价里声明、经历中无佐证，不计分'
                                           '（防关键词堆砌刷分："声称会" ≠ "做过"）',
                         'excluded_soft_hard': soft_hard,
                         'excluded_soft_hard_note': '软性素质不参与硬性要求计分（简历里拿不到客观证据，'
                                                    '计入会让每个候选人都必然失分）',
                         'to_confirm': to_confirm,
                         'to_confirm_note': '意愿/可用性条件不参与计分，简历中不会有证据，'
                                            '必须在面试中确认',
                         'scored_hard_count': len(scored_hard)},
                        ensure_ascii=False)

    return {'score': score, 'level': level, 'matched': matched,
            'missing': missing, 'suspect': suspect, 'risk': risk, 'detail': detail}
