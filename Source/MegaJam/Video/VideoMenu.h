// Настройки видео (просьба автора 15.11, вечер): одна модель и одна отрисовка для главного меню и меню на Tab.
// Там же переключатель режима обучения (ARunDirector::IsTrainingOn, план интерфейса 15.11).
// Значения живут в UGameUserSettings (GameUserSettings.ini у игрока), яркость — там же, своим ключом.
// Каждое изменение применяется и сохраняется сразу: кнопки «Применить» нет. Управление — клавиши, в главном меню
// ещё и мышь (строки отдаёт Draw).

#pragma once

#include "CoreMinimal.h"
#include "Templates/Function.h"

class UCanvas;
class UFont;

namespace MegaJamUI
{
	/** Шрифт из файла Content/Fonts: буквы рисует кэш Slate, чёткие при любом масштабе. Нет файла — nullptr. */
	MEGAJAM_API UFont* LoadFileFont(UObject* Outer, const TCHAR* File, int32 Size);
}

class MEGAJAM_API FVideoMenu
{
public:
	enum ERow : int32 { Quality, Scale, Mode, Resolution, VSync, FrameLimit, Brightness, Training, Detect, Back, NumRows };

	/** Перечитать значения и список разрешений экрана; выделение — на первую строку. */
	void Open();
	void Move(int32 Step);
	void Select(int32 Row);
	/** Влево / вправо: сменить значение выделенной строки. */
	void Change(int32 Step);
	/** Enter: на «Back» возвращает true (закрыть), на «Detect» — замер машины и подбор качества. */
	bool Activate();

	int32 GetSelected() const { return Selected; }
	static FString Label(int32 Row);
	FString Value(int32 Row) const;
	bool IsEnabled(int32 Row) const;
	/** Строки-полосы (масштаб, яркость): заполнение 0–1; у остальных −1. */
	float Fill(int32 Row) const;
	const FString& GetNote() const { return Note; }

	/** Поправка экспозиции от яркости, ступени (−1…+1). Читают ведущие забега и меню. */
	static float GetBrightness();

	/** Что нарисовано: строки (для мыши) и середина колонки значений — левее неё щелчок уменьшает, правее увеличивает. */
	struct FLayout
	{
		TArray<FBox2D> Rows;
		float ValueLeft = 0.f;
		float ValueMid = 0.f;
	};
	/**
	 * Панель настроек на холсте: X, Y — левый верхний угол, W — ширина, U — масштаб (высота экрана / 720).
	 * Alpha — поправка прозрачности (слою главного меню нужна своя), Font — шрифт экрана. Возвращает высоту панели.
	 */
	float Draw(UCanvas* Canvas, UFont* Font, float X, float Y, float W, float U, TFunctionRef<float(float)> Alpha, FLayout* Out = nullptr) const;

private:
	int32 Selected = 0;
	TArray<FIntPoint> Resolutions;
	FString Note;
	static int32 BrightnessStep();
	void ApplyAndSave(bool bResolution);
};
