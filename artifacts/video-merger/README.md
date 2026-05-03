# 🎬 Video Merger API v2.0

> Production-ready REST API to merge multiple video URLs into a single professional video using FFmpeg + FastAPI.
> Supports **9:16 portrait** (phone/vertical) and 16:9 landscape output, smooth transitions, color grading, zoom, Ultra HD 4K output, and much more.

---

## 📋 Table of Contents

- [Features](#-features)
- [Requirements](#-requirements)
- [VPS Installation (Ubuntu/Debian)](#-vps-installation-ubuntudebian)
- [Docker Installation](#-docker-installation)
- [Manual Installation (Local)](#-manual-installation-local)
- [API Usage](#-api-usage)
- [All Endpoints](#-all-endpoints)
- [Request Fields Reference](#-request-fields-reference)
- [Request Examples (curl)](#-request-examples-curl)
- [Error Codes](#-error-codes)
- [Run as System Service](#-run-as-system-service-auto-restart)
- [Troubleshooting](#-troubleshooting)
- [Tech Stack](#-tech-stack)

---

## ✅ Features

| Feature | Details |
|---------|---------|
| **Output orientation** | **9:16 portrait** (default, phone/vertical) or 16:9 landscape |
| **Resolutions** | SD (480p), HD (720p), Full HD (1080p), 2K/QHD (1440p), **4K Ultra HD (2160p)** |
| **Video count** | Merge 1 to 20 video URLs in exact order |
| **Fast mode** | Simple concat, no re-encoding (`apply_editing: false`) |
| **Zoom** | Static zoom from 1% to 20%+ — scale up + center crop on all clips |
| **Fade transitions** | Fade in/out on each clip (`transition_type: "fade"`) |
| **Crossfade** | Smooth xfade blend between clips (`transition_type: "crossfade"`) |
| **Wipe transitions** | `wipe_left`, `wipe_right` |
| **Slide transitions** | `slide_left`, `slide_right` |
| **Zoom / dissolve** | `zoom_in`, `dissolve`, `radial` |
| **Transition duration** | 0.1s to 5.0s (default 0.5s) |
| **Color grading** | `brightness` (-1.0–1.0), `contrast` (0.5–2.0), `saturation` (0.0–3.0) |
| **Visual effects** | `blur`, `sharpen`, `vignette` (dark corners) |
| **Speed control** | 0.25x slow-mo to 4.0x fast-forward |
| **Rotation** | 0, 90, 180, or 270 degrees |
| **Per-clip trimming** | Trim start/end time for each video individually |
| **Background music** | Mix in audio file at custom volume with loop + fade options |
| **Watermark** | Text overlay on the video |
| **Audio controls** | Original volume, mute, music start/volume/fade/loop |
| **Async jobs** | Submit → Poll → Download (no timeout issues) |
| **Auto cleanup** | Temp files deleted after job finishes |
| **Error handling** | Clean JSON errors for all failures |
| **Docker ready** | Single command deploy |

---

## 🖥️ Requirements

### For VPS (Ubuntu 20.04 / 22.04 / 24.04)
- VPS with at least **2 GB RAM** (8 GB recommended for 4K)
- Ubuntu/Debian OS
- Port **6767** open in firewall
- Internet access to download videos

### For Docker
- Docker installed
- Port **6767** available

---

## 🚀 VPS Installation (Ubuntu/Debian)

### Step 1 — Connect to your VPS

```bash
ssh root@YOUR_VPS_IP
```

### Step 2 — Update system

```bash
apt update && apt upgrade -y
```

### Step 3 — Install required system packages

```bash
apt install -y python3 python3-pip python3-venv ffmpeg git curl
```

Verify FFmpeg is installed:
```bash
ffmpeg -version
```

### Step 4 — Clone from GitHub

```bash
cd /opt
git clone https://github.com/shakapakalo/Python-API-Combine.git video-merger
cd video-merger/artifacts/video-merger
```

### Step 5 — Create Python virtual environment

```bash
python3 -m venv venv
source venv/bin/activate
```

### Step 6 — Install Python dependencies

```bash
pip install -r requirements.txt
```

### Step 7 — Run the API

```bash
PORT=6767 python main.py
```

You should see:
```
INFO:     Uvicorn running on http://0.0.0.0:6767
```

### Step 8 — Open firewall port (if UFW is active)

```bash
ufw allow 6767
ufw reload
```

### Step 9 — Test it

```bash
curl http://YOUR_VPS_IP:6767/healthz
```

---

## 🐳 Docker Installation

### Step 1 — Install Docker

```bash
curl -fsSL https://get.docker.com | sh
```

### Step 2 — Clone the repo

```bash
cd /opt
git clone https://github.com/shakapakalo/Python-API-Combine.git video-merger
cd video-merger/artifacts/video-merger
```

### Step 3 — Build Docker image

```bash
docker build -t video-merger .
```

### Step 4 — Run the container

```bash
docker run -d \
  --name video-merger \
  -p 6767:6767 \
  --restart unless-stopped \
  video-merger
```

### Step 5 — Test

```bash
curl http://YOUR_VPS_IP:6767/healthz
```

### Useful Docker commands

```bash
# View live logs
docker logs -f video-merger

# Stop the service
docker stop video-merger

# Start again
docker start video-merger

# Update (pull new code and rebuild)
cd /opt/video-merger
git pull
cd artifacts/video-merger
docker stop video-merger && docker rm video-merger
docker build -t video-merger .
docker run -d --name video-merger -p 6767:6767 --restart unless-stopped video-merger
```

---

## 💻 Manual Installation (Local / Windows / Mac)

### Prerequisites
- Python 3.10 or higher
- FFmpeg installed

| OS | Install FFmpeg |
|----|---------------|
| Ubuntu/Debian | `sudo apt install ffmpeg` |
| Mac | `brew install ffmpeg` |
| Windows | Download from [ffmpeg.org](https://ffmpeg.org/download.html) and add to PATH |

### Steps

```bash
git clone https://github.com/shakapakalo/Python-API-Combine.git
cd Python-API-Combine/artifacts/video-merger

pip install -r requirements.txt

PORT=6767 python main.py
```

API will be at: `http://localhost:6767`

Interactive docs: `http://localhost:6767/docs`

---

## 📡 API Usage

The API works in **3 steps**:

```
1. POST /merge      → Submit job  → get job_id
2. GET  /status/ID  → Poll until status = "done"
3. GET  /download/ID → Download the merged MP4
```

---

## 📌 All Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/healthz` | Check API, FFmpeg status, and available features |
| `POST` | `/merge` | Submit a video merge job |
| `GET` | `/status/{job_id}` | Check job progress |
| `GET` | `/download/{job_id}` | Download the merged video |
| `GET` | `/jobs` | List all jobs |
| `GET` | `/docs` | Swagger UI (interactive docs in browser) |

---

## 📦 Request Fields Reference

### Video & Output

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `videos` | `array` | — | **Required.** List of video URLs (1–20), merged in order |
| `output_resolution` | `string` | `"720p"` | See resolution table below |
| `orientation` | `string` | `"portrait"` | `"portrait"` = **9:16** (phone/vertical), `"landscape"` = 16:9 |

#### Resolution Options

| Value | Name | Portrait dimensions | Landscape dimensions |
|-------|------|--------------------|--------------------|
| `"480p"` | SD | 480 × 854 | 854 × 480 |
| `"720p"` | HD | 720 × 1280 | 1280 × 720 |
| `"1080p"` | Full HD | 1080 × 1920 | 1920 × 1080 |
| `"1440p"` or `"2k"` | 2K / QHD | 1440 × 2560 | 2560 × 1440 |
| `"4k"` or `"uhd"` or `"2160p"` | **4K Ultra HD** | 2160 × 3840 | 3840 × 2160 |

> ⚠️ 4K requires significant server resources. Recommended: 8 GB RAM, 4+ CPU cores.

---

### Zoom

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `zoom` | `float` | `1.0` | Zoom level applied to all clips (1.0–3.0). See table below |

#### Zoom Value Guide

| `zoom` value | Actual zoom applied | Visible effect |
|-------------|--------------------|--------------------|
| `1.0` | 0% (no zoom) | Original size, no change |
| `1.1` | 1% zoom in | Very subtle, barely visible |
| `1.2` | 2% zoom in | Slight zoom in |
| `1.5` | 5% zoom in | Noticeably zoomed |
| `2.0` | 10% zoom in | Clearly zoomed in |
| `3.0` | 20% zoom in | Strongly zoomed in |

> Zoom scales up all clips then center-crops back to the target resolution. No animation — same zoom level from start to end of every clip.

---

### Editing & Transitions

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `apply_editing` | `boolean` | `false` | Enable transition effects and audio normalization |
| `transition_type` | `string` | `"fade"` | See transition types table below |
| `transition_duration` | `float` | `0.5` | Transition length in seconds (0.1–5.0) |

#### Transition Types

| Value | Effect |
|-------|--------|
| `"none"` | No transition — hard cut between clips |
| `"fade"` | Fade-in at clip start, fade-out at clip end |
| `"crossfade"` | Smooth crossfade blend between clips (xfade) |
| `"wipe_left"` | Wipe from right to left |
| `"wipe_right"` | Wipe from left to right |
| `"slide_left"` | Slide clips to the left |
| `"slide_right"` | Slide clips to the right |
| `"zoom_in"` | Circle crop zoom-in reveal |
| `"dissolve"` | Random pixel dissolve |
| `"radial"` | Radial (clockwise) wipe |

---

### 🎨 Color Grading Filters

Apply cinematic color grading to all clips.

| Field | Type | Default | Range | Description |
|-------|------|---------|-------|-------------|
| `brightness` | `float` | `0.0` | `-1.0` to `1.0` | Negative = darker, positive = brighter. `0.0` = no change |
| `contrast` | `float` | `1.0` | `0.5` to `2.0` | Below 1.0 = flat/washed, above 1.0 = punchy. `1.0` = no change |
| `saturation` | `float` | `1.0` | `0.0` to `3.0` | `0.0` = grayscale/black & white, `1.0` = no change, `3.0` = very vivid colors |

#### Color Grading Presets (suggested values)

| Look / Style | brightness | contrast | saturation |
|-------------|-----------|---------|-----------|
| No change (default) | `0.0` | `1.0` | `1.0` |
| Bright & vivid | `0.1` | `1.2` | `1.5` |
| Cinematic dark | `-0.05` | `1.3` | `0.85` |
| Black & white | `0.0` | `1.1` | `0.0` |
| Faded / vintage | `-0.05` | `0.8` | `0.7` |
| High contrast | `0.0` | `1.5` | `1.0` |
| Soft / warm | `0.05` | `0.95` | `1.2` |
| Cold / blue tone | `0.0` | `1.0` | `0.8` |

---

### ✨ Visual Effects Filters

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `blur` | `float` | `0.0` | Gaussian blur. `0.0` = off. `1`–`5` = soft blur. `6`–`10` = heavy blur |
| `sharpen` | `boolean` | `false` | Apply unsharp mask — makes edges crisper and details pop |
| `vignette` | `boolean` | `false` | Adds dark corners / edges overlay (cinematic look) |

#### Visual Effects Guide

| Effect | Setting | When to use |
|--------|---------|-------------|
| No effects | all default | Clean output |
| Soft focus / dreamy | `blur: 2.0` | Background clips, intro |
| Heavy blur | `blur: 8.0` | Privacy blur, artistic |
| Sharp & crisp | `sharpen: true` | Action clips, text-heavy |
| Cinematic borders | `vignette: true` | Film look, storytelling |
| Full cinematic | `sharpen: true, vignette: true, contrast: 1.2` | Premium look |

---

### Speed & Rotation

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `speed` | `float` | `1.0` | Playback speed for all clips. `0.25` (slow-mo) to `4.0` (fast-forward) |
| `rotate` | `int` | `0` | Rotate all clips: `0`, `90`, `180`, or `270` degrees |

---

### Per-Clip Trimming

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `trim_videos` | `array` | `null` | List of trim configs (same order as `videos`). Use `null` for a clip to skip trimming |

Each trim entry: `{"start": 5.0, "end": 30.0}` (seconds). `end` is optional.

---

### Background Music

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `background_music` | `string` | `null` | URL of audio file (mp3, aac, wav, ogg, m4a) |
| `music_volume` | `float` | `0.15` | Music volume: `0.0`–`5.0`. `1.0` = 100% |
| `music_loop` | `boolean` | `true` | Loop music to fill full video length |
| `music_start_time` | `float` | `0.0` | Start position in music file in seconds |
| `music_fade_in` | `float` | `0.0` | Fade-in duration at music start (seconds) |
| `music_fade_out` | `float` | `0.0` | Fade-out duration at music end (seconds) |

---

### Original Audio

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `original_audio_volume` | `float` | `1.0` | Original video audio volume: `0.0`–`5.0` |
| `mute_original` | `boolean` | `false` | Completely mute original video audio |

---

### Other

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `watermark` | `string` | `null` | Text overlay in the top-left corner of the video |

---

## 📝 Request Examples (curl)

> Replace `YOUR_VPS_IP:6767` with your actual server address.

### 1. Health Check

```bash
curl http://YOUR_VPS_IP:6767/healthz
```

---

### 2. Simple Merge — 9:16 Portrait (Phone Format, Fast)

```bash
curl -X POST http://YOUR_VPS_IP:6767/merge \
  -H "Content-Type: application/json" \
  -d '{
    "videos": [
      "https://example.com/clip1.mp4",
      "https://example.com/clip2.mp4",
      "https://example.com/clip3.mp4"
    ],
    "orientation": "portrait",
    "output_resolution": "1080p",
    "apply_editing": false
  }'
```

---

### 3. 4K Ultra HD Output

```bash
curl -X POST http://YOUR_VPS_IP:6767/merge \
  -H "Content-Type: application/json" \
  -d '{
    "videos": [
      "https://example.com/clip1.mp4",
      "https://example.com/clip2.mp4"
    ],
    "orientation": "portrait",
    "output_resolution": "4k",
    "apply_editing": false
  }'
```

---

### 4. 2K / QHD Output

```bash
curl -X POST http://YOUR_VPS_IP:6767/merge \
  -H "Content-Type: application/json" \
  -d '{
    "videos": [
      "https://example.com/clip1.mp4",
      "https://example.com/clip2.mp4"
    ],
    "orientation": "landscape",
    "output_resolution": "2k"
  }'
```

---

### 5. Zoom (2% zoom in on all clips)

```bash
curl -X POST http://YOUR_VPS_IP:6767/merge \
  -H "Content-Type: application/json" \
  -d '{
    "videos": [
      "https://example.com/clip1.mp4",
      "https://example.com/clip2.mp4"
    ],
    "orientation": "portrait",
    "output_resolution": "1080p",
    "zoom": 1.2
  }'
```

---

### 6. Crossfade Transitions

```bash
curl -X POST http://YOUR_VPS_IP:6767/merge \
  -H "Content-Type: application/json" \
  -d '{
    "videos": [
      "https://example.com/clip1.mp4",
      "https://example.com/clip2.mp4"
    ],
    "orientation": "portrait",
    "apply_editing": true,
    "transition_type": "crossfade",
    "transition_duration": 0.8,
    "output_resolution": "1080p"
  }'
```

---

### 7. Wipe Transition

```bash
curl -X POST http://YOUR_VPS_IP:6767/merge \
  -H "Content-Type: application/json" \
  -d '{
    "videos": ["https://example.com/clip1.mp4", "https://example.com/clip2.mp4"],
    "apply_editing": true,
    "transition_type": "wipe_right",
    "transition_duration": 0.5
  }'
```

---

### 8. Color Grading — Bright & Vivid

```bash
curl -X POST http://YOUR_VPS_IP:6767/merge \
  -H "Content-Type: application/json" \
  -d '{
    "videos": ["https://example.com/clip1.mp4", "https://example.com/clip2.mp4"],
    "apply_editing": true,
    "brightness": 0.1,
    "contrast": 1.2,
    "saturation": 1.5
  }'
```

---

### 9. Color Grading — Cinematic Dark

```bash
curl -X POST http://YOUR_VPS_IP:6767/merge \
  -H "Content-Type: application/json" \
  -d '{
    "videos": ["https://example.com/clip1.mp4", "https://example.com/clip2.mp4"],
    "brightness": -0.05,
    "contrast": 1.3,
    "saturation": 0.85,
    "vignette": true
  }'
```

---

### 10. Color Grading — Black & White

```bash
curl -X POST http://YOUR_VPS_IP:6767/merge \
  -H "Content-Type: application/json" \
  -d '{
    "videos": ["https://example.com/clip1.mp4", "https://example.com/clip2.mp4"],
    "saturation": 0.0,
    "contrast": 1.1
  }'
```

---

### 11. Visual Effects — Sharpen + Vignette (Cinematic)

```bash
curl -X POST http://YOUR_VPS_IP:6767/merge \
  -H "Content-Type: application/json" \
  -d '{
    "videos": ["https://example.com/clip1.mp4"],
    "sharpen": true,
    "vignette": true,
    "contrast": 1.2
  }'
```

---

### 12. Visual Effects — Blur

```bash
curl -X POST http://YOUR_VPS_IP:6767/merge \
  -H "Content-Type: application/json" \
  -d '{
    "videos": ["https://example.com/clip1.mp4"],
    "blur": 3.0
  }'
```

---

### 13. Slow Motion (0.5x Speed)

```bash
curl -X POST http://YOUR_VPS_IP:6767/merge \
  -H "Content-Type: application/json" \
  -d '{
    "videos": ["https://example.com/clip1.mp4"],
    "speed": 0.5,
    "apply_editing": false
  }'
```

---

### 14. Per-Clip Trimming

```bash
curl -X POST http://YOUR_VPS_IP:6767/merge \
  -H "Content-Type: application/json" \
  -d '{
    "videos": [
      "https://example.com/clip1.mp4",
      "https://example.com/clip2.mp4",
      "https://example.com/clip3.mp4"
    ],
    "trim_videos": [
      {"start": 0, "end": 10},
      {"start": 5, "end": 20},
      null
    ],
    "apply_editing": true,
    "transition_type": "fade"
  }'
```

---

### 15. With Background Music

```bash
curl -X POST http://YOUR_VPS_IP:6767/merge \
  -H "Content-Type: application/json" \
  -d '{
    "videos": [
      "https://example.com/clip1.mp4",
      "https://example.com/clip2.mp4"
    ],
    "background_music": "https://example.com/music.mp3",
    "music_volume": 0.2,
    "music_loop": true,
    "music_fade_in": 1.5,
    "music_fade_out": 2.0,
    "mute_original": true,
    "apply_editing": true,
    "transition_type": "crossfade"
  }'
```

---

### 16. Rotate + Watermark + Landscape

```bash
curl -X POST http://YOUR_VPS_IP:6767/merge \
  -H "Content-Type: application/json" \
  -d '{
    "videos": ["https://example.com/clip1.mp4", "https://example.com/clip2.mp4"],
    "orientation": "landscape",
    "output_resolution": "1080p",
    "rotate": 90,
    "watermark": "MyChannel",
    "apply_editing": true,
    "transition_type": "dissolve"
  }'
```

---

### 17. Everything Together (Full Options)

```bash
curl -X POST http://YOUR_VPS_IP:6767/merge \
  -H "Content-Type: application/json" \
  -d '{
    "videos": [
      "https://example.com/clip1.mp4",
      "https://example.com/clip2.mp4",
      "https://example.com/clip3.mp4"
    ],
    "orientation": "portrait",
    "output_resolution": "1080p",

    "zoom": 1.2,

    "apply_editing": true,
    "transition_type": "crossfade",
    "transition_duration": 0.7,

    "brightness": 0.05,
    "contrast": 1.1,
    "saturation": 1.2,

    "vignette": true,
    "sharpen": true,
    "blur": 0.0,

    "speed": 1.0,
    "rotate": 0,

    "trim_videos": [
      {"start": 0, "end": 15},
      {"start": 5},
      null
    ],

    "background_music": "https://example.com/music.mp3",
    "music_volume": 0.15,
    "music_loop": true,
    "music_start_time": 10.0,
    "music_fade_in": 1.0,
    "music_fade_out": 2.0,

    "original_audio_volume": 0.8,
    "mute_original": false,

    "watermark": "MyBrand"
  }'
```

---

### 18. Check Job Status

```bash
curl http://YOUR_VPS_IP:6767/status/YOUR-JOB-ID-HERE
```

Response (while processing):
```json
{
  "job_id": "abc12345-...",
  "status": "processing",
  "message": "Merging with crossfade transition...",
  "download_url": null
}
```

Response (when done):
```json
{
  "job_id": "abc12345-...",
  "status": "done",
  "message": "Merge complete. Output: portrait 1080p (34.5s, 84.2 MB)",
  "download_url": "/download/abc12345-..."
}
```

---

### 19. Download Merged Video

```bash
curl -L http://YOUR_VPS_IP:6767/download/YOUR-JOB-ID-HERE \
  -o my_merged_video.mp4
```

> Note: File is automatically deleted from the server after download.

---

### 20. List All Jobs

```bash
curl http://YOUR_VPS_IP:6767/jobs
```

---

### 21. Interactive Docs (Browser)

Open in browser:
```
http://YOUR_VPS_IP:6767/docs
```

---

## ❌ Error Codes

| Code | Meaning | Example |
|------|---------|---------|
| `400` | Validation error | Invalid URL, too many videos, invalid transition_type |
| `404` | Job not found | Wrong job_id |
| `409` | Job not ready | Job still processing |
| `410` | File gone | Already downloaded or expired |
| `413` | File too large | Video over 500 MB |
| `502` | Download failed | URL unreachable or HTTP error |

All errors return clean JSON:
```json
{
  "detail": "Failed to download https://example.com/video.mp4: HTTP 403"
}
```

---

## 🔄 Run as System Service (Auto-restart)

```bash
nano /etc/systemd/system/video-merger.service
```

Paste this:

```ini
[Unit]
Description=Video Merger API v2
After=network.target

[Service]
User=root
WorkingDirectory=/opt/video-merger/artifacts/video-merger
ExecStart=/opt/video-merger/artifacts/video-merger/venv/bin/python main.py
Environment=PORT=6767
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
systemctl daemon-reload
systemctl enable video-merger
systemctl start video-merger
systemctl status video-merger
```

View live logs:
```bash
journalctl -u video-merger -f
```

---

## 🔧 Troubleshooting

### API not responding
```bash
systemctl status video-merger
ss -tlnp | grep 6767
ufw status && ufw allow 6767
```

### FFmpeg not found
```bash
apt install -y ffmpeg
which ffmpeg
```

### Out of disk space (temp files)
```bash
df -h
rm -rf /tmp/video-merger-*
```

### Job stuck in "processing"
```bash
journalctl -u video-merger -n 100
# or Docker:
docker logs video-merger --tail 100
```

### Crossfade/xfade not working
- Requires FFmpeg 4.3+ (xfade filter added in 4.3)
- Check `ffmpeg -version`
- Fall back to `transition_type: "fade"` if needed

### 4K processing is slow
- 4K requires significant CPU. Use a server with 4+ cores and 8 GB RAM.
- For faster 4K, consider hardware acceleration (NVIDIA GPU + `-hwaccel cuda` flag).

### Update to latest code
```bash
cd /opt/video-merger
git pull

# Systemd:
cd artifacts/video-merger
source venv/bin/activate
pip install -r requirements.txt
systemctl restart video-merger

# Docker:
cd artifacts/video-merger
docker stop video-merger && docker rm video-merger
docker build -t video-merger .
docker run -d --name video-merger -p 6767:6767 --restart unless-stopped video-merger
```

---

## 📁 Project Structure

```
artifacts/video-merger/
├── main.py           # FastAPI application — all logic here
├── requirements.txt  # Python dependencies
├── Dockerfile        # Docker build file
└── README.md         # This file
```

---

## ⚙️ Tech Stack

| Component | Technology |
|-----------|-----------|
| Language | Python 3.11+ |
| Framework | FastAPI 0.115 |
| Video processing | FFmpeg 4.3+ (xfade filter required for crossfade/wipe/slide) |
| HTTP downloads | httpx (async streaming) |
| Server | Uvicorn |
| Validation | Pydantic v2 |
| Containerization | Docker |

---

## 📞 Quick Reference

```bash
# Health check
curl http://IP:PORT/healthz

# Submit job (portrait 1080p, crossfade, 2% zoom)
curl -X POST http://IP:PORT/merge -H "Content-Type: application/json" \
  -d '{"videos":["URL1","URL2"],"orientation":"portrait","output_resolution":"1080p","apply_editing":true,"transition_type":"crossfade","zoom":1.2}'

# Submit job (4K Ultra HD)
curl -X POST http://IP:PORT/merge -H "Content-Type: application/json" \
  -d '{"videos":["URL1","URL2"],"orientation":"portrait","output_resolution":"4k"}'

# Check status
curl http://IP:PORT/status/JOB_ID

# Download result
curl -L http://IP:PORT/download/JOB_ID -o output.mp4

# Interactive docs
open http://IP:PORT/docs
```
