# GitHub Pages 房源页部署

## 文件放在哪里

这里不是新的首页。保留你仓库原来的 index.html、音乐、游戏等文件，不要覆盖或删除。
将本 code 文件夹中的内容合并进现有网站仓库的根目录：

```text
仓库根目录/
├── index.html                       # 你原来的首页，保持不变
├── code_artifact.html               # 本次修改的房源页，与首页同级
├── data/
│   └── listings.json                # 初始快照，Actions 自动更新
├── scripts/
│   └── collect.py                   # 服务器端采集
├── tests/
│   └── test_collect.py              # 采集与历史数据保留检查
├── requirements.txt
├── .github/
│   └── workflows/
│       └── rentals.yml              # 定时采集和 Pages 发布
└── 你原有的音乐和其他页面...
```

不要把整个 code 文件夹上传成仓库里的 code 子目录。你的首页当前调用的是 `code_artifact.html`，所以它们必须同级。
`.github` 是以点开头的目录，上传或复制时不能漏掉。仓库已有同名目录时合并目录，保留其他工作流。
DEPLOY.md 可以一起上传，用于查阅，不影响网站。

## 第一次部署

1. 打开已有的网站仓库。将上述文件上传到**默认分支**（通常是 main），保留目录结构并提交。可用 Git 或 GitHub 网页 Add file → Upload files；网页中检查最终确实有 `.github/workflows/rentals.yml`。
2. 打开仓库 Settings → Actions → General。确保允许 GitHub Actions，以及本工作流使用的 GitHub 官方 actions。
3. 在同页 Workflow permissions 选择 **Read and write permissions** 并保存。工作流会将最新 JSON 提交回仓库，需要 contents: write。若组织禁用写权限或默认分支禁止机器人直接提交，需先按组织/分支规则允许该更新方式，否则 Save data 步骤会失败。
4. 打开 Settings → Pages，在 Build and deployment 的 Source 选择 **GitHub Actions**。不要再选 Deploy from a branch。
5. 打开 Actions → **Update rentals and deploy Pages** → Run workflow，选择默认分支并运行。首次上传也会触发；如在启用 Pages 前已失败，设置好后重新运行。
6. 等 build 和 deploy 都成功，在最后的 Deploy 步骤或 Settings → Pages 查看网站网址。
7. 打开 `https://你的用户名.github.io/仓库名/` 访问现有首页，再点房源按钮；也可直接打开 `https://你的用户名.github.io/仓库名/code_artifact.html`。若仓库名本身是 `你的用户名.github.io`，网址中不带仓库名这一段。自定义域名继续使用原来的域名。

不用申请 API Key，不用在 HTML 放 GitHub Token。工作流使用仓库内置的 GITHUB_TOKEN。
如果仓库已配置其他 Pages 发布工作流，应只保留一套发布流程，避免它们交替覆盖网站；可停用旧的 Pages 发布工作流，但保留其他无关工作流。

## 数据如何更新

- 首页用 iframe 打开房源页，调用关系不变。
- 房源页请求相对地址 `./data/listings.json`，不再直接跨域请求房产平台。
- GitHub Actions 的 Linux 服务器请求三个公开平台，提取来源中实际存在的单套链接与字段。
- 每6小时在 UTC 的 00:23、06:23、12:23、18:23 尝试运行，对应北京时间 **08:23、14:23、20:23、次日02:23**。GitHub 可能延迟或跳过繁忙时段的计划任务；默认分支工作流才会定时运行，长期无活动的公共仓库可能停用计划任务。
- 每次推送默认分支，以及手动 Run workflow，也会运行采集和部署。
- 页面“重新读取最新发布数据”只重新加载已发布 JSON，**不会触发新的采集**。要马上重新采集，进入 Actions 手动运行，部署完成再刷新页面。
- 默认房天下、我爱我家各尝试最多3页；贝壳尝试1页。按原始详情 URL 去重。可在工作流 `--pages 3` 调整到1～5页。不是全平台全部房源。
- 某来源失败或记录本次未再出现，旧记录继续保留，但显示为历史，保留最后获取时间。不宣称仍在出租。
- 每次任务后 JSON 自动提交回仓库，再通过 Pages artifact 发布整个现有网站，原首页与资源一并保留。

## 已知限制与排查

- GitHub Pages 只托管静态网页，无法在每个访客打开页面时执行 Python。要按访问即时采集，需要另设在线后端服务；本方案是定时更新。
- 去掉浏览器 CORS 限制不等于平台一定允许采集。GitHub IP 仍可能遭遇403、验证码、登录或页面结构变化。此时页面显示失败并保留历史，不使用虚构房源补齐，不绕过验证码。
- 全部来源失败也会发布最新失败状态及历史记录，工作流会给出 warning。**Actions 绿色表示流程执行和部署成功，不代表全部平台采集成功**，需查看页面的来源状态或 Collect public listings 日志。
- 404：确认 Pages 已启用、deploy 成功、文件在根目录、文件名大小写正确；直接访问 `/data/listings.json` 应能看到 JSON。
- 首页房源按钮打不开：确认首页和 code_artifact.html 同级，不要把房源页多包一层 code 文件夹。
- Save data 步骤403：检查 Workflow permissions、组织规则和默认分支保护。
- 部署等待批准：检查 Settings → Environments → github-pages 的部署保护规则，按仓库规则处理。
- 图片仍由来源平台提供，可能防盗链或下线；图片失败时页面显示占位，不替换成虚构照片。
- 双击本地 HTML 时 fetch JSON 可能被限制。可在仓库根目录运行 `python -m http.server 8000`，再访问 `http://localhost:8000/code_artifact.html`。不要通过本地双击判断线上 JSON 是否可用。

## 本地检查（可选）

```sh
python -m pip install -r requirements.txt
python -m unittest discover -s tests
python scripts/collect.py --pages 1
python -m http.server 8000
```

当前文件已通过 Python 测试和 JavaScript 语法检查。实际平台能否在 GitHub 服务器上访问，以首次 Actions 运行结果为准。尚未替你上传或发布 GitHub 仓库。

参考：[GitHub Pages 自定义工作流](https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages)、[GitHub Actions 定时任务](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule)。
