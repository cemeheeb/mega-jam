"""Симуляция забегов: мир-дерево из копий комнат и модели игроков.

Игроки:
- NotesPlayer  — действует только по запискам из блокнота. Берёт предмет, только если
                 записки сказали, что он нужен, и всё, что для него нужно, уже в кармане.
- RandomPlayer — записки не читает, хватает и меняет предметы наугад, ходит в случайные двери.
- ProbePlayer  — дополнительно, сверх задания: записки не читает, но умный. Проверяет предметы
                 по одному и смотрит, изменился ли вид комнаты; если изменился без урона —
                 оставляет предмет. Это оценка того, выгоден ли осмысленный перебор.

Запуск: python3 sim.py --seeds 5000
"""

import argparse
import statistics
from collections import defaultdict, Counter, deque
from dataclasses import dataclass, field

import generator as G
from config import Config, DEFAULT
from rng import Rng


class Room:
    """Комната за конкретной дверью. Вещи и записки у неё общие со всеми комнатами того же набора:
    что бы ни лежало в комнате набора, оно лежит там, через какую дверь в неё ни войди.
    Свои у комнаты только двери и состояние аномалии."""
    __slots__ = ("id", "key", "cls", "level", "look", "anomaly", "anomaly_active", "items", "notes",
                 "doors", "parent")

    def __init__(self, rid, rc: G.RoomContent, items: list, parent):
        self.id = rid
        self.key = rc.key
        self.cls = G.room_class(rc.key) if rid > 0 else G.CLS_START
        self.level = G.chain_level(rc.key)
        self.look = (rc.room_type, rc.switches)
        self.anomaly = rc.anomaly
        # Новая комната за нераскрытой дверью всегда начинает с исходного состояния аномалии;
        # устранённая в этой комнате больше не бьёт.
        self.anomaly_active = rc.anomaly != G.NO_ANOMALY
        self.items = items                      # общий список набора
        self.notes = rc.notes
        # id комнаты за дверью или None, если не раскрыта. Дверей четыре, одна из них входная.
        self.doors: list = [None] * (G.DOORS_PER_ROOM if parent < 0 else G.DOORS_PER_ROOM - 1)
        self.parent = parent                    # входная дверь ведёт сюда (-1 у стартовой рубки)


class World:
    def __init__(self, layout: G.RunLayout):
        self.layout = layout
        start = layout.start_room()
        # вещи набора, общие для его комнат. Скафандра здесь нет: он слот не занимает, а встречают его всегда раньше
        # разгерметизации (рядом с предыдущим ключом) — модель считает, что игрок его надел (DESIGN 5.9)
        self.items_of: dict[int, list] = {start.key: [i for i in start.items if i != G.SUIT]}
        self.rooms: list[Room] = [Room(0, start, self.items_of[start.key], -1)]

    def reveal(self, rid: int, door: int, key: int) -> int:
        rc = self.layout.room(key)
        if key not in self.items_of:
            self.items_of[key] = [i for i in rc.items if i != G.SUIT]
        room = Room(len(self.rooms), rc, self.items_of[key], rid)
        self.rooms.append(room)
        self.rooms[rid].doors[door] = room.id
        return room.id

    def neighbors(self, rid: int) -> list[int]:
        r = self.rooms[rid]
        out = [d for d in r.doors if d is not None]
        if r.parent >= 0:
            out.append(r.parent)
        return out

    def path(self, src: int, goal) -> list[int] | None:
        """Кратчайший путь по раскрытым дверям до комнаты, где goal(room) истинно. Без src."""
        prev = {src: -1}
        q = deque([src])
        while q:
            u = q.popleft()
            if u != src and goal(self.rooms[u]):
                out = []
                while u != src:
                    out.append(u)
                    u = prev[u]
                return out[::-1]
            for v in self.neighbors(u):
                if v not in prev:
                    prev[v] = u
                    q.append(v)
        return None


