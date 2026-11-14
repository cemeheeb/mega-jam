#include "RunThreat.h"

#include "Components/SkeletalMeshComponent.h"
#include "Components/LightComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/StaticMesh.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "GameFramework/Character.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "GameFramework/Pawn.h"
#include "GameFramework/PlayerController.h"
#include "Kismet/GameplayStatics.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "Materials/MaterialInterface.h"
#include "RunDirector.h"
#include "RunGen.h"
#include "RunItem.h"
#include "RunRoom.h"
#include "UObject/ConstructorHelpers.h"

using namespace RunGen;
using namespace RunThreatTune;
using namespace RunRoomGeo;

namespace
{
	bool InsideRoom(const FVector& Local)
	{
		return FMath::Abs(Local.X) < HalfX && FMath::Abs(Local.Y) < HalfY;
	}

	/** Материалы аномалий (tools/ue/import_anomalies.py). Нет — аномалия работает, но без своего вида. */
	UMaterialInterface* AnomalyMaterial(const TCHAR* Name)
	{
		return LoadObject<UMaterialInterface>(nullptr, *FString::Printf(TEXT("/Game/FX/Anomalies/%s.%s"), Name, Name),
			nullptr, LOAD_NoWarn | LOAD_Quiet);
	}
}

ARunThreat::ARunThreat()
{
	PrimaryActorTick.bCanEverTick = true;
	SetRootComponent(CreateDefaultSubobject<USceneComponent>(TEXT("Root")));
	static ConstructorHelpers::FObjectFinder<UStaticMesh> CubeMesh(TEXT("/Engine/BasicShapes/Cube.Cube"));
	static ConstructorHelpers::FObjectFinder<UStaticMesh> SphereMesh(TEXT("/Engine/BasicShapes/Sphere.Sphere"));
	static ConstructorHelpers::FObjectFinder<UStaticMesh> PlaneMesh(TEXT("/Engine/BasicShapes/Plane.Plane"));
	static ConstructorHelpers::FObjectFinder<UMaterialInterface> Dark(TEXT("/Game/Game/Materials/MI_Gray_Dark.MI_Gray_Dark"));
	static ConstructorHelpers::FObjectFinder<UMaterialInterface> Light(TEXT("/Game/Game/Materials/MI_Gray_Furniture.MI_Gray_Furniture"));
	Cube = CubeMesh.Succeeded() ? CubeMesh.Object : nullptr;
	Sphere = SphereMesh.Succeeded() ? SphereMesh.Object : nullptr;
	Plane = PlaneMesh.Succeeded() ? PlaneMesh.Object : nullptr;
	MatDark = Dark.Succeeded() ? Dark.Object : nullptr;
	MatLight = Light.Succeeded() ? Light.Object : nullptr;
}

bool ARunThreat::IsAnomaly(int32 InKind)
{
	return InKind >= ThreatBlackHole && InKind <= ThreatFungus;
}

const TCHAR* ARunThreat::DisplayName(int32 InKind)
{
	static const TCHAR* const Names[] = { TEXT("Nothing"), TEXT("A tiny black hole"), TEXT("Smoke"), TEXT("Slow time"),
		TEXT("Fungal growth"), TEXT("Mad maintenance robot"), TEXT("Rats"), TEXT("Another you") };
	return InKind >= 0 && InKind <= NumThreats ? Names[InKind] : TEXT("?");
}

UStaticMeshComponent* ARunThreat::AddShape(UStaticMesh* Mesh, UMaterialInterface* Mat, const FVector& SizeCm, const FVector& WorldPos)
{
	UStaticMeshComponent* C = NewObject<UStaticMeshComponent>(this);
	C->SetMobility(EComponentMobility::Movable);
	C->SetStaticMesh(Mesh);
	if (Mat)
	{
		C->SetMaterial(0, Mat);
	}
	C->SetCollisionProfileName(TEXT("NoCollision"));
	C->SetReceivesDecals(false);
	C->SetCastShadow(false);
	C->SetupAttachment(RootComponent);
	C->RegisterComponent();
	C->SetWorldScale3D(SizeCm / 100.f);   // базовые фигуры движка — 100 см
	C->SetWorldLocation(WorldPos);
	Shapes.Add(C);
	return C;
}

