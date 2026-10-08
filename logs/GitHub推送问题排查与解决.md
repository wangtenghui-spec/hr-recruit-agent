# GitHub 推送失败排查与解决（完整记录）

> **现象**：`git push` 和 GitHub Desktop 的 Push 都失败。
> **结论**：不是账号问题、不是仓库问题、不是操作问题 ——
> 是 **DNS 把 `github.com` 解析到了一个被网络阻断的 IP**，叠加 **git 默认用 HTTP/2 被重置**。
>
> 这份文档完整记录了排查过程，包括走过的弯路和最终的验证证据。

---

# 一、最初的报错

GitHub Desktop 日志（`%APPDATA%\GitHub Desktop\logs\`）里的原文：

```
git fetch --progress --prune --recurse-submodules=on-demand origin
  exited with an unexpected code: 128.
fatal: unable to access 'https://github.com/.../hr-recruit-agent.git/':
       Recv failure: Connection was reset

git push origin main --set-upstream --progress
  exited with an unexpected code: 128.
fatal: unable to access 'https://github.com/.../hr-recruit-agent.git/':
       Failed to connect to github.com port 443 after 21099 ms: Could not connect to server
```

## 关键线索：不是一直失败

```
03:41:06  Executing fetch ... (took 3.302s)     ← 成功
03:41:19  Executing fetch ... (took 1.733s)     ← 成功
03:46:19  Executing fetch ... (took 1.780s)     ← 成功
03:52:11  Executing fetch ... (took 41.056s)    ← 失败：Connection was reset
03:52:49  Executing push  ... (took 21.227s)    ← 失败：连接超时
03:54:06  Executing push  ... (took 56.139s)    ← 失败：Connection was reset
```

> **"时通时断"这个特征非常关键** —— 它排除了"配置错误"这类原因，
> 把方向直接指向**网络链路**。

---

# 二、排查步骤（每一步都留证据）

## 步骤 1：先排除"是不是我机器上的代理在捣乱"

```powershell
# 检查常见代理端口
7890,7897,7891,10809,10808,1080,8080,...
Get-NetTCPConnection -State Listen

# 检查系统代理设置
Get-ItemProperty 'HKCU:\...\Internet Settings'   # ProxyEnable = 0
netsh winhttp show proxy                          # Direct access（无代理）
```

**结果**：没有代理软件在运行，系统代理也没开。→ **不是代理配置冲突。**

## 步骤 2：分离"是全网问题，还是只有 GitHub 有问题"

| 目标 | 端口 | 结果 |
|---|---|---|
| `baidu.com` | 443 | ✅ 103 ms |
| `gitee.com` | 443 | ✅ 31 ms |
| **`github.com`** | 443 | ❌ **6012 ms 超时** |

**结论**：普通网络完全正常，**只有 github.com 不通**。

## 步骤 3：★ 关键一步 —— 绕过 DNS，直接测 IP

```powershell
# 先看 DNS 解析成什么
Resolve-DnsName github.com -Type A
# → 20.205.243.166
```

然后**逐个测试 GitHub 各机房的真实 IP**（这一步是转折点）：

| IP | 真实身份 | 结果 |
|---|---|---|
| `20.205.243.166` | **DNS 给我们的那个** | ❌ **4013 ms 失败** |
| `140.82.112.3` | GitHub 前端 | ✅ 338 ms |
| `140.82.112.4` | GitHub 前端 | ✅ 306 ms |
| `140.82.113.3` | GitHub 前端 | ✅ 306 ms |
| `140.82.113.4` | GitHub 前端 | ✅ 306 ms |
| `140.82.114.4` | GitHub 前端 | ✅ 306 ms |
| `140.82.116.3` | GitHub 前端 | ✅ **181 ms** |
| `140.82.121.3` | GitHub 前端 | ✅ 241 ms |
| `20.200.245.247` | GitHub 前端 | ✅ 169 ms |
| `4.208.26.197` | GitHub 前端 | ✅ 306 ms |
| `ssh.github.com` | 备用通道 | ✅ 101 ms |
| `codeload.github.com` | 代码打包服务 | ✅ 101 ms |
| `objects.githubusercontent.com` | 对象存储 | ✅ 409 ms |

> ## 🎯 根因确定
> **DNS 返回的 `20.205.243.166` 被阻断了，但 GitHub 其他所有 IP 都是通的。**
> 所以问题不在"GitHub 被墙"，而在**"被解析到了一个坏 IP"**。

## 步骤 4：验证"换个 IP 是不是真的能用"

```powershell
curl.exe --resolve github.com:443:140.82.113.4 https://github.com/
```

| 方式 | 结果 |
|---|---|
| 直连（用 DNS 的坏 IP） | ❌ `HTTP 000` 连接失败 |
| **`--resolve` 强制走 `140.82.113.4`** | ✅ **`HTTP 200`，连接耗时 0.278 秒** |

**证据确凿**：换 IP 就能通。

## 步骤 5：弯路 —— 换 DNS 服务器没用

以为"换个 DNS 就好了"，于是查了 5 家：

```
223.5.5.5     (阿里)   → 20.205.243.166
119.29.29.29  (腾讯)   → 20.205.243.166
180.76.76.76  (百度)   → 20.205.243.166
1.1.1.1       (Cloudflare) → 20.205.243.166
8.8.8.8       (Google) → 20.205.243.166
```

**五家 DNS 返回同一个 IP。** → 换 DNS 这条路走不通，
**必须在"应用层"覆盖解析结果。**

## 步骤 6：没有管理员权限，不能改 hosts

```
管理员: False
```

→ 排除"改 hosts 文件"这个常规方案（后来做成了一键脚本）。

## 步骤 7：★ 找到不需要管理员权限的解法

git 2.37+ 支持 `http.curloptResolve`，可以让 git **绕过系统 DNS**：

```powershell
git config --global --add http.curloptResolve "github.com:443:140.82.113.4"
```

**第一次测试失败了** —— 用 `GIT_CURL_VERBOSE=1` 抓出真实过程：

```
== Info: Host github.com:443 was resolved.
== Info:   Trying 140.82.113.4:443...            ← 覆盖生效了！
== Info: RESOLVE github.com:443 - old addresses discarded
== Info: Connection #0 to host github.com:443 left intact
<= Recv header: x-github-edge-region: iad        ← GitHub 正常响应
exit code = 0
```

**连接成功。**（当时误判为"没生效"，其实是我漏了 `git -C <仓库路径>`，
命令跑在了没有 origin 的目录里 —— **这也是个教训：测试命令一定要带对工作目录。**）

## 步骤 8：小请求通了，但 push 还是被重置

```
git ls-remote origin    → ✅ 通
git push origin main    → ❌ Recv failure: Connection was reset（30 秒后）
```

**新问题**：请求小的时候能过，**要上传数据就被重置**。

这是 HTTP/2 在国内链路上的典型表现。改成 HTTP/1.1：

```powershell
git config --global http.version HTTP/1.1
git config --global http.postBuffer 524288000
```

## 步骤 9：✅ 推送成功

```
Writing objects: 100% (97/97), 221.19 KiB | 6.32 MiB/s, done.
To https://github.com/wangtenghui-spec/hr-recruit-agent.git
 * [new branch]      main -> main
