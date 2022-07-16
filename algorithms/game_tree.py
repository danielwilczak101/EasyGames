from typing import AsyncGenerator, AsyncIterable, Hashable, Optional, Protocol, TypeVar

T = TypeVar("T", bound=Hashable)
Self = TypeVar("Self", bound="GameTree")


class GameTree(Protocol[T]):

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
        ...

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

    async def play(self: Self, state: Optional[T] = ...) -> AsyncGenerator[T, T]:
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
        ...

    async def train(
        self: Self,
        iterations: Optional[int] = ...,
        seconds: Optional[float] = ...,
        state: Optional[T] = ...,
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
        ...

    @property
    def initial_state(self: Self) -> T:
        """The initial state of the game."""
        ...
