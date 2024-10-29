from flask import Flask, request, jsonify, send_file, after_this_request
from flask_cors import CORS
from yt_dlp import YoutubeDL
from threading import Lock
import tempfile
import os
import shutil

app = Flask(__name__)
CORS(app, origins=["http://localhost:5500", "http://127.0.0.1:5500"])  # 両方のオリジンを許可

download_lock = Lock()

def download_video(url, format_option, quality):
    # 一時ディレクトリを作成
    temp_dir = tempfile.mkdtemp()
    ydl_opts = {
        "format": "bestaudio" if format_option == "audio" else "best",
        "outtmpl": os.path.join(temp_dir, "downloaded.%(ext)s")
    }
    if quality == "low":
        ydl_opts["format"] = "worst" if format_option == "video" else "worstaudio"
    elif quality == "medium":
        ydl_opts["format"] = "best[height<=480]" if format_option == "video" else "bestaudio[abr<=128]"

    with YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])
        info_dict = ydl.extract_info(url, download=False)
        filename = ydl.prepare_filename(info_dict)
    return filename, temp_dir

@app.route("/download", methods=["POST"])
def download():
    if not download_lock.acquire(blocking=False):
        return jsonify({"status": "busy"}), 429

    try:
        data = request.get_json()
        url = data.get("url")
        format_option = data.get("type")
        quality = data.get("quality")

        filename, temp_dir = download_video(url, format_option, quality)

        # リクエスト後に一時ファイルを削除する処理
        @after_this_request
        def remove_file(response):
            try:
                shutil.rmtree(temp_dir)  # 一時ディレクトリとその中のファイルを削除
            except Exception as e:
                app.logger.error(f"Error removing or cleaning up temp files: {e}")
            return response

        # ファイルを送信
        return send_file(filename, as_attachment=True, download_name=os.path.basename(filename))
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        download_lock.release()

import os

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
