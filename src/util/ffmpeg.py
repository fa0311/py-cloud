import json
import logging
from pathlib import Path
from typing import Any, Union

from aiofiles.ospath import wrap
from ffmpeg.asyncio import FFmpeg as AsyncFFmpeg
from ffmpeg.ffmpeg import FFmpeg as SyncFFmpeg

FFmpeg = SyncFFmpeg if __debug__ else AsyncFFmpeg


class FFmpegWrapper:
    logger = logging.getLogger(__name__)

    def __init__(self, input_file: Path, ffprobe: dict[str, Any]):
        self.input_file = input_file
        self.ffprobe = ffprobe

    @classmethod
    async def execute(cls, stream: Union[SyncFFmpeg, AsyncFFmpeg]):
        cmd = [stream._executable] + [f'"{x}"' for x in stream.arguments[1:]]
        cls.logger.info(" ".join(cmd))
        if __debug__:
            assert isinstance(stream, SyncFFmpeg)
            return await wrap(stream.execute)()
        else:
            assert isinstance(stream, AsyncFFmpeg)
            return await stream.execute()

    @classmethod
    async def from_file(cls, input_file: Path):
        stream = (
            FFmpeg(executable="ffprobe")
            .input(input_file.as_posix())
            .option("show_format")
            .option("show_streams")
            .option("of", "json")
        )
        try:
            data = await cls.execute(stream)
            ffprobe = json.loads(data)
        except Exception:
            ffprobe = {
                "format": {},
                "streams": [],
            }

        return cls(input_file, ffprobe)

    def is_video(self) -> bool:
        return float(self.ffprobe["format"].get("duration", 0)) > 0


class FFmpegVideo(FFmpegWrapper):
    def __init__(self, input_file: Path, ffprobe: dict[str, Any]):
        super().__init__(input_file, ffprobe)
        video = self.get_video_stream()
        if video is None:
            raise ValueError("No video stream found")
        self.video = video

    def get_video_stream(self):
        for stream in self.ffprobe["streams"]:
            if stream["codec_type"] == "video":
                return stream
        return None

    def get_thumbnail_stream(self):
        video = [x for x in self.ffprobe["streams"] if x["codec_type"] == "video"]
        if len(video) > 1:
            return video[1]
        return None

    def check(self, width: int, bitrate: int) -> bool:
        if self.video["width"] < width:
            return True
        if int(self.video["bit_rate"]) < bitrate * 1024:
            return True

        return False

    async def thumbnail(self, output_dir: Path, prefix: str) -> Path:
        thumbnail = self.get_thumbnail_stream()
        output_path = output_dir.joinpath(f"thumbnail_{prefix}.png")
        if thumbnail is None:
            stream = (
                FFmpeg()
                .input(self.input_file.as_posix())
                .output(
                    output_path.as_posix(),
                    options={
                        "ss": 1,
                        "vf": "scale=320:320:force_original_aspect_ratio=decrease",
                        "frames:v": 1,
                        "y": None,
                    },
                )
            )
        else:
            stream = (
                FFmpeg()
                .input(self.input_file.as_posix())
                .output(
                    output_path.as_posix(),
                    options={
                        "map": "v:1",
                        "c": "copy",
                        "frames:v": 1,
                        "y": None,
                    },
                )
            )
        await self.__class__.execute(stream)
        return output_path

    async def down_scale(
        self,
        output_dir: Path,
        prefix: str,
        width: int,
        bitrate: int,
    ) -> Path:
        output_path = output_dir.joinpath(f"hls_{prefix}{output_dir.suffix}")
        stream = (
            FFmpeg()
            .input(self.input_file.as_posix())
            .output(
                output_path.as_posix(),
                options={
                    "c:v": "h264_nvenc",
                    "c:a": "copy",
                    "vf": f"scale={width}:-1",
                    "b:v": f"{bitrate}k",
                    "y": None,
                },
            )
        )
        self.logger.info("ffmpeg " + " ".join([f'"{x}"' for x in stream.arguments[1:]]))
        await self.__class__.execute(stream)
        return output_path
