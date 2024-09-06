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
            return obj.decode("utf-8")
        except Exception:
            return "Binary data"
    else:
        return str(obj)


def get_media_info(file_path: Path) -> dict:
    media_info = MediaInfo.parse(file_path)
    assert isinstance(media_info, MediaInfo)
    res: dict = media_info.to_data().get("tracks", [{}])[0]
    return {k: json_or_str(v) for k, v in res.items()}


def get_mutagen_metadata(file_path: Path) -> dict:
    try:
        audio: FileType = MutagenFile(file_path)  # type: ignore
    except Exception:
        return {}
    if audio is None:
        return {}
    elif audio:
        return {k: json_or_str(v) for k, (v,) in audio.items()}
    else:
        items = audio.info.__dict__.items()
        return {k: json_or_str(v) for k, v in items if not k.startswith("_")}


def get_pillow_metadata(file_path: Path) -> dict:
    res = {}
    try:
        with Image.open(file_path) as img:
            getxmp = img.getxmp()
            exif = img.getexif().items()
    except Exception:
        return {}

    if isinstance(img, PngImageFile):
        res.update({x: json_or_str(v) for x, v in img.info.items()})

    res.update({x: json_or_str(v) for k, v in exif if (x := TAGS.get(k))})
    if getxmp:
        desc = getxmp.get("xmpmeta", {}).get("RDF", {}).get("Description", {})
        if isinstance(desc, list):
            desc = reduce(lambda x, y: (x if isinstance(x, dict) else (x | y)), desc)
        res.update({k: json_or_str(v) for k, v in desc.items()})

    return res


def get_iptc_info(file_path: Path) -> dict:
    iptc = IPTCInfo(file_path)._data.items()
    return {x: json_or_str(v) for k, v in iptc if (x := IPTC_TAGS.get(k))}
