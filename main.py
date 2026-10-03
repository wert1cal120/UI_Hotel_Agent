from datetime import date
from agents.baseline import BaseLineAgent
from environment import HotelEnvironment
from models import Hotel

import config

def main():
    hotel = Hotel()
    environment = HotelEnvironment(hotel, date(2026, 9, 1), seed=config.SEED)
    baseline_agent = BaseLineAgent(hotel)

    environment.generate_rooms(config.NUMBER_OF_ROOMS)

    for _ in range(config.WORKING_DAYS):
        print(f"Day {environment.current_date.strftime('%m-%d')}")

        clients = environment.generate_clients()
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
        environment.step()

if __name__ == "__main__":
    main()
