import shutil

from aiofiles.ospath import wrap

copyfile = wrap(shutil.copyfile)
copy = wrap(shutil.copy)
copy2 = wrap(shutil.copy2)
copytree = wrap(shutil.copytree)
rmtree = wrap(shutil.rmtree)
move = wrap(shutil.move)
