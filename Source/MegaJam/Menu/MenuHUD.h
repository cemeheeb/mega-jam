// Экран главного меню поверх заставки: пункты, справа от них логотип игры (/Game/UI/T_Logo), подсказка, затемнение.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/HUD.h"
#include "MenuHUD.generated.h"

class AMenuDirector;
class UTexture2D;
class UTextureRenderTarget2D;

UCLASS()
class MEGAJAM_API AMenuHUD : public AHUD
{
	GENERATED_BODY()

public:
	virtual void DrawHUD() override;
	/** Пункт под курсором мыши или −1 (по прямоугольникам, нарисованным в прошлом кадре). */
	int32 ItemUnderMouse() const;

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
	/** Снимки меню для проверки (-MenuShot): сколько уже сделано. */
	int32 MenuShots = 0;
};