@dataclass
class Result:
    status: str = ""           # win / dead / timeout
    doors: int = 0             # раскрыто дверей (включая дверь в двигательный отсек и финальную в рубку)
    entries: int = 0           # входов в комнаты, включая повторные
    hits: int = 0
    anomaly_entries: int = 0   # входов в комнату с действующей аномалией
    max_level: int = 0         # самый дальний уровень цепочки, куда дошёл
    guess_rooms: int = 0       # сколько раз раскрыл дверь в комнату-догадку


class Sim:
    name = "base"

    def __init__(self, layout: G.RunLayout, health: int | None = None, salt: int = 0):
        self.L = layout
        self.cfg: Config = layout.cfg
        self.world = World(layout)
        self.health = layout.cfg.health if health is None else health
        self.rng = Rng(layout.seed, G.D_PLAYER, salt)
        self.pocket: list[int] = []
        self.cur = 0
        self.visited: set[int] = set()
        self.engine_fixed = False
        self.res = Result()

    # --- действия ---

    @property
    def room(self) -> Room:
        return self.world.rooms[self.cur]

    def enter(self, rid: int) -> None:
        first = rid not in self.visited
        self.visited.add(rid)
        self.cur = rid
        self.res.entries += 1
        r = self.room
        if r.cls == G.CLS_ENGINE:
            self.engine_fixed = True        # 5.10: войти с правильным набором достаточно
        if self.engine_fixed and r.look[0] == G.BRIDGE:
            self.res.status = "win"         # рубка после починки двигателя — концовка
            return
        if r.anomaly_active:
            self.res.anomaly_entries += 1
            if self.rng.chance(self.cfg.p_hit):
                self.res.hits += 1
                if self.res.hits >= self.health:
                    self.res.status = "dead"
                    return
            if self.rng.chance(self.cfg.p_fix):
                r.anomaly_active = False
        if first:
            self.on_first_visit(r)

    def reveal(self, door: int) -> None:
        key = self.L.pocket_key(self.pocket)
        rid = self.world.reveal(self.cur, door, key)
        self.res.doors += 1
        lvl = G.chain_level(key)
        self.res.max_level = max(self.res.max_level, lvl)
        if G.room_class(key) == G.CLS_GUESS:
            self.res.guess_rooms += 1
        self.enter(rid)

    def unrevealed(self) -> list[int]:
        return [i for i, d in enumerate(self.room.doors) if d is None]

    def free_slots(self) -> int:
        return G.POCKET_SLOTS - len(self.pocket)

    def pick(self, item: int) -> None:
        assert self.free_slots() > 0
        self.room.items.remove(item)
        self.pocket.append(item)

    def drop(self, item: int) -> None:
        self.pocket.remove(item)
        self.room.items.append(item)

    def explore(self) -> None:
        """Раскрыть дверь здесь, а если все раскрыты — шагнуть к ближайшей комнате с нераскрытой."""
        doors = self.unrevealed()
        if doors:
            self.reveal(doors[0])
            return
        p = self.world.path(self.cur, lambda r: any(d is None for d in r.doors))
        self.enter(p[0])

    # --- цикл ---

    def run(self) -> Result:
        self.enter(0)
        self.pick(G.NOTEBOOK)
        while not self.res.status:
            if self.res.entries >= self.cfg.max_entries:
                self.res.status = "timeout"
                break
            if self.room.cls == G.CLS_ENGINE:
                # Финал (решение автора 13.11): двигатель починен; «вспомни, как попал в рубку» —
                # выложить всё, кроме блокнота: один блокнот ведёт в рубку, это концовка.
                for it in [i for i in self.pocket if i != G.NOTEBOOK]:
                    self.drop(it)
                self.reveal(self.unrevealed()[0])
                assert self.res.status == "win" and self.room.look[0] == G.BRIDGE
                break
            self.step()
        return self.res

    def on_first_visit(self, room: Room) -> None:
        pass

    def step(self) -> None:
        raise NotImplementedError


