# IMD — Interactive Markdown

IMD 是带代码执行的 Markdown 编辑器，代码在运行 service 的计算机上执行。  
浏览器提供 GitHub 风格的 preview、block editing 和 full-source editing。  
Svelte 提供界面。  
CodeMirror 提供编辑器。  
每个 document 使用带 PTY 的持久 shell。  

## Scope

IMD 支持 Unix 和 macOS。  
HTTP link 和 directory link 在 macOS 上使用 Google Chrome automation。  
这些操作不需要 browser extension。  
Image output、rich output、run-all、reset 和 full-screen terminal 程序不在 version 1 范围内。  

## Session design

同一操作系统用户的所有 session 共用一个后台 service 和一个固定 HTTP port。  
第一个 session 启动 service。  
关闭最后一个 session 会停止 service 并释放 port。  
port 冲突会报告 error。  
每个 session 有自己的 access token、固定 start directory、document 和 shell。  
Session number 在 service 重启后继续递增。  
打开 document 不会执行代码。  

### CLI and Python API

两个接口使用相同的实现、operation name、argument、行为和 session 信息。  

| Operation | CLI | Python API | Result |
| --- | --- | --- | --- |
| 创建 session | `imd open` | `imd.open()` | 一个 session |
| 列出 live session | `imd list` | `imd.list()` | 当前用户的全部 live session |
| 关闭一个 session | `imd close <number>` | `imd.close(number)` | 停止该 session 并保留其 file |
| 关闭全部 session | `imd close` | `imd.close()` | 停止全部 session 并保留其 file |

Open 不接受 argument，并使用当前 working directory。  
每次 open 在 `/tmp/<current absolute directory>/` 下创建一个空 Markdown file。  
IMD 会创建缺失的 directory，并且从不覆盖已有 file。  
File name 使用本地时间、process ID 和随机后缀：`yyyy-MM-ddTHH-mm-ss-<pid>-<random>.md`。  
操作系统可以删除这些临时 document。  
Open 把控制权交回调用方，并且不打开浏览器。  

CLI 为每个 session 打印 `(http_address, cwd, file1, file2, ...)`。  
该 address 包含 access token。  
File path 是绝对路径，并按 panel 顺序排列。  
空 list 和成功的 close 不打印文本。  
CLI 失败会报告 error。  

Python API 的 open 返回 `Session`，list 返回 `Session` 对象列表，close 返回 `None`。  
API 调用不打印文本，失败时 raise exception。  

| Session field | Meaning |
| --- | --- |
| `url` | 带 access token 的 session address |
| `cwd` | 绝对 start directory |
| `paths` | 按 panel 顺序排列的绝对 document path 元组 |
| `number` | 来自 URL path 的正整数 |
| `port` | Public URL 的 port；缺省时 HTTP 为 80，HTTPS 为 443 |

Close 只接受一个可选的正数 session number。  
Document 内的调用不能通过任一接口用 number 关闭自己的 session。  
该 session 之外的调用可以关闭它。  
不带 number 的调用可以关闭全部 session，包括调用方自己的 session。  
IMD 最后关闭调用方的 session，所以该调用可能不返回。  
Close 会尝试每一个选中的 session，并报告任何 error。  
外部 close 在关闭最后一个 session 时，会等待 service shutdown。  
没有 session 时，不带 number 的 close 会成功，并且不启动 service。  

### Access and service state

每个 session URL 使用 `/<number>/#token=<token>`。  
页面把 token 从 address bar 移到该 tab 的 `sessionStorage`。  
刷新同一 tab 会保持访问。  
新 tab 需要带 token 的完整 URL。  
Service 接受任意 HTTP Host name。  
本地 session operation 使用 Unix socket，并且只允许当前用户访问。  

Session record 存放在 `~/.imd/sessions.json`。  
每条 record 存储 number、address、start directory、document path 和 service process ID。  
List 和 close 会删除已不在运行的 process 的 record。  
`~/.imd` directory 只允许当前用户访问。  
Service log 写入 `~/.imd/server.log`。  
每次启动 service 都会替换该 log file。  

## Document design

### Panels and editing

每次点击 file 都会在页面右端增加一个 panel，包括重复点击同一 file。  
Panel 等宽，没有 panel 数量上限，也没有关闭或调整宽度的控件。  
在同一 session 内，同一 file 的 panel 共用一个 document 和 shell。  
每个 panel 保留自己的未保存 draft。  
不同 document 使用不同的 shell。  

后缀为 `.md` 或 `.markdown` 的 file 支持编辑和执行。  
其他 UTF-8 文本 file 显示只读文本，并带 Read-only 标签。  
Binary file 和缺失 path 会报告 error。  

