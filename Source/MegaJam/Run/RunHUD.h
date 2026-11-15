// Экранный интерфейс серого прототипа: карман и вещь в руке, здоровье, подсказка, сообщение, блокнот, осмотр.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/HUD.h"
#include "RunHUD.generated.h"

class ARunDirector;
class UFont;
class UTexture2D;

UCLASS()
class MEGAJAM_API ARunHUD : public AHUD
{
	GENERATED_BODY()

public:
	virtual void DrawHUD() override;

private:
	TWeakObjectPtr<ARunDirector> Director;
	void Centered(const FString& Text, float Y, const FLinearColor& Color, float Scale);
	/** Меню на Tab: разворот блокнота с закладками записок, справа — записки, скафандр, карман. */
	void DrawMenu(ARunDirector& D, float S);
	/** Разворот блокнота: лист из карточки ui/notebook-page, записи по порядку, листается. Возвращает строку о страницах. */
	FString DrawNotebook(ARunDirector& D, float S, float X0, float Y0, float W, float H);

	/** Здоровье с задержкой: светлый хвост полосы показывает, сколько отняло последнее попадание. */
	float LagHealth = 100.f;

	/** Насколько открыто меню на Tab (0–1): фон темнеет и расплывается плавно, по реальному времени — мир на паузе. */
	float MenuBlend = 0.f;
	/** Затемнение под меню: ровный слой, к краям плотнее. */
	void DrawShade(float Alpha);

	UPROPERTY()
	TObjectPtr<UTexture2D> PageTexture;
	bool bPageLoaded = false;

	/** Свои шрифты вместо Roboto движка (решение автора 15.11): технический Chakra Petch — экран, рукописный Kalam —
	 *  блокнот. Файлы .ttf лежат в Content/Fonts и читаются напрямую (исходники и лицензии OFL — SourceArt/ui/fonts).
	 *  Нет файла — шрифт движка. */
	UPROPERTY()
	TObjectPtr<UFont> HudFont;
	UPROPERTY()
	TObjectPtr<UFont> HandFont;
	bool bFontsLoaded = false;
	UFont* Hud();
	UFont* Hand();
};
