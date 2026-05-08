"""
FFmpeg 转码引擎
支持硬件加速（QSV/VAAPI/NVENC/VideoToolbox）和软件编码。

GPU 优先级：
- Windows: NVENC > QSV(D3D11VA) > 软件编码
- Linux: VAAPI > NVENC > QSV > 软件编码
- macOS: VideoToolbox
"""
from __future__ import annotations

import asyncio
import logging
import os
import shutil
import signal as _signal
import subprocess
import sys
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from app.config import get_settings

logger = logging.getLogger(__name__)


class HWAccelType(str, Enum):
    AUTO = "auto"
    QSV = "qsv"
    VAAPI = "vaapi"
    NVENC = "nvenc"
    VIDEOTOOLBOX = "videotoolbox"
    NONE = "none"


@dataclass
class TranscodeProfile:
    """转码配置"""
    name: str            # original, 4k, 1080p, 720p, 480p
    width: int | None = None
    height: int | None = None
    bitrate: str | None = None
    codec: str = "h264"
    audio_codec: str = "aac"
    audio_bitrate: str = "128k"

    @classmethod
    def get_profile(cls, quality: str) -> TranscodeProfile:
        profiles = {
            "original": cls(name="original", width=None, height=None, bitrate=None),
            "4k": cls(name="4k", width=3840, height=2160, bitrate="15000k"),
            "1080p": cls(name="1080p", width=1920, height=1080, bitrate="5000k"),
            "720p": cls(name="720p", width=1280, height=720, bitrate="2500k"),
            "480p": cls(name="480p", width=854, height=480, bitrate="1000k"),
        }
        return profiles.get(quality, profiles["720p"])


@dataclass
class TranscodeJob:
    """转码任务"""
    id: str
    media_id: int
    input_file: str
    profile: TranscodeProfile
    output_dir: Path
    status: str = "pending"  # pending / running / completed / failed / cancelled
    progress: float = 0.0
    pid: int | None = None
    error: str | None = None
    duration_sec: float = 0.0  # 源文件总时长（秒）
    created_at: float = field(default_factory=lambda: asyncio.get_event_loop().time())


