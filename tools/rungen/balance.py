"""Подбор чисел баланса по сетке и отчёт BALANCE.md.

Цели (решение автора 13.11, раздел 14 DESIGN.md):
- игрок по запискам побеждает примерно в 60% забегов (допуск ±3%);
- умный перебор без записок побеждает в 3–4% забегов;
- игрок наугад почти всегда умирает (побед не больше 1%).
Среди точек, где цели выполнены, берётся самый короткий забег (медиана дверей до победы,
допущение: забег около 11 дверей), затем точка ближе к числам раздела 5.8.

Три прохода: грубая сетка на --seeds зёрнах; лучшие --refine точек на --refine-seeds других
зёрнах (выборка большая, потому что полоса 3–4% у перебора сравнима с разбросом); выбранная
точка — на свежих --final-seeds зёрнах.

Запуск: python3 balance.py
"""

import argparse
import itertools
import os
from concurrent.futures import ProcessPoolExecutor
from dataclasses import replace

import sim
from config import START_5_8

TARGET_NOTES, TOL_NOTES = 0.60, 0.03
TARGET_PROBE, TOL_PROBE = 0.035, 0.005
MAX_RANDOM_WIN = 0.01
TARGET_P_MEANINGFUL = 0.15  # 5.8: аномалия на цепочке ~15%

GRID = {
    "health": (4, 5),
    "p_meaningful": (0.15, 0.20, 0.25, 0.275, 0.30, 0.35),
    "p_target": (0.10, 0.15, 0.175, 0.20, 0.225, 0.25),
    "target_guarantee_by": (5, 7, 8, 9),
    "false_weight": (1, 2),
}
PLAYERS = ("notes", "random", "probe")
VARIANTS = {"notes": ("notes", {}), "miss": ("notes", {"miss": 0.3}),
            "random": ("random", {}), "probe": ("probe", {})}


def evaluate(args):
    params, seeds, players = args
    cfg = replace(START_5_8, **params)
    out = {"params": params}
    for tag in players:
        name, kw = VARIANTS[tag]
        out[tag] = sim.summarize(sim.run_many(cfg, seeds, name, **kw), cfg.health)
    return out


def run_one(args):
    """Один игрок на одной конфигурации — для таблиц чувствительности."""
    params, seeds, player, kw = args
    cfg = replace(START_5_8, **params)
    return sim.summarize(sim.run_many(cfg, seeds, player, **kw), cfg.health)


def penalty(r) -> float:
    n, rnd, pb = r["notes"], r["random"], r["probe"]
    p = 10 * max(0.0, abs(n["win"] - TARGET_NOTES) - TOL_NOTES)
    p += 20 * max(0.0, abs(pb["win"] - TARGET_PROBE) - TOL_PROBE)
    p += 10 * max(0.0, rnd["win"] - MAX_RANDOM_WIN)
    return p


def preference(r) -> tuple:
    """Порядок выбора: цели выполнены → короче забег → ближе к 5.8 → ближе к центру целей."""
    pr = r["params"]
    return (round(penalty(r), 2),
            r["notes"].get("win_doors_median", 99),
            round(abs(pr["p_meaningful"] - TARGET_P_MEANINGFUL), 3),
            abs(r["notes"]["win"] - TARGET_NOTES) / TOL_NOTES + abs(r["probe"]["win"] - TARGET_PROBE) / TOL_PROBE)


def row(r) -> str:
    pr, n, rnd, pb = r["params"], r["notes"], r["random"], r["probe"]
    m = r.get("miss")
    miss = f"{100 * m['win']:.1f}%" if m else "—"
    return (f"| {pr['health']} | {pr['p_meaningful']:g} | {pr['p_target']:g} | {pr['target_guarantee_by']} "
            f"| {pr['false_weight']} | {100 * n['win']:.1f}% | {100 * n.get('win_with_damage', 0):.0f}% "
            f"| {n['hits_mean']:.2f} | {n.get('win_doors_median', '-')} | {miss} | {100 * rnd['win']:.2f}% "
            f"| {100 * pb['win']:.1f}% | {penalty(r):.2f} |")


HEADER = ("| HP | аномалия на цепочке | шанс предмета | гарантия к копии | вес ложных | по запискам: победа "
          "| побед с уроном | урон ср. | дверей до победы (медиана) | пропуск 30% записок: победа "
          "| наугад: победа | умный перебор: победа | штраф |\n|" + "---|" * 13)


