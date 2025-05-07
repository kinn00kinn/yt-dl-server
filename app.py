from flask import Flask, request, jsonify, send_file, after_this_request
from flask_cors import CORS
from yt_dlp import YoutubeDL
from threading import Lock
import tempfile
import os
import shutil

app = Flask(__name__)
CORS(app, origins=["https://kinn00kinn.github.io"])  # GitHub Pages フロントエンドからの許可

download_lock = Lock()

def save_cookies_to_file(cookies_str):
    """ クッキー文字列をNetscape形式で一時ファイルに保存 """
    cookies_file = tempfile.mktemp(suffix='.txt')
    with open(cookies_file, 'w') as f:
        f.write(cookies_str)
    return cookies_file

def download_video(url, format_option, quality, cookies_file):
    """ yt-dlpを使って動画をダウンロード """
    temp_dir = tempfile.mkdtemp()

    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": os.path.join(temp_dir, "%(title)s.%(ext)s"),
        "noplaylist": True,
        "quiet": True,
        "geo_bypass": True,
        "nocheckcertificate": True,
        "cookiefile": cookies_file,  # クッキーを指定
    }

    if format_option == "audio":
        ydl_opts["format"] = "bestaudio"
        ydl_opts["postprocessors"] = [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "192",
        }]
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
        cookies = data.get("cookies", "")

        if not url or format_option not in {"audio", "video"}:
            return jsonify({"error": "Invalid request parameters"}), 400

        # クッキーをNetscape形式のファイルに保存
        if cookies:
            cookies_file = save_cookies_to_file(cookies)
        else:
            cookies_file = None

        filename, temp_dir = download_video(url, format_option, quality, cookies_file)

        @after_this_request
        def cleanup(response):
            try:
                shutil.rmtree(temp_dir)
                if cookies_file:
                    os.remove(cookies_file)  # クッキーの一時ファイルを削除
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
