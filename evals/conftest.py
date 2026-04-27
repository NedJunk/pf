from collections import defaultdict
import pytest

_eval_results = []


@pytest.fixture
def eval_results():
    return _eval_results


def pytest_terminal_summary(terminalreporter, exitstatus, config):
    if not _eval_results:
        return

    experts = sorted({r["expected"] for r in _eval_results if r["expected"] is not None})
    tp = defaultdict(int)
    fp = defaultdict(int)
    fn = defaultdict(int)
    correct = 0

    for r in _eval_results:
        expected, actual = r["expected"], r["actual"]
        if expected == actual:
            correct += 1
            if expected is not None:
                tp[expected] += 1
        else:
            if actual is not None and actual in experts:
                fp[actual] += 1
            if expected is not None:
                fn[expected] += 1

    terminalreporter.write_sep("─", "Expert Selection Results")
    terminalreporter.write_line(
        f"{'Expert':<20} {'Precision':>10} {'Recall':>8} {'F1':>6}"
    )
    terminalreporter.write_line("─" * 48)
    for expert in experts:
        p = tp[expert] / (tp[expert] + fp[expert]) if (tp[expert] + fp[expert]) > 0 else 0.0
        r = tp[expert] / (tp[expert] + fn[expert]) if (tp[expert] + fn[expert]) > 0 else 0.0
        f1 = 2 * p * r / (p + r) if (p + r) > 0 else 0.0
        terminalreporter.write_line(f"{expert:<20} {p:>10.2f} {r:>8.2f} {f1:>6.2f}")
    terminalreporter.write_line("─" * 48)
    terminalreporter.write_line(
        f"Overall: {correct}/{len(_eval_results)} cases correct"
    )
