#include "RunRoom.h"

#include "Engine/StaticMesh.h"
#include "Materials/MaterialInterface.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "Components/DecalComponent.h"
#include "Components/InstancedStaticMeshComponent.h"
#include "Components/LightComponent.h"
#include "Components/TextRenderComponent.h"
#include "Components/StaticMeshComponent.h"
#include "GameFramework/Pawn.h"
#include "Kismet/GameplayStatics.h"
#include "Algo/Find.h"
#include "Misc/Crc.h"
#include "Misc/CommandLine.h"
#include "Misc/PackageName.h"
#include "Misc/Parse.h"
#include "RunAudio.h"
#include "RunDirector.h"
#include "RunGen.h"

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
	// плитка пола: блюпринты комнат собраны раньше неё, пересборка долгая, поэтому пол красится здесь
	// (build_rooms.py ставит её сам при следующей пересборке). Сетка привязана к центру комнаты (M_FloorTiles).
	if (UMaterialInterface* Tiles = LoadObject<UMaterialInterface>(nullptr,
		TEXT("/Game/Environment/Common/FloorTiles/MI_FloorTiles.MI_FloorTiles"), nullptr, LOAD_NoWarn | LOAD_Quiet))
	{
		for (UStaticMeshComponent* M : Meshes)
		{
			const FString N = M->GetName();
			if (N == TEXT("Floor") || N.EndsWith(TEXT("_Airlock_Floor")))
			{
				M->SetMaterial(0, Tiles);
			}
		}
	}
	// створки шлюзов: модель автора (Tripo, 15.11) вместо оранжевых коробок. Коробка 150 × 10 × 225 см стоит без
	// поворота, тонкой стороной вдоль X или Y; модель — шириной вдоль X, привязка в середине, своя коробка коллизии
	if (UStaticMesh* DoorMesh = LoadObject<UStaticMesh>(nullptr, TEXT("/Game/Environment/Common/AirlockDoor/SM_AirlockDoor.SM_AirlockDoor"),
		nullptr, LOAD_NoWarn | LOAD_Quiet))
	{
		for (UStaticMeshComponent* M : Meshes)
		{
			const FString N = M->GetName();
			if (!N.EndsWith(TEXT("_DoorInner")) && !N.EndsWith(TEXT("_DoorOuter")))
			{
				continue;
			}
			const FVector Size = M->GetStaticMesh() ? M->GetStaticMesh()->GetBoundingBox().GetSize() * M->GetRelativeScale3D() : FVector(150.f, 10.f, 225.f);
			M->SetStaticMesh(DoorMesh);
			M->EmptyOverrideMaterials();
			M->SetRelativeScale3D(FVector(1.f));
			M->SetRelativeRotation(FRotator(0.f, Size.X < Size.Y ? 90.f : 0.f, 0.f));
		}
	}
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
	// пустой текст — табло нет: двери, кроме обратной, снова не определены после каждого прохода, и прочерки
	// над ними ничего не говорили (автор, 15.11: табло только над обратной дверью и HULL BREACH)
	bSignKnown[Door] = !Text.IsEmpty();
	if (!Sign[Door] && !bSignKnown[Door])
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
		T->SetReceivesDecals(false);                         // копоть выгоревшей комнаты табло не закрывает
		Sign[Door] = T;
		// тёмная плашка под текстом: стены светлые, без неё табло не читается
		UStaticMeshComponent* Plate = NewObject<UStaticMeshComponent>(this);
		Plate->SetupAttachment(GetRootComponent());
		Plate->RegisterComponent();
		Plate->SetMobility(EComponentMobility::Movable);
		Plate->SetCollisionProfileName(TEXT("NoCollision"));
		Plate->SetReceivesDecals(false);
		Plate->SetStaticMesh(LoadObject<UStaticMesh>(nullptr, TEXT("/Engine/BasicShapes/Cube.Cube")));
		if (UMaterialInterface* Dark = LoadObject<UMaterialInterface>(nullptr, TEXT("/Game/Game/Materials/MI_Gray_Dark.MI_Gray_Dark")))
		{
			Plate->SetMaterial(0, Dark);
		}
		Plate->SetRelativeLocation(Dir(Door) * (InnerFace(Door) - 1.5f) + FVector(0.f, 0.f, 275.f));
		Plate->SetRelativeRotation((-Dir(Door)).Rotation());
		Plate->SetRelativeScale3D(FVector(0.03f, 2.3f, 0.42f));
		SignPlate[Door] = Plate;
	}
	Sign[Door]->SetVisibility(bSignKnown[Door]);
	SignPlate[Door]->SetVisibility(bSignKnown[Door]);
	if (bSignKnown[Door])
	{
		Sign[Door]->SetText(FText::FromString(Text));
		Sign[Door]->SetTextRenderColor(Text.StartsWith(TEXT("HULL")) ? FColor(235, 60, 45) : FColor(95, 198, 201));   // красное — разгерметизация
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

// Числа аварийного освещения: правятся здесь, пока идёт подбор вида.
namespace RunEmergencyTune
{
	const FLinearColor Red(1.f, 0.045f, 0.02f);
	constexpr float General = 0.045f;     // общий свет: доля прежней силы (автор 15.11: темнее, иначе фонарик не нужен)
	constexpr float Beacon = 0.18f;       // маячки тамбуров
	constexpr float Accent = 0.06f;       // остальные источники: только очертания
	constexpr float PanelGlow = 0.2f;     // свечение потолочных панелей (было 6, белое); ярче — уходит в жёлтый
	constexpr float PulseDepth = 0.22f;   // красный свет «дышит»: на столько падает в нижней точке
	constexpr float PulseSeconds = 3.2f;
}

FIntVector ARunRoom::ApplyEmergency()
{
	using namespace RunEmergencyTune;
	bEmergency = true;
	FIntVector Count(0, 0, 0);
	TInlineComponentArray<ULightComponent*> Lights(this);
	for (ULightComponent* L : Lights)
	{
		const FString N = L->GetName();
		const bool bGeneral = N.StartsWith(TEXT("Room_Light")), bBeacon = N.EndsWith(TEXT("_Airlock_Light"));
		if (bGeneral || bBeacon)
		{
			L->SetLightColor(Red);
			L->SetIntensity(L->Intensity * (bGeneral ? General : Beacon));
			PulseLights.Add({ L, L->Intensity });
			++Count.X;
		}
		else
		{
			L->SetIntensity(L->Intensity * Accent);
			L->SetCastShadows(false);   // тлеющий акцент теней не даёт: и незаметно, и дешевле
			++Count.Y;
		}
	}
	// потолочные панели-светильники (слот MI_CeilingFrosted) светятся красным вместо белого
	TInlineComponentArray<UStaticMeshComponent*> Meshes(this);
	TMap<UMaterialInterface*, UMaterialInstanceDynamic*> Made;
	for (UStaticMeshComponent* M : Meshes)
	{
		for (int32 I = 0; I < M->GetNumMaterials(); ++I)
		{
			UMaterialInterface* Mat = M->GetMaterial(I);
			if (!Mat || !Mat->GetName().StartsWith(TEXT("MI_CeilingFrosted")))
			{
				continue;
			}
			UMaterialInstanceDynamic*& Dyn = Made.FindOrAdd(Mat);
			if (!Dyn)
			{
				Dyn = UMaterialInstanceDynamic::Create(Mat, this);
				Dyn->SetVectorParameterValue(TEXT("Color"), Red);
				Dyn->SetScalarParameterValue(TEXT("EmissiveStrength"), PanelGlow);
				PulsePanels.Add(Dyn);
			}
			M->SetMaterial(I, Dyn);
			++Count.Z;
		}
	}
	return Count;
}

void ARunRoom::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);
	if (bEmergency)
	{
		using namespace RunEmergencyTune;
		const float K = 1.f - PulseDepth * (0.5f - 0.5f * FMath::Cos(GetWorld()->GetTimeSeconds() * 2.f * PI / PulseSeconds));
		for (const FPulse& P : PulseLights)
		{
			if (P.Light.IsValid())
			{
				P.Light->SetIntensity(P.Base * K);
			}
		}
		for (UMaterialInstanceDynamic* M : PulsePanels)
		{
			M->SetScalarParameterValue(TEXT("EmissiveStrength"), PanelGlow * K);
		}
	}

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
		if (bWantOpen != bLeafWanted[D])
		{
			bLeafWanted[D] = bWantOpen;
			if (Leaf[D] && GetWorld()->GetTimeSeconds() > CreationTime + 0.5f)   // не звучать, пока комната только появилась
			{
				RunAudio::PlayAt(this, bWantOpen ? TEXT("DoorOpen") : TEXT("DoorClose"), Leaf[D]->GetComponentLocation(), 0.8f);
			}
		}
		LeafOpen[D] = FMath::Clamp(LeafOpen[D] + (bWantOpen ? 1.f : -1.f) * DeltaSeconds / 0.6f, 0.f, 1.f);
		if (Leaf[D])
		{
			const float Eased = FMath::SmoothStep(0.f, 1.f, LeafOpen[D]);
			Leaf[D]->SetRelativeLocation(LeafClosed[D] + Slide(D) * DoorWidth * Eased);
		}
	}
}

