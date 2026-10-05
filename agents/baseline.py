from agents.actions import BookRoomAction, RejectClientAction
from agents.agent_class import Agent


class BaselineAgent(Agent):
    def decide(self, percept):
        for room in percept:
            if room.available:
                return BookRoomAction(room.room_number)
        return RejectClientAction()