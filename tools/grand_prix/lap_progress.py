"""Bounded free-lap event accounting. No AST, clock source or sensor decisions.

Only the geometric evaluator may supply validated directed crossing events.
This module cannot certify a trajectory, landing, sensor recognition or score.
"""
from __future__ import annotations
from dataclasses import dataclass, field
import math

MAX_LAPS = 20

@dataclass
class Progress:
    ring: tuple[str, ...]
    final: tuple[str, ...]
    max_laps: int = MAX_LAPS
    phase: str = field(default='ring', init=False)
    cursor: int = field(default=0, init=False)
    laps: int = field(default=0, init=False)
    crossings: int = field(default=0, init=False)
    pending_crossings: int = field(default=0, init=False)

    def __post_init__(self):
        if (not self.ring or self.ring[-1] != 'junction' or
                len(set(self.ring)) != len(self.ring) or
                len(set(self.final)) != len(self.final) or
                any(not isinstance(token, str) or not token for token in (*self.ring, *self.final)) or
                any(not (token.startswith('h:') and len(token) > 2 or
                         token.startswith('corner:') and len(token) > 7)
                    for token in self.ring[:-1]) or
                any(not (token.startswith('final:') and len(token) > 6)
                    for token in self.final) or
                set(self.ring) & set(self.final) or
                type(self.max_laps) is not int or not 1 <= self.max_laps <= MAX_LAPS):
            raise ValueError('invalid route event contract')

    @property
    def expected(self):
        events = self.ring if self.phase == 'ring' else self.final
        return events[self.cursor] if self.phase in ('ring', 'final') and self.cursor < len(events) else None

    @property
    def exit_eligible(self):
        return self.phase == 'ring' and self.cursor == 0 and self.laps > 0

    @property
    def final_complete(self):
        return self.phase == 'final' and self.cursor == len(self.final)

    def fail(self):
        self.phase = 'invalid'
        return False

    def advance(self, token):
        if token != self.expected or self.expected is None:
            return self.fail()
        if self.phase == 'ring' and self.laps >= self.max_laps:
            return self.fail()
        self.cursor += 1
        if self.phase == 'final':
            self.crossings += 1
        elif token != 'junction' and not token.startswith('corner:'):
            self.pending_crossings += 1
        if self.phase == 'ring' and self.cursor == len(self.ring):
            self.laps += 1
            self.crossings += self.pending_crossings
            self.pending_crossings = 0
            self.cursor = 0
        return True

    def choose_exit(self):
        if not self.exit_eligible:
            return self.fail()
        self.phase = 'final'
        self.cursor = 0
        return True


def candidate_score(crossings: int, seconds: float, penalty_threshold: float) -> int:
    """Issue #587's *candidate* started-second convention; not owner acceptance.

    Call only for a separately certified completed attempt, never partial/failed
    attempts. Keeping this pure calculation cannot confer mission authority.
    The public scenario threshold T is a mandatory input; 120 s is not a
    product requirement. No epsilon silently forgives fractions of a second.
    """
    if (type(crossings) is not int or crossings < 0 or
            isinstance(seconds, bool) or not isinstance(seconds, (int, float)) or
            not math.isfinite(seconds) or seconds < 0 or
            isinstance(penalty_threshold, bool) or
            not isinstance(penalty_threshold, (int, float)) or
            not math.isfinite(penalty_threshold) or penalty_threshold < 0):
        raise ValueError('invalid score operands')
    return 5 * crossings - math.ceil(max(0, seconds - penalty_threshold))
