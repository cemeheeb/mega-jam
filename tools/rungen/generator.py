"""Эталонный генератор забега: зерно -> раскладка. Чистая логика без движка.

Разделы DESIGN.md: 5.4–5.8. Всё, что зависит от случая, берётся из Rng с ключом
(seed, домен, ...), поэтому каждая величина считается независимо от остальных
и порядок вызовов в других местах на неё не влияет.

Сигнатура хранится как маска ролей (6 бит): бит 0 — проводник L, 1–3 — ключи K1–K3,
4–5 — ложные X и Y. Пустышки в маску не попадают. Ключ комнаты = маска, а при пустой
маске добавляется бит ANCHOR, если в кармане блокнот. Только блокнот (ANCHOR) — капитанская
рубка, это первая петля; совсем пустой карман (ключ 0) — жилая комната. Всего ключей 0..127,
счётчики копий можно держать в массиве.
"""

from dataclasses import dataclass

import content as C
from config import Config, DEFAULT
from rng import Rng, hash32

# Роли значимых предметов = номера битов в маске
L, K1, K2, K3, X, Y = 0, 1, 2, 3, 4, 5
DUMMY = 6
NOT_IN_RUN = -1
ROLE_NAMES = ("L", "K1", "K2", "K3", "X", "Y", "dummy")
NUM_SIG = 6

RM_L, RM_K1, RM_K2, RM_K3, RM_X, RM_Y = 1, 2, 4, 8, 16, 32
FINAL_MASK = RM_K1 | RM_K2 | RM_K3
ANCHOR = 64
NOTEBOOK = -1           # id блокнота в кармане (вне каталога)
POCKET_SLOTS = 4

# Типы отсеков, 5.1
BRIDGE, LIVING, LAB, LIFE_SUPPORT, ENGINE = 0, 1, 2, 3, 4
ROOM_TYPE_NAMES = ("Bridge", "Living", "Lab", "LifeSupport", "Engine")
ORDINARY_TYPES = (LIVING, LAB, LIFE_SUPPORT)

# Класс комнаты. CLS_START — только стартовая рубка (копия 0), у ключей такого класса нет.
CLS_START, CLS_CHAIN, CLS_GUESS, CLS_ENGINE = 0, 1, 2, 3
CLS_NAMES = ("start", "chain", "guess", "engine")

# Аномалии ядра, 5.9
NO_ANOMALY, FROZEN_MOMENT, RADIATION, GRAVITY_FAILURE, SLOW_TIME = 0, 1, 2, 3, 4
ANOMALY_NAMES = ("none", "FrozenMoment", "Radiation", "GravityFailure", "SlowTime")

# Записки
N_NOTEBOOK_FIRST, N_LOOP_EXIT, N_NEXT_KEY, N_USELESS, N_DANGER, N_ENGINE_SET, N_FINALE = range(7)

# Домены ГСЧ. Номер 2 свободен: раньше им выбирались типы уровней цепочки.
D_ROLES, _D_FREE_2, D_ROOM_TYPE, D_SWITCH, D_ANOMALY, D_DOORS, D_ITEMS, D_NOTES, \
    D_GUARANTEE, D_COSMETIC, D_START, D_PLAYER = range(1, 13)

# Цепочка: уровень петли -> роль предмета, который из неё выводит
CHAIN_TARGET = (L, K1, K2, K3)
# Предпосылки ключей, 5.7.2
PREREQ = {K1: RM_L, K2: RM_K1, K3: RM_K1 | RM_K2}


def popcount(x: int) -> int:
    return bin(x).count("1")


def room_key(role_mask: int, has_notebook: bool) -> int:
    if role_mask:
        return role_mask
    return ANCHOR if has_notebook else 0


def chain_level(key: int) -> int:
    """Уровень петли: 0 — без значимых предметов (рубка-петля при одном блокноте,
    жилая при пустом кармане), 1 {L}, 2 {L,K1}/{K1}, 3 {L,K1,K2}/{K1,K2},
    4 двигательный отсек. -1 — догадка."""
    if key in (0, ANCHOR):
        return 0
    if key & (RM_X | RM_Y):
        return -1
    if key & RM_K3:
        return 4 if key == FINAL_MASK else -1
    if key & RM_K2:
        return 3 if key & RM_K1 else -1
    if key & RM_K1:
        return 2
    if key & RM_L:
        return 1
    return -1


