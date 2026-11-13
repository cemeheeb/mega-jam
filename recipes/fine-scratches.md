# Мелкие царапины — `fine-scratches`

Студия: `assets/environment/common/fine-scratches/asset.yaml` · kind: texture (шаблон grayscale-map) · стадия сейчас: image · в игре: `environment/common/fine-scratches`

Маска мелких царапин: краска после многих лет службы. Нужна для слоя износа на всех палубах.

Заменяет `weathering` в слое Scuffs наборов модулей. У `weathering` не подошли группы царапин, потёртости и грязь.

## Результат

В игре — `environment/common/fine-scratches/fine-scratches.png`: бесшовная по обеим осям серая маска 1024 × 1024, PNG RGB 8 бит. Белое — царапина, чёрное — чистая краска. Все три канала одинаковые.

Поле `game` манифеста:
- `directory: environment/common/fine-scratches`
- `textures: [environment/common/fine-scratches/fine-scratches.png]`

## Картинка

Шаблон `grayscale-map`, свои исключения: chips, scuffs or blotches, smudges of grime, scratches running across the whole frame, deep gouges. Снимок `approved/fine-scratches-1.txt`, собранный промт совпадает:

```text
Grayscale texture map for a semi-realistic PBR video game: a square swatch of a material seen straight from above, filling the whole frame edge to edge, in shades of grey only. One continuous image, not a grid of repeated copies.

Wear mask of fine scratches on painted metal after many years of daily use, a swatch about one metre across: white scratches on a black background. Hundreds of small thin scratches, each one to five centimetres long, straight or gently curved, crisp and only a couple of pixels wide, in random directions, crossing and overlapping; some lie in loose parallel groups, as if from wiping or from objects slid across the surface. Most are faint grey, fewer are brighter. About a quarter of the frame carries scratches, spread evenly over the whole frame.

Style: a clean scanned material map at real-world scale: pure grey values with no color, no lighting, no shadows, no highlights or reflections; the same density and brightness over the whole frame with no vignette, so that it tiles calmly.

Avoid: color, a grid of repeated copies, perspective, side view, objects, text, logos, directional shadows, specular highlights, vignette, a frame around the image, a gradient across the image, one large feature in the middle, chips, scuffs or blotches, smudges of grime, scratches running across the whole frame, deep gouges.
```

Генерация — PNG 1024 × 1024. Утверждена с первой попытки.

Почему образец около метра. Набор модулей кладёт около 322 пикселей атласа на метр. Царапина шириной в пару пикселей картинки при метре на 1024 пикселя ложится примерно в один тексель. Тоньше на атласе не видно.

## Бесшовность

Метод — `pipeline/seamless-texture.md`, режим поверхности:
- окна нет — узор нерегулярный, берётся вся картинка;
- скачок на краях снимается разложением на периодическую и гладкую части;
- размер 1024 — совпадает с исходным, интерполяция ничего не меняет.

Результат пишется в `fine-scratches.png` в папке игры.

## Как маску кладут на модули

Подробности — в рецептах `wall-columns` и `sliding-door`. Суть, чтобы маска подходила к ним:
1. **Каналы.** Маска идёт в G и B текстуры `<набор>_scuffs.png`, два раза. В R этой текстуры — где краску царапают: у ручек, кромок дверец, винтов.
2. **Оси.** Маска кладётся в метрах по главной оси грани:
   - фасад — по x и z;
   - бок — по y и z;
   - пол и верх — по двум горизонтальным осям.
3. **Плитка.** Первая укладка — 0,6 м на плитку. Вторая — 0,75 м, повёрнута на четверть оборота и сдвинута на (0,37; 0,61) м.
4. **Уменьшение.** Перед укладкой маска уменьшается усреднением блоков 2 × 2, 4 × 4 и так далее. Уменьшать, пока пиксель маски остаётся хотя бы вдвое мельче текселя атласа.
5. **Ячейки без повтора.** Маска раскладывается ячейками размером в плитку. У каждой ячейки свой случайный сдвиг и поворот на 0, 90, 180 или 270°.
   - Случайное число ячейки — дробная часть |sin(номер_u · 127,1 + номер_v · 311,7 + зерно · 74,7) · 43758,5453|.
   - Сеток две, вторая сдвинута на полъячейки. Они смешиваются «шатром» от середины ячейки, так что границы ячеек не видны.
   - Зерно первой укладки 3,7, второй — 8,2.
6. **Чтение по текселю.** Маска читается по всему текселю: среднее 3 × 3 точек через треть текселя.
7. **Нормировка.** Значения переводятся в 0…1 по процентилям: 60-й процентиль → 0, 99,5-й → 1.

Следы — у краёв фасадов. Середина дверцы чистая.

## Проверка

- Плитка 3 × 3: шва нет, царапины не выстраиваются в сетку.
- Около четверти площади несёт царапины. Большинство бледно-серые, яркие реже.
- Сколов, пятен и грязи нет. Если генерация дала пятна шире 4 пикселей, перегенерировать или убрать их.

## Подводные камни

- Пятна и сколы при ужатии до текселя читаются серыми точками. Поэтому в исключениях промта — chips, scuffs, blotches, grime. Это урок `weathering`.
- Маска нужна бесшовной по обеим осям. Иначе ячейки укладки покажут шов внутри каждой плитки.
