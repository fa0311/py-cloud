import json
import pathlib

from ffmpeg.asyncio import FFmpeg


class FFmpegWrapper:
    def __init__(self, input_file: pathlib.Path, ffprobe: dict):
        self.input_file = input_file
        self.ffprobe = ffprobe

    @classmethod
    async def from_file(cls, input_file: pathlib.Path):
        stream = (
            FFmpeg(executable="ffprobe")
            .input(input_file.as_posix())
            .option("show_format")
            .option("show_streams")
            .option("of", "json")
        )
        data = await stream.execute()
        ffprobe = json.loads(data)

        return cls(input_file, ffprobe)

    def is_video(self) -> bool:
        return float(self.ffprobe["format"].get("duration", 0)) > 0


class FFmpegVideo(FFmpegWrapper):
    def __init__(self, input_file: pathlib.Path, ffprobe: dict):
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
        for stream in self.ffprobe["streams"][1:]:
            if stream["codec_type"] == "video":
                return stream
        return None

    def check(self, width: int, bitrate: int) -> bool:
        if self.video["width"] < width:
            return True
        if int(self.video["bit_rate"]) < bitrate * 1024:
            return True

        return False

    async def thumbnail(self, output_dir: pathlib.Path, prefix: str):
        thumbnail = self.get_thumbnail_stream()
        if thumbnail is None:
            stream = (
                FFmpeg()
                .input(self.input_file.as_posix())
                .output(
                    output_dir.joinpath(f"thumbnail_{prefix}.png").as_posix(),
                    options={
                        "ss": 1,
                        "vf": "scale=320:320:force_original_aspect_ratio=decrease",
                        "frames:v": 1,
                        "y": None,
                    },
                )
            )
            await stream.execute()
        else:
            stream = (
                FFmpeg()
                .input(self.input_file.as_posix())
                .output(
                    output_dir.joinpath(f"thumbnail_{prefix}.png").as_posix(),
                    options={
                        "map": "v:1",
                        "c": "copy",
                        "frames:v": 1,
                        "y": None,
                    },
                )
            )
            print("ffmpeg" + " ".join([f'"{x}"' for x in stream.arguments[1:]]))
            await stream.execute()

    async def down_scale(
        self,
        output_dir: pathlib.Path,
        prefix: str,
        width: int,
        bitrate: int,
    ):
        stream = (
            FFmpeg()
            .input(self.input_file.as_posix())
            .output(
                output_dir.joinpath(f"hls_{prefix}.mkv").as_posix(),
                options={
                    "c:v": "h264_nvenc",
                    "c:a": "copy",
                    "vf": f"scale={width}:-1",
                    "b:v": f"{bitrate}k",
                    "y": None,
                },
            )
        )
        print("ffmpeg " + " ".join([f'"{x}"' for x in stream.arguments[1:]]))
        await stream.execute()
