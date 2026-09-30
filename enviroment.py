from models import Room, Client
from clients_data import get_names
from random import randint, choice
import datetime

def generate_rooms(num_rooms):
    rooms = []
    for i in range(num_rooms):
        room = Room(i, randint(1, 4), ["Available", "Broken"][randint(0, 1)])
        rooms.append(room)
    return rooms

def generate_clinet():
    arrival_date = datetime.date(2026, 9, 1) + datetime.timedelta(days=randint(1, 30))
    departure_date = arrival_date + datetime.timedelta(days=randint(1, 10))
    client = Client(f"{choice(get_names())}", randint(1, 4), arrival_date, departure_date)
    return client

def generate_clients(num_clients):
    clients = []
    for i in range(num_clients):
        clients.append(generate_clinet())
    return clients