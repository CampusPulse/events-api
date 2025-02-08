from flask import Flask, Response, jsonify, request, send_file, request as frequest
from flask_cors import CORS
from pathlib import Path
from icalendar import Calendar, Event
import json

from campuspulse_event_ingest_schema import NormalizedEvent
from datetime import datetime, date, timezone
import logging
import os
from functools import wraps
from werkzeug.utils import secure_filename

app = Flask(__name__) 
CORS(app)

alldata = []

input_dir = Path("./data")
archive_dir = Path("./data/archive")


def check_auth(username, password):
    expected_credential = os.getenv("UPLOAD_CREDENTIAL")
    if expected_credential is None or expected_credential == "":
        return False
    return username == 'loader' and password == expected_credential

def login_required(f):
    """ basic auth for api """
    # https://stackoverflow.com/a/70317010/
    @wraps(f)
    def decorated_function(*args, **kwargs):
        auth = frequest.authorization
        if not auth or not check_auth(auth.username, auth.password):
            return jsonify({'message': 'Authentication required'}), 401
        return f(*args, **kwargs)
    return decorated_function

@app.route('/v0/public.json', methods = ['GET'])  
def public_json():

    return jsonify(alldata)

@app.route('/v0/public.ics')
def public_ics():    
    # Create a new calendar
    cal = Calendar()

    # Add events to the calendar
    for event in alldata:
        try:
            cal_event = Event()
            cal_event.add('summary', event['title'])
            cal_event.add('dtstart', event['start'])
            cal_event.add('dtend', event['end'])
            cal_event.add('description', event['description'])
            
            location = event['location']
            location_str = ', '.join(filter(None, [
                location.get('building'),
                location.get('room_number'),
                location.get('street'),
                location.get('city'),
                location.get('state'),
                location.get('zipcode')
            ]))
            cal_event.add('location', location_str)
            cal.add_component(cal_event)
        except Exception as e:
            print(e)
        
    # Create a response object
    response = Response(cal.to_ical(), mimetype='text/calendar')
    response.headers['Content-Disposition'] = 'attachment; filename=calendar.ics'
    
    return response

def archive_file(archive_filename, timestamp, archive_path):
    archive_name = archive_path.with_name(f"{archive_filename.stem}_{timestamp}{archive_filename.suffix}")
    archive_filename.rename(archive_name)



def allowed_file(filename):
    return '.' in filename and filename.endswith(".parsed.normalized.ndjson")

@app.route('/v0/import', methods=["POST"])
@login_required
def upload():

    # check if the post request has the file part
    if 'file' not in request.files:
        return jsonify({'message': 'No Files Provided'}), 400
    file = request.files['file']
    # If the user does not select a file, the browser submits an
    # empty file without a filename.
    if file.filename == '':
        return jsonify({'message': 'empty filename'}), 400
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        destination = input_dir.joinpath(filename)
        if destination.exists():
            timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
            archive_file(destination, timezone, archive_dir)
        file.save()
        return jsonify({'message': 'Success'}), 200

def update_data(input_dir):
    global alldata
    app.logger.info("Processing event data started")
    for datafile in input_dir.glob("*.parsed.normalized.ndjson"):
        if not datafile.is_file():
            continue
        tzun_count = 0
        for line in datafile.read_text().split("\n"):
            if line.strip() != "":
                # TODO: update date filters on each request or on a schedule to keep it up to date

                event = NormalizedEvent.parse_obj(json.loads(line))
                try:
                    if not event.start < datetime.now(timezone.utc):
                        alldata.append(event)
                except TypeError as e:
                    if str(e) != "can't compare offset-naive and offset-aware datetimes":
                        # app.logger.error(f"file {datafile }")

                        raise
                    tzun_count += 1
        if tzun_count >= 1:
            app.logger.warning(f"file {datafile} contains {tzun_count} skipped timezone-unaware events")


    alldata_tmp = sorted(alldata, key=lambda e: e.start)

    alldata_tmp = map(lambda e: e.dict(), alldata_tmp)
    alldata = list(alldata_tmp)

    app.logger.info("Processing event data complete")


if __name__ != '__main__':

    gunicorn_error_logger = logging.getLogger('gunicorn.error')
    app.logger.handlers = gunicorn_error_logger.handlers
    app.logger.setLevel(gunicorn_error_logger.level)


update_data(input_dir)

if __name__ == '__main__':
    app.run(debug=True, port=5000)
