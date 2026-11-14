// Экранный интерфейс серого прототипа: карман и вещь в руке, здоровье, подсказка, сообщение, блокнот, осмотр.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/HUD.h"
#include "RunHUD.generated.h"

class ARunDirector;
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
	/** Разворот блокнота: лист из карточки ui/notebook-page, записи по порядку, листается. */
	void DrawNotebook(ARunDirector& D, float S);

	/** Здоровье с задержкой: светлый хвост полосы показывает, сколько отняло последнее попадание. */
	float LagHealth = 100.f;

	UPROPERTY()
	TObjectPtr<UTexture2D> PageTexture;
	bool bPageLoaded = false;
};