// ---------- выгоревшая комната (DESIGN.md §14) ----------

namespace
{
	float Unit(uint32 H)
	{
		return static_cast<float>(H & 0xFFFFFF) / 16777216.f;
	}

	/** Коробка комнаты, тамбуры и створки: на них копоть не кладётся элементами, пол и потолок — отдельно. */
	bool IsShellPart(const FString& N)
	{
		return N == TEXT("Floor") || N == TEXT("Ceiling") || N.StartsWith(TEXT("Wall_")) || N.Contains(TEXT("_Airlock_"))
			|| N.EndsWith(TEXT("_DoorInner")) || N.EndsWith(TEXT("_DoorOuter"));
	}

	/** Сгоревшая версия меша: <путь>_Burned, <путь>_Burned2, ... в той же папке; из нескольких Pick выбирает одну.
	 *  Они есть только у моделей автора, поэтому ищутся лишь среди мешей окружения; отсутствующие пути
	 *  запоминаются, чтобы не искать их в каждой комнате заново. */
	UStaticMesh* BurnedVariant(const UStaticMesh* Mesh, uint32 Pick)
	{
		static TSet<FString> Missing;
		if (!Mesh)
		{
			return nullptr;
		}
		const FString Pkg = Mesh->GetPackage()->GetName();
		if (!Pkg.StartsWith(TEXT("/Game/Environment/")) || Pkg.Contains(TEXT("_Burned")))
		{
			return nullptr;
		}
		TArray<UStaticMesh*, TInlineAllocator<4>> Found;
		for (int32 N = 1; N <= 4; ++N)
		{
			const FString Name = N == 1 ? Pkg + TEXT("_Burned") : FString::Printf(TEXT("%s_Burned%d"), *Pkg, N);
			if (Missing.Contains(Name))
			{
				break;
			}
			UStaticMesh* V = LoadObject<UStaticMesh>(nullptr, *(Name + TEXT(".") + FPackageName::GetShortName(Name)),
				nullptr, LOAD_NoWarn | LOAD_Quiet);
			if (!V)
			{
				Missing.Add(Name);
				break;
			}
			Found.Add(V);
		}
		return Found.Num() > 0 ? Found[Pick % Found.Num()] : nullptr;
	}
}

namespace
{
	UMaterialInterface* SootMaterial(const FString& Mask)
	{
		return LoadObject<UMaterialInterface>(nullptr,
			*FString::Printf(TEXT("/Game/Environment/Common/Soot/MI_Soot_%s.MI_Soot_%s"), *Mask, *Mask), nullptr,
			LOAD_NoWarn | LOAD_Quiet);
	}

	/** Пятно для стоячей поверхности: A, B (потёки) или C. */
	FString Spot(uint32 Hash)
	{
		static const TCHAR* const Spots[3] = { TEXT("A"), TEXT("B"), TEXT("C") };
		return Spots[Hash % 3];
	}

	/** Пятно для пола и верха мебели: A или C. Потёки B на горизонтали выглядят растянутыми полосами. */
	FString Blot(uint32 Hash)
	{
		return (Hash & 1) ? TEXT("C") : TEXT("A");
	}

	/** Маска из набора <Prefix>1, <Prefix>2, ... (картинки автора, make_soot_from_images.py) по хешу; если набора
	 *  нет — Fallback. Сколько их, считается один раз за запуск: новые маски видны после перезапуска редактора. */
	FString SootPick(const TCHAR* Prefix, uint32 Hash, const TCHAR* Fallback)
	{
		static TMap<FString, int32> Count;
		int32* N = Count.Find(Prefix);
		if (!N)
		{
			int32 K = 0;
			while (K < 16 && SootMaterial(FString::Printf(TEXT("%s%d"), Prefix, K + 1)))
			{
				++K;
			}
			N = &Count.Add(Prefix, K);
		}
		return *N > 0 ? FString::Printf(TEXT("%s%d"), Prefix, static_cast<int32>(Hash % static_cast<uint32>(*N)) + 1) : FString(Fallback);
	}
}

