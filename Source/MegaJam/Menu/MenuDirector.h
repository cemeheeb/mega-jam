// Главное меню: корабль медленно поворачивается на фоне чёрной дыры.
// Небо — сфера вокруг камеры с материалом M_BlackHole (tools/ue/shaders/BlackHole.hlsl): лучи от камеры гнутся
// у дыры по Шварцшильду, диск аккреции светится с доплеровским сдвигом, звёзды и Млечный Путь искажены линзой.
// Ведущий стоит на уровне Lvl_Menu (tools/ue/build_menu.py), пункты рисует AMenuHUD.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "../Video/VideoMenu.h"
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

	enum : int32 { ItemNewGame = 0, ItemSettings = 1, ItemQuit = 2, ItemCount = 3 };
	static FString ItemName(int32 Item);
	int32 GetSelected() const { return Selected; }
	/** Мышь навела на пункт (экран меню проверяет это каждый кадр, пока мышь двигается). */
	void Hover(int32 Item);
	bool IsLeaving() const { return LeaveAt >= 0.f; }
	/** Открыты настройки видео (пункт SETTINGS; просьба автора 15.11, вечер). Та же панель, что в меню на Tab. */
	bool IsVideoOpen() const { return bVideoOpen; }
	const FVideoMenu& GetVideo() const { return Video; }
	/** Мышь над строкой настроек: выделить её. */
	void HoverVideo(int32 Row);
	/** Затемнение экрана 0..1: появление в начале и уход в игру или из игры. */
	float GetFade() const;
	/** Сколько секунд показывается меню: пункты проявляются не сразу. */
	float GetClock() const { return Clock; }
	/** Направление на чёрную дыру в мире. */
	FVector HoleDirection() const;
	/** Середина линзы на экране в долях его ширины и высоты: плавно идёт за мышью (см. LensStrength). */
	FVector2D GetLens() const { return Lens; }
	/**
	 * На сколько пикселей уходит красный канал в точке, отстоящей от линзы на Offset (пиксели; ScreenH — высота экрана).
	 * Синий уходит на столько же в обратную сторону. Та же формула — в материале M_MenuLens (tools/ue/build_menu.py).
	 */
	FVector2D LensShift(const FVector2D& Offset, float ScreenH) const
	{
		const float Len = Offset.Size() / FMath::Max(ScreenH, 1.f) / FMath::Max(LensRadius, 0.01f);
		return Offset * (LensStrength / FMath::Sqrt(1.f + Len * Len));
	}
	const FString& GetTitle() const { return GameTitle; }

	/** Сцена концовки (просьба автора 15.11, ночь): уровень открыт с опцией Ending после победы (или ключ -MenuEnding).
	 *  Корабль у чёрной дыры запускает двигатели и с разгоном идёт от неё на камеру; у камеры она цепляется к нему
	 *  и летит впереди, глядя назад, а неподвижные в пространстве титры (рисует AMenuHUD) уходят за корабль, к дыре. */
	bool IsEnding() const { return bEnding; }
	/** Титр концовки, который сейчас на экране: подпись, имя, точка в пространстве (левый верх имени), высота имени
	 *  в пространстве (см; подпись — треть её), возраст. Титр стоит на месте: уменьшается, потому что камера улетает. */
	struct FCreditView
	{
		FString Caption;
		FString Name;
		FVector At = FVector::ZeroVector;
		float Height = 0.f;
		float Size = 0.f;   // высота имени в момент появления, доля высоты экрана (в этом размере шрифт растрируется)
		float Age = 0.f;
		float Life = 0.f;
	};
	void GetCredits(TArray<FCreditView>& Out) const;
	/** Заслоняет ли корабль точку To при взгляде из From: титр за кораблём не рисуется (буква за буквой). */
	bool IsBehindShip(const FVector& From, const FVector& To) const;
	static constexpr float EndingIgnite = 2.2f;   // с: двигатели загораются
	static constexpr float EndingGo = 3.4f;       // с: корабль трогается
	static constexpr float EndingLength = 29.f;   // с: вся сцена (музыка победы — 30 с)

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

	// --- линза: хроматическая аберрация вокруг курсора (просьба автора 15.11) ---
	// Под курсором картинка чистая; чем дальше от него, тем сильнее расходятся цвета: красный уходит от курсора,
	// синий — к нему. Сцену разводит материал M_MenuLens (tools/ue/build_menu.py), слой меню — AMenuHUD, формула одна.
	// Сдвиг не растёт без конца: его предел — LensStrength * LensRadius высот экрана (0,0035 * 0,7 — около 2,5 px
	// при 1080 строках), иначе при курсоре в дальнем углу мелкие буквы меню расходятся до нечитаемости.
	/** На какую долю расстояния до курсора сдвигаются красный и синий рядом с ним. */
	UPROPERTY(EditAnywhere, Category = "Menu|Lens")
	float LensStrength = 0.0035f;
	/** На каком расстоянии от курсора сдвиг перестаёт расти, в высотах экрана. */
	UPROPERTY(EditAnywhere, Category = "Menu|Lens")
	float LensRadius = 0.7f;
	/** Как быстро линза догоняет мышь: больше — резче. */
	UPROPERTY(EditAnywhere, Category = "Menu|Lens")
	float LensFollow = 5.f;

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
	UPROPERTY(Transient) TObjectPtr<UMaterialInstanceDynamic> LensMaterial;
	UPROPERTY(VisibleAnywhere) TObjectPtr<class UPointLightComponent> EngineLight;
	UPROPERTY(Transient) TObjectPtr<UMaterialInstanceDynamic> ShipGlow;
	bool bEnding = false;
	bool bIgnited = false;
	bool bEndingLeft = false;
	FRotator CamRot = FRotator::ZeroRotator;
	FVector CamDir = FVector::ForwardVector;
	bool bCamInit = false;
	void PlaceShipEnding();
	/** Путь концовки на сейчас (в осях ведущего): где корабль, где камера и сколько она уже пролетела. */
	void EndingPath(FVector& ShipPos, FVector& CamPos, float& CamTravel) const;
	// титры концовки: точка в пространстве и высота имени у каждого (ставятся при появлении), рисует их AMenuHUD
	TArray<FVector> CreditAnchor;
	TArray<float> CreditHeight;
	TArray<bool> CreditPlaced;
	void TickCredits();
	void EndEnding();
	void OnDebugEnding();

	/** Меши и материал по путям /Game/Game/Menu, параметры неба, свет и постобработка — из свойств выше. */
	void ApplyLook();
	void PlaceShip();

	void OnUp();
	void OnDown();
	void OnAccept();
	void OnClick();
	void OnBack();
	void OnLeft();
	void OnRight();
	void Activate(int32 Item);
	void Leave();

	float Clock = 0.f;
	int32 Selected = ItemNewGame;
	int32 Chosen = -1;
	float LeaveAt = -1.f;
	bool bSelfTest = false;
	FVector2D Lens = FVector2D(0.5f, 0.5f);
	FVector2D LensTarget = FVector2D(0.5f, 0.5f);
	/** Проверка без рук: -MenuMouse=0.8,0.3 ставит линзу в это место и не слушает мышь. */
	bool bLensFixed = false;
	FVideoMenu Video;
	bool bVideoOpen = false;
	/** Яркость из настроек, уже применённая к экспозиции сцены меню: её видно сразу, пока двигаешь полосу. */
	float AppliedBrightness = 0.f;
	/** Проверка без рук: -MenuVideo открывает настройки на 3-й секунде (снимки — вместе с -MenuShot). */
	bool bVideoAtStart = false;
};
