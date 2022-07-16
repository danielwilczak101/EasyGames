from enum import Enum


class FinishedGame(Exception, Enum):
    """
    Exceptions to be raised for when the game is finished and the next
    move is requested.
    """
    WON = 1
    TIED = 0
    LOST = -1