def lever_tables(params, seeds) -> list[str]:
    """Чувствительность выбранной точки к числам, которые решаются отдельно."""
    a = [(pg, fw) for pg in (0.80, 0.85, 0.90) for fw in (1, 2, 3, 4)]
    b = [(bt, pf) for bt in (0, 1, 2) for pf in (0.0, 0.5, 1.0)]
    jobs = []
    for pg, fw in a:
        p = {**params, "p_guess": pg, "false_weight": fw}
        jobs += [(p, seeds, k, {}) for k in ("notes", "probe", "random")]
    for bt, pf in b:
        jobs.append(({**params, "p_fix": pf}, seeds, "notes", {"max_risky_backtrack": bt}))
    with ProcessPoolExecutor() as ex:
        res = list(ex.map(run_one, jobs))

    lines = ["### Аномалия в догадке и вес ложных предметов", "",
             "| аномалия в догадке | вес ложных | по запискам: победа | умный перебор: победа | наугад: победа |",
             "|" + "---|" * 5]
    for i, (pg, fw) in enumerate(a):
        n, pb, rnd = res[3 * i: 3 * i + 3]
        lines.append(f"| {pg:.2f} | {fw} | {100 * n['win']:.1f}% | {100 * pb['win']:.1f}% | {100 * rnd['win']:.2f}% |")
    lines += ["", "### Возврат через комнаты с аномалией и шанс её устранить", "",
              "Основной игрок по запискам не возвращается за предметом через комнату с действующей аномалией, "
              "а новые двери всегда ведут в новые копии. Поэтому `p_fix` на основные числа не влияет. "
              "Здесь игрок готов пройти назад через 1–2 такие комнаты; `p_fix` — шанс устранить аномалию "
              "за визит (модель игрока, в игру не переносится).", "",
              "| готов пройти через опасных комнат | шанс устранить | по запискам: победа | урон ср. "
              "| входов в действующую аномалию ср. |", "|" + "---|" * 5]
    off = 3 * len(a)
    for j, (bt, pf) in enumerate(b):
        n = res[off + j]
        lines.append(f"| {bt} | {pf:.1f} | {100 * n['win']:.1f}% | {n['hits_mean']:.2f} "
                     f"| {n.get('anomaly_entries_mean', 0):.2f} |")
    return lines


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, default=1500)
    ap.add_argument("--refine", type=int, default=30)
    ap.add_argument("--refine-seeds", type=int, default=6000)
    ap.add_argument("--final-seeds", type=int, default=10000)
    ap.add_argument("--out", default=os.path.join(os.path.dirname(__file__), "BALANCE.md"))
    args = ap.parse_args()

    keys = list(GRID)
    seeds = range(1, 1 + args.seeds)
    jobs = [(dict(zip(keys, vals)), seeds, PLAYERS) for vals in itertools.product(*GRID.values())]
    with ProcessPoolExecutor() as ex:
        coarse = list(ex.map(evaluate, jobs))
    coarse.sort(key=preference)

    rseeds = range(300_001, 300_001 + args.refine_seeds)
    start_params = {k: getattr(START_5_8, k) for k in keys}
    with ProcessPoolExecutor() as ex:
        refined = list(ex.map(evaluate, [(r["params"], rseeds, PLAYERS + ("miss",))
                                          for r in coarse[:args.refine]] + [(start_params, rseeds, PLAYERS + ("miss",))]))
    start = refined.pop()
    refined.sort(key=preference)
    best = refined[0]

    final_seeds = range(100_001, 100_001 + args.final_seeds)
    with ProcessPoolExecutor() as ex:
        parts = list(ex.map(evaluate, [(best["params"], final_seeds, (t,)) for t in PLAYERS + ("miss",)]))
    final = {"params": best["params"]}
    for p in parts:
        final.update({k: v for k, v in p.items() if k != "params"})
    best_cfg = replace(START_5_8, **best["params"])
    static_bad, stuck = sim.generator_errors(best_cfg, final_seeds)
    levers = lever_tables(best["params"], range(200_001, 200_001 + 4000))

    lines = [
        "# Подбор баланса генератора забега",
        "",
        "Файл пишет `python3 balance.py`. Не править руками.",
        "",
        f"Цели: по запискам {100 * TARGET_NOTES:.0f}% ± {100 * TOL_NOTES:.0f}% побед, умный перебор "
        f"{100 * (TARGET_PROBE - TOL_PROBE):.0f}–{100 * (TARGET_PROBE + TOL_PROBE):.0f}% побед, "
        f"наугад не больше {100 * MAX_RANDOM_WIN:.0f}% побед. Среди точек, где цели выполнены, выбран самый "
        "короткий забег, затем аномалия на цепочке ближе к 15% из раздела 5.8.",
        "",
        "Модель урона: аномалия бьёт при каждом входе, пока её не устранили в этой копии комнаты "
        f"(`p_hit` = {START_5_8.p_hit}, шанс устранить за визит `p_fix` = {START_5_8.p_fix}). Новая копия "
        "начинает с исходного состояния.",
        "",
        f"Сетка: `{GRID}`. Грубый проход — {args.seeds} зёрен на точку (1..{args.seeds}), лучшие "
        f"{args.refine} точек — {args.refine_seeds} других зёрен ({rseeds.start}..{rseeds.stop - 1}). "
        "Остальные числа как в `config.START_5_8`. Разброс: при 6000 зёрнах стандартная ошибка "
        "около 0,6% для 60% и около 0,25% для 3,5%.",
        "",
        f"## Стартовая точка из раздела 5.8 ({args.refine_seeds} зёрен)",
        "",
        HEADER,
        row(start),
        "",
        f"## Лучшие точки ({args.refine_seeds} зёрен), в порядке выбора",
        "",
        HEADER,
        *[row(r) for r in refined],
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
                       ("random", "наугад"), ("probe", "умный перебор")):
        lines.append(f"{title}: {final[tag]}")
    lines += ["```", "", "## Чувствительность выбранной точки (4000 зёрен)", "", *levers, ""]
    with open(args.out, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print("best", best["params"], "penalty", round(penalty(best), 3))
    print(HEADER)
    print(row(start))
    for r in refined:
        print(row(r))
    print("final", row(final))
    print("generator errors", len(static_bad), len(stuck))
    print("\n".join(levers))
    print("written", args.out)


if __name__ == "__main__":
    main()
