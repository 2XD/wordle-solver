from __future__ import annotations

from collections import Counter, defaultdict
from functools import lru_cache
from pathlib import Path
import math

BASE = Path(__file__).resolve().parent
ANSWERS_FILE = BASE / "wordle_answers.txt"
ALLOWED_FILE = BASE / "wordle_allowed_guesses.txt"

# Wordle feedback: 0 = gray, 1 = yellow, 2 = green.
def feedback(guess: str, answer: str) -> tuple[int, ...]:
    # Exact Wordle duplicate-letter handling, with no allocations beyond a small
    # integer count array. 0=gray, 1=yellow, 2=green.
    result = [0] * 5
    counts = [0] * 26
    for i in range(5):
        g = ord(guess[i]) - 97
        a = ord(answer[i]) - 97
        if g == a:
            result[i] = 2
        else:
            counts[a] += 1
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
        w = line.strip().lower()
        if len(w) == 5 and w.isalpha():
            words.append(w)
    return list(dict.fromkeys(words))


def load_data() -> tuple[list[str], list[str]]:
    answers = load_words(ANSWERS_FILE)
    allowed = load_words(ALLOWED_FILE)

    # Official answers are also legal guesses. Keep them in the guess pool.
    guesses = list(dict.fromkeys(allowed + answers))
    return answers, guesses


@lru_cache(maxsize=None)
def cached_feedback(guess: str, answer: str) -> tuple[int, ...]:
    return feedback(guess, answer)


def partition(candidates: list[str], guess: str) -> dict[tuple[int, ...], list[str]]:
    groups = defaultdict(list)
    for answer in candidates:
        groups[cached_feedback(guess, answer)].append(answer)
    return groups


def entropy(groups: dict[tuple[int, ...], list[str]], total: int) -> float:
    value = 0.0
    for group in groups.values():
        p = len(group) / total
        value -= p * math.log2(p)
    return value


def expected_remaining(groups: dict[tuple[int, ...], list[str]], total: int) -> float:
    # E[size of remaining candidate set after the guess].
    return sum(len(group) ** 2 for group in groups.values()) / total


def score_guess(guess: str, candidates: list[str]) -> tuple[float, float, int, float]:
    groups = partition(candidates, guess)
    total = len(candidates)
    return (
        expected_remaining(groups, total),
        max(map(len, groups.values())),
        -len(groups),
        -entropy(groups, total),
    )


def best_guesses(candidates: list[str], guesses: list[str], limit: int = 10,
                 restrict_to_candidates: bool = False) -> list[tuple[str, tuple[float, float, int, float]]]:
    pool = candidates if restrict_to_candidates else guesses
    scored = []
    for guess in pool:
        scored.append((guess, score_guess(guess, candidates)))
    scored.sort(key=lambda x: x[1])
    return scored[:limit]


def analyze_opening(answers: list[str], guesses: list[str], opening: list[str]) -> None:
    candidates = answers[:]
    guesses_used = 0

    print("\nOPENING ANALYSIS")
    print("=" * 72)
    print(" -> ".join(w.upper() for w in opening))

    for guess in opening:
        groups = partition(candidates, guess)
        print(f"\n{guess.upper()}: {len(groups)} possible feedback patterns")
        print(f"Expected remaining: {expected_remaining(groups, len(candidates)):.3f}")
        print(f"Worst-case remaining: {max(map(len, groups.values()))}")

        # Aggregate over all possible answers. This is what a blind simulation uses.
        solved = len(candidates) if all(all(x == 2 for x in p) for p in groups if p == (2, 2, 2, 2, 2)) else 0
        guesses_used += 1

        # For the fixed opening, don't choose a real feedback pattern here;
        # this section just reports the distribution from the current candidate set.
        sizes = Counter(len(g) for g in groups.values())
        print("Remaining-candidate distribution (group size -> number of patterns):")
        print("  " + ", ".join(f"{size}->{count}" for size, count in sorted(sizes.items())))

        if guess != opening[-1]:
            # The next opening guess is fixed, so show the average result over all answers.
            candidates = [a for a in candidates]  # unchanged until actual feedback is known


