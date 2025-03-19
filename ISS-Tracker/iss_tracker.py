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
response = requests.get(url='https://nasa-public-data.s3.amazonaws.com/iss-coords/current/ISS_OEM/ISS.OEM_J2K_EPH.xml')


def data_range(response: str) -> None:
    '''
    This functions purpose is to give the data range for the epochs from the first to last one

    Arguments:

    reponse: the xml converted string file we are using to pull the data from. The XML file was created from the ISS data found in the nasa website

    Returns:

    It is supposed to return a statement which contains the date range which is present for the whole datset. If there is an error then it is supposed to return an "error" message.

    '''

    epochs = [line.strip() for line in response.split('\n') if '<EPOCH>' in line]

    if epochs:
        first_epoch = epochs[0].split('>')[1].split('<')[0]
        last_epoch = epochs[-1].split('>')[1].split('<')[0]


        first_time = datetime.strptime(first_epoch, "%Y-%jT%H:%M:%S.%fZ")
        last_time = datetime.strptime(last_epoch, "%Y-%jT%H:%M:%S.%fZ")

        print(f"Data range is from {first_time} to {last_time}")
    else:
        print("Error")






def current_epoch(response: str) -> None:
    '''

    This function is used to output the epoch which is closest in time to when the program is run. It will change everytime the program is run.

    Arguments:    

response: variable under which we stored the xml data which we pulled from NASA website. Used xmltodict to parse through the data.

    Returns:

    The output of this function is to print out the whole epoch which is closest to the time which the program is run.

    '''

    data = xmltodict.parse(response)

    state_vector = data['ndm']['oem']['body']['segment']['data']['stateVector']

    current_time = datetime.now(timezone.utc)
    close_epoch = min(state_vector, key=lambda x: abs((datetime.strptime(x['EPOCH'], "%Y-%jT%H:%M:%S.%fZ").replace(tzinfo=timezone.utc) - current_time).total_seconds()))

    for i, j in close_epoch.items():
        if i in ['X', 'Y', 'Z']:
            print(f"{i}: {j} km")
        elif i in ['X_DOT', 'Y_DOT', 'Z_DOT']:
            print(f"{i}: {j}")
        else:
            print(f"{i}: {j}")


def average_speed(response: str) -> None:
    data = xmltodict.parse(response)
    state_vector = data['ndm']['oem']['body']['segment']['data']['stateVector']


    overall_speed = []
    all_epochs = []
    all_speed = []


    for i in state_vector:
        speed = math.sqrt(float(i['X_DOT']['#text'])**2 + float(i['Y_DOT']['#text'])**2 + float(i['Z_DOT']['#text'])**2)
        all_speed.append(speed)

        all_epochs.append(datetime.strptime(i['EPOCH'], "%Y-%jT%H:%M:%S.%fZ"))

        overall_speed += all_speed


    average_speed = sum(overall_speed) / len(all_speed)
    print(f"Average speed for the dataset: {average_speed}")

    current_time = datetime.now(timezone.utc)
    close_epoch = min(range(len(all_epochs)), key=lambda x: abs((all_epochs[x].replace(tzinfo=timezone.utc) - current_time).total_seconds()))

    instant_speed = all_speed[close_epoch]

    print(f"Instataneous Speed: {instant_speed}")



def wait_for_redis():
    max_retries = 30
    for i in range(max_retries):
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

    for vector in state_vector:
        epoch = vector['EPOCH']
        config.rd.hset(f"iss:{epoch}", mapping={'EPOCH': vector['EPOCH'],'X': vector['X']['#text'], 'X_DOT': vector['X_DOT']['#text'],'Y': vector['Y']['#text'],'Y_DOT': vector['Y_DOT']['#text'], 'Z': vector['Z']['#text'],'Z_DOT': vector['Z_DOT']['#text']})

    return "Data stored in Redis"



#Returns entire dataset
@app.route('/epochs', methods=['GET'])
def all_epochs(): 
    try:
        keys = config.rd.keys("iss:*")
        keys.sort()

        epochs = [':'.join(key.split(':')[1:]) for key in keys]
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
            return jsonify({"error": "Epoch not found"}), 404
        return jsonify(data)
    except Exception as e:
        # Return the exception message in case of an error
        return jsonify({"error": str(e)}), 500


#Returns the instantaneous speed for a specific epoch
@app.route('/epochs/<epoch>/speed', methods=['GET'])
def speed_epoch(epoch):
    try:
        data = config.rd.hgetall(f"iss:{epoch}")
        
        if not data:
            return jsonify({"error": "Epoch not found"}), 404
        speed = math.sqrt(
            float(data['X_DOT'])**2 +float(data['Y_DOT'])**2 + float(data['Z_DOT'])**2)
        
        return jsonify({"speed": speed})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

#Returns the Longtitude, latitude, geopoisiton for specific Epoch
@app.route('/epochs/<epoch>/location', methods=['GET'])
def current_location(epoch):
    try:
        data = config.rd.hgetall(f"iss:{epoch}")
        if not data:
            return jsonify({"error": "Epoch not found"}), 404

        x = float(data['X'])
        y = float(data['Y'])
        z = float(data['Z'])

        lat = math.degrees(math.atan2(z, math.sqrt(x**2 + y**2)))
        long = math.degrees(math.atan2(y, x)) - (datetime.now().hour * 15 + datetime.now().minute / 4)
        altitude = math.sqrt(x**2 + y**2 + z**2) - 6371

        try:
            geographical_position = location.reverse(f"{lat}, {long}")
            address_geo = geographical_position.address if geographical_position else "Unknown"
        except:
            address_geo = "Geocoding failed"

        return jsonify({"latitude": lat,"longitude": long,"altitude": altitude,"geoposition": address_geo})

    except Exception as e:
        return jsonify({"error": str(e)}), 500



#Returns speed, latitude. longtitude, altitude, geoposistion for the epoch closest in time(refine)
@app.route('/now', methods=['GET'])
def current_closest_epoch():
    try:
        current_time = datetime.now(timezone.utc)
        keys = config.rd.keys("iss:*")

        epoch = [':'.join(key.split(':')[1:]) for key in keys]

        closest_epoch = min(epoch, key=lambda x: abs(datetime.strptime(x, "%Y-%jT%H:%M:%S.%fZ").replace(tzinfo=timezone.utc) - current_time))

        data_epoch_response = current_location(closest_epoch)
        data_speed_response = speed_epoch(closest_epoch)

        if isinstance(data_epoch_response, tuple):
            data_epoch = data_epoch_response[0]
        elif hasattr(data_epoch_response, "get_json"):
            data_epoch = data_epoch_response.get_json()
        else:
            data_epoch = data_epoch_response

        if isinstance(data_speed_response, tuple):
            data_speed = data_speed_response[0]
        elif hasattr(data_speed_response, "get_json"):
            data_speed = data_speed_response.get_json()
        else:
            data_speed = data_speed_response

        if not isinstance(data_epoch, dict) or not isinstance(data_speed, dict):
            raise ValueError("Data returned from current_location or speed_epoch is not a dictionary")

        data_combined = {**data_epoch, **data_speed}

        return jsonify(data_combined)

    except Exception as e:
        return jsonify({"Error": str(e)}), 500

if __name__ == '__main__':
    wait_for_redis()
    data_read()
    app.run(debug=True, host='0.0.0.0', port = 5000)
