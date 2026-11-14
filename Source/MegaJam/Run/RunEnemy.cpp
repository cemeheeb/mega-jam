#include "RunEnemy.h"

#include "Components/StaticMeshComponent.h"
#include "Components/TextRenderComponent.h"
#include "Engine/StaticMesh.h"
#include "Engine/World.h"
#include "GameFramework/Pawn.h"
#include "Kismet/GameplayStatics.h"
#include "Materials/MaterialInterface.h"
#include "RunDirector.h"
#include "RunGen.h"
#include "UObject/ConstructorHelpers.h"

using namespace RunGen;
using namespace RunEnemyTune;

ARunEnemy::ARunEnemy()
{
	PrimaryActorTick.bCanEverTick = true;
	SetRootComponent(CreateDefaultSubobject<USceneComponent>(TEXT("Root")));
	static ConstructorHelpers::FObjectFinder<UStaticMesh> Cube(TEXT("/Engine/BasicShapes/Cube.Cube"));
	static ConstructorHelpers::FObjectFinder<UMaterialInterface> Dark(TEXT("/Game/Game/Materials/MI_Gray_Dark.MI_Gray_Dark"));
	static ConstructorHelpers::FObjectFinder<UMaterialInterface> Hot(TEXT("/Game/Game/Materials/MI_Gray_Door.MI_Gray_Door"));
	static ConstructorHelpers::FObjectFinder<UMaterialInterface> Pale(TEXT("/Game/Game/Materials/MI_Gray_Linen.MI_Gray_Linen"));
	MatDark = Dark.Succeeded() ? Dark.Object : nullptr;
	MatHot = Hot.Succeeded() ? Hot.Object : nullptr;
	MatPale = Pale.Succeeded() ? Pale.Object : nullptr;

	Body = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("Body"));
	Head = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("Head"));
	for (UStaticMeshComponent* M : { Body.Get(), Head.Get() })
	{
		M->SetupAttachment(RootComponent);
		M->SetMobility(EComponentMobility::Movable);
		M->SetCollisionProfileName(TEXT("NoCollision"));
		M->SetReceivesDecals(false);
		if (Cube.Succeeded())
		{
			M->SetStaticMesh(Cube.Object);
		}
	}
	Label = CreateDefaultSubobject<UTextRenderComponent>(TEXT("Label"));
	Label->SetupAttachment(RootComponent);
	Label->SetHorizontalAlignment(EHTA_Center);
	Label->SetWorldSize(16.f);
	Label->SetTextRenderColor(FColor(255, 70, 40));
}

const TCHAR* ARunEnemy::DisplayName(int32 InKind)
{
	return InKind == ThreatHuman ? TEXT("Another you") : InKind == ThreatRobot ? TEXT("Mad maintenance robot") : TEXT("Rat");
}

int32 ARunEnemy::StartHealth(int32 InKind)
{
	return InKind == ThreatHuman ? HumanHealth : InKind == ThreatRobot ? RobotHealth : RatHealth;
}

void ARunEnemy::Setup(int32 InKind, int32 InEnemyId, ARunDirector* InDirector, const FVector& FloorPos, int32 Health, float StartStun)
{
	Kind = InKind;
	EnemyId = InEnemyId;
	Director = InDirector;
	Pos = FloorPos;
	Stun = StartStun;
	if (const APawn* Pawn = UGameplayStatics::GetPlayerPawn(this, 0))
	{
		const FVector To = (Pawn->GetActorLocation() - Pos).GetSafeNormal2D();   // сразу лицом к игроку
		Dir = To.IsNearlyZero() ? Dir : To;
	}
	// размеры тела и головы в сантиметрах
	FVector BodySize(70, 70, 150), HeadSize(46, 46, 30);
	UMaterialInterface* BodyMat = MatDark;
	UMaterialInterface* HeadMat = MatHot;
	if (Kind == ThreatHuman)
	{
		BodySize = FVector(34, 52, 140);
		HeadSize = FVector(26, 26, 28);
		HeadMat = MatPale;   // «другая версия игрока»: тёмный силуэт со светлой головой, на светлых стенах его видно
		Radius = 32.f;
	}
	else if (Kind == ThreatRats)
	{
		BodySize = FVector(42, 18, 18);
		HeadSize = FVector(12, 12, 12);
		HeadMat = MatDark;
		Radius = 16.f;
	}
	else
	{
		Radius = 38.f;
	}
	HalfHeight = BodySize.Z * 0.5f;
	Body->SetWorldScale3D(BodySize / 100.f);
	Head->SetWorldScale3D(HeadSize / 100.f);
	if (BodyMat)
	{
		Body->SetMaterial(0, BodyMat);
	}
	if (HeadMat)
	{
		Head->SetMaterial(0, HeadMat);
	}
	ShowHealth(Health);
	Place();
}

