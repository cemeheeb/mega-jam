#include "RunRoom.h"

#include "Engine/StaticMesh.h"
#include "Materials/MaterialInterface.h"
#include "Components/TextRenderComponent.h"
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

	float InnerFace(int32 Door)
	{
		return Door < 2 ? HalfX : HalfY;
	}

	float OuterFace(int32 Door)
	{
		return InnerFace(Door) + Lining + Wall;
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

void ARunRoom::SetDoorSign(int32 Door, const FString& Text)
{
	if (Door < 0 || Door >= 4)
	{
		return;
	}
	if (!Sign[Door])
	{
		// табло создаётся на ходу: блюпринты комнат менять не нужно
		UTextRenderComponent* T = NewObject<UTextRenderComponent>(this);
		T->SetupAttachment(GetRootComponent());
		T->RegisterComponent();
		T->SetHorizontalAlignment(EHTA_Center);
		T->SetVerticalAlignment(EVRTA_TextCenter);
		T->SetWorldSize(30.f);
		// на лице перемычки над проёмом (2,5–3 м), она стоит вровень с колонками
		T->SetRelativeLocation(Dir(Door) * (InnerFace(Door) - 5.f) + FVector(0.f, 0.f, 275.f));
		T->SetRelativeRotation((-Dir(Door)).Rotation());   // текст смотрит внутрь комнаты
		Sign[Door] = T;
		// тёмная плашка под текстом: стены светлые, без неё табло не читается
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
		Plate->SetRelativeLocation(Dir(Door) * (InnerFace(Door) - 1.5f) + FVector(0.f, 0.f, 275.f));
		Plate->SetRelativeRotation((-Dir(Door)).Rotation());
		Plate->SetRelativeScale3D(FVector(0.03f, 2.3f, 0.42f));
	}
	bSignKnown[Door] = !Text.IsEmpty();
	Sign[Door]->SetText(FText::FromString(bSignKnown[Door] ? Text : FString(TEXT("-  -  -"))));
	Sign[Door]->SetTextRenderColor(bSignKnown[Door] ? FColor(95, 198, 201) : FColor(230, 230, 230));
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

TArray<FTransform> ARunRoom::TakeFirstAidCases()
{
	TArray<FTransform> Out;
	TInlineComponentArray<UStaticMeshComponent*> Comps(this);
	Comps.Sort([](const UStaticMeshComponent& A, const UStaticMeshComponent& B) { return A.GetName() < B.GetName(); });
	for (UStaticMeshComponent* C : Comps)
	{
		if (C->GetName().EndsWith(TEXT("_FirstAid")))
		{
			Out.Add(C->GetComponentTransform());
			C->SetVisibility(false);
			C->SetCollisionEnabled(ECollisionEnabled::NoCollision);
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

void ARunRoom::OpenFor(int32 Door, float Seconds)
{
	if (Door >= 0 && Door < 4)
	{
		ForcedOpenLeft[Door] = FMath::Max(ForcedOpenLeft[Door], Seconds);
	}
}

int32 ARunRoom::VestibuleOf(const FVector& WorldPos) const
{
	const FVector Local = WorldPos - GetActorLocation();
	for (int32 D = 0; D < 4; ++D)
	{
		if (FVector::DotProduct(Local, Dir(D)) > InnerFace(D))   // за лицом колонок есть только проём и тамбур
		{
			return D;
		}
	}
	return -1;
}

void ARunRoom::BuildNav()
{
	bNavBuilt = true;
	NavGoal = -1;
	FCollisionQueryParams Params(FName(TEXT("RunNav")), false);
	if (const APawn* Pawn = UGameplayStatics::GetPlayerPawn(this, 0))
	{
		Params.AddIgnoredActor(Pawn);
	}
	const FCollisionShape Body = FCollisionShape::MakeSphere(36.f);
	for (int32 Cell = 0; Cell < NavCells; ++Cell)
	{
		NavFree[Cell] = !GetWorld()->OverlapBlockingTestByChannel(NavCenter(Cell) + FVector(0, 0, 50.f), FQuat::Identity, ECC_WorldStatic, Body, Params);
	}
}

FVector ARunRoom::NavCenter(int32 Cell) const
{
	return GetActorLocation() + FVector(-HalfX + 25.f + 50.f * (Cell / NavNY), -HalfY + 25.f + 50.f * (Cell % NavNY), 0.f);
}

// Клетка точки; если она занята мебелью — ближайшая свободная рядом. −1 — рядом свободных нет.
int32 ARunRoom::NavCellAt(const FVector& Local) const
{
	const int32 CX = FMath::Clamp(FMath::FloorToInt32((Local.X + HalfX) / 50.f), 0, NavNX - 1);
	const int32 CY = FMath::Clamp(FMath::FloorToInt32((Local.Y + HalfY) / 50.f), 0, NavNY - 1);
	int32 Best = -1;
	float BestDist = 0.f;
	for (int32 X = FMath::Max(0, CX - 3); X <= FMath::Min(NavNX - 1, CX + 3); ++X)
	{
		for (int32 Y = FMath::Max(0, CY - 3); Y <= FMath::Min(NavNY - 1, CY + 3); ++Y)
		{
			const int32 Cell = X * NavNY + Y;
			const float D = FVector::DistSquared2D(NavCenter(Cell) - GetActorLocation(), Local);
			if (NavFree[Cell] && (Best < 0 || D < BestDist))
			{
				Best = Cell;
				BestDist = D;
			}
		}
	}
	return Best;
}

// Расстояния от всех клеток до клетки цели: шаг по прямой 10, по диагонали 14, углы мебели не срезаются.
void ARunRoom::NavFlood(int32 Goal)
{
	NavGoal = Goal;
	for (int32& D : NavDist)
	{
		D = MAX_int32;
	}
	TArray<int32, TInlineAllocator<NavCells>> Queue;
	NavDist[Goal] = 0;
	Queue.Add(Goal);
	for (int32 Head = 0; Head < Queue.Num(); ++Head)
	{
		const int32 Cell = Queue[Head], X = Cell / NavNY, Y = Cell % NavNY;
		for (int32 DX = -1; DX <= 1; ++DX)
		{
			for (int32 DY = -1; DY <= 1; ++DY)
			{
				const int32 NX = X + DX, NY = Y + DY;
				if ((DX == 0 && DY == 0) || NX < 0 || NY < 0 || NX >= NavNX || NY >= NavNY || !NavFree[NX * NavNY + NY])
				{
					continue;
				}
				if (DX != 0 && DY != 0 && (!NavFree[NX * NavNY + Y] || !NavFree[X * NavNY + NY]))
				{
					continue;
				}
				const int32 Next = NX * NavNY + NY, Cost = NavDist[Cell] + (DX != 0 && DY != 0 ? 14 : 10);
				if (Cost < NavDist[Next])
				{
					NavDist[Next] = Cost;
					Queue.Add(Next);
				}
			}
		}
		if (Queue.Num() > NavCells * 16)
		{
			break;   // страховка от зацикливания
		}
	}
}

bool ARunRoom::ClearWay(const FVector& From, const FVector& To) const
{
	FCollisionQueryParams Params(FName(TEXT("RunNavWay")), false);
	if (const APawn* Pawn = UGameplayStatics::GetPlayerPawn(this, 0))
	{
		Params.AddIgnoredActor(Pawn);
	}
	const float Z = GetActorLocation().Z + 45.f;
	return !GetWorld()->SweepTestByChannel(FVector(From.X, From.Y, Z), FVector(To.X, To.Y, Z), FQuat::Identity, ECC_WorldStatic,
		FCollisionShape::MakeSphere(30.f), Params);
}

FVector ARunRoom::SteerTarget(const FVector& From, const FVector& To)
{
	const int32 A = VestibuleOf(From), B = VestibuleOf(To);
	if (A >= 0 && A == B)
	{
		return To;
	}
	const FVector Origin = GetActorLocation();
	FVector Goal = To;
	if (A >= 0 || B >= 0)
	{
		const int32 D = A >= 0 ? A : B;   // из своего тамбура сначала выйти; иначе идти к тамбуру цели
		const FVector Local = From - Origin;
		const float Along = FVector::DotProduct(Local, Dir(D));
		const float Lateral = FVector::DotProduct(Local, Slide(D));
		const float Inner = InnerFace(D);
		if (A >= 0)
		{
			// в тамбуре: встать на ось двери, потом пройти проём в комнату
			FVector Out = FMath::Abs(Lateral) > 30.f && Along > OuterFace(D) + 40.f ? Origin + Dir(D) * Along : Origin + Dir(D) * (Inner - 90.f);
			Out.Z = From.Z;
			return Out;
		}
		if (FMath::Abs(Lateral) < 30.f && Along > Inner - 160.f)
		{
			// стоит перед проёмом на оси: пройти проём по оси, а к игроку повернуть уже в тамбуре
			FVector Through = Origin + Dir(D) * (OuterFace(D) + 40.f);
			Through.Z = From.Z;
			return Through;
		}
		Goal = Origin + Dir(D) * (Inner - 100.f);
	}
	Goal.Z = From.Z;
	if (ClearWay(From, Goal))
	{
		return Goal;
	}
	// прямой путь закрыт мебелью: шаг к соседней клетке, от которой до цели ближе
	if (!bNavBuilt)
	{
		BuildNav();
	}
	const int32 Start = NavCellAt(From - Origin), End = NavCellAt(Goal - Origin);
	if (Start < 0 || End < 0 || Start == End)
	{
		return Goal;
	}
	if (End != NavGoal)
	{
		NavFlood(End);
	}
	if (NavDist[Start] == MAX_int32)
	{
		return Goal;
	}
	int32 Best = Start;
	const int32 X = Start / NavNY, Y = Start % NavNY;
	for (int32 DX = -1; DX <= 1; ++DX)
	{
		for (int32 DY = -1; DY <= 1; ++DY)
		{
			const int32 NX = X + DX, NY = Y + DY;
			if (NX < 0 || NY < 0 || NX >= NavNX || NY >= NavNY || !NavFree[NX * NavNY + NY])
			{
				continue;
			}
			if (DX != 0 && DY != 0 && (!NavFree[NX * NavNY + Y] || !NavFree[X * NavNY + NY]))
			{
				continue;
			}
			if (NavDist[NX * NavNY + NY] < NavDist[Best])
			{
				Best = NX * NavNY + NY;
			}
		}
	}
	FVector Step = NavCenter(Best);
	Step.Z = From.Z;
	return Step;
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
		const float Inner = InnerFace(D);
		// у двери со стороны комнаты; в проёме и первых 90 см тамбура; в глубине тамбура
		const bool bApproach = bPawnHere && Along > Inner - 220.f && Along <= Inner && Lateral < 150.f;
		const bool bDoorway = bPawnHere && Along > Inner && Along <= Outer + 90.f && Lateral < VestibuleWidth * 0.5f;
		const bool bDeep = bPawnHere && Along > Outer + 90.f && Along < Outer + VestibuleDepth + Wall && Lateral < VestibuleWidth * 0.5f + Wall;

		if (Sign[D] && !bSignKnown[D])
		{
			// нераскрытая дверь: табло неровно мерцает
			const float T = GetWorld()->GetTimeSeconds() * 7.f + D * 1.7f;
			Sign[D]->SetVisibility(FMath::Sin(T) + 0.6f * FMath::Sin(T * 2.3f) > -0.9f);
		}
		if (bApproach && Director.IsValid())
		{
			Director->OnDoorApproach();
		}
		if (bArrival[D] && !bDeep && !bDoorway)
		{
			bArrival[D] = false;   // игрок вышел из тамбура в комнату
		}
		if (bDeep && !bArrival[D] && !bSealed && Director.IsValid())
		{
			Director->BeginTransition(this, D);   // ставит bSealed
		}

		ForcedOpenLeft[D] = FMath::Max(0.f, ForcedOpenLeft[D] - DeltaSeconds);
		const bool bWantOpen = !bSealed && (bArrival[D] || bApproach || bDoorway || ForcedOpenLeft[D] > 0.f);
		LeafOpen[D] = FMath::Clamp(LeafOpen[D] + (bWantOpen ? 1.f : -1.f) * DeltaSeconds / 0.6f, 0.f, 1.f);
		if (Leaf[D])
		{
			const float Eased = FMath::SmoothStep(0.f, 1.f, LeafOpen[D]);
			Leaf[D]->SetRelativeLocation(LeafClosed[D] + Slide(D) * DoorWidth * Eased);
		}
	}
}
