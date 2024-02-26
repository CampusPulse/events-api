from flask import Flask, jsonify, request, send_file
from flask_cors import CORS
from pathlib import Path
import json

from campuspulse_event_ingest_schema import NormalizedEvent

app = Flask(__name__) 
CORS(app)

alldata = []

@app.route('/campus-pulse-api', methods = ['GET'])  
def hello():

    return jsonify(alldata)

if __name__ == '__main__':

    input_dir = Path("./data")
    
    for datafile in input_dir.glob("*.parsed.normalized.ndjson"):
        if not datafile.is_file():
            continue

        for line in datafile.read_text():   
            alldata.append(NormalizedEvent.parse_obj(json.loads(line)))


    app.run(debug=True, port=3500)