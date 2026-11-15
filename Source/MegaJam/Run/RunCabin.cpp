#include "RunCabin.h"

#include "Camera/PlayerCameraManager.h"
#include "Components/PointLightComponent.h"
#include "Components/SceneCaptureComponent2D.h"
#include "Components/StaticMeshComponent.h"
#include "Components/TextRenderComponent.h"
#include "Engine/StaticMesh.h"
#include "Engine/TextureRenderTarget2D.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "Engine/World.h"
#include "GameFramework/Pawn.h"
#include "Kismet/GameplayStatics.h"
#include "Materials/MaterialInterface.h"
#include "RunAudio.h"
#include "RunDirector.h"
#include "RunRoom.h"

using namespace RunCabinGeo;

FVector RunCabinGeo::BridgeOffset()
{
	// внешняя грань каюты + глубина тамбура + от южной грани рубки до её середины
	return FVector(OuterFace + RunRoomGeo::VestibuleDepth + RunRoomGeo::OuterFace(1), 0.f, 0.f);
}

ARunCabin::ARunCabin()
{
	PrimaryActorTick.bCanEverTick = true;
	Root = CreateDefaultSubobject<USceneComponent>(TEXT("Root"));
	SetRootComponent(Root);
}

void ARunCabin::BeginPlay()
{
	Super::BeginPlay();
	TInlineComponentArray<UStaticMeshComponent*> Meshes(this);
	UMaterialInterface* Tiles = LoadObject<UMaterialInterface>(nullptr,
		TEXT("/Game/Environment/Common/FloorTiles/MI_FloorTiles.MI_FloorTiles"), nullptr, LOAD_NoWarn | LOAD_Quiet);
	UStaticMesh* DoorMesh = LoadObject<UStaticMesh>(nullptr, TEXT("/Game/Environment/Common/AirlockDoor/SM_AirlockDoor.SM_AirlockDoor"),
		nullptr, LOAD_NoWarn | LOAD_Quiet);
	for (UStaticMeshComponent* M : Meshes)
	{
		const FString N = M->GetName();
		if (Tiles && (N == TEXT("Floor") || N.EndsWith(TEXT("_Airlock_Floor"))))
		{
			M->SetMaterial(0, Tiles);
		}
		// створки — модель автора, как в комнатах (ARunRoom::BeginPlay)
		if (DoorMesh && (N.EndsWith(TEXT("_DoorInner")) || N.EndsWith(TEXT("_DoorOuter"))))
		{
			const FVector Size = M->GetStaticMesh() ? M->GetStaticMesh()->GetBoundingBox().GetSize() * M->GetRelativeScale3D() : FVector(10.f, 150.f, 225.f);
			M->SetStaticMesh(DoorMesh);
			M->EmptyOverrideMaterials();
			M->SetRelativeScale3D(FVector(1.f));
			M->SetRelativeRotation(FRotator(0.f, Size.X < Size.Y ? 90.f : 0.f, 0.f));
		}
		if (N == TEXT("N_DoorInner"))
		{
			Leaf = M;
			M->SetMobility(EComponentMobility::Movable);
			LeafClosed = M->GetRelativeLocation();
		}
		else if (N == TEXT("Lock_Keypad"))
		{
			Keypad = M;
		}
		else if (N == TEXT("Mirror"))
		{
			SetupMirror(M);
		}
	}
	if (!Leaf)
	{
		UE_LOG(LogTemp, Warning, TEXT("RunCabin %s: нет створки N_DoorInner"), *GetName());
	}

	// табло над дверью, как у комнат: LOCKED красным, после кода — OPEN бирюзовым
	Sign = NewObject<UTextRenderComponent>(this);
	Sign->SetupAttachment(GetRootComponent());
	Sign->RegisterComponent();
	Sign->SetHorizontalAlignment(EHTA_Center);
	Sign->SetVerticalAlignment(EVRTA_TextCenter);
	Sign->SetWorldSize(30.f);
	Sign->SetRelativeLocation(FVector(InnerFace - 5.f, 0.f, 275.f));
	Sign->SetRelativeRotation(FRotator(0.f, 180.f, 0.f));   // текст смотрит в каюту
	UStaticMeshComponent* Plate = NewObject<UStaticMeshComponent>(this);
	Plate->SetupAttachment(GetRootComponent());
	Plate->RegisterComponent();
	Plate->SetMobility(EComponentMobility::Movable);
	Plate->SetCollisionProfileName(TEXT("NoCollision"));
	Plate->SetStaticMesh(LoadObject<UStaticMesh>(nullptr, TEXT("/Engine/BasicShapes/Cube.Cube")));
	if (UMaterialInterface* Dark = LoadObject<UMaterialInterface>(nullptr, TEXT("/Game/Game/Materials/MI_Gray_Dark.MI_Gray_Dark")))
	{
		Plate->SetMaterial(0, Dark);
	}
	Plate->SetRelativeLocation(FVector(InnerFace - 1.5f, 0.f, 275.f));
	Plate->SetRelativeRotation(FRotator(0.f, 180.f, 0.f));
	Plate->SetRelativeScale3D(FVector(0.03f, 2.3f, 0.42f));
	UpdateSign();
}

