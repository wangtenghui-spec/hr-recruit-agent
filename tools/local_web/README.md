# 本地网页界面

给「HR 招聘助手」做了**两版**本地界面，功能一样，选一个用就行：

| 版本 | 文件 | 启动 | 依赖 |
|---|---|---|---|
| **标准库版** | `server.py` | 双击 `启动界面.bat` | **零依赖**，7 个 Python 里哪个都能跑 |
| **Streamlit 版** | `app_streamlit.py` | 双击 `启动界面-Streamlit.bat` | 需要 streamlit（启动脚本会自动找） |

---

## 两版怎么选

| | 标准库版 | Streamlit 版 |
|---|---|---|
| 需要依赖 | ❌ 不需要 | ✅ 需要 streamlit |
| 双击就能跑 | ✅ | ✅（脚本会自动找解释器） |
| 代码量 | 482 行（含内嵌 HTML/CSS/JS） | 约 300 行，纯 Python |
| Markdown 报告渲染 | 自己写的 JS 渲染器 | **Streamlit 原生 `st.markdown`** |
| 结果组件 | 手写 HTML | `st.metric` / `st.tabs` / `st.json` / 下载按钮 |
| 快速载入某组用例 | 用 `tools\准备输入.bat` | **界面里直接选，不用切窗口** |
| 端口 | 8000 | 8001 |

> **两个可以同时开**（端口不同），方便对比。
>
> **要给别人演示、或者换台机器跑** → 用标准库版（不怕环境变）。
> **自己平时用、想快速跑 20 组评测** → 用 Streamlit 版（载入用例更方便）。

---

## ⚠️ 关于"这台机器上到底装了什么"（更正一次）

我一开始说"这台机器上 flask/streamlit/fastapi 都没装"——**这句话是错的**。
实际情况是：**我只查了默认的那个 Python，就下了全机的结论。**

这台机器上**有 7 个 Python**，其中：

| 解释器 | streamlit | fastapi |
|---|---|---|
| `C:\develop\python`（默认 `python` 命令） | ❌ | ❌ |
| `C:\develop\miniconda3` | ❌ | ❌ |
| `C:\develop\miniconda3\envs\agent_env` | ❌ | ❌ |
| **`C:\Project\.venv_pd3`** | **✅ 1.64.0** | ❌ |
| `<你的用户目录>\ai_project\.venv` | ❌ | ❌ |
| **`<你的用户目录>\PycharmProjects\PythonProject\.venv`** | **✅ 1.63.0** | **✅ 0.142.2** |

详细清单见仓库根目录的 `环境说明.md`。

**`启动界面-Streamlit.bat` 会自动按顺序探测上面两个装了 streamlit 的解释器**，
找到哪个用哪个；都找不到会给出提示（并建议改用标准库版）。

---

## 快速开始

### 1. 先配 API 密钥（只需要一次）

1. 打开 Dify → 你的应用 `hr-recruit-agent-v0.1`
2. 右上角点 **「发布」→「发布更新」**（⚠️ 必须先发布，否则 API 用不了）
3. 左侧点 **「访问 API」** → 在「API 密钥」那里点 **创建** → 复制那串 `app-xxxxxxxx`
4. 打开本目录的 `config.json`，填进去：

```json
{
  "api_base": "http://localhost/v1",
  "api_key": "app-你复制的那串"
}
```

> ⚠️ **红线**：`config.json` 里是真实密钥，**不要提交到 GitHub**。
> 也可以改用环境变量 `DIFY_API_KEY`，脚本会优先读它。
> 仓库里给的是 `config.example.json` 模板。

### 2. 启动

**标准库版**：双击 **`启动界面.bat`** → 浏览器访问 <http://127.0.0.1:8000>

**Streamlit 版**：双击 **`启动界面-Streamlit.bat`** → 浏览器自动打开 <http://localhost:8001>

> Streamlit 版不能在默认 `python` 里跑（那个没装 streamlit）。
> **启动脚本会自动找到装了 streamlit 的解释器**，你不用管。

### 3. 停止

