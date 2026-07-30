# Haru Urara Codex Pet

**把春乌拉拉带进 Codex，同时为所有 Codex 宠物提供真正可执行的视觉 QA。**

[English](README.md) · [PetSight](docs/PETSIGHT.md) ·
[架构](docs/ARCHITECTURE.md) · [选题研究](docs/RESEARCH.md) ·
[故障修复](docs/TROUBLESHOOTING.md)

![春乌拉拉完整 v2 动画与观察方向](artwork/hatch-run/qa/contact-sheet-extended.png)

这不是“只有一张图和安装说明”的空壳仓库。项目包含：

- 完整 Codex v2 宠物：74 个已填充单元（73 个动画/方向帧与 1 个中性
  视线帧）、14 个透明保留格、9 种任务状态、16 个顺时针观察方向；
- **PetSight**：读取最终图集的真实像素，在正常、红色盲、绿色盲、
  蓝黄色盲四种视图和深浅两种背景上检查可读性；
- 可复现、可防路径穿越的 `.codex-pet` 打包器；
- 带锁、先验证、原子替换、自动备份、漂移诊断、修复、卸载和恢复的
  安装器；
- JSON、PNG、HTML 三种审计证据；
- Windows/Linux CI、测试、覆盖率、类型检查、静态检查和发布门禁。

## 安装

从 [最新 Release](https://github.com/KanadeK/haru-urara-codex-pet/releases/latest)
下载 wheel 和 `haru-urara.codex-pet`：

```powershell
python -m pip install .\haru_urara_codex_pet-0.1.0-py3-none-any.whl
urara-pet verify-archive .\haru-urara.codex-pet
urara-pet install --source .\haru-urara.codex-pet
urara-pet doctor --source .\haru-urara.codex-pet
```

wheel 自带已验证宠物，所以安装 wheel 后也可以直接运行：

```powershell
urara-pet install
```

若 Codex 的宠物选择器没有立即刷新，重启一次 Codex。

## 从源码验收

```powershell
git clone https://github.com/KanadeK/haru-urara-codex-pet.git
cd haru-urara-codex-pet
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe scripts\verify.py
```

`scripts/verify.py` 会执行 Ruff、严格 Mypy、完整测试和分支覆盖率、
v2 图集验证、PetSight、两次延时构建的字节级确定性比较、归档安全检查、
wheel/sdist 检查、密钥扫描和文档链接检查。

## PetSight

```powershell
urara-pet audit pet\haru-urara `
  --policy examples\petsight-policy.json `
  --matrix-out build\petsight-matrix.png `
  --json-out build\petsight-report.json `
  --html-out build\petsight-report.html
```

它检查的不是文件名，而是最终 1536×2288 图集的实际像素：轮廓对比度、
不同色觉模式、帧占比、尺寸突变、基线跳动、相邻重复帧、动作幅度、
隐藏 RGB 和蓝幕残留。策略通过 JSON 配置，可以在 CI 中收紧而不用改代码。

![PetSight 的四种色觉模式与两种背景](docs/assets/petsight-matrix.png)

## 失败后的修复

```powershell
# 查明缺失、损坏或字节漂移
urara-pet doctor --source .\haru-urara.codex-pet

# 从已验证来源原子修复，旧版本自动备份
urara-pet repair --source .\haru-urara.codex-pet

# 可恢复卸载
urara-pet uninstall

# 恢复最新的有效备份
urara-pet restore
```

每一个错误都会打印稳定的错误码和具体修复建议。完整映射见
[`docs/TROUBLESHOOTING.md`](docs/TROUBLESHOOTING.md)。

## 选题与权利说明

春乌拉拉是官方存在且有人气基础的角色；选择过程同时核对了官方角色资料、
近年的全球热度证据、Codex Pet 索引以及 GitHub 仓库/代码搜索。我们只能严谨地
表述为“截至检索日期未发现同名 Codex Pet”，不能宣称数学意义上的全网不存在。
完整查询和边界见 [`docs/RESEARCH.md`](docs/RESEARCH.md)。

本项目是非官方、非商业同人项目，与 Cygames、OpenAI 均无隶属或背书关系。
MIT 许可证只覆盖原创代码和文档，不授予第三方角色权利。复用角色素材前请阅读
[`ASSET_TERMS.md`](ASSET_TERMS.md)。
