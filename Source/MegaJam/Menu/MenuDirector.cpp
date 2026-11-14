#include "MenuDirector.h"

#include "MenuHUD.h"
#include "Camera/CameraComponent.h"
#include "Components/DirectionalLightComponent.h"
#include "Components/InputComponent.h"
#include "Components/PostProcessComponent.h"
#include "Components/SkyLightComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/StaticMesh.h"
#include "GameFramework/PlayerController.h"
#include "Kismet/GameplayStatics.h"
#include "Kismet/KismetSystemLibrary.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "Materials/MaterialInterface.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"

DEFINE_LOG_CATEGORY_STATIC(LogMenu, Log, All);

namespace MenuAssets
{
	// Сфера движка радиусом 50 см; масштаб SkyScale делает из неё небо в 10 км вокруг камеры.
	const TCHAR* SkySphere = TEXT("/Engine/BasicShapes/Sphere.Sphere");
	const TCHAR* SkyMaterial = TEXT("/Game/Game/Menu/M_BlackHole.M_BlackHole");
	const TCHAR* Ship = TEXT("/Game/Game/Menu/SM_MenuShip.SM_MenuShip");
	constexpr float SkyScale = 20000.f;
	constexpr float FadeIn = 2.5f;      // с
	constexpr float FadeOut = 0.9f;     // с
}

FString AMenuDirector::ItemName(int32 Item)
{
	return Item == ItemNewGame ? TEXT("NEW GAME") : TEXT("QUIT");
}

AMenuDirector::AMenuDirector()
{
	PrimaryActorTick.bCanEverTick = true;

	Root = CreateDefaultSubobject<USceneComponent>(TEXT("Root"));
	RootComponent = Root;

	Camera = CreateDefaultSubobject<UCameraComponent>(TEXT("Camera"));
	Camera->SetupAttachment(Root);
	Camera->SetFieldOfView(55.f);
	Camera->bConstrainAspectRatio = false;

	Sky = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("Sky"));
	Sky->SetupAttachment(Root);
	Sky->SetRelativeScale3D(FVector(MenuAssets::SkyScale));
	Sky->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	Sky->SetCastShadow(false);
	Sky->bAffectDistanceFieldLighting = false;
	Sky->bReceivesDecals = false;
	Sky->SetMobility(EComponentMobility::Movable);

	ShipPivot = CreateDefaultSubobject<USceneComponent>(TEXT("ShipPivot"));
	ShipPivot->SetupAttachment(Root);
	ShipPivot->SetMobility(EComponentMobility::Movable);

	Ship = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("Ship"));
	Ship->SetupAttachment(ShipPivot);
	Ship->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	Ship->SetMobility(EComponentMobility::Movable);

	// Главный свет — сбоку, с резкими тенями (малый угловой размер источника) и контактными тенями на мелких деталях;
	// контровой — тёплый от диска из-за корабля, обводит край силуэта. Спереди корабль не подсвечивается ничем.
	KeyLight = CreateDefaultSubobject<UDirectionalLightComponent>(TEXT("KeyLight"));
	KeyLight->SetupAttachment(Root);
	KeyLight->SetMobility(EComponentMobility::Movable);
	KeyLight->SetLightColor(FLinearColor(1.f, 0.84f, 0.66f));
	KeyLight->LightSourceAngle = 0.25f;
	KeyLight->ContactShadowLength = 0.05f;
	KeyLight->ForwardShadingPriority = 1;   // два направленных света: главный — этот (иначе движок пишет предупреждение)

	RimLight = CreateDefaultSubobject<UDirectionalLightComponent>(TEXT("RimLight"));
	RimLight->SetupAttachment(Root);
	RimLight->SetMobility(EComponentMobility::Movable);
	RimLight->SetLightColor(FLinearColor(1.f, 0.72f, 0.45f));
	RimLight->SetCastShadows(false);
	RimLight->ForwardShadingPriority = 0;

	// Окружающий свет — снимок неба: ближе SkyDistanceThreshold (корабль) в снимок не попадает.
	Ambient = CreateDefaultSubobject<USkyLightComponent>(TEXT("Ambient"));
	Ambient->SetupAttachment(Root);
	Ambient->SetMobility(EComponentMobility::Movable);
	Ambient->SourceType = ESkyLightSourceType::SLS_CapturedScene;
	Ambient->SkyDistanceThreshold = 300000.f;

	Post = CreateDefaultSubobject<UPostProcessComponent>(TEXT("Post"));
	Post->SetupAttachment(Root);
	Post->bUnbound = true;
}

FVector AMenuDirector::HoleDirection() const
{
	return GetActorRotation().RotateVector(FRotator(HolePitch, HoleYaw, 0.f).Vector());
}

