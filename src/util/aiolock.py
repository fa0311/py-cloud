# import fcntl
# import msvcrt
# import sys


# from aiofiles import open
# from aiofiles.ospath import wrap


# class FileLockBase:
#     def __init__(self, filepath: Path) -> None:
#         self.filepath = filepath
#         self.file = None

#     async def __aenter__(self):
#         raise NotImplementedError

#     async def __aexit__(self, exc_type, exc_val, exc_tb):
#         raise NotImplementedError


# class WindowsFileLock(FileLockBase):
#     async def __aenter__(self):
#         self.file = await open(self.filepath, "wb")
#         wrap(msvcrt.locking)(self.file.fileno(), msvcrt.LK_LOCK, 0)
#         return self.file

#     async def __aexit__(self, exc_type, exc_val, exc_tb):
#         wrap(msvcrt.locking)(self.file.fileno(), msvcrt.LK_UNLCK, 0)
#         await self.file.close()


# class UnixFileLock(FileLockBase):
#     async def __aenter__(self):
#         self.file = await open(self.filepath, "wb")
#         await wrap(fcntl.flock)(self.file.fileno(), fcntl.LOCK_EX)  # type: ignore
#         return self.file

#     async def __aexit__(self, exc_type, exc_val, exc_tb):
#         await wrap(fcntl.flock)(self.file.fileno(), fcntl.LOCK_UN)  # type: ignore
#         await self.file.close()


# class FileLock(FileLockBase):
#     clas = WindowsFileLock if sys.platform == "win32" else UnixFileLock

#     async def __aenter__(self):
#         self.file = self.clas(self.filepath)
#         return await self.file.__aenter__()

#     async def __aexit__(self, exc_type, exc_val, exc_tb):
#         return await self.file.__aexit__(exc_type, exc_val, exc_tb)


# class FileLock:
#     def __init__(self, filepath: Path, new: bool) -> None:
#         self.filepath = filepath
#         self.new = new

#     async def __aenter__(self):
#         rename = self.filepath.with_suffix(".lock")
#         if not self.new:
#             await os.rename(self.filepath, rename)
#         return rename

#     async def __aexit__(self, exc_type, exc_val, exc_tb):
#         if self.new:
#             await os.rename(self.filepath.with_suffix(".lock"), self.filepath)
#         return False
