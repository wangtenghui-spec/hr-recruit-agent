# -*- coding: utf-8 -*-
"""生成「无占位符版」的用户提示词，从根上杜绝粘贴残留。

为什么需要这个文件：
    原来的用户提示词里写着 {{JD解析 / text}} 这样的**占位符**。
    但粘贴时如果只选中了花括号里面的内容（留下一个 {），再插入变量胶囊，
    就会变成 {{{#节点ID.变量名#}} —— 前面多一个花括号。
    实测 5 个 LLM 节点的用户提示词**全部**出现了这个残留，
    其中报告生成的「疑似命中」那一处更被截断成了孤零零的 {{，
    导致 suspect 变量完全失效。

解决办法：
    把 {{X / Y}} 全部替换成 «插入变量：X / Y»。
    标记里**没有花括号**，所以不可能留下多余的花括号。
    整行选中替换即可，或者选中 «» 之间的内容再插变量也行。

用法（在 hr-recruit-agent 目录下）：
    python tools/gen_placeholder_free.py
"""
import io
import os
import re
import sys
# --- 中文 Windows 兼容：输出被重定向时 stdout 会退化成 GBK，emoji 会抛 UnicodeEncodeError ---
try:
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
except Exception:
    pass


HERE = os.path.dirname(os.path.abspath(__file__))
PROMPTS = os.path.join(os.path.dirname(HERE), 'prompts')
OUT = os.path.join(PROMPTS, '用户提示词汇总.txt')

NODES = [
    ('jd_parse.md', '节点① JD解析'),
    ('resume_parse.md', '节点② 简历解析'),
    ('hard_check.md', '节点③ 硬性要求判断'),
    ('questions.md', '节点⑤ 面试问题生成'),
    ('report.md', '节点⑥ 报告生成'),
]

VAR = re.compile(r'\{\{\s*([^{}]+?)\s*\}\}')


def extract_user_prompt(md_path):
    t = io.open(md_path, encoding='utf-8').read()
    m = re.search(r'^##\s*用户提示词\s*$(.*?)^```\n(.*?)^```', t, re.M | re.S)
    if not m:
        raise SystemExit('❌ %s 里找不到「用户提示词」代码块' % md_path)
    return m.group(2).rstrip('\n')


def to_marker(text):
    """{{节点 / 变量}} → «插入变量：节点 / 变量»（去掉所有花括号）"""
    text = text.replace('**', '')
    text = re.sub(r'`([^`]*)`', r'\1', text)
    return VAR.sub(lambda m: '«插入变量：%s»' % m.group(1).strip(), text)


BAR = '=' * 80
HASHBAR = '#' * 80
lines = [
    BAR,
    ' 用户提示词 · 无占位符版（推荐用这个，不会再出现花括号残留）',
    '',
    ' ⚠️ 本文件由 tools/gen_placeholder_free.py 自动生成，不要手改。',
    '',
    ' 【为什么要有这个版本】',
    '   原来的用户提示词里是 {{JD解析 / text}} 这种占位符。粘贴时如果只选中了',
    '   花括号里面的内容（留下一个 {），再插入变量胶囊，就会变成',
    '       {{{#节点ID.变量名#}}     ← 前面多一个花括号',
    '   实测 5 个 LLM 节点的用户提示词全都出现了这个残留，其中一处还被截断成',
    '   孤零零的 {{，导致变量彻底失效。',
    '',
    ' 【用法】',
    '   1. 整段复制本小节内容，粘到对应节点的「用户提示词」框（覆盖原内容）',
    '   2. 找到 «插入变量：X / Y» 这样的标记',
    '   3. 把光标放进去，**整行选中**（或选中 «» 之间的全部内容）',
    '   4. 用变量选择器插入对应的变量 —— 标记会被替换成蓝色胶囊',
    '   5. 标记里没有花括号，所以**不可能留下多余的花括号**',
    '',
    ' 【验收】',
    '   粘完检查：框里再也搜不到「{{」和「«」这两个符号，只有蓝色胶囊。',
    BAR,
    '',
]

for md_name, disp in NODES:
    body = to_marker(extract_user_prompt(os.path.join(PROMPTS, md_name)))
    n = len(VAR.findall(extract_user_prompt(os.path.join(PROMPTS, md_name))))
    lines += [HASHBAR,
              '# %s —— 用户提示词（需要插入 %d 个变量）   （来源：prompts/%s）' % (disp, n, md_name),
              HASHBAR, '',
              body, '', '']

lines += [
    BAR,
    ' 系统提示词不需要用这个版本（系统提示词里没有变量，直接整段复制即可，',
    ' 见 prompts/节点提示词汇总.txt）。',
    BAR,
    '',
]

txt = '\n'.join(lines)
with io.open(OUT, 'w', encoding='utf-8-sig', newline='\r\n') as f:
    f.write(txt)

print('✅ 已生成', OUT)
for md_name, disp in NODES:
    b = extract_user_prompt(os.path.join(PROMPTS, md_name))
    print('   %-16s 需插入 %d 个变量' % (disp, len(VAR.findall(b))))
print()
print('   文件共 %d 字符' % len(txt))
