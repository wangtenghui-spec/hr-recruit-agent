"""HR 招聘助手 · Streamlit 版本地界面

和标准库版（server.py）功能一样：填 JD + 简历 + 岗位档案 → 出评估报告。
区别是这版用 Streamlit，代码短很多，Markdown 报告（含表格）由 Streamlit 原生渲染。

⚠️ 必须在装了 streamlit 的解释器里跑，而且要这样启动：
       <python路径> -m streamlit run app_streamlit.py
    不要用 python app_streamlit.py（那样不会起服务）。
    直接双击「启动界面-Streamlit.bat」最省事，它会自动找装了 streamlit 的解释器。

为什么用 urllib 而不是 requests 调 Dify：
    只依赖标准库调接口，就不用管这个 venv 里 requests 是哪个版本。
"""
import csv
import io
import json
import os
import time
import urllib.error
import urllib.request

import streamlit as st
import sys
# --- 中文 Windows 兼容：输出被重定向时 stdout 会退化成 GBK，emoji 会抛 UnicodeEncodeError ---
try:
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
except Exception:
    pass


HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
CONFIG_PATH = os.path.join(HERE, 'config.json')
RUN_LIST = os.path.join(ROOT, 'test', '运行清单.csv')

st.set_page_config(page_title='HR 招聘助手 · 候选人评估', page_icon='📋', layout='wide')


# ---------------------------------------------------------------- 配置
def load_config():
    cfg = {'api_base': 'http://localhost/v1', 'api_key': ''}
    if os.path.exists(CONFIG_PATH):
        try:
            # utf-8-sig：记事本另存可能带 BOM，用 utf-8 读会报错，api_key 就变空了
            with io.open(CONFIG_PATH, encoding='utf-8-sig') as f:
                cfg.update(json.load(f))
        except Exception as e:
            st.sidebar.error('config.json 读取失败：%s: %s' % (type(e).__name__, e))
    if os.environ.get('DIFY_API_KEY'):
        cfg['api_key'] = os.environ['DIFY_API_KEY']
    return cfg


CFG = load_config()


# ---------------------------------------------------------------- 调 Dify
def call_dify(jd_text, resume_text, jd_json_fixed):
    url = CFG['api_base'].rstrip('/') + '/workflows/run'
    inputs = {'jd_text': jd_text, 'resume_text': resume_text}
    if jd_json_fixed and jd_json_fixed.strip():
        inputs['jd_json_fixed'] = jd_json_fixed
    payload = json.dumps({'inputs': inputs, 'response_mode': 'blocking',
                          'user': 'streamlit-web'}, ensure_ascii=False).encode('utf-8')
    req = urllib.request.Request(url, data=payload, method='POST')
    req.add_header('Authorization', 'Bearer ' + CFG['api_key'])
    req.add_header('Content-Type', 'application/json')
    try:
        with urllib.request.urlopen(req, timeout=300) as resp:
            return json.loads(resp.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        body = e.read().decode('utf-8', 'replace')
        try:
            detail = json.loads(body)
        except Exception:
            detail = {'message': body[:500]}
        if e.code == 401:
            raise RuntimeError('HTTP 401：密钥不对，或者应用还没发布。'
                               '去 Dify 点「发布更新」，再确认 config.json 里的 api_key。')
        if e.code == 404:
            raise RuntimeError('HTTP 404：应用没有已发布版本。去 Dify 点「发布更新」。')
        raise RuntimeError('Dify 返回 HTTP %s：%s' % (e.code, json.dumps(detail, ensure_ascii=False)))
    except urllib.error.URLError as e:
        raise RuntimeError('连不上 Dify（%s）。确认 Dify 已启动：双击 C:\\agent\\打开管理界面.bat 选 3'
                           % e.reason)


MOCK = {
    'report_result': 86, 'level': '推荐进入面试',
    'elapsed_time': 2.0, 'total_tokens': 15905, 'total_steps': 9,
    'outputs': {
        'report_result': 86, 'level': '推荐进入面试',
        'detail': json.dumps({'hard_score': 100, 'keyword_score': 55, 'experience_score': 100,
                              'weight': '5:3:2', 'hard_mode': 'model', 'scored_hard_count': 4,
                              'to_confirm': ['每周可到岗 4 天以上', '实习期不少于 3 个月']},
                             ensure_ascii=False),
        'suspect': ['简历筛选', '电话初筛', 'Word', 'PPT'],
        'report': ('# 候选人评估报告\n\n'
                   '## 一、结论速览\n'
                   '- 应聘岗位：人力资源实习生（招聘方向）\n'
                   '- 综合得分：86/100（档位：推荐进入面试）\n'
                   '- 分项得分：硬性要求 100｜关键词匹配 55｜经历完整度 100（权重 5:3:2）\n\n'
                   '## 二、硬性要求核对\n\n'
                   '| 硬性要求 | 是否满足 | 证据（简历原文） |\n|---|---|---|\n'
                   '| 大专及以上在读 | 是 | 某大学 人力资源管理 本科 2023.09-2027.06 |\n'
                   '| 熟练使用 Excel | 是 | 使用 Excel 整理候选人台账，每周输出招聘周报 |\n\n'
                   '> 这是演示模式返回的**样例报告**，内容被截短了。真实模式会返回完整六章节。\n'),
    },
}


# ---------------------------------------------------------------- 载入示例
def read_file(rel):
    p = os.path.join(ROOT, rel)
    if not os.path.exists(p):
        return None
    return io.open(p, encoding='utf-8').read()


def load_run_list():
    if not os.path.exists(RUN_LIST):
        return []
    with io.open(RUN_LIST, encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))