void ARunRoom::AddSoot(const FVector& Pos, const FRotator& Rot, const FVector& HalfSize, uint32 Hash, const FString& Mask, float Opacity)
{
	if (Mask.IsEmpty())
	{
		return;
	}
	UMaterialInterface* Base = SootMaterial(Mask);
	if (!Base)
	{
		return;   // нет копоти в проекте (tools/ue/import_soot.py): комната просто без неё
	}
	UMaterialInstanceDynamic* Mat = UMaterialInstanceDynamic::Create(Base, this);
	Mat->SetScalarParameterValue(TEXT("Opacity"), Opacity);
	if (DecalColor.A > 0.f)
	{
		Mat->SetVectorParameterValue(TEXT("Color"), DecalColor);   // те же маски другим цветом: мох грибной комнаты
	}
	UDecalComponent* D = NewObject<UDecalComponent>(this);
	D->SetupAttachment(GetRootComponent());
	D->SetDecalMaterial(Mat);
	D->DecalSize = HalfSize;
	D->SetFadeScreenSize(0.f);         // не гаснет издалека
	D->RegisterComponent();
	// у пятен A–C нет верха и низа: поворот на пол-оборота вокруг оси проекции и немного вкось;
	// у дымовых следов (D, Band*, Plume*) верх есть — их кладут ровно
	FRotator R = Rot;
	if (Mask.Len() == 1 && Mask != TEXT("D"))
	{
		R.Roll += ((RunGen::Hash32({ Hash, 9U }) & 1) ? 180.f : 0.f) + (Unit(RunGen::Hash32({ Hash, 11U })) - 0.5f) * 24.f;
	}
	D->SetWorldLocationAndRotation(Pos, R);
	// ось проекции (локальная X декали): на поверхностях вдоль неё M_SootDecal гасит копоть, чтобы не тянулась полосами
	const FVector Axis = R.Vector();
	Mat->SetVectorParameterValue(TEXT("Axis"), FLinearColor(Axis.X, Axis.Y, Axis.Z, 0.f));
	// зеркало картинки по горизонтали (MirrorU в M_SootDecal): одна маска на разных стенах не повторяется
	Mat->SetScalarParameterValue(TEXT("MirrorU"), (RunGen::Hash32({ Hash, 13U }) & 1) ? 1.f : 0.f);
	++Decals;
}

void ARunRoom::CollectElements(TArray<FString>& Names, TMap<FString, TArray<UStaticMeshComponent*>>& Groups) const
{
	TInlineComponentArray<UStaticMeshComponent*> All(this);
	TMap<FString, UStaticMeshComponent*> ByName;
	for (UStaticMeshComponent* M : All)
	{
		const FString N = M->GetName();
		const bool bLeaf = Algo::Find(Leaf, M) != nullptr;
		// маркеры выходов и кнопки дверей остаются чистыми: двери всегда читаются; табло и плашки создаёт этот класс
		if (bLeaf || !M->IsVisible() || !M->GetStaticMesh() || IsShellPart(N) || N.Contains(TEXT("DoorButton"))
			|| N.Contains(TEXT("FloorMarker")) || N.StartsWith(TEXT("ItemSpot")) || N.StartsWith(TEXT("NoteSpot"))
			|| N.StartsWith(TEXT("StaticMeshComponent"))
			|| N.StartsWith(TEXT("CeilingTile")))   // панели потолка (build_rooms.py): копоть на них дают пятна потолка ниже
		{
			continue;
		}
		ByName.Add(N, M);
	}
	// элемент — компонент со всеми, чьё имя продолжает его имя через «_»: Rack1 с Rack1_Strip1 и Rack1_Top
	for (const TPair<FString, UStaticMeshComponent*>& It : ByName)
	{
		FString Group = It.Key;
		FString P = It.Key;
		int32 Cut;
		while (P.FindLastChar(TEXT('_'), Cut))
		{
			P.LeftInline(Cut);
			if (ByName.Contains(P))
			{
				Group = P;   // самый короткий существующий префикс: Lining_N_L1_Extinguisher -> Lining_N_L1
			}
		}
		Groups.FindOrAdd(Group).Add(It.Value);
	}
	Groups.GetKeys(Names);
	Names.Sort();
}

