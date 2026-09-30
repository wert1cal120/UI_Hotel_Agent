from agents.baseline import BaseLineAgent
from enviroment import *
from models import *

hotel = Hotel()
baseline_agent = BaseLineAgent(hotel)

working_days = 30
num_rooms = 5

hotel.set_rooms(generate_rooms(num_rooms))


for i in range(working_days):
    print(f"Day {i+1}")

    clients = generate_clients(randint(1, 5))
    print("\n".join(str(client) for client in clients))
    print()

    baseline_agent.act(hotel.rooms, clients)
    hotel.print_bookings()

    denied_clients = 0
    for client in clients:
        if client not in hotel.clients:
            print(f"{client.name}, ", end="")
            denied_clients += 1

    print(f"\nTotal denied clients: {denied_clients}/{len(clients)}\n")

    input("Press Enter to continue...")