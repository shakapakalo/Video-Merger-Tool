import asyncio
import json
import logging
import os
import shutil
import subprocess
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import httpx
from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, field_validator

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("video-merger")

OUTPUT_DIR = Path("/tmp/video-merger-output")
TEMP_DIR = Path("/tmp/video-merger-temp")
MAX_VIDEOS = 20
MAX_VIDEO_SIZE_MB = 500
ALLOWED_VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".webm", ".flv", ".m4v"}
ALLOWED_AUDIO_EXTENSIONS = {".mp3", ".aac", ".wav", ".ogg", ".m4a"}

XFADE_TRANSITIONS = {
    "crossfade": "fade",
    "wipe_left": "wipeleft",
    "wipe_right": "wiperight",
    "slide_left": "slideleft",
    "slide_right": "slideright",
    "zoom_in": "circlecrop",
    "dissolve": "dissolve",
    "radial": "radial",
}


@asynccontextmanager
async def lifespan(app: FastAPI):
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    TEMP_DIR.mkdir(parents=True, exist_ok=True)
    logger.info("Video merger service started. Output dir: %s", OUTPUT_DIR)
    yield
    logger.info("Video merger service shutting down.")


app = FastAPI(
    title="Video Merger API",
    description=(
        "Merge multiple video URLs into a single output video using FFmpeg. "
        "Supports 9:16 portrait format, fade/crossfade/wipe/slide/zoom transitions, "
        "color grading, blur, sharpen, vignette, speed control, rotation, per-clip trimming, "
        "background music, watermark, and more."
    ),
    version="2.0.0",
    lifespan=lifespan,
)


class TrimConfig(BaseModel):
    start: float = 0.0
    end: Optional[float] = None


