# downloader.py
import os
import yt_dlp
import uuid
from pathlib import Path

BASE_DOWNLOADS = Path("downloads")
BASE_DOWNLOADS.mkdir(exist_ok=True)

def make_job_id():
    return uuid.uuid4().hex

def make_ydl_opts(output_dir: Path, as_audio: bool):
    outtmpl = str(output_dir / "%(title)s.%(ext)s")
    opts = {
        "outtmpl": outtmpl,
        "noplaylist": True,
        "ignoreerrors": True,
        "quiet": True,  # we capture logs via ydl params, but keep this for clarity
    }
    if as_audio:
        opts.update({
            "format": "bestaudio/best",
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }],
        })
    else:
        opts["format"] = "bestvideo+bestaudio/best"
    return opts

def download_url_to(output_dir: Path, url: str, as_audio: bool):
    """
    Downloads and returns the absolute path of resulting file.
    May raise exceptions from yt_dlp.
    """
    options = make_ydl_opts(output_dir, as_audio)
    with yt_dlp.YoutubeDL(options) as ydl:
        info = ydl.extract_info(url, download=True)
        # info can be dict or None
        if not info:
            raise RuntimeError("Não foi possível obter informações do vídeo.")
        # title + ext
        title = info.get("title")
        # determine ext produced
        ext = "mp3" if as_audio else info.get("ext", "mp4")
        filename = f"{title}.{ext}"
        filepath = output_dir / filename
        # In some cases ext from info may differ; attempt to find matching file
        if not filepath.exists():
            # try to find a file that starts with title in output_dir
            matches = list(output_dir.glob(f"{title}.*"))
            if matches:
                filepath = matches[0]
            else:
                raise FileNotFoundError(f"Arquivo final não encontrado para: {title}")
        return filepath.resolve()
