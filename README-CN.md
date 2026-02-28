# AutoDetection

[English](./README.md)

## 简介

这是一个批量视频筛选工具。

程序会扫描指定目录中的视频文件，读取每个视频的第一帧进行检测，并按规则把视频移动到不同文件夹。

当前支持的筛选能力：

- 严格人物筛选：必须检测到站立的人，并且至少有一张可见的正脸
- 时长筛选：低于用户指定秒数的视频会被单独归类
- 比例筛选：不符合用户指定宽高比的视频会被单独归类
- 重复视频筛选：按文件哈希精确识别重复内容

## 安装

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

也可以直接运行 [run.bat](/d:/GitHub_list/AutoDetectionVideo/run.bat)，脚本会自动创建 `.venv` 并安装依赖。

## 一键运行

编辑 [config.json](/d:/GitHub_list/AutoDetectionVideo/config.json)：

- `root_folder`：要扫描的视频目录，输出目录也会创建在这里
- `pretty`：是否格式化输出 JSON
- `min_duration_seconds`：最小时长，留空则不按时长筛选
- `target_width`：目标宽度，留空则不按比例筛选
- `target_height`：目标高度，留空则不按比例筛选
- `detect_duplicates`：是否开启重复视频检测，填写 `true` 或 `false`

然后运行：

```powershell
.\run.bat
```

## 配置示例

```json
{
  "root_folder": "D:\\videos",
  "pretty": true,
  "min_duration_seconds": "",
  "target_width": "",
  "target_height": "",
  "detect_duplicates": true
}
```

## 输出目录

程序会在 `root_folder` 下创建这些目录：

- `has_person`：满足严格人物规则（站立的人 + 可见脸）
- `no_person`：不满足严格人物规则
- `short_video`：低于配置的最小时长
- `ratio_mismatch`：不符合配置的宽高比
- `duplicate_video`：检测为重复内容

说明：

- 文件会被移动，不是复制
- 如果目标文件名已存在，会自动追加数字后缀
- 扫描时会自动跳过这些输出目录，避免重复处理

## 判定顺序

程序按以下顺序处理文件：

1. 如果启用重复检测，先筛出重复视频
2. 如果配置了最小时长，筛出低于阈值的视频
3. 如果配置了目标宽高比，筛出比例不匹配的视频
4. 对剩余视频执行人物检测，并移动到 `has_person` 或 `no_person`

## 检测逻辑

严格人物检测的判定流程如下：

1. 先读取视频首帧
2. 使用 OpenCV HOG 检测画面中的人体
3. 使用 OpenCV Haar 级联检测人脸和眼睛
4. 只有在“至少检测到一个站立的人”且“至少检测到一张可见脸”时，才判定为通过

## JSON 输出

汇总字段包括：

- `total_video_files`
- `min_duration_seconds`
- `target_width`
- `target_height`
- `detect_duplicates`
- `short_video_count`
- `ratio_mismatch_count`
- `duplicate_video_count`
- `has_person_count`
- `no_person_count`
- `failed_count`
- `results`
- `failed_files`

每个视频结果通常包括：

- `input_path`
- `duration_seconds`
- `width`
- `height`
- `aspect_ratio`
- `has_human`
- `passed`
- `category`
- `duplicate_of`
- `moved_to`

## 注意事项

- 只分析每个视频的第一帧
- 当前实现使用 OpenCV HOG 和 Haar 级联，准确率有限
- “可见脸”是启发式判断，不是专门的遮挡识别模型
- 重复视频检测是基于文件哈希的精确去重，不是基于画面相似度
