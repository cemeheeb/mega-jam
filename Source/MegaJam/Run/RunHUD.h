// Экранный интерфейс серого прототипа: карман, здоровье, подсказка, сообщение, блокнот.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/HUD.h"
#include "RunHUD.generated.h"

class ARunDirector;

UCLASS()
class MEGAJAM_API ARunHUD : public AHUD
{
	GENERATED_BODY()

public:
	virtual void DrawHUD() override;

private:
	TWeakObjectPtr<ARunDirector> Director;
	void Centered(const FString& Text, float Y, const FLinearColor& Color, float Scale);
};
