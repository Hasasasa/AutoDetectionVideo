# AutoDetection

[中文说明](./README-CN.md)

## Overview

This is a batch video filtering tool.

It scans videos in a target folder, reads the first frame of each video, and moves files into different folders based on filtering rules.

Current features:

- Strict person filtering: requires a standing person and at least one visible frontal face
- Duration filtering: videos shorter than a user-defined threshold are separated
- Aspect ratio filtering: videos that do not match the user-defined width/height ratio are separated
- Duplicate detection: exact duplicate files are detected by file hash

## Installation

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

You can also run [run.bat](/d:/GitHub_list/AutoDetection/run.bat) directly. It will create `.venv` and install dependencies automatically.

## One-Click Run

Edit [config.json](/d:/GitHub_list/AutoDetection/config.json):

- `root_folder`: source folder to scan; output folders are created inside it
- `pretty`: whether to pretty-print JSON output
- `min_duration_seconds`: minimum duration; leave empty to disable duration filtering
- `target_width`: target width; leave empty to disable aspect ratio filtering
- `target_height`: target height; leave empty to disable aspect ratio filtering
- `detect_duplicates`: enable duplicate detection with `true` or `false`

Then run:

```powershell
.\run.bat
```

## Example Config

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

## Output Folders

The tool creates these folders under `root_folder`:

- `has_person`: matches the strict rule (standing person + visible face)
- `no_person`: does not match the strict person rule
- `short_video`: shorter than the configured duration threshold
- `ratio_mismatch`: does not match the configured aspect ratio
- `duplicate_video`: detected as duplicate content

Notes:

- Files are moved, not copied
- If a target filename already exists, a numeric suffix is added
- These output folders are skipped during scanning to avoid reprocessing

## Processing Order

The tool processes files in this order:

1. If enabled, detect duplicates first
2. If configured, filter videos shorter than the minimum duration
3. If configured, filter videos that do not match the target aspect ratio
4. Run person detection on the remaining videos and move them to `has_person` or `no_person`

## Detection Logic

The strict person detection rule works like this:

1. Read only the first frame of the video
2. Use OpenCV HOG to detect people in that frame
3. Use OpenCV Haar cascades to detect faces and eyes
4. Mark the video as passed only if at least one standing person and at least one visible face are detected

## JSON Output

Summary fields include:

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

Each video result may include:

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

## Notes

- Only the first frame of each video is analyzed
- The current implementation uses OpenCV HOG and Haar cascades, so accuracy is limited
- "Visible face" is a heuristic, not a dedicated occlusion model
- Duplicate detection is exact hash-based deduplication, not perceptual similarity matching
