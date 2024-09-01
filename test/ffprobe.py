from PIL import Image
from PIL.ExifTags import TAGS

filename = "sample.png"
img = Image.open(filename)
dict = img.getexif()
for id, value in dict.items():
    print(id, TAGS.get(id), value)


# Outputs data whose chunk type is "tEXt", "zTXt", "iTXt".

from PIL import Image
from PIL.PngImagePlugin import PngInfo

filename = "sample.png"
img = Image.open(filename)
metadata = PngInfo()


print(metadata.chunks)