FIntVector ARunRoom::ApplyBurn(uint32 Seed)
{
	using RunGen::Hash32;
	TArray<FString> Names;
	TMap<FString, TArray<UStaticMeshComponent*>> Groups;
	CollectElements(Names, Groups);

	const float Share = 0.35f + 0.40f * Unit(Hash32({ Seed, 1U }));   // сколько элементов сгорело
	const FVector Center = GetActorLocation();
	int32 Swapped = 0;
	int32 Sooted = 0;
	TArray<FVector> Burnt;      // сгоревшие элементы: под ними копоть на полу и потолке
	TArray<FVector> Spots;      // все элементы: если сгоревших нет
	TArray<TPair<FVector, FVector>> Plumes;   // сгоревшие колонки у стен: середина лица и куда оно смотрит
	for (const FString& G : Names)
	{
		TArray<UStaticMeshComponent*>& Parts = Groups[G];
		const uint32 H = Hash32({ Seed, FCrc::StrCrc32(*G) });
		// аварийный пост не горит: в нише аптечка
		bool bPost = false;
		for (const UStaticMeshComponent* P : Parts)
		{
			bPost |= P->GetStaticMesh()->GetName().Contains(TEXT("WallColumnEmergency"));
		}
		bool bDestroyed = false;
		if (!bPost && Unit(H) < Share)
		{
			for (UStaticMeshComponent* P : Parts)
			{
				if (UStaticMesh* V = BurnedVariant(P->GetStaticMesh(), Hash32({ H, 10U })))
				{
					P->SetMobility(EComponentMobility::Movable);   // меш статичного компонента в игре не меняется
					P->SetStaticMesh(V);
					P->EmptyOverrideMaterials();                   // у сгоревшей версии свой материал
					// у колонок стен моделей мало, соседние одинаковые колонки читались копией: часть зеркалится по
					// ширине (локальная X; модель стоит серединой спины в точке привязки, место не меняется)
					if (G.StartsWith(TEXT("Lining_")) && (Hash32({ H, 12U }) & 1))
					{
						FVector S = P->GetRelativeScale3D();
						S.X = -S.X;
						P->SetRelativeScale3D(S);
					}
					bDestroyed = true;
				}
			}
		}
		FBox Box(ForceInit);
		for (const UStaticMeshComponent* P : Parts)
		{
			Box += P->Bounds.GetBox();
		}
		const FVector C = Box.GetCenter();
		const FVector Ext = Box.GetExtent();
		Spots.Add(C);
		if (bDestroyed)
		{
			++Swapped;
			Burnt.Add(C);
			if (G.StartsWith(TEXT("Lining_")) && Box.Min.Z < 50.f)
			{
				// колонка стоит от пола: середина её лица — 45 см от спины (точка привязки — середина спины на полу)
				const FVector Face = Parts[0]->GetRightVector();
				const FVector FaceMid = Parts[0]->GetComponentLocation() + Face * Lining;
				Plumes.Add({ FaceMid, Face });
				// поверх модели — два пятна копоти в случайных местах лица: одинаковые модели рядом не совпадают
				const FVector Across = Parts[0]->GetForwardVector();
				for (uint32 K = 0; K < 2; ++K)
				{
					const uint32 Hk = Hash32({ H, 20U, K });
					const float R = 30.f + 30.f * Unit(Hash32({ Hk, 1U }));
					const float Z = 40.f + 160.f * Unit(Hash32({ Hk, 2U }));
					const float X = 25.f * (2.f * Unit(Hash32({ Hk, 3U })) - 1.f);
					AddSoot(FaceMid + Across * X + FVector(0.f, 0.f, Z), (-Face).Rotation(), FVector(40.f, R, R), Hk,
						Spot(Hk), 0.6f + 0.35f * Unit(Hash32({ Hk, 4U })));
				}
			}
			continue;
		}
		++Sooted;
		if (G.StartsWith(TEXT("Lining_")))
		{
			// колонка или перемычка у стены: дымовой след под потолком кладётся ниже, полосами вдоль всей стены;
			// здесь только потёки (+Y меша смотрит в комнату)
			const FVector Face = Parts[0]->GetRightVector();
			const float HalfW = FMath::Abs(Face.X) > 0.5f ? Ext.Y : Ext.X;
			// местами потёки ниже: полосы B на части высоты
			if (Unit(Hash32({ H, 5U })) < 0.35f && Ext.Z > 100.f)
			{
				const float Hz = 50.f + 40.f * Unit(Hash32({ H, 6U }));
				const float Z = Box.Min.Z + Hz + 40.f + (Box.GetSize().Z * 0.6f - 2.f * Hz) * Unit(Hash32({ H, 3U }));
				AddSoot(FVector(C.X, C.Y, Z), (-Face).Rotation(), FVector(35.f, HalfW + 1.f, Hz), Hash32({ H, 8U }), TEXT("B"),
					0.5f + 0.3f * Unit(Hash32({ H, 9U })));
			}
		}
		else
		{
			// мебель: декаль сбоку, со стороны середины комнаты, и сверху, если до верха можно дотянуться взглядом
			FVector D = C - Center;
			D.Z = 0.f;
			D = D.SizeSquared() < 2500.f ? FVector(1, 0, 0) : D.GetSafeNormal();
			const float Along = FMath::Abs(D.X) * Ext.X + FMath::Abs(D.Y) * Ext.Y;
			const float Across = FMath::Abs(D.Y) * Ext.X + FMath::Abs(D.X) * Ext.Y;
			AddSoot(C, FRotator(0.f, D.Rotation().Yaw, 0.f), FVector(Along + 10.f, Across + 10.f, Ext.Z + 5.f), H, Spot(H),
				0.65f + 0.3f * Unit(Hash32({ H, 7U })));
			if (Box.Max.Z < 200.f)
			{
				const float R = FMath::Max(Ext.X, Ext.Y) + 10.f;
				const uint32 Ht = Hash32({ H, 4U });
				AddSoot(FVector(C.X, C.Y, Box.Max.Z), FRotator(-90.f, 0.f, 0.f), FVector(30.f, R, R), Ht, Blot(Ht),
					0.65f + 0.3f * Unit(Hash32({ Ht, 7U })));
			}
		}
	}

	// пол и потолок: пятна у сгоревших элементов, ближе к середине комнаты
	const TArray<FVector>& Near = Burnt.Num() > 0 ? Burnt : Spots;
	if (Near.Num() > 0)
	{
		const int32 NumFloor = 5 + static_cast<int32>(Hash32({ Seed, 5U }) % 4);
		const int32 NumCeiling = 6 + static_cast<int32>(Hash32({ Seed, 6U }) % 4);
		for (int32 I = 0; I < NumFloor + NumCeiling; ++I)
		{
			const uint32 H = Hash32({ Seed, 20U, static_cast<uint32>(I) });
			FVector P = Near[H % Near.Num()] - Center;
			P = FVector(P.X, P.Y, 0.f) * (0.7f + 0.2f * Unit(Hash32({ H, 1U })));
			P.X = FMath::Clamp(P.X, -HalfX + 60.f, HalfX - 60.f);
			P.Y = FMath::Clamp(P.Y, -HalfY + 60.f, HalfY - 60.f);
			const bool bFloor = I < NumFloor;
			const float R = (bFloor ? 90.f : 140.f) + 80.f * Unit(Hash32({ H, 2U }));
			// на потолке — размытые пятна A: дым ложится облаком; на полу — A или C
			AddSoot(Center + P + FVector(0.f, 0.f, bFloor ? 0.f : Height), FRotator(bFloor ? -90.f : 90.f, 0.f, 0.f),
				FVector(40.f, R, R), H, bFloor ? Blot(H) : FString(TEXT("A")), 0.7f + 0.3f * Unit(Hash32({ H, 7U })));
		}
	}

	// Копоть на стенах. Если в проекте есть маски Wall1..N (картинки автора 21:9, 15.11), на каждую стену одна
	// декаль на всю длину и высоту: плотно под потолком и у пола, чистых шкафов рядом со сгоревшими не остаётся.
	// Без них — прежняя схема: широкие полосы под потолком через несколько колонок, внахлёст (Band1..N, иначе D).
	// Верх картинки в декали лежит вдоль её локальной оси Y: поворот на 90° вокруг оси проекции ставит его
	// к потолку (проверено в Play 14.11), поэтому высота идёт в Y, длина вдоль стены — в Z.
	for (int32 Side = 0; Side < 4; ++Side)
	{
		const FVector Out = Dir(Side);
		const FVector Along = Side < 2 ? FVector(0, 1, 0) : FVector(1, 0, 0);
		const float L = Side < 2 ? HalfY : HalfX;
		FRotator Up = Out.Rotation();
		Up.Roll = 90.f;
		const uint32 Hwall = Hash32({ Seed, 50U, static_cast<uint32>(Side) });
		const FString WallMask = SootPick(TEXT("Wall"), Hwall, TEXT(""));
		if (!WallMask.IsEmpty())
		{
			// заходит за углы на 20 см: на стыке стен копоть не рвётся
			const FVector Pos = Center + Out * (InnerFace(Side) + 10.f) + FVector(0.f, 0.f, Height * 0.5f);
			AddSoot(Pos, Up, FVector(35.f, Height * 0.5f + 5.f, L + 20.f), Hwall, WallMask, 0.85f + 0.15f * Unit(Hash32({ Hwall, 7U })));
			continue;
		}
		float S = -L - 30.f;
		for (int32 I = 0; S < L && I < 12; ++I)
		{
			const uint32 H = Hash32({ Seed, 40U, static_cast<uint32>(Side), static_cast<uint32>(I) });
			// маски — квадратные картинки, внизу у них пустая треть: коробка почти квадратная, чтобы дым не сплющило
			const float Hw = 100.f + 40.f * Unit(Hash32({ H, 1U }));                       // полдлины: 2–2,8 м
			const float Hs = 80.f + 35.f * Unit(Hash32({ H, 2U }));                        // полвысоты: 1,6–2,3 м
			const float Mid = FMath::Min(S + Hw, L + 20.f - Hw);
			const FVector Pos = Center + Out * (InnerFace(Side) + 10.f) + Along * Mid + FVector(0.f, 0.f, Height - Hs);
			AddSoot(Pos, Up, FVector(35.f, Hs, Hw), H, SootPick(TEXT("Band"), H, TEXT("D")), 0.8f + 0.2f * Unit(Hash32({ H, 7U })));
			S += 2.f * Hw * 0.7f;
		}
	}
	// над сгоревшей колонкой — язык дыма от неё до потолка (маски Plume1..N; без них не кладётся)
	for (int32 I = 0; I < Plumes.Num(); ++I)
	{
		const uint32 H = Hash32({ Seed, 60U, static_cast<uint32>(I) });
		const FVector Face = Plumes[I].Value;
		FRotator Up = (-Face).Rotation();
		Up.Roll = 90.f;
		const float Hw = 80.f + 40.f * Unit(Hash32({ H, 1U }));
		const float Bottom = 40.f + 50.f * Unit(Hash32({ H, 2U }));
		const float Hs = (Height - Bottom) * 0.5f;
		const FVector Pos = Plumes[I].Key - Face * (Lining - 10.f) + FVector(0.f, 0.f, Bottom + Hs);
		AddSoot(Pos, Up, FVector(35.f, Hs, Hw), H, SootPick(TEXT("Plume"), H, TEXT("")), 0.85f + 0.15f * Unit(Hash32({ H, 7U })));
	}
	return FIntVector(Swapped, Sooted, Decals);
}

