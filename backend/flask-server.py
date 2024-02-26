from flask import Flask, jsonify, request, send_file
from flask_cors import CORS
from schema import NormalizedEvent

app = Flask(__name__) 
CORS(app)

@app.route('/campus-pulse-api', methods = ['GET'])  
def hello():
    name = request.args.get('name')
    if name is None:
        text = 'Hello!'
    else: 
        text = 'Hello ' + name + '!'

    return jsonify({"message": text})

if __name__ == '__main__':
    app.run(debug=True, port=3500)