void ARunCabin::SetupMirror(UStaticMeshComponent* Backing)
{
	UMaterialInterface* MirrorMat = LoadObject<UMaterialInterface>(nullptr, TEXT("/Game/Game/Materials/M_Mirror.M_Mirror"), nullptr, LOAD_NoWarn | LOAD_Quiet);
	UStaticMesh* Plane = LoadObject<UStaticMesh>(nullptr, TEXT("/Engine/BasicShapes/Plane.Plane"));
	if (!MirrorMat || !Plane || !Backing->GetStaticMesh())
	{
		UE_LOG(LogTemp, Warning, TEXT("RunCabin: зеркало не собрано (нет M_Mirror или плоскости)"));
		return;
	}
	// стекло — тёмная коробка из блюпринта (build_rooms.py, cabin()): её лицо смотрит в каюту, на +Y
	const FVector Size = Backing->GetStaticMesh()->GetBoundingBox().GetSize() * Backing->GetComponentScale();
	MirrorHalf = FVector2D(Size.X * 0.5f, Size.Z * 0.5f);
	const FVector Face = Backing->GetComponentLocation() + FVector(0.f, Size.Y * 0.5f + 0.15f, 0.f);

	MirrorTarget = NewObject<UTextureRenderTarget2D>(this);
	MirrorTarget->RenderTargetFormat = RTF_RGBA16f;
	MirrorTarget->ClearColor = FLinearColor::Black;
	MirrorTarget->InitAutoFormat(FMath::RoundToInt32(MirrorHalf.X * 12.f), FMath::RoundToInt32(MirrorHalf.Y * 12.f));   // 6 точек на см
	MirrorTarget->UpdateResourceImmediate(true);

	// плоскость движка 100 × 100 лицом на +Z; лицо — в каюту, ширина вдоль X, высота вдоль Z. Знаки масштаба подобраны
	// так, чтобы u кадра шёл вдоль правой оси камеры зеркала (−X мира), v — сверху вниз
	MirrorGlass = NewObject<UStaticMeshComponent>(this, TEXT("MirrorGlass"));
	MirrorGlass->SetupAttachment(GetRootComponent());
	MirrorGlass->RegisterComponent();
	MirrorGlass->SetStaticMesh(Plane);
	MirrorGlass->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	MirrorGlass->SetCastShadow(false);
	MirrorGlass->SetWorldLocationAndRotation(Face, FRotationMatrix::MakeFromXZ(FVector(-1.f, 0.f, 0.f), FVector(0.f, 1.f, 0.f)).Rotator());
	MirrorGlass->SetWorldScale3D(FVector(Size.X / 100.f, -Size.Z / 100.f, 1.f));
	UMaterialInstanceDynamic* Mid = UMaterialInstanceDynamic::Create(MirrorMat, this);
	Mid->SetTextureParameterValue(TEXT("Tex"), MirrorTarget);
	// в кадре камеры зеркала нет Lumen: без подсветки отражённая каюта выходит темнее настоящей (проверено по кадру)
	Mid->SetScalarParameterValue(TEXT("Gain"), 1.3f);
	MirrorGlass->SetMaterial(0, Mid);

	MirrorCapture = NewObject<USceneCaptureComponent2D>(this, TEXT("MirrorCapture"));
	MirrorCapture->SetupAttachment(GetRootComponent());
	MirrorCapture->SetUsingAbsoluteLocation(true);
	MirrorCapture->SetUsingAbsoluteRotation(true);
	MirrorCapture->TextureTarget = MirrorTarget;
	MirrorCapture->CaptureSource = ESceneCaptureSource::SCS_SceneColorHDR;   // тон и экспозицию даст основной кадр
	MirrorCapture->bCaptureEveryFrame = true;
	MirrorCapture->bCaptureOnMovement = false;
	MirrorCapture->bAlwaysPersistRenderingState = true;
	MirrorCapture->bUseCustomProjectionMatrix = true;
	MirrorCapture->ShowFlags.SetMotionBlur(false);
	// отражённый свет в кадре зеркала (автор, 16.11: «там оно темнее и контрастнее, поэтому сразу ощущение, что это
	// не зеркало, а комната за стеклом»): без него в отражении есть только прямой свет ламп, тени чёрные
	MirrorCapture->ShowFlags.SetGlobalIllumination(true);
	MirrorCapture->ShowFlags.SetLumenGlobalIllumination(true);
	MirrorCapture->ShowFlags.SetLumenReflections(true);
	MirrorCapture->PostProcessBlendWeight = 1.f;
	MirrorCapture->PostProcessSettings.bOverride_DynamicGlobalIlluminationMethod = true;
	MirrorCapture->PostProcessSettings.DynamicGlobalIlluminationMethod = EDynamicGlobalIlluminationMethod::Lumen;
	MirrorCapture->PostProcessSettings.bOverride_ReflectionMethod = true;
	MirrorCapture->PostProcessSettings.ReflectionMethod = EReflectionMethod::Lumen;
	MirrorCapture->HideComponent(MirrorGlass);
	MirrorCapture->HideComponent(Backing);
	MirrorCapture->RegisterComponent();
	// лампа над зеркалом: тот, кто стоит перед ним, обращён лицом к стене, спиной к свету каюты, а в кадре камеры
	// зеркала нет отражённого света — без лампы отражение выходило чёрным силуэтом (кадры вступительной сцены, 16.11)
	UPointLightComponent* Lamp = NewObject<UPointLightComponent>(this, TEXT("MirrorLamp"));
	Lamp->SetupAttachment(GetRootComponent());
	Lamp->SetMobility(EComponentMobility::Movable);
	Lamp->SetIntensity(260.f);
	Lamp->SetAttenuationRadius(280.f);
	Lamp->SetLightColor(FLinearColor(1.f, 0.94f, 0.86f));
	Lamp->SetCastShadows(false);
	Lamp->RegisterComponent();
	Lamp->SetWorldLocation(Face + FVector(0.f, 28.f, MirrorHalf.Y + 12.f));
	UpdateMirror();
}

