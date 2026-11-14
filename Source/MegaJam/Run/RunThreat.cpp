#include "RunThreat.h"

#include "Components/StaticMeshComponent.h"
#include "Engine/StaticMesh.h"
#include "Engine/World.h"
#include "GameFramework/Pawn.h"
#include "Kismet/GameplayStatics.h"
#include "Materials/MaterialInterface.h"
#include "RunDirector.h"
#include "RunGen.h"
#include "RunRoom.h"
#include "UObject/ConstructorHelpers.h"

using namespace RunGen;
using namespace RunThreatTune;

namespace
{
	// комната внутри, чуть меньше стен: сюда ставятся зоны и здесь бьют разряды
	constexpr float InX = RunRoomGeo::HalfX;
	constexpr float InY = RunRoomGeo::HalfY;

	bool InsideRoom(const FVector& Local)
	{
		return FMath::Abs(Local.X) < InX && FMath::Abs(Local.Y) < InY;
	}
}

ARunThreat::ARunThreat()
{
	PrimaryActorTick.bCanEverTick = true;
	SetRootComponent(CreateDefaultSubobject<USceneComponent>(TEXT("Root")));
	static ConstructorHelpers::FObjectFinder<UStaticMesh> CubeMesh(TEXT("/Engine/BasicShapes/Cube.Cube"));
	static ConstructorHelpers::FObjectFinder<UStaticMesh> CylinderMesh(TEXT("/Engine/BasicShapes/Cylinder.Cylinder"));
	static ConstructorHelpers::FObjectFinder<UMaterialInterface> Hot(TEXT("/Game/Game/Materials/MI_Gray_Door.MI_Gray_Door"));
	static ConstructorHelpers::FObjectFinder<UMaterialInterface> Dark(TEXT("/Game/Game/Materials/MI_Gray_Dark.MI_Gray_Dark"));
	static ConstructorHelpers::FObjectFinder<UMaterialInterface> Glow(TEXT("/Game/Game/Materials/MI_Gray_Glow.MI_Gray_Glow"));
	static ConstructorHelpers::FObjectFinder<UMaterialInterface> Green(TEXT("/Game/Game/Materials/MI_Gray_Plant.MI_Gray_Plant"));
	static ConstructorHelpers::FObjectFinder<UMaterialInterface> Light(TEXT("/Game/Game/Materials/MI_Gray_Linen.MI_Gray_Linen"));
	Cube = CubeMesh.Succeeded() ? CubeMesh.Object : nullptr;
	Cylinder = CylinderMesh.Succeeded() ? CylinderMesh.Object : nullptr;
	MatHot = Hot.Succeeded() ? Hot.Object : nullptr;
	MatDark = Dark.Succeeded() ? Dark.Object : nullptr;
	MatGlow = Glow.Succeeded() ? Glow.Object : nullptr;
	MatGreen = Green.Succeeded() ? Green.Object : nullptr;
	MatLight = Light.Succeeded() ? Light.Object : nullptr;
}

bool ARunThreat::IsAnomaly(int32 InKind)
{
	return (InKind >= ThreatFrozenMoment && InKind <= ThreatSlowTime) || InKind == ThreatEcho;
}

