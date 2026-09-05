"""Wordle-style guess evaluation."""


def evaluate_guess(guess, answer):
    """Return per-letter feedback: 'correct', 'present', or 'absent'."""
    g = list(guess.lower())
    a = list(answer.lower())
    result = ["absent"] * 5
    used = [False] * 5

    for i in range(5):
        if g[i] == a[i]:
            result[i] = "correct"
            used[i] = True

    for i in range(5):
        if result[i] == "correct":
            continue
        for j in range(5):
            if not used[j] and g[i] == a[j]:
                result[i] = "present"
                used[j] = True
                break

    return result
