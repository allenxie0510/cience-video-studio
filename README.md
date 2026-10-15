# 科普视频工坊 · Science Video Studio

面向中文科普视频的 Agent skill：把可靠知识、三维模型、教学镜头、自然旁白、字幕和确定性导出接到同一时间轴。

## 功能

- 适合空间表达的主题优先真实 3D，支持整体定位、局部特写、剖切、跟拍与曲线对照。
- 多种视觉风格；风格变化不改变科学事实或对象身份。
- 科学来源、适用条件、简化边界与逐项审校记录；不把 AI 审查称为真人专家签审。
- 复用已有中文 TTS 服务，区分字幕文本与发音文本，以实测音频锁定时间轴。
- 处理共面阴影、前后关系、标注避让、字幕安全区和符号穿字问题。
- 输出 MP4、SRT、可交互 HTML、源代码与核验记录。

## 安装与使用

在支持本地 skill 的 Codex 环境中安装到独立目录（目录已存在时先检查现有内容）：

```sh
git clone https://github.com/allenxie0510/cience-video-studio.git ~/.codex/skills/science-video-studio
```

仓库名是 `cience-video-studio`；skill 名称及安装目录为 `science-video-studio`。

示例请求：

> 用 $science-video-studio 制作“磁铁穿过线圈，为什么会产生电流？”的中文科普视频。面向初高中学生，约 3 分钟，优先真实 3D，采用自然温润男声。检查科学依据、讲解条件和标注遮挡。

也可以只要求风格预览、分镜或制作方案，不必自动制作完整影片。

## 环境与工具

需要能够运行本地命令与浏览器的 Agent 环境。当前导出工具使用 Node.js、Python 3、FFmpeg / ffprobe 及已配置的 ego-browser。运行环境检查：

```sh
python3 scripts/pipeline.py doctor
```

- `SKILL.md`：入口及制作流程。
- `references/`：风格、3D 运镜、科学审校、声音、空间关系、学生选题和导出契约。
- `scripts/pipeline.py`：按实际音频构建时间轴、字幕和统一 WAV。
- `scripts/render.mjs`：按页面 `setTime(t)` 逐帧导出 MP4。
- `assets/`：早期平面风格示例及片段清单示例；不是正式 3D 模板。

新主题仍需 Agent 制作对应模型、脚本和场景。本仓库不内置云 TTS 适配器，也不包含 API 密钥、个人声音档案或成片媒体；按当前服务的实际配置与文档接入。

## Anatomy 来源

理念参考 [Anatomy](https://github.com/wheresryan22/anatomy)。本仓库提供视频制作编排与教学约束，不打包上游源码。需要上游工具时按 [接入边界](references/anatomy.md) 获取固定版本，并遵守上游许可证。
