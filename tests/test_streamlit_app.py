# -*- coding: utf-8 -*-
r"""用 Streamlit 官方的 AppTest 真正执行一遍 app_streamlit.py，验证逻辑没问题。

为什么需要这个：
    `streamlit run` 起来之后，只有浏览器建立 websocket 会话时才会执行脚本。
    所以"页面能打开"并不能证明脚本没报错。
    AppTest 可以在没有浏览器的情况下跑脚本，并拿到 exception 列表。

用装了 streamlit 的解释器跑（见 tools\local_web\启动界面-Streamlit.bat 里那两个路径）：
    <venv 路径>\Scripts\python.exe tools\_test_streamlit_app.py
"""
import sys

from streamlit.testing.v1 import AppTest
# --- 中文 Windows 兼容：输出被重定向时 stdout 会退化成 GBK，emoji 会抛 UnicodeEncodeError ---
try:
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
except Exception:
    pass


APP = r'C:\agent\hr-recruit-agent\tools\local_web\app_streamlit.py'
FAIL = []


def check(name, cond, extra=''):
    print(('  ✅ ' if cond else '  ❌ ') + name + (('   → ' + str(extra)) if extra else ''))
    if not cond:
        FAIL.append(name)


def ss(at, key, default=None):
    """AppTest 的 session_state 不支持 .get()，只能下标访问，这里包一层。"""
    try:
        return at.session_state[key]
    except Exception:
        return default


def exc_of(at):
    return [str(e.value)[:200] for e in at.exception]


def btn(at, kw):
    return next((b for b in at.button if kw in b.label), None)


print('=' * 74)
print('一、脚本能不能跑起来（首次加载）')
print('=' * 74)
at = AppTest.from_file(APP, default_timeout=60)
at.run()

check('没有抛异常', len(at.exception) == 0, exc_of(at))
check('标题渲染了', any('HR 招聘助手' in str(t.value) for t in at.title))
check('有 3 个输入框（JD / 简历 / 岗位档案）', len(at.text_area) == 3, '实际 %d 个' % len(at.text_area))
check('侧边栏有"演示模式"勾选框',
      any('演示' in c.label for c in at.checkbox), [c.label for c in at.checkbox])
check('有"载入这一组数据"按钮', btn(at, '载入这一组数据') is not None,
      [b.label for b in at.button])

print()
print('=' * 74)
print('二、快速载入用例 01（读 运行清单.csv + 三个数据文件）')
print('=' * 74)
b = btn(at, '载入用例 01') or btn(at, '载入这一组数据')
check('找到载入按钮', b is not None)
if b is not None:
    b.click().run()
    check('载入后没抛异常', len(at.exception) == 0, exc_of(at))
    jd = ss(at, 'jd_text', '') or ''
    cv = ss(at, 'cv_text', '') or ''
    fx = ss(at, 'fx_text', '') or ''
    check('jd_text 有内容（%d 字）' % len(jd), len(jd) > 200)
    check('cv_text 有内容（%d 字）' % len(cv), len(cv) > 200)
    check('fx_text 有内容（%d 字）' % len(fx), len(fx) > 500)

print()
print('=' * 74)
print('三、演示模式跑一次，看结果区渲染是否正常')
print('=' * 74)
at2 = AppTest.from_file(APP, default_timeout=60)
at2.run()
at2.checkbox[0].check().run()
check('勾选演示模式后没抛异常', len(at2.exception) == 0, exc_of(at2))

b2 = btn(at2, '载入用例 01') or btn(at2, '载入这一组数据')
b2.click().run()
check('载入数据后没抛异常', len(at2.exception) == 0, exc_of(at2))

go = btn(at2, '开始评估')
check('找到"开始评估"按钮', go is not None)
if go is not None:
    go.click().run()
    check('评估后没抛异常', len(at2.exception) == 0, exc_of(at2))
    res = ss(at2, 'result')
    check('session_state 里有 result', bool(res))
    if res:
        o = res.get('outputs') or {}
        check('返回了 report 字段', bool(o.get('report')))
        check('得分为 86', o.get('report_result') == 86, o.get('report_result'))
        check('档位是"推荐进入面试"', o.get('level') == '推荐进入面试', o.get('level'))
    check('渲染出了 metric（得分/档位/耗时…）', len(at2.metric) >= 4,
          '实际 %d 个' % len(at2.metric))
    check('报告用 st.markdown 渲染（表格能原生显示）',
          any('候选人评估报告' in str(m.value) for m in at2.markdown))
    check('有折叠面板（报告/明细/结构化字段）', len(at2.expander) >= 3,
          '实际 %d 个' % len(at2.expander))
    check('有下载报告的按钮', len(at2.get('download_button')) >= 1,
          '实际 %d 个' % len(at2.get('download_button')))

print()
print('=' * 74)
print('四、短输入时有没有给出警告（防"填成路径"）')
print('=' * 74)
at3 = AppTest.from_file(APP, default_timeout=30)
at3.run()
at3.text_area[0].set_value('data\\jd\\jd_01.txt').run()
check('填路径后出现警告',
      any('文件路径' in str(w.value) for w in at3.warning),
      [str(w.value)[:80] for w in at3.warning])

print()
print('=' * 74)
if FAIL:
    print('❌ 有 %d 项失败：' % len(FAIL))
    for x in FAIL:
        print('   -', x)
    sys.exit(1)
print('全部通过 ✅')
sys.exit(0)