def fill_case(row):
    jd = read_file(os.path.join('data', 'jd', (row.get('JD文件') or '') + '.txt'))
    cv = read_file(os.path.join('data', 'resume', (row.get('CV文件') or '') + '.txt'))
    fx = ''
    if (row.get('档案文件') or '').strip():
        fx = read_file(os.path.join('data', 'jd_fixed', row['档案文件'].strip())) or ''
    st.session_state.jd_text = jd or ''
    st.session_state.cv_text = cv or ''
    st.session_state.fx_text = fx


# ---------------------------------------------------------------- 侧边栏
with st.sidebar:
    st.header('设置')

    mock = st.checkbox('演示模式（不调 Dify）', value=False,
                       help='勾上之后不调用 Dify，直接返回一份样例报告。用来演示界面长什么样。')
    st.caption('Dify 地址：`%s`' % CFG['api_base'])
    if CFG['api_key']:
        st.caption('API 密钥：✅ 已配置（%s……）' % CFG['api_key'][:12])
    else:
        st.caption('API 密钥：❌ 未配置')
        st.info('把密钥填进 `tools\\local_web\\config.json` 的 `api_key`，'
                '改完记得 **Ctrl+S 保存**。', icon='⚠️')

    st.divider()
    st.header('快速载入')
    st.caption('直接读 `test\\运行清单.csv`，把某一组的三个输入填好')

    rows = load_run_list()
    if rows:
        labels = ['%s  %s' % (r['用例编号'], r['场景']) for r in rows]
        pick = st.selectbox('选一个用例', labels, index=0)
        idx = labels.index(pick)
        row = rows[idx]
        st.caption('JD：`%s`　简历：`%s`　档案：`%s`'
                   % (row.get('JD文件'), row.get('CV文件'), row.get('档案文件') or '（未固化）'))
        if st.button('载入这一组数据', use_container_width=True):
            fill_case(row)
            st.rerun()

        if st.button('载入用例 01（完全匹配）', use_container_width=True):
            fill_case(rows[0])
            st.rerun()
    else:
        st.warning('找不到 `test\\运行清单.csv`')

    st.divider()
    st.caption('停止服务：在这个窗口按 Ctrl+C')


# ---------------------------------------------------------------- 主体
st.title('📋 HR 招聘助手 · 候选人评估')
st.caption('输入一份岗位 JD 和一份简历，输出带评分、证据和面试题的评估报告　｜　'
           '工作流 9 个节点，约 35~60 秒')

c1, c2 = st.columns(2)
jd_text = c1.text_area('① 岗位 JD（原文）', key='jd_text', height=280,
                       placeholder='把岗位 JD 的完整内容粘贴到这里…')
c1.caption('%d 字' % len(jd_text))

cv_text = c2.text_area('② 候选人简历（原文）', key='cv_text', height=280,
                       placeholder='把简历的完整内容粘贴到这里…')
c2.caption('%d 字' % len(cv_text))

with st.expander('③ 岗位档案（固化版，可选）—— 填了就保证同一岗位的打分分母恒定'):
    fx_text = st.text_area('岗位档案', key='fx_text', height=160,
                           label_visibility='collapsed',
                           placeholder='粘贴 data\\jd_fixed\\jd_01.json 的全部内容。'
                                       '留空则每次现场解析（分母会变）。')
    st.caption('%d 字　%s' % (len(fx_text),
                             '（留空 = 现场解析）' if not fx_text.strip() else '（固化生效）'))

left, right = st.columns([1, 3])
run = left.button('🚀 开始评估', type='primary', use_container_width=True)
if right.button('清空', use_container_width=False):
    st.session_state.jd_text = ''
    st.session_state.cv_text = ''
    st.session_state.fx_text = ''
    st.session_state.pop('result', None)
    st.rerun()

