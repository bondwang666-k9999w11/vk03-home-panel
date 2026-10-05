# 发布到 GitHub

先审阅源码和文档，并运行测试及 `tools/check_public_tree.py`。本机运行配置、加密 Token、日志和背景素材都不上传。

## 首次上传

在 GitHub 新建公开仓库，例如 `vk03-home-panel`。本工程已自带 README、MIT LICENSE 和 .gitignore，创建远程时不要再次初始化这些文件，避免首次提交冲突。官方步骤见 [创建仓库](https://docs.github.com/en/repositories/creating-and-managing-repositories/creating-a-new-repository)。

在工程目录打开 PowerShell；下面的地址需要改成自己的仓库：

```powershell
git init -b main
git add .
git diff --cached --stat
git commit -m "Release VK03 Home Panel v1.0.0"
git remote add origin https://github.com/YOUR_ACCOUNT/vk03-home-panel.git
git push -u origin main
git tag -a v1.0.0 -m "VK03 Home Panel v1.0.0"
git push origin v1.0.0
```

本机需配置自己的 Git 作者身份，建议使用 GitHub 提供的 noreply 邮箱。不要把 GitHub 登录凭据或访问 Token 写入命令、仓库配置示例或聊天。可使用 GitHub Desktop 的登录和“Publish repository”流程代替命令。

如果仓库已初始化，直接从 `git add .` 开始；如果 `origin` 已存在，先检查它是否是正确目标，不要随意覆盖。

## Release

按 BUILD.md 生成核心 ZIP。仓库主页进入 Releases → Draft a new release，选择 `v1.0.0` 标签，复制 `docs/RELEASE-v1.0.0.md` 的说明，并附上 ZIP。

不要将 EXE、构建缓存、FFmpeg、LHM DLL、PawnIO 安装包提交到源码仓库。发布前在全新目录解压核心 ZIP，确认首启向导、自己绑定后的实体控制和可选组件安装都符合说明。官方步骤见 [管理 Releases](https://docs.github.com/en/repositories/releasing-projects-on-github/managing-releases-in-a-repository)。

## 后续更新

发布新标签，不覆盖已经公开的旧标签。重大配置变化写入 CHANGELOG，并提供迁移说明。接收 issue 时先要求脱敏，禁止请求他人的 HA Token 或完整个人配置。
