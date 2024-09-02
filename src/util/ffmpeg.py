import pathlib

import ffmpeg


class FFmpegWrapper:
    def __init__(self, input_file: pathlib.Path, ffprobe: dict):
        self.input_file = input_file
        self.ffprobe = ffprobe

    @classmethod
    def from_file(cls, input_file: pathlib.Path):
        ffprobe = ffmpeg.probe(input_file)
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

    def thumbnail(self, output_dir: pathlib.Path, prefix: str):
        thumbnail = self.get_thumbnail_stream()
        if thumbnail is None:
            stream = ffmpeg.input(self.input_file.as_posix())
            stream = ffmpeg.output(
                stream,
                output_dir.joinpath(f"thumbnail_{prefix}.png").as_posix(),
                **{
                    "ss": 1,
                    "vf": "scale=320:320:force_original_aspect_ratio=decrease",
                    "vframes": 1,
                },
            )
            ffmpeg.run(stream, overwrite_output=True)
        else:
            stream = ffmpeg.input(self.input_file.as_posix())

            stream = ffmpeg.output(
                stream["v:1"],
                output_dir.joinpath(f"thumbnail_{prefix}.png").as_posix(),
                **{
                    "c": "copy",
                },
            )
            print(ffmpeg.get_args(stream))
            ffmpeg.run(stream, overwrite_output=True)

    def down_scale(
        self,
        output_dir: pathlib.Path,
        prefix: str,
        width: int,
        bitrate: int,
    ):
        param = {
            "c:v": "h264_nvenc",
            "c:a": "copy",
            "vf": f"scale={width}:-1",
            "b:v": f"{bitrate}k",
        }

        stream = ffmpeg.input(self.input_file.as_posix())
        stream = ffmpeg.output(
            stream,
            output_dir.joinpath(f"hls_{prefix}.mp4").as_posix(),
            **param,
        )
        print(ffmpeg.get_args(stream))
        ffmpeg.run(stream, overwrite_output=True)
