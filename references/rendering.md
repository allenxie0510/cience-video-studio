# 确定性导出契约

页面提供 `window.__VIDEO__ = {duration, setTime(seconds)}`。`setTime` 可同步或返回 Promise，必须可任意跳转，重复调用同一时刻画面相同。可选 `setStyle(id)` 让同一个模型切换风格。渲染器等待字体就绪；外部素材应本地化并在 `setTime` 内等加载完成。

`?export=1` 时只展示成片画布，隐藏播放器按钮；视口决定画幅。停止 requestAnimationFrame 自动播放、CSS transition/animation 和未固定随机。依赖弹簧/物理积分时预计算或从固定起点重放，不能以录制帧率改变模拟结果。

`pipeline.py prepare lesson.json --out build [--draft]` 生成时间轴。lesson.json 格式：

```json
{
  "title": "题目",
  "segments": [
    {
      "id": "s01",
      "narration": "这是一句字幕和旁白。",
      "spoken_text": "这是一句合成用的文字。",
      "audio": "audio/s01.wav",
      "tail": 0.25,
      "focus": ["gear-input"],
      "action": "rotate",
      "claims": ["c01"]
    }
  ]
}
```

草稿去掉 audio，填 `draft_duration`（包含 tail），并用 `--draft`。每段生成 start、speech_end、end。字幕生成到 speech_end；画面在 end 前完成停留。片段内动作关键点使用相对时间或比例，换配音后从新的时间轴重新计算。

随附齿轮示例可直接跑通时间轴到页面：

```bash
python3 scripts/pipeline.py prepare assets/example-lesson.json --out /absolute/demo/build --draft
python3 scripts/pipeline.py preview /absolute/demo/build/timeline.json --out /absolute/demo/preview.html
```

`preview` 为内置齿轮示例专用，片段 `scene=0/1/2` 分别表示认识对象、观察旋向、解释速比。它把完整时间轴嵌入页面，离线也能播放。新主题应编写对应场景模板；不能只替换这份例子的旁白就声称完成其他主题。模板绑定后的页面沿用实测片段边界和字幕结束时间。

渲染入口：

```bash
node scripts/render.mjs --url 'http://127.0.0.1:PORT/preview.html?export=1&style=precision' --out /absolute/final.mp4 --space SPACE_ID --width 1280 --height 720 --fps 30 --audio /absolute/build/narration.wav
```

不填 `--audio` 输出明确的静音预览；`--seconds 2` 仅用于短导出测试。脚本使用 ego-browser 已有 TaskSpace，按帧调用 setTime 并将截图送到 FFmpeg，支持含空格路径。不抓取声音，不录浏览器 UI，不通过实时屏幕录制积累掉帧误差。`--space` 必须是当前目标的空间；同一任务复用一个空间。渲染器不结束已有空间，由调用者完成质检后结束。

浏览器页面自带字幕时，MP4 有烧录字幕；否则 render.mjs 不自动烧字幕。SRT 作为独立文件交付。有声导出前须校验时间轴与页面 duration 相等；脚本拒绝音轨时长与当前导出长度相差超过 0.15 秒，避免尾部被静默裁切。短测试需使用相同长度的测试音轨。

## 3D 镜头与叠层

镜头编排见 [3D 与镜头编排](cinematic-direction.md)。沿用同一个 `__VIDEO__` 导出契约，不另建以墙钟运行的录屏时间轴。

- `setTime(t)` 必须先更新模型、相机姿态/目标、剖面和布局，再提交 WebGL/其他渲染器的实际绘制；若异步绘制，返回 Promise，在帧完成后才截图。只修改场景数据而依赖下一次自动循环会产生错帧。
- 初始化时等待模型、材质、字体和 shader 首次编译完成；以 ready 状态或 `setTime` 的 Promise 表达。粒子固定种子并从 t 求状态，不靠积累帧数运动。
- 世界标注先更新矩阵再投影到屏幕；处理遮挡。字幕、读数和二维曲线作为明确的屏幕叠层，与相机共享最新状态和时间。
- 交互 OrbitControls 等用户相机控制在导出模式中禁用，确定性相机轨迹仍运行；“禁用交互”不等于把相机冻结在默认机位。
- 默认输出依旧兼容逐帧浏览器渲染。若选 Blender 等离线引擎，由该引擎按同一帧时间导出，再合成相同音轨/字幕；当前 `render.mjs` 不自动驱动 Blender，不宣称已有现成适配器。