Markdown panel 显示 file name、Local badge、Document 和 Source 控件，以及 save status。  
窄 panel 会隐藏 Local badge。  
底栏显示绝对 file path 和 `Markdown · Shell`。  
只读 panel 没有 Document 或 Source 控件。  
浏览器标题列出已打开的 file name，用 ` | ` 分隔，然后是 ` · IMD`。  

Document view 支持 block editing，以及添加 text 或 code 的控件。  
新的 code block 使用 `python` tag。  
Click、Enter 或 Space 开始编辑选中的 block。  
Source view 编辑完整 Markdown document。  

| Control | Behavior |
| --- | --- |
| 编辑器中的 Enter | 添加一行 |
| code block 中的 Shift + Enter | Save 并 run 该 block |
| Source view 中的 Shift + Enter | Run 光标所在的 code block |
| Markdown block editor 中的 Shift + Enter | Save，不执行 |
| Ctrl + S 或 Cmd + S | Save |
| 编辑器中的 Tab | 无动作 |

编辑器不显示 completion menu。  

### Markdown and images

Preview 支持 table、strikethrough 和 task list，但不渲染 raw HTML。  
本地 image path 使用 document directory，并且必须留在该 directory 内。  
支持的后缀是 `.png`、`.jpg`、`.jpeg`、`.gif`、`.webp`、`.svg`、`.avif`、`.ico` 和 `.bmp`。  
Image 只在 document 打开后加载。  
Image request 不在 URL 中包含 session token。  

### Save and conflicts

IMD 在 execution 之前、execution output 之后，以及 Cmd + click 打开 link 之前进行 save。  
编辑器失去 focus，或用户切换浏览器 window 或 tab 时，IMD 也会 save。  
Document 正在 run code 时，拒绝用户 save。  
IMD 在 execution 期间阻止点击 link，并要求用户等待。  
Save 失败会阻止打开 link。  
Save 保留原来的 LF 或 CRLF line ending 和 file mode。  
有未保存更改或正在运行的 block 时，关闭 tab 前浏览器会询问。  

Panel 读取 file 之后，如果 file 又发生变化，save 会失败。  
这条规则适用于另一个 program 或另一个 panel 的更改。  
Conflict 会保持 file 不变，并显示 error。  
使用 Download current content 保留 draft，然后 reload document。  

### Links

Cmd + click 处理 preview、block editor、Source view、code block 和 output 中的 link。  
只有以 `http://` 或 `https://` 开头的文本才是 HTTP link。  

HTTP link 会选中匹配的 Chrome tab，并且不改变或 reload 其页面。  
匹配使用 protocol、host 和 effective port，host 不区分字母大小写。  
默认 port 是 HTTP 的 80 和 HTTPS 的 443。  
Path、query parameter 和 fragment 不影响 HTTP link 匹配。  
`localhost` 和 `127.0.0.1` 是不同的 host。  
IMD 按从前到后搜索所有 Chrome window，并按从左到右搜索 tab。  
IMD 会还原并选中第一个匹配的 window 和 tab。  
如果没有 tab 匹配，IMD 在最前面的 window 打开一个 tab，或创建一个 window。  
Automation 失败会显示 error。  
macOS 可以在首次使用时请求控制 Chrome 的 permission。  

本地 link 接受绝对 path 和相对 path。  
相对 path 使用固定的 session start directory，即使 shell 之后更改了 directory。  
Path 可以以 `./` 或 `../` 开头，包含 `/`，或命名一个 file，例如 `README.md`。  
不含 `/` 的 directory name 需要 `./` 前缀。  
带空格的 path 需要引号、backtick 或 Markdown link。  
File link 按上文规则打开 panel。  

Directory link 会选中具有相同 resolved start directory 的最新 live session。  
如果不存在，IMD 在该 directory 中使用 open operation。  
IMD 在 Chrome 中打开该 session，并且不向当前页面添加 panel。  
与 HTTP link 匹配不同，directory session 匹配还使用 URL path。  

## Execution design

### Shell and Python

第一次 execution 在 session start directory 中启动 document shell。  
Shell 必须在 30 秒内完成启动，否则报告 error。  
IMD 使用 `$SHELL`；如果没有 `$SHELL`，则使用用户的 login shell。  
Shell 以 interactive mode 启动，不使用 login mode，并加载其 configuration。  
IMD 需要 POSIX-compatible shell，并拒绝 `fish`、`csh` 和 `tcsh`。  
Shell 在 block 之间保留 environment variable、alias、function、working directory 和 option。  
Shell 停止时，shell state 结束。  

| Language tag | Execution |
| --- | --- |
| 无 tag 或 `shell` | 在 document shell 中 source 该 block |
| `python` | 用 document shell 中的 `python3` 运行新 script |
| 任何其他 tag，包括 `py` | 报告 error 并且不运行 |

