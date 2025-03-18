import requests
from datetime import datetime, timezone
import xmltodict
import math
from flask import Flask, request, jsonify
import redis
import json
from geopy.geocoders import Nominatim
import configurations as config


app = Flask(__name__)
location = Nominatim(user_agent = "iss_tracker")


def wait_for_redis():
    max_retries = 30
    for _ in range(max_retries):
        try:
            config.rd.ping()
            print("Successfully connected to Redis")
            return
        except config.redis.exceptions.ConnectionError:
            print("Waiting for Redis to be ready...")
            time.sleep(1)
    raise Exception("Unable to connect to Redis after multiple attempts")




def data_read():
    if config.rd.keys("iss:*"):
        return "Data is already present"

    response = requests.get(url='https://nasa-public-data.s3.amazonaws.com/iss-coords/current/ISS_OEM/ISS.OEM_J2K_EPH.xml')
    data = xmltodict.parse(response.text)
    state_vector = data['ndm']['oem']['body']['segment']['data']['stateVector']

    for i in state_vector:
        epoch = i['EPOCH']
        config.rd.hset(f"iss:{epoch}", mapping={'EPOCH': vector['EPOCH'],'X': vector['X']['#text'], 'X_DOT': vector['X_DOT']['#text'],'Y': vector['Y']['#text'],'Y_DOT': vector['Y_DOT']['#text'], 'Z': vector['Z']['#text'],'Z_DOT': vector['Z_DOT']['#text']})

    return "Data stored in Redis"



#Returns entire dataset

@app.route('/epochs', methods=['GET'])

def all_epochs(): 
    try:
        keys = config.rd.keys("iss:*")
        keys.sort()

        epochs = [key.decode().split(':')[1] for key in keys]
        return jsonify({"epochs": epochs})
    except Exception as e:
        return jsonify({"error": str(e)}), 400

#modified lists of epoch
@app.route('/epochs?limit=int&offset=int', methods = ['GET'])
def get_epochs():
    try: 
        limit = request.args.get('limit', default=None, type=int)
        offset = request.args.get('offset', default=0, type=int)

        keys = config.rd.keys("iss:*")
        keys.sort()

        if limit:
            keys = keys[offset:offset+limit]
        else:
            keys = keys[offset:]

        epochs = [key.decode().split(':')[1] for key in keys]
        return {"epochs": epochs}
    except Exception as e:
        return {"error"}


#Returns the specific state vectors for specific epoch

@app.route('/epochs/<epoch>', methods=['GET'])
def specific_epoch(epoch):
    try:
        data = config.rd.hgetall(f"iss:{epoch}")
        if not data:
            return {"error": "Not found"}, 404
        return {k.decode(): json.loads(v.decode()) for k, v in data.items()}
    except Exception as e:
        return {"error"}


#Returns the instantaneous speed for a specific epoch
@app.route('/epochs/<epoch>/speed', methods=['GET'])
def speed_epoch(epoch):
    try: 
        data = config.rd.hgetall(f"iss:{epoch}")
        if not data:
            return {"error": "Not found"}, 404
    
        state_vector = {k.decode(): json.loads(v.decode()) for k, v in data.items()}
        speed = math.sqrt(float(state_vector['X_DOT'])**2 + float(state_vector['Y_DOT'])**2 + float(state_vector['Z_DOT'])**2)
        return {"speed": speed}
    except Exception as e:
        return {"error"}


#Returns the Longtitude, latitude, geopoisiton for specific Epoch

@app.route('/epochs/<epoch>/location', methods=['GET'])
def current_location(epoch):
    try:
        data = config.rd.hgetall(f"iss:{epoch}")
        if not data:
            return {"error": "Not found"}, 404

        x = float(data[b'X'].decode())
        y = float(data[b'Y'].decode())
        z = float(data[b'Z'].decode())

        lat = math.degrees(math.atan(z, math.sqrt(x**2 + y**2)))
        long = math.degrees(math.atan2(y.x)) - (datetime.datetime.now().hour * 15 + datetime.datetime.now().minute /4)
        altitude = math.sqrt(x**2 + y**2 + z**2) - 6371
        geographical_position = location.reverse(f"{lat}, {long}")
        return {"latitude": lat, "longtitude": long, "altitude": altitude, "geoposition": location}

    except Exception as e:
        return {"error"}


#Returns speed, latitude. longtitude, altitude, geoposistion for the epoch closest in time(refine)
@app.route('/now', methods=['GET'])
def current_closest_epoch():
    try:
        current_time = datetime.now(timezone.utc)
        keys = config.rd.keys("iss:*")

        closest_epoch = min(keys, key=lambda x: abs(datetime.strptime(x.decode().split(':')[1], "%Y-%jT%H:%M:%S.%fZ").replace(tzinfo=timezone.utc) - current_time))

        data_epoch = current_location(closest_epoch.decode().split(':')[1])
        data_speed = speed_epoch(closest_epoch.decode().split(':')[1])
        return {**data_epoch, **data_speed}

    except Exception as e: 
        return {"Error", str(e)}

if __name__ == '__main__':
    wait_for_redis()
    data_read()
    app.run(debug=True, host='0.0.0.0', port = 5000)
