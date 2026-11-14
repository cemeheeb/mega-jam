// Экран главного меню поверх заставки: пункты, справа от них логотип игры (/Game/UI/T_Logo), подсказка, затемнение.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/HUD.h"
#include "MenuHUD.generated.h"

class AMenuDirector;
class UTexture2D;

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
	/** Номера кусков края букв (LogoDust.h), из них рождается поток пыли; пересчитывается, когда порог сдвинулся. */
	TArray<int32> DustEdge;
	float DustEdgeAt = -1.f;
	/** Где дыра на экране и радиус её тени по расчёту (для журнала снимков). */
	FVector2D DustCenter = FVector2D::ZeroVector;
	float DustRadius = 0.f;
	/** Кольцо, к которому слетается пыль, в радиусах расчётной тени (подобрано по кадру меню). */
	static constexpr float RingScale = 1.2f;
	/** Снимки меню для проверки (-MenuShot): сколько уже сделано. */
	int32 MenuShots = 0;

	/**
	 * Логотип с последними буквами, которые затягивает в чёрную дыру. Буквы левее разреза — одна плитка текстуры,
	 * последние три — куски LogoDust.h. Съеденное выше порога исчезает, рядом с порогом висят оторванные куски,
	 * с края идёт поток пикселей по спирали в плоскости диска; у края тени они краснеют, тормозят и гаснут.
	 * Порог ползёт к пределу как 1 / (1 + t / 60 с): слово не исчезает никогда (для смотрящего со стороны
	 * падающее в дыру не пересекает горизонт).
	 */
	void DrawLogo(const AMenuDirector* D, FVector2D Pos, FVector2D Size, float Appear, float Clock);
};
