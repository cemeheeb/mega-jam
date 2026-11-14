// Главное меню: корабль медленно поворачивается на фоне чёрной дыры.
// Небо — сфера вокруг камеры с материалом M_BlackHole (tools/ue/shaders/BlackHole.hlsl): лучи от камеры гнутся
// у дыры по Шварцшильду, диск аккреции светится с доплеровским сдвигом, звёзды и Млечный Путь искажены линзой.
// Ведущий стоит на уровне Lvl_Menu (tools/ue/build_menu.py), пункты рисует AMenuHUD.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "MenuDirector.generated.h"

class UCameraComponent;
class UStaticMeshComponent;
class UDirectionalLightComponent;
class USkyLightComponent;
class UPostProcessComponent;
class UMaterialInstanceDynamic;

UCLASS()
class MEGAJAM_API AMenuDirector : public AActor
{
	GENERATED_BODY()

public:
	AMenuDirector();
	virtual void OnConstruction(const FTransform& Transform) override;
	virtual void BeginPlay() override;
	virtual void Tick(float DeltaSeconds) override;

	enum : int32 { ItemNewGame = 0, ItemQuit = 1, ItemCount = 2 };
	static FString ItemName(int32 Item);
	int32 GetSelected() const { return Selected; }
	/** Мышь навела на пункт (экран меню проверяет это каждый кадр, пока мышь двигается). */
	void Hover(int32 Item);
	bool IsLeaving() const { return LeaveAt >= 0.f; }
	/** Затемнение экрана 0..1: появление в начале и уход в игру или из игры. */
	float GetFade() const;
	/** Сколько секунд показывается меню: пункты проявляются не сразу. */
	float GetClock() const { return Clock; }
	const FString& GetTitle() const { return GameTitle; }

	/** Название игры над пунктами. Пока автор его не выбрал (DESIGN.md §12), строки нет. */
	UPROPERTY(EditAnywhere, Category = "Menu")
	FString GameTitle;

	UPROPERTY(EditAnywhere, Category = "Menu")
	FName GameLevel = TEXT("Lvl_Game");

	// --- корабль: середина модели, наклон и скорость поворота ---
	UPROPERTY(EditAnywhere, Category = "Menu|Ship")
	FVector ShipOffset = FVector(13000.f, -3700.f, 300.f);
	UPROPERTY(EditAnywhere, Category = "Menu|Ship")
	FRotator ShipStart = FRotator(14.f, 35.f, 0.f);
	UPROPERTY(EditAnywhere, Category = "Menu|Ship")
	float SpinDegPerSec = 3.f;
	UPROPERTY(EditAnywhere, Category = "Menu|Ship")
	float RollDegPerSec = 1.2f;
	UPROPERTY(EditAnywhere, Category = "Menu|Ship")
	float BobCm = 60.f;

	// --- чёрная дыра: где она относительно взгляда камеры, расстояние до неё и диск (радиусы в радиусах горизонта) ---
	UPROPERTY(EditAnywhere, Category = "Menu|Black Hole")
	float HoleYaw = 9.f;
	UPROPERTY(EditAnywhere, Category = "Menu|Black Hole")
	float HolePitch = 3.f;
	UPROPERTY(EditAnywhere, Category = "Menu|Black Hole")
	float HoleDistance = 30.f;
	/** Насколько камера выше плоскости диска, градусы. */
	UPROPERTY(EditAnywhere, Category = "Menu|Black Hole")
	float DiskElevation = 7.f;
	/** Наклон диска на экране, градусы. */
	UPROPERTY(EditAnywhere, Category = "Menu|Black Hole")
	float DiskRoll = -11.f;
	UPROPERTY(EditAnywhere, Category = "Menu|Black Hole")
	float DiskInner = 3.f;
	UPROPERTY(EditAnywhere, Category = "Menu|Black Hole")
	float DiskOuter = 13.f;
	UPROPERTY(EditAnywhere, Category = "Menu|Black Hole")
	float DiskBrightness = 3.f;
	UPROPERTY(EditAnywhere, Category = "Menu|Black Hole")
	float StarBrightness = 1.f;
	/** Множитель времени для вращения диска: 1 — около оборота внутреннего края за 10 с. */
	UPROPERTY(EditAnywhere, Category = "Menu|Black Hole")
	float DiskSpeed = 1.f;
	/** Температура самого горячего места диска, К: цвет от оранжевого до бело-голубого. */
	UPROPERTY(EditAnywhere, Category = "Menu|Black Hole")
	float DiskTemperature = 4600.f;

	// --- свет и кадр ---
	// Автор, 14.11: «хочу увидеть контрастные, глубокие, почти черные тени». Поэтому света со стороны камеры нет:
	// главный — сбоку справа сверху (со стороны диска), контровой — от диска из-за корабля, окружающий почти нулевой.
	/** Главный свет, люкс. */
	UPROPERTY(EditAnywhere, Category = "Menu|Look")
	float KeyLux = 7.f;
	/** Откуда светит главный свет (в осях ведущего: X — вперёд от камеры, Y — вправо), градусы по горизонтали. */
	UPROPERTY(EditAnywhere, Category = "Menu|Look")
	float KeyYaw = 75.f;
	/** Высота главного света над горизонтом, градусы. */
	UPROPERTY(EditAnywhere, Category = "Menu|Look")
	float KeyPitch = 20.f;
	/** Контровой свет от диска (светит из направления дыры), люкс. */
	UPROPERTY(EditAnywhere, Category = "Menu|Look")
	float RimLux = 8.f;
	/** Окружающий свет от снимка неба: чем меньше, тем чернее тени. */
	UPROPERTY(EditAnywhere, Category = "Menu|Look")
	float AmbientIntensity = 0.06f;
	UPROPERTY(EditAnywhere, Category = "Menu|Look")
	float ExposureBias = 0.f;
	UPROPERTY(EditAnywhere, Category = "Menu|Look")
	float CameraDriftCm = 120.f;

private:
	UPROPERTY(VisibleAnywhere) TObjectPtr<USceneComponent> Root;
	UPROPERTY(VisibleAnywhere) TObjectPtr<UCameraComponent> Camera;
	UPROPERTY(VisibleAnywhere) TObjectPtr<UStaticMeshComponent> Sky;
	UPROPERTY(VisibleAnywhere) TObjectPtr<USceneComponent> ShipPivot;
	UPROPERTY(VisibleAnywhere) TObjectPtr<UStaticMeshComponent> Ship;
	UPROPERTY(VisibleAnywhere) TObjectPtr<UDirectionalLightComponent> KeyLight;
	UPROPERTY(VisibleAnywhere) TObjectPtr<UDirectionalLightComponent> RimLight;
	UPROPERTY(VisibleAnywhere) TObjectPtr<USkyLightComponent> Ambient;
	UPROPERTY(VisibleAnywhere) TObjectPtr<UPostProcessComponent> Post;
	UPROPERTY(Transient) TObjectPtr<UMaterialInstanceDynamic> SkyMaterial;

	/** Меши и материал по путям /Game/Game/Menu, параметры неба, свет и постобработка — из свойств выше. */
	void ApplyLook();
	void PlaceShip();
	FVector HoleDirection() const;

	void OnUp();
	void OnDown();
	void OnAccept();
	void OnClick();
	void OnBack();
	void Activate(int32 Item);
	void Leave();

	float Clock = 0.f;
	int32 Selected = ItemNewGame;
	int32 Chosen = -1;
	float LeaveAt = -1.f;
	bool bSelfTest = false;
};
