import pathlib
import shutil
from logging import Logger

import ffmpeg
from fastapi import APIRouter, Depends, File, UploadFile
from sqlmodel import Session

from src.depends.logging import LoggingDepends
from src.depends.sql import SQLDepends

router = APIRouter()


class FileResolver:
    base_path = pathlib.Path("./data/data")
    temp_path = pathlib.Path("./data/temp")

    @staticmethod
    def get_file(file_path: str) -> pathlib.Path:
        file = FileResolver.base_path.joinpath(file_path)
        file.parent.mkdir(parents=True, exist_ok=True)
        return file

    @staticmethod
    def get_temp(file_path: str) -> pathlib.Path:
        temp = FileResolver.temp_path.joinpath(file_path)
        temp.mkdir(parents=True, exist_ok=True)
        return temp


class FFmpegWrapper:
    def __init__(self, input_file: pathlib.Path):
        self.input_file = input_file
        self.ffprobe = ffmpeg.probe(input_file)
        self.stream = self.get_stream()

    def is_video(self) -> bool:
        return float(self.ffprobe["format"].get("duration", 0)) > 0

    def get_stream(self):
        for stream in self.ffprobe["streams"]:
            if stream["codec_type"] == "video":
                return stream
        raise ValueError("No video stream found")

    def check(self, width: int, bitrate: int) -> bool:
        if self.stream["width"] < width:
            return True
        if int(self.stream["bit_rate"]) < bitrate * 1024:
            return True
        return False

    def hls(
        self,
        output_dir: pathlib.Path,
        prefix: str,
        width: int,
        bitrate: int,
    ):
        param = {
            # "f": "hls",
            # "hls_time": 10,
            # "hls_segment_filename": output_dir.joinpath(f"hls_{prefix}_%06d.ts"),
            # "hls_playlist_type": "vod",
            # "c:v": "libx264",
            "c:v": "h264_nvenc",
            "c:a": "copy",
            "vf": f"scale={width}:-1",
            "b:v": f"{bitrate}k",
        }

        stream = ffmpeg.input(self.input_file.as_posix())
        stream = ffmpeg.output(
            stream,
            # output_dir.joinpath(f"hls_{prefix}.m3u8").as_posix(),
            output_dir.joinpath(f"hls_{prefix}.mp4").as_posix(),
            **param,
        )
        ffmpeg.run(stream, overwrite_output=True)


@router.post(
    "/upload/{file_path:path}",
    operation_id="post_upload",
    tags=["upload"],
    description="upload",
)
def post_upload(
    file_path: str,
    file: UploadFile = File(),
    logger: Logger = Depends(LoggingDepends.depends),
    session: Session = Depends(SQLDepends.depends),
):
    output_file = FileResolver.get_file(file_path)
    with output_file.open("wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    video = FFmpegWrapper(output_file)

    temp_dir = FileResolver.get_temp(file_path)

    if video.is_video():
        temp_dir = FileResolver.get_temp(file_path)

        if not video.check(640, 1000):
            video.hls(
                temp_dir,
                prefix="video_low",
                width=640,
                bitrate=250,
            )

        if not video.check(1280, 2000):
            video.hls(
                temp_dir,
                prefix="video_mid",
                width=1280,
                bitrate=500,
            )

        if not video.check(1920, 4000):
            video.hls(
                temp_dir,
                prefix="video_high",
                width=1920,
                bitrate=1000,
            )