void AMenuDirector::OnConstruction(const FTransform& Transform)
{
	Super::OnConstruction(Transform);
	ApplyLook();
	PlaceShip();
}

void AMenuDirector::ApplyLook()
{
	if (!Sky->GetStaticMesh())
	{
		Sky->SetStaticMesh(LoadObject<UStaticMesh>(nullptr, MenuAssets::SkySphere));
	}
	if (!Ship->GetStaticMesh())
	{
		Ship->SetStaticMesh(LoadObject<UStaticMesh>(nullptr, MenuAssets::Ship));
	}
	if (!SkyMaterial)
	{
		if (UMaterialInterface* Base = LoadObject<UMaterialInterface>(nullptr, MenuAssets::SkyMaterial))
		{
			SkyMaterial = UMaterialInstanceDynamic::Create(Base, this);
			Sky->SetMaterial(0, SkyMaterial);
		}
	}
	const FVector Hole = HoleDirection();
	if (SkyMaterial)
	{
		SkyMaterial->SetVectorParameterValue(TEXT("Hole"), FLinearColor(Hole.X, Hole.Y, Hole.Z, HoleDistance));
		SkyMaterial->SetVectorParameterValue(TEXT("Disk"), FLinearColor(DiskElevation, DiskRoll, DiskInner, DiskOuter));
		SkyMaterial->SetVectorParameterValue(TEXT("Look"), FLinearColor(DiskBrightness, StarBrightness, DiskSpeed, DiskTemperature));
	}
	// направленный свет поворачивают туда, куда он светит: от источника
	const FVector KeyFrom = GetActorRotation().RotateVector(FRotator(KeyPitch, KeyYaw, 0.f).Vector());
	KeyLight->SetWorldRotation((-KeyFrom).Rotation());
	KeyLight->SetIntensity(KeyLux);
	RimLight->SetWorldRotation((-Hole).Rotation());     // свет диска идёт из направления дыры
	RimLight->SetIntensity(RimLux);
	Ambient->SetIntensity(AmbientIntensity);

	FPostProcessSettings& S = Post->Settings;
	S.bOverride_AutoExposureMethod = true;
	S.AutoExposureMethod = EAutoExposureMethod::AEM_Manual;
	S.bOverride_AutoExposureApplyPhysicalCameraExposure = true;
	S.AutoExposureApplyPhysicalCameraExposure = false;
	S.bOverride_AutoExposureBias = true;
	S.AutoExposureBias = ExposureBias;
	S.bOverride_BloomIntensity = true;
	S.BloomIntensity = 1.4f;
	S.bOverride_BloomThreshold = true;
	S.BloomThreshold = 1.0f;
	S.bOverride_VignetteIntensity = true;
	S.VignetteIntensity = 0.55f;
	S.bOverride_SceneFringeIntensity = true;
	S.SceneFringeIntensity = 0.35f;
	S.bOverride_FilmGrainIntensity = true;
	S.FilmGrainIntensity = 0.12f;
	S.bOverride_LensFlareIntensity = true;
	S.LensFlareIntensity = 0.25f;
	S.bOverride_MotionBlurAmount = true;
	S.MotionBlurAmount = 0.f;
}

void AMenuDirector::PlaceShip()
{
	ShipPivot->SetRelativeLocation(ShipOffset + FVector(0.f, 0.f, FMath::Sin(Clock * 0.35f) * BobCm));
	ShipPivot->SetRelativeRotation(FRotator(ShipStart.Pitch, ShipStart.Yaw + SpinDegPerSec * Clock,
		ShipStart.Roll + RollDegPerSec * Clock));
}

void AMenuDirector::BeginPlay()
{
	Super::BeginPlay();
	ApplyLook();
	PlaceShip();
	Ambient->RecaptureSky();
	bSelfTest = FParse::Param(FCommandLine::Get(), TEXT("MenuSelfTest"));

	APlayerController* PC = UGameplayStatics::GetPlayerController(this, 0);
	if (!PC)
	{
		return;
	}
	PC->SetViewTarget(this);
	PC->ClientSetHUD(AMenuHUD::StaticClass());
	PC->SetIgnoreMoveInput(true);
	PC->SetIgnoreLookInput(true);
	PC->bShowMouseCursor = true;
	FInputModeGameAndUI Mode;
	Mode.SetHideCursorDuringCapture(false);
	Mode.SetLockMouseToViewportBehavior(EMouseLockMode::DoNotLock);
	PC->SetInputMode(Mode);

	EnableInput(PC);
	for (const FKey& Key : {EKeys::Up, EKeys::W})
	{
		InputComponent->BindKey(Key, IE_Pressed, this, &AMenuDirector::OnUp);
	}
	for (const FKey& Key : {EKeys::Down, EKeys::S})
	{
		InputComponent->BindKey(Key, IE_Pressed, this, &AMenuDirector::OnDown);
	}
	for (const FKey& Key : {EKeys::Enter, EKeys::SpaceBar, EKeys::E})
	{
		InputComponent->BindKey(Key, IE_Pressed, this, &AMenuDirector::OnAccept);
	}
	InputComponent->BindKey(EKeys::LeftMouseButton, IE_Pressed, this, &AMenuDirector::OnClick);
	InputComponent->BindKey(EKeys::Escape, IE_Pressed, this, &AMenuDirector::OnBack);
	UE_LOG(LogMenu, Log, TEXT("Menu: ready"));
}

