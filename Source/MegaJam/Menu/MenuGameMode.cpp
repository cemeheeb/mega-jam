#include "MenuGameMode.h"

#include "MenuHUD.h"

AMenuGameMode::AMenuGameMode()
{
	DefaultPawnClass = nullptr;     // в меню некем ходить: вид даёт камера AMenuDirector
	HUDClass = AMenuHUD::StaticClass();
}
