import asyncio
from typing import AsyncIterator, Literal, Tuple, TypeVar

from aio_stdout import ainput

from .finished_game import FinishedGame
from .monte_carlo import MonteCarlo

Self = TypeVar("Self", bound="TicTacToe")

Player = Literal[0, 1, 2]
Board = Tuple[
    Player, Player, Player,
    Player, Player, Player,
    Player, Player, Player,
]
BOARD_STRING = """
    A | B | C
   -----------
 1  {} | {} | {}
   -----------
 2  {} | {} | {}
   -----------
 3  {} | {} | {}
"""


class TicTacToe(MonteCarlo[Board]):

    async def moves_after(self: Self, state: Board) -> AsyncIterator[Board]:
        """
        Computes the moves available from the current state.

        Parameters
        -----------
            state:
                The current state.

        Returns
        --------
            moves:
                The next possible move from the current state.

        Raises
        -------
            FinishedGame.(WON/TIED/LOST):
                The player that would make the next move has won/tied/lost.

        Usage
        ------
            try:
                async for move in ai.moves_after(state):
                    ...
            except FinishedGame:
                ...
        """
        is_player_one = state.count(0) % 2 == 1
        for s in (
            # Horizontal 3 in a row.
            slice(0, 3),
            slice(3, 6),
            slice(6, 9),
            # Vertical 3 in a row.
            slice(0, None, 3),
            slice(1, None, 3),
            slice(2, None, 3),
            # Diagonal 3 in a row.
            slice(None, None, 4),
            slice(2, 8, 2),
        ):
            if state[s].count(1) == 3:
                if is_player_one:
                    raise FinishedGame.WON
                else:
                    raise FinishedGame.LOST
            elif state[s].count(2) == 3:
                if is_player_one:
                    raise FinishedGame.LOST
                else:
                    raise FinishedGame.WON
        # No moves left.
        if 0 not in state:
            raise FinishedGame.TIE
        new_state = list(state)
        player = 1 if is_player_one else 2
        for i, b in enumerate(new_state):
            if b == 0:
                new_state[i] = player
                yield tuple(new_state)
                new_state[i] = 0

    @property
    def initial_state(self: Self) -> Board:
        """The initial state of the game is an empty board."""
        return (0,) * 9


async def main() -> TicTacToe:
    """
    Run to play tic-tac-toe.

    Returns
    --------
        ttt:
            The tic-tac-toe AI.
    """
    ttt = TicTacToe()
    board = ttt.initial_state
    new_board = None
    while True:
        if new_board is not None:
            for i, (b1, b2) in enumerate(zip(board, new_board)):
                if b1 != b2:
                    print(f"AI move: {'ABC'[i % 3] + '123'[i // 3]}")
                    break
        print(BOARD_STRING.format(*board))
        try:
            await ttt.move(board)
        except FinishedGame as e:
            if e is FinishedGame.WON:
                print("Congratulations! You won!")
            elif e is FinishedGame.TIE:
                print("Well... nobody won.")
            else:
                print("Better luck next time, the AI won.")
            break
        while True:
            move = await ainput("move (e.g. A2): ")
            if len(move) != 2 or move[0] not in "ABC" or move[1] not in "123":
                print("illegal move, use (ABC)(123) e.g. A2")
                continue
            index = "ABC".index(move[0]) + "123".index(move[1]) * 3
            if board[index] != 0:
                print(f"illegal move, {move} is already taken")
                continue
            break
        new_board = board = (*board[:index], 1, *board[index + 1:])
        print(BOARD_STRING.format(*board))
        try:
            board = await ttt.move(board)
        except FinishedGame as e:
            if e is FinishedGame.WON:
                print("Better luck next time, the AI won.")
            elif e is FinishedGame.TIE:
                print("Well... nobody won.")
            else:
                print("Congratulations! You won!")
    return ttt
    while True:
        game = ttt.play()
        try:
            new_board = None
            async for board in game:
                if new_board is not None:
                    for i, (b1, b2) in enumerate(zip(board, new_board)):
                        if b1 != b2:
                            print(f"AI move: {'ABC'[i % 3] + '123'[i // 3]}")
                            break
                print(BOARD_STRING.format(*board))
                try:
                    await ttt.move(board)
                except FinishedGame as e:
                    if e is FinishedGame.WON:
                        print("Congratulations! You won!")
                    elif e is FinishedGame.TIE:
                        print("Well... nobody won.")
                    else:
                        print("Better luck next time, the AI won.")
                    break
                while True:
                    move = await ainput("move (e.g. A2): ")
                    if len(move) != 2 or move[0] not in "ABC" or move[1] not in "123":
                        print("illegal move, use (ABC)(123) e.g. A2")
                        continue
                    index = "ABC".index(move[0]) + "123".index(move[1]) * 3
                    if board[index] != 0:
                        print(f"illegal move, {move} is already taken")
                        continue
                    break
                new_board = board = (*board[:index], 1, *board[index + 1:])
                await game.asend(board)
                print(BOARD_STRING.format(*board))
            else:
                try:
                    await ttt.move(board)
                except FinishedGame as e:
                    if e is FinishedGame.WON:
                        print("Better luck next time, the AI won.")
                    elif e is FinishedGame.TIE:
                        print("Well... nobody won.")
                    else:
                        print("Congratulations! You won!")
                else:
                    assert False, "Game should only end if someone won."
        finally:
            await game.aclose()
        while True:
            play_again = (await ainput("Play again? (Y/N) ")).upper()
            if play_again == "Y" or play_again == "N":
                break
            else:
                print("Invalid input, use Y or N")
        if play_again == "N":
            break
    return ttt

if __name__ == "__main__":
    asyncio.run(main())