const TCHAR* ARunThreat::DisplayName(int32 InKind)
{
	static const TCHAR* const Names[] = { TEXT("Nothing"), TEXT("Frozen moment"), TEXT("Radiation"), TEXT("Gravity failure"),
		TEXT("Slow time"), TEXT("Mad maintenance robot"), TEXT("Rats"), TEXT("Echo"), TEXT("Another you") };
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

FVector ARunThreat::RandomFloorPoint(const FVector& Avoid, float AvoidRadius)
{
	FVector Pt = Origin;
	for (int32 Try = 0; Try < 12; ++Try)
	{
		Pt = Origin + FVector((Random01() * 2.f - 1.f) * (InX - 110.f), (Random01() * 2.f - 1.f) * (InY - 110.f), 0.f);
		if (FVector::Dist2D(Pt, Avoid) > AvoidRadius)
		{
			break;
		}
	}
	return Pt;
}

void ARunThreat::Setup(int32 InKind, ARunDirector* InDirector, const FVector& InOrigin, int32 ArrivalDoor, uint32 Seed)
{
	Kind = InKind;
	Director = InDirector;
	Origin = InOrigin;
	Rand = Seed | 1U;
	SetActorLocation(Origin);
	// место, где игрок выходит из тамбура: рядом с ним ничего опасного не ставим
	const FVector Entry = ArrivalDoor >= 0
		? Origin + RunRoomGeo::Dir(ArrivalDoor) * (RunRoomGeo::OuterFace(ArrivalDoor) - RunRoomGeo::Wall - 60.f) : Origin;

	if (Kind == ThreatRobot || Kind == ThreatRats || Kind == ThreatHuman)
	{
		// противников создаёт ведущий забега, см. RunEnemy
	}
	else if (Kind == ThreatEcho)
	{
		FBody B;
		B.Pos = Entry;
		B.Mesh = AddShape(Cube, MatGlow, FVector(50, 50, 170), B.Pos);
		B.Mesh->SetVisibility(false);
		Bodies.Add(B);
	}
	else if (Kind == ThreatFrozenMoment)
	{
		const float XS[2] = { -200.f, 200.f };
		const float YS[2] = { -150.f, 150.f };
		for (int32 I = 0; I < 2; ++I)
		{
			Bars.Add({ true, XS[I], I * BarCycle * 0.5f, AddShape(Cube, MatHot, FVector(8, InY * 2.f, 6), Origin + FVector(XS[I], 0, 3)) });
			Bars.Add({ false, YS[I], I * BarCycle * 0.5f + BarCycle * 0.25f, AddShape(Cube, MatHot, FVector(InX * 2.f, 8, 6), Origin + FVector(0, YS[I], 3)) });
		}
	}
	else if (Kind == ThreatRadiation)
	{
		for (int32 I = 0; I < RadiationZones; ++I)
		{
			FZone Z;
			Z.Radius = RadiationRadius;
			Z.Center = RandomFloorPoint(Entry, 230.f);
			Z.Mesh = AddShape(Cylinder, MatGreen, FVector(Z.Radius * 2.f, Z.Radius * 2.f, 1.5f), Z.Center + FVector(0, 0, 1.f));
			Zones.Add(Z);
		}
	}
	else if (Kind == ThreatGravityFailure)
	{
		// четыре полосы вдоль стен: светится та, к которой сейчас тянет. Порядок как у дверей: N, S, W, E
		Bars.Add({ true, InX - 6.f, 0.f, AddShape(Cube, MatHot, FVector(10, InY * 2.f, 60), Origin + FVector(InX - 6.f, 0, 30)) });
		Bars.Add({ true, -InX + 6.f, 0.f, AddShape(Cube, MatHot, FVector(10, InY * 2.f, 60), Origin + FVector(-InX + 6.f, 0, 30)) });
		Bars.Add({ false, -InY + 6.f, 0.f, AddShape(Cube, MatHot, FVector(InX * 2.f, 10, 60), Origin + FVector(0, -InY + 6.f, 30)) });
		Bars.Add({ false, InY - 6.f, 0.f, AddShape(Cube, MatHot, FVector(InX * 2.f, 10, 60), Origin + FVector(0, InY - 6.f, 30)) });
		for (FBar& B : Bars)
		{
			B.Mesh->SetVisibility(false);
		}
	}
	else if (Kind == ThreatSlowTime)
	{
		for (int32 I = 0; I < SlowZones; ++I)
		{
			FZone Z;
			Z.Radius = SlowRadius;
			Z.Center = RandomFloorPoint(Entry, 260.f);
			Z.Mesh = AddShape(Cylinder, MatGlow, FVector(Z.Radius * 2.f, Z.Radius * 2.f, 1.5f), Z.Center + FVector(0, 0, 1.f));
			Zones.Add(Z);
		}
		// луч начинает с направления от двери, через которую пришёл игрок
		ArmAngle = (Origin - Entry).GetSafeNormal2D().Rotation().Yaw;
		Bars.Add({ true, 0.f, 0.f, AddShape(Cube, MatHot, FVector(ArmLength - ArmInner, 14, 200), Origin) });
	}
}

void ARunThreat::Hurt(const TCHAR* Text, const FVector& From)
{
	if (Director.IsValid())
	{
		Director->HurtPlayer(Text, From);
	}
}

void ARunThreat::TickEcho(float Dt, const FVector& P)
{
	Trail.Add(TPair<float, FVector>(Age, P));
	const float Then = Age - EchoDelay;
	int32 Drop = 0;
	while (Drop + 1 < Trail.Num() && Trail[Drop + 1].Key <= Then)
	{
		++Drop;
	}
	if (Drop > 0)
	{
		Trail.RemoveAt(0, Drop);
	}
	FBody& B = Bodies[0];
	if (Then < 0.f)
	{
		return;   // эхо ещё не появилось
	}
	B.Mesh->SetVisibility(true);
	const FVector Was = Trail[0].Value;
	B.Dir = FVector(Was.X - B.Pos.X, Was.Y - B.Pos.Y, 0.f).GetSafeNormal2D();
	B.Pos = FVector(Was.X, Was.Y, Origin.Z);
	B.HalfHeight = 85.f;
	B.Mesh->SetWorldLocation(FVector(B.Pos.X, B.Pos.Y, Origin.Z + B.HalfHeight));
	if (FVector::Dist2D(B.Pos, P) < EchoReach)
	{
		Hurt(TEXT("Your own echo walks through you."), B.Pos);
	}
}

void ARunThreat::TickBars(const FVector& Local)
{
	for (FBar& B : Bars)
	{
		const float T = FMath::Fmod(Age + B.Phase, BarCycle);
		const bool bOn = T < BarOn;
		const bool bWarn = T > BarCycle - BarWarn;
		B.Mesh->SetVisibility(bOn || bWarn);
		// предупреждение — тонкая полоска на полу, разряд — стена до потолка
		const float Thick = bOn ? 24.f : 8.f, Tall = bOn ? 230.f : 6.f;
		B.Mesh->SetWorldScale3D(B.bSpansY ? FVector(Thick, InY * 2.f, Tall) / 100.f : FVector(InX * 2.f, Thick, Tall) / 100.f);
		B.Mesh->SetWorldLocation(Origin + (B.bSpansY ? FVector(B.Coord, 0, Tall * 0.5f) : FVector(0, B.Coord, Tall * 0.5f)));
		const float Dist = FMath::Abs((B.bSpansY ? Local.X : Local.Y) - B.Coord);
		if (bOn && Dist < BarHalfWidth && InsideRoom(Local) && Age > EntryGrace)
		{
			Hurt(TEXT("The discharge catches you."), Origin + (B.bSpansY ? FVector(B.Coord, Local.Y, 0) : FVector(Local.X, B.Coord, 0)));
		}
	}
}

void ARunThreat::TickRadiation(float Dt, const FVector& P)
{
	bool bIn = false;
	for (const FZone& Z : Zones)
	{
		bIn |= FVector::Dist2D(P, Z.Center) < Z.Radius;
	}
	Exposure = bIn ? Exposure + Dt : FMath::Max(0.f, Exposure - Dt * 0.5f);
	if (Director.IsValid())
	{
		Director->SetThreatHint(bIn ? TEXT("RADIATION - get out of the hot spot") : TEXT("RADIATION"), Exposure / RadiationDose);
	}
	if (Exposure >= RadiationDose)
	{
		Exposure = 0.f;
		Hurt(TEXT("Radiation burns through you."), P);
	}
}

void ARunThreat::TickGravity(float Dt, APawn* Pawn, const FVector& Local)
{
	static const TCHAR* const Sides[4] = { TEXT("NORTH"), TEXT("SOUTH"), TEXT("WEST"), TEXT("EAST") };
	const int32 Step = FMath::FloorToInt(Age / GravityCycle);
	if (Step != GravityStep)
	{
		GravityStep = Step;
		GravityDir = static_cast<int32>(Random01() * 4.f) & 3;
	}
	const float T = Age - Step * GravityCycle;
	const bool bPull = T > GravityWarn;
	for (int32 I = 0; I < Bars.Num(); ++I)
	{
		Bars[I].Mesh->SetVisibility(I == GravityDir);
		const float Tall = bPull ? 120.f : 30.f;
		const FVector S = Bars[I].bSpansY ? FVector(10, InY * 2.f, Tall) : FVector(InX * 2.f, 10, Tall);
		Bars[I].Mesh->SetWorldScale3D(S / 100.f);
	}
	if (Director.IsValid())
	{
		const FString Hint = bPull ? FString::Printf(TEXT("GRAVITY PULLS %s"), Sides[GravityDir])
			: FString::Printf(TEXT("GRAVITY SHIFT TO %s..."), Sides[GravityDir]);
		Director->SetThreatHint(Hint, bPull ? 1.f : T / GravityWarn);
	}
	if (!bPull || !InsideRoom(Local))
	{
		return;
	}
	const FVector Pull = RunRoomGeo::Dir(GravityDir);
	Pawn->AddActorWorldOffset(Pull * GravityPull * Dt, true);
	const float ToWall = (GravityDir < 2 ? InX : InY) - FVector::DotProduct(Local, Pull);
	if (ToWall < GravityWallReach)
	{
		Hurt(TEXT("Gravity slams you into the live wall."), Pawn->GetActorLocation() + Pull * 100.f);
	}
}

void ARunThreat::TickSlowTime(float Dt, const FVector& P, const FVector& Local)
{
	bool bIn = false;
	for (const FZone& Z : Zones)
	{
		bIn |= FVector::Dist2D(P, Z.Center) < Z.Radius;
	}
	if (Director.IsValid())
	{
		if (bIn)
		{
			Director->RequestSpeedFactor(SlowFactor);
		}
		Director->SetThreatHint(bIn ? TEXT("TIME IS THICK HERE") : TEXT("SLOW TIME"), bIn ? 1.f : 0.f);
	}
	ArmAngle = FMath::Fmod(ArmAngle + ArmDegPerSec * Dt, 360.f);
	const FVector ArmDir = FRotator(0.f, ArmAngle, 0.f).Vector();
	const float Mid = (ArmInner + ArmLength) * 0.5f;
	Bars[0].Mesh->SetWorldLocation(Origin + ArmDir * Mid + FVector(0, 0, 100));
	Bars[0].Mesh->SetWorldRotation(FRotator(0.f, ArmAngle, 0.f));
	// попадание: игрок рядом с отрезком луча
	const FVector Flat(Local.X, Local.Y, 0.f);
	const float Along = FVector::DotProduct(Flat, ArmDir);
	const float Side = FMath::Abs(FVector::CrossProduct(ArmDir, Flat).Z);
	if (Along > ArmInner && Along < ArmLength && Side < BarHalfWidth && InsideRoom(Local) && Age > EntryGrace)
	{
		Hurt(TEXT("The beam sweeps over you while time drags."), Origin + ArmDir * Along);
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
	const FVector Local = P - Origin;
	switch (Kind)
	{
	case ThreatEcho: TickEcho(DeltaSeconds, P); break;
	case ThreatFrozenMoment: TickBars(Local); break;
	case ThreatRadiation: TickRadiation(DeltaSeconds, P); break;
	case ThreatGravityFailure: TickGravity(DeltaSeconds, Pawn, Local); break;
	case ThreatSlowTime: TickSlowTime(DeltaSeconds, P, Local); break;
	default: break;
	}
}