class MergeRequest(BaseModel):
    videos: List[str]
    background_music: Optional[str] = None
    apply_editing: bool = False
    watermark: Optional[str] = None
    output_resolution: Optional[str] = "720p"

    # Orientation: portrait = 9:16 (default), landscape = 16:9
    orientation: str = "portrait"

    # Transition effect (used when apply_editing=True)
    # "fade"        — fade in/out on each clip (default, no xfade between clips)
    # "none"        — no transitions
    # "crossfade"   — smooth crossfade (xfade) between clips
    # "wipe_left"   — wipe from right to left
    # "wipe_right"  — wipe from left to right
    # "slide_left"  — slide clips to the left
    # "slide_right" — slide clips to the right
    # "zoom_in"     — circle crop zoom-in effect
    # "dissolve"    — random pixel dissolve
    # "radial"      — radial wipe
    transition_type: str = "fade"
    transition_duration: float = 0.5

    # Color grading
    brightness: float = 0.0    # -1.0 (darker) to 1.0 (brighter), 0.0 = no change
    contrast: float = 1.0      # 0.5 to 2.0, 1.0 = no change
    saturation: float = 1.0    # 0.0 (grayscale) to 3.0 (vivid), 1.0 = no change

    # Visual effects
    vignette: bool = False      # Dark corners vignette overlay
    sharpen: bool = False       # Apply sharpening filter
    blur: float = 0.0           # Gaussian blur radius (0.0 = off, 1-10 = strength)

    # Playback speed (applies to all clips)
    speed: float = 1.0          # 0.25 (slow-mo) to 4.0 (fast-forward)

    # Rotation (applies to all clips after scaling)
    rotate: int = 0             # 0, 90, 180, or 270 degrees

    # Per-clip trim: list of {start, end} dicts (same order as videos)
    # Use null to skip trimming for a specific clip
    trim_videos: Optional[List[Optional[Dict[str, float]]]] = None

    # Music controls
    music_volume: float = 0.15
    music_loop: bool = True
    music_start_time: float = 0.0
    music_fade_in: float = 0.0
    music_fade_out: float = 0.0

    # Original video audio controls
    original_audio_volume: float = 1.0
    mute_original: bool = False

    @field_validator("videos")
    @classmethod
    def validate_videos(cls, v: List[str]) -> List[str]:
        if not v:
            raise ValueError("At least one video URL is required.")
        if len(v) > MAX_VIDEOS:
            raise ValueError(f"Maximum {MAX_VIDEOS} videos allowed.")
        for url in v:
            _validate_url(url)
        return v

    @field_validator("background_music")
    @classmethod
    def validate_music(cls, v: Optional[str]) -> Optional[str]:
        if v:
            _validate_url(v)
        return v

    @field_validator("output_resolution")
    @classmethod
    def validate_resolution(cls, v: Optional[str]) -> Optional[str]:
        if v and v not in {"480p", "720p", "1080p"}:
            raise ValueError("output_resolution must be '480p', '720p', or '1080p'")
        return v

    @field_validator("orientation")
    @classmethod
    def validate_orientation(cls, v: str) -> str:
        if v not in ("portrait", "landscape"):
            raise ValueError("orientation must be 'portrait' or 'landscape'")
        return v

    @field_validator("transition_type")
    @classmethod
    def validate_transition_type(cls, v: str) -> str:
        allowed = {
            "fade", "none", "crossfade", "wipe_left", "wipe_right",
            "slide_left", "slide_right", "zoom_in", "dissolve", "radial",
        }
        if v not in allowed:
            raise ValueError(f"transition_type must be one of: {sorted(allowed)}")
        return v

    @field_validator("transition_duration")
    @classmethod
    def validate_transition_duration(cls, v: float) -> float:
        if not 0.1 <= v <= 5.0:
            raise ValueError("transition_duration must be between 0.1 and 5.0 seconds")
        return round(v, 4)

    @field_validator("brightness")
    @classmethod
    def validate_brightness(cls, v: float) -> float:
        if not -1.0 <= v <= 1.0:
            raise ValueError("brightness must be between -1.0 and 1.0")
        return round(v, 4)

    @field_validator("contrast")
    @classmethod
    def validate_contrast(cls, v: float) -> float:
        if not 0.5 <= v <= 2.0:
            raise ValueError("contrast must be between 0.5 and 2.0")
        return round(v, 4)

    @field_validator("saturation")
    @classmethod
    def validate_saturation(cls, v: float) -> float:
        if not 0.0 <= v <= 3.0:
            raise ValueError("saturation must be between 0.0 and 3.0")
        return round(v, 4)

    @field_validator("blur")
    @classmethod
    def validate_blur(cls, v: float) -> float:
        if not 0.0 <= v <= 10.0:
            raise ValueError("blur must be between 0.0 and 10.0")
        return round(v, 1)

    @field_validator("speed")
    @classmethod
    def validate_speed(cls, v: float) -> float:
        if not 0.25 <= v <= 4.0:
            raise ValueError("speed must be between 0.25 and 4.0")
        return round(v, 4)

    @field_validator("rotate")
    @classmethod
    def validate_rotate(cls, v: int) -> int:
        if v not in (0, 90, 180, 270):
            raise ValueError("rotate must be 0, 90, 180, or 270")
        return v

    @field_validator("music_volume", "original_audio_volume")
    @classmethod
    def validate_volume(cls, v: float) -> float:
        if not 0.0 <= v <= 5.0:
            raise ValueError("Volume must be between 0.0 and 5.0")
        return round(v, 4)

    @field_validator("music_start_time", "music_fade_in", "music_fade_out")
    @classmethod
    def validate_timing(cls, v: float) -> float:
        if v < 0.0:
            raise ValueError("Timing values must be >= 0.0")
        return round(v, 4)


class MergeResponse(BaseModel):
    job_id: str
    status: str
    message: str


class StatusResponse(BaseModel):
    job_id: str
    status: str
    message: str
    download_url: Optional[str] = None


_jobs: dict[str, dict] = {}


def _validate_url(url: str) -> None:
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            raise ValueError(f"URL must use http or https: {url}")
        if not parsed.netloc:
            raise ValueError(f"Invalid URL (no host): {url}")
    except Exception as exc:
        raise ValueError(str(exc)) from exc


def _get_extension(url: str) -> str:
    path = urlparse(url).path
    return Path(path).suffix.lower()


async def _download_file(
    client: httpx.AsyncClient, url: str, dest: Path, max_mb: int = MAX_VIDEO_SIZE_MB
) -> None:
    logger.info("Downloading %s -> %s", url, dest)
    try:
        async with client.stream("GET", url, follow_redirects=True, timeout=120) as resp:
            resp.raise_for_status()
            total = 0
            max_bytes = max_mb * 1024 * 1024
            with dest.open("wb") as f:
                async for chunk in resp.aiter_bytes(chunk_size=65536):
                    total += len(chunk)
                    if total > max_bytes:
                        raise HTTPException(
                            status_code=413,
                            detail=f"File exceeds maximum size of {max_mb}MB: {url}",
                        )
                    f.write(chunk)
        logger.info("Downloaded %s (%.1f MB)", url, total / 1024 / 1024)
    except httpx.HTTPStatusError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Failed to download {url}: HTTP {exc.response.status_code}",
        ) from exc
    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Network error downloading {url}: {exc}",
        ) from exc