void ARunEnemy::ShowHealth(int32 Health)
{
	FString Pips;
	for (int32 I = 0; I < Health; ++I)
	{
		Pips += TEXT("#");
	}
	Label->SetText(FText::FromString(Kind == ThreatRats ? FString() : Pips));
}

void ARunEnemy::Place()
{
	SetActorLocation(Pos);
	const FRotator Rot(0.f, Dir.Rotation().Yaw, 0.f);
	Body->SetWorldLocationAndRotation(Pos + FVector(0, 0, HalfHeight), Rot);
	const float HeadZ = Kind == ThreatRats ? HalfHeight : HalfHeight * 2.f + Head->GetComponentScale().Z * 50.f;
	Head->SetWorldLocationAndRotation(Pos + (Kind == ThreatRats ? Dir * 24.f : FVector::ZeroVector) + FVector(0, 0, HeadZ), Rot);
	Label->SetWorldLocation(Pos + FVector(0, 0, HalfHeight * 2.f + 55.f));
	if (const APlayerCameraManager* Cam = UGameplayStatics::GetPlayerCameraManager(this, 0))
	{
		Label->SetWorldRotation(FRotator(0.f, (Cam->GetCameraLocation() - Label->GetComponentLocation()).Rotation().Yaw, 0.f));
	}
}

float ARunEnemy::Move(const FVector& Delta, const AActor* Ignore)
{
	const FVector Before = Pos;
	// Шаг с проверкой препятствий: упёрся — скользит вдоль стены или мебели. Навигационной сетки нет.
	FCollisionQueryParams Params(FName(TEXT("RunEnemy")), false, this);
	if (Ignore)
	{
		Params.AddIgnoredActor(Ignore);
	}
	const FCollisionShape Shape = FCollisionShape::MakeSphere(Radius);
	// низ сферы на 16 см от пола — как у сетки обхода: низкий подиум не мешает, мебель мешает
	const FVector Lift(0, 0, Radius + 16.f);
	FVector Step(Delta.X, Delta.Y, 0.f);
	for (int32 Pass = 0; Pass < 2 && !Step.IsNearlyZero(0.01f); ++Pass)
	{
		FHitResult Hit;
		const FVector From = Pos + Lift;
		if (!GetWorld()->SweepSingleByChannel(Hit, From, From + Step, FQuat::Identity, ECC_WorldStatic, Shape, Params))
		{
			Pos += Step;
			break;
		}
		if (Hit.bStartPenetrating)
		{
			Pos += Step;   // застрял внутри препятствия (например, на нём закрылась створка): дать выйти
			break;
		}
		Pos += Step * FMath::Max(0.f, Hit.Time - 0.02f);
		const FVector N = FVector(Hit.ImpactNormal.X, Hit.ImpactNormal.Y, 0.f).GetSafeNormal2D();
		const FVector Rest = Step * (1.f - Hit.Time);
		Step = Rest - N * FVector::DotProduct(Rest, N);
	}
	return FVector::Dist2D(Before, Pos);
}

