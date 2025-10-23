# app.py
import os
import threading
import time
from pathlib import Path
from flask import Flask, render_template, request, jsonify, send_file, abort
from downloader import make_job_id, download_url_to, BASE_DOWNLOADS

# Config: token for basic auth (set env var WEB_TOKEN for deployment)
WEB_TOKEN = os.getenv("WEB_TOKEN", "secret")

app = Flask(__name__, static_folder="static", template_folder="templates")

# job store in-memory (simple). For production, usar DB/Redis.
# job structure: { job_id: {"status":"queued/downloading/done/error", "url":..., "path":..., "error":...} }
jobs = {}

def authorized(req):
    token = req.headers.get("X-Auth-Token") or req.form.get("token") or req.args.get("token")
    return token == WEB_TOKEN

def worker_download(job_id, url, as_audio):
    jobs[job_id]["status"] = "downloading"
    try:
        # cada job tem sua própria pasta
        job_dir = BASE_DOWNLOADS / job_id
        job_dir.mkdir(parents=True, exist_ok=True)
        filepath = download_url_to(job_dir, url, as_audio)
        jobs[job_id]["status"] = "done"
        jobs[job_id]["path"] = str(filepath)
        # pega o nome do vídeo
        jobs[job_id]["title"] = filepath.stem  # nome do arquivo sem extensão
    except Exception as e:
        jobs[job_id]["status"] = "error"
        jobs[job_id]["error"] = str(e)


@app.route("/")
def index():
    # NB: For security, we can require the token in query param if desired.
    return render_template("index.html")

@app.route("/api/download", methods=["POST"])
def api_download():
    if not authorized(request):
        return jsonify({"error":"Unauthorized"}), 401

    data = request.form or request.json
    if not data:
        return jsonify({"error":"no data"}), 400

    url = data.get("url") or request.form.get("url")
    formato = (data.get("formato") or request.form.get("formato") or "mp3").lower()
    if not url:
        return jsonify({"error":"Missing url"}), 400

    as_audio = formato == "mp3"
    job_id = make_job_id()
    jobs[job_id] = {"status":"queued", "url": url, "format": formato, "created": time.time()}

    # start background thread
    t = threading.Thread(target=worker_download, args=(job_id, url, as_audio), daemon=True)
    t.start()

    return jsonify({"job_id": job_id}), 202

@app.route("/api/status/<job_id>", methods=["GET"])
def api_status(job_id):
    if not authorized(request):
        return jsonify({"error":"Unauthorized"}), 401
    job = jobs.get(job_id)
    if not job:
        return jsonify({"error":"job not found"}), 404
    return jsonify(job)

@app.route("/api/result/<job_id>", methods=["GET"])
def api_result(job_id):
    if not authorized(request):
        return jsonify({"error":"Unauthorized"}), 401
    job = jobs.get(job_id)
    if not job:
        return jsonify({"error":"job not found"}), 404
    if job.get("status") != "done":
        return jsonify({"error":"job not finished", "status": job.get("status")}), 400
    path = job.get("path")
    if not path or not Path(path).exists():
        return jsonify({"error":"file not found"}), 404
    # send file as attachment
    return send_file(path, as_attachment=True)

# optional: endpoint to upload .txt with multiple links
@app.route("/api/upload_txt", methods=["POST"])
def api_upload_txt():
    if not authorized(request):
        return jsonify({"error":"Unauthorized"}), 401
    uploaded = request.files.get("file")
    if not uploaded:
        return jsonify({"error":"no file uploaded"}), 400
    content = uploaded.read().decode("utf-8", errors="ignore")
    # parse lines
    links = [line.strip() for line in content.splitlines() if line.strip()]
    job_ids = []
    for url in links:
        job_id = make_job_id()
        jobs[job_id] = {"status":"queued", "url": url, "format":"mp3", "created": time.time()}
        t = threading.Thread(target=worker_download, args=(job_id, url, True), daemon=True)
        t.start()
        job_ids.append(job_id)
    return jsonify({"jobs": job_ids}), 202

if __name__ == "__main__":
    # For local dev:
    app.run(host="0.0.0.0", port=5000, debug=True)