void ARunCabin::UpdateMirror()
{
	const APlayerCameraManager* Cam = UGameplayStatics::GetPlayerCameraManager(this, 0);
	if (!MirrorCapture || !MirrorGlass || !Cam)
	{
		return;
	}
	const FVector N(0.f, 1.f, 0.f);   // нормаль стекла, в каюту
	const FVector C = MirrorGlass->GetComponentLocation();
	const FVector Eye = Cam->GetCameraLocation();
	const float Dist = FVector::DotProduct(Eye - C, N);
	// камера игрока за плоскостью зеркала или стекло у неё за спиной — второй проход рендера не нужен
	const bool bFacing = FVector::DotProduct(Cam->GetCameraRotation().Vector(), (C - Eye).GetSafeNormal()) > -0.2f;
	MirrorCapture->bCaptureEveryFrame = Dist > 5.f && bFacing;
	if (!MirrorCapture->bCaptureEveryFrame)
	{
		return;
	}
	// отражённая точка смотрит из-за стекла в каюту: вперёд +N, вверх +Z, вправо — −X мира
	const FVector EyeR = Eye - 2.f * Dist * N;
	const FRotator Rot = N.Rotation();
	const FVector Right = FRotationMatrix(Rot).GetUnitAxis(EAxis::Y), Up = FVector::UpVector;
	const FVector Rel = C - EyeR;
	const float Near = FVector::DotProduct(Rel, N);   // = Dist: ближняя плоскость — плоскость зеркала
	const float Cx = FVector::DotProduct(Rel, Right), Cy = FVector::DotProduct(Rel, Up);
	const float L = Cx - MirrorHalf.X, R = Cx + MirrorHalf.X, B = Cy - MirrorHalf.Y, T = Cy + MirrorHalf.Y;
	// несимметричная перспектива с обратной глубиной и бесконечной дальней плоскостью (как FReversedZPerspectiveMatrix):
	// x_ndc = (2n·x/z − (r+l)) / (r−l) и так же по y, глубина = n / z
	MirrorCapture->CustomProjectionMatrix = FMatrix(
		FPlane(2.f * Near / (R - L), 0.f, 0.f, 0.f),
		FPlane(0.f, 2.f * Near / (T - B), 0.f, 0.f),
		FPlane(-(R + L) / (R - L), -(T + B) / (T - B), 0.f, 1.f),
		FPlane(0.f, 0.f, Near, 0.f));
	MirrorCapture->SetWorldLocationAndRotation(EyeR, Rot);
}

