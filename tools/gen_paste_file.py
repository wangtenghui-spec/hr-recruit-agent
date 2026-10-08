# -*- coding: utf-8 -*-
"""从 prompts/*.md 生成 prompts/节点提示词汇总.txt

单一来源原则：**md 是唯一真相，txt 是派生产物**。
生成时剥掉 markdown 强调符号（** 加粗、` 行内代码），
保证粘进 Dify 的是干净文本，不会把星号和反引号一起喂给模型。

为什么要有这个脚本：
    我（AI）第一次是手写 txt 的，结果和 md 出现了 4 处不一致
    （文本框了规则、占位符写法不同、加粗符号没剥干净）。
    手写两遍必然不一致 —— 所以改成脚本生成，并且写了一个校验脚本
    反过来比对 txt 和 md，确保 8 个小节完全一致。

用法（在本目录下）：
    python tools/gen_paste_file.py
然后跑一下校验：
    python tools/verify_prompts.py
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
OUT = os.path.join(PROMPTS, '节点提示词汇总.txt')

# (md 文件名, 显示名) —— 顺序 = 节点在画布上的先后顺序
NODES = [
    ('jd_parse.md', '节点① JD解析'),
    ('resume_parse.md', '节点② 简历解析'),
    ('hard_check.md', '节点③ 硬性要求判断'),
    ('questions.md', '节点⑤ 面试问题生成'),
    ('report.md', '节点⑥ 报告生成'),
]


def extract(md_path):
    """按 '## 系统提示词' / '## 用户提示词' 标题取紧随其后的 ``` 代码块。"""
    t = io.open(md_path, encoding='utf-8').read()
    out = {}
    for role in ('系统提示词', '用户提示词'):
        m = re.search(r'^##\s*' + role + r'\s*$(.*?)^```\n(.*?)^```', t, re.M | re.S)
        if not m:
            raise SystemExit('❌ %s 里找不到「%s」的代码块' % (md_path, role))
        out[role] = m.group(2).rstrip('\n')
    return out


def clean(text):
    """剥掉 markdown 强调：**加粗**、`行内代码`。"""
    text = text.replace('**', '')
    text = re.sub(r'`([^`]*)`', r'\1', text)
    return text


BAR = '=' * 80
HASHBAR = '#' * 80

lines = [
    BAR,
    ' HR 招聘助手 Agent · 提示词粘贴清单（共 %d 个节点 / %d 个小节）'
    % (len(NODES), len(NODES) * 2),
    '',
    ' ⚠️ 本文件由 tools/gen_paste_file.py 自动生成，不要手改本文件！',
    '    要改提示词，请改 prompts/ 下对应的 md 文档，然后重新运行生成脚本。',
    '',
    ' 用法：用记事本打开本文件，找到对应节点的小节，从「系统提示词 ↓」的下一行开始',
    '       整段选中复制，粘到 Dify 节点里，覆盖原来的内容。',
    ' 注意：带 {{...}} 的地方必须用 Dify 的【变量选择器】插入，不要手打！',
    '       手打的只是普通文字，不会变成蓝色小方块，也不会被替换。',
    BAR,
    '',
]

for md_name, disp in NODES:
    blocks = extract(os.path.join(PROMPTS, md_name))
    for role in ('系统提示词', '用户提示词'):
        lines += [HASHBAR,
                  '# %s —— %s ↓   （来源：prompts/%s）' % (disp, role, md_name),
                  HASHBAR, '',
                  clean(blocks[role]), '', '']

lines += [
    BAR,
    ' 代码节点（节点④ 匹配打分）不需要从这里复制',
    ' —— 请直接打开：',
    '    C:\\agent\\hr-recruit-agent\\code\\score_dify.py',
    '    从第 1 行到最后一行整段复制，粘到代码节点里，覆盖原内容。',
    BAR,
    '',
]

txt = '\n'.join(lines)
with io.open(OUT, 'w', encoding='utf-8-sig', newline='\r\n') as f:
    f.write(txt)

print('✅ 已生成', OUT)
print('   共 %d 小节，%d 字符' % (len(NODES) * 2, len(txt)))
for md_name, disp in NODES:
    b = extract(os.path.join(PROMPTS, md_name))
    print('   %-18s 系统 %4d 字 / 用户 %4d 字'
          % (md_name, len(clean(b['系统提示词'])), len(clean(b['用户提示词']))))