float ARunThreat::Random01()
{
	Rand = Mix32(Rand + 0x9E3779B9U);
	return (Rand >> 8) / 16777216.f;
}

void ARunThreat::Setup(int32 InKind, ARunDirector* InDirector, ARunRoom* InRoom, int32 ArrivalDoor, uint32 Seed)
{
	Kind = InKind;
	Director = InDirector;
	Room = InRoom;
	Origin = InRoom->GetActorLocation();
	Rand = Seed | 1U;
	SetActorLocation(Origin);
	switch (Kind)
	{
	case ThreatBlackHole: SetupBlackHole(); break;
	case ThreatSmoke: SetupSmoke(); break;
	case ThreatSlowTime: SetupSlowTime(); break;
	case Decompression: SetupVacuum(); break;
	case ThreatFungus:
	{
		const FIntVector F = InRoom->ApplyFungus(Seed);
		UE_LOG(LogTemp, Display, TEXT("Run: fungus: overgrown %d, mushrooms %d, decals %d"), F.X, F.Y, F.Z);
		break;
	}
	default: break;
	}
}

void ARunThreat::EndPlay(const EEndPlayReason::Type Reason)
{
	// замедление времени и затягивание дыры меняют самого героя: вернуть как было
	if (APawn* Pawn = UGameplayStatics::GetPlayerPawn(this, 0))
	{
		Pawn->CustomTimeDilation = 1.f;
	}
	Super::EndPlay(Reason);
}

void ARunThreat::Hurt(const TCHAR* Text, const FVector& From, float Damage, bool bKnockback)
{
	if (Director.IsValid())
	{
		Director->HurtPlayer(Text, From, Damage, bKnockback);
	}
}

bool ARunThreat::PlayerHere(const FVector& P) const
{
	const FVector Local = P - Origin;
	if (InsideRoom(Local))
	{
		return true;
	}
	// тамбур: от лица колонок до дальнего края, по ширине тамбура
	for (int32 D = 0; D < 4; ++D)
	{
		const float Along = FVector::DotProduct(Local, Dir(D));
		const float Across = FMath::Abs(FVector::DotProduct(Local, Slide(D)));
		if (Along > InnerFace(D) - 1.f && Along < OuterFace(D) + VestibuleDepth && Across < VestibuleWidth * 0.5f)
		{
			return true;
		}
	}
	return false;
}

// ---------- чёрная дыра ----------

void ARunThreat::SetupBlackHole()
{
	// угол, где дальше всего до мест предметов и записок, лежащих вещей и выходов из тамбуров: дыра не должна
	// запирать путь (DESIGN 5.9 — любую угрозу можно пережить)
	TArray<FVector> Keep;
	if (Room.IsValid())
	{
		Keep.Append(Room->GetSpots(TEXT("ItemSpot")));
		Keep.Append(Room->GetSpots(TEXT("NoteSpot")));
	}
	for (TActorIterator<ARunItem> It(GetWorld()); It; ++It)
	{
		Keep.Add(It->GetActorLocation());
	}
	for (int32 D = 0; D < 4; ++D)
	{
		Keep.Add(Origin + Dir(D) * (InnerFace(D) - 60.f));
	}
	float Best = -1.f;
	const int32 First = static_cast<int32>(Random01() * 4.f) & 3;   // при равенстве — угол по зерну
	for (int32 I = 0; I < 4; ++I)
	{
		const int32 C = (First + I) & 3;
		const FVector P = Origin + FVector((C & 1 ? 1.f : -1.f) * (HalfX - HoleInset), (C & 2 ? 1.f : -1.f) * (HalfY - HoleInset), HoleHeight);
		float Near = 1e9f;
		for (const FVector& K : Keep)
		{
			Near = FMath::Min(Near, FVector::Dist2D(P, K));
		}
		if (Near > Best)
		{
			Best = Near;
			HolePos = P;
		}
	}
	KillRadius = FMath::Clamp(Best - HoleClearance, HoleKillMin, HoleKill);
	UMaterialInterface* Lens = AnomalyMaterial(TEXT("MI_BlackHole"));
	AddShape(Sphere, Lens ? Lens : MatDark.Get(), FVector(HoleRadius * 2.f), HolePos);
	// соринки кружат вокруг дыры на наклонных орбитах, как мусор над аномалиями в STALKER
	for (int32 I = 0; I < HoleDust; ++I)
	{
		FDebris B;
		B.Radius = HoleRadius * 0.6f + 70.f * Random01();
		B.Angle = 360.f * Random01();
		B.Speed = (150.f + 150.f * Random01()) * (60.f / B.Radius);
		B.Tilt = FRotator(70.f * (Random01() - 0.5f), 360.f * Random01(), 70.f * (Random01() - 0.5f));
		const float S = 1.5f + 2.5f * Random01();
		B.Mesh = AddShape(Cube, Random01() < 0.6f ? MatDark.Get() : MatLight.Get(), FVector(S, S * (0.5f + Random01()), S * 0.4f), HolePos);
		Debris.Add(B);
	}
	UE_LOG(LogTemp, Display, TEXT("Run: black hole at (%.0f, %.0f), kill radius %.0f, nearest spot %.0f"),
		HolePos.X - Origin.X, HolePos.Y - Origin.Y, KillRadius, Best);
}