# 短输入提醒（上次就是有人把"文件路径"填进来了）
short = [n for n, v in (('JD', jd_text), ('简历', cv_text)) if 0 < len(v.strip()) < 60]
if short:
    st.warning('⚠️ %s 的内容不到 60 字，看起来像是把【文件路径】填进来了。\n\n'
               '**要填的是文件里的内容**，不是路径。自检：JD 那格应该有几百字。'
               % '、'.join(short), icon='⚠️')


# ---------------------------------------------------------------- 执行
if run:
    if not jd_text.strip() or not cv_text.strip():
        st.error('请先填写「岗位 JD」和「简历原文」。')
    else:
        t0 = time.time()
        try:
            if mock:
                with st.spinner('演示模式：正在生成样例报告…'):
                    time.sleep(2)
                st.session_state.result = dict(MOCK, mock=True)
            else:
                if not CFG['api_key']:
                    raise RuntimeError('还没有配置 Dify API 密钥。'
                                       '请编辑 tools\\local_web\\config.json 的 api_key（记得 Ctrl+S 保存）。')
                with st.spinner('正在调用工作流：解析 JD → 解析简历 → 硬性要求判断 → '
                                '打分 → 出题 → 出报告…（约 35~60 秒）'):
                    r = call_dify(jd_text, cv_text, fx_text)
                d = (r or {}).get('data') or {}
                if d.get('status') != 'succeeded':
                    raise RuntimeError('工作流没跑成功（status=%s）：%s'
                                       % (d.get('status'), d.get('error') or '无错误信息'))
                st.session_state.result = {
                    'outputs': d.get('outputs') or {},
                    'elapsed_time': d.get('elapsed_time'),
                    'total_tokens': d.get('total_tokens'),
                    'total_steps': d.get('total_steps'),
                    'workflow_run_id': r.get('workflow_run_id'),
                }
        except RuntimeError as e:
            st.session_state.pop('result', None)
            st.error('评估失败：%s' % e)
        except Exception as e:
            st.session_state.pop('result', None)
            st.error('意外错误：%s: %s' % (type(e).__name__, e))
        finally:
            st.session_state.last_seconds = time.time() - t0


# ---------------------------------------------------------------- 结果
res = st.session_state.get('result')
if res:
    o = res.get('outputs') or {}
    score = o.get('report_result', o.get('score', '—'))
    level = o.get('level', '—')

    st.divider()

    if res.get('mock'):
        st.info('演示模式的结果（没有真的调用 Dify）', icon='🧪')

    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric('综合得分', '%s / 100' % score)
    m2.metric('档位', level)
    m3.metric('耗时', ('%.1f 秒' % res['elapsed_time']) if res.get('elapsed_time') else '—')
    m4.metric('消耗', ('%s tokens' % res['total_tokens']) if res.get('total_tokens') else '—')
    m5.metric('节点数', res.get('total_steps', '—'))

    if isinstance(level, str):
        if '数据不足' in level:
            st.error('档位是「数据不足，无法评分」——**说明输入没填对**，不是候选人不行。'
                     '最常见的原因是填了文件路径而不是文件内容。')
        elif '暂不推荐' in level:
            st.error('档位：**%s**' % level)
        elif '边界' in level:
            st.warning('档位：**%s**' % level)
        elif '推荐进入面试' in level:
            st.success('档位：**%s**' % level)
        else:
            st.info('档位：**%s**' % level)

    rep = o.get('report') or ''
    if rep:
        # 注意：这里原本用的是 st.tabs。
        # 但选项卡组件在"结果区从无到有"这种大幅重绘时，偶尔会和浏览器插件
        # （翻译 / 划词 / 广告拦截类）打架，报：
        #   NotFoundError: Failed to execute 'removeChild' on 'Node'
        # 换成 st.expander（折叠面板）后没有这个问题，而且不占屏幕、可以全展开。
        with st.expander('📄 评估报告', expanded=True):
            st.markdown(rep)
            st.download_button('下载报告（Markdown）', rep.encode('utf-8'),
                               file_name='候选人评估报告.md', mime='text/markdown')

        with st.expander('🔍 打分明细（detail）'):
            det = o.get('detail')
            if det:
                try:
                    st.json(json.loads(det))
                except Exception:
                    st.code(det, language='json')
            else:
                st.caption('上游没有返回 detail')

        with st.expander('🧩 结构化字段'):
            cols = st.columns(2)
            with cols[0]:
                st.markdown('**命中关键词**')
                st.write(o.get('matched') or [])
                st.markdown('**疑似命中（不计分，需人工确认）**')
                st.write(o.get('suspect') or [])
            with cols[1]:
                st.markdown('**缺口关键词**')
                st.write(o.get('missing') or [])
                st.markdown('**风险提示**')
                for x in (o.get('risk') or []):
                    st.markdown('- %s' % x)
    else:
        st.warning('上游没有返回 report 字段')
else:
    st.info('左侧可以「载入用例 01」，或者自己粘贴 JD 和简历，然后点「开始评估」。')
