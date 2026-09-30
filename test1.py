from models import *
from random import randint

hotel = Hotel()
for i in range(10):
    room = Room(i, randint(1, 5), "Available")
    hotel.add_room(room)

for i in range(50):
    date = randint(1, 15)
    client = Client(f"Client {i}", randint(1, 4), date, date+randint(1, 15))

    if hotel.book_room(client, hotel.rooms[randint(0, 9)]):
        hotel.add_client(client)

hotel.print_bookings()