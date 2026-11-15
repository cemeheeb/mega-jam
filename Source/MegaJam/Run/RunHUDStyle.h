// Общий вид экрана (план интерфейса 15.11, решено автором): панели со срезанными углами и тонкой кромкой, угловые
// скобки, мягкое свечение, клавиши-кнопки вместо «[E]». Всё рисуется кодом на холсте, без текстур.
// Палитра: бирюзовый — основной, оранжевый — второй, красный — опасность. Без сканлайнов и зерна (DESIGN.md).

#pragma once

#include "CoreMinimal.h"

class UCanvas;
class UFont;

namespace RunStyle
{
	inline const FLinearColor Teal(0.37f, 0.78f, 0.79f);
	inline const FLinearColor Orange(0.95f, 0.42f, 0.13f);
	inline const FLinearColor Danger(0.95f, 0.3f, 0.22f);
	/** Заливка панелей: почти чёрный с синевой. */
	inline const FLinearColor Fill(0.012f, 0.03f, 0.045f, 0.88f);

	inline FLinearColor A(FLinearColor C, float Alpha)
	{
		C.A = Alpha;
		return C;
	}

	MEGAJAM_API void Rect(UCanvas* C, float X, float Y, float W, float H, const FLinearColor& Color);
	/** Рамка из четырёх полос толщиной T внутрь прямоугольника. */
	MEGAJAM_API void Frame(UCanvas* C, float X, float Y, float W, float H, float T, const FLinearColor& Color);
	/** Залитый выпуклый многоугольник. */
	MEGAJAM_API void Poly(UCanvas* C, TArrayView<const FVector2D> Pts, const FLinearColor& Color);
	/** Замкнутая ломаная. */
	MEGAJAM_API void Outline(UCanvas* C, TArrayView<const FVector2D> Pts, const FLinearColor& Color, float Thick);
	/** Панель: срезаны левый верхний и правый нижний углы на Cut; Edge.A = 0 — без кромки. */
	MEGAJAM_API void Panel(UCanvas* C, float X, float Y, float W, float H, float Cut, const FLinearColor& FillColor, const FLinearColor& Edge, float EdgeThick);
	/** Угловые скобки вокруг прямоугольника: уголки длиной Len. */
	MEGAJAM_API void Brackets(UCanvas* C, float X, float Y, float W, float H, float Len, float Thick, const FLinearColor& Color);
	/** Мягкое свечение вокруг прямоугольника: три расходящиеся рамки. */
	MEGAJAM_API void Glow(UCanvas* C, float X, float Y, float W, float H, float U, const FLinearColor& Color);
	/** Пунктирная рамка — пустая ячейка. */
	MEGAJAM_API void Dashed(UCanvas* C, float X, float Y, float W, float H, float Dash, float Thick, const FLinearColor& Color);

	/** Текст; Align: 0 — от X, 0.5 — серединой в X, 1 — правым краем в X. Возвращает ширину. */
	MEGAJAM_API float Text(UCanvas* C, UFont* Font, const FString& Str, float X, float Y, float Scale, const FLinearColor& Color, float Align = 0.f);
	/**
	 * Строка с клавишами: всё в квадратных скобках ([E], [Tab], [1]-[4]) рисуется кнопкой, остальное — текстом.
	 * Возвращает ширину; bMeasure — только измерить, ничего не рисуя.
	 */
	MEGAJAM_API float Rich(UCanvas* C, UFont* Font, const FString& Str, float X, float Y, float Scale, const FLinearColor& TextColor,
		const FLinearColor& KeyColor, bool bMeasure = false);
	/** То же серединой в X. */
	MEGAJAM_API float RichCentered(UCanvas* C, UFont* Font, const FString& Str, float X, float Y, float Scale, const FLinearColor& TextColor,
		const FLinearColor& KeyColor);
}
