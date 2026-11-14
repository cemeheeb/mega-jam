// Экран главного меню поверх заставки: название игры (когда оно будет), пункты, подсказка, затемнение.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/HUD.h"
#include "MenuHUD.generated.h"

class AMenuDirector;

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
};
