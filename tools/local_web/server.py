# -*- coding: utf-8 -*-
"""HR 招聘助手 · 本地网页界面（只用 Python 标准库，不需要装任何包）

为什么用标准库：
    这台机器上 flask / streamlit / fastapi / gradio 都没装，
    而标准库的 http.server + urllib.request 足够做一个本地网页 + 调 Dify API 的代理。
    不用联网装包，也不会有版本冲突。

它做什么：
    1. 提供一个本地网页（http://127.0.0.1:8000）
    2. 网页上填「岗位 JD」和「简历原文」（可选填「岗位档案」）
    3. 后端把请求转发给 Dify 的 /v1/workflows/run（blocking 模式）
    4. 把返回的 Markdown 报告渲染出来

为什么需要一个后端代理，不能网页直接调 Dify：
    浏览器的同源策略（CORS）会拦住跨域请求。所以由本脚本做中转。

用法：
    python server.py              # 正常模式：调真实的 Dify
    python server.py --mock       # 演示模式：不调 Dify，返回一份样例报告
    python server.py --port 8080  # 换端口

配置：
    同目录下的 config.json：
        {"api_base": "http://localhost/v1", "api_key": "app-xxxxxxxx"}
    ⚠️ api_key 不要提交到 GitHub。可以改用环境变量 DIFY_API_KEY。
"""
import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
# --- 中文 Windows 兼容：输出被重定向时 stdout 会退化成 GBK，emoji 会抛 UnicodeEncodeError ---
try:
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
except Exception:
    pass


HERE = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(HERE, 'config.json')

MOCK_REPORT = """# 候选人评估报告

## 一、结论速览
- 应聘岗位：人力资源实习生（招聘方向）
- 综合得分：86/100（档位：推荐进入面试）
- 分项得分：硬性要求 100｜关键词匹配 55｜经历完整度 100（权重 5:3:2）
- 一句话结论：有招聘实习经历与 Excel 实操佐证，到岗时间待面试确认。

## 二、硬性要求核对

| 硬性要求 | 是否满足 | 证据（简历原文） |
|---|---|---|
| 大专及以上在读 | 是 | 某大学 人力资源管理 本科 2023.09-2027.06 |
| 每周可到岗 4 天以上 | 否 | 简历未提及。属意愿/可用性条件，不参与计分，**必须在面试中确认** |
| 实习期不少于 3 个月 | 否 | 简历未提及。同上，必须在面试中确认 |
| 熟练使用 Excel | 是 | 使用 Excel 整理候选人台账，每周输出招聘周报，累计整理候选人数据 800 余条 |
| 熟练使用 Word | 是 | 技能栏「熟练使用 Excel（数据透视表、VLOOKUP）、Word、PPT」 |
| 熟练使用 PPT | 是 | 同上 |

## 三、能力匹配分析

### 命中项
- 面试安排 —— 简历原文："协助安排面试，日均电话邀约 10+ 位候选人，跟进面试结果反馈"
- Excel —— 简历原文："使用 Excel 整理候选人台账，每周输出招聘周报"
- 候选人数据库 —— 简历原文："使用 Excel 整理候选人台账……累计整理候选人数据 800 余条"
- 校园宣讲会 —— 简历原文："参与组织校园宣讲会 2 场，负责场地对接、物料准备与现场签到"

### 缺口项
- 双选会 —— 用途：JD 要求"协助组织校园宣讲会、双选会等线下招聘活动"。简历仅有宣讲会经历，无双选会。影响程度：中。

### 疑似命中（需人工确认）
- 简历筛选：① 岗位用词"简历筛选"；② 简历只在技能栏列出；③ 需确认是否独立承担过筛选工作及处理量。
- 电话初筛：① 岗位用词"电话初筛"；② 简历写"日均电话邀约"；③ 需确认电话邀约中是否含初筛判断。

## 四、风险提示
- 有 4 个关键词只出现在技能清单/自我评价里、实习或项目经历中没有佐证，未计入分数，需人工确认。
- 有 2 条"意愿/可用性"条件简历中不会有证据，已改为面试确认项，必须在面试中确认。

## 五、面试建议问题

### 缺口验证
1. 问题：我们岗位会涉及协助组织双选会，但简历里写的是校园宣讲会。如果让你负责一场双选会，从前期企业对接到现场执行，你会怎么安排？
   - 考察点：验证双选会组织的实际认知与可迁移能力
   - 追问方向：如果开场前有企业临时取消或场地临时调整，你会按什么优先级处理？
   - 合格回答要点：能说出企业邀约、展位动线、物料签到、现场协调、数据回收等关键环节

### 疑点澄清
2. 问题：简历里写了熟练 Word 和 PPT，招聘中 PPT 常用于校园宣讲。请说说你最近一次用 PPT 做的作品是什么？
   - 考察点：核实 Word、PPT 是罗列技能还是真能用
   - 追问方向：如果要你独立做一份宣讲会 PPT，你会怎么搭结构？

## 六、数据说明与免责声明
- 评分口径：硬性要求满足度 50% + 关键词加权覆盖 30% + 经历完整度 20%
- 硬性要求判定方式：hard_mode = model（语义判断）
- 免责声明：本报告由 AI 自动生成，仅作为简历初筛的辅助参考，不构成录用建议；所有结论均需 HR 人工复核，最终录用决定由 HR 与用人部门做出。
"""