void AMenuDirector::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);
	Clock += DeltaSeconds;
	PlaceShip();
	// лёгкий дрейф камеры: корабль чуть смещается на фоне неба (небо бесконечно далеко и не смещается)
	const float D = CameraDriftCm;
	Camera->SetRelativeLocation(FVector(FMath::Sin(Clock * 0.11f) * D, FMath::Sin(Clock * 0.07f + 1.f) * D,
		FMath::Sin(Clock * 0.09f + 2.f) * D * 0.5f));

	if (APlayerController* PC = UGameplayStatics::GetPlayerController(this, 0))
	{
		if (PC->GetViewTarget() != this)
		{
			PC->SetViewTarget(this);   // если режим игры всё же дал игроку пешку, вид остаётся за меню
		}
	}
	if (bSelfTest && Chosen < 0 && Clock > 3.f)
	{
		UE_LOG(LogMenu, Log, TEXT("Menu: self test chooses %s"), *ItemName(ItemNewGame));
		Activate(ItemNewGame);
	}
	if (LeaveAt >= 0.f && Clock >= LeaveAt)
	{
		LeaveAt = -2.f;     // не повторять
		Leave();
	}
}

float AMenuDirector::GetFade() const
{
	float Fade = 1.f - FMath::Clamp(Clock / MenuAssets::FadeIn, 0.f, 1.f);
	if (Chosen >= 0)
	{
		const float Start = (LeaveAt >= 0.f ? LeaveAt : Clock) - MenuAssets::FadeOut;
		Fade = FMath::Max(Fade, LeaveAt == -2.f ? 1.f : FMath::Clamp((Clock - Start) / MenuAssets::FadeOut, 0.f, 1.f));
	}
	return Fade * Fade * (3.f - 2.f * Fade);
}

void AMenuDirector::Hover(int32 Item)
{
	if (Chosen < 0 && Item >= 0 && Item < ItemCount)
	{
		Selected = Item;
	}
}

void AMenuDirector::OnUp()
{
	if (Chosen < 0)
	{
		Selected = (Selected + ItemCount - 1) % ItemCount;
	}
}

void AMenuDirector::OnDown()
{
	if (Chosen < 0)
	{
		Selected = (Selected + 1) % ItemCount;
	}
}

void AMenuDirector::OnAccept()
{
	Activate(Selected);
}

void AMenuDirector::OnClick()
{
	const APlayerController* PC = UGameplayStatics::GetPlayerController(this, 0);
	const AMenuHUD* Hud = PC ? Cast<AMenuHUD>(PC->GetHUD()) : nullptr;
	const int32 Item = Hud ? Hud->ItemUnderMouse() : -1;
	if (Item >= 0)
	{
		Activate(Item);
	}
}

void AMenuDirector::OnBack()
{
	if (Chosen < 0)
	{
		Selected = ItemQuit;
	}
}

void AMenuDirector::Activate(int32 Item)
{
	if (Chosen >= 0 || Clock < 0.6f)
	{
		return;
	}
	Chosen = Item;
	Selected = Item;
	LeaveAt = Clock + MenuAssets::FadeOut;
	UE_LOG(LogMenu, Log, TEXT("Menu: %s"), *ItemName(Item));
}

void AMenuDirector::Leave()
{
	APlayerController* PC = UGameplayStatics::GetPlayerController(this, 0);
	if (PC)
	{
		// режим ввода живёт в окне игры и переживает смену уровня: вернуть обычный
		PC->bShowMouseCursor = false;
		PC->SetInputMode(FInputModeGameOnly());
	}
	if (Chosen == ItemNewGame)
	{
		UE_LOG(LogMenu, Log, TEXT("Menu: open %s"), *GameLevel.ToString());
		UGameplayStatics::OpenLevel(this, GameLevel);
	}
	else
	{
		UKismetSystemLibrary::QuitGame(this, PC, EQuitPreference::Quit, false);
	}
}
