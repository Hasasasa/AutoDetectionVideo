from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from dataclasses import asdict, dataclass
from pathlib import Path

import cv2


@dataclass
class FaceResult:
    bbox: tuple[int, int, int, int]
    visible: bool
    eye_count: int


@dataclass
class PersonResult:
    bbox: tuple[int, int, int, int]
    standing: bool
    aspect_ratio: float


@dataclass
class DetectionResult:
    input_path: str
    duration_seconds: float
    width: int
    height: int
    aspect_ratio: float | None
    person_count: int
    standing_person_count: int
    face_count: int
    visible_face_count: int
    has_human: bool
    passed: bool
    persons: list[PersonResult]
    faces: list[FaceResult]
    reason: str


class CoverDetector:
    def __init__(self) -> None:
        self.hog = cv2.HOGDescriptor()
        self.hog.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())

        cascade_root = Path(cv2.data.haarcascades)
        self.face_cascade = cv2.CascadeClassifier(
            str(cascade_root / "haarcascade_frontalface_default.xml")
        )
        self.eye_cascade = cv2.CascadeClassifier(str(cascade_root / "haarcascade_eye.xml"))

        if self.face_cascade.empty() or self.eye_cascade.empty():
            raise RuntimeError("OpenCV haar cascade files are not available.")

    def load_cover(
        self, path: Path
    ) -> tuple[str, cv2.typing.MatLike, float, int, int, float | None]:
        capture = cv2.VideoCapture(str(path))
        fps = float(capture.get(cv2.CAP_PROP_FPS) or 0.0)
        frame_count = float(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0.0)
        width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
        height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
        ok, frame = capture.read()
        capture.release()
        if not ok or frame is None:
            raise ValueError(f"Cannot read video cover frame: {path}")
        duration_seconds = 0.0
        if fps > 0:
            duration_seconds = frame_count / fps
        aspect_ratio = None
        if width > 0 and height > 0:
            aspect_ratio = round(width / height, 4)
        return str(path), frame, round(duration_seconds, 3), width, height, aspect_ratio

    def detect_people(self, frame: cv2.typing.MatLike) -> list[PersonResult]:
        boxes, _weights = self.hog.detectMultiScale(
            frame, winStride=(8, 8), padding=(8, 8), scale=1.03
        )
        people: list[PersonResult] = []
        for x, y, w, h in boxes:
            ratio = h / max(w, 1)
            standing = bool(ratio >= 1.8 and h >= 120)
            people.append(
                PersonResult(
                    bbox=(int(x), int(y), int(w), int(h)),
                    standing=standing,
                    aspect_ratio=round(float(ratio), 3),
                )
            )
        return people

    def detect_faces(self, frame: cv2.typing.MatLike) -> list[FaceResult]:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.equalizeHist(gray)
        faces = self.face_cascade.detectMultiScale(
            gray, scaleFactor=1.1, minNeighbors=5, minSize=(48, 48)
        )

        results: list[FaceResult] = []
        for x, y, w, h in faces:
            face_roi = gray[y : y + h, x : x + w]
            eyes = self.eye_cascade.detectMultiScale(
                face_roi, scaleFactor=1.1, minNeighbors=4, minSize=(12, 12)
            )
            visible = bool(len(eyes) >= 1)
            results.append(
                FaceResult(
                    bbox=(int(x), int(y), int(w), int(h)),
                    visible=visible,
                    eye_count=len(eyes),
                )
            )
        return results

    def evaluate(self, path: Path) -> DetectionResult:
        input_path, frame, duration_seconds, width, height, aspect_ratio = self.load_cover(path)
        persons = self.detect_people(frame)
        faces = self.detect_faces(frame)

        standing_count = sum(1 for p in persons if p.standing)
        visible_face_count = sum(1 for f in faces if f.visible)
        has_human = bool(len(persons) > 0 or len(faces) > 0)

        if standing_count == 0:
            passed = False
            reason = "No standing person detected."
        elif visible_face_count == 0:
            passed = False
            reason = "No visible face detected."
        else:
            passed = True
            reason = "At least one standing person and one visible face detected."

        return DetectionResult(
            input_path=input_path,
            duration_seconds=duration_seconds,
            width=width,
            height=height,
            aspect_ratio=aspect_ratio,
            person_count=len(persons),
            standing_person_count=standing_count,
            face_count=len(faces),
            visible_face_count=visible_face_count,
            has_human=has_human,
            passed=passed,
            persons=persons,
            faces=faces,
            reason=reason,
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Scan a folder of videos and sort them by whether a human is detected."
    )
    parser.add_argument(
        "input",
        nargs="?",
        help="Path to a folder that contains video files.",
    )
    parser.add_argument(
        "--output",
        default="output",
        help="Base output directory. Default: ./output",
    )
    parser.add_argument(
        "--config",
        help="Path to a JSON config file that provides input/output settings.",
    )
    parser.add_argument(
        "--pretty",
        action="store_true",
        help="Pretty-print JSON output.",
    )
    return parser.parse_args()


