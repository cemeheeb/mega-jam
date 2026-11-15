// Экран главного меню поверх заставки: пункты, справа от них логотип игры (/Game/UI/T_Logo), подсказка, затемнение.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/HUD.h"
#include "../Video/VideoMenu.h"
#include "MenuHUD.generated.h"

class AMenuDirector;
class UTexture2D;
class UTextureRenderTarget2D;
class UFont;

UCLASS()
class MEGAJAM_API AMenuHUD : public AHUD
{
	GENERATED_BODY()

public:
	virtual void DrawHUD() override;
	/** Пункт под курсором мыши или −1 (по прямоугольникам, нарисованным в прошлом кадре). */
	int32 ItemUnderMouse() const;
	/** Строка настроек видео под мышью и что сделает щелчок: −1 / +1 — левая / правая половина значения, 0 — название. */
	bool VideoUnderMouse(int32& Row, int32& Step) const;

private:
	TWeakObjectPtr<AMenuDirector> Director;
	TArray<FBox2D> ItemBoxes;
	FVector2D LastMouse = FVector2D(-1.f, -1.f);
	/** Плавное выделение пунктов: 0..1 на каждый. */
	TArray<float> Glow;
	/** Логотип PERIBOTHRON: белые буквы на прозрачном (SourceArt/ui/logo, tools/ue/import_ui.py). */
	UPROPERTY()
	TObjectPtr<UTexture2D> Logo;
	bool bLogoLoaded = false;
	/**
	 * Слой меню: пункты, логотип, название и подсказка рисуются сюда, а не сразу на экран. На экран слой
	 * складывается трижды — красным, зелёным и синим — в разном масштабе вокруг линзы (AMenuDirector::GetLens):
	 * та же хроматическая аберрация, что материал M_MenuLens даёт сцене.
	 */
	UPROPERTY(Transient)
	TObjectPtr<UTextureRenderTarget2D> Layer;
	/** Панель настроек видео (FVideoMenu::Draw) — шрифтом экрана игры Chakra Petch; где строки — для мыши. */
	UPROPERTY()
	TObjectPtr<UFont> VideoFont;
	bool bVideoFontLoaded = false;
	FVideoMenu::FLayout VideoLayout;
	float VideoU = 1.f;
	/** Снимки меню для проверки (-MenuShot): сколько уже сделано. */
	int32 MenuShots = 0;

	// титры концовки (AMenuDirector::GetCredits): стоят в пространстве, буквы слева направо, заслонённые кораблём не рисуются
	void DrawCredits(const AMenuDirector* D, float S);
	void DrawReveal(const FString& Text, FVector2D At, float Size, FName Face, int32 Spacing, const FLinearColor& Color,
		float Raster, float Age, float Life, const AMenuDirector* D, float Depth);
	float CharWidth(const struct FSlateFontInfo& Info, const FString& Str);
	TMap<FString, float> CharWidths;
};
