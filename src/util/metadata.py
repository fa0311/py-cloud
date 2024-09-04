import json
from functools import reduce
from pathlib import Path
from typing import Any

from iptcinfo3 import IPTCInfo
from mutagen._file import File as MutagenFile
from mutagen._file import FileType
from PIL import ExifTags, Image
from PIL.PngImagePlugin import PngImageFile
from pillow_heif import register_heif_opener
from pymediainfo import MediaInfo

register_heif_opener()


REMOVABLE_TAGS = [
    "XMLPacket",
]

TAGS = {k: v for k, v in ExifTags.TAGS.items() if v not in REMOVABLE_TAGS}

MEDIA_EXTENSIONS = [".pdf", ".zip", ".mp4", ".mov", ".webm", ".mkv"]
AUDIO_EXTENSIONS = [".flac", ".mp3", ".ogg", ".wav"]
IMAGE_EXTENSIONS = [
    ".heic",
    ".jpeg",
    ".jpg",
    ".tiff",
    ".tif",
    ".png",
    ".bmp",
    ".gif",
    ".webp",
    ".ico",
]
IPTC_TAGS = {
    5: "ObjectName",
    7: "EditStatus",
    10: "Urgency",
    15: "Category",
    20: "SupplementalCategories",
    22: "FixtureIdentifier",
    25: "Keywords",
    30: "ReleaseDate",
    35: "ReleaseTime",
    37: "ExpirationDate",
    38: "ExpirationTime",
    40: "SpecialInstructions",
    45: "ReferenceService",
    47: "ReferenceDate",
    50: "ReferenceNumber",
    55: "DateCreated",
    60: "TimeCreated",
    65: "DigitalCreationDate",
    70: "DigitalCreationTime",
    75: "OriginatingProgram",
    80: "ProgramVersion",
    85: "ObjectCycle",
    90: "Byline",
    95: "BylineTitle",
    100: "City",
    101: "SubLocation",
    103: "ProvinceState",
    105: "CountryPrimaryLocationCode",
    110: "CountryPrimaryLocationName",
    115: "OriginalTransmissionReference",
    116: "Headline",
    120: "Credit",
    122: "Source",
    125: "CopyrightNotice",
    130: "Contact",
    135: "CaptionAbstract",
    150: "WriterEditor",
    199: "ImageType",
    200: "ImageOrientation",
    220: "LanguageIdentifier",
    221: "AudioType",
    222: "AudioSamplingRate",
    223: "AudioSamplingResolution",
    224: "AudioDuration",
    225: "AudioOutcue",
    230: "JobID",
    231: "MasterDocumentID",
    232: "ShortDocumentID",
    233: "UniqueDocumentID",
    234: "OwnerID",
    240: "ObjectPreviewFileFormat",
    241: "ObjectPreviewFileFormatVersion",
    242: "ObjectPreviewData",
    255: "CatalogSets",
}


def json_or_str(obj: Any) -> str:
    if isinstance(obj, dict):
        try:
            return json.dumps(obj)
        except Exception:
            return "Unsupported dict"
    elif isinstance(obj, (list, tuple)):
        return json.dumps([json_or_str(item) for item in obj])
    elif isinstance(obj, (bytes, bytearray)):
        try:
            try:
                try:
                    return obj.decode("utf-8")
                except Exception:
                    return obj.decode("utf-16")
            except Exception:
                return obj.decode("shift-jis")
        except Exception:
            return "Binary data"
    else:
        return str(obj)


def get_metadata(file_path: Path):
    file_extension = file_path.suffix.lower()

    if file_extension in MEDIA_EXTENSIONS:
        return get_media_info(file_path)
    elif file_extension in AUDIO_EXTENSIONS:
        return get_audio_metadata(file_path)
    elif file_extension in IMAGE_EXTENSIONS:
        return get_image_metadata(file_path)
    else:
        return None


def get_media_info(file_path: Path):
    media_info = MediaInfo.parse(file_path)
    assert isinstance(media_info, MediaInfo)
    res = media_info.to_data()["tracks"][0]  # type: ignore
    return {k: json_or_str(v) for k, v in res.items()}


def get_audio_metadata(file_path: Path):
    audio: FileType = MutagenFile(file_path)  # type: ignore https://github.com/microsoft/pyright/discussions/8608
    if audio:
        return {k: json_or_str(v) for k, (v,) in audio.items()}
    else:
        items = audio.info.__dict__.items()
        return {k: json_or_str(v) for k, v in items if not k.startswith("_")}


def get_image_metadata(file_path: Path):
    res = {}
    with Image.open(file_path) as img:
        getxmp = img.getxmp()
        exif = img.getexif().items()

    if isinstance(img, PngImageFile):
        res.update(img.info)

    if img.info.get("photoshop"):
        iptc = IPTCInfo(file_path)._data.items()
        res.update({x: json_or_str(v) for k, v in iptc if (x := IPTC_TAGS.get(k))})

    res.update({x: json_or_str(v) for k, v in exif if (x := TAGS.get(k))})
    if getxmp:
        desc = getxmp["xmpmeta"]["RDF"]["Description"]  # type: ignore https://github.com/microsoft/pyright/discussions/8608
        if isinstance(desc, list):
            desc = reduce(lambda x, y: (x if isinstance(x, dict) else (x | y)), desc)
        res.update({k: json_or_str(v) for k, v in desc.items()})

    return res
