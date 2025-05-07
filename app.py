from flask import Flask, request, jsonify, send_file, after_this_request
from flask_cors import CORS
from yt_dlp import YoutubeDL
from threading import Lock
import tempfile
import os
import shutil

app = Flask(__name__)
CORS(app, origins=["https://kinn00kinn.github.io"])  # フロントエンドからのCORS許可

download_lock = Lock()

def download_video(url, format_option, quality, cookies=None):
    temp_dir = tempfile.mkdtemp()

    # yt-dlp基本オプション
    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": os.path.join(temp_dir, "%(title)s.%(ext)s"),
        "noplaylist": True,
        "quiet": True,
        "geo_bypass": True,
        "nocheckcertificate": True,
        "http_headers": {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
        }
    }

    # クッキーが指定されていればヘッダーに追加
    if cookies:
        ydl_opts["http_headers"]["Cookie"] = cookies

    # 音声(mp3)形式オプション
    if format_option == "audio":
        ydl_opts["format"] = "bestaudio"
        ydl_opts["postprocessors"] = [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "192",
        }]

    # 映像(mp4)形式オプション
    elif format_option == "video":
        if quality == "low":
            ydl_opts["format"] = "worstvideo+bestaudio"
        elif quality == "medium":
            ydl_opts["format"] = "bestvideo[height<=480]+bestaudio"
        elif quality == "high":
            ydl_opts["format"] = "bestvideo+bestaudio"
        else:
            raise ValueError("Invalid quality option")
    else:
        raise ValueError("Invalid format option")

    with YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        filename = ydl.prepare_filename(info)
        if format_option == "audio":
            filename = os.path.splitext(filename)[0] + ".mp3"

    return filename, temp_dir

@app.route("/download", methods=["POST"])
def download():
    if not download_lock.acquire(blocking=False):
        return jsonify({"status": "busy"}), 429

    try:
        data = request.get_json()
        url = data.get("url")
        format_option = data.get("type")
        quality = data.get("quality", "high")
        cookies = data.get("cookies", None)

        if not url or format_option not in {"audio", "video"}:
            return jsonify({"error": "Invalid request parameters"}), 400

        filename, temp_dir = download_video(url, format_option, quality, cookies)

        @after_this_request
        def cleanup(response):
            try:
                shutil.rmtree(temp_dir)
            except Exception as e:
                app.logger.error(f"Failed to clean up: {e}")
            return response

        return send_file(filename, as_attachment=True, download_name=os.path.basename(filename))
    except Exception as e:
        app.logger.exception("Download failed:")
        return jsonify({"error": str(e)}), 500
    finally:
        download_lock.release()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
