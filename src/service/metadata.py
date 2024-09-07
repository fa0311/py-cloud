from pathlib import Path

from src.util.aiometadata import (
    get_iptc_info,
    get_media_info,
    get_mutagen_metadata,
    get_pillow_metadata,
)
from src.util.ffmpeg import FFmpegWrapper


class MetadataFile:
    def __init__(
        self,
        path: Path,
        ffmpeg: FFmpegWrapper,
        media_info: dict,
        mutagen: dict,
        pillow: dict,
        iptc_info: dict,
    ):
        self.path = path
        self.ffmpeg = ffmpeg
        self.media_info = media_info
        self.mutagen = mutagen
        self.pillow = pillow
        self.iptc_info = iptc_info

    def to_dict(self):
        return {
            "ffprobe": self.ffmpeg.ffprobe,
            "media_info": self.media_info,
            "mutagen": self.mutagen,
            "pillow": self.pillow,
            "iptc_info": self.iptc_info,
        }

    def get_internet_media_type(self):
        return self.media_info.get("internet_media_type", "application/octet-stream")

    @classmethod
    async def factory(cls, path: Path):
        return cls(
            path=path,
            ffmpeg=await FFmpegWrapper.from_file(path),
            media_info=await get_media_info(path),
            mutagen=await get_mutagen_metadata(path),
            pillow=await get_pillow_metadata(path),
            iptc_info=await get_iptc_info(path),
        )