class NotesPlayer(Sim):
    """Действует только по запискам. miss — шанс не заметить записку при входе."""
    name = "notes"

    def __init__(self, layout, health=None, salt=1, miss: float = 0.0, max_risky_backtrack: int = 0):
        super().__init__(layout, health, salt)
        self.miss = miss
        self.max_risky_backtrack = max_risky_backtrack
        self.read: set[tuple[int, int]] = set()
        self.chain: set[int] = {layout.first_note.items[0]}  # предметы, которые записки назвали нужными
        self.prereq: dict[int, frozenset] = {}               # что нужно держать, чтобы предмет появился
        self.final: frozenset | None = None
        self.order: list[int] = [layout.first_note.items[0]] # порядок, в котором узнавал о предметах
        self.discarded: set[int] = set()                     # выбросил сам: своё дело сделали

    def learn(self, note: G.Note) -> None:
        def add(it):
            if it not in self.chain:
                self.chain.add(it)
                self.order.append(it)
        if note.kind in (G.N_NOTEBOOK_FIRST, G.N_LOOP_EXIT):
            add(note.items[0])
        elif note.kind == G.N_NEXT_KEY:
            for it in note.items[1:]:
                add(it)
            add(note.items[0])
            self.prereq[note.items[0]] = frozenset(note.items[1:])
        elif note.kind == G.N_ENGINE_SET:
            for it in note.items[:3]:
                add(it)
            self.final = frozenset(note.items[:3])

    def read_notes(self, room: Room) -> None:
        for i, n in enumerate(room.notes):
            if (room.key, i) in self.read:
                continue
            if self.miss > 0 and self.rng.chance(self.miss):
                continue  # не заметил; при следующем визите попробует снова
            self.read.add((room.key, i))
            self.learn(n)

    def wanted(self) -> list[int]:
        held = set(self.pocket)
        return [it for it in self.order
                if it not in held and it not in self.discarded
                and self.prereq.get(it, frozenset()) <= held]

    def make_space(self, target: int) -> bool:
        """Освободить слот: выбросить самый ранний из известных предметов, который не нужен
        для target и не входит в финальный набор (если он известен). Блокнот не трогает."""
        if self.free_slots() > 0:
            return True
        keep = set(self.prereq.get(target, ())) | set(self.final or ())
        for it in sorted(self.pocket, key=lambda i: self.order.index(i) if i in self.order else -1):
            if it != G.NOTEBOOK and it not in keep:
                self.drop(it)
                self.discarded.add(it)
                return True
        return False

    def step(self) -> None:
        room = self.room
        self.read_notes(room)
        for it in self.wanted():
            if it in room.items and self.make_space(it):
                self.pick(it)
                return
        # Вернуться за нужным предметом, который видел раньше, если путь не опасен.
        want = set(self.wanted())
        if want:
            p = self.world.path(self.cur, lambda r: any(i in want for i in r.items) and r.id in self.visited)
            if p is not None:
                risky = sum(1 for rid in p if self.world.rooms[rid].anomaly_active)
                if risky <= self.max_risky_backtrack:
                    self.enter(p[0])
                    return
        self.explore()


class RandomPlayer(Sim):
    """Не читает записки. Блокнот держит, остальное хватает и меняет наугад."""
    name = "random"

    def __init__(self, layout, health=None, salt=2, p_take=0.5, p_swap=0.5, p_new_door=0.8):
        super().__init__(layout, health, salt)
        self.p_take, self.p_swap, self.p_new_door = p_take, p_swap, p_new_door

    def step(self) -> None:
        room = self.room
        items = list(room.items)
        self.rng.shuffle(items)
        for it in items:
            if not self.rng.chance(self.p_take):
                continue
            if self.free_slots() > 0:
                self.pick(it)
            elif self.rng.chance(self.p_swap):
                others = [i for i in self.pocket if i != G.NOTEBOOK]
                self.drop(others[self.rng.below(len(others))])
                self.pick(it)
        doors = self.unrevealed()
        if doors and self.rng.chance(self.p_new_door):
            self.reveal(doors[self.rng.below(len(doors))])
        else:
            nb = self.world.neighbors(self.cur)
            if nb:
                self.enter(nb[self.rng.below(len(nb))])
            else:
                self.reveal(doors[self.rng.below(len(doors))])