namespace
{
	/** Материал грибов (tools/ue/import_anomalies.py); без него — серые заглушки прототипа. */
	UMaterialInterface* FungusMaterial(const TCHAR* Name, const TCHAR* Fallback)
	{
		UMaterialInterface* M = LoadObject<UMaterialInterface>(nullptr, *FString::Printf(TEXT("/Game/FX/Anomalies/%s.%s"), Name, Name),
			nullptr, LOAD_NoWarn | LOAD_Quiet);
		return M ? M : LoadObject<UMaterialInterface>(nullptr,
			*FString::Printf(TEXT("/Game/Game/Materials/%s.%s"), Fallback, Fallback), nullptr, LOAD_NoWarn | LOAD_Quiet);
	}
}

FIntVector ARunRoom::ApplyFungus(uint32 Seed)
{
	using RunGen::Hash32;
	// мох — те же маски, что у копоти, цветом болотной зелени; грибы — кучки ножек и шляпок (базовые фигуры движка,
	// пока у автора нет моделей), у колонок на полу, на мебели и по полу. Без коллизии: путь не запирают
	DecalColor = FLinearColor(0.07f, 0.085f, 0.028f, 1.f);
	TArray<FString> Names;
	TMap<FString, TArray<UStaticMeshComponent*>> Groups;
	CollectElements(Names, Groups);
	const FVector Center = GetActorLocation();
	TArray<FVector> Avoid = GetSpots(TEXT("ItemSpot"));
	Avoid.Append(GetSpots(TEXT("NoteSpot")));

	auto MakeIsm = [this](const TCHAR* Shape, UMaterialInterface* Mat)
	{
		UInstancedStaticMeshComponent* C = NewObject<UInstancedStaticMeshComponent>(this);
		C->SetStaticMesh(LoadObject<UStaticMesh>(nullptr, Shape));
		C->SetMaterial(0, Mat);
		C->SetCollisionEnabled(ECollisionEnabled::NoCollision);
		C->SetReceivesDecals(false);
		C->SetupAttachment(GetRootComponent());
		C->RegisterComponent();
		return C;
	};
	UInstancedStaticMeshComponent* Stems = MakeIsm(TEXT("/Engine/BasicShapes/Cylinder.Cylinder"), FungusMaterial(TEXT("MI_MushroomStem"), TEXT("MI_Gray_Linen")));
	UInstancedStaticMeshComponent* Caps = MakeIsm(TEXT("/Engine/BasicShapes/Sphere.Sphere"), FungusMaterial(TEXT("MI_MushroomCap"), TEXT("MI_Gray_Door")));
	// модели кучек (автор, Tripo, 15.11): пять мешей SM_Fungus1–5; есть они — ставятся вместо фигур, реже и крупнее
	TArray<UInstancedStaticMeshComponent*> Models;
	for (int32 I = 1; I <= 5; ++I)
	{
		const FString Path = FString::Printf(TEXT("/Game/Environment/Common/FungusClusters/SM_Fungus%d.SM_Fungus%d"), I, I);
		if (UStaticMesh* Model = LoadObject<UStaticMesh>(nullptr, *Path, nullptr, LOAD_NoWarn | LOAD_Quiet))
		{
			UInstancedStaticMeshComponent* C = MakeIsm(TEXT("/Engine/BasicShapes/Cube.Cube"), nullptr);
			C->SetStaticMesh(Model);
			C->EmptyOverrideMaterials();
			Models.Add(C);
		}
	}
	auto Cluster = [&](const FVector& At, uint32 H, float Spread, int32 Count, float Scale)
	{
		if (Models.Num() > 0)
		{
			// кучка из модели заменяет три-четыре гриба из фигур
			const int32 N = FMath::Max(1, (Count + 2) / 3);
			for (int32 K = 0; K < N; ++K)
			{
				const uint32 Hk = Hash32({ H, 71U, static_cast<uint32>(K) });
				const float R = Spread * FMath::Sqrt(Unit(Hash32({ Hk, 2U })));
				const FVector P = At + FRotator(0.f, 360.f * Unit(Hash32({ Hk, 1U })), 0.f).Vector() * R;
				bool bClear = true;
				for (const FVector& A : Avoid)
				{
					bClear &= FVector::Dist2D(A, P) > 55.f;
				}
				if (!bClear)
				{
					continue;
				}
				const float S = Scale * (0.5f + 0.6f * Unit(Hash32({ Hk, 3U }))) * (1.f - 0.3f * R / FMath::Max(Spread, 1.f));
				Models[Hash32({ Hk, 4U }) % Models.Num()]->AddInstance(FTransform(FRotator(0.f, 360.f * Unit(Hash32({ Hk, 5U })), 0.f), P, FVector(S)), true);
			}
			return;
		}
		for (int32 K = 0; K < Count; ++K)
		{
			const uint32 Hk = Hash32({ H, 70U, static_cast<uint32>(K) });
			const float Ang = 360.f * Unit(Hash32({ Hk, 1U }));
			const float R = Spread * FMath::Sqrt(Unit(Hash32({ Hk, 2U })));
			const FVector P = At + FRotator(0.f, Ang, 0.f).Vector() * R;
			bool bClear = true;
			for (const FVector& A : Avoid)
			{
				bClear &= FVector::Dist2D(A, P) > 45.f;
			}
			if (!bClear)
			{
				continue;
			}
			// к краю кучки мельче; ножка чуть вкось
			const float Hgt = Scale * (8.f + 22.f * Unit(Hash32({ Hk, 3U }))) * (1.f - 0.5f * R / FMath::Max(Spread, 1.f));
			const float Stem = Hgt * (0.1f + 0.06f * Unit(Hash32({ Hk, 4U })));
			const float Cap = Hgt * (0.32f + 0.25f * Unit(Hash32({ Hk, 5U })));
			const FRotator Tilt(14.f * (Unit(Hash32({ Hk, 6U })) - 0.5f), Ang, 14.f * (Unit(Hash32({ Hk, 7U })) - 0.5f));
			const FVector Up = Tilt.RotateVector(FVector::UpVector);
			Stems->AddInstance(FTransform(Tilt, P + Up * Hgt * 0.5f, FVector(Stem / 50.f, Stem / 50.f, Hgt / 100.f)), true);
			Caps->AddInstance(FTransform(Tilt, P + Up * Hgt, FVector(Cap / 50.f, Cap / 50.f, Cap * 0.9f / 100.f)), true);
		}
	};

	int32 Overgrown = 0;
	for (const FString& G : Names)
	{
		TArray<UStaticMeshComponent*>& Parts = Groups[G];
		const uint32 H = Hash32({ Seed, 80U, FCrc::StrCrc32(*G) });
		FBox Box(ForceInit);
		for (const UStaticMeshComponent* P : Parts)
		{
			Box += P->Bounds.GetBox();
		}
		const FVector C = Box.GetCenter();
		const FVector Ext = Box.GetExtent();
		if (G.StartsWith(TEXT("Lining_")))
		{
			if (Box.Min.Z > 50.f || Unit(H) > 0.6f)
			{
				continue;   // перемычки над проёмами и часть колонок чистые
			}
			++Overgrown;
			// колонка стоит серединой спины в точке привязки, +Y меша смотрит в комнату
			const FVector Face = Parts[0]->GetRightVector();
			const FVector Base = Parts[0]->GetComponentLocation() + Face * Lining;
			const float HalfW = FMath::Abs(Face.X) > 0.5f ? Ext.Y : Ext.X;
			const float Hz = 60.f + 50.f * Unit(Hash32({ H, 1U }));
			AddSoot(Base + FVector(0.f, 0.f, Hz), (-Face).Rotation(), FVector(35.f, HalfW + 5.f, Hz + 10.f), Hash32({ H, 2U }),
				Spot(Hash32({ H, 2U })), 0.7f + 0.3f * Unit(Hash32({ H, 3U })));
			Cluster(Base + Face * 18.f, H, 35.f, 4 + static_cast<int32>(Hash32({ H, 4U }) % 7), 1.f);
		}
		else
		{
			FVector D = C - Center;
			D.Z = 0.f;
			D = D.SizeSquared() < 2500.f ? FVector(1, 0, 0) : D.GetSafeNormal();
			if (Unit(H) < 0.6f)
			{
				const float Along = FMath::Abs(D.X) * Ext.X + FMath::Abs(D.Y) * Ext.Y;
				const float Across = FMath::Abs(D.Y) * Ext.X + FMath::Abs(D.X) * Ext.Y;
				AddSoot(C, FRotator(0.f, D.Rotation().Yaw, 0.f), FVector(Along + 10.f, Across + 10.f, Ext.Z + 5.f), H, Spot(H),
					0.6f + 0.3f * Unit(Hash32({ H, 7U })));
				++Overgrown;
			}
			if (Box.Max.Z < 160.f && Unit(Hash32({ H, 5U })) < 0.45f)
			{
				const float R = FMath::Max(Ext.X, Ext.Y) + 10.f;
				AddSoot(FVector(C.X, C.Y, Box.Max.Z), FRotator(-90.f, 0.f, 0.f), FVector(30.f, R, R), Hash32({ H, 6U }),
					Blot(Hash32({ H, 6U })), 0.7f);
				Cluster(FVector(C.X, C.Y, Box.Max.Z), Hash32({ H, 8U }), FMath::Min(Ext.X, Ext.Y) * 0.7f,
					3 + static_cast<int32>(Hash32({ H, 9U }) % 4), 0.7f);
			}
		}
	}
	// пол: пятна мха и кучки грибов по всей комнате; потолок: несколько пятен
	const int32 NumFloor = 9 + static_cast<int32>(Hash32({ Seed, 81U }) % 4);
	for (int32 I = 0; I < NumFloor + 5; ++I)
	{
		const uint32 H = Hash32({ Seed, 82U, static_cast<uint32>(I) });
		const FVector P((2.f * Unit(Hash32({ H, 1U })) - 1.f) * (HalfX - 60.f), (2.f * Unit(Hash32({ H, 2U })) - 1.f) * (HalfY - 60.f), 0.f);
		const bool bFloor = I < NumFloor;
		const float R = (bFloor ? 100.f : 130.f) + 100.f * Unit(Hash32({ H, 3U }));
		AddSoot(Center + P + FVector(0.f, 0.f, bFloor ? 0.f : Height), FRotator(bFloor ? -90.f : 90.f, 0.f, 0.f),
			FVector(40.f, R, R), H, Blot(H), 0.75f + 0.25f * Unit(Hash32({ H, 7U })));
		if (bFloor && (H & 1))
		{
			Cluster(Center + P, Hash32({ H, 9U }), 30.f + 30.f * Unit(Hash32({ H, 4U })), 4 + static_cast<int32>(Hash32({ H, 5U }) % 6), 0.9f);
		}
	}
	// стены: одна декаль на стену, как копоть выгоревшей комнаты (маски Wall1..N)
	for (int32 Side = 0; Side < 4; ++Side)
	{
		const uint32 Hwall = Hash32({ Seed, 83U, static_cast<uint32>(Side) });
		const FString WallMask = SootPick(TEXT("Wall"), Hwall, TEXT(""));
		if (WallMask.IsEmpty())
		{
			break;
		}
		const FVector Out = Dir(Side);
		FRotator Up = Out.Rotation();
		Up.Roll = 90.f;
		const FVector Pos = Center + Out * (InnerFace(Side) + 10.f) + FVector(0.f, 0.f, Height * 0.5f);
		AddSoot(Pos, Up, FVector(35.f, Height * 0.5f + 5.f, (Side < 2 ? HalfY : HalfX) + 20.f), Hwall, WallMask,
			0.7f + 0.2f * Unit(Hash32({ Hwall, 7U })));
	}
	// свет тусклее и болотного оттенка
	TInlineComponentArray<ULightComponent*> Lights(this);
	for (ULightComponent* L : Lights)
	{
		L->SetLightColor(FLinearColor(0.78f, 0.92f, 0.55f));
		L->SetIntensity(L->Intensity * 0.7f);
	}
	DecalColor = FLinearColor(0.f, 0.f, 0.f, 0.f);
	int32 Instances = Stems->GetInstanceCount();
	for (const UInstancedStaticMeshComponent* M : Models)
	{
		Instances += M->GetInstanceCount();
	}
	return FIntVector(Overgrown, Instances, Decals);
}

