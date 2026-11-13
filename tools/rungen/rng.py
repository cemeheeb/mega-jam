"""Детерминированный ГСЧ генератора забега.

Вся арифметика 32-битная беззнаковая, поэтому переносится в C++ один в один
(uint32, переполнение по модулю 2^32). Никакого random из стандартной библиотеки.

Правила, которые должен повторить порт:
- mix32: lowbias32 (Chris Wellons), см. код.
- hash32(v1, v2, ...): h = 0x811C9DC5; для каждого v: h = mix32(((h ^ v) + 0x9E3779B9) mod 2^32).
- Rng(key...): base = hash32(key...); n-й вызов next_u32() возвращает hash32(base, n), n с 1.
- below(n) = next_u32() % n.
- chance(p): порог T = floor(p * 65536 + 0.5) в double; успех, если (next_u32() >> 16) < T.
- shuffle: Фишер–Йетс от последнего элемента к первому, j = below(i + 1).
- weighted(weights): r = below(sum); первый индекс, где накопленная сумма > r.
"""

MASK32 = 0xFFFFFFFF


def mix32(x: int) -> int:
    x &= MASK32
    x ^= x >> 16
    x = (x * 0x7FEB352D) & MASK32
    x ^= x >> 15
    x = (x * 0x846CA68B) & MASK32
    x ^= x >> 16
    return x


def hash32(*values: int) -> int:
    h = 0x811C9DC5
    for v in values:
        h = mix32(((h ^ (v & MASK32)) + 0x9E3779B9) & MASK32)
    return h


def prob16(p: float) -> int:
    t = int(p * 65536.0 + 0.5)
    return 0 if t < 0 else (65536 if t > 65536 else t)


class Rng:
    __slots__ = ("base", "counter")

    def __init__(self, *key: int):
        self.base = hash32(*key)
        self.counter = 0

    def next_u32(self) -> int:
        self.counter += 1
        return hash32(self.base, self.counter)

    def below(self, n: int) -> int:
        if n <= 0:
            raise ValueError("below(n) needs n > 0")
        return self.next_u32() % n

    def chance(self, p: float) -> bool:
        return (self.next_u32() >> 16) < prob16(p)

    def shuffle(self, arr: list) -> None:
        for i in range(len(arr) - 1, 0, -1):
            j = self.below(i + 1)
            arr[i], arr[j] = arr[j], arr[i]

    def weighted(self, weights: list[int]) -> int:
        total = sum(weights)
        r = self.below(total)
        acc = 0
        for i, w in enumerate(weights):
            acc += w
            if r < acc:
                return i
        raise AssertionError("unreachable")
