# 节点 · 岗位要求路由（代码节点）
#
# 作用：让「岗位要求（JD 的结构化解析结果）」可以被**固化复用**。
#
# 为什么需要它：
#   同一个岗位连跑多次，JD解析 会给出**不同的关键词表**（实测 15 个词里只有 8 个稳定），
#   导致打分分母在变 → 不同候选人不在同一把尺子上量 → 分数不可比、档位来回跳。
#
#   而「岗位要求」是**岗位的属性，与候选人无关**，本不该每个候选人跑一次就重新抽签。
#
# 用法：
#   1. 用户输入 节点加一个可选变量 jd_json_fixed（段落文本，非必填）
#   2. 本节点放在 JD解析 之后：
#        jd_json_fixed  <- 用户输入 / jd_json_fixed
#        jd_json_parsed <- JD解析 / text
#   3. 「硬性要求判断」和「匹配打分」的 JD 输入都改成读本节点的 jd_json
#      （而不是直接读 JD解析/text）
#
# 效果：
#   - jd_json_fixed 有内容（有效的 JD JSON）→ 原样使用，**逐字不变**
#   - jd_json_fixed 为空或不是合法 JSON → 自动回退用 JD解析 的结果，流程不中断
#
#   于是"每个岗位解析一次、固化下来、所有候选人复用"就成为可能，
#   跟真实 ATS 系统的做法一致。
#
# 输入变量（均声明为 String）：
#   jd_json_fixed   —— 用户输入 / jd_json_fixed（可为空）
#   jd_json_parsed  —— JD解析 / text
# 输出变量：
#   jd_json   (String) —— 最终使用的 JD JSON
#   jd_source (String) —— "fixed" 或 "parsed"，便于核对当前用的是哪一份
import json
import re


def _extract_json(t):
    """括号配平扫描，取出第一个完整的 JSON 对象（容忍前后废话与 ```json 包裹）。"""
    t = re.sub(r'^```(?:json)?|```$', '', (t or '').strip(), flags=re.M)
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
    return None


def main(jd_json_fixed: str = '', jd_json_parsed: str = '') -> dict:
    fixed = (jd_json_fixed or '').strip()

    # 固化值必须是一个**能解析出内容的** JD JSON，否则视为没填，自动回退
    if fixed:
        obj = _extract_json(fixed)
        # 至少要有关键词或硬性要求，才算一份可用的 JD 解析结果
        if isinstance(obj, dict) and (obj.get('keywords') or obj.get('hard_requirements')):
            return {'jd_json': json.dumps(obj, ensure_ascii=False), 'jd_source': 'fixed'}

    return {'jd_json': jd_json_parsed or '', 'jd_source': 'parsed'}