class ProbePlayer(Sim):
    """Не читает записки, но знает правило «значимый предмет меняет вид комнаты».

    Держит набор «рабочих» предметов. Чтобы проверить незнакомый предмет, берёт его
    и раскрывает дверь: вид как без него — пустышка; вид другой и урона нет — оставляет;
    вид другой и урон — помечает опасным. Если рабочий предмет дважды ранил в своих
    комнатах, выбрасывает его. Когда карман полон, выбрасывает самый старый рабочий.
    Если долго нечего проверять, забывает пометки «опасен» (мог ошибиться).
    """
    name = "probe"

    def __init__(self, layout, health=None, salt=3, patience=4):
        super().__init__(layout, health, salt)
        self.status: dict[int, str] = {}     # item -> dummy / good / bad
        self.kept: list[int] = []            # рабочие предметы, по порядку взятия
        self.ref: dict[frozenset, tuple] = {}  # вид комнаты для набора рабочих предметов
        self.testing: int | None = None
        self.blame: Counter = Counter()
        self.idle = 0
        self.patience = patience
        self.last_hits = 0

    def candidates(self, room: Room) -> list[int]:
        return [i for i in room.items if i >= 0 and self.status.get(i) is None and i not in self.kept]

    def after_reveal(self, kept_set: frozenset) -> None:
        room = self.room
        hurt = self.res.hits > self.last_hits
        if self.testing is not None:
            t = self.testing
            ref = self.ref.get(kept_set)
            if room.cls == G.CLS_ENGINE:
                return
            if ref is not None and room.look == ref:
                self.status[t] = "dummy"
                self.drop(t)
            elif hurt:
                self.status[t] = "bad"
                self.drop(t)
            else:
                self.status[t] = "good"
                self.kept.append(t)
                self.ref[frozenset(self.kept)] = room.look
            self.testing = None
        else:
            self.ref.setdefault(kept_set, room.look)
            if hurt and self.kept:
                newest = self.kept[-1]
                self.blame[newest] += 1
                if self.blame[newest] >= 2:
                    self.kept.remove(newest)
                    self.status[newest] = "bad"
                    self.drop(newest)

    def step(self) -> None:
        room = self.room
        self.last_hits = self.res.hits
        kept_set = frozenset(self.kept)
        cands = self.candidates(room)
        if self.testing is None and cands and kept_set in self.ref:
            if self.free_slots() == 0:
                old = self.kept.pop(0)
                self.drop(old)
                self.status[old] = None
                kept_set = frozenset(self.kept)
            if kept_set in self.ref:
                t = cands[self.rng.below(len(cands))]
                self.pick(t)
                self.testing = t
            self.idle = 0
        else:
            self.idle += 1
            if self.idle > self.patience:
                for k, v in list(self.status.items()):
                    if v == "bad":
                        self.status[k] = None
                self.idle = 0
        before = self.res.doors
        self.explore()
        if self.res.doors > before and not self.res.status:
            self.after_reveal(kept_set)


PLAYERS = {"notes": NotesPlayer, "random": RandomPlayer, "probe": ProbePlayer}


# ---------- прогон и сводка ----------

def run_many(cfg: Config, seeds, player: str, **kw) -> list[Result]:
    cls = PLAYERS[player]
    return [cls(G.RunLayout(s, cfg), **kw).run() for s in seeds]


def pct(x: float) -> str:
    return f"{100 * x:5.1f}%"


