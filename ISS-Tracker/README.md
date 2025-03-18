##Midterm Report


Title: SUMMARY STATITICS FOR ISS DATA



Description for folder: 

This folder's goal is to provide different summary statistics for ISS data written on a containerized Python script which is stored on as a public 
dataset on NASA's website. It is ISS data for a 15 day period. Its important that we are able to decipher this data as it can be used for tracking
the movement of the ISS and seeing exactly what speed its travelling at and which direction it is headed in. 



How to Access data: 

I used the requests library to load the data into my file. The code to do this is as follows:

LINK TO ISS-data -> https://nasa-public-data.s3.amazonaws.com/iss-coords/current/ISS_OEM/ISS.OEM_J2K_EPH.xml

import requests

response = requests.get(url='https://nasa-public-data.s3.amazonaws.com/iss-coords/current/ISS_OEM/ISS.OEM_J2K_EPH.xml')

I also used the wget https://nasa-public-data.s3.amazonaws.com/iss-coords/current/ISS_OEM/ISS.OEM_J2K_EPH.xml feature outside the script in the 
termial to play around with the data and see some of the features I am working with. 

Inside of the "stateVector" column in the xml file it contained the "X,Y,Z, X_DOT, Y_DOT, Z_DOT, EPOCH" features which is the data we want to work 
with. 


How to build container for code: 

I used nano to create a Dockerfile to containerize the Python3 code which I had made, I had done it with the following code snippet, in which I 
loaded python 3.12, then installed the required libraries (pytest, math, xmltodict, flask, requests) and then used the COPY and RUN functions to load the scripts 
into the file. 

CODE to containerize Flask(Dockerfile): 

FROM python:3.12

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "iss_tracker.py"]


How to deploy the app with docker compose: 


version: "3.8"

services:
  redis-db:
    image: redis:7.0
    container_name: midterm-redis
    ports:
      - "6379:6379"
    volumes:
      - ./data:/data
    command: ["redis-server", "--bind", "0.0.0.0"]

  flask-app:
    build:
      context: ./
      dockerfile: ./Dockerfile
    container_name: midterm-flask
    depends_on:
      - redis-db
    environment:
      REDIS_HOST: redis-db
      REDIS_PORT: 6379
    ports:
      - "5001:5000"


#Used the 5001 port as there was an issue with the 5000 port


How to run the containerized scripts and running the app routes: 

To run flask app in back with 5000 port: 

docker-compose up --build -d (to build the dockerfile)

What route codes would be to run the the curls(With output meaning): 
/epochs → curl http://localhost:5000/epochs - Returns entire dataset 
/epochs?Limit=intsoffset=int →> curl "http://localhost:5000/epochs?limit=10&offset=5" - Returns modified epochs 
/epochs/<epoch> - curl http://localhost:5000/epochs/2025-084T12:00:00.000z→> Returns State vectors for Epoch in dataset
/epochs/<epoch>/speed → curl http://localhost:5000/epochs/2025-084T12:00:00.000Z/speed - Returns an instantaenous speed of a specific epoch 
/epochs/‹epoch>/location → curl http://lpcalhost:5000/epochs/2025-084T12:00:00.000Z/location - Returns the latitude, longtitude, altitude and geoposition of specific epoch 
/now → curl http://localhost:5001/now --> Returns speed, latitude, longtitude, altitude., geoposition for epoch closest in time when it is ran



Instructions to run containerized unit tests: 

docker build -t iss_tracker_tests
docker run iss_tracker_tests




Expected output: 

The expected output for the iss_tracker.py file should be of the 3 main functions which are present in the code: 

For the first function "date_range" the output would be a single line which contains the range of the dates which are present in the dataset. 

For the second function "closest_epoch" the ouptut contains 7 lines in which outputs the closest epach and the "X,Y,Z, X_DOT, Y_DOT, Z_DOT" 
associated with it.

For the third function "average_speed" the output is 2 lines, one which contains the average speed of the entire dataset, and the second line which 
has the instatenous speed. 


For the test_iss_tracker.py file the expected output includes the program passing a series of 6 test passes which should all be passed. 
