from __future__ import annotations
from collections import Counter, defaultdict
from functools import lru_cache
from pathlib import Path
import math
import sys

BASE = Path(__file__).resolve().parent
ANSWERS_FILE = BASE / "wordle_answers.txt"
ALLOWED_FILE = BASE / "wordle_allowed_guesses.txt"

# These are the best opening guesses. already been computed so no point in adding 40 seconds of overhead to startup recomputing every time
OPENING_GUESSES = [
    "roate",
    "raise",
    "raile",
    "soare",
    "arise",
    "irate",
    "orate",
    "ariel",
]

# Wordle feedback: 0 = gray, 1 = yellow, 2 = green.
def feedback(guess: str, answer: str) -> tuple[int, ...]:
    result = [0] * 5
    counts = [0] * 26

    # Find green letters first.
    for i in range(5):
        g = ord(guess[i]) - 97
        a = ord(answer[i]) - 97

        if g == a:
            result[i] = 2
        else:
            counts[a] += 1

    # Then check for yellow letters.
    for i in range(5):
        if result[i] == 0:
            g = ord(guess[i]) - 97

            if counts[g]:
                result[i] = 1
                counts[g] -= 1

    return tuple(result)


def pattern_string(pattern: tuple[int, ...]) -> str:
    return "".join("⬛🟨🟩"[x] for x in pattern)


def load_words(path: Path) -> list[str]:
    words = []

    for line in path.read_text(encoding="utf-8").splitlines():
        word = line.strip().lower()

        if len(word) == 5 and word.isalpha():
            words.append(word)

    return list(dict.fromkeys(words))


def load_data() -> tuple[list[str], list[str]]:
    answers = load_words(ANSWERS_FILE)
    allowed = load_words(ALLOWED_FILE)

    # Official answers are also legal guesses.
    guesses = list(dict.fromkeys(allowed + answers))

    return answers, guesses


@lru_cache(maxsize=None)
def cached_feedback(guess: str, answer: str) -> tuple[int, ...]:
    return feedback(guess, answer)


def partition(
    candidates: list[str],
    guess: str,
) -> dict[tuple[int, ...], list[str]]:
    groups = defaultdict(list)

    for answer in candidates:
        groups[cached_feedback(guess, answer)].append(answer)

    return groups


def entropy(
    groups: dict[tuple[int, ...], list[str]],
    total: int,
) -> float:
    value = 0.0

    for group in groups.values():
        p = len(group) / total
        value -= p * math.log2(p)

    return value


def expected_remaining(
    groups: dict[tuple[int, ...], list[str]],
    total: int,
) -> float:
    # Average number of candidates left after a guess.
    return sum(len(group) ** 2 for group in groups.values()) / total


def score_guess(
    guess: str,
    candidates: list[str],
) -> tuple[float, float, int, float]:
    groups = partition(candidates, guess)
    total = len(candidates)

    return (
        expected_remaining(groups, total),
        max(map(len, groups.values())),
        -len(groups),
        -entropy(groups, total),
    )


def best_guesses(
    candidates: list[str],
    guesses: list[str],
    limit: int = 10,
    restrict_to_candidates: bool = False,
) -> list[tuple[str, tuple[float, float, int, float]]]:
    pool = candidates if restrict_to_candidates else guesses

    scored = []

    for guess in pool:
        scored.append((guess, score_guess(guess, candidates)))

    scored.sort(key=lambda x: x[1])

    return scored[:limit]


def get_opening_guesses(
    guesses: list[str],
    limit: int = 8,
) -> list[str]:
    # Use the precomputed opening ranking.
    return [
        word
        for word in OPENING_GUESSES
        if word in guesses
    ][:limit]


def solve_from_feedback(
    candidates: list[str],
    guess: str,
    pattern: tuple[int, ...],
) -> list[str]:
    return [
        answer
        for answer in candidates
        if cached_feedback(guess, answer) == pattern
    ]


def run_cli() -> None:
    answers, guesses = load_data()

    print("WORDLE SOLVER / ANALYZER")
    print("=" * 72)
    print(f"Answers loaded:        {len(answers)}")
    print(f"Allowed guesses:       {len(guesses)}")

    # Start with the static opening ranking.
    opening_guesses = get_opening_guesses(guesses)

    print("\nTOP OPENING GUESSES")
    print("=" * 72)

    for i, guess in enumerate(opening_guesses, 1):
        print(f"{i:>2}. {guess.upper()}")

    print("\nEnter your opening guess.")
    opening = input("> ").strip().lower()

    while len(opening) != 5 or opening not in guesses:
        print("Please enter a valid five-letter Wordle guess.")
        opening = input("> ").strip().lower()

    candidates = answers[:]
    turn = 1

    while turn <= 6:
        print(f"\nGUESS {turn}: {opening.upper()}")

        pattern_text = input(
            "Enter feedback "
            "(G = green, Y = yellow, X = gray): "
        ).strip().upper()

        while (
            len(pattern_text) != 5
            or any(char not in "GYX" for char in pattern_text)
        ):
            print("Use exactly 5 characters: G, Y, or X.")
            pattern_text = input("> ").strip().upper()

        pattern_map = {
            "X": 0,
            "Y": 1,
            "G": 2,
        }

        pattern = tuple(pattern_map[char] for char in pattern_text)

        # Keep only answers that match the feedback.
        candidates = solve_from_feedback(
            candidates,
            opening,
            pattern,
        )

        if pattern == (2, 2, 2, 2, 2):
            print("\nSolved!")
            break

        print(f"\nPossible answers remaining: {len(candidates)}")

        if not candidates:
            print("No answers match that feedback.")
            break

        if len(candidates) <= 10:
            print("\nRemaining answers:")
            print(", ".join(word.upper() for word in candidates))

        # Once we have feedback, calculate the best guesses
        # from the smaller candidate pool.
        suggestions = best_guesses(
            candidates,
            guesses,
            limit=10,
        )

        print("\nBEST NEXT GUESSES")
        print("=" * 72)

        for i, (word, score) in enumerate(suggestions, 1):
            print(
                f"{i:>2}. {word.upper():<8} "
                f"Expected remaining: {score[0]:.2f}"
            )

        opening = input("\nYour next guess > ").strip().lower()

        while len(opening) != 5 or opening not in guesses:
            print("Please enter a valid five-letter Wordle guess.")
            opening = input("> ").strip().lower()

        turn += 1


def main() -> None:
    if "--gui" in sys.argv:
        from gui import launch_gui
        launch_gui()
        return

    run_cli()
if __name__ == "__main__":
    main()
