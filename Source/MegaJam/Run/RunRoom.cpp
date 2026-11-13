#include "RunRoom.h"

#include "Components/StaticMeshComponent.h"
#include "GameFramework/Pawn.h"
#include "Kismet/GameplayStatics.h"
#include "RunDirector.h"

namespace RunRoomGeo
{
	FVector Dir(int32 Door)
	{
		static const FVector Dirs[4] = { FVector(1, 0, 0), FVector(-1, 0, 0), FVector(0, -1, 0), FVector(0, 1, 0) };
		return Dirs[Door];
	}

	FVector Slide(int32 Door)
	{
		return Door < 2 ? FVector(0, 1, 0) : FVector(1, 0, 0);
	}

	float OuterFace(int32 Door)
	{
		return (Door < 2 ? HalfX : HalfY) + Wall;
	}

	int32 Opposite(int32 Door)
	{
		return Door ^ 1;
	}

	FVector NeighborOffset(int32 Door)
	{
		return Dir(Door) * (2.f * OuterFace(Door) + VestibuleDepth);
	}

	const TCHAR* DoorName(int32 Door)
	{
		static const TCHAR* const Names[4] = { TEXT("N"), TEXT("S"), TEXT("W"), TEXT("E") };
		return Names[Door];
	}
}

using namespace RunRoomGeo;

ARunRoom::ARunRoom()
{
	PrimaryActorTick.bCanEverTick = true;
	Root = CreateDefaultSubobject<USceneComponent>(TEXT("Root"));
	SetRootComponent(Root);
}

void ARunRoom::BeginPlay()
{
	Super::BeginPlay();
	TInlineComponentArray<UStaticMeshComponent*> Meshes(this);
	for (int32 D = 0; D < 4; ++D)
	{
		const FString Name = FString::Printf(TEXT("%s_DoorInner"), DoorName(D));
		for (UStaticMeshComponent* M : Meshes)
		{
			if (M->GetName() == Name)
			{
				Leaf[D] = M;
				M->SetMobility(EComponentMobility::Movable);
				LeafClosed[D] = M->GetRelativeLocation();
				break;
			}
		}
		if (!Leaf[D])
		{
			UE_LOG(LogTemp, Warning, TEXT("RunRoom %s: нет створки %s"), *GetName(), *Name);
		}
	}
}

void ARunRoom::SetArrivalDoor(int32 Door)
{
	if (Door >= 0 && Door < 4)
	{
		bArrival[Door] = true;
	}
}

FVector ARunRoom::VestibuleCenter(int32 Door) const
{
	return GetActorLocation() + Dir(Door) * (OuterFace(Door) + VestibuleDepth * 0.6f);
}

TArray<FVector> ARunRoom::GetSpots(const TCHAR* Prefix) const
{
	TArray<FVector> Out;
	TInlineComponentArray<USceneComponent*> Comps(this);
	Comps.Sort([](const USceneComponent& A, const USceneComponent& B) { return A.GetName() < B.GetName(); });
	for (const USceneComponent* C : Comps)
	{
		if (C->GetName().StartsWith(Prefix))
		{
			Out.Add(C->GetComponentLocation());
		}
	}
	return Out;
}

bool ARunRoom::AllLeavesClosed() const
{
	for (int32 D = 0; D < 4; ++D)
	{
		if (LeafOpen[D] > 0.01f)
		{
			return false;
		}
	}
	return true;
}

void ARunRoom::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);

	const APawn* Pawn = UGameplayStatics::GetPlayerPawn(this, 0);
	const FVector Local = Pawn ? Pawn->GetActorLocation() - GetActorLocation() : FVector(0, 0, -100000);
	const bool bPawnHere = Pawn && Local.Z > -50.f && Local.Z < 400.f;

	for (int32 D = 0; D < 4; ++D)
	{
		const float Along = FVector::DotProduct(Local, Dir(D));
		const float Lateral = FMath::Abs(FVector::DotProduct(Local, Slide(D)));
		const float Outer = OuterFace(D);
		const float Inner = Outer - Wall;
		// у двери со стороны комнаты; в проёме и первых 90 см тамбура; в глубине тамбура
		const bool bApproach = bPawnHere && Along > Inner - 220.f && Along <= Inner && Lateral < 150.f;
		const bool bDoorway = bPawnHere && Along > Inner && Along <= Outer + 90.f && Lateral < VestibuleWidth * 0.5f;
		const bool bDeep = bPawnHere && Along > Outer + 90.f && Along < Outer + VestibuleDepth + Wall && Lateral < VestibuleWidth * 0.5f + Wall;

		if (bArrival[D] && !bDeep && !bDoorway)
		{
			bArrival[D] = false;   // игрок вышел из тамбура в комнату
		}
		if (bDeep && !bArrival[D] && !bSealed && Director.IsValid())
		{
			Director->BeginTransition(this, D);   // ставит bSealed
		}

		const bool bWantOpen = !bSealed && (bApproach || bDoorway || bArrival[D]);
		LeafOpen[D] = FMath::Clamp(LeafOpen[D] + (bWantOpen ? 1.f : -1.f) * DeltaSeconds / 0.6f, 0.f, 1.f);
		if (Leaf[D])
		{
			const float Eased = FMath::SmoothStep(0.f, 1.f, LeafOpen[D]);
			Leaf[D]->SetRelativeLocation(LeafClosed[D] + Slide(D) * DoorWidth * Eased);
		}
	}
}
