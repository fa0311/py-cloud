from aiofiles.ospath import wrap

from src.util import metadata

get_media_info = wrap(metadata.get_media_info)
get_mutagen_metadata = wrap(metadata.get_mutagen_metadata)
get_pillow_metadata = wrap(metadata.get_pillow_metadata)
get_iptc_info = wrap(metadata.get_iptc_info)