class Transcoder:
    """FFmpeg 转码管理器"""

    def __init__(self):
        settings = get_settings()
        self.ffmpeg_path = settings.ffmpeg_path
        self.ffprobe_path = settings.ffprobe_path
        self.hw_accel = settings.hw_accel
        self.max_jobs = settings.max_transcode_jobs
        self.cache_dir = settings.transcode_cache_dir
        self._active_jobs: dict[str, TranscodeJob] = {}
        self._lock = asyncio.Lock()

    def detect_hw_accel(self) -> HWAccelType:
        """
        检测可用的硬件加速方式。
        优先级：NVENC > VAAPI/QSV(平台相关) > VideoToolbox > 软件编码
        """
        if self.hw_accel != "auto":
            return HWAccelType(self.hw_accel)

        # 1. 检测 NVIDIA GPU (所有平台)
        if shutil.which("nvidia-smi"):
            try:
                result = subprocess.run(
                    ["nvidia-smi", "--query-gpu=name,driver_version"],
                    capture_output=True, text=True, timeout=5,
                )
                if result.returncode == 0 and result.stdout.strip():
                    gpu_name = result.stdout.split("\n")[1].strip() if "\n" in result.stdout else ""
                    logger.info(f"Detected NVIDIA GPU ({gpu_name}), using NVENC")
                    return HWAccelType.NVENC
            except Exception:
                pass

        # 2. 检测 Intel QSV / D3D11VA (Windows)
        if sys.platform == "win32":
            try:
                # 通过 FFmpeg 检查 QSV 支持
                result = subprocess.run(
                    [self.ffmpeg_path, "-hwaccels"],
                    capture_output=True, text=True, timeout=5,
                )
                if "qsv" in result.stdout.lower():
                    logger.info("Detected Intel QSV support on Windows (D3D11VA)")
                    return HWAccelType.QSV
            except Exception:
                pass

        # 3. 检测 VAAPI (Linux)
        if sys.platform != "win32" and Path("/dev/dri/renderD128").exists():
            logger.info("Detected VAAPI device, using VAAPI")
            return HWAccelType.VAAPI

        # 4. 检测 QSV on Linux
        if sys.platform != "win32" and shutil.which("ls") is not None:
            try:
                result = subprocess.run(
                    ["ls", "/dev/dri/"],
                    capture_output=True, text=True, timeout=2,
                )
                if "renderD128" in result.stdout or "renderD129" in result.stdout:
                    try:
                        check_qsv = subprocess.run(
                            [self.ffmpeg_path, "-hwaccels"],
                            capture_output=True, text=True, timeout=5,
                        )
                        if "qsv" in check_qsv.stdout.lower():
                            logger.info("Detected Intel QSV on Linux")
                            return HWAccelType.QSV
                    except Exception:
                        pass
            except Exception:
                pass

        # 5. 检测 macOS VideoToolbox
        if sys.platform == "darwin":
            logger.info("macOS detected, using VideoToolbox")
            return HWAccelType.VIDEOTOOLBOX

        logger.info("No hardware acceleration detected, using software encoding (libx264)")
        return HWAccelType.NONE

    def _get_duration(self, file_path: str) -> float:
        """用 ffprobe 获取视频总时长（秒）"""
        try:
            result = subprocess.run(
                [
                    self.ffprobe_path, "-v", "quiet",
                    "-show_entries", "format=duration",
                    "-of", "default=noprint_wrappers=1:nokey=1",
                    file_path,
                ],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode == 0 and result.stdout.strip():
                return float(result.stdout.strip())
        except Exception as e:
            logger.warning(f"Failed to get duration with ffprobe: {e}")
        return 0.0

    def _build_transcode_cmd(
        self,
        input_file: str,
        output_playlist: str,
        profile: TranscodeProfile,
        hw_accel: HWAccelType,
    ) -> list[str]:
        """构建 FFmpeg HLS 转码命令，根据硬件加速类型选择最优参数"""
        cmd = [self.ffmpeg_path, "-y", "-hide_banner", "-loglevel", "warning"]

        # 输入
        cmd.extend(["-i", input_file])

        # ── 硬件加速参数 ──
        if hw_accel == HWAccelType.NVENC:
            # NVIDIA CUDA 硬件解码 + NVENC 编码
            cmd.extend(["-hwaccel", "cuda", "-hwaccel_output_format", "cuda"])
        elif hw_accel == HWAccelType.VAAPI:
            # Linux VAAPI
            cmd.extend([
                "-hwaccel", "vaapi",
                "-vaapi_device", "/dev/dri/renderD128",
                "-hwaccel_output_format", "vaapi",
            ])
        elif hw_accel == HWAccelType.QSV:
            # Intel Quick Sync Video (Windows D3D11VA / Linux)
            cmd.extend(["-hwaccel", "qsv", "-hwaccel_output_format", "nv12"])
        elif hw_accel == HWAccelType.VIDEOTOOLBOX:
            cmd.extend(["-hwaccel", "videotoolbox"])

        # ── 视频编码 ──
        if hw_accel == HWAccelType.NVENC:
            cmd.extend([
                "-c:v", "h264_nvenc",
                "-preset", "p4",       # P4 平衡质量与速度
                "-tune", "hq",         # 高质量调优
                "-rc", "vbr",          # 可变码率
                "-cq", "23",
            ])
        elif hw_accel == HWAccelType.VAAPI:
            cmd.extend([
                "-c:v", "h264_vaapi",
                "-profile:v", "high",
                "-compression_level", "8",
            ])
        elif hw_accel == HWAccelType.QSV:
            cmd.extend([
                "-c:v", "h264_qsv",
                "-preset", "medium",
                "-global_quality", "23",
            ])
        elif hw_accel == HWAccelType.VIDEOTOOLBOX:
            cmd.extend([
                "-c:v", "h264_videotoolbox",
                "-q:v", "65",
                "-realtime", "true",
            ])
        else:
            # 软件编码 libx264
            cmd.extend([
                "-c:v", "libx264",
                "-preset", "fast",
                "-crf", "23",
                "-tune", "film",
            ])

        # 分辨率缩放
        if profile.width and profile.height:
            if hw_accel == HWAccelType.VAAPI:
                cmd.extend(["-vf", f"scale_vaapi=w={profile.width}:h={profile.height}"])
            elif hw_accel == HWAccelType.NVENC:
                cmd.extend(["-vf", f"scale_cuda={profile.width}:{profile.height}"])
            elif hw_accel == HWAccelType.QSV:
                cmd.extend(["-vf", f"scale_qsv=w={profile.width}:h={profile.height}"])
            else:
                cmd.extend(["-vf", f"scale={profile.width}:h={profile.height}"])

        # 码率控制
        if profile.bitrate:
            cmd.extend(["-b:v", profile.bitrate])
            cmd.extend(["-maxrate", profile.bitrate])
            buf_val = int(int(profile.bitrate[:-1]) * 1.5)
            cmd.extend(["-bufsize", f"{buf_val}k"])

        # 音频
        cmd.extend(["-c:a", profile.audio_codec, "-b:a", profile.audio_bitrate])

        # 移除字幕流（避免编码问题）
        cmd.extend(["-sn"])

        # ── HLS 输出配置 ──
        seg_dir = str(Path(output_playlist).parent)
        cmd.extend([
            "-f", "hls",
            "-hls_time", "4",
            "-hls_list_size", "0",
            "-hls_segment_filename", str(Path(seg_dir) / "seg_%03d.ts"),
            "-hls_segment_type", "mpegts",
            output_playlist,
        ])

        return cmd

    async def get_or_create_hls(
        self,
        media_id: int,
        file_path: str,
        quality: str = "720p",
    ) -> dict[str, Any]:
        """获取或创建 HLS 转码任务"""
        job_key = f"{media_id}_{quality}"

        # 构建 API 可访问的 HLS URL（非本地文件路径）
        playlist_url = f"/api/playback/hls/{job_key}/playlist.m3u8"

        # 检查缓存
        cache_playlist = self.cache_dir / job_key / "playlist.m3u8"
        if cache_playlist.exists():
            return {"mode": "hls", "playlist_url": playlist_url, "cached": True}

        # 创建新转码任务
        async with self._lock:
            if job_key in self._active_jobs:
                job = self._active_jobs[job_key]
                if job.status in ("running", "pending"):
                    return {"mode": "hls", "playlist_url": playlist_url, "status": job.status}

        # 启动转码
        output_dir = self.cache_dir / job_key
        output_dir.mkdir(parents=True, exist_ok=True)
        output_playlist = str(output_dir / "playlist.m3u8")

        profile = TranscodeProfile.get_profile(quality)
        hw_accel = self.detect_hw_accel()

        job = TranscodeJob(
            id=job_key,
            media_id=media_id,
            input_file=file_path,
            profile=profile,
            output_dir=output_dir,
        )

        # 预获取视频时长用于进度计算
        loop = asyncio.get_event_loop()
        try:
            job.duration_sec = await loop.run_in_executor(None, self._get_duration, file_path)
        except Exception:
            pass

        asyncio.create_task(self._run_transcode(job, hw_accel))
        hw_name = hw_accel.value.upper()
        logger.info(f"[Transcoder] Job {job_key} started: {quality}, HW={hw_name}")
        return {"mode": "hls", "playlist_url": playlist_url, "status": "started"}

    async def _run_transcode(self, job: TranscodeJob, hw_accel: HWAccelType):
        """执行转码任务，实时解析 FFmpeg 输出计算进度百分比"""
        job.status = "running"
        self._active_jobs[job.id] = job

        output_playlist = str(job.output_dir / "playlist.m3u8")
        cmd = self._build_transcode_cmd(job.input_file, output_playlist, job.profile, hw_accel)

        hw_label = hw_accel.value
        logger.info(f"Starting transcode job {job.id}: mode={hw_label} quality={job.profile.name}")

        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            job.pid = process.pid

            # 读取 stderr 解析进度
            while True:
                line = await process.stderr.readline()
                if not line:
                    break
                text = line.decode("utf-8", errors="ignore").strip()
                # 解析 FFmpeg 进度: time=HH:MM:SS.mm
                if "time=" in text and "speed=" not in text:
                    try:
                        time_str = text.split("time=")[1].split(" ")[0]
                        parts = time_str.split(":")
                        if len(parts) >= 3:
                            h, m, s = parts[0], parts[1], parts[2]
                            current_time = float(h) * 3600 + float(m) * 60 + float(s)
                            # 用实际总时长计算百分比
                            if job.duration_sec > 0:
                                job.progress = min(99.0, (current_time / job.duration_sec) * 100)
                            else:
                                # 无时长信息时的降级方案：假设不超过60秒每%点
                                job.progress = min(99.0, current_time / 60.0)
                    except (ValueError, IndexError):
                        pass

            await process.wait()

            if process.returncode == 0:
                job.status = "completed"
                job.progress = 100.0
                logger.info(f"Transcode job {job.id} completed successfully")
            else:
                job.status = "failed"
                job.error = f"FFmpeg exited with code {process.returncode}"
                logger.error(f"Transcode job {job.id} failed: {job.error}")

        except asyncio.CancelledError:
            job.status = "cancelled"
            logger.info(f"Transcode job {job.id} cancelled")
        except Exception as e:
            job.status = "failed"
            job.error = str(e)
            logger.error(f"Transcode job {job.id} error: {e}")

    async def cancel_job(self, job_id: str):
        """取消转码任务"""
        job = self._active_jobs.get(job_id)
        if job and job.pid:
            try:
                if sys.platform == "win32":
                    os.kill(job.pid, _signal.CTRL_C_EVENT if hasattr(_signal, 'CTRL_C_EVENT') else _signal.SIGTERM)
                else:
                    os.kill(job.pid, _signal.SIGTERM)
            except (ProcessLookupError, OSError, ValueError):
                pass
            job.status = "cancelled"

    def get_job_status(self, job_id: str) -> dict:
        job = self._active_jobs.get(job_id)
        if not job:
            return {"status": "not_found"}
        return {
            "id": job.id,
            "status": job.status,
            "progress": round(job.progress, 1),
            "profile": job.profile.name,
            "duration_sec": job.duration_sec,
        }

    async def cleanup_cache(self, max_age_hours: int = 24):
        """清理过期的转码缓存"""
        import time
        cutoff = time.time() - max_age_hours * 3600
        cleaned = 0
        for entry in self.cache_dir.iterdir():
            if entry.is_dir():
                try:
                    mtime = entry.stat().st_mtime
                    if mtime < cutoff:
                        shutil.rmtree(entry, ignore_errors=True)
                        cleaned += 1
                except Exception:
                    pass
        logger.info(f"Cleaned up {cleaned} expired transcode cache directories")
        return cleaned
