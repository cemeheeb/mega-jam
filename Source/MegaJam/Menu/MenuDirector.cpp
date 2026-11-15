#include "MenuDirector.h"
#include "../Run/RunAudio.h"

#include "MenuHUD.h"
#include "Camera/CameraComponent.h"
#include "Components/DirectionalLightComponent.h"
#include "Components/InputComponent.h"
#include "Components/PointLightComponent.h"
#include "Engine/GameViewportClient.h"
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

// Концовка (автор, 15.11, ночь): «корабль разгоняется как сейчас в начале, потом когда приближается вплотную к камере,
// камера к нему плавно цепляется и двигается вместе с ним, а титры статично располагаются за камерой, получится эффект
// когда титры будут появляться за кораблем и уходить вдаль перспективной проекцией».
// В осях ведущего (камера смотрит в +X): корабль висит у дыры и идёт прямо от неё. Камера стоит, пока он далеко;
// когда до него остаётся около Follow + 2 Soft, она мягко трогается и дальше держится впереди него на Follow, глядя
// назад — на корабль и дыру. Обе идут вдоль одной прямой, поэтому корабль в кадре стоит, а неподвижное в мире
// уходит к дыре и уменьшается.
namespace MenuEnding
{
	const FVector ShipFrom(24000.f, 1200.f, -150.f);   // где корабль висит до запуска (у дыры, на фоне диска)
	constexpr float Speed = 3000.f;    // см/с: крейсерская скорость (с ней же титры уходят вдаль)
	constexpr float Tau = 3.4f;        // с: разгон — за Tau корабль набирает две трети скорости
	constexpr float Follow = 6000.f;   // см: насколько камера впереди корабля, когда летит с ним (длина корабля 60 м)
	constexpr float Soft = 2000.f;     // см: мягкость сцепки — чем больше, тем раньше и плавнее камера трогается
	constexpr float HoleFar = 1.4f / 50000.f;   // дыра уменьшается: её расстояние растёт на столько за сантиметр пути камеры
}

// Титры: «MegaJam 2026, Unreal Engine, Claude, и в конце Eldar Semeneev», буквы проявляются слева направо, как в
// заставках GTA V. Титр появляется точкой в пространстве там, где в этот миг виден в точке X, Y экрана (доли, левый верх
// имени), на глубине Depth (см) — за кормой корабля; высота имени в этот миг — Size высоты экрана. Дальше он стоит,
// а камера улетает: титр уменьшается и уходит к дыре (чем больше Depth, тем медленнее). Углы чередуются: слева
// вверху, справа внизу (автор: «пусть made with claude будет в другом месте» — не за кораблём). Рисует их экран меню поверх кадра (текстом в сцене он шёл через
// линзу и зерно и не читался — автор); буквы, которые корабль заслоняет, не рисуются.
namespace MenuCredits
{
	struct FCredit
	{
		const TCHAR* Caption;
		const TCHAR* Name;
		float X, Y, Start, Depth;
	};
	// корабль в кадре слева внизу, дыра справа вверху; корма — в 9400 см от камеры
	const FCredit Credits[] = {
		{ TEXT("MADE FOR"), TEXT("MegaJam 2026"), 0.05f, 0.22f, 12.8f, 14500.f },
		{ TEXT("BUILT WITH"), TEXT("Unreal Engine"), 0.52f, 0.78f, 16.4f, 14500.f },
		{ TEXT("MADE WITH"), TEXT("Claude"), 0.06f, 0.24f, 20.f, 14500.f },
		// последний остаётся до конца: дальше остальных, поэтому уходит медленнее
		{ TEXT("CREATED BY"), TEXT("Eldar Semeneev"), 0.50f, 0.78f, 23.6f, 26000.f },
	};
	constexpr float Size = 0.095f;     // высота имени в момент появления, доля высоты экрана
	constexpr float Hold = 4.2f;       // с: сколько титр виден целиком
}

namespace MenuAssets
{
	// Сфера движка радиусом 50 см; масштаб SkyScale делает из неё небо в 10 км вокруг камеры.
	const TCHAR* SkySphere = TEXT("/Engine/BasicShapes/Sphere.Sphere");
	const TCHAR* SkyMaterial = TEXT("/Game/Game/Menu/M_BlackHole.M_BlackHole");
	const TCHAR* Ship = TEXT("/Game/Game/Menu/SM_MenuShip.SM_MenuShip");
	const TCHAR* Lens = TEXT("/Game/Game/Menu/M_MenuLens.M_MenuLens");
	constexpr float SkyScale = 20000.f;
	constexpr float FadeIn = 2.5f;      // с
	constexpr float FadeOut = 0.9f;     // с
}