def iter_video_files(folder: Path) -> list[Path]:
    video_suffixes = {
        ".mp4",
        ".mov",
        ".avi",
        ".mkv",
        ".wmv",
        ".flv",
        ".webm",
        ".m4v",
        ".mpg",
        ".mpeg",
    }
    skipped_dirs = {
        "has_person",
        "no_person",
        "short_video",
        "ratio_mismatch",
        "duplicate_video",
    }
    files: list[Path] = []
    for path in folder.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix.lower() not in video_suffixes:
            continue
        if any(part in skipped_dirs for part in path.parts):
            continue
        files.append(path)
    return sorted(files)


def ensure_unique_path(target_dir: Path, source_path: Path) -> Path:
    candidate = target_dir / source_path.name
    if not candidate.exists():
        return candidate

    index = 1
    while True:
        candidate = target_dir / f"{source_path.stem}_{index}{source_path.suffix}"
        if not candidate.exists():
            return candidate
        index += 1


def compute_file_hash(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(chunk_size)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def load_config(config_path: Path) -> dict[str, object]:
    if not config_path.exists() or not config_path.is_file():
        raise ValueError(f"Config file does not exist: {config_path}")

    with config_path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)

    if not isinstance(data, dict):
        raise ValueError("Config file must contain a JSON object.")
    return data


def parse_optional_float(value: object, field_name: str) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} must be a number or empty.") from exc


def parse_optional_bool(value: object, default: bool = False) -> bool:
    if value in (None, ""):
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1", "yes", "y", "on"}:
            return True
        if normalized in {"false", "0", "no", "n", "off"}:
            return False
    raise ValueError("detect_duplicates must be true/false or empty.")


def resolve_settings(
    args: argparse.Namespace,
) -> tuple[Path, Path, bool, float | None, int | None, int | None, bool]:
    input_value = args.input
    output_value = args.output
    pretty_value = args.pretty
    min_duration_seconds: float | None = None
    target_width: int | None = None
    target_height: int | None = None
    detect_duplicates = False

    if args.config:
        config = load_config(Path(args.config))
        root_value = config.get("root_folder")
        if root_value is not None:
            input_value = root_value
            output_value = root_value
        else:
            input_value = config.get("input_folder", input_value)
            output_value = config.get("output_folder", output_value)
        pretty_value = bool(config.get("pretty", pretty_value))
        min_duration_seconds = parse_optional_float(
            config.get("min_duration_seconds"), "min_duration_seconds"
        )
        parsed_width = parse_optional_float(config.get("target_width"), "target_width")
        parsed_height = parse_optional_float(config.get("target_height"), "target_height")
        if parsed_width is not None:
            target_width = int(parsed_width)
        if parsed_height is not None:
            target_height = int(parsed_height)
        detect_duplicates = parse_optional_bool(config.get("detect_duplicates"), False)

    if not input_value:
        raise ValueError("An input folder is required. Pass it directly or set root_folder in config.")

    return (
        Path(str(input_value)),
        Path(str(output_value)),
        pretty_value,
        min_duration_seconds,
        target_width,
        target_height,
        detect_duplicates,
    )