void ARunThreat::TickBlackHole(float Dt, APawn* Pawn)
{
	ACharacter* Ch = Cast<ACharacter>(Pawn);
	if (!Ch)
	{
		return;
	}
	USkeletalMeshComponent* Mesh = Ch->GetMesh();
	if (SwallowT >= 0.f)
	{
		// спагеттификация: тело клонится к дыре, вытягивается вдоль себя и уходит в неё; камера остаётся на месте
		SwallowT += Dt;
		const float A = FMath::Clamp(SwallowT / SpaghettiTime, 0.f, 1.f);
		const float E = A * A;
		const FVector ToHole = (HolePos - SwallowFeet).GetSafeNormal();
		const FQuat Upright = Ch->GetActorQuat() * MeshRelative.GetRotation();
		const FQuat Tilt = FQuat(FRotationMatrix::MakeFromZX(ToHole, Ch->GetActorForwardVector()).Rotator()) * MeshRelative.GetRotation();
		Mesh->SetWorldLocationAndRotation(FMath::Lerp(SwallowFeet, HolePos, E), FQuat::Slerp(Upright, Tilt, FMath::Min(1.f, A * 3.f)));
		const FVector S = MeshRelative.GetScale3D();
		Mesh->SetWorldScale3D(FVector(S.X / (1.f + 2.5f * E), S.Y / (1.f + 2.5f * E), S.Z * (1.f + 3.f * E)));
		if (A < 1.f)
		{
			return;
		}
		SwallowT = -1.f;
		Mesh->SetVisibility(false, true);
		if (Director.IsValid())
		{
			Director->KillPlayer(TEXT("The black hole pulls you apart, thread by thread."), HolePos);
		}
		if (Director.IsValid() && Director->GetPhase() == ERunPhase::Playing)
		{
			// самопроверка: игрок бессмертен — вернуть тело и поставить у входа
			Mesh->SetRelativeTransform(MeshRelative);
			Mesh->SetVisibility(true, true);
			Ch->GetCharacterMovement()->SetMovementMode(MOVE_Walking);
			if (APlayerController* PC = Cast<APlayerController>(Ch->GetController()))
			{
				Ch->EnableInput(PC);
			}
			Ch->SetActorLocation(Origin + FVector(0.f, 0.f, 100.f), false, nullptr, ETeleportType::TeleportPhysics);
		}
		return;
	}
	for (FDebris& B : Debris)
	{
		B.Angle = FMath::Fmod(B.Angle + B.Speed * Dt, 360.f);
		B.Spin = FMath::Fmod(B.Spin + 300.f * Dt, 360.f);
		const FVector Ring = FRotator(0.f, B.Angle, 0.f).Vector() * B.Radius;
		B.Mesh->SetWorldLocationAndRotation(HolePos + B.Tilt.RotateVector(Ring), FRotator(B.Spin, B.Spin * 0.6f, 0.f));
	}
	const float D = FVector::Dist(Ch->GetActorLocation(), HolePos);
	if (Director.IsValid())
	{
		const float Near = 1.f - FMath::Clamp((D - KillRadius) / (HoleWarn - KillRadius), 0.f, 1.f);
		Director->SetThreatHint(Near > 0.f ? TEXT("GRAVITY WELL - KEEP AWAY") : TEXT("SOMETHING BENDS THE LIGHT"), Near);
	}
	if (D < KillRadius && Director.IsValid() && Director->GetPhase() == ERunPhase::Playing)
	{
		SwallowT = 0.f;
		MeshRelative = Mesh->GetRelativeTransform();
		SwallowFeet = Mesh->GetComponentLocation();
		Ch->GetCharacterMovement()->DisableMovement();
		if (APlayerController* PC = Cast<APlayerController>(Ch->GetController()))
		{
			Ch->DisableInput(PC);
		}
		UE_LOG(LogTemp, Display, TEXT("Run: black hole swallows the player at %.0f cm"), D);
	}
}