def room_class(key: int) -> int:
    lvl = chain_level(key)
    if lvl == 4:
        return CLS_ENGINE
    if lvl >= 0:
        return CLS_CHAIN
    return CLS_GUESS


def all_keys(max_items: int = POCKET_SLOTS) -> list[int]:
    """Все ключи, которые можно получить карманом на 4 слота."""
    keys = [0, ANCHOR]
    keys += [m for m in range(1, 64) if popcount(m) <= max_items]
    return keys


@dataclass(frozen=True)
class Note:
    kind: int
    items: tuple[int, ...]  # id предметов: см. порядок ниже
    tpl: int                # номер шаблона текста
    # NOTEBOOK_FIRST: (L,)  LOOP_EXIT: (цель,)  NEXT_KEY: (ключ, *предпосылки)
    # USELESS: (пустышка,)  DANGER: (X или Y,)  ENGINE_SET: (K1, K2, K3, L)  FINALE: ()

    def text(self) -> str:
        return C.render(self.kind, self.tpl, self.items)


@dataclass(frozen=True)
class RoomContent:
    key: int
    copy: int
    room_type: int
    switches: int
    anomaly: int
    doors: int               # нераскрытых дверей, кроме входной
    items: tuple[int, ...]   # id предметов (NOTEBOOK для блокнота)
    notes: tuple[Note, ...]


