from flask import Flask, Response, jsonify, request, send_file
from flask_cors import CORS
from pathlib import Path
from icalendar import Calendar, Event
import json

from campuspulse_event_ingest_schema import NormalizedEvent
from datetime import datetime, date, timezone
import logging

app = Flask(__name__) 
CORS(app)

alldata = []

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
            cal_event.add('dtstart', datetime.strptime(event['start'], '%Y-%m-%dT%H:%M:%S%z'))
            cal_event.add('dtend', datetime.strptime(event['end'], '%Y-%m-%dT%H:%M:%S%z'))
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

input_dir = Path("./data")

update_data(input_dir)

if __name__ == '__main__':
    app.run(debug=True, port=5000)
