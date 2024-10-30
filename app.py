from flask import Flask, request, jsonify, send_file, after_this_request
from flask_cors import CORS
from yt_dlp import YoutubeDL
from threading import Lock
import tempfile
import os
import shutil

app = Flask(__name__)
CORS(app, origins=["https://kinn00kinn.github.io/yt-dl-server-front.github.io/"])  # GitHub PagesのURLを指定

download_lock = Lock()

def download_video(url, format_option, quality):
    # 一時ディレクトリを作成
    temp_dir = tempfile.mkdtemp()

    # yt-dlpオプション設定
    ydl_opts = {
        "format": "bestaudio" if format_option == "audio" else "best",
        "outtmpl": os.path.join(temp_dir, "%(title)s.%(ext)s"),  # 動画タイトルをファイル名にする
        "noplaylist": True,
        "geo_bypass": True,  # 地理的制限を回避
        "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0",  # ヘッダー追加
        "http_headers": {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0"
        }
    }

    # 品質オプション設定
    if quality == "low":
        ydl_opts["format"] = "worstvideo+bestaudio" if format_option == "video" else "worstaudio"
    elif quality == "medium":
        ydl_opts["format"] = "best[height<=480]+bestaudio" if format_option == "video" else "bestaudio[abr<=128]"
    elif quality == "high":
        ydl_opts["format"] = "bestvideo+bestaudio"

    with YoutubeDL(ydl_opts) as ydl:
        info_dict = ydl.extract_info(url, download=True)
        filename = ydl.prepare_filename(info_dict)  # ダウンロードされたファイルの名前を取得

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

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
