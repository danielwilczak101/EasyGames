import asyncio
import operator
import random
from abc import ABC, abstractmethod
from enum import Enum
from typing import AsyncGenerator, AsyncIterable, AsyncIterator
from typing import ClassVar, Dict, Generic, Hashable, Literal, Optional
from typing import Protocol, Tuple, TypeVar

from aio_stdout import ainput

T = TypeVar("T", bound=Hashable)


class FinishedGame(Exception, Enum):
    WON = 1
    TIE = 0
    LOSS = -1


class GameTree(Protocol[T]):

    async def move(self, state: T) -> T: ...

    async def moves_after(self, state: T) -> AsyncIterable[T]: ...

    async def play(self, state: Optional[T] = ...) -> AsyncGenerator[T, T]: ...

    async def train(self) -> None: ...

    @property
    def initial_state(self) -> T: ...


class MonteCarlo(GameTree[T], ABC):
    states: Dict[T, Dict[T, Tuple[int, int, int]]]

    def __init__(self) -> None:
        self.states = {}

    async def _train_from_states(
        self,
        states: "asyncio.Queue[T]",
        iterations: Optional[int] = None,
    ) -> Optional[BaseException]:
        ITERATIONS = 0
        try:
            state = await states.get()
            while True:
                if iterations == 0:
                    break
                elif iterations is not None:
                    iterations -= 1
                moves = [state]
                try:
                    while True:
                        _next_moves = self.moves_after(moves[-1])
                        try:
                            next_moves = [
                                move
                                async for move in _next_moves
                            ]
                        finally:
                            await _next_moves.aclose()
                        if moves[-1] not in self.states:
                            self.states[moves[-1]] = {
                                move: (0, 0, 0)
                                for move in next_moves
                            }
                        if (0, 0, 0) in self.states[moves[-1]].values():
                            moves.append(random.choice(next_moves))
                        else:
                            moves.append(random.choices(
                                next_moves,
                                weights=[
                                    (wins + ties / 2 + 1) / (wins + ties + losses + 1)
                                    for wins, ties, losses in self.states[moves[-1]].values()
                                ],
                            )[0])
                        await asyncio.sleep(0)
                except FinishedGame as e:
                    if len(moves) == 1:
                        break
                    result = e
                    for i in reversed(range(1, len(moves))):
                        wins, ties, losses = self.states[moves[i - 1]][moves[i]]
                        if result is FinishedGame.LOSS:
                            self.states[moves[i - 1]][moves[i]] = (wins + 1, ties, losses)
                            result = FinishedGame.WON
                        elif result is FinishedGame.TIE:
                            self.states[moves[i - 1]][moves[i]] = (wins, ties + 1, losses)
                        else:
                            self.states[moves[i - 1]][moves[i]] = (wins, ties, losses + 1)
                            result = FinishedGame.LOSS
                        await asyncio.sleep(0)
                if states.qsize() > 0:
                    state = await states.get()
                ITERATIONS += 1
                await asyncio.sleep(0)
        except BaseException as e:
            return e

    async def move(self, state: T) -> T:
        _next_moves = self.moves_after(state)
        try:
            next_moves = [
                move
                async for move in _next_moves
            ]
        finally:
            await _next_moves.aclose()
        states = asyncio.Queue()
        await states.put(state)
        trainer = asyncio.create_task(self._train_from_states(states))
        while state not in self.states:
            if trainer.done():
                if trainer.result() is not None:
                    raise trainer.result()
            await asyncio.sleep(0)
        while any(
            sum(stats) < 100
            for stats in self.states[state].values()
        ):
            if trainer.done():
                if trainer.result() is not None:
                    raise trainer.result()
            await asyncio.sleep(0)
        if not trainer.done():
            trainer.cancel()
            try:
                await trainer
            except asyncio.CancelledError:
                pass
        elif trainer.result() is not None:
            raise trainer.result()
        weights = [
            (wins + ties / 2 + 1) / (wins + ties + losses + 1)
            for wins, ties, losses in self.states[state].values()
        ]
        best = max(range(len(weights)), key=lambda i: weights[i])
        for i, move in enumerate(self.states[state]):
            if i == best:
                return move

    @abstractmethod
    async def moves_after(self, state: T) -> AsyncIterable[T]: ...

    async def play(self, state: Optional[T] = None) -> AsyncGenerator[T, T]:
        if state is None:
            state = self.initial_state
        states = asyncio.Queue()
        await states.put(state)
        trainer = asyncio.create_task(self._train_from_states(states))
        exited = False
        try:
            while True:
                if trainer.done():
                    break
                state = yield state
                if trainer.done():
                    break
                if state is None:
                    break
                response = yield state
                if response is not None:
                    raise TypeError("cannot .asend() during the opponent's turn")
                next_moves = self.moves_after(state)
                try:
                    async for next_move in next_moves:
                        break
                except FinishedGame:
                    break
                finally:
                    await next_moves.aclose()
                try:
                    state = await self.move(state)
                except FinishedGame:
                    break
                await states.put(state)
                await asyncio.sleep(0)
        except GeneratorExit as e:
            exited = True
            if not trainer.done():
                trainer.cancel()
                try:
                    await trainer
                except asyncio.CancelledError:
                    pass
            elif trainer.result() is None:
                raise
            else:
                raise trainer.result() from e
        finally:
            if not exited:
                if not trainer.done():
                    trainer.cancel()
                    try:
                        await trainer
                    except asyncio.CancelledError:
                        pass
                elif trainer.result() is not None:
                    raise trainer.result()

    async def train(self, iterations: Optional[int] = 1_000_000, seconds: Optional[float] = 10.0, state: Optional[T] = None) -> None:
        if iterations is not None:
            try:
                iterations = operator.index(iterations)
            except TypeError:
                raise TypeError(f"could not interpret the number of iterations as an integer, got {iterations!r}") from None
            if iterations <= 0:
                raise ValueError(f"requires iterations > 0, got {iterations!r}")
        if seconds is not None:
            try:
                seconds = float(seconds)
            except TypeError:
                raise TypeError(f"could not interpret the number of seconds as a real value, got {seconds!r}") from None
            if seconds < 0:
                raise ValueError(f"requires seconds >= 0, got {seconds!r}")
        states = asyncio.Queue()
        await states.put(self.initial_state if state is None else state)
        try:
            await asyncio.wait_for(self._train_from_states(states, iterations), seconds)
        except asyncio.TimeoutError:
            pass

    @property
    @abstractmethod
    def initial_state(self) -> T: ...


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

    async def moves_after(self, state: Board) -> AsyncIterator[Board]:
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
                    raise FinishedGame.LOSS
            elif state[s].count(2) == 3:
                if is_player_one:
                    raise FinishedGame.LOSS
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
    def initial_state(self) -> Board:
        return (0,) * 9


async def main() -> TicTacToe:
    ttt = TicTacToe()
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
            game.aclose()
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
