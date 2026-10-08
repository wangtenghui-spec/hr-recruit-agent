# -*- coding: utf-8 -*-
"""校验 prompts/节点提示词汇总.txt 与 prompts/*.md 是否完全一致。

这是一个**独立的反向校验**：生成脚本说"我写对了"不算数，
这里重新把 txt 按小节切开，逐段和 md 里的提示词比对（忽略空白与 markdown 强调符号），
任何一处不一致都会打印出首个差异的位置和上下文。

用法：python tools/verify_prompts.py
退出码：0 = 全部一致，1 = 存在不一致
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
TXT = os.path.join(PROMPTS, '节点提示词汇总.txt')

NODES = [
    ('jd_parse.md', '节点① JD解析'),
    ('resume_parse.md', '节点② 简历解析'),
    ('hard_check.md', '节点③ 硬性要求判断'),
    ('questions.md', '节点⑤ 面试问题生成'),
    ('report.md', '节点⑥ 报告生成'),
]


def norm(s):
    s = s.replace('**', '')
    s = re.sub(r'`([^`]*)`', r'\1', s)
    return re.sub(r'\s+', '', s)


def md_block(path, role):
    t = io.open(path, encoding='utf-8').read()
    m = re.search(r'^##\s*' + role + r'\s*$(.*?)^```\n(.*?)^```', t, re.M | re.S)
    if not m:
        raise SystemExit('❌ %s 里找不到「%s」的代码块' % (path, role))
    return m.group(2).strip()


def main():
    txt = io.open(TXT, encoding='utf-8-sig').read()
    lines = txt.split('\n')

    # 按 "# <显示名> —— <role> ↓" 定位每一小节的正文范围
    sections = []
    for md_name, disp in NODES:
        for role in ('系统提示词', '用户提示词'):
            head = '# %s —— %s ↓' % (disp, role)
            idx = next((i for i, l in enumerate(lines) if l.startswith(head)), None)
            if idx is None:
                print('❌ txt 里找不到小节：', head)
                return 1
            body = []
            for l in lines[idx + 2:]:          # 跳过标题和 #### 分隔线
                if l.startswith('####') or l.startswith('===='):
                    break
                body.append(l)
            sections.append((md_name, disp, role, '\n'.join(body).strip()))

    ok = True
    for md_name, disp, role, body in sections:
        expected = md_block(os.path.join(PROMPTS, md_name), role)
        a, b = norm(body), norm(expected)
        same = a == b
        ok = ok and same
        print(('✅ 一致    ' if same else '❌ 不一致  ') + '%s · %s' % (disp, role))
        if not same:
            print('    txt %d 字符 / md %d 字符' % (len(a), len(b)))
            for i in range(min(len(a), len(b))):
                if a[i] != b[i]:
                    print('    首个差异在第 %d 字符：' % i)
                    print('      txt:', a[max(0, i - 30):i + 30])
                    print('      md :', b[max(0, i - 30):i + 30])
                    break
            else:
                print('    一个是另一个的前缀，长度不同')

    print()
    print('全部一致 ✅（txt 与 md 完全同步）' if ok
          else '存在不一致 ❌ —— 请重新运行 tools/gen_paste_file.py')
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