// ---------- мертвецы ----------

void ARunRoom::SpawnCorpses(const TArray<FRunCorpsePlace>& Places)
{
	for (const FRunCorpsePlace& P : Places)
	{
		UStaticMesh* Mesh = LoadObject<UStaticMesh>(nullptr, *FString::Printf(TEXT("/Game/Characters/DeadMan/SM_DeadMan_%s.SM_DeadMan_%s"), *P.Pose, *P.Pose),
			nullptr, LOAD_NoWarn | LOAD_Quiet);
		if (!Mesh)
		{
			continue;
		}
		UStaticMeshComponent* C = NewObject<UStaticMeshComponent>(this);
		C->SetStaticMesh(Mesh);
		C->SetMobility(EComponentMobility::Movable);
		C->SetCollisionProfileName(TEXT("NoCollision"));
		C->SetReceivesDecals(false);
		C->SetupAttachment(GetRootComponent());
		C->RegisterComponent();
		C->SetWorldLocationAndRotation(GetActorLocation() + P.Local, FRotator(0.f, P.Yaw, 0.f));
	}
}

int32 ARunRoom::ApplyCorpses(uint32 Seed, int32 Count, const TArray<FVector>& Occupied, TArray<FRunCorpsePlace>& Out)
{
	using RunGen::Hash32;
	if (Count < 0)
	{
		static const int32 Odds[] = { 0, 0, 1, 1, 1, 1, 2, 2, 2, 3 };   // в среднем чуть больше одного тела на комнату
		Count = Odds[Hash32({ Seed, 1U }) % UE_ARRAY_COUNT(Odds)];
	}
	if (Count <= 0)
	{
		return 0;
	}
	const FVector Origin = GetActorLocation();
	FCollisionQueryParams Params(FName(TEXT("RunCorpse")), false);
	if (const APawn* Pawn = UGameplayStatics::GetPlayerPawn(this, 0))
	{
		Params.AddIgnoredActor(Pawn);
	}
	const auto Free = [&](const FVector& At, float R)
	{
		return !GetWorld()->OverlapBlockingTestByChannel(FVector(At.X, At.Y, Origin.Z + 20.f + R), FQuat::Identity, ECC_WorldStatic,
			FCollisionShape::MakeSphere(R), Params);
	};
	TArray<FVector> Keep = GetSpots(TEXT("ItemSpot"));
	Keep.Append(GetSpots(TEXT("NoteSpot")));
	const auto NearKeep = [&](const FVector& At, float R)
	{
		for (const FVector& K : Keep)
		{
			if (FVector::Dist2D(K, At) < R)
			{
				return true;
			}
		}
		for (int32 D = 0; D < 4; ++D)
		{
			if (FVector::Dist2D(Origin + Dir(D) * InnerFace(D), At) < 190.f)   // проход к двери свободен
			{
				return true;
			}
		}
		return false;
	};

	struct FSpot
	{
		FVector At;
		float Yaw;
	};
	TArray<FSpot> OnFloor, AtWall, InWall, OnTable, OnConsole, OnLongTable;

	// пол: тело длиной около 1,7 м — свободны середина и две точки вдоль него
	for (float X = -HalfX + 120.f; X <= HalfX - 120.f; X += 60.f)
	{
		for (float Y = -HalfY + 120.f; Y <= HalfY - 120.f; Y += 60.f)
		{
			const FVector At = Origin + FVector(X, Y, 0.f);
			const float Yaw = 360.f * Unit(Hash32({ Seed, 10U, static_cast<uint32>(X + 1000.f), static_cast<uint32>(Y + 1000.f) }));
			const FVector Along = FRotator(0.f, Yaw, 0.f).Vector();
			if (!NearKeep(At, 110.f) && Free(At, 45.f) && Free(At + Along * 60.f, 38.f) && Free(At - Along * 60.f, 38.f)
				&& Free(At + FRotator(0.f, Yaw + 90.f, 0.f).Vector() * 60.f, 38.f) && Free(At - FRotator(0.f, Yaw + 90.f, 0.f).Vector() * 60.f, 38.f))
			{
				OnFloor.Add({ At, Yaw });
			}
		}
	}

	TArray<FString> Names;
	TMap<FString, TArray<UStaticMeshComponent*>> Groups;
	CollectElements(Names, Groups);
	for (const FString& G : Names)
	{
		const TArray<UStaticMeshComponent*>& Parts = Groups[G];
		const UStaticMeshComponent* Base = nullptr;
		bool bNiche = false;
		for (const UStaticMeshComponent* P : Parts)
		{
			const FString N = P->GetName();
			Base = N == G ? P : Base;
			bNiche |= N.Contains(TEXT("FirstAid")) || N.Contains(TEXT("Extinguisher")) || N.Contains(TEXT("Emergency"));
		}
		if (!Base)
		{
			continue;
		}
		const FBox Box = Base->Bounds.GetBox();
		if (G.StartsWith(TEXT("Lining_")))
		{
			if (Box.Min.Z - Origin.Z > 50.f || bNiche)
			{
				continue;   // перемычки над проёмами и аварийные ниши — без тел
			}
			// колонка стоит серединой спины в точке привязки, +Y меша смотрит в комнату; лицо колонки — на Lining дальше
			const FVector Face = Base->GetRightVector();
			const FVector At = FVector(Base->GetComponentLocation().X, Base->GetComponentLocation().Y, Origin.Z) + Face * Lining;
			const float Yaw = Face.Rotation().Yaw - 90.f;   // у меша тела стена в −Y, тело в +Y
			if (NearKeep(At + Face * 50.f, 90.f))
			{
				continue;
			}
			if (Free(At + Face * 50.f, 36.f))
			{
				InWall.Add({ At, Yaw });
				if (Free(At + Face * 105.f, 40.f))
				{
					AtWall.Add({ At, Yaw });   // сидящему у стены нужно место для ног
				}
			}
			continue;
		}
		// мебель: коробка без поворота с ровным верхом на высоте от 0,5 до 1,05 м (койка, столешница, пульт),
		// на ней нет мест предметов и записок и ничего не стоит. Позы сделаны под стол 0,78 м и пульт 1,0 м:
		// на поверхности другой высоты тело ставится со сдвигом по высоте (лежащему вдоль края это не вредит)
		const float Turn = FMath::Abs(FMath::Fmod(Base->GetComponentRotation().Yaw, 90.f));
		const float Top = Box.Max.Z - Origin.Z;
		const bool bDebug = FParse::Param(FCommandLine::Get(), TEXT("RunCorpseDebug"));
		if (bDebug)
		{
			UE_LOG(LogTemp, Display, TEXT("Run: corpse furniture %s top %.0f size %.0f x %.0f turn %.0f"), *G, Top, Box.GetSize().X, Box.GetSize().Y, Turn);
		}
		if (Top < 52.f || Top > 106.f || (Turn > 1.f && Turn < 89.f))
		{
			continue;
		}
		// занята ли поверхность: на ней сейчас лежит вещь или записка (возможные, но пустые места не мешают)
		bool bUsed = false;
		for (const FVector& K : Occupied)
		{
			bUsed |= K.X > Box.Min.X - 12.f && K.X < Box.Max.X + 12.f && K.Y > Box.Min.Y - 12.f && K.Y < Box.Max.Y + 12.f;
		}
		if (bUsed)
		{
			if (bDebug)
			{
				UE_LOG(LogTemp, Display, TEXT("Run:   %s rejected: an item or a note lies on it"), *G);
			}
			continue;
		}
		const FVector C = Box.GetCenter(), E = Box.GetExtent();
		for (int32 Side = 0; Side < 4; ++Side)
		{
			// сторона, с которой к мебели можно подойти: перед её краем свободно
			const FVector Normal = Side == 0 ? FVector(1, 0, 0) : Side == 1 ? FVector(-1, 0, 0) : Side == 2 ? FVector(0, 1, 0) : FVector(0, -1, 0);
			const float Depth = 2.f * (Side < 2 ? E.X : E.Y), Length = 2.f * (Side < 2 ? E.Y : E.X);
			const FVector Edge = FVector(C.X, C.Y, Origin.Z) + Normal * (Depth * 0.5f);
			bool bNearThing = false;
			for (int32 D = 0; D < 4; ++D)
			{
				bNearThing |= FVector::Dist2D(Origin + Dir(D) * InnerFace(D), Edge + Normal * 55.f) < 190.f;   // проход к двери свободен
			}
			if (!Free(Edge + Normal * 55.f, 38.f) || bNearThing)
			{
				if (bDebug)
				{
					UE_LOG(LogTemp, Display, TEXT("Run:   %s side %d rejected: front blocked=%d near a door=%d"), *G, Side,
						Free(Edge + Normal * 55.f, 38.f) ? 0 : 1, bNearThing ? 1 : 0);
				}
				continue;
			}
			// над поверхностью чисто: в передних двух третях ничего выше 12 см не стоит (подушка — можно, монитор — нет)
			const FVector Along = FVector(-Normal.Y, Normal.X, 0.f);
			const FVector Mid = Edge - Normal * (Depth * 0.35f) + FVector(0.f, 0.f, Top + 28.f);
			const FVector Half = (Normal * (Depth * 0.35f)).GetAbs() + (Along * FMath::Max(10.f, Length * 0.5f - 10.f)).GetAbs() + FVector(0.f, 0.f, 16.f);
			const FBox Above(Mid - Half, Mid + Half);
			bool bClear = true;
			for (const TPair<FString, TArray<UStaticMeshComponent*>>& Other : Groups)
			{
				for (const UStaticMeshComponent* M : Other.Value)
				{
					bClear &= M == Base || !M->Bounds.GetBox().Intersect(Above);
				}
			}
			if (bDebug)
			{
				UE_LOG(LogTemp, Display, TEXT("Run:   %s side %d depth %.0f length %.0f clear above=%d"), *G, Side, Depth, Length, bClear ? 1 : 0);
			}
			if (!bClear)
			{
				continue;
			}
			const float Yaw = Normal.Rotation().Yaw - 90.f;   // у меша мебель в −Y, край поверхности — y = 0
			if (Top > 72.f && Top < 84.f && Depth >= 75.f && Length >= 70.f)
			{
				OnTable.Add({ Edge, Yaw });        // поперёк стола, ноги свисают до пола: только на высоте стола
			}
			if (Top < 88.f && Length >= 180.f && Depth >= 45.f)
			{
				OnLongTable.Add({ Edge + FVector(0.f, 0.f, Top - 78.f), Yaw });    // вдоль края: койка, стол
			}
			if (Top >= 88.f && Length >= 150.f && Depth >= 45.f)
			{
				OnConsole.Add({ Edge + FVector(0.f, 0.f, Top - 100.f), Yaw });      // вдоль края: столешница, пульт
			}
		}
	}

	// по телу: вид опоры по жребию, место — из свободных для этого вида; тела не ближе двух метров друг к другу
	struct FKind
	{
		TArray<FSpot>* Spots;
		const TCHAR* Poses[4];
		int32 Num;
		uint32 Weight;
	};
	FKind Kinds[] = {
		{ &OnFloor, { TEXT("Floor1"), TEXT("Floor2"), TEXT("Floor3"), TEXT("Curl1") }, 4, 30U },
		{ &OnFloor, { TEXT("Curl2"), TEXT("Curl3"), TEXT("Floor1"), TEXT("Floor3") }, 4, 10U },
		{ &AtWall, { TEXT("Wall1"), TEXT("Wall2"), TEXT("Wall3"), TEXT("Wall1") }, 3, 28U },
		{ &InWall, { TEXT("Embed1"), TEXT("Embed2"), TEXT("Embed3"), TEXT("Embed1") }, 3, 18U },
		{ &OnTable, { TEXT("Table1"), TEXT("Table1"), TEXT("Table1"), TEXT("Table1") }, 1, 14U },
		{ &OnLongTable, { TEXT("Table2"), TEXT("Table2"), TEXT("Table2"), TEXT("Table2") }, 1, 10U },
		{ &OnConsole, { TEXT("Console1"), TEXT("Console1"), TEXT("Console1"), TEXT("Console1") }, 1, 14U },
	};
	TArray<FVector> Placed;
	FString What;
	for (int32 I = 0; I < Count; ++I)
	{
		uint32 Total = 0;
		for (const FKind& K : Kinds)
		{
			Total += K.Spots->Num() > 0 ? K.Weight : 0U;
		}
		if (Total == 0)
		{
			break;
		}
		uint32 Roll = Hash32({ Seed, 20U, static_cast<uint32>(I) }) % Total;
		const FKind* Pick = nullptr;
		for (const FKind& K : Kinds)
		{
			const uint32 W = K.Spots->Num() > 0 ? K.Weight : 0U;
			if (!Pick && Roll < W)
			{
				Pick = &K;
			}
			Roll -= FMath::Min(Roll, W);
		}
		// отладка: -RunCorpsePose=Wall1 ставит только эту позу (проверка опоры и поворота)
		FString ForcePose;
		if (FParse::Value(FCommandLine::Get(), TEXT("RunCorpsePose="), ForcePose))
		{
			Pick = nullptr;
			for (const FKind& K : Kinds)
			{
				for (int32 N = 0; N < K.Num && !Pick; ++N)
				{
					Pick = ForcePose == K.Poses[N] && K.Spots->Num() > 0 ? &K : nullptr;
				}
			}
		}
		if (!Pick)
		{
			continue;
		}
		// место: первое подходящее, начиная со случайного
		const int32 Start = static_cast<int32>(Hash32({ Seed, 21U, static_cast<uint32>(I) }) % static_cast<uint32>(Pick->Spots->Num()));
		const FSpot* Spot = nullptr;
		for (int32 K = 0; K < Pick->Spots->Num() && !Spot; ++K)
		{
			const FSpot& Try = (*Pick->Spots)[(Start + K) % Pick->Spots->Num()];
			if (!Placed.ContainsByPredicate([&Try](const FVector& P) { return FVector::Dist2D(P, Try.At) < 200.f; }))
			{
				Spot = &Try;
			}
		}
		if (!Spot)
		{
			continue;
		}
		const FString Pose = ForcePose.IsEmpty() ? FString(Pick->Poses[Hash32({ Seed, 22U, static_cast<uint32>(I) }) % static_cast<uint32>(Pick->Num)]) : ForcePose;
		Out.Add({ Pose, Spot->At - Origin, Spot->Yaw });
		Placed.Add(Spot->At);
		What += FString::Printf(TEXT(" %s(%.0f,%.0f)"), *Pose, Spot->At.X - Origin.X, Spot->At.Y - Origin.Y);
	}
	SpawnCorpses(Out);
	UE_LOG(LogTemp, Display, TEXT("Run: corpses %d of %d:%s | spots floor %d wall %d embed %d table %d long %d console %d"), Placed.Num(), Count, *What,
		OnFloor.Num(), AtWall.Num(), InWall.Num(), OnTable.Num(), OnLongTable.Num(), OnConsole.Num());
	return Placed.Num();
}
