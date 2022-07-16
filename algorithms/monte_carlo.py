import asyncio
import random
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import AsyncGenerator, AsyncIterable, Dict, Hashable, Optional, Tuple, TypeVar

from .finished_game import FinishedGame
from .game_tree import GameTree

T = TypeVar("T", bound=Hashable)
Self = TypeVar("Self", bound="MonteCarlo")


class MonteCarlo(GameTree[T], ABC):
    states: Dict[T, Dict[T, Tuple[int, int, int]]]
    timeout: timedelta
    train_until: Optional[datetime]

    def __init__(self: Self) -> None:
        self.states = {}
        self.timeout = timedelta(seconds=10)
        self.train_until = datetime.now()

    async def _train_from_states(
        self: Self,
        states: "asyncio.Queue[T]",
        iterations: Optional[int] = None,
    ) -> Optional[BaseException]:
        """
        Trains in the background from a dynamically updating set of states.

        Parameters
        -----------
            states:
                A queue of incoming states.
            iterations:
                The maximum amount of iterations trained.

        Returns
        --------
            exception:
                None or an exception. Should be re-raised elsewhere.

        Usage
        ------
            # Initial state to train on.
            states = asyncio.Queue()
            await states.put(initial_state)
            trainer = asyncio.create_task(ai._train_from_states(states))

            while ...:

                # As the game progresses, keep the trainer updated.
                await states.put(new_state)

                # As the game progresses, check if the trainer stopped.
                if trainer.done():
                    break

            # When the game finishes, stop the trainer and raise any exceptions.
            exception = await trainer
            if exception is not None:
                raise exception
        """
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
                            if isinstance(_next_moves, AsyncGenerator):
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
                                    min((2 * wins + ties + 1) / (wins + ties + losses + 1), 0.01)
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
                        if result is FinishedGame.LOST:
                            self.states[moves[i - 1]][moves[i]
                                                      ] = (wins + 1, ties, losses)
                            result = FinishedGame.WON
                        elif result is FinishedGame.TIED:
                            self.states[moves[i - 1]][moves[i]
                                                      ] = (wins, ties + 1, losses)
                        else:
                            self.states[moves[i - 1]][moves[i]
                                                      ] = (wins, ties, losses + 1)
                            result = FinishedGame.LOST
                        await asyncio.sleep(0)
                if None is not self.train_until < datetime.now():
                    break
                elif states.qsize() > 0:
                    state = await states.get()
                await asyncio.sleep(0)
        except BaseException as e:
            return e

    async def move(self: Self, state: T) -> T:
        """
        Computes the next move.

        Parameters
        -----------
            state:
                The current state.

        Returns
        --------
            state:
                The AI's next move from the current state.

        Raises
        -------
            FinishedGame.(WON/TIED/LOST):
                The AI won/tied/lost.

        Usage
        ------
            try:
                state = ai.move(state)
            except FinishedGame:
                ...
        """
        _next_moves = self.moves_after(state)
        try:
            next_moves = [
                move
                async for move in _next_moves
            ]
        finally:
            if isinstance(_next_moves, AsyncGenerator):
                await _next_moves.aclose()
        states = asyncio.Queue()
        await states.put(state)
        if self.train_until is not None:
            self.train_until = datetime.now() + self.timeout
        trainer = asyncio.create_task(self._train_from_states(states))
        while state not in self.states:
            if trainer.done():
                exception = await trainer
                if exception is not None:
                    raise exception
            await asyncio.sleep(0)
        while any(
            sum(stats) < 100
            for stats in self.states[state].values()
        ):
            if trainer.done():
                exception = await trainer
                if exception is not None:
                    raise exception
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
            (2 * wins + ties + 1) / (wins + ties + losses + 1)
            for wins, ties, losses in self.states[state].values()
        ]
        best = max(range(len(weights)), key=lambda i: weights[i])
        for i, move in enumerate(self.states[state]):
            if i == best:
                return move

    @abstractmethod
    async def moves_after(self: Self, state: T) -> AsyncIterable[T]:
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
        ...

    async def play(self: Self, state: Optional[T] = None) -> AsyncGenerator[T, T]:
        """
        Creates a generator for playing games with the AI.

        Parameters
        -----------
            state:
                An initial state to play from.

        Yields
        -------
            state:
                The next move by the AI, or an initial state.

        Receives
        ---------
            state:
                The next move by whatever is playing with the AI.

        Usage
        ------
            game = ai.play()
            try:
                async for move in game:
                    # Check if valid moves remain.
                    try:
                        await ai.move(move)
                    except FinishedGame as e:
                        # Check if the player won/tied/lost.
                        ...
                        # Stop the game.
                        break
                    # Make a move.
                    move = ...
                # Game ended on the last move made by the player.
                else:
                    try:
                        await game.asend(move)
                    except FinishedGame as e:
                        # Check if the ai won/tied/lost.
                        ...
            finally:
                # Stop training the ai when the game finishes.
                await game.aclose()
        """
        if state is None:
            state = self.initial_state
        states = asyncio.Queue()
        await states.put(state)
        self.train_until = datetime.now() + timedelta(seconds=10)
        trainer = asyncio.create_task(self._train_from_states(states))
        exited = False
        try:
            while True:
                if trainer.done():
                    break
                state = yield state
                if self.train_until is not None:
                    self.train_until = datetime.now() + self.timeout
                if trainer.done():
                    exception = await trainer
                    if exception is not None:
                        raise exception
                    elif state is not None:
                        await states.put(state)
                        trainer = asyncio.create_task(
                            self._train_from_states(states))
                if state is None:
                    break
                response = yield state
                if self.train_until is not None:
                    self.train_until = datetime.now() + self.timeout
                if trainer.done():
                    exception = await trainer
                    if exception is not None:
                        raise exception
                    else:
                        await states.put(state)
                        trainer = asyncio.create_task(
                            self._train_from_states(states))
                if response is not None:
                    raise TypeError(
                        "cannot .asend() during the opponent's turn")
                next_moves = self.moves_after(state)
                try:
                    async for next_move in next_moves:
                        break
                except FinishedGame:
                    break
                finally:
                    if isinstance(next_moves, AsyncGenerator):
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

    async def train(
        self: Self,
        iterations: Optional[int] = 1_000_000,
        seconds: Optional[float] = 10.0,
        state: Optional[T] = None,
    ) -> None:
        """
        Train the ai.

        Parameters
        -----------
            iterations:
                The number of iterations trained.
            seconds:
                The number of seconds trained.
            state:
                The initial state to train from.
        """
        if iterations is not None:
            try:
                iterations = operator.index(iterations)
            except TypeError:
                raise TypeError(
                    f"could not interpret the number of iterations as an integer, got {iterations!r}") from None
            if iterations <= 0:
                raise ValueError(
                    f"requires iterations > 0, got {iterations!r}")
        if seconds is not None:
            try:
                seconds = float(seconds)
            except TypeError:
                raise TypeError(
                    f"could not interpret the number of seconds as a real value, got {seconds!r}") from None
            if seconds < 0:
                raise ValueError(f"requires seconds >= 0, got {seconds!r}")
        states = asyncio.Queue()
        self.train_until = None
        try:
            await states.put(self.initial_state if state is None else state)
            try:
                await asyncio.wait_for(self._train_from_states(states, iterations), seconds)
            except asyncio.TimeoutError:
                pass
        finally:
            self.train_until = datetime.now()

    @property
    @abstractmethod
    def initial_state(self: Self) -> T:
        """The initial state of the game."""
        ...
