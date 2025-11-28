import grpc
from concurrent import futures
import time
import sys
import os
import random

# Add generated proto path
sys.path.append(os.path.join(os.path.dirname(__file__), '.'))
sys.path.append(os.path.join(os.path.dirname(__file__), '../protos'))

import spacex.api.device.device_pb2 as device_pb2
import spacex.api.device.device_pb2_grpc as device_pb2_grpc
import spacex.api.common.status.status_pb2 as status_pb2

class DeviceServicer(device_pb2_grpc.DeviceServicer):
    def Handle(self, request, context):
        response = device_pb2.Response()
        
        if request.HasField('get_status'):
            print("Received GetStatus request")
            response.get_status.CopyFrom(device_pb2.GetStatusRequest())
            # In a real response, status is often in the 'status' field of Response or specific sub-messages
            # For this mock, we'll populate device_info as a sign of connection
            
            # Also populate the top-level status
            response.status.uptime_s = int(time.time())
            
            # And device info
            dev_info = device_pb2.DeviceInfo()
            dev_info.id = "ut-12345678"
            dev_info.hardware_version = "rev3_proto2"
            response.get_device_info.device_info.CopyFrom(dev_info)
            
        elif request.HasField('get_location'):
            print("Received GetLocation request")
            # Mock location (SpaceX HQ)
            response.get_location.lla.lat = 33.9207
            response.get_location.lla.lon = -118.3278
            response.get_location.lla.alt = 15.0
            
        elif request.HasField('get_history'):
            print("Received GetHistory request (simulating speed)")
            # We use this to trigger speed updates in our client
            # In reality, client parses history. Here we just return success
            # and let the client mock the speed values for now, 
            # OR we could try to populate history data if we knew the format well.
            # For the MVP client, we just check for success.
            pass
            
        return response

def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    device_pb2_grpc.add_DeviceServicer_to_server(DeviceServicer(), server)
    server.add_insecure_port('[::]:9200')
    print("Mock Starlink Dish running on port 9200...")
    server.start()
    try:
        while True:
            time.sleep(86400)
    except KeyboardInterrupt:
        server.stop(0)

if __name__ == '__main__':
    serve()