FString AMenuDirector::ItemName(int32 Item)
{
	return Item == ItemNewGame ? TEXT("NEW GAME") : Item == ItemSettings ? TEXT("SETTINGS") : TEXT("QUIT");
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
	// свет двигателей для концовки: за кормой (нос модели в +X, длина 60 м), до запуска выключен
	EngineLight = CreateDefaultSubobject<UPointLightComponent>(TEXT("EngineLight"));
	EngineLight->SetupAttachment(Ship);
	EngineLight->SetRelativeLocation(FVector(-3400.f, 0.f, 0.f));
	EngineLight->SetMobility(EComponentMobility::Movable);
	EngineLight->SetIntensity(0.f);
	EngineLight->SetAttenuationRadius(14000.f);
	EngineLight->SetLightColor(FLinearColor(0.45f, 0.75f, 1.f));
	EngineLight->SetCastShadows(false);
	EngineLight->SetVisibility(false);

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
	AppliedBrightness = FVideoMenu::GetBrightness();
	S.AutoExposureBias = ExposureBias + AppliedBrightness;   // яркость из настроек видео
	S.bOverride_BloomIntensity = true;
	S.BloomIntensity = 1.4f;
	S.bOverride_BloomThreshold = true;
	S.BloomThreshold = 1.0f;
	S.bOverride_VignetteIntensity = true;
	S.VignetteIntensity = 0.55f;
	// аберрация движка расходится от середины экрана; когда работает линза за мышью, она не нужна
	S.bOverride_SceneFringeIntensity = true;
	S.SceneFringeIntensity = LensMaterial ? 0.f : 0.35f;
	S.bOverride_FilmGrainIntensity = true;
	S.FilmGrainIntensity = 0.12f;
	S.bOverride_LensFlareIntensity = true;
	S.LensFlareIntensity = 0.25f;
	S.bOverride_MotionBlurAmount = true;
	S.MotionBlurAmount = 0.f;
}

void AMenuDirector::PlaceShip()
{
	if (bEnding)
	{
		PlaceShipEnding();
		return;
	}
	ShipPivot->SetRelativeLocation(ShipOffset + FVector(0.f, 0.f, FMath::Sin(Clock * 0.35f) * BobCm));
	ShipPivot->SetRelativeRotation(FRotator(ShipStart.Pitch, ShipStart.Yaw + SpinDegPerSec * Clock,
		ShipStart.Roll + RollDegPerSec * Clock));
}

void AMenuDirector::BeginPlay()
{
	Super::BeginPlay();
	bEnding = GetWorld()->URL.HasOption(TEXT("Ending")) || FParse::Param(FCommandLine::Get(), TEXT("MenuEnding"));
	if (bEnding)
	{
		RunAudio::Loop(this, TEXT("Win"), 0.85f, 1.5f);      // музыка победы (audio/music/win), 30 с
		ShipGlow = Ship->CreateDynamicMaterialInstance(0);
		bLensFixed = true;                                    // в концовке мыши нет: линза посередине
		Lens = LensTarget = FVector2D(0.5f, 0.5f);
		// по кораблю проверяется, какие буквы титров он заслоняет (AMenuHUD): только запросы, ничто в меню о него не бьётся
		Ship->SetCollisionEnabled(ECollisionEnabled::QueryOnly);
		Ship->SetCollisionResponseToAllChannels(ECR_Block);
		UE_LOG(LogMenu, Log, TEXT("Menu: ending"));
	}
	else
	{
		RunAudio::Loop(this, TEXT("MenuTheme"), 0.6f, 3.f);   // музыка меню (карточка audio/music/menu-theme)
	}
	// линза: материал постобработки поверх готового кадра (только в игре: в сохранённый уровень не попадает)
	if (UMaterialInterface* Base = LoadObject<UMaterialInterface>(nullptr, MenuAssets::Lens))
	{
		LensMaterial = UMaterialInstanceDynamic::Create(Base, this);
		Post->AddOrUpdateBlendable(LensMaterial, 1.f);
	}
	FString Fixed;
	if (FParse::Value(FCommandLine::Get(), TEXT("MenuMouse="), Fixed, false))
	{
		FString X, Y;
		if (Fixed.Split(TEXT(","), &X, &Y))
		{
			bLensFixed = true;
			Lens = LensTarget = FVector2D(FCString::Atof(*X), FCString::Atof(*Y));
		}
	}
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
	PC->bShowMouseCursor = !bEnding;
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
#if WITH_EDITOR
	// отладка: K в меню — сразу сцена концовки (только в редакторе, в упакованной игре клавиши нет)
	InputComponent->BindKey(EKeys::K, IE_Pressed, this, &AMenuDirector::OnDebugEnding);
#endif
	// в настройках видео влево и вправо меняют значение
	for (const FKey& Key : {EKeys::Left, EKeys::A})
	{
		InputComponent->BindKey(Key, IE_Pressed, this, &AMenuDirector::OnLeft);
	}
	for (const FKey& Key : {EKeys::Right, EKeys::D})
	{
		InputComponent->BindKey(Key, IE_Pressed, this, &AMenuDirector::OnRight);
	}
	bVideoAtStart = FParse::Param(FCommandLine::Get(), TEXT("MenuVideo"));
	UE_LOG(LogMenu, Log, TEXT("Menu: ready"));
}

