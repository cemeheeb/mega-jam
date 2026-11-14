// Режим игры уровня Lvl_Menu: без персонажа, экран — AMenuHUD. Ставится уровню в World Settings (tools/ue/build_menu.py).

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/GameModeBase.h"
#include "MenuGameMode.generated.h"

UCLASS()
class MEGAJAM_API AMenuGameMode : public AGameModeBase
{
	GENERATED_BODY()

public:
	AMenuGameMode();
};