void ARunCabin::UpdateSign()
{
	if (Sign)
	{
		Sign->SetText(FText::FromString(bUnlocked ? TEXT("OPEN") : TEXT("LOCKED")));
		Sign->SetTextRenderColor(bUnlocked ? FColor(95, 198, 201) : FColor(235, 60, 45));
	}
}

void ARunCabin::Unlock()
{
	bUnlocked = true;
	UpdateSign();
}

FVector ARunCabin::KeypadLocation() const
{
	return Keypad ? Keypad->GetComponentLocation() : GetActorLocation() + FVector(InnerFace, KeypadY, 130.f);
}

bool ARunCabin::IsNearKeypad(const FVector& PawnPos) const
{
	const FVector Local = PawnPos - GetActorLocation();
	return Local.X < InnerFace + 10.f && FVector::Dist2D(PawnPos, KeypadLocation()) < 175.f;
}

FVector ARunCabin::MirrorCenter() const
{
	return MirrorGlass ? MirrorGlass->GetComponentLocation() : GetActorLocation() + FVector(37.5f, -147.6f, 150.f);
}

FVector ARunCabin::WakeLocation() const
{
	// ближе к двери: камера за спиной (штанга 2,7 м) упирается в капсулу снаружи, а не заезжает под её крышу
	return GetActorLocation() + FVector(140.f, 60.f, 100.f);
}

void ARunCabin::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);
	const APawn* Pawn = UGameplayStatics::GetPlayerPawn(this, 0);
	const FVector Local = Pawn ? Pawn->GetActorLocation() - GetActorLocation() : FVector(0, 0, -100000);
	const bool bPawnHere = Pawn && Local.Z > -50.f && Local.Z < 400.f;
	const float Lateral = FMath::Abs(Local.Y);
	const float VW = RunRoomGeo::VestibuleWidth, VD = RunRoomGeo::VestibuleDepth, Wall = RunRoomGeo::Wall;
	// те же зоны, что у двери комнаты (ARunRoom::Tick): перед дверью, в проёме и начале тамбура, в глубине тамбура
	const bool bApproach = bPawnHere && Local.X > InnerFace - 220.f && Local.X <= InnerFace && Lateral < 150.f;
	const bool bDoorway = bPawnHere && Local.X > InnerFace && Local.X <= OuterFace + 90.f && Lateral < VW * 0.5f;
	const bool bDeep = bPawnHere && Local.X > OuterFace + 90.f && Local.X < OuterFace + VD + Wall && Lateral < VW * 0.5f + Wall;
	if (bUnlocked && bDeep && !bLeaving)
	{
		bLeaving = true;   // створка за игроком закрывается
		RunAudio::Play(this, TEXT("AirlockScan"));
	}
	else if (bLeaving && !bDeep && !bLeft)
	{
		bLeaving = false;   // вышел из тамбура обратно, пока створка закрывалась
	}
	const bool bWantOpen = bUnlocked && !bLeaving && (bApproach || bDoorway || bDeep);
	if (bWantOpen != bLeafWanted)
	{
		bLeafWanted = bWantOpen;
		if (Leaf)
		{
			RunAudio::PlayAt(this, bWantOpen ? TEXT("DoorOpen") : TEXT("DoorClose"), Leaf->GetComponentLocation(), 0.8f);
		}
	}
	LeafOpen = FMath::Clamp(LeafOpen + (bWantOpen ? 1.f : -1.f) * DeltaSeconds / 0.6f, 0.f, 1.f);
	if (Leaf)
	{
		Leaf->SetRelativeLocation(LeafClosed + FVector(0.f, 1.f, 0.f) * RunRoomGeo::DoorWidth * FMath::SmoothStep(0.f, 1.f, LeafOpen));
	}
	UpdateMirror();
	if (bLeaving && !bLeft && LeafOpen <= 0.f && Director.IsValid())
	{
		bLeft = true;
		Director->LeaveCabin(this);   // каюту убирает ведущий забега
	}
}
