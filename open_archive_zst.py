import pathlib
import zstandard

src = pathlib.Path("for_hackathon.zst")
dst = pathlib.Path("for_hackathon.unpacked")

if not src.exists():
    raise SystemExit("Файл for_hackathon.zst не найден")

with src.open("rb") as fsrc, dst.open("wb") as fdst:
    zstandard.ZstdDecompressor().copy_stream(fsrc, fdst)

print("Распаковка завершена:", dst)