// ---------- дым ----------

void ARunThreat::SetupSmoke()
{
	// дым объёмом, как у дымовой гранаты CS2 (просьба автора 15.11): коробки от SmokeBottom до потолка — комната
	// и каждый тамбур (тамбур заполнен сразу, решение 15.11). Материал идёт лучом сквозь коробку; её границы
	// (относительно актёра — середины пола) задаются здесь, шум общий, так что на стыках коробок шва нет
	if (UMaterialInterface* Volume = Cube ? AnomalyMaterial(TEXT("MI_SmokeVolume")) : nullptr)
	{
		const auto Box = [this, Volume](const FVector& Min, const FVector& Max)
		{
			UStaticMeshComponent* C = AddShape(Cube, nullptr, Max - Min, Origin + (Min + Max) * 0.5f);
			if (UMaterialInstanceDynamic* M = C->CreateDynamicMaterialInstance(0, Volume))
			{
				M->SetVectorParameterValue(TEXT("BoxMin"), FLinearColor(Min.X, Min.Y, Min.Z, 0.f));
				M->SetVectorParameterValue(TEXT("BoxMax"), FLinearColor(Max.X, Max.Y, Max.Z, 0.f));
				M->SetScalarParameterValue(TEXT("Bottom"), SmokeBottom);
			}
		};
		Box(FVector(-HalfX - Lining, -HalfY - Lining, SmokeBottom), FVector(HalfX + Lining, HalfY + Lining, Height));
		for (int32 D = 0; D < 4; ++D)
		{
			const float Depth = OuterFace(D) - InnerFace(D) + VestibuleDepth;
			const FVector C = Dir(D) * (InnerFace(D) + Depth * 0.5f);
			const FVector Half = (D < 2 ? FVector(Depth, VestibuleWidth, 0.f) : FVector(VestibuleWidth, Depth, 0.f)) * 0.5f;
			Box(C - Half + FVector(0.f, 0.f, SmokeBottom), C + Half + FVector(0.f, 0.f, Height));
		}
		UE_LOG(LogTemp, Display, TEXT("Run: smoke volume, %d boxes from %.0f cm"), Shapes.Num(), SmokeBottom);
		return;
	}
	UMaterialInterface* Mat = AnomalyMaterial(TEXT("MI_Smoke"));
	if (!Mat || !Plane)
	{
		UE_LOG(LogTemp, Warning, TEXT("Run: smoke without its look: no /Game/FX/Anomalies/MI_SmokeVolume (tools/ue/import_anomalies.py)"));
		return;
	}
	// запасной вид: слои-плоскости от SmokeBottom до потолка
	for (int32 I = 0; I < SmokeLayers; ++I)
	{
		const float Z = SmokeBottom + (Height - 12.f - SmokeBottom) * I / (SmokeLayers - 1);
		AddShape(Plane, Mat, FVector((HalfX + Lining) * 2.f, (HalfY + Lining) * 2.f, 1.f), Origin + FVector(0.f, 0.f, Z));
		for (int32 D = 0; D < 4; ++D)
		{
			const float Depth = OuterFace(D) - InnerFace(D) + VestibuleDepth;
			const FVector C = Origin + Dir(D) * (InnerFace(D) + Depth * 0.5f) + FVector(0.f, 0.f, Z);
			AddShape(Plane, Mat, D < 2 ? FVector(Depth, VestibuleWidth, 1.f) : FVector(VestibuleWidth, Depth, 1.f), C);
		}
	}
}

