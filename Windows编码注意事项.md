# Windows 中文环境的文件编码注意事项

> 📌 **先说一个我犯过的错**：本文档里我曾写过
> "这台机器上 flask / streamlit / fastapi 都没装"——**那句话是错的**。
> 实际情况是这台机器有 **7 个 Python**，streamlit 和 fastapi 装在别的 venv 里。
> 详见仓库根目录的 `环境说明.md`。
>
> 留在这里当反面教材：**我从单个解释器的检查结果，过度推广成了全机结论。**
> 这和本文档里那些"默认值悄悄出错"的坑是同一类问题——
> **范围没铺满就下结论。**

这份文档是踩坑记录。做这个项目的过程中，**编码问题一共坑了我们 6 次**，
每次的现象都不一样，很难凭直觉找到原因。记下来，下次直接查表。

---

## 一、按文件类型查表

| 文件类型 | 必须的编码 | 为什么 |
|---|---|---|
| **`.bat`** | **GBK（ANSI）+ CRLF 行尾** | cmd.exe 按当前代码页（中文 Windows 是 936/GBK）读文件；**行尾必须是 CRLF** |
| **`.ps1`** | **UTF-8 with BOM** | PowerShell 5.1 读**没有 BOM** 的 UTF-8 文件时会按 GBK 解码 → 中文全乱 → 语法错误 |
| **`.py`** | UTF-8 **不带** BOM | Python 3 默认按 UTF-8 读；带 BOM 反而可能报错 |
| **`.txt`（给人看的）** | **UTF-8 with BOM** | 记事本/Excel 打开无 BOM 的 UTF-8 会乱码 |
| **`.csv`（给 Excel 的）** | **UTF-8 with BOM** | 同上；Excel 另存后还会变回 GBK，见第四节 |
| **`.md`** | 随意（一般不带 BOM） | 用编辑器看，不敏感 |

---

## 二、踩坑记录（每次的现象 + 原因）

### 坑 1：PowerShell 的 `Get-Content` 把 195 行读成 178 行

```powershell
(Get-Content score_dify.py).Count          # → 178  ❌
(Get-Content score_dify.py -Encoding UTF8).Count   # → 195  ✅
```

**原因**：不加 `-Encoding` 时 PS 5.1 按 GBK 解码 UTF-8 文件，
多字节序列会把换行符 `\n` 当成非法尾字节**吞掉**，于是行数变少。

**正确写法**：`Get-Content -Encoding UTF8`，或用
`[System.IO.File]::ReadAllText($p, [System.Text.UTF8Encoding]::new($false))`

### 坑 2：`.bat` 一输入就退出

**现象**：双击 `.bat`，输入内容后窗口直接关闭。

**原因**：`.bat` 是**纯 LF 行尾**（8 个 LF、0 个 CRLF）。
cmd.exe 解析 LF-only 的批处理文件会出错，`goto :eof`、`set /p` 都会失灵。

**修法**：写成 **CRLF** 行尾 + GBK 编码，并且**把交互逻辑尽量搬进 `.ps1`**，
让 `.bat` 只留几行。

### 坑 3：`.ps1` 报语法错误，错误信息里全是乱码

```
Unexpected token '鍙傝€冩。浣?' in expression or statement.
```

**原因**：`.ps1` 是 UTF-8 **没有 BOM**，PS 5.1 按 GBK 解码，
中文变成乱码，引号/括号配对全乱。

**修法**：存成 **UTF-8 with BOM**。

### 坑 4：Excel 另存 CSV 后，Python 读不了

```
UnicodeDecodeError: 'utf-8' codec can't decode byte 0xd3 in position 0
```

**原因**：用 Excel 编辑并保存 CSV 时，Excel 会把文件**转成本地 ANSI 编码（GBK）**。

**修法**：读的时候按 GBK 读；或者编辑完再转回 UTF-8 BOM。

### 坑 5：Dify 提示词里的变量引用多了一层花括号

**现象**：提示词里出现 `{{{#节点ID.变量名#}}`（三个左花括号）。

**原因**：占位符写的是 `{{JD解析 / text}}`。粘贴时如果**只选中花括号里面的内容**
（留下一个 `{`），再插入变量胶囊，就变成 `{` + `{{#...#}}`。

**后果**：Dify 从**第二个** `{` 开始匹配，变量还能生效，但会**多一个 `{` 原样发给模型**。
更糟的是有一次粘歪成了孤零零的 `{{`，变量**彻底失效**。

**修法**：
1. 用 `prompts\用户提示词汇总.txt`——标记是 `«插入变量：X / Y»`，
   **不含花括号**，从结构上不可能粘出多余花括号
2. 更彻底：用 `tools\sync_dify.py` 直接改数据库，不用手粘

### 坑 6：把测试文件粘进了 Dify 代码节点

**现象**：代码节点里装的是 `tests\test_score.py`，没有入口函数，运行直接报错。

**原因**：两个文件都以 `# -*- coding: utf-8 -*-` 开头，长得像。

**修法**：两个文件都加了**醒目的首行横幅**；
`tools\sync_dify.py` 里加了硬校验（写入前必须检测到 `def main(jd_json`）。

---

## 三、一句话原则

> **在中文 Windows 上，凡是"中文 + 非 ASCII 字符"跨程序传递，
> 一定要显式指定编码，不要依赖默认值。**

默认值在这些地方各不相同，而且**默认错了通常不报错，只是悄悄出问题**——
这才是最麻烦的地方（坑 1、坑 4、坑 5 都属于"静默出错"）。

---

## 四、本项目各文件的编码现状（自检结果）

| 文件 | 编码 | 状态 |
|---|---|---|
| `tools\准备输入.bat` | GBK + CRLF | ✅ |
| `tools\准备输入.ps1` | UTF-8 BOM | ✅ |
| `tools\*.py` | UTF-8 无 BOM | ✅ |
| `prompts\*汇总.txt` | UTF-8 BOM | ✅ |
| `test\运行清单.csv` | UTF-8 BOM | ✅ |
| 其余 `.md` / `.py` | UTF-8 无 BOM | ✅ |

**改动这些文件时，务必保持上表的编码**，否则会重现上面的坑。