def load_config():
    """读配置。

    注意用 utf-8-sig：记事本另存时可能带上 UTF-8 BOM，
    用普通的 utf-8 读会报 "Unexpected UTF-8 BOM"，然后 api_key 就变成空的了
    （第一次用的时候就踩了这个坑，导致界面一直说"未配置密钥"）。

    每次请求都会重新调用本函数，所以**改完 config.json 不用重启服务**。
    """
    cfg = {'api_base': 'http://localhost/v1', 'api_key': ''}
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, encoding='utf-8-sig') as f:
                cfg.update(json.load(f))
        except Exception as e:
            print('  [!] config.json 读取失败：%s: %s' % (type(e).__name__, e))
    # 环境变量优先（避免把密钥写进文件）
    if os.environ.get('DIFY_API_KEY'):
        cfg['api_key'] = os.environ['DIFY_API_KEY']
    return cfg


def call_dify(cfg, jd_text, resume_text, jd_json_fixed):
    """调 Dify 的工作流 API（blocking 模式）。"""
    url = cfg['api_base'].rstrip('/') + '/workflows/run'
    inputs = {'jd_text': jd_text, 'resume_text': resume_text}
    if jd_json_fixed and jd_json_fixed.strip():
        inputs['jd_json_fixed'] = jd_json_fixed
    payload = json.dumps({
        'inputs': inputs,
        'response_mode': 'blocking',
        'user': 'local-web',
    }, ensure_ascii=False).encode('utf-8')

    req = urllib.request.Request(url, data=payload, method='POST')
    req.add_header('Authorization', 'Bearer ' + cfg['api_key'])
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
        raise RuntimeError('Dify 返回 HTTP %s：%s' % (e.code, json.dumps(detail, ensure_ascii=False)))
    except urllib.error.URLError as e:
        raise RuntimeError('连不上 Dify（%s）。确认 Dify 已启动：双击 C:\\agent\\打开管理界面.bat 选 3'
                           % e.reason)


