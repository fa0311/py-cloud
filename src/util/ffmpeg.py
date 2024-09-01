import pathlib

import ffmpeg


class FFmpegWrapper:
    def __init__(self, input_file: pathlib.Path, ffprobe: dict):
        self.input_file = input_file
        self.ffprobe = ffprobe
        self.stream = self.get_stream()

    @classmethod
    def from_file(cls, input_file: pathlib.Path):
        ffprobe = ffmpeg.probe(input_file)
        return cls(input_file, ffprobe)

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