void ARunThreat::TickSmoke(float Dt, const FVector& P)
{
	const bool bCrouched = Director.IsValid() && Director->IsPlayerCrouched();
	const bool bIn = PlayerHere(P) && !bCrouched;
	Exposure = bIn ? Exposure + Dt : FMath::Max(0.f, Exposure - Dt * 0.5f);
	if (Director.IsValid() && PlayerHere(P))
	{
		Director->RequestCameraCeiling(Origin.Z + SmokeBottom - SmokeCameraGap);
	}
	if (Director.IsValid())
	{
		Director->SetThreatHint(bIn ? TEXT("SMOKE - [C] GET DOWN UNDER IT") : bCrouched ? TEXT("SMOKE - STAY LOW") : TEXT("SMOKE"),
			Exposure / SmokeTick);
	}
	if (Exposure >= SmokeTick)
	{
		Exposure = 0.f;
		Hurt(TEXT("The smoke burns your throat."), P, SmokeDamage, false);
	}
}

// ---------- замедление времени ----------

void ARunThreat::SetupSlowTime()
{
	if (UMaterialInterface* Bubble = AnomalyMaterial(TEXT("MI_TimeBubble")))
	{
		AddShape(Sphere, Bubble, FVector(150.f), Origin + FVector(0.f, 0.f, 110.f));
	}
	// обломки кружат вокруг середины: у края быстро, у середины почти стоят
	for (int32 I = 0; I < SlowDebris; ++I)
	{
		FDebris B;
		B.Radius = 70.f + (SlowRadius - 40.f) * Random01();
		B.Angle = 360.f * Random01();
		B.Height = 40.f + 190.f * Random01();
		B.Spin = 360.f * Random01();
		const float S = 5.f + 9.f * Random01();
		B.Mesh = AddShape(Cube, Random01() < 0.5f ? MatDark.Get() : MatLight.Get(), FVector(S, S * (0.6f + Random01()), S * 0.5f), Origin);
		Debris.Add(B);
	}
}

void ARunThreat::TickSlowTime(float Dt, APawn* Pawn, const FVector& P)
{
	auto Factor = [](float R) { return FMath::Lerp(SlowMin, 1.f, FMath::SmoothStep(SlowCore, SlowRadius, R)); };
	const FVector Local = P - Origin;
	const float F = InsideRoom(Local) ? Factor(Local.Size2D()) : 1.f;
	// время героя: движение и анимация идут медленнее; мышь (поворот камеры) — нет
	Pawn->CustomTimeDilation = F;
	if (Director.IsValid())
	{
		Director->SetThreatHint(F < 0.9f ? TEXT("TIME IS THICK HERE") : TEXT("TIME RUNS STRANGE"), 1.f - F);
	}
	for (FDebris& B : Debris)
	{
		const float Fb = Factor(B.Radius);
		B.Angle = FMath::Fmod(B.Angle + 45.f * Fb * Dt, 360.f);
		B.Spin = FMath::Fmod(B.Spin + 120.f * Fb * Dt, 360.f);
		B.Mesh->SetWorldLocationAndRotation(Origin + FRotator(0.f, B.Angle, 0.f).Vector() * B.Radius + FVector(0.f, 0.f, B.Height),
			FRotator(B.Spin * 0.7f, B.Spin, 0.f));
	}
}