class RunLayout:
    """Раскладка забега. Всё вычисляется из seed и cfg."""

    def __init__(self, seed: int, cfg: Config = DEFAULT):
        if cfg.items_in_run < NUM_SIG + 2 or cfg.items_in_run > len(C.CATALOG):
            raise ValueError("items_in_run out of range")
        self.seed = seed & 0xFFFFFFFF
        self.cfg = cfg

        # 1. Роли. Перемешать каталог, первые items_in_run идут в забег;
        #    из них первые шесть получают роли L, K1, K2, K3, X, Y, остальные — пустышки.
        order = list(range(len(C.CATALOG)))
        Rng(self.seed, D_ROLES).shuffle(order)
        self.run_items: tuple[int, ...] = tuple(order[:cfg.items_in_run])
        self.role_item: tuple[int, ...] = self.run_items[:NUM_SIG]
        self.dummies: tuple[int, ...] = self.run_items[NUM_SIG:]
        self.item_role = [NOT_IN_RUN] * len(C.CATALOG)
        for r, it in enumerate(self.role_item):
            self.item_role[it] = r
        for it in self.dummies:
            self.item_role[it] = DUMMY

        # 2. Тип отсека для сигнатуры со значимыми предметами — по хешу в look().
        #    Шаг цепочки не обязан менять тип: выход из петли видно по переключателям
        #    и поведению комнаты (решение автора 13.11).

        # 3. Переключатели, 5.1: в каждом обычном типе каждый значимый предмет
        #    включает ровно один из шести переключателей. switch_of[type][role] -> номер.
        self.switch_of: dict[int, tuple[int, ...]] = {}
        for t in ORDINARY_TYPES:
            perm = list(range(NUM_SIG))
            Rng(self.seed, D_SWITCH, t).shuffle(perm)
            self.switch_of[t] = tuple(perm)
        # Рубка (только блокнот) и двигательный отсек бывают при одной сигнатуре:
        # их переключатели косметические, постоянные в пределах забега.
        self.bridge_switches = hash32(self.seed, D_COSMETIC, BRIDGE) & 63
        self.engine_switches = hash32(self.seed, D_COSMETIC, ENGINE) & 63

        # 4. Прочие предметы для раскладки: пустышки и ложные.
        self.filler_pool: tuple[int, ...] = self.dummies + (self.role_item[X], self.role_item[Y])
        self.filler_weights: tuple[int, ...] = (cfg.dummy_weight,) * len(self.dummies) + (cfg.false_weight,) * 2

        self.first_note = Note(N_NOTEBOOK_FIRST, (self.role_item[L],), 0)

    # ---------- роли и сигнатуры ----------

    def role_of(self, item: int) -> int:
        if item == NOTEBOOK:
            return NOT_IN_RUN
        return self.item_role[item]

    def role_mask(self, pocket) -> int:
        m = 0
        for it in pocket:
            r = self.role_of(it)
            if 0 <= r < NUM_SIG:
                m |= 1 << r
        return m

    def pocket_key(self, pocket) -> int:
        return room_key(self.role_mask(pocket), NOTEBOOK in pocket)

    # ---------- сигнатура -> вид комнаты ----------

    def look(self, key: int) -> tuple[int, int]:
        """(тип отсека, маска переключателей). Детерминирована от seed и key."""
        if key == ANCHOR:
            return BRIDGE, self.bridge_switches
        if key == 0:
            return LIVING, 0
        if key == FINAL_MASK:
            return ENGINE, self.engine_switches
        t = ORDINARY_TYPES[hash32(self.seed, D_ROOM_TYPE, key) % len(ORDINARY_TYPES)]
        sw = 0
        perm = self.switch_of[t]
        for r in range(NUM_SIG):
            if key & (1 << r):
                sw |= 1 << perm[r]
        return t, sw

    def anomaly_chance(self, key: int) -> float:
        cls = room_class(key)
        if cls == CLS_CHAIN:
            return self.cfg.p_meaningful
        if cls == CLS_GUESS:
            return self.cfg.p_guess
        return 0.0

    def guarantee_copy(self, key: int) -> int:
        """Номер копии (с 1), в которой нужный предмет лежит наверняка. 0 — гарантии нет."""
        g = self.cfg.target_guarantee_by
        if g <= 0:
            return 0
        return 1 + hash32(self.seed, D_GUARANTEE, key) % g

    # ---------- записки ----------

    def _ahead_note(self, lvl: int) -> tuple[int, tuple[int, ...]]:
        """Записка «на шаг вперёд» для петли уровня lvl, 5.7.4."""
        ri = self.role_item
        if lvl == 0:
            return N_NEXT_KEY, (ri[K1], ri[L])
        if lvl == 1:
            return N_NEXT_KEY, (ri[K2], ri[K1])
        if lvl == 2:
            return N_NEXT_KEY, (ri[K3], ri[K1], ri[K2])
        return N_ENGINE_SET, (ri[K1], ri[K2], ri[K3], ri[L])

    def _note(self, rng: Rng, kind: int, items: tuple[int, ...]) -> Note:
        return Note(kind, items, rng.below(len(C.TEMPLATES[kind])))

    def _chain_notes(self, key: int, copy: int) -> tuple[Note, ...]:
        # Порядок вызовов rng важен для порта: см. комментарии.
        lvl = chain_level(key)
        rng = Rng(self.seed, D_NOTES, key, copy)
        notes = []
        if copy == 1:  # гарантированная записка на шаг вперёд в первой копии
            kind, items = self._ahead_note(lvl)
            notes.append(self._note(rng, kind, items))          # rng: шаблон
        if rng.chance(self.cfg.p_extra_note):                    # rng: есть ли доп. записка
            pick = rng.weighted([2, 2, 2, 1])                    # rng: вид
            if pick == 1 and copy == 1:
                pick = 0  # в первой копии записка на шаг вперёд уже есть, вместо повтора — выход из петли
            if pick == 0:
                kind, items = N_LOOP_EXIT, (self.role_item[CHAIN_TARGET[lvl]],)
            elif pick == 1:
                kind, items = self._ahead_note(lvl)
            elif pick == 2:
                kind, items = N_USELESS, (self.dummies[rng.below(len(self.dummies))],)   # rng: предмет
            else:
                kind, items = N_DANGER, (self.role_item[X + rng.below(2)],)            # rng: предмет
            notes.append(self._note(rng, kind, items))           # rng: шаблон
        return tuple(notes)

    def _guess_notes(self, key: int, copy: int) -> tuple[Note, ...]:
        rng = Rng(self.seed, D_NOTES, key, copy)
        if not rng.chance(self.cfg.p_guess_note):
            return ()
        if rng.weighted([2, 1]) == 0:
            kind, items = N_USELESS, (self.dummies[rng.below(len(self.dummies))],)
        else:
            kind, items = N_DANGER, (self.role_item[X + rng.below(2)],)
        return (self._note(rng, kind, items),)

    # ---------- содержимое копии комнаты ----------

    def _draw_filler(self, rng: Rng, n: int) -> list[int]:
        pool = list(self.filler_pool)
        weights = list(self.filler_weights)
        out = []
        for _ in range(min(n, len(pool))):
            i = rng.weighted(weights)
            out.append(pool.pop(i))
            weights.pop(i)
        return out

    def start_room(self) -> RoomContent:
        """Рубка в начале забега: блокнот и две пустышки, без аномалии и записок.
        Вид — как у рубки-петли (ключ ANCHOR), номер копии 0."""
        rng = Rng(self.seed, D_START)
        dummies = list(self.dummies)
        a = dummies.pop(rng.below(len(dummies)))
        b = dummies.pop(rng.below(len(dummies)))
        t, sw = self.look(ANCHOR)
        return RoomContent(ANCHOR, 0, t, sw, NO_ANOMALY, 3, (NOTEBOOK, a, b), ())

    def room_copy(self, key: int, copy: int) -> RoomContent:
        """Содержимое copy-й (с 1) копии комнаты с ключом key. Разыгрывается отдельно
        для каждой копии, 5.4."""
        cfg = self.cfg
        t, sw = self.look(key)
        cls = room_class(key)

        if cls == CLS_ENGINE:
            rng = Rng(self.seed, D_NOTES, key, copy)
            return RoomContent(key, copy, t, sw, NO_ANOMALY, 2, (), (self._note(rng, N_FINALE, ()),))

        arng = Rng(self.seed, D_ANOMALY, key, copy)
        anomaly = NO_ANOMALY
        if arng.chance(self.anomaly_chance(key)):
            anomaly = 1 + arng.below(4)

        drng = Rng(self.seed, D_DOORS, key, copy)
        doors = cfg.doors_min + drng.below(cfg.doors_max - cfg.doors_min + 1)

        irng = Rng(self.seed, D_ITEMS, key, copy)
        items: list[int] = []
        if cls == CLS_CHAIN:
            target = self.role_item[CHAIN_TARGET[chain_level(key)]]
            rolled = irng.chance(cfg.p_target)                   # бросок делается всегда
            if rolled or copy == self.guarantee_copy(key):
                items.append(target)
        n_fill = cfg.filler_min + irng.below(cfg.filler_max - cfg.filler_min + 1)
        items += self._draw_filler(irng, n_fill)

        notes = self._chain_notes(key, copy) if cls == CLS_CHAIN else self._guess_notes(key, copy)
        return RoomContent(key, copy, t, sw, anomaly, doors, tuple(items), notes)

    # ---------- описание для дампа ----------

    def describe(self) -> dict:
        ri = self.role_item
        return {
            "seed": self.seed,
            "roles": {ROLE_NAMES[r]: C.CATALOG[ri[r]].name for r in range(NUM_SIG)},
            "dummies": [C.CATALOG[i].name for i in self.dummies],
            "chain": [C.CATALOG[ri[r]].name for r in CHAIN_TARGET],
            "final_set": [C.CATALOG[ri[r]].name for r in (K1, K2, K3)],
            "chain_room_types": {name: ROOM_TYPE_NAMES[self.look(k)[0]] for name, k in (
                ("notebook only", ANCHOR), ("empty pocket", 0), ("L", RM_L), ("L,K1", RM_L | RM_K1),
                ("K1", RM_K1), ("L,K1,K2", RM_L | RM_K1 | RM_K2), ("K1,K2", RM_K1 | RM_K2),
                ("K1,K2,K3", FINAL_MASK))},
            "notebook_first": self.first_note.text(),
        }


