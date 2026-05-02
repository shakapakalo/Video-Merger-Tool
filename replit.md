# Workspace

## Overview

pnpm workspace monorepo using TypeScript + Python. Each package manages its own dependencies.

## Stack

- **Monorepo tool**: pnpm workspaces
- **Node.js version**: 24
- **Package manager**: pnpm
- **TypeScript version**: 5.9
- **API framework**: Express 5
- **Database**: PostgreSQL + Drizzle ORM
- **Validation**: Zod (`zod/v4`), `drizzle-zod`
- **API codegen**: Orval (from OpenAPI spec)
- **Build**: esbuild (CJS bundle)

## Key Commands

- `pnpm run typecheck` — full typecheck across all packages
- `pnpm run build` — typecheck + build all packages
- `pnpm --filter @workspace/api-spec run codegen` — regenerate API hooks and Zod schemas from OpenAPI spec
- `pnpm --filter @workspace/db run push` — push DB schema changes (dev only)
- `pnpm --filter @workspace/api-server run dev` — run API server locally

See the `pnpm-workspace` skill for workspace structure, TypeScript setup, and package details.

## Video Merger API

A Python FastAPI service in `artifacts/video-merger/` that merges multiple video URLs using FFmpeg.

- **Version**: 2.0.0
- **Workflow**: "Video Merger API" — runs on port 8000
- **Endpoints**: `POST /merge`, `GET /status/{job_id}`, `GET /download/{job_id}`, `GET /jobs`, `GET /healthz`
- **Docs**: Swagger UI at `/docs`
- **Stack**: Python 3.11, FastAPI 0.115, Uvicorn, httpx, Pydantic v2, FFmpeg 6.1

### Output Formats
- **Portrait 9:16** (default) — phone/vertical format: 480p (480×854), 720p (720×1280), 1080p (1080×1920)
- **Landscape 16:9** — widescreen: 480p (854×480), 720p (1280×720), 1080p (1920×1080)

### Transition Types
`fade`, `none`, `crossfade`, `wipe_left`, `wipe_right`, `slide_left`, `slide_right`, `zoom_in`, `dissolve`, `radial`

### Effects
- Color grading: `brightness`, `contrast`, `saturation`
- Visual: `blur`, `sharpen`, `vignette`
- Speed: 0.25x–4.0x
- Rotation: 0, 90, 180, 270
- Per-clip trim: `trim_videos`
- Background music with volume, loop, fade controls
- Watermark text overlay

### Files
```
artifacts/video-merger/
├── main.py           # FastAPI app — all processing logic
├── requirements.txt  # Python deps (fastapi, uvicorn, httpx, pydantic)
├── Dockerfile        # Docker build for VPS deployment (port 6767)
└── README.md         # Full API docs with curl examples
```
