# AI-Skills

这是一个个人创建的 AI skill 分享仓库，用于收集和管理自己编写的技能目录。每个目录代表一个单独的 skill，包含说明文档、脚本和示例。

## Skill 列表

- `agnes-image` 调用免费的 Agnes AI 的生图模型，生成需要的图片

## 技能安装及使用说明

以下示例说明如何将 skill 安装到常见 Agent 环境，并调用对应技能。

- `Claude`
  - 安装方式：将 skill 目录（如 `agnes-image/`）拷贝到 Claude 外部工具或插件管理目录，或通过 Claude 的自定义工具注册功能添加该目录。
  - 调用方式：在 Claude prompt 中定义工具名和参数，Claude 接收到用户描述后调用脚本，例如 `python agnes-image/scripts/agnes_image.py --prompt "生成一张科幻城市图" --output result.png`。

- `Codex`
  - 安装方式：将 skill 目录放在项目仓库中，或放入 Codex/IDE 所在工作区的工具文件夹；确保 `scripts/agnes_image.py` 可执行，并且 Python 环境已配置。
  - 调用方式：让 Codex 生成调用命令或脚本，例如 `python agnes-image/scripts/agnes_image.py --prompt "生成一张卡通风格机器人" --output bot.png`，然后执行。

- `OpenClaw`
  - 安装方式：将 skill 目录注册为 OpenClaw 的自定义工具库，或将 `agnes-image` 目录复制到 OpenClaw 插件目录下。
  - 调用方式：在 OpenClaw 任务流中选择该 skill，并传入参数 `prompt`、`style`、`size`、`output`，由 OpenClaw 触发对应脚本执行。

- `Hermes Agent`
  - 安装方式：将 skill 目录放入 Hermes Agent 的技能插件目录，或在 Hermes 的配置中添加 `agnes-image` 目录路径。
  - 调用方式：通过 Hermes 的 flow 定义一个 skill action，调用 `python agnes-image/scripts/agnes_image.py`，并将用户请求映射为命令行参数。

## 目录结构

- `agnes-image/` - 图片生成 skill，基于 Agnes AI 的图像生成 API。