**标准库版**：在窗口里按 `Ctrl+C`，或者直接关窗口。
**Streamlit 版**：在窗口里按 `Ctrl+C`。

---

## Streamlit 版有什么不一样

| 特性 | 说明 |
|---|---|
| **侧边栏直接选用例** | 下拉框列出 `test\运行清单.csv` 里的 20 组，点「载入这一组数据」就把 JD / 简历 / 岗位档案一次填好 —— **跑 20 组评测时不用切窗口复制粘贴了** |
| **原生 Markdown 渲染** | 报告里的表格由 `st.markdown` 直接渲染，不用自己写渲染器 |
| **结果分三个标签页** | 📄 评估报告 ｜ 🔍 打分明细（`st.json`）｜ 🧩 结构化字段（命中/疑似/缺口/风险） |
| **可下载报告** | 一键下载 `.md` 文件 |
| **演示模式** | 侧边栏勾一下就行，不用改启动参数 |

---

## 不想配密钥？用演示模式

- **标准库版**：双击 **`演示模式.bat`**
- **Streamlit 版**：侧边栏勾「演示模式（不调 Dify）」

两种都是不调用 Dify、直接返回一份样例报告，用来演示界面长什么样、报告怎么呈现。

---

## 界面怎么用

| 输入框 | 填什么 | 从哪来 |
|---|---|---|
| ① 岗位 JD（原文） | JD 的**完整文字** | `data\jd\jd_01.txt` 的内容 |
| ② 候选人简历（原文） | 简历的**完整文字** | `data\resume\cv_01.txt` 的内容 |
| ③ 岗位档案（固化版，可选） | 岗位档案 JSON | `data\jd_fixed\jd_01.json` 的内容 |

> ⚠️ **填的是文件里的内容，不是文件路径。**
> 自检：JD 那格应该有**几百字**。如果只有十几个字，就是填成路径了——
> 界面会弹窗提醒你。

**填了第 ③ 格** → 同一个岗位的所有候选人用同一套关键词表，打分分母恒定、分数可比。
**留空** → 每次现场解析，分母会变（只是不方便做候选人之间对比，不影响单次评估）。

---

## 底层发生了什么

```
浏览器  →  本地 server.py（本目录）  →  Dify /v1/workflows/run  →  9 个节点的完整工作流
```

为什么不让网页直接调 Dify：**浏览器的同源策略（CORS）会拦住跨域请求**，
所以需要本脚本做一次中转。

调用的接口（blocking 模式）：

```
POST http://localhost/v1/workflows/run
Authorization: Bearer app-xxxx
{"inputs": {"jd_text": "...", "resume_text": "...", "jd_json_fixed": "..."},
 "response_mode": "blocking", "user": "local-web"}
```

返回里 `data.outputs` 就是工作流「输出」节点里的那些字段：
`report`（Markdown 报告）、`report_result`（得分）、`level`（档位）、
`detail`、`suspect` 等。界面会把 `report` 渲染成带表格的网页。

---

## 命令行参数

```bash
python server.py                 # 默认 127.0.0.1:8000，真实模式
python server.py --mock          # 演示模式
python server.py --port 8080     # 换端口
python server.py --host 0.0.0.0  # 允许局域网访问（⚠️ 别人也能用你的密钥额度）
```

---

## 出错了怎么查

| 现象 | 原因 | 怎么办 |
|---|---|---|
| 页面显示「未配置 API 密钥」 | `config.json` 里 `api_key` 是空的 | 按上面第 1 步配 |
| 提示 `HTTP 401` | 密钥不对，或者应用没发布 | 确认已点「发布更新」，确认密钥复制完整 |
| 提示 `HTTP 404` | 应用没有已发布版本 | 去 Dify 点「发布更新」 |
| 提示「连不上 Dify」 | Dify 没启动 | 双击 `C:\agent\打开管理界面.bat` 选 `3` |
| 提示「工作流没跑成功」 | 某个节点报错了 | 去 Dify 看那次运行的哪个节点是红的 |
| 界面打不开 | 端口被占 | `python server.py --port 8080` |
