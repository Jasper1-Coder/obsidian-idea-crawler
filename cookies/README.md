# cookies/ —— 放你的登录凭证（不打包、不外传）

本目录放爬虫需要的网站登录 cookie。**这些是登录凭证，等同于账号密码，请勿提交到 Git / 发给任何人。**

## 需要哪些
- `xiaohongshu.txt` —— **小红书图文抓取必需**。用浏览器插件 **Cookie-Editor** 在 `xiaohongshu.com` 网页版导出 Netscape 格式。
- `douyin.txt` —— **抖音视频转写必需**（B站不需要）。同样用 Cookie-Editor 在 `douyin.com` 网页版导出。

## 怎么导出（以 Chrome + Cookie-Editor 为例）
1. 浏览器登录对应网站（小红书 / 抖音网页版）。
2. 打开 Cookie-Editor 插件 → 点「导出」→ 选「Netscape」格式 → 复制文本。
3. 存成 `cookies/xiaohongshu.txt` 或 `cookies/douyin.txt`（纯文本，每行 `domain\tflag\tpath\tsecure\texpiry\tname\tvalue`）。

## 过期了怎么办
cookie 会在退出登录 / 一段时间后失效。脚本报 "Cookie 缺失 / 未登录 / Sign in to confirm" 时，重新导出覆盖同名文件即可。

## 路径（可被环境变量覆盖，详见 SKILL.md）
- 小红书：`cookies/xiaohongshu.txt`（或 `XHS_COOKIE` 环境变量）
- 抖音：`cookies/douyin.txt`（或 `VIDKNOT_DOUYIN_COOKIE_FILE` 环境变量）