void AMenuDirector::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);
	Clock += DeltaSeconds;
	PlaceShip();
	if (Post && FVideoMenu::GetBrightness() != AppliedBrightness)
	{
		AppliedBrightness = FVideoMenu::GetBrightness();
		Post->Settings.AutoExposureBias = ExposureBias + AppliedBrightness;
	}
	if (bVideoAtStart && Clock > 3.f)
	{
		bVideoAtStart = false;
		Activate(ItemSettings);
		if (FParse::Param(FCommandLine::Get(), TEXT("MenuVideoTest")))
		{
			// проверка без рук: значение сдвинуть влево и обратно вправо, в журнал — что показывала строка
			for (const int32 Row : { FVideoMenu::Quality, FVideoMenu::Scale, FVideoMenu::FrameLimit, FVideoMenu::VSync, FVideoMenu::Brightness, FVideoMenu::Training })
			{
				Video.Select(Row);
				const FString Was = Video.Value(Row);
				Video.Change(-1);
				const FString Down = Video.Value(Row);
				Video.Change(1);
				UE_LOG(LogMenu, Display, TEXT("Menu: video %s: %s -> %s -> %s"), *FVideoMenu::Label(Row), *Was, *Down, *Video.Value(Row));
			}
			Video.Select(0);
		}
	}
	// лёгкий дрейф камеры: корабль чуть смещается на фоне неба (небо бесконечно далеко и не смещается)
	const float D = bEnding ? 0.f : CameraDriftCm;   // в концовке камерой правит своя часть ниже
	Camera->SetRelativeLocation(FVector(FMath::Sin(Clock * 0.11f) * D, FMath::Sin(Clock * 0.07f + 1.f) * D,
		FMath::Sin(Clock * 0.09f + 2.f) * D * 0.5f));

	if (APlayerController* PC = UGameplayStatics::GetPlayerController(this, 0))
	{
		if (PC->GetViewTarget() != this)
		{
			PC->SetViewTarget(this);   // если режим игры всё же дал игроку пешку, вид остаётся за меню
		}
		// линза идёт за мышью с запаздыванием; мышь ушла из окна — линза остаётся, где была
		int32 VX = 0, VY = 0;
		float MX = 0.f, MY = 0.f;
		PC->GetViewportSize(VX, VY);
		if (!bLensFixed && VX > 0 && VY > 0 && PC->GetMousePosition(MX, MY))
		{
			LensTarget = FVector2D(FMath::Clamp(MX / VX, 0.f, 1.f), FMath::Clamp(MY / VY, 0.f, 1.f));
		}
		if (LensMaterial && VX > 0 && VY > 0)
		{
			LensMaterial->SetVectorParameterValue(TEXT("Lens"), FLinearColor(Lens.X, Lens.Y, LensStrength, float(VX) / VY));
			LensMaterial->SetScalarParameterValue(TEXT("Radius"), LensRadius);
		}
	}
	Lens = FMath::Vector2DInterpTo(Lens, LensTarget, DeltaSeconds, LensFollow);
	if (bEnding)
	{
		// двигатели: свет за кормой и огни корабля разгораются за секунду, свет чуть дрожит
		const float Ignite = FMath::Clamp((Clock - EndingIgnite) / 1.2f, 0.f, 1.f);
		if (!bIgnited && Clock >= EndingIgnite)
		{
			bIgnited = true;
			EngineLight->SetVisibility(true);
			RunAudio::Play(this, TEXT("EnginesOnline"));
		}
		EngineLight->SetIntensity(60000.f * Ignite * (1.f + 0.08f * FMath::Sin(Clock * 23.f)));
		if (ShipGlow)
		{
			ShipGlow->SetScalarParameterValue(TEXT("EmissiveStrength"), 6.f + 20.f * Ignite);
		}
		// Камера (MenuEnding): стоит и смотрит между дырой и кораблём, пока он идёт на неё; у самой камеры мягко
		// трогается и летит впереди него — тогда направление на корабль и на дыру больше не меняется и кадр замирает
		FVector ShipPos, CamPos;
		float Travel = 0.f;
		EndingPath(ShipPos, CamPos, Travel);
		Camera->SetRelativeLocation(CamPos + FVector(0.f, FMath::Sin(Clock * 0.23f) * 50.f, FMath::Sin(Clock * 0.19f + 1.f) * 35.f));
		const FVector HoleLocal = FRotator(HolePitch, HoleYaw, 0.f).Vector();
		const FVector ToShip = (ShipPivot->GetRelativeLocation() - CamPos).GetSafeNormal();
		const float W = 0.45f + 0.1f * FMath::Clamp((Clock - EndingGo) / 8.f, 0.f, 1.f);
		CamDir = (HoleLocal * (1.f - W) + ToShip * W).GetSafeNormal();
		if (!bCamInit)
		{
			bCamInit = true;
			CamRot = CamDir.Rotation();
		}
		CamRot = FMath::RInterpTo(CamRot, CamDir.Rotation(), DeltaSeconds, 2.2f);
		const float Shake = Ignite * (1.f - FMath::Clamp((Clock - EndingIgnite - 1.2f) / 2.f, 0.f, 1.f));
		const FRotator Sway(FMath::Sin(Clock * 0.21f) * 0.25f, FMath::Sin(Clock * 0.17f + 0.5f) * 0.3f, FMath::Sin(Clock * 0.13f) * 0.6f);
		Camera->SetRelativeRotation(CamRot + Sway + FRotator(FMath::Sin(Clock * 31.f) * 0.15f * Shake, FMath::Sin(Clock * 27.f) * 0.15f * Shake, 0.f));
		// камера уходит от дыры вместе с кораблём: дыра уменьшается (расстояние до неё в материале неба растёт)
		if (SkyMaterial)
		{
			const FVector Hole = HoleDirection();
			SkyMaterial->SetVectorParameterValue(TEXT("Hole"), FLinearColor(Hole.X, Hole.Y, Hole.Z, HoleDistance * (1.f + MenuEnding::HoleFar * Travel)));
		}
		TickCredits();
		if (Clock >= EndingLength)
		{
			EndEnding();
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

void AMenuDirector::EndingPath(FVector& ShipPos, FVector& CamPos, float& CamTravel) const
{
	using namespace MenuEnding;
	const FVector Away = -FRotator(HolePitch, HoleYaw, 0.f).Vector();   // от дыры
	// разгон без рывка: скорость растёт от нуля к Speed, путь — её интеграл
	const float T = FMath::Max(Clock - EndingGo, 0.f);
	const float Path = Speed * (T - Tau * (1.f - FMath::Exp(-T / Tau)));
	ShipPos = ShipFrom + Away * Path;
	// сколько было бы от корабля до камеры вдоль пути, стой камера на месте; камера мягко не подпускает ближе Follow
	// (гладкий максимум: далеко — стоит, близко — летит со скоростью корабля, между — плавно разгоняется)
	const float Free = FVector::DotProduct(-ShipFrom, Away) - Path;
	const float X = (Free - Follow) / Soft;
	const float Kept = X > 20.f ? Free : Follow + Soft * FMath::Loge(1.f + FMath::Exp(X));
	CamTravel = Kept - Free;
	CamPos = Away * CamTravel;
}

void AMenuDirector::PlaceShipEnding()
{
	FVector Pos, CamPos;
	float Travel = 0.f;
	EndingPath(Pos, CamPos, Travel);
	// корабль живой: чуть покачивается и кренится (камера летит с ним, поэтому качание видно в кадре)
	const float Go = FMath::Clamp((Clock - EndingGo) / 8.f, 0.f, 1.f);
	Pos += FVector(0.f, FMath::Sin(Clock * 0.45f) * 70.f, FMath::Sin(Clock * 0.6f) * 50.f);
	const FRotator Heading = (-FRotator(HolePitch, HoleYaw, 0.f).Vector()).Rotation();   // нос (+X модели) — от дыры
	ShipPivot->SetRelativeLocation(Pos);
	ShipPivot->SetRelativeRotation(FRotator(Heading.Pitch + 2.f + FMath::Sin(Clock * 0.33f) * 0.8f, Heading.Yaw,
		-10.f * Go + FMath::Sin(Clock * 0.4f) * 3.f * Go));
}

void AMenuDirector::TickCredits()
{
	using namespace MenuCredits;
	const int32 Num = UE_ARRAY_COUNT(Credits);
	CreditAnchor.SetNum(Num);
	CreditHeight.SetNum(Num);
	CreditPlaced.SetNum(Num);
	for (int32 I = 0; I < Num; ++I)
	{
		const FCredit& Cr = Credits[I];
		if (CreditPlaced[I] || Clock < Cr.Start)
		{
			continue;
		}
		// точка в пространстве, которая сейчас видна в нужном месте экрана; дальше титр стоит, камера улетает
		CreditPlaced[I] = true;
		const FVector Loc = Camera->GetComponentLocation();
		const FRotator Rot = Camera->GetComponentRotation();
		FVector2D View(16.f, 9.f);
		if (GEngine && GEngine->GameViewport)
		{
			GEngine->GameViewport->GetViewportSize(View);
		}
		const float TanX = FMath::Tan(FMath::DegreesToRadians(Camera->FieldOfView * 0.5f));
		const float TanY = TanX * View.Y / FMath::Max(View.X, 1.f);
		const FVector Dir(1.f, (Cr.X * 2.f - 1.f) * TanX, (1.f - Cr.Y * 2.f) * TanY);
		CreditAnchor[I] = Loc + Rot.RotateVector(Dir * Cr.Depth);
		CreditHeight[I] = Size * 2.f * Cr.Depth * TanY;
	}
}

void AMenuDirector::GetCredits(TArray<FCreditView>& Out) const
{
	using namespace MenuCredits;
	Out.Reset();
	const int32 Num = UE_ARRAY_COUNT(Credits);
	for (int32 I = 0; I < Num && I < CreditPlaced.Num(); ++I)
	{
		const FCredit& Cr = Credits[I];
		const float Age = Clock - Cr.Start;
		const float Life = I == Num - 1 ? 1000.f : Hold;
		if (!CreditPlaced[I] || Age < 0.f || Age > Life + 1.5f)
		{
			continue;
		}
		FCreditView& V = Out.AddDefaulted_GetRef();
		V.Caption = Cr.Caption;
		V.Name = Cr.Name;
		V.At = CreditAnchor[I];
		V.Height = CreditHeight[I];
		V.Size = Size;
		V.Age = Age;
		V.Life = Life;
	}
}

bool AMenuDirector::IsBehindShip(const FVector& From, const FVector& To) const
{
	FHitResult Hit;
	FCollisionQueryParams Params(NAME_None, true);   // по треугольникам модели, а не по коробке
	return Ship && Ship->GetStaticMesh() && Ship->LineTraceComponent(Hit, From, To, Params);
}

void AMenuDirector::OnDebugEnding()
{
	if (!bEnding)
	{
		UE_LOG(LogMenu, Log, TEXT("Menu: debug K - ending"));
		UGameplayStatics::OpenLevel(this, FName(*UGameplayStatics::GetCurrentLevelName(this)), true, TEXT("Ending"));
	}
}

void AMenuDirector::EndEnding()
{
	if (bEndingLeft)
	{
		return;
	}
	bEndingLeft = true;
	UE_LOG(LogMenu, Log, TEXT("Menu: ending done"));
	UGameplayStatics::OpenLevel(this, FName(*UGameplayStatics::GetCurrentLevelName(this)));   // то же меню, без концовки
}

float AMenuDirector::GetFade() const
{
	float Fade = 1.f - FMath::Clamp(Clock / MenuAssets::FadeIn, 0.f, 1.f);
	if (bEnding)
	{
		Fade = FMath::Max(Fade, FMath::Clamp((Clock - (EndingLength - 2.f)) / 2.f, 0.f, 1.f));
		return Fade * Fade * (3.f - 2.f * Fade);
	}
	if (Chosen >= 0)
	{
		const float Start = (LeaveAt >= 0.f ? LeaveAt : Clock) - MenuAssets::FadeOut;
		Fade = FMath::Max(Fade, LeaveAt == -2.f ? 1.f : FMath::Clamp((Clock - Start) / MenuAssets::FadeOut, 0.f, 1.f));
	}
	return Fade * Fade * (3.f - 2.f * Fade);
}

void AMenuDirector::HoverVideo(int32 Row)
{
	if (bVideoOpen)
	{
		Video.Select(Row);
	}
}

void AMenuDirector::OnLeft()
{
	if (bVideoOpen)
	{
		Video.Change(-1);
		RunAudio::Play(this, TEXT("UiClick"));
	}
}

void AMenuDirector::OnRight()
{
	if (bVideoOpen)
	{
		Video.Change(1);
		RunAudio::Play(this, TEXT("UiClick"));
	}
}

void AMenuDirector::Hover(int32 Item)
{
	if (Chosen < 0 && !bVideoOpen && Item >= 0 && Item < ItemCount)
	{
		Selected = Item;
	}
}

void AMenuDirector::OnUp()
{
	if (bEnding)
	{
		return;
	}
	if (bVideoOpen)
	{
		Video.Move(-1);
		RunAudio::Play(this, TEXT("UiClick"));
	}
	else if (Chosen < 0)
	{
		Selected = (Selected + ItemCount - 1) % ItemCount;
		RunAudio::Play(this, TEXT("UiClick"));
	}
}

void AMenuDirector::OnDown()
{
	if (bEnding)
	{
		return;
	}
	if (bVideoOpen)
	{
		Video.Move(1);
		RunAudio::Play(this, TEXT("UiClick"));
	}
	else if (Chosen < 0)
	{
		Selected = (Selected + 1) % ItemCount;
		RunAudio::Play(this, TEXT("UiClick"));
	}
}

void AMenuDirector::OnAccept()
{
	if (bEnding)
	{
		if (Clock > 2.f)
		{
			EndEnding();   // титры можно пропустить
		}
		return;
	}
	if (bVideoOpen)
	{
		bVideoOpen = !Video.Activate();   // Enter на «Back» закрывает настройки
		RunAudio::Play(this, TEXT("UiConfirm"));
		return;
	}
	Activate(Selected);
}

void AMenuDirector::OnClick()
{
	if (bEnding)
	{
		if (Clock > 2.f)
		{
			EndEnding();   // титры можно пропустить
		}
		return;
	}
	const APlayerController* PC = UGameplayStatics::GetPlayerController(this, 0);
	const AMenuHUD* Hud = PC ? Cast<AMenuHUD>(PC->GetHUD()) : nullptr;
	if (bVideoOpen)
	{
		// щелчок по строке: по названию — выделить, по левой половине значения — меньше, по правой — больше
		int32 Row = -1, Step = 0;
		if (Hud && Hud->VideoUnderMouse(Row, Step))
		{
			Video.Select(Row);
			if (Row >= FVideoMenu::Detect)
			{
				bVideoOpen = !Video.Activate();
				RunAudio::Play(this, TEXT("UiConfirm"));
			}
			else if (Step != 0)
			{
				Video.Change(Step);
				RunAudio::Play(this, TEXT("UiClick"));
			}
		}
		return;
	}
	const int32 Item = Hud ? Hud->ItemUnderMouse() : -1;
	if (Item >= 0)
	{
		Activate(Item);
	}
}

void AMenuDirector::OnBack()
{
	if (bEnding)
	{
		if (Clock > 2.f)
		{
			EndEnding();   // титры можно пропустить
		}
		return;
	}
	if (bVideoOpen)
	{
		bVideoOpen = false;   // Esc из настроек — обратно к пунктам
		RunAudio::Play(this, TEXT("UiClick"));
		return;
	}
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
	if (Item == ItemSettings)
	{
		Selected = Item;
		bVideoOpen = true;   // настройки открываются поверх меню, уровень не меняется
		Video.Open();
		RunAudio::Play(this, TEXT("UiConfirm"));
		return;
	}
	Chosen = Item;
	Selected = Item;
	LeaveAt = Clock + MenuAssets::FadeOut;
	RunAudio::Play(this, TEXT("UiConfirm"));
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