def simulate_fixed_opening(answers: list[str], guesses: list[str], opening: list[str]) -> dict:
    """Simulate the fixed opening, then use a greedy information guess until solved.

    The third-and-later guess is selected independently for each feedback branch,
    minimizing expected remaining candidates. This is deliberately transparent and
    reproducible rather than a massive exhaustive optimal-tree search.
    """
    guess_pool = guesses
    totals = Counter()
    examples = {}
    branch_cache = {}

    for answer in answers:
        candidates = answers
        solved = False
        n = 0

        for guess in opening:
            n += 1
            pattern = cached_feedback(guess, answer)
            if pattern == (2, 2, 2, 2, 2):
                solved = True
                break
            candidates = [a for a in candidates if cached_feedback(guess, a) == pattern]

        while not solved and n < 6:
            n += 1
            key = tuple(candidates)
            if key not in branch_cache:
                # Prefer legal guesses that are also candidates only when the candidate
                # set is tiny; otherwise the full legal pool can provide more information.
                best = best_guesses(candidates, guess_pool, limit=1, restrict_to_candidates=True)[0][0]
                branch_cache[key] = best
            guess = branch_cache[key]
            pattern = cached_feedback(guess, answer)
            if pattern == (2, 2, 2, 2, 2):
                solved = True
                break
            candidates = [a for a in candidates if cached_feedback(guess, a) == pattern]

        if not solved:
            n = 7  # Wordle failure / did not solve within six guesses.
        totals[n] += 1
        examples.setdefault(n, (answer, candidates[:10]))

    total = len(answers)
    average = sum(k * v for k, v in totals.items()) / total
    return {"totals": totals, "average": average, "examples": examples}



def benchmark_second_guesses(answers: list[str], guesses: list[str]) -> None:
    """Rank legal second guesses after SALET by expected remaining answers.

    This is a fast first-stage benchmark. It measures the quality of the
    second guess itself; full recursive simulation can be added afterward.
    """
    first = "salet"
    n = len(answers)

    first_groups = defaultdict(list)
    for answer in answers:
        first_groups[cached_feedback(first, answer)].append(answer)

    rows = []
    for guess in guesses:
        if guess == first:
            continue

        # For each possible SALET result, partition that branch with the
        # candidate second guess.
        total_squared = 0
        worst = 0

        for candidates in first_groups.values():
            if not candidates:
                continue
            groups = partition(candidates, guess)
            total_squared += sum(len(g) ** 2 for g in groups.values())
            worst = max(worst, max(map(len, groups.values())))

        expected = total_squared / n
        rows.append((expected, worst, guess))

    rows.sort()

    print("WORDLE SOLVER / ANALYZER")
    print("=" * 72)
    print(f"Answers loaded:        {n}")
    print(f"Allowed guesses:       {len(guesses)}")

    print("\nBEST SECOND GUESSES AFTER SALET")
    print("=" * 72)
    print(f"{'Rank':>4}  {'Guess':<8} {'Expected':>10} {'Worst':>8}")
    print("-" * 44)

    for i, (expected, worst, guess) in enumerate(rows[:30], 1):
        print(f"{i:>4}  {guess.upper():<8} {expected:>10.3f} {worst:>8}")



def run_cli() -> None:
    answers, guesses = load_data()

    print("WORDLE SOLVER / ANALYZER")
    print("=" * 72)
    print(f"Answers loaded:        {len(answers)}")
    print(f"Allowed guesses:       {len(guesses)} total legal guesses")
    print(f"SALET legal:           {'salet' in set(guesses)}")

    opening = ["salet"]
    print("\nOPENING")
    print("-" * 72)
    groups = partition(answers, "salet")
    print("SALET")
    print(f"Feedback patterns:     {len(groups)}")
    print(f"Expected remaining:    {expected_remaining(groups, len(answers)):.3f}")
    print(f"Worst-case remaining:  {max(map(len, groups.values()))}")

    print("\nFULL SIMULATION")
    print("=" * 72)
    print("Running all answers with SALET, then greedy information guesses...")
    result = simulate_fixed_opening(answers, guesses, opening)
    for n in range(2, 8):
        count = result["totals"].get(n, 0)
        print(f"Solved in {n}:            {count:>4} ({count/len(answers):.2%})")
    print(f"Average guesses:        {result['average']:.4f}")

def main() -> None:
    import sys

    if "--gui" in sys.argv:
        from gui import launch_gui
        launch_gui()
        return

    if "--benchmark-second" in sys.argv:
        answers, guesses = load_data()
        benchmark_second_guesses(answers, guesses)
        return

    run_cli()


if __name__ == "__main__":
    main()