// ---------- грибы ----------

void ARunThreat::TickFungus(float Dt, const FVector& P)
{
	const bool bSuit = Director.IsValid() && Director->IsSuitOn();
	const bool bIn = PlayerHere(P) && !bSuit;
	if (bIn)
	{
		Exposure += Dt;
	}
	if (Director.IsValid())
	{
		Director->SetThreatHint(bSuit ? TEXT("SPORES - THE SUIT HOLDS") : TEXT("SPORES IN THE AIR"), FMath::Min(1.f, Exposure / SporeGrace));
	}
	if (bIn && Exposure >= SporeGrace)
	{
		Ticker += Dt;
		if (Ticker >= SporeTick)
		{
			Ticker = 0.f;
			Hurt(TEXT("The spores scratch at your lungs."), P, SporeDamage, false);
		}
	}
}

// ---------- разгерметизация ----------

void ARunThreat::SetupVacuum()
{
	// аварийный свет — тусклый красный; обломки висят в воздухе и медленно плывут, как без тяжести
	if (Room.IsValid() && !Room->IsEmergency())   // в аварийном свете комната и так красная
	{
		TInlineComponentArray<ULightComponent*> Lights(Room.Get());
		for (ULightComponent* L : Lights)
		{
			L->SetLightColor(FLinearColor(1.f, 0.32f, 0.25f));
			L->SetIntensity(L->Intensity * 0.45f);
		}
	}
	for (int32 I = 0; I < 14; ++I)
	{
		FDebris B;
		B.Radius = 120.f + 280.f * Random01();
		B.Angle = 360.f * Random01();
		B.Height = 50.f + 200.f * Random01();
		B.Speed = 4.f + 6.f * Random01();
		B.Spin = 360.f * Random01();
		const float S = 8.f + 14.f * Random01();
		B.Mesh = AddShape(Cube, Random01() < 0.5f ? MatDark.Get() : MatLight.Get(), FVector(S, S * (0.5f + Random01()), S * 0.3f), Origin);
		Debris.Add(B);
	}
}

void ARunThreat::TickVacuum(float Dt, const FVector& P)
{
	for (FDebris& B : Debris)
	{
		B.Angle = FMath::Fmod(B.Angle + B.Speed * Dt, 360.f);
		B.Spin = FMath::Fmod(B.Spin + 8.f * Dt, 360.f);
		B.Mesh->SetWorldLocationAndRotation(Origin + FRotator(0.f, B.Angle, 0.f).Vector() * B.Radius
			+ FVector(0.f, 0.f, B.Height + 15.f * FMath::Sin(Age * 0.4f + B.Spin)), FRotator(B.Spin, B.Spin * 0.5f, B.Spin * 0.3f));
	}
	const bool bSuit = Director.IsValid() && Director->IsSuitOn();
	if (Director.IsValid())
	{
		Director->SetThreatHint(bSuit ? TEXT("VACUUM - THE SUIT HOLDS") : TEXT("NO AIR - PUT THE SUIT ON"), bSuit ? 0.f : 1.f);
	}
	if (!bSuit && PlayerHere(P))
	{
		Ticker += Dt;
		if (Ticker >= VacuumTick)
		{
			Ticker = 0.f;
			Hurt(TEXT("There is no air. Your lungs burn."), P, VacuumDamage, false);
		}
	}
}

void ARunThreat::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);
	APawn* Pawn = UGameplayStatics::GetPlayerPawn(this, 0);
	if (!Pawn)
	{
		return;
	}
	Age += DeltaSeconds;
	const FVector P = Pawn->GetActorLocation();
	switch (Kind)
	{
	case ThreatBlackHole: TickBlackHole(DeltaSeconds, Pawn); break;
	case ThreatSmoke: TickSmoke(DeltaSeconds, P); break;
	case ThreatSlowTime: TickSlowTime(DeltaSeconds, Pawn, P); break;
	case ThreatFungus: TickFungus(DeltaSeconds, P); break;
	case Decompression: TickVacuum(DeltaSeconds, P); break;
	default: break;
	}
}