Language tag 忽略字母大小写。  
Shell command 不需要 `!` 前缀。  
Python 继承 shell 已 export 的 environment 和 working directory。  
Python 在 block 之间不保留 state，也不打印最后一个 expression 的值。  
Standard output 和 standard error 都出现在 output region。  
一个 document 同一时间只运行一次 execution。  
Background job 可以在 block 结束后继续，其后续 output 出现在下一次 execution 中。  
以 `__imd_` 开头的 name 属于 IMD。  

### Output and input

Execution 期间，相邻的 output region 显示 100 column、24 row 的 terminal。  
Terminal 把每个按键发给 PTY，并且不自动添加 newline。  
Program 控制 Space、方向键、Enter，以及 Python `input()` 这类 input。  
Progress update 在 cursor 位置替换文本。  
Execution 结束时，IMD save 最终文本，并将其渲染为 Markdown，不显示 exit code。  
空的 output region 显示 `(no output)`。  

每个 output region 使用唯一 ID，并写在两行 marker 中：  

```markdown
<!-- imd:output:begin ID -->

Output content

<!-- imd:output:end ID -->
```

Preview 隐藏这些 marker。  
Output 内的 code block 支持编辑和执行。  
它们的 output 留在父 output region 内。  
每次 run 会替换相邻 output region 及其全部 nested content。  
`out` tag 没有特殊含义，也不用来标识 output region。  

Code block 和 output region 有 Del 控件。  
删除 code 也会删除其相邻 output region。  
删除 output 会删除两个 marker 及其内容。  
Deletion 立即 save，并且不打开 confirmation dialog。  
Document 正在 run code 时，Delete 控件保持 disabled。  

### Stop and close

Stop 和 terminal Ctrl+C 向 foreground process group 发送 interrupt。  
如果 shell 在 interrupt 后仍然存活，它会保留其 state。  
Stop 之后，如果 execution 仍在继续，Kill 可用。  
Kill 停止 shell process group，并在 output 中 save `The shell stopped. The state is lost.`。  
下一次 execution 启动一个新 shell。  

浏览器断开连接会 interrupt execution，但不会 kill shell，并 save 最终文本。  
关闭 document 会 interrupt execution，并在停止 shell 前最多等待两秒。  
Close 会释放 shell、其子 process、PTY 和 execution 临时 file。  
Document file 仍留在磁盘上。  

## Install and start

本项目需要 Python 3.11 或更新版本、uv，以及用于 frontend build 的 Node.js 22.12 或更新版本。  
从项目 directory 安装该 tool：  

```sh
uv tool install .
```

每次 wheel build 都会安装 frontend dependency，并用 npm rebuild frontend。  
Wheel 包含 `imd/static` 中生成的 file，该目录不进入 Git。  

可从任意 directory 运行：  

```sh
imd open
imd list
imd close 1
```

在浏览器中打开打印出的 URL。  
在 close command 中使用 URL path 里的实际 session number。  

从 Python 使用相同 operation：  

```python
import imd

session = imd.open()
print(session.url, session.cwd, session.paths, session.number)
imd.close(session.number)
```

### Server configuration

每次 open 都用当前用户的 permission 读取 `~/.imd/config.py`。  
该 file 定义名为 `config` 的 Python dictionary。  
缺少该 file 时使用下面的 default。  
无效 file 会报告其 path 和 error。  

```python
config = {
    "host": "0.0.0.0",
    "port": 8000,
}
```

`host` 接受 IPv4 或 IPv6 listen address。  
`port` 设置固定 HTTP port。  
可选的 `public_url` 设置打印出的 HTTP 或 HTTPS origin，可带 port，但不能有 path、query 或 token。  
没有 `public_url` 时，IMD 用 `host` 和 `port` 构造 HTTP URL。  
对于 HTTPS reverse proxy，使用类似这样的 configuration：  

```python
config = {
    "host": "127.0.0.1",
    "port": 8000,
    "public_url": "https://imd.example.com",
}
```

Proxy 提供 HTTPS，并把 request 原样转发到 listen address，保留其 path。  
设置 `public_url` 不会配置 proxy。  
正在运行的 service 保持其初始 setting。  
更改 configuration 后，先运行 `imd close`，再运行 `imd open`。  
如果 configuration file 有 error，list 和 close 仍然可用。  

## Development

本项目使用 uv，并把 `uv.lock` 保留在 Git 中。  
`uv sync` 以 editable mode 安装 package，并安装 `dev` dependency group。  
Editable install 需要单独的 frontend build：  

```sh
uv sync
npm --prefix web ci
npm --prefix web run build
uv run imd open
```

完成上述 setup 后，在项目 directory 运行检查：  

```sh
uv run pytest -q
npm --prefix web run check
cd web
npx playwright install chromium
npm run test:e2e
```

Browser test 使用 `.venv/bin/python` 和临时 document。  
Test 不在用户 document 中执行代码。  