def _run_ffmpeg(args: List[str], job_id: str) -> None:
    cmd = ["ffmpeg", "-y"] + args
    logger.info("[%s] FFmpeg: %s", job_id, " ".join(cmd))
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        logger.error("[%s] FFmpeg stderr: %s", job_id, result.stderr[-3000:])
        raise RuntimeError(
            f"FFmpeg failed (code {result.returncode}): {result.stderr[-800:]}"
        )
    logger.info("[%s] FFmpeg completed.", job_id)


def _probe_video(path: Path) -> dict:
    cmd = [
        "ffprobe", "-v", "quiet", "-print_format", "json",
        "-show_streams", "-show_format", str(path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffprobe failed on {path}: {result.stderr}")
    return json.loads(result.stdout)


def _get_duration(path: Path) -> float:
    info = _probe_video(path)
    duration = float(info.get("format", {}).get("duration", 0))
    if duration <= 0:
        for stream in info.get("streams", []):
            d = float(stream.get("duration", 0))
            if d > 0:
                duration = d
                break
    return duration


def _has_audio(path: Path) -> bool:
    info = _probe_video(path)
    return any(s.get("codec_type") == "audio" for s in info.get("streams", []))


def _resolution_dims(resolution: str, orientation: str) -> str:
    """
    Returns FFmpeg scale WxH string.
    Portrait (9:16): phone/vertical format
    Landscape (16:9): standard widescreen
    """
    portrait_map = {
        "480p": "480:854",
        "720p": "720:1280",
        "1080p": "1080:1920",
    }
    landscape_map = {
        "480p": "854:480",
        "720p": "1280:720",
        "1080p": "1920:1080",
    }
    if orientation == "landscape":
        return landscape_map.get(resolution, "1280:720")
    return portrait_map.get(resolution, "720:1280")


def _build_color_vf(req: MergeRequest) -> str:
    """Build eq filter string for brightness/contrast/saturation if any differ from defaults."""
    if req.brightness == 0.0 and req.contrast == 1.0 and req.saturation == 1.0:
        return ""
    return (
        f"eq=brightness={req.brightness:.4f}"
        f":contrast={req.contrast:.4f}"
        f":saturation={req.saturation:.4f}"
    )


def _build_extra_vf(req: MergeRequest) -> str:
    """Build extra visual effect filters: blur, sharpen, vignette, speed, rotate."""
    parts: List[str] = []

    if req.blur > 0:
        parts.append(f"gblur=sigma={req.blur:.1f}")

    if req.sharpen:
        parts.append("unsharp=5:5:1.0:5:5:0.0")

    if req.vignette:
        parts.append("vignette=PI/4")

    if req.speed != 1.0:
        parts.append(f"setpts={1.0 / req.speed:.6f}*PTS")

    if req.rotate == 90:
        parts.append("transpose=1")
    elif req.rotate == 180:
        parts.append("transpose=1,transpose=1")
    elif req.rotate == 270:
        parts.append("transpose=2")

    return ",".join(parts)


def _build_speed_af(speed: float) -> str:
    """Build audio tempo filter for speed changes. atempo range: 0.5–2.0 (chain for outside)."""
    if speed == 1.0:
        return ""
    if 0.5 <= speed <= 2.0:
        return f"atempo={speed:.4f}"
    if speed < 0.5:
        # e.g. 0.25x → atempo=0.5,atempo=0.5
        return f"atempo=0.5,atempo={speed * 2:.4f}"
    # speed > 2.0 → e.g. 4.0x → atempo=2.0,atempo=2.0
    return f"atempo=2.0,atempo={speed / 2:.4f}"


def _normalize_clip(
    vp: Path,
    norm_path: Path,
    i: int,
    job_id: str,
    req: MergeRequest,
    scale: str,
    trim: Optional[Dict[str, float]],
) -> float:
    """
    Normalize a single clip to target format (9:16 or 16:9), apply all effects,
    and return the final clip duration.
    """
    has_audio = _has_audio(vp)

    # Trim args (optional)
    trim_args: List[str] = []
    if trim:
        if trim.get("start", 0.0) > 0.0:
            trim_args += ["-ss", f"{trim['start']:.6f}"]
        if trim.get("end") is not None:
            trim_args += ["-to", f"{trim['end']:.6f}"]

    # First pass: get duration after trim (or full duration)
    probe_path = vp
    if trim_args:
        # Apply trim to a quick re-encode to get accurate duration
        trimmed_path = norm_path.parent / f"trim_{i:03d}.mp4"
        _run_ffmpeg(
            trim_args + ["-i", str(vp), "-c", "copy", str(trimmed_path)],
            job_id,
        )
        probe_path = trimmed_path
    else:
        probe_path = vp

    clip_dur = _get_duration(probe_path)
    if clip_dur <= 0:
        clip_dur = 1.0  # fallback

    # Apply speed to duration
    effective_dur = clip_dur / req.speed if req.speed != 1.0 else clip_dur

    fade_d = min(req.transition_duration, clip_dur / 4)
    fade_out_start = max(0.0, clip_dur - fade_d) if clip_dur > fade_d * 2 else 0.0

    # ── Build video filter chain ──────────────────────────────────────
    scale_vf = (
        f"scale={scale}:force_original_aspect_ratio=decrease,"
        f"pad={scale}:(ow-iw)/2:(oh-ih)/2,"
        f"setsar=1,fps=30"
    )

    color_vf = _build_color_vf(req)
    extra_vf = _build_extra_vf(req)

    vf_parts = [scale_vf]
    if color_vf:
        vf_parts.append(color_vf)
    if extra_vf:
        vf_parts.append(extra_vf)

    if req.apply_editing and req.transition_type == "fade":
        vf_parts.append(f"fade=t=in:st=0:d={fade_d}")
        vf_parts.append(f"fade=t=out:st={fade_out_start:.4f}:d={fade_d}")

    vf = ",".join(vf_parts)

    # ── Build audio filter chain ──────────────────────────────────────
    apad = f"apad=whole_dur={clip_dur:.6f}"
    af_parts: List[str] = []

    if req.apply_editing and req.transition_type == "fade":
        af_parts.append(f"afade=t=in:st=0:d={fade_d}")
        af_parts.append(f"afade=t=out:st={fade_out_start:.4f}:d={fade_d}")
        af_parts.append("dynaudnorm")

    speed_af = _build_speed_af(req.speed)
    if speed_af:
        af_parts.append(speed_af)

    af_parts.append(apad)
    af = ",".join(af_parts)

    # ── Run ffmpeg normalization ──────────────────────────────────────
    base_input = ["-i", str(probe_path)]

    if has_audio:
        _run_ffmpeg(
            base_input + [
                "-map", "0:v:0", "-map", "0:a:0",
                "-vf", vf, "-af", af,
                "-c:v", "libx264", "-c:a", "aac",
                "-ar", "44100", "-ac", "2",
                "-preset", "fast", "-crf", "23",
                str(norm_path),
            ],
            job_id,
        )
    else:
        _run_ffmpeg(
            base_input + [
                "-f", "lavfi",
                "-i", f"anullsrc=channel_layout=stereo:sample_rate=44100:duration={clip_dur:.6f}",
                "-map", "0:v:0", "-map", "1:a:0",
                "-vf", vf, "-af", af,
                "-c:v", "libx264", "-c:a", "aac",
                "-ar", "44100", "-ac", "2",
                "-preset", "fast", "-crf", "23",
                "-t", f"{clip_dur:.6f}",
                str(norm_path),
            ],
            job_id,
        )

    final_dur = _get_duration(norm_path)
    logger.info(
        "[%s] clip %d: source=%.3fs  normalized=%.3fs  audio=%s  speed=%.2fx",
        job_id, i, clip_dur, final_dur, has_audio, req.speed,
    )
    return final_dur


def _merge_concat(
    normalized_paths: List[Path],
    concat_path: Path,
    merged_path: Path,
    job_id: str,
) -> None:
    """Simple concat merge (no xfade, per-clip fades already applied)."""
    with concat_path.open("w") as f:
        for np in normalized_paths:
            f.write(f"file '{np}'\n")

    _run_ffmpeg(
        [
            "-f", "concat", "-safe", "0",
            "-i", str(concat_path),
            "-fflags", "+genpts",
            "-c", "copy",
            str(merged_path),
        ],
        job_id,
    )


def _merge_xfade(
    normalized_paths: List[Path],
    durations: List[float],
    merged_path: Path,
    job_id: str,
    transition_type: str,
    transition_duration: float,
) -> None:
    """
    Merge clips using FFmpeg xfade filter for smooth transitions between clips.
    Handles 1-N clips. Audio uses acrossfade.
    """
    n = len(normalized_paths)
    if n == 1:
        shutil.copy2(str(normalized_paths[0]), str(merged_path))
        return

    xf_name = XFADE_TRANSITIONS.get(transition_type, "fade")
    d = transition_duration

    inputs: List[str] = []
    for p in normalized_paths:
        inputs += ["-i", str(p)]

    fc_parts: List[str] = []
    prev_v = "[0:v]"
    prev_a = "[0:a]"

    for i in range(1, n):
        # offset = cumulative sum of durations before clip i minus i * d
        offset = max(0.0, sum(durations[:i]) - i * d)

        out_v = f"[v{i:03d}]" if i < n - 1 else "[vout]"
        out_a = f"[a{i:03d}]" if i < n - 1 else "[aout]"

        fc_parts.append(
            f"{prev_v}[{i}:v]xfade=transition={xf_name}"
            f":duration={d:.4f}:offset={offset:.4f}{out_v}"
        )
        fc_parts.append(
            f"{prev_a}[{i}:a]acrossfade=d={d:.4f}:o=1{out_a}"
        )

        prev_v = out_v
        prev_a = out_a

    filter_complex = ";".join(fc_parts)

    _run_ffmpeg(
        inputs + [
            "-filter_complex", filter_complex,
            "-map", "[vout]",
            "-map", "[aout]",
            "-c:v", "libx264", "-preset", "fast", "-crf", "23",
            "-c:a", "aac", "-ar", "44100", "-ac", "2",
            str(merged_path),
        ],
        job_id,
    )


def _build_audio_filter(
    req: MergeRequest,
    music_input_idx: int,
    merged_dur: float,
    has_music: bool,
) -> tuple[str, str]:
    """
    Returns (filter_complex_string, audio_output_label).
    """
    parts: List[str] = []
    audio_out = "[0:a]"

    if req.mute_original:
        parts.append("[0:a]volume=0[orig]")
        audio_out = "[orig]"
    elif req.original_audio_volume != 1.0:
        parts.append(f"[0:a]volume={req.original_audio_volume:.4f}[orig]")
        audio_out = "[orig]"

    if has_music:
        chain: List[str] = []

        if req.music_start_time > 0:
            chain.append(
                f"atrim=start={req.music_start_time:.4f},"
                "asetpts=PTS-STARTPTS"
            )

        if req.music_loop:
            chain.append("aloop=loop=-1:size=2000000000")

        if req.music_fade_in > 0:
            chain.append(f"afade=t=in:st=0:d={req.music_fade_in:.4f}")

        if req.music_fade_out > 0:
            fo_start = max(0.0, merged_dur - req.music_fade_out)
            chain.append(
                f"afade=t=out:st={fo_start:.4f}:d={req.music_fade_out:.4f}"
            )

        chain.append(f"volume={req.music_volume:.4f}")
        chain_str = ",".join(chain) if chain else "anull"
        parts.append(f"[{music_input_idx}:a]{chain_str}[music]")
        parts.append(
            f"{audio_out}[music]amix=inputs=2:duration=first:normalize=0[aout]"
        )
        audio_out = "[aout]"

    return ";".join(parts), audio_out


async def _process_merge(job_id: str, request: MergeRequest) -> None:
    job_dir = TEMP_DIR / job_id
    job_dir.mkdir(parents=True, exist_ok=True)
    output_path = OUTPUT_DIR / f"{job_id}.mp4"

    try:
        _jobs[job_id]["status"] = "downloading"
        _jobs[job_id]["message"] = "Downloading video files..."

        async with httpx.AsyncClient() as client:
            download_tasks = []
            video_paths: List[Path] = []

            for i, url in enumerate(request.videos):
                ext = _get_extension(url) or ".mp4"
                if ext not in ALLOWED_VIDEO_EXTENSIONS:
                    ext = ".mp4"
                dest = job_dir / f"video_{i:03d}{ext}"
                video_paths.append(dest)
                download_tasks.append(_download_file(client, url, dest))

            music_path: Optional[Path] = None
            if request.background_music:
                m_ext = _get_extension(request.background_music) or ".mp3"
                if m_ext not in ALLOWED_AUDIO_EXTENSIONS:
                    m_ext = ".mp3"
                music_path = job_dir / f"music{m_ext}"
                download_tasks.append(
                    _download_file(client, request.background_music, music_path, max_mb=50)
                )

            await asyncio.gather(*download_tasks)

        _jobs[job_id]["status"] = "processing"
        _jobs[job_id]["message"] = "Normalizing clips..."

        resolution = request.output_resolution or "720p"
        scale = _resolution_dims(resolution, request.orientation)

        normalized_paths: List[Path] = []
        clip_durations: List[float] = []

        for i, vp in enumerate(video_paths):
            norm_path = job_dir / f"norm_{i:03d}.mp4"
            trim = None
            if request.trim_videos and i < len(request.trim_videos):
                trim = request.trim_videos[i]

            dur = _normalize_clip(vp, norm_path, i, job_id, request, scale, trim)
            normalized_paths.append(norm_path)
            clip_durations.append(dur)

        _jobs[job_id]["message"] = "Merging clips..."

        # ── Choose merge strategy ─────────────────────────────────────
        merged_path = job_dir / "merged_raw.mp4"
        uses_xfade = (
            request.apply_editing
            and request.transition_type not in ("fade", "none")
            and len(normalized_paths) > 1
        )

        if uses_xfade:
            _jobs[job_id]["message"] = f"Merging with {request.transition_type} transition..."
            _merge_xfade(
                normalized_paths,
                clip_durations,
                merged_path,
                job_id,
                request.transition_type,
                request.transition_duration,
            )
        else:
            concat_path = job_dir / "concat_list.txt"
            _merge_concat(normalized_paths, concat_path, merged_path, job_id)

        merged_dur = _get_duration(merged_path)
        logger.info(
            "[%s] merged duration: %.3fs (clips: %s)",
            job_id, merged_dur, [f"{d:.2f}s" for d in clip_durations],
        )

        # ── Post-processing: audio mix + watermark ────────────────────
        has_music = music_path is not None and music_path.exists()
        has_watermark = bool(request.watermark)
        needs_audio_work = (
            has_music
            or request.mute_original
            or request.original_audio_volume != 1.0
        )

        if needs_audio_work:
            _jobs[job_id]["message"] = "Mixing audio..."
            music_idx = 1 if has_music else 0
            fc, audio_out_label = _build_audio_filter(request, music_idx, merged_dur, has_music)

            cmd: List[str] = ["-i", str(merged_path)]
            if has_music:
                cmd += ["-i", str(music_path)]

            if has_watermark:
                safe_wm = request.watermark.replace("'", "\\'")
                wm_filter = (
                    f"[0:v]drawtext=text='{safe_wm}':"
                    f"fontcolor=white:fontsize=24:x=10:y=10:"
                    f"box=1:boxcolor=black@0.5:boxborderw=5[vout]"
                )
                fc = wm_filter + (";" + fc if fc else "")
                cmd += [
                    "-filter_complex", fc,
                    "-map", "[vout]", "-map", audio_out_label,
                    "-c:v", "libx264", "-preset", "fast",
                    "-c:a", "aac", "-ar", "44100", "-ac", "2",
                    "-t", f"{merged_dur:.6f}",
                    str(output_path),
                ]
            else:
                cmd += [
                    "-filter_complex", fc,
                    "-map", "0:v",
                    "-map", audio_out_label,
                    "-c:v", "copy",
                    "-c:a", "aac", "-ar", "44100", "-ac", "2",
                    "-t", f"{merged_dur:.6f}",
                    str(output_path),
                ]
            _run_ffmpeg(cmd, job_id)

        elif has_watermark:
            _jobs[job_id]["message"] = "Adding watermark..."
            safe_wm = request.watermark.replace("'", "\\'")
            _run_ffmpeg(
                [
                    "-i", str(merged_path),
                    "-vf", (
                        f"drawtext=text='{safe_wm}':"
                        f"fontcolor=white:fontsize=24:x=10:y=10:"
                        f"box=1:boxcolor=black@0.5:boxborderw=5"
                    ),
                    "-c:v", "libx264", "-c:a", "copy",
                    "-preset", "fast", str(output_path),
                ],
                job_id,
            )
        else:
            shutil.copy2(merged_path, output_path)

        file_size = output_path.stat().st_size
        logger.info(
            "[%s] Output ready: %s (%.1f MB)", job_id, output_path, file_size / 1024 / 1024
        )

        _jobs[job_id]["status"] = "done"
        _jobs[job_id]["message"] = (
            f"Merge complete. "
            f"Output: {request.orientation} {resolution} "
            f"({merged_dur:.1f}s, {file_size / 1024 / 1024:.1f} MB)"
        )
        _jobs[job_id]["output_path"] = str(output_path)

    except HTTPException as exc:
        logger.error("[%s] HTTP error: %s", job_id, exc.detail)
        _jobs[job_id]["status"] = "error"
        _jobs[job_id]["message"] = exc.detail
    except RuntimeError as exc:
        logger.error("[%s] Processing error: %s", job_id, exc)
        _jobs[job_id]["status"] = "error"
        _jobs[job_id]["message"] = str(exc)
    except Exception as exc:
        logger.exception("[%s] Unexpected error", job_id)
        _jobs[job_id]["status"] = "error"
        _jobs[job_id]["message"] = f"Unexpected error: {exc}"
    finally:
        if job_dir.exists():
            shutil.rmtree(job_dir, ignore_errors=True)
            logger.info("[%s] Cleaned up temp files.", job_id)


# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.get("/healthz", summary="Health check")
async def health():
    ffmpeg_ok = shutil.which("ffmpeg") is not None
    ffprobe_ok = shutil.which("ffprobe") is not None
    return {
        "status": "ok" if ffmpeg_ok else "degraded",
        "ffmpeg": ffmpeg_ok,
        "ffprobe": ffprobe_ok,
        "version": "2.0.0",
        "features": [
            "9:16 portrait (default)", "16:9 landscape",
            "fade", "crossfade", "wipe_left", "wipe_right",
            "slide_left", "slide_right", "zoom_in", "dissolve", "radial",
            "brightness", "contrast", "saturation",
            "blur", "sharpen", "vignette",
            "speed control", "rotation (0/90/180/270)",
            "per-clip trimming", "background music", "watermark",
        ],
    }


@app.post("/merge", response_model=MergeResponse, status_code=202, summary="Submit merge job")
async def merge_videos(request: MergeRequest, background_tasks: BackgroundTasks):
    job_id = str(uuid.uuid4())
    _jobs[job_id] = {
        "status": "queued",
        "message": "Job queued, starting soon...",
        "output_path": None,
        "created_at": time.time(),
    }
    background_tasks.add_task(_process_merge, job_id, request)
    logger.info(
        "[%s] Job created — %d video(s), orientation=%s, resolution=%s, "
        "editing=%s, transition=%s",
        job_id, len(request.videos), request.orientation,
        request.output_resolution, request.apply_editing, request.transition_type,
    )
    return MergeResponse(
        job_id=job_id,
        status="queued",
        message=f"Job {job_id} created. Poll /status/{job_id} for progress.",
    )


@app.get("/status/{job_id}", response_model=StatusResponse, summary="Check job status")
async def job_status(job_id: str):
    job = _jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found.")

    download_url = f"/download/{job_id}" if job["status"] == "done" else None

    return StatusResponse(
        job_id=job_id,
        status=job["status"],
        message=job["message"],
        download_url=download_url,
    )


@app.get("/download/{job_id}", summary="Download merged video")
async def download_video(job_id: str, background_tasks: BackgroundTasks):
    job = _jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found.")
    if job["status"] != "done":
        raise HTTPException(
            status_code=409, detail=f"Job not ready. Status: {job['status']}"
        )

    output_path = Path(job["output_path"])
    if not output_path.exists():
        raise HTTPException(status_code=410, detail="Output file no longer available.")

    def cleanup():
        output_path.unlink(missing_ok=True)
        _jobs.pop(job_id, None)
        logger.info("[%s] Output file removed after download.", job_id)

    background_tasks.add_task(cleanup)

    return FileResponse(
        path=str(output_path),
        media_type="video/mp4",
        filename=f"merged_{job_id[:8]}.mp4",
    )


@app.get("/jobs", summary="List all jobs")
async def list_jobs():
    summary = []
    for jid, job in _jobs.items():
        summary.append({
            "job_id": jid,
            "status": job["status"],
            "message": job["message"],
            "age_seconds": round(time.time() - job.get("created_at", time.time())),
        })
    return {"jobs": summary, "total": len(summary)}


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)