void ARunEnemy::Walk(const FVector& WantDir, float Speed, float Dt, const AActor* Ignore)
{
	if (DetourLeft > 0.f)
	{
		DetourLeft -= Dt;
		Move(DetourDir * Speed * Dt, Ignore);
		return;
	}
	const float Want = Speed * Dt;
	const float Done = Move(WantDir * Want, Ignore);
	StuckTime = Done < Want * 0.3f ? StuckTime + Dt : FMath::Max(0.f, StuckTime - Dt);
	if (StuckTime > 0.35f)
	{
		// прямой путь закрыт мебелью: полсекунды идём вбок, каждый раз в другую сторону
		StuckTime = 0.f;
		DetourLeft = 0.6f;
		bDetourFlip = !bDetourFlip;
		DetourDir = FVector(-WantDir.Y, WantDir.X, 0.f) * (bDetourFlip ? 1.f : -1.f);
	}
}

void ARunEnemy::Knock(const FVector& From, float StunSeconds)
{
	Stun = FMath::Max(Stun, StunSeconds);
	bFlee = false;
	Push = FVector(Pos.X - From.X, Pos.Y - From.Y, 0.f).GetSafeNormal2D() * 420.f;
}

void ARunEnemy::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);
	APawn* Pawn = UGameplayStatics::GetPlayerPawn(this, 0);
	if (!Pawn || !Director.IsValid() || Director->GetPhase() != ERunPhase::Playing)
	{
		return;
	}
	const FVector P = Pawn->GetActorLocation();
	const FVector To(P.X - Pos.X, P.Y - Pos.Y, 0.f);
	const float Dist = To.Size2D();
	// куда идти: прямо к игроку или сначала к двери, если между ними стена тамбура
	const FVector Aim = Director->SteerTarget(Pos, P);
	const FVector Want = FVector(Aim.X - Pos.X, Aim.Y - Pos.Y, 0.f).GetSafeNormal2D();

	if (!Push.IsNearlyZero(1.f))
	{
		Move(Push * DeltaSeconds, Pawn);
		Push *= FMath::Max(0.f, 1.f - 6.f * DeltaSeconds);
	}
	if (Stun > 0.f)
	{
		Stun -= DeltaSeconds;
		if (bFlee && Push.IsNearlyZero(1.f))
		{
			Move(Dir * RatSpeed * 0.7f * DeltaSeconds, Pawn);   // после укуса крыса отбегает
		}
		Place();
		return;
	}

	bFlee = false;
	if (Kind == ThreatRats)
	{
		// поворот с ограниченной скоростью: на бегу крыса проскакивает мимо
		const float WantYaw = Want.Rotation().Yaw;
		const float Have = Dir.Rotation().Yaw;
		const float Turn = FMath::Clamp(FMath::FindDeltaAngleDegrees(Have, WantYaw), -RatTurnDegPerSec * DeltaSeconds, RatTurnDegPerSec * DeltaSeconds);
		Dir = FRotator(0.f, Have + Turn, 0.f).Vector();
		Walk(Dir, RatSpeed, DeltaSeconds, Pawn);
		if (Dist < RatReach)
		{
			Director->HurtPlayer(TEXT("A rat bites you."), Pos, RatDamage);
			Stun = RatScatter;
			bFlee = true;
			Dir = -To.GetSafeNormal2D();
		}
	}
	else
	{
		const bool bHuman = Kind == ThreatHuman;
		if (!Want.IsNearlyZero())
		{
			Dir = Want;
		}
		Walk(Dir, bHuman ? HumanSpeed : RobotSpeed, DeltaSeconds, Pawn);
		if (Dist < (bHuman ? HumanReach : RobotReach))
		{
			Director->HurtPlayer(bHuman ? TEXT("The other you gets its hands on you.") : TEXT("The maintenance robot slams into you."), Pos,
				bHuman ? HumanDamage : RobotDamage);
			Stun = bHuman ? HumanStun : RobotStun;
		}
	}
	Place();
}
