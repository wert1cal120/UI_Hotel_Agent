from models import Room, Client, RoomStatus, RoomType
from config import CLIENT_NAMES

import random
import datetime

class HotelEnvironment:
    def __init__(self, hotel, start_date, seed):
        self.hotel = hotel
        self.current_date = start_date
        self.random = random.Random(seed)

    def step(self):
        self.current_date += datetime.timedelta(days=1)

    def generate_rooms(self, num_rooms):
        rooms = []
        for room_num in range(num_rooms):
            room = Room(room_num,
                        self.random.choices(list(RoomType), weights=[30, 40, 20, 10], k=1)[0],
                        self.random.choices(list(RoomStatus), weights=[90, 10], k=1)[0])
            rooms.append(room)

        self.hotel.set_rooms(rooms)

    def generate_client(self):
        arrival_date = self.current_date + datetime.timedelta(days=self.random.randint(1, 30))
        departure_date = arrival_date + datetime.timedelta(days=self.random.randint(1, 10))
        client = Client(f"{self.random.choice(CLIENT_NAMES)}",
                        self.random.choices(list(RoomType), weights=[30, 40, 20, 10], k=1)[0],
                        arrival_date, departure_date)
        return client

    def generate_clients(self):
        clients = []
        num_clients = self.random.randint(1, 5)

        for _ in range(num_clients):
            clients.append(self.generate_client())
        return clients
