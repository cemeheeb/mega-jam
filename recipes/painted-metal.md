# Крашеный металл — `painted-metal`

Студия: `assets/environment/common/painted-metal/asset.yaml` · kind: texture · стадия сейчас: idea · в игре: нет

Бесшовная белая краска панелей. Это материал `WallPaint` всех модулей корабля: панели, бока и внутренность ниш колонок у стен (`wall-columns`), дальше — стены, перегородки, потолок.

Картинки ещё нет. Есть только промт и замысел.

## Результат

Что должно получиться:
- `environment/common/painted-metal/painted-metal_base.png` — бесшовный цвет, 1024 × 1024. Развёртка модулей в метрах, плитка 2 × 2 м.
- карта высоты и нормаль `painted-metal_nor.png`, 1024.

Имена — предложение.

Поле `game` манифеста:
- `directory: environment/common/painted-metal`
- `textures` — эти файлы.

## Картинка

Шаблон `texture`, своих исключений нет. Снимков нет — собранный промт:

```text
PBR albedo texture for a first-person sci-fi video game set aboard a bright NASA-punk spaceship: a square swatch of the surface seen straight from above, filling the whole frame edge to edge. One continuous image, not a grid of repeated copies.

Off-white paint #ECEAE4 over satin painted metal, a flat wall panel: a smooth, even factory coating with a very faint orange-peel grain, sparse pin-sized chips and a few faint hairline scuffs, a slight cloudy variation of tone and a little dust; no seams, edges, bolts, panels or markings, nothing larger than a fingertip.

Style: semi-realistic material at real-world scale; subtle surface variation, light wear and a little dust in the crevices; flat even diffuse lighting with no shadows, highlights or reflections; low contrast so it reads as one calm surface from a distance.

Avoid: large distinct elements, high contrast, a grid of repeated copies, side view, perspective, horizon, objects, text, logos, directional shadows, specular highlights, vignette, borders, heavy rust, heavy grime.
```

## Обработка

1. **Бесшовность** — `pipeline/seamless-texture.md`, режим поверхности. Без окна: узора нет. Если края темнее — отступ 4 пикселя. Размер 1024.
2. **Средний цвет.** Он должен совпасть с полосами краски трим-листа `ship-trim`: sRGB около 0,90 0,90 0,88. Иначе на швах панелей будет видна граница.
   - Если не совпал — сдвинуть среднее после бесшовности: прибавить к каждому каналу разность между целевым и средним значением.
   - Деталь не трогать.
3. **Карта высоты и нормаль** — по гайду (`assets/environment/style.md`, «Карта высоты»): высота от Nano Banana по готовой картинке, нормаль через Bump и запекание Normal.
4. **Материал WallPaint:** Roughness 0,45, Metallic 0 (словарь материалов).

## Куда идёт дальше

Материал `WallPaint` набора `wall-columns` и картинки его выгрузки. После этого колонки пересобираются и выгружаются заново, по рецепту `wall-columns`.

Износ модулей — свои текстуры набора (ADR-032): краска и трим запекаются в атлас набора, ArmorPaint кладёт износ сверху. Поменялась краска — набор перезапекается.

## Проверка

- Плитка 3 × 3: ни пятен, ни сетки, ничего крупнее кончика пальца.
- Средний цвет ≈ (0,90; 0,90; 0,88) в sRGB.
- На модуле рядом с полосой краски трим-листа границы не видно.

## Подводные камни

- Сколы и пятна при повторе 2 м выстраиваются сеткой. В промте поэтому «sparse pin-sized» и «nothing larger than a fingertip». Если вышло крупнее — перегенерировать.
