"""Подбор чисел баланса по сетке и отчёт BALANCE.md.

Цели (рабочее допущение, записано в разделе 14 DESIGN.md):
- игрок по запискам: побед 85–93%, из побед с уроном не меньше 75%, медиана 10–14 дверей;
- игрок наугад: смертей не меньше 95%, побед не больше 1%;
- игрок по запискам, пропускающий 30% записок: побед не меньше 75% (устойчивость).
Из подходящих точек берётся ближайшая к числам раздела 5.8.

Запуск: python3 balance.py [--seeds 2000] [--final-seeds 5000]
"""

import argparse
import itertools
import os
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict, replace

import sim
from config import START_5_8

GRID = {
    "health": (4, 5),
    "p_meaningful": (0.15, 0.18, 0.20, 0.22, 0.25),
    "p_target": (0.20, 0.25, 0.30, 0.35),
    "target_guarantee_by": (3, 4, 5),
}


def evaluate(args):
    params, seeds = args
    cfg = replace(START_5_8, **params)
    out = {"params": params}
    for name, kw, tag in (("notes", {}, "notes"), ("notes", {"miss": 0.3}, "miss"),
                          ("random", {}, "random"), ("probe", {}, "probe")):
        out[tag] = sim.summarize(sim.run_many(cfg, seeds, name, **kw), cfg.health)
    return out


def penalty(r) -> float:
    n, m, rnd = r["notes"], r["miss"], r["random"]
    p = 0.0
    p += 10 * max(0.0, 0.85 - n["win"]) + 10 * max(0.0, n["win"] - 0.93)
    p += 5 * max(0.0, 0.75 - n.get("win_with_damage", 0))
    med = n.get("win_doors_median", 0)
    p += 0.3 * max(0.0, 10 - med) + 0.3 * max(0.0, med - 14)
    p += 10 * max(0.0, 0.95 - rnd["dead"]) + 10 * max(0.0, rnd["win"] - 0.01)
    p += 5 * max(0.0, 0.75 - m["win"])
    return p


def closeness_to_5_8(params) -> float:
    return abs(params["p_meaningful"] - 0.15) * 10 + (0 if params["health"] in (4, 5) else 5)


def row(r) -> str:
    pr, n, m, rnd, pb = r["params"], r["notes"], r["miss"], r["random"], r["probe"]
    return (f"| {pr['health']} | {pr['p_meaningful']:.2f} | {pr['p_target']:.2f} | {pr['target_guarantee_by']} "
            f"| {100 * n['win']:.1f}% | {100 * n.get('win_with_damage', 0):.0f}% | {n['hits_mean']:.2f} "
            f"| {n.get('win_doors_median', '-')} | {100 * m['win']:.1f}% | {100 * rnd['dead']:.1f}% "
            f"| {100 * rnd['win']:.2f}% | {100 * pb['win']:.1f}% | {penalty(r):.2f} |")


HEADER = ("| HP | аномалия на цепочке | шанс предмета | гарантия к копии | по запискам: победа | побед с уроном "
          "| урон ср. | дверей (медиана) | пропуск 30%: победа | наугад: смерть | наугад: победа "
          "| умный перебор: победа | штраф |\n|" + "---|" * 13)


def lever_table(base_cfg, seeds) -> list[str]:
    """Как числа, которые не трогают игрока по запискам, влияют на перебор."""
    lines = ["| аномалия в догадке | вес ложных предметов | по запискам: победа | наугад: победа "
             "| умный перебор: победа | умный перебор: смерть |", "|" + "---|" * 6]
    for pg, fw in itertools.product((0.80, 0.85, 0.90), (1, 2, 3)):
        cfg = replace(base_cfg, p_guess=pg, false_weight=fw)
        n = sim.summarize(sim.run_many(cfg, seeds, "notes"), cfg.health)
        rnd = sim.summarize(sim.run_many(cfg, seeds, "random"), cfg.health)
        pb = sim.summarize(sim.run_many(cfg, seeds, "probe"), cfg.health)
        lines.append(f"| {pg:.2f} | {fw} | {100 * n['win']:.1f}% | {100 * rnd['win']:.2f}% "
                     f"| {100 * pb['win']:.1f}% | {100 * pb['dead']:.1f}% |")
    return lines


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, default=2000)
    ap.add_argument("--final-seeds", type=int, default=5000)
    ap.add_argument("--out", default=os.path.join(os.path.dirname(__file__), "BALANCE.md"))
    args = ap.parse_args()

    seeds = range(1, 1 + args.seeds)
    keys = list(GRID)
    jobs = [(dict(zip(keys, vals)), seeds) for vals in itertools.product(*GRID.values())]
    with ProcessPoolExecutor() as ex:
        results = list(ex.map(evaluate, jobs))

    start = evaluate(({k: getattr(START_5_8, k) for k in keys}, seeds))
    ranked = sorted(results, key=lambda r: (round(penalty(r), 2), closeness_to_5_8(r["params"]),
                                            abs(r["notes"]["win"] - 0.89)))
    best = ranked[0]

    # Проверка выбранной точки на свежих зёрнах (не тех, на которых подбирали)
    final_seeds = range(100_001, 100_001 + args.final_seeds)
    final = evaluate((best["params"], final_seeds))
    best_cfg = replace(START_5_8, **best["params"])
    static_bad, stuck = sim.generator_errors(best_cfg, final_seeds)
    levers = lever_table(best_cfg, range(200_001, 200_001 + 2000))

    lines = [
        "# Подбор баланса генератора забега",
        "",
        "Файл пишет `python3 balance.py`. Не править руками.",
        "",
        f"Сетка: {GRID}. На каждую точку {args.seeds} зёрен (1..{args.seeds}). "
        f"Остальные числа как в `config.START_5_8`.",
        "",
        "## Стартовая точка из раздела 5.8",
        "",
        HEADER,
        row(start),
        "",
        "## Лучшие 15 точек",
        "",
        HEADER,
        *[row(r) for r in ranked[:15]],
        "",
        f"## Выбранная точка на свежих зёрнах ({args.final_seeds} зёрен, {final_seeds.start}..{final_seeds.stop - 1})",
        "",
        f"Параметры: `{best['params']}`",
        "",
        HEADER,
        row(final),
        "",
        f"Ошибки генератора на этих зёрнах: статическая проверка {len(static_bad)}, "
        f"непроходимо по запискам {len(stuck)}.",
        "",
        "Подробно:",
        "",
        "```",
    ]
    for tag, title in (("notes", "по запискам"), ("miss", "по запискам, пропуск 30%"),
                       ("random", "наугад"), ("probe", "умный перебор (доп.)")):
        s = final[tag]
        lines.append(f"{title}: {s}")
    lines += [
        "```",
        "",
        "## Рычаги против перебора при выбранной точке (2000 зёрен)",
        "",
        "Эти числа не влияют на игрока по запискам: он не заходит в комнаты-догадки.",
        "",
        *levers,
        "",
    ]
    with open(args.out, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print("best", best["params"], "penalty", round(penalty(best), 3))
    print(HEADER)
    print(row(start))
    for r in ranked[:15]:
        print(row(r))
    print("final", row(final))
    print("generator errors", len(static_bad), len(stuck))
    print("\n".join(levers))
    print("written", args.out)


if __name__ == "__main__":
    main()