HTML = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<title>HR 招聘助手 · 候选人评估</title>
<style>
  :root { --bd:#e3e6ea; --mut:#6b7280; --pri:#2563eb; --ok:#0f9d58; --warn:#d97706; }
  * { box-sizing:border-box; }
  body { margin:0; font-family:"Microsoft YaHei","Segoe UI",sans-serif; background:#f6f7f9; color:#1f2328; }
  header { background:#fff; border-bottom:1px solid var(--bd); padding:14px 22px; display:flex; align-items:center; gap:12px; }
  header h1 { font-size:17px; margin:0; font-weight:600; }
  header .tag { font-size:12px; color:var(--mut); border:1px solid var(--bd); border-radius:10px; padding:2px 8px; }
  .wrap { max-width:1180px; margin:0 auto; padding:18px 22px 60px; }
  .grid { display:grid; grid-template-columns:1fr 1fr; gap:14px; }
  @media (max-width:900px){ .grid{ grid-template-columns:1fr; } }
  .card { background:#fff; border:1px solid var(--bd); border-radius:10px; padding:14px; }
  .card h2 { font-size:13px; margin:0 0 8px; color:var(--mut); font-weight:600; }
  textarea { width:100%; height:190px; resize:vertical; border:1px solid var(--bd); border-radius:8px;
             padding:10px; font-family:Consolas,monospace; font-size:13px; line-height:1.55; }
  textarea:focus { outline:2px solid #bfdbfe; border-color:var(--pri); }
  .row { display:flex; gap:10px; align-items:center; margin-top:14px; flex-wrap:wrap; }
  button { border:none; border-radius:8px; padding:10px 20px; font-size:14px; cursor:pointer; font-family:inherit; }
  #go { background:var(--pri); color:#fff; font-weight:600; }
  #go:disabled { background:#9ca3af; cursor:not-allowed; }
  .ghost { background:#fff; border:1px solid var(--bd); color:#374151; }
  .mut { color:var(--mut); font-size:12px; }
  .sum { display:flex; gap:26px; align-items:baseline; background:#fff; border:1px solid var(--bd);
         border-radius:10px; padding:14px 18px; margin-bottom:14px; flex-wrap:wrap; }
  .sum .big { font-size:30px; font-weight:700; }
  .sum .lb { display:inline-block; padding:3px 12px; border-radius:999px; font-size:13px; font-weight:600; }
  .lb.ok { background:#e7f6ee; color:var(--ok); }
  .lb.warn { background:#fef3e2; color:var(--warn); }
  .lb.bad { background:#fdecec; color:#c53030; }
  .lb.na { background:#eef1f5; color:var(--mut); }
  #err { display:none; background:#fdecec; border:1px solid #f5c2c2; color:#8a1f1f;
         border-radius:10px; padding:12px 14px; margin-bottom:14px; white-space:pre-wrap; font-size:13px; }
  #rep { background:#fff; border:1px solid var(--bd); border-radius:10px; padding:22px 26px; line-height:1.75; font-size:14px; }
  #rep h1 { font-size:20px; border-bottom:2px solid var(--bd); padding-bottom:8px; }
  #rep h2 { font-size:16px; margin-top:24px; color:#111; }
  #rep h3 { font-size:14px; margin-top:16px; color:#333; }
  #rep table { border-collapse:collapse; width:100%; margin:10px 0; font-size:13px; }
  #rep th, #rep td { border:1px solid var(--bd); padding:7px 9px; text-align:left; vertical-align:top; }
  #rep th { background:#f3f4f6; font-weight:600; }
  #rep code { background:#f3f4f6; padding:1px 5px; border-radius:4px; font-size:12.5px; }
  #rep hr { border:none; border-top:1px solid var(--bd); margin:18px 0; }
  .spin { display:inline-block; width:13px; height:13px; border:2px solid #ffffff88; border-top-color:#fff;
          border-radius:50%; animation:sp .7s linear infinite; vertical-align:-2px; margin-right:6px; }
  @keyframes sp { to { transform:rotate(360deg); } }
  details summary { cursor:pointer; color:var(--mut); font-size:12px; }
</style>
</head>
<body>
<header>
  <h1>HR 招聘助手 · 候选人评估</h1>
  <span class="tag" id="mode">检查中…</span>
</header>
<div class="wrap">
  <div id="err"></div>

  <div class="grid">
    <div class="card">
      <h2>① 岗位 JD（原文）</h2>
      <textarea id="jd" placeholder="把岗位 JD 的完整内容粘贴到这里…"></textarea>
      <div class="mut" id="jdlen" style="margin-top:6px;">0 字</div>
    </div>
    <div class="card">
      <h2>② 候选人简历（原文）</h2>
      <textarea id="cv" placeholder="把简历的完整内容粘贴到这里…"></textarea>
      <div class="mut" id="cvlen" style="margin-top:6px;">0 字</div>
    </div>
  </div>

  <div class="card" style="margin-top:14px;">
    <details>
      <summary>③ 岗位档案（固化版，可选 —— 填了就保证同一岗位的打分分母恒定）</summary>
      <textarea id="fix" style="height:120px; margin-top:10px;"
        placeholder="粘贴 data\jd_fixed\jd_01.json 的全部内容。留空则每次现场解析（分母会变）。"></textarea>
      <div class="mut" id="fixlen" style="margin-top:6px;">0 字（留空 = 现场解析）</div>
    </details>
  </div>

  <div class="row">
    <button id="go">开始评估</button>
    <button class="ghost" id="clr">清空</button>
    <span class="mut" id="hint">一次评估约 35 秒</span>
  </div>

  <div id="out" style="margin-top:20px;"></div>
</div>

<script>
const $ = id => document.getElementById(id);
const esc = s => String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');

function inline(s){
  return esc(s)
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/`(.+?)`/g, '<code>$1</code>');
}

function md(t){
  const L = String(t||'').split(/\r?\n/);
  let out = [], i = 0;
  while (i < L.length){
    let l = L[i];
    // 表格
    if (/^\s*\|/.test(l) && i+1 < L.length && /^\s*\|[\s:|\-]+\|\s*$/.test(L[i+1])){
      const cells = r => r.trim().replace(/^\||\|$/g,'').split('|').map(x=>x.trim());
      const head = cells(l); i += 2;
      let rows = [];
      while (i < L.length && /^\s*\|/.test(L[i])) { rows.push(cells(L[i])); i++; }
      out.push('<table><thead><tr>' + head.map(h=>'<th>'+inline(h)+'</th>').join('') +
               '</tr></thead><tbody>' +
               rows.map(r=>'<tr>'+r.map(c=>'<td>'+inline(c)+'</td>').join('')+'</tr>').join('') +
               '</tbody></table>');
      continue;
    }
    let m;
    if ((m = l.match(/^(#{1,6})\s+(.*)$/))) { const n = m[1].length; out.push('<h'+n+'>'+inline(m[2])+'</h'+n+'>'); i++; continue; }
    if (/^\s*(---|\*\*\*)\s*$/.test(l)) { out.push('<hr>'); i++; continue; }
    if (/^\s*[-*+]\s+/.test(l)) {
      let items = [];
      while (i < L.length && /^\s*[-*+]\s+/.test(L[i])) { items.push('<li>'+inline(L[i].replace(/^\s*[-*+]\s+/,''))+'</li>'); i++; }
      out.push('<ul>'+items.join('')+'</ul>'); continue;
    }
    if (/^\s*\d+[.、)]\s+/.test(l)) {
      let items = [];
      while (i < L.length && /^\s*\d+[.、)]\s+/.test(L[i])) { items.push('<li>'+inline(L[i].replace(/^\s*\d+[.、)]\s+/,''))+'</li>'); i++; }
      out.push('<ol>'+items.join('')+'</ol>'); continue;
    }
    if (!l.trim()) { i++; continue; }
    out.push('<p>'+inline(l)+'</p>'); i++;
  }
  return out.join('\n');
}

function levelClass(lv){
  lv = String(lv||'');
  if (lv.indexOf('数据不足') >= 0) return 'na';
  if (lv.indexOf('暂不推荐') >= 0) return 'bad';
  if (lv.indexOf('推荐进入面试') >= 0) return lv.indexOf('边界') >= 0 ? 'warn' : 'ok';
  if (lv.indexOf('待定') >= 0) return 'warn';
  return 'na';
}

function bind(id, out){
  const el = $(id), lab = $(out);
  const upd = () => { lab.textContent = el.value.length + (id==='fix' ? ' 字（留空 = 现场解析）' : ' 字'); };
  el.addEventListener('input', upd); upd();
}
bind('jd','jdlen'); bind('cv','cvlen'); bind('fix','fixlen');

fetch('api/config').then(r=>r.json()).then(c=>{
  $('mode').textContent = c.mock ? '演示模式（不调 Dify）'
                       : (c.has_key ? '已连接 Dify · ' + c.api_base : '未配置 API 密钥');
  if (!c.mock && !c.has_key) {
    $('err').style.display = 'block';
    $('err').textContent = '还没有配置 Dify API 密钥。\n' +
      '请打开 tools\\local_web\\config.json，把 api_key 填成你在 Dify「访问 API」页面创建的密钥。';
  }
}).catch(()=>{ $('mode').textContent = '后端未响应'; });

$('clr').onclick = () => { $('jd').value = ''; $('cv').value = ''; $('fix').value = '';
  ['jd','cv','fix'].forEach(i=>$(i).dispatchEvent(new Event('input'))); $('out').innerHTML=''; $('err').style.display='none'; };

$('go').onclick = async () => {
  const jd = $('jd').value.trim(), cv = $('cv').value.trim(), fx = $('fix').value.trim();
  $('err').style.display = 'none';
  if (!jd || !cv){ $('err').style.display='block'; $('err').textContent='请先填写「岗位 JD」和「简历原文」。'; return; }
  if (jd.length < 60 || cv.length < 60){
    if (!confirm('JD 或简历只有 ' + Math.min(jd.length,cv.length) + ' 个字，看起来像是把【文件路径】填进来了。\n\n'
      + '要填的是【文件里的内容】。确定要继续吗？')) return;
  }
  const t0 = Date.now();
  $('go').disabled = true;
  $('go').innerHTML = '<span class="spin"></span>评估中…（约 35 秒）';
  $('hint').textContent = '正在调用工作流：解析 JD → 解析简历 → 硬性要求判断 → 打分 → 出题 → 出报告';
  try {
    const res = await fetch('api/run', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({jd_text: jd, resume_text: cv, jd_json_fixed: fx})
    });
    const j = await res.json();
    if (!res.ok || j.error){ throw new Error(j.error || ('HTTP ' + res.status)); }
    const o = j.outputs || {};
    const sc = o.report_result !== undefined ? o.report_result : (o.score !== undefined ? o.score : '—');
    const lv = o.level || '—';
    $('out').innerHTML =
      '<div class="sum">' +
        '<div><div class="mut">综合得分</div><div class="big">' + esc(sc) + '<span class="mut" style="font-size:14px"> /100</span></div></div>' +
        '<div><div class="mut">档位</div><div class="lb ' + levelClass(lv) + '">' + esc(lv) + '</div></div>' +
        '<div><div class="mut">耗时</div><div>' + (j.elapsed_time||'—') + ' 秒</div></div>' +
        '<div><div class="mut">消耗</div><div>' + (j.total_tokens||'—') + ' tokens</div></div>' +
        '<div><div class="mut">节点数</div><div>' + (j.total_steps||'—') + '</div></div>' +
      '</div>' +
      (o.detail ? '<details style="margin-bottom:12px"><summary>查看打分明细（detail）</summary><pre style="white-space:pre-wrap;font-size:12.5px;background:#fff;border:1px solid #e3e6ea;border-radius:8px;padding:12px;">' + esc(o.detail) + '</pre></details>' : '') +
      '<div id="rep">' + md(o.report || '（上游没有返回 report 字段）') + '</div>';
  } catch (e) {
    $('err').style.display='block';
    $('err').textContent = '评估失败：' + e.message;
  } finally {
    $('go').disabled = false;
    $('go').textContent = '开始评估';
    $('hint').textContent = '上次耗时 ' + ((Date.now()-t0)/1000).toFixed(1) + ' 秒';
  }
};
</script>
</body>
</html>
"""


class Handler(BaseHTTPRequestHandler):
    server_version = 'HRRecruitAgentLocal/1.0'
    cfg = None
    mock = False

    def log_message(self, fmt, *args):
        sys.stderr.write('  %s - %s\n' % (time.strftime('%H:%M:%S'), fmt % args))

    def _send(self, code, body, ctype):
        if isinstance(body, str):
            body = body.encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', ctype)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(body)

    def _json(self, code, obj):
        self._send(code, json.dumps(obj, ensure_ascii=False), 'application/json; charset=utf-8')

    def _cfg(self):
        """每次请求都重新读配置 —— 这样改完 config.json 不用重启服务。"""
        return load_config()

    def do_GET(self):
        if self.path in ('/', '/index.html'):
            self._send(200, HTML, 'text/html; charset=utf-8')
        elif self.path == '/api/config':
            c = self._cfg()
            self._json(200, {'mock': self.mock, 'api_base': c['api_base'],
                             'has_key': bool(c['api_key'])})
        elif self.path == '/api/health':
            self._json(200, {'ok': True})
        else:
            self._send(404, 'not found', 'text/plain; charset=utf-8')

    def do_POST(self):
        if self.path != '/api/run':
            self._send(404, 'not found', 'text/plain; charset=utf-8')
            return
        try:
            n = int(self.headers.get('Content-Length') or 0)
            data = json.loads(self.rfile.read(n).decode('utf-8') or '{}')
        except Exception as e:
            self._json(400, {'error': '请求体解析失败：%s' % e})
            return

        jd = (data.get('jd_text') or '').strip()
        cv = (data.get('resume_text') or '').strip()
        fx = (data.get('jd_json_fixed') or '').strip()
        if not jd or not cv:
            self._json(400, {'error': '岗位 JD 和简历原文都要填。'})
            return

        if self.mock:
            time.sleep(2.0)
            self._json(200, {
                'outputs': {'report': MOCK_REPORT, 'report_result': 86,
                            'level': '推荐进入面试',
                            'detail': '{"hard_score": 100, "keyword_score": 55, "experience_score": 100,'
                                      ' "weight": "5:3:2", "hard_mode": "model",'
                                      ' "scored_hard_count": 4, "to_confirm": ["每周可到岗 4 天以上",'
                                      ' "实习期不少于 3 个月"]}',
                            'suspect': ['简历筛选', '电话初筛', 'Word', 'PPT']},
                'elapsed_time': 2.0, 'total_tokens': 15905, 'total_steps': 9,
                'mock': True,
            })
            return

        cfg = self._cfg()
        if not cfg['api_key']:
            self._json(400, {'error': '还没有配置 Dify API 密钥。请编辑 '
                                      + CONFIG_PATH +
                                      '，把 api_key 填成 Dify「访问 API」页面创建的密钥。'
                                      '（改完记得按 Ctrl+S 保存；不用重启本服务，下次请求就会生效）'})
            return
        try:
            r = call_dify(cfg, jd, cv, fx)
        except RuntimeError as e:
            self._json(502, {'error': str(e)})
            return
        except Exception as e:
            self._json(500, {'error': '意外错误：%s' % e})
            return

        d = (r or {}).get('data') or {}
        if d.get('status') != 'succeeded':
            self._json(200, {'error': '工作流没跑成功（status=%s）：%s'
                                      % (d.get('status'), d.get('error') or '无错误信息')})
            return
        self._json(200, {
            'outputs': d.get('outputs') or {},
            'elapsed_time': d.get('elapsed_time'),
            'total_tokens': d.get('total_tokens'),
            'total_steps': d.get('total_steps'),
            'workflow_run_id': r.get('workflow_run_id'),
        })


def main():
    ap = argparse.ArgumentParser(description='HR 招聘助手本地界面')
    ap.add_argument('--port', type=int, default=8000)
    ap.add_argument('--mock', action='store_true', help='演示模式：不调 Dify，返回样例报告')
    ap.add_argument('--host', default='127.0.0.1')
    a = ap.parse_args()

    Handler.cfg = load_config()
    Handler.mock = a.mock

    print('=' * 66)
    print('  HR 招聘助手 · 本地界面')
    print('=' * 66)
    if a.mock:
        print('  模式：演示模式（不调 Dify，返回样例报告）')
    else:
        print('  模式：真实模式')
        print('  Dify 地址：%s' % Handler.cfg['api_base'])
        print('  配置文件：%s' % CONFIG_PATH)
        if Handler.cfg['api_key']:
            k = Handler.cfg['api_key']
            print('  API 密钥：%s……（已配置，共 %d 位）' % (k[:12], len(k)))
        else:
            print('  API 密钥：[未配置]')
            print()
            print('  ┌────────────────────────────────────────────────────────┐')
            print('  │ 密钥还没填。请用记事本打开上面那个配置文件：          │')
            print('  │   "api_key": ""  →  "api_key": "app-你复制的密钥"     │')
            print('  │ ⚠️ 改完一定要按 Ctrl+S 保存（上次就是漏了这一步）      │')
            print('  │ 本服务每次请求都会重读配置，改完不用重启。             │')
            print('  └────────────────────────────────────────────────────────┘')
    print()
    print('  打开浏览器访问：  http://%s:%d' % (a.host, a.port))
    print('  停止服务：按 Ctrl+C')
    print('=' * 66)

    srv = ThreadingHTTPServer((a.host, a.port), Handler)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print('\n  已停止。')


if __name__ == '__main__':
    main()