# ---------- проверка правдивости записок ----------

def note_is_true(layout: RunLayout, note: Note, key: int) -> bool:
    """Независимая проверка утверждения записки по ролям забега."""
    role = layout.role_of
    ri = layout.role_item
    if note.kind == N_NOTEBOOK_FIRST:
        return note.items == (ri[L],)
    if note.kind == N_LOOP_EXIT:
        lvl = chain_level(key)
        return 0 <= lvl <= 3 and note.items == (ri[CHAIN_TARGET[lvl]],)
    if note.kind == N_NEXT_KEY:
        k = role(note.items[0])
        if k not in PREREQ:
            return False
        pre = 0
        for it in note.items[1:]:
            r = role(it)
            if not (0 <= r < NUM_SIG):
                return False
            pre |= 1 << r
        return pre == PREREQ[k] and len(note.items) - 1 == popcount(pre)
    if note.kind == N_USELESS:
        return role(note.items[0]) == DUMMY
    if note.kind == N_DANGER:
        return role(note.items[0]) in (X, Y)
    if note.kind == N_ENGINE_SET:
        return note.items == (ri[K1], ri[K2], ri[K3], ri[L])
    if note.kind == N_FINALE:
        return note.items == () and room_class(key) == CLS_ENGINE
    return False


def validate_layout(layout: RunLayout, copies: int = 12) -> list[str]:
    """Статическая проверка раскладки. Пустой список — ошибок нет."""
    err: list[str] = []
    cfg = layout.cfg
    ri = layout.role_item

    if len(set(layout.run_items)) != cfg.items_in_run:
        err.append("run items not distinct")
    if layout.first_note.items != (ri[L],):
        err.append("notebook first entry does not name L")
    if popcount(FINAL_MASK) > POCKET_SLOTS - 1:
        err.append("final set does not fit next to the notebook")

    # Вид комнаты: рубка только при одном блокноте, жилая при пустом кармане, двигатель только
    # при финальной сигнатуре, один вид на одну сигнатуру, разные виды у разных.
    seen_looks: dict[tuple[int, int], int] = {}
    for key in all_keys():
        t, sw = layout.look(key)
        if (t == BRIDGE) != (key == ANCHOR):
            err.append(f"key {key}: bridge rule broken")
        if (t == ENGINE) != (key == FINAL_MASK):
            err.append(f"key {key}: engine rule broken")
        if key == 0 and t != LIVING:
            err.append("empty pocket does not lead to living quarters")
        if (t, sw) in seen_looks:
            err.append(f"keys {seen_looks[(t, sw)]} and {key} look identical")
        seen_looks[(t, sw)] = key
        if layout.look(key) != (t, sw):
            err.append(f"key {key}: look not deterministic")

    # Содержимое копий: предпосылки, гарантия цели, правдивость записок,
    # записка на шаг вперёд в первой копии каждой петли цепочки.
    chain_items = {ri[L]: 0, ri[K1]: RM_L, ri[K2]: RM_K1, ri[K3]: RM_K1 | RM_K2}
    for key in all_keys():
        cls = room_class(key)
        lvl = chain_level(key)
        target_seen_by = None
        for c in range(1, copies + 1):
            rc = layout.room_copy(key, c)
            if rc != layout.room_copy(key, c):
                err.append(f"key {key} copy {c}: content not deterministic")
            for it in rc.items:
                if it in chain_items:
                    need = chain_items[it]
                    if it == ri[L]:
                        if lvl != 0:
                            err.append(f"key {key} copy {c}: L outside the first loop")
                    elif key & need != need:
                        err.append(f"key {key} copy {c}: {ROLE_NAMES[layout.role_of(it)]} without prerequisites")
                    if cls != CLS_CHAIN or it != ri[CHAIN_TARGET[lvl]]:
                        err.append(f"key {key} copy {c}: chain item placed off-target")
                    elif target_seen_by is None:
                        target_seen_by = c
                elif layout.role_of(it) == NOT_IN_RUN:
                    err.append(f"key {key} copy {c}: item not in this run")
            for n in rc.notes:
                if not note_is_true(layout, n, key):
                    err.append(f"key {key} copy {c}: false note {n}")
                if n.kind in (N_LOOP_EXIT, N_NEXT_KEY, N_ENGINE_SET) and cls != CLS_CHAIN:
                    err.append(f"key {key} copy {c}: chain note outside the chain")
            if cls == CLS_ENGINE and rc.anomaly != NO_ANOMALY:
                err.append(f"key {key}: anomaly in a safe room")
            if cls == CLS_CHAIN and c == 1:
                want_kind, want_items = layout._ahead_note(lvl)
                if not any(n.kind == want_kind and n.items == want_items for n in rc.notes):
                    err.append(f"key {key}: first copy lacks the next-link note")
        if cls == CLS_CHAIN and cfg.target_guarantee_by > 0:
            if target_seen_by is None or target_seen_by > cfg.target_guarantee_by:
                err.append(f"key {key}: target not placed by copy {cfg.target_guarantee_by}")
    return err
