import json
import logging
import os
from datetime import date, datetime, timezone
from functools import wraps
from pathlib import Path

from campuspulse_event_ingest_schema import NormalizedEvent
from flask import Flask, Response, jsonify, request
from flask import request as frequest
from flask_cors import CORS
from ics import Calendar, Event
from werkzeug.utils import secure_filename

app = Flask(__name__)
CORS(app)

alldata = []

MINIMUM_FILE_UPLOAD_SIZE_BYTES = 1024

input_dir = Path("./data")
if not input_dir.exists():
    input_dir.mkdir()
archive_dir = Path("./data/archive")
if not archive_dir.exists():
    archive_dir.mkdir()


def check_auth(username, password):
    expected_credential = os.getenv("UPLOAD_CREDENTIAL")
    if expected_credential is None or expected_credential == "":
        return False
    return username == "loader" and password == expected_credential


def login_required(f):
    """basic auth for api"""

    @wraps(f)
    def decorated_function(*args, **kwargs):
        auth = frequest.authorization
        if not auth or not check_auth(auth.username, auth.password):
            return jsonify({"message": "Authentication required"}), 401
        return f(*args, **kwargs)

    return decorated_function


@app.route("/v0/public.json", methods=["GET"])
def public_json():
    return jsonify(alldata)


@app.route("/v0/public.ics")
def public_ics():
    cal = Calendar()

    for event in alldata:
        try:
            cal_event = Event()
            cal_event.name = event["title"]
            cal_event.begin = event["start"]
            cal_event.end = event["end"]
            cal_event.description = event["description"]

            location = event["location"]
            location_str = ", ".join(
                filter(
                    None,
                    [
                        location.get("building"),
                        location.get("room_number"),
                        location.get("street"),
                        location.get("city"),
                        location.get("state"),
                        location.get("zipcode"),
                    ],
                )
            )
            if location_str:
                cal_event.location = location_str

            cal.events.add(cal_event)
        except Exception as e:
            print(e)

    response = Response(str(cal), mimetype="text/calendar")
    response.headers["Content-Disposition"] = "attachment; filename=calendar.ics"
    return response


def archive_file(archive_filename, timestamp, archive_path):
    archive_name = archive_path.with_name(
        f"{archive_filename.stem}_{timestamp}{archive_filename.suffix}"
    )
    archive_filename.rename(archive_name)


def allowed_file(filename):
    return "." in filename and filename.endswith(".parsed.normalized.ndjson")


@app.route("/v0/import", methods=["POST"])
@login_required
def upload():
    global alldata
    if "file" not in request.files:
        return jsonify({"message": "No Files Provided"}), 400
    file = request.files["file"]
    if file.filename == "":
        return jsonify({"message": "empty filename"}), 400
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        destination = input_dir.joinpath(filename)
        temp_dest = input_dir.joinpath(filename + "_temp")

        if temp_dest.exists():
            temp_dest.unlink()

        try:
            file.save(temp_dest)
        except Exception as e:
            app.logger.error(f"Error saving file {destination}: {e}")
            return jsonify({"message": "Error saving file"}), 500

        tempsize = temp_dest.stat().st_size
        if tempsize < MINIMUM_FILE_UPLOAD_SIZE_BYTES:
            app.logger.error(
                f"Error saving file {destination}: file size {tempsize} not greater than configured minimum {MINIMUM_FILE_UPLOAD_SIZE_BYTES}"
            )
            temp_dest.unlink()
            return jsonify({"message": "File too small"}), 400

        if destination.exists():
            timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
            archive_file(destination, timezone, archive_dir)

        temp_dest.rename(destination)
        app.logger.info(f"File saved successfully: {destination}")

        for item in input_dir.iterdir():
            if item != destination:
                if item.is_file():
                    try:
                        item.unlink()
                    except OSError as e:
                        app.logger.error(f"Error deleting file {item}: {e}")
        alldata = []
        update_data(input_dir)
        return jsonify({"message": "Success"}), 200


def update_data(input_dir):
    global alldata
    app.logger.info("Processing event data started")
    for datafile in input_dir.glob("*.parsed.normalized.ndjson"):
        if not datafile.is_file():
            continue
        tzun_count = 0
        for line in datafile.read_text().split("\n"):
            if line.strip() != "":
                event = NormalizedEvent.parse_obj(json.loads(line))
                try:
                    if not event.start < datetime.now(timezone.utc):
                        alldata.append(event)
                except TypeError as e:
                    if (
                        str(e)
                        != "can't compare offset-naive and offset-aware datetimes"
                    ):
                        raise
                    tzun_count += 1
        if tzun_count >= 1:
            app.logger.warning(
                f"file {datafile} contains {tzun_count} skipped timezone-unaware events"
            )

    alldata_tmp = sorted(alldata, key=lambda e: e.start)

    alldata_tmp = map(lambda e: e.dict(), alldata_tmp)
    alldata = list(alldata_tmp)

    app.logger.info("Processing event data complete")


if __name__ != "__main__":
    gunicorn_error_logger = logging.getLogger("gunicorn.error")
    app.logger.handlers = gunicorn_error_logger.handlers
    app.logger.setLevel(gunicorn_error_logger.level)


update_data(input_dir)

if __name__ == "__main__":
    app.run(debug=True, port=5000)
