from flask import Flask, jsonify, request, send_file
from flask_cors import CORS
from pathlib import Path
import json

from campuspulse_event_ingest_schema import NormalizedEvent
from datetime import datetime, date


app = Flask(__name__) 
CORS(app)

alldata = []

@app.route('/campus-pulse-api', methods = ['GET'])  
def hello():

    return jsonify(alldata)

def update_data(input_dir):
    global alldata
    for datafile in input_dir.glob("*.parsed.normalized.ndjson"):
        if not datafile.is_file():
            continue
        for line in datafile.read_text().split("\n"):
            if line.strip() != "":
                event = NormalizedEvent.parse_obj(json.loads(line))
                if not event.start < datetime.now():
                    alldata.append(event)


    alldata = sorted(alldata, key=lambda e: e.start)

    alldata = map(lambda e: e.dict(), alldata)
    alldata = list(alldata)


input_dir = Path("./data")

update_data(input_dir)

if __name__ == '__main__':


    app.run(debug=True, port=3500)