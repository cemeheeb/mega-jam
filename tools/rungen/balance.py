"""Подбор чисел баланса по сетке и отчёт BALANCE.md.

Правила (решения автора 13.11, раздел 14 DESIGN.md): правильный путь безопасен, аномалию несёт
неправильное сочетание предметов. Поэтому игрок по запискам урона не получает, а подбирается одно:
как часто выигрывает умный перебор без записок.

Цели:
- игрок по запискам побеждает всегда (не меньше 99,5%);
- умный перебор побеждает в 3–4% забегов;
- игрок наугад почти всегда умирает (побед не больше 1%).
Среди точек, где цели выполнены, берётся ближайшая к середине полосы перебора.

Рычаги: число лишних значимых предметов, как часто они лежат в комнатах (веса лишнего и пустышки),
сколько прочих вещей лежит в комнате, здоровье.

Запуск: python3 balance.py
"""

import argparse
import itertools
import os
from concurrent.futures import ProcessPoolExecutor
from dataclasses import replace

import sim
from config import DEFAULT

MIN_NOTES = 0.995
TARGET_PROBE, TOL_PROBE = 0.035, 0.005
MAX_RANDOM_WIN = 0.01

EXTRAS = (5, 6, 7, 8)
WEIGHTS = ((2, 3), (1, 2), (2, 5), (1, 3))   # (вес пустышки, вес лишнего значимого)
FILLERS = ((2, 3), (3, 4), (4, 5))           # прочих вещей в комнате: от и до
HEALTH = (4,)
PLAYERS = ("notes", "random", "probe")


def evaluate(args):
    params, seeds = args
    cfg = replace(DEFAULT, **params)
    out = {"params": params}
    for name in PLAYERS:
        out[name] = sim.summarize(sim.run_many(cfg, seeds, name), cfg.health)
    return out


def penalty(r) -> float:
    p = 10 * max(0.0, MIN_NOTES - r["notes"]["win"])
    p += 20 * max(0.0, abs(r["probe"]["win"] - TARGET_PROBE) - TOL_PROBE)
    p += 10 * max(0.0, r["random"]["win"] - MAX_RANDOM_WIN)
    return p


def preference(r) -> tuple:
    return (round(penalty(r), 2), abs(r["probe"]["win"] - TARGET_PROBE))


def row(r) -> str:
    pr, n, rnd, pb = r["params"], r["notes"], r["random"], r["probe"]
    return (f"| {pr['health']} | {pr['extras']} | {pr['dummy_weight']}:{pr['extra_weight']} | {pr['filler_min']}–{pr['filler_max']} "
            f"| {100 * n['win']:.1f}% | {n['hits_mean']:.2f} | {n.get('win_doors_median', '-')} "
            f"| {100 * rnd['win']:.2f}% | {100 * pb['win']:.1f}% | {pb.get('win_doors_median', '-')} | {penalty(r):.2f} |")


HEADER = ("| HP | лишних значимых | веса пустышка:лишний | прочих вещей в комнате | по запискам: победа "
          "| по запискам: урон ср. | по запискам: дверей (медиана) | наугад: победа | умный перебор: победа "
          "| перебор: дверей (медиана) | штраф |\n|" + "---|" * 11)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, default=1500)
    ap.add_argument("--refine", type=int, default=8)
    ap.add_argument("--refine-seeds", type=int, default=6000)
    ap.add_argument("--out", default=os.path.join(os.path.dirname(__file__), "BALANCE.md"))
    args = ap.parse_args()

    grid = [dict(health=h, extras=e, dummy_weight=dw, extra_weight=ew, filler_min=fm, filler_max=fx)
            for h, e, (dw, ew), (fm, fx) in itertools.product(HEALTH, EXTRAS, WEIGHTS, FILLERS)]
    seeds = range(1, 1 + args.seeds)
    with ProcessPoolExecutor() as ex:
        coarse = list(ex.map(evaluate, [(p, seeds) for p in grid]))
    rseeds = range(300_001, 300_001 + args.refine_seeds)
    best_coarse = sorted(coarse, key=preference)[:args.refine]
    current = {k: getattr(DEFAULT, k) for k in ("health", "extras", "dummy_weight", "extra_weight", "filler_min", "filler_max")}
    todo = [r["params"] for r in best_coarse]
    if current not in todo:
        todo.append(current)
    with ProcessPoolExecutor() as ex:
        refined = list(ex.map(evaluate, [(p, rseeds) for p in todo]))
    refined.sort(key=preference)
    now = next(r for r in refined if r["params"] == current)

    lines = [
        "# Подбор баланса генератора забега",
        "",
        "Файл пишет `python3 balance.py`. Не править руками.",
        "",
        "Правила: комнату определяет только набор в кармане; правильный путь безопасен, аномалию несёт любое "
        "неправильное сочетание предметов. Игрок по запискам проходит за 5 дверей без урона, поэтому подбирается "
        "одно — как часто выигрывает умный перебор без записок.",
        "",
        f"Цели: по запискам не меньше {100 * MIN_NOTES:.1f}% побед, умный перебор "
        f"{100 * (TARGET_PROBE - TOL_PROBE):.0f}–{100 * (TARGET_PROBE + TOL_PROBE):.0f}%, "
        f"наугад не больше {100 * MAX_RANDOM_WIN:.0f}%.",
        "",
        f"## Числа по умолчанию (`config.DEFAULT`), {args.refine_seeds} зёрен",
        "",
        HEADER,
        row(now),
        "",
        f"## Вся сетка, {args.seeds} зёрен на точку",
        "",
        "Видно, чем двигается перебор: числом лишних значимых предметов, тем, как часто они лежат, и числом вещей в комнате.",
        "",
        HEADER,
        *[row(r) for r in coarse],
        "",
        f"## Лучшие точки на других зёрнах, {args.refine_seeds} зёрен ({rseeds.start}..{rseeds.stop - 1})",
        "",
        HEADER,
        *[row(r) for r in refined],
        "",
        "Разброс при 6000 зёрнах: стандартная ошибка около 0,25% для доли 3,5%.",
        "",
    ]
    with open(args.out, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(HEADER)
    for r in refined:
        print(row(r))
    print("written", args.out)


if __name__ == "__main__":
    main()
