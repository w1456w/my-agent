# 实验2 RAG个人知识库助手 学生骨架 v2.1 编码修订版

配套《实验2 RAG个人知识库助手实验操作手册 学生简明版 v3.0》。使用 Python 3.12 和标准库，无需安装第三方包。

## 先按这5步操作

1. 解压到一个新文件夹，不要覆盖已有的配置、代码或学生作业。
2. 双击 `check_local.cmd`，先做基础离线检查。此检查不需要密钥，也不请求真实接口。
3. 首次复制 `config.example.json`，将副本命名为 `config.json`，填入教师提供的 `endpoint`、`model`、`embedding_endpoint`、`embedding_model`，其他设置先保持默认。
4. 双击 `start_assistant.cmd`。缺少配置时会有中文提示；按提示补齐后重新启动。对话与嵌入密钥在运行时分别输入，不回显，不写入配置；两个接口共用密钥时，第二次直接回车。
5. 出现“你>”后输入 `/index` 建库，再按手册完成代码修改、问答和对照实验。原始3份虚构资料按默认设置会生成6个片段。

## 需要自己完成的两处代码

打开 `rag_core.py`：

- `select_top_k`：按 `score` 从大到小排序，再取前 `k` 条。
- `build_rag_messages`：用 `format_context(hits)` 把编号、文件名、资料正文和当前问题放进本轮 `user` 消息，保留历史顺序。

两处故意留给学生补全。未修改时运行学生任务检查应不通过，这是正常状态，不是程序故障。修改后保存；在助手中先输入 `/quit`，回到该文件夹的 PowerShell 再运行：

```powershell
.\check_local.cmd --student
```

通过后重新启动助手。代码或 `config.json` 改过都要重启；资料、分块设置或嵌入模型改过还需重新 `/index`。

## 常用命令

- `/index`：读取 `data`，生成供检索使用的 `index.json`。
- `/search 完整问题`：只查看检索结果；可能调用嵌入接口，不调用回答模型。
- `/mode direct`、`/mode rag`：切换不附资料与附检索资料两种模式，并开始新会话。
- `/k 1`、`/k 3`：改变取回的片段数，并开始新会话。
- `/new`：清空对话；旧日志和 `index.json` 保留。
- `/show`：查看上次请求的片段、消息和状态。清空后要先问新问题，再用它检查新会话。
- `/quit`：退出助手，回到 PowerShell。

`questions.csv` 有10道公开练习题：8道有答案、2道资料外问题。每题在两种模式各问一次，提问前 `/new`；错误回答也要保留。不要把 `questions.csv` 放进 `data`。

## 文件编码与记录

包内 `.py`、`.md`、`.json`、`.csv` 统一使用 UTF-8 BOM 和 Windows 换行，便于记事本、VS Code 及 Windows PowerShell 识别中文；CSV加BOM以兼容Excel直接打开。旧应用若仍显示乱码，请明确选择“UTF-8”编码打开，不要按ANSI或GBK另存。两个 `.cmd` 启动器为ASCII文件和Windows换行。

程序在 `logs` 中保存实际片段、相似度、请求消息，以及回答、用量、状态等选定字段；不是完整的原始接口回包。日志和 `index.json` 会含资料正文，提交前确认资料允许共享，且不含真实密钥。

## 教师课前接入

教师须提供可用的对话、文本嵌入接口，并预留调用额度。接入层使用完整HTTPS地址和Bearer鉴权：对话按Chat Completions格式发送并读取 `choices`；嵌入发送文本列表，读取 `data` 中的 `index`、`embedding`。协议或参数不同须先适配代码，批量上限也须按学校服务调整。

若学校提供独立的Python程序路径，可由教师设置环境变量RAG_LAB_PYTHON为该python.exe的完整路径，启动器会使用它；否则使用py -3.12。

本包离线检查使用模拟响应，不代表学校真实接口已经连通。教师应实际完成一次建库和问答后再开课。