branch 'main' set up to track 'origin/main'

exit code = 0   耗时 3.9 秒
```

---

# 三、最终生效的配置

```powershell
git config --global http.version HTTP/1.1
git config --global http.postBuffer 524288000
git config --global --add http.curloptResolve "github.com:443:140.82.113.4"
```

| 配置 | 作用 |
|---|---|
| `http.curloptResolve` | **绕开系统 DNS**，强制把 github.com 解析到可用 IP |
| `http.version HTTP/1.1` | 避免 HTTP/2 连接被重置 |
| `http.postBuffer` | 允许较大的推送缓冲 |

> ✅ **GitHub Desktop 也会吃这套配置** —— 它自带的 git 是 **2.53.0**（≥2.37），
> 并且会读取全局 `~/.gitconfig`。所以以后在 GitHub Desktop 里点 Push 也能用。

---

# 四、这次排查的方法论（可复用到任何"某网站连不上"）

```
1. 先看报错原文              → 别猜，去 %APPDATA%\GitHub Desktop\logs\ 找日志
2. 看失败是不是持续的        → "时通时断" 说明是链路问题，不是配置问题
3. 排除本地因素              → 代理端口 / 系统代理 / 防火墙
4. 分离变量                  → 别的网站通不通？只有它不通 → 锁定目标
5. ★ 绕过 DNS 直接测 IP      → 找到根因的决定性一步
6. 用 --resolve 做单次验证   → 证明"换 IP 就能好"
7. 找到不需要高权限的写配置法 → http.curloptResolve
8. 开 verbose 看真实连接目标 → GIT_CURL_VERBOSE=1
9. 解决后立刻验证            → ls-remote / status -sb 确认远程真的有了
```

## 两个具体的教训

| 教训 | 说明 |
|---|---|
| **测试命令必须带对工作目录** | `git ls-remote origin` 漏了 `-C <repo>`，跑在别的目录里报"not a git repository"，差点误判成"配置没生效" |
| **"能连上"和"能传数据"是两件事** | `ls-remote` 通 ≠ `push` 能通。小请求过关、大流量被重置，要分开测 |

---

# 五、如果以后再出问题

## 症状 A：又连不上了

先测哪个 IP 还活着：

```powershell
foreach ($ip in '140.82.113.4','140.82.116.3','140.82.121.3','20.200.245.247','4.208.26.197') {
    $c = New-Object System.Net.Sockets.TcpClient
    $t = $c.ConnectAsync($ip, 443)
    "$ip  " + $(if ($t.Wait(4000) -and $c.Connected) { '✅' } else { '❌' })
    $c.Close()
}
```

把通的 IP 填进：

```powershell
git config --global --unset-all http.curloptResolve
git config --global --add http.curloptResolve "github.com:443:<新的可用IP>"
```

## 症状 B：浏览器也打不开 github.com

git 的配置只管 git，**不管浏览器**。浏览器需要改 hosts：

```
双击运行  C:\agent\修复GitHub访问.bat
（右键 → 以管理员身份运行）
```

这个脚本会：备份原 hosts → 写入可用 IP → 刷新 DNS → 自动验证。

## 症状 C：想彻底恢复原状

```powershell
# 撤销 git 配置
git config --global --unset-all http.curloptResolve
git config --global --unset http.version

# 恢复 hosts
copy /y "%SystemRoot%\System32\drivers\etc\hosts.bak-githubfix" "%SystemRoot%\System32\drivers\etc\hosts"
ipconfig /flushdns
```

---

# 六、一句话总结

> **"GitHub 被墙"这个说法太粗了。**
> 真实情况是：DNS 把 `github.com` 解析到了一个坏 IP，
> 而 GitHub 的其他十几个 IP 全是通的。
>
> **定位方法就是一句话：绕过 DNS，直接测 IP，再逐个试。**