def summarize(results: list[Result], health: int) -> dict:
    n = len(results)
    st = Counter(r.status for r in results)
    wins = [r for r in results if r.status == "win"]
    out = {
        "runs": n,
        "win": st["win"] / n,
        "dead": st["dead"] / n,
        "timeout": st["timeout"] / n,
        "hits_mean": statistics.fmean(r.hits for r in results),
        "anomaly_entries_mean": statistics.fmean(r.anomaly_entries for r in results),
        # входов в уже пройденные комнаты: каждый раскрытый проём — один вход, плюс стартовая рубка
        "revisits_mean": statistics.fmean(r.entries - r.doors - 1 for r in results),
        "doors_mean_all": statistics.fmean(r.doors for r in results),
        "guess_rooms_mean": statistics.fmean(r.guess_rooms for r in results),
        "max_level": dict(sorted(Counter(r.max_level for r in results).items())),
    }
    if wins:
        d = sorted(r.doors for r in wins)
        out.update({
            "win_doors_mean": statistics.fmean(d),
            "win_doors_median": statistics.median(d),
            "win_doors_p10": d[int(0.1 * (len(d) - 1))],
            "win_doors_p90": d[int(0.9 * (len(d) - 1))],
            "win_hits_mean": statistics.fmean(r.hits for r in wins),
            "win_with_damage": sum(1 for r in wins if r.hits > 0) / len(wins),
            "win_hits_hist": dict(sorted(Counter(r.hits for r in wins).items())),
        })
    out["hits_hist"] = dict(sorted(Counter(r.hits for r in results).items()))
    return out


def print_summary(title: str, s: dict, health: int) -> None:
    print(f"\n== {title} ==")
    print(f"  забегов {s['runs']}: победа {pct(s['win'])}, смерть {pct(s['dead'])}, завис {pct(s['timeout'])}")
    print(f"  урон в среднем {s['hits_mean']:.2f} из {health}; распределение попаданий {s['hits_hist']}")
    print(f"  комнат-догадок за забег в среднем {s['guess_rooms_mean']:.2f}; "
          f"возвратов в пройденные комнаты {s['revisits_mean']:.2f}")
    print(f"  дальний уровень цепочки (0 рубка-петля .. 4 двигатель): {s['max_level']}")
    if "win_doors_mean" in s:
        print(f"  до победы раскрыто дверей: среднее {s['win_doors_mean']:.1f}, медиана {s['win_doors_median']}, "
              f"10–90% {s['win_doors_p10']}–{s['win_doors_p90']}")
        print(f"  у победителей урон {s['win_hits_mean']:.2f}, с потерями {pct(s['win_with_damage'])}, "
              f"распределение {s['win_hits_hist']}")


def generator_errors(cfg: Config, seeds) -> tuple[list, list]:
    """(сиды с ошибками статической проверки, сиды, где игрок по запискам с бесконечным
    здоровьем не дошёл до конца). Оба списка должны быть пустыми."""
    static_bad, notes_stuck = [], []
    for s in seeds:
        layout = G.RunLayout(s, cfg)
        e = G.validate_layout(layout)
        if e:
            static_bad.append((s, e[:3]))
        r = NotesPlayer(layout, health=10 ** 9).run()
        if r.status != "win":
            notes_stuck.append((s, r.status))
    return static_bad, notes_stuck


def main() -> None:
    ap = argparse.ArgumentParser(description="Прогон симуляторов по многим зёрнам")
    ap.add_argument("--seeds", type=int, default=5000)
    ap.add_argument("--first", type=int, default=1)
    ap.add_argument("--miss", type=float, default=0.3, help="доля незамеченных записок для проверки устойчивости")
    args = ap.parse_args()

    cfg = DEFAULT
    seeds = range(args.first, args.first + args.seeds)
    print(f"Конфигурация: {cfg}")

    static_bad, stuck = generator_errors(cfg, seeds)
    print(f"\nОшибки генератора: статическая проверка {len(static_bad)}, "
          f"непроходимо по запискам {len(stuck)} из {len(seeds)}")
    for s, e in static_bad[:5]:
        print("  ", s, e)
    for s, st in stuck[:5]:
        print("  ", s, st)

    for name, kw in (("notes", {}), ("notes", {"miss": args.miss}), ("random", {}), ("probe", {})):
        res = run_many(cfg, seeds, name, **kw)
        title = {"notes": "Игрок по запискам", "random": "Игрок наугад", "probe": "Умный перебор без записок (доп.)"}[name]
        if kw.get("miss"):
            title += f", пропускает {int(100 * kw['miss'])}% записок"
        print_summary(title, summarize(res, cfg.health), cfg.health)


if __name__ == "__main__":
    main()