def process_folder(
    folder: Path,
    output_root: Path,
    pretty: bool,
    min_duration_seconds: float | None,
    target_width: int | None,
    target_height: int | None,
    detect_duplicates: bool,
) -> dict[str, object]:
    if not folder.exists() or not folder.is_dir():
        raise ValueError(f"Input folder does not exist or is not a directory: {folder}")

    detector = CoverDetector()
    has_person_dir = output_root / "has_person"
    no_person_dir = output_root / "no_person"
    short_video_dir = output_root / "short_video"
    ratio_mismatch_dir = output_root / "ratio_mismatch"
    duplicate_video_dir = output_root / "duplicate_video"
    has_person_dir.mkdir(parents=True, exist_ok=True)
    no_person_dir.mkdir(parents=True, exist_ok=True)
    short_video_dir.mkdir(parents=True, exist_ok=True)
    ratio_mismatch_dir.mkdir(parents=True, exist_ok=True)
    duplicate_video_dir.mkdir(parents=True, exist_ok=True)

    video_files = iter_video_files(folder)
    results: list[dict[str, object]] = []
    failed_files: list[dict[str, str]] = []
    has_person_count = 0
    no_person_count = 0
    short_video_count = 0
    ratio_mismatch_count = 0
    duplicate_video_count = 0
    seen_hashes: dict[str, str] = {}

    for video_path in video_files:
        try:
            duplicate_of: str | None = None
            if detect_duplicates:
                file_hash = compute_file_hash(video_path)
                duplicate_of = seen_hashes.get(file_hash)
                if duplicate_of is None:
                    seen_hashes[file_hash] = str(video_path)

            if duplicate_of is not None:
                target_dir = duplicate_video_dir
                target_path = ensure_unique_path(target_dir, video_path)
                shutil.move(str(video_path), str(target_path))
                duplicate_video_count += 1
                results.append(
                    {
                        "input_path": str(video_path),
                        "duration_seconds": None,
                        "width": None,
                        "height": None,
                        "aspect_ratio": None,
                        "person_count": 0,
                        "standing_person_count": 0,
                        "face_count": 0,
                        "visible_face_count": 0,
                        "has_human": False,
                        "passed": False,
                        "persons": [],
                        "faces": [],
                        "reason": "Duplicate video detected.",
                        "category": "duplicate_video",
                        "duplicate_of": duplicate_of,
                        "moved_to": str(target_path),
                    }
                )
                continue

            result = detector.evaluate(video_path)
            if (
                min_duration_seconds is not None
                and result.duration_seconds > 0
                and result.duration_seconds < min_duration_seconds
            ):
                target_dir = short_video_dir
                short_video_count += 1
                category = "short_video"
            elif (
                target_width is not None
                and target_height is not None
                and result.aspect_ratio is not None
                and round(target_width / target_height, 4) != result.aspect_ratio
            ):
                target_dir = ratio_mismatch_dir
                ratio_mismatch_count += 1
                category = "ratio_mismatch"
            elif result.passed:
                target_dir = has_person_dir
                has_person_count += 1
                category = "has_person"
            else:
                target_dir = no_person_dir
                no_person_count += 1
                category = "no_person"
            target_path = ensure_unique_path(target_dir, video_path)
            shutil.move(str(video_path), str(target_path))

            payload = asdict(result)
            payload["moved_to"] = str(target_path)
            payload["category"] = category
            results.append(payload)
        except Exception as exc:
            failed_files.append({"input_path": str(video_path), "error": str(exc)})

    summary: dict[str, object] = {
        "input_folder": str(folder),
        "output_folder": str(output_root),
        "total_video_files": len(video_files),
        "min_duration_seconds": min_duration_seconds,
        "target_width": target_width,
        "target_height": target_height,
        "detect_duplicates": detect_duplicates,
        "short_video_count": short_video_count,
        "ratio_mismatch_count": ratio_mismatch_count,
        "duplicate_video_count": duplicate_video_count,
        "has_person_count": has_person_count,
        "no_person_count": no_person_count,
        "failed_count": len(failed_files),
        "results": results,
        "failed_files": failed_files,
    }

    if pretty:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        print(json.dumps(summary, ensure_ascii=False))
    return summary


def main() -> None:
    args = parse_args()
    (
        input_folder,
        output_folder,
        pretty,
        min_duration_seconds,
        target_width,
        target_height,
        detect_duplicates,
    ) = resolve_settings(args)
    process_folder(
        input_folder,
        output_folder,
        pretty,
        min_duration_seconds,
        target_width,
        target_height,
        detect_duplicates,
    )


if __name__ == "__main__":
    main()
