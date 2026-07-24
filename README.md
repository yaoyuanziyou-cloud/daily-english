# Daily English Practice - Cloud Edition

GitHub Actions 自动生成每日英语口语练习 + 新闻听力，部署到 GitHub Pages，手机随时访问。

## 功能

- 每天 8:00 (北京时间) 自动生成：
  - 口语练习文章 (200-300词, B1-B2难度, 商务/生活交替)
  - China Daily 新闻听力 (2篇, 附中文翻译)
- 微软 Aria 神经网络语音朗读 (自然逼真)
- 逐句高亮 + 语速调节 + 循环播放
- 词汇/短语单独发音
- 飞书群机器人推送通知
- GitHub Pages 永久在线，无需电脑开机

## 快速设置

### 1. 创建 GitHub 仓库

1. 登录 GitHub，点击 New repository
2. 仓库名随意，例如 `daily-english`
3. 设为 **Public** (免费版 GitHub Pages 需要 Public)
4. 不要勾选任何初始化文件
5. 点击 Create repository

### 2. 上传文件

把 `cloud-repo` 目录下的所有文件推送到这个仓库：

```bash
cd cloud-repo
git init
git add .
git commit -m "Daily English Practice - Cloud Edition"
git branch -M main
git remote add origin https://github.com/你的用户名/daily-english.git
git push -u origin main
```

### 3. 开启 GitHub Pages

1. 进入仓库 Settings → Pages
2. Source 选择 **Deploy from a branch**
3. Branch 选择 `gh-pages`，文件夹选 `/ (root)`
4. 点击 Save
5. 等待几分钟后，你的页面地址是：`https://你的用户名.github.io/daily-english/`

### 4. 配置 Secrets

进入仓库 Settings → Secrets and variables → Actions → New repository secret，添加以下 Secrets：

| Secret 名称 | 值 | 说明 |
|---|---|---|
| `MINIMAX_API_KEY` | 你的 MiniMax API Key | 在 [MiniMax 开放平台](https://platform.minimaxi.com/) 获取 |
| `FEISHU_WEBHOOK_URL` | 飞书机器人 Webhook URL | 见下方飞书配置 |
| `SITE_URL` | `https://你的用户名.github.io/daily-english` | GitHub Pages 地址 (末尾不要加 /) |

**可选 Secret：**

| Secret 名称 | 默认值 | 说明 |
|---|---|---|
| `MINIMAX_BASE_URL` | `https://api.minimaxi.com/v1` | MiniMax API 地址 |
| `MINIMAX_MODEL` | `MiniMax-M3` | 使用的模型 |

### 5. 飞书群机器人配置

1. 打开飞书，创建一个群 (或用现有的群)
2. 群设置 → 群机器人 → 添加机器人 → 选择「自定义机器人」
3. 机器人名字随意，例如 "English Practice Bot"
4. 保存后复制 Webhook 地址 (格式: `https://open.feishu.cn/open-apis/bot/v2/hook/xxxxx`)
5. 把这个地址填到 GitHub Secret 的 `FEISHU_WEBHOOK_URL` 中

### 6. 手动触发测试

1. 进入仓库 Actions 页面
2. 选择 "Daily English Practice" workflow
3. 点击 "Run workflow" 手动触发一次
4. 等待执行完成 (约 3-5 分钟)
5. 检查飞书群是否收到通知
6. 访问 GitHub Pages 地址查看效果

## 文件说明

```
cloud-repo/
├── .github/workflows/
│   └── daily.yml          # GitHub Actions 定时任务
├── generate_content.py    # 调用 MiniMax API 生成内容
├── generate_practice.py   # 生成口语练习 HTML + 神经语音
├── generate_news.py       # 生成新闻 HTML + 神经语音
├── notify_feishu.py       # 飞书通知
├── run_daily.py           # 主调度脚本
├── requirements.txt       # Python 依赖
├── .gitignore
└── README.md
```

## 常见问题

### Q: GitHub Actions 没按时执行？

GitHub 免费版的 cron 定时任务可能有延迟 (最多 15-30 分钟)。如果需要更准时，可以考虑升级到 GitHub Pro 或使用外部 cron 服务触发 workflow_dispatch。

### Q: 新闻抓取失败？

China Daily 网站结构可能变化。脚本已内置 fallback 机制：如果抓取失败，会自动用 MiniMax API 生成模拟新闻内容。

### Q: 如何修改生成时间？

编辑 `.github/workflows/daily.yml` 中的 cron 表达式：
- `0 0 * * *` = 北京时间 8:00 (默认)
- `0 23 * * *` = 北京时间 7:00
- `0 1 * * *` = 北京时间 9:00

### Q: 如何修改语音？

编辑 `generate_practice.py` 和 `generate_news.py` 中的 `VOICE` 变量：
- `en-US-AriaNeural` (默认, 女声)
- `en-US-GuyNeural` (男声)
- `en-GB-SoniaNeural` (英式女声)
- 更多语音见 [edge-tts 文档](https://github.com/rany2/edge-tts)
