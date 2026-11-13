#include "RunDirector.h"

#include "Components/InputComponent.h"
#include "Engine/World.h"
#include "GameFramework/Pawn.h"
#include "GameFramework/PlayerController.h"
#include "InputCoreTypes.h"
#include "Kismet/GameplayStatics.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"
#include "RunHUD.h"
#include "RunItem.h"
#include "RunRoom.h"

DEFINE_LOG_CATEGORY_STATIC(LogRun, Log, All);

using namespace RunGen;

ARunDirector::ARunDirector()
{
	PrimaryActorTick.bCanEverTick = true;
	SetRootComponent(CreateDefaultSubobject<USceneComponent>(TEXT("Root")));
}

ARunDirector::~ARunDirector() = default;

int32 ARunDirector::GetHealth() const
{
	return Layout ? Layout->Cfg.Health : 0;
}

void ARunDirector::BeginPlay()
{
	Super::BeginPlay();

	uint32 CmdSeed = 0;
	if (FParse::Value(FCommandLine::Get(), TEXT("RunSeed="), CmdSeed))
	{
		Seed = CmdSeed;
	}
	else if (FixedSeed != 0)
	{
		Seed = static_cast<uint32>(FixedSeed);
	}
	else
	{
		Seed = Hash32({ static_cast<uint32>(FDateTime::UtcNow().GetTicks() & 0xFFFFFFFF), static_cast<uint32>(FPlatformTime::Cycles()) });
	}
	bSelfTest = FParse::Param(FCommandLine::Get(), TEXT("RunSelfTest"));
	bShowDebug = bDebugAtStart || FParse::Param(FCommandLine::Get(), TEXT("RunDebug"));

	Layout = MakeUnique<FRunLayout>(Seed);
	// Стартовая рубка — комната набора «только блокнот», в которой ещё лежит сам блокнот.
	FRunKeyState& StartKey = Keys.Add(Anchor);
	StartKey.Content = Layout->StartRoom();
	for (int32 It : StartKey.Content.Items)
	{
		StartKey.Items.Add({ It, false, FVector::ZeroVector });
	}
	StartKey.NoteRead.Init(false, StartKey.Content.Notes.Num());
	FRunRoomState Start;
	Start.Key = Anchor;
	Start.bVisited = true;
	Rooms.Add(Start);
	CurrentRoom = 0;
	SpawnRoom(0, GetActorLocation(), -1);
	UE_LOG(LogRun, Display, TEXT("Run: seed=%u"), Seed);
	BuildSolution();
	for (const FString& Line : Solution)
	{
		UE_LOG(LogRun, Display, TEXT("Run: solution: %s"), *Line);
	}
	LogRoom(TEXT("start"));
}

void ARunDirector::BuildSolution()
{
	const TArray<int32>& RI = Layout->RoleItem;
	auto Name = [&](int32 Role) { return ItemName(RI[Role]); };
	auto TypeOf = [&](int32 Key)
	{
		int32 Type = 0, Sw = 0;
		Layout->Look(Key, Type, Sw);
		return FString(RoomTypeName(Type));
	};
	const FString L = Name(RoleL), K1 = Name(RoleK1), K2 = Name(RoleK2), K3 = Name(RoleK3);
	Solution.Reset();
	Solution.Add(FString::Printf(TEXT("SOLUTION, seed %u. Any door works: only the pocket matters. Junk items and the notebook do not change the room."), Seed));
	Solution.Add(TEXT("Shortest way:"));
	Solution.Add(FString::Printf(TEXT("  1. Bridge: take Notebook + %s"), *L));
	Solution.Add(FString::Printf(TEXT("  2. door -> %s: take %s"), *TypeOf(MaskL), *K1));
	Solution.Add(FString::Printf(TEXT("  3. door -> %s: take %s (pocket is full now)"), *TypeOf(MaskL | MaskK1), *K2));
	Solution.Add(FString::Printf(TEXT("  4. door -> %s: drop %s, take %s"), *TypeOf(MaskL | MaskK1 | MaskK2), *L, *K3));
	Solution.Add(TEXT("  5. door -> Engine: engines fixed. Drop everything except Notebook"));
	Solution.Add(TEXT("  6. door -> Bridge: the end"));
	Solution.Add(TEXT("All safe pockets (what matters in the pocket -> room, what lies there):"));
	Solution.Add(FString::Printf(TEXT("  [Notebook only] -> Bridge: %s"), *L));
	Solution.Add(TEXT("  [nothing at all] -> Living: nothing needed"));
	Solution.Add(FString::Printf(TEXT("  [%s] -> %s: %s"), *L, *TypeOf(MaskL), *K1));
	Solution.Add(FString::Printf(TEXT("  [%s, %s] -> %s: %s"), *L, *K1, *TypeOf(MaskL | MaskK1), *K2));
	Solution.Add(FString::Printf(TEXT("  [%s] -> %s: %s"), *K1, *TypeOf(MaskK1), *K2));
	Solution.Add(FString::Printf(TEXT("  [%s, %s, %s] -> %s: %s"), *L, *K1, *K2, *TypeOf(MaskL | MaskK1 | MaskK2), *K3));
	Solution.Add(FString::Printf(TEXT("  [%s, %s] -> %s: %s"), *K1, *K2, *TypeOf(MaskK1 | MaskK2), *K3));
	Solution.Add(FString::Printf(TEXT("  [%s, %s, %s] -> Engine"), *K1, *K2, *K3));
	FString Extras, Junk;
	for (int32 R = NumChain; R < Layout->NumSig; ++R)
	{
		Extras += (Extras.IsEmpty() ? TEXT("") : TEXT(", ")) + ItemName(RI[R]);
	}
	for (int32 It : Layout->Dummies)
	{
		Junk += (Junk.IsEmpty() ? TEXT("") : TEXT(", ")) + ItemName(It);
	}
	Solution.Add(TEXT("Any other pocket leads to an anomaly room."));
	Solution.Add(FString::Printf(TEXT("Trap items (any pocket with one of them is wrong): %s"), *Extras));
	Solution.Add(FString::Printf(TEXT("Junk items (change nothing): %s"), *Junk));
}

FRunKeyState& ARunDirector::KeyState(int32 Key)
{
	if (FRunKeyState* Found = Keys.Find(Key))
	{
		return *Found;
	}
	FRunKeyState& State = Keys.Add(Key);
	State.Content = Layout->Room(Key);
	for (int32 It : State.Content.Items)
	{
		State.Items.Add({ It, false, FVector::ZeroVector });
	}
	State.NoteRead.Init(false, State.Content.Notes.Num());
	return State;
}

void ARunDirector::SetupPlayer()
{
	APlayerController* PC = UGameplayStatics::GetPlayerController(this, 0);
	APawn* Pawn = PC ? PC->GetPawn() : nullptr;
	if (!Pawn || !RoomActor)
	{
		return;
	}
	// игрок приходит в себя в стартовой рубке, к югу от поста капитана, лицом на север
	Pawn->SetActorLocation(RoomActor->GetActorLocation() + FVector(-200.f, 0.f, 100.f), false, nullptr, ETeleportType::TeleportPhysics);
	PC->SetControlRotation(FRotator(-10.f, 0.f, 0.f));

	EnableInput(PC);
	if (InputComponent)
	{
		InputComponent->BindKey(EKeys::E, IE_Pressed, this, &ARunDirector::OnInteract);
		InputComponent->BindKey(EKeys::One, IE_Pressed, this, &ARunDirector::OnDrop1);
		InputComponent->BindKey(EKeys::Two, IE_Pressed, this, &ARunDirector::OnDrop2);
		InputComponent->BindKey(EKeys::Three, IE_Pressed, this, &ARunDirector::OnDrop3);
		InputComponent->BindKey(EKeys::Four, IE_Pressed, this, &ARunDirector::OnDrop4);
		InputComponent->BindKey(EKeys::Tab, IE_Pressed, this, &ARunDirector::OnToggleJournal);
		// не F1–F12: в редакторе это клавиши режимов вида (F1 — каркас, F2 — без света, F3 — со светом)
		InputComponent->BindKey(EKeys::H, IE_Pressed, this, &ARunDirector::OnToggleDebug);
	}
	PC->ClientSetHUD(ARunHUD::StaticClass());
	bPlayerReady = true;
	Say(TEXT("You wake up on the bridge. Something is very wrong with the doors."), 7.f);
}

void ARunDirector::SpawnRoom(int32 RoomId, const FVector& Location, int32 ArrivalDoor)
{
	const TCHAR* TypeName = RoomTypeName(KeyState(Rooms[RoomId].Key).Content.RoomType);
	const FString Path = FString::Printf(TEXT("/Game/Game/Rooms/BP_Room_%s.BP_Room_%s_C"), TypeName, TypeName);
	UClass* Cls = StaticLoadClass(ARunRoom::StaticClass(), nullptr, *Path);
	if (!Cls)
	{
		UE_LOG(LogRun, Error, TEXT("Run: нет блюпринта комнаты %s, ставлю пустую"), *Path);
		Cls = ARunRoom::StaticClass();
	}
	FActorSpawnParameters Params;
	Params.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
	RoomActor = GetWorld()->SpawnActor<ARunRoom>(Cls, Location, FRotator::ZeroRotator, Params);
	RoomActor->RoomId = RoomId;
	RoomActor->Director = this;
	RoomActor->SetArrivalDoor(ArrivalDoor);
	SpawnRoomContents();
}

ARunItem* ARunDirector::SpawnItemActor(int32 Item, int32 NoteIndex, const FVector& Location)
{
	ARunItem* Actor = GetWorld()->SpawnActor<ARunItem>(ARunItem::StaticClass(), Location, FRotator::ZeroRotator);
	Actor->Setup(Item, NoteIndex, NoteIndex >= 0 ? FString(TEXT("Note")) : ItemName(Item));
	ItemActors.Add(Actor);
	return Actor;
}

void ARunDirector::SpawnRoomContents()
{
	for (ARunItem* A : ItemActors)
	{
		if (A)
		{
			A->Destroy();
		}
	}
	ItemActors.Reset();

	FRunKeyState& State = CurrentKeyState();
	const FVector Origin = RoomActor->GetActorLocation();
	TArray<FVector> ItemSpots = RoomActor->GetSpots(TEXT("ItemSpot"));
	TArray<FVector> NoteSpots = RoomActor->GetSpots(TEXT("NoteSpot"));
	// на какие метки лягут вещи, решают зерно и набор: комната набора всегда выглядит одинаково
	const uint32 Shift = Hash32({ Seed, 100U, static_cast<uint32>(State.Content.Key) });
	int32 Unplaced = 0;
	for (const FRunPlacedItem& P : State.Items)
	{
		FVector Loc;
		if (P.bHasPos)
		{
			Loc = Origin + P.LocalPos;
		}
		else if (ItemSpots.Num() > 0)
		{
			Loc = ItemSpots[(Shift + Unplaced++) % ItemSpots.Num()] + FVector(0, 0, 11.f);
		}
		else
		{
			Loc = Origin + FVector(-150.f + 60.f * Unplaced++, 250.f, 11.f);
		}
		SpawnItemActor(P.Item, -1, Loc);
	}
	for (int32 I = 0; I < State.Content.Notes.Num(); ++I)
	{
		if (!State.NoteRead[I])
		{
			const FVector Loc = NoteSpots.Num() > 0 ? NoteSpots[(Shift / 7U + I) % NoteSpots.Num()] + FVector(0, 0, 1.f)
				: Origin + FVector(-150.f + 60.f * I, -250.f, 1.f);
			SpawnItemActor(0, I, Loc);
		}
	}
}

void ARunDirector::BeginTransition(ARunRoom* Room, int32 Door)
{
	if (bBusy || Phase != ERunPhase::Playing || Room != RoomActor)
	{
		return;
	}
	bBusy = true;
	PendingDoor = Door;
	Room->bSealed = true;
	SwapAt = GetWorld()->GetTimeSeconds() + TransitionSeconds;
}

void ARunDirector::DoSwap()
{
	const int32 Door = PendingDoor;
	const int32 From = CurrentRoom;
	int32 To = Rooms[From].Doors[Door];
	if (To < 0)
	{
		// нераскрытая дверь: комнату определяет карман в этот момент, дальше дверь не меняется (5.2)
		const int32 Key = Layout->PocketKey(Pocket);
		FRunRoomState State;
		State.Key = Key;
		State.bAnomalyActive = KeyState(Key).Content.Anomaly != 0;   // за новой дверью аномалия снова действует
		State.Doors[RunRoomGeo::Opposite(Door)] = From;              // обратный путь ведёт туда, откуда пришёл
		To = Rooms.Add(State);
		Rooms[From].Doors[Door] = To;
	}
	const FVector NewLocation = RoomActor->GetActorLocation() + RunRoomGeo::NeighborOffset(Door);
	ARunRoom* Old = RoomActor;
	CurrentRoom = To;
	SpawnRoom(To, NewLocation, RunRoomGeo::Opposite(Door));
	Old->Destroy();
	bBusy = false;
	PendingDoor = -1;
	EnterRoom(To);
}

void ARunDirector::EnterRoom(int32 RoomId)
{
	FRunRoomState& State = Rooms[RoomId];
	const FRunRoomContent& Content = KeyState(State.Key).Content;
	const bool bFirst = !State.bVisited;
	State.bVisited = true;
	LogRoom(bFirst ? TEXT("new") : TEXT("back"));

	if (RoomClass(State.Key) == ClsEngine)
	{
		if (!bEngineFixed)
		{
			bEngineFixed = true;
			Say(TEXT("The warp engines hum back to life. Now get back to the bridge."), 8.f);
		}
		return;
	}
	if (bEngineFixed && Content.RoomType == Bridge)
	{
		// концовка наступает раньше, чем сработает аномалия в этой рубке
		Phase = ERunPhase::Won;
		RestartAt = GetWorld()->GetTimeSeconds() + 8.f;
		Say(TEXT("You are on the bridge. The ship tears itself free. YOU ESCAPED."), 8.f);
		return;
	}
	if (State.bAnomalyActive)
	{
		++Hits;
		if (Hits >= GetHealth())
		{
			Phase = ERunPhase::Dead;
			RestartAt = GetWorld()->GetTimeSeconds() + 5.f;
			Say(FString::Printf(TEXT("%s. It was one hit too many. YOU DIED."), AnomalyName(Content.Anomaly)), 5.f);
		}
		else
		{
			Say(FString::Printf(TEXT("Anomaly: %s. You are hurt."), AnomalyName(Content.Anomaly)), 4.f);
		}
	}
}

void ARunDirector::Say(const FString& Text, float Seconds)
{
	Message = Text;
	MessageUntil = GetWorld()->GetTimeSeconds() + Seconds;
}

FString ARunDirector::GetMessage() const
{
	return GetWorld() && GetWorld()->GetTimeSeconds() < MessageUntil ? Message : FString();
}

ARunItem* ARunDirector::NearestItem() const
{
	const APawn* Pawn = UGameplayStatics::GetPlayerPawn(this, 0);
	if (!Pawn)
	{
		return nullptr;
	}
	ARunItem* Best = nullptr;
	float BestDist = 170.f;
	for (ARunItem* A : ItemActors)
	{
		if (A)
		{
			const float D = FVector::Dist2D(A->GetActorLocation(), Pawn->GetActorLocation());
			if (D < BestDist)
			{
				BestDist = D;
				Best = A;
			}
		}
	}
	return Best;
}

FString ARunDirector::GetPrompt() const
{
	if (Phase != ERunPhase::Playing || bBusy)
	{
		return FString();
	}
	if (const ARunItem* A = NearestItem())
	{
		if (A->IsNote())
		{
			return TEXT("[E] Read the note");
		}
		return Pocket.Num() < PocketSlots ? FString::Printf(TEXT("[E] Take %s"), *ItemNoun(A->ItemId).Replace(TEXT("the "), TEXT("")))
			: FString(TEXT("Pocket is full. Drop something with [1]-[4]"));
	}
	return FString();
}

void ARunDirector::AddToJournal(const FString& Text)
{
	if (!Journal.Contains(Text))
	{
		Journal.Add(Text);
	}
}

void ARunDirector::OnInteract()
{
	if (Phase != ERunPhase::Playing || bBusy)
	{
		return;
	}
	ARunItem* A = NearestItem();
	if (!A)
	{
		return;
	}
	FRunKeyState& State = CurrentKeyState();
	if (A->IsNote())
	{
		const FString Text = State.Content.Notes[A->NoteIndex].Text();
		State.NoteRead[A->NoteIndex] = true;
		AddToJournal(Text);   // записки складываются в блокнот (5.6)
		Say(Text, 9.f);
	}
	else
	{
		if (Pocket.Num() >= PocketSlots)
		{
			Say(TEXT("Pocket is full."), 2.f);
			return;
		}
		const int32 Item = A->ItemId;
		const int32 Index = State.Items.IndexOfByPredicate([Item](const FRunPlacedItem& P) { return P.Item == Item; });
		if (Index != INDEX_NONE)
		{
			State.Items.RemoveAt(Index);
		}
		Pocket.Add(Item);
		if (Item == Notebook && !bFirstNoteRead)
		{
			bFirstNoteRead = true;
			const FString Text = Layout->FirstNote.Text();
			Journal.Insert(Text, 0);
			Say(Text, 10.f);
		}
	}
	ItemActors.Remove(A);
	A->Destroy();
}

void ARunDirector::OnDrop(int32 Slot)
{
	if (Phase != ERunPhase::Playing || bBusy || !Pocket.IsValidIndex(Slot) || !RoomActor)
	{
		return;
	}
	const APawn* Pawn = UGameplayStatics::GetPlayerPawn(this, 0);
	if (!Pawn)
	{
		return;
	}
	const int32 Item = Pocket[Slot];
	Pocket.RemoveAt(Slot);
	// выброшенный предмет остаётся лежать там, где его выбросили (5.3)
	FVector Loc = Pawn->GetActorLocation() + Pawn->GetActorForwardVector() * 70.f;
	FHitResult Hit;
	if (GetWorld()->LineTraceSingleByChannel(Hit, Loc + FVector(0, 0, 50.f), Loc - FVector(0, 0, 300.f), ECC_Visibility))
	{
		Loc = Hit.ImpactPoint + FVector(0, 0, 11.f);
	}
	CurrentKeyState().Items.Add({ Item, true, Loc - RoomActor->GetActorLocation() });
	SpawnItemActor(Item, -1, Loc);
}

void ARunDirector::OnToggleJournal()
{
	bShowJournal = !bShowJournal && Pocket.Contains(Notebook);
	if (!bShowJournal && !Pocket.Contains(Notebook))
	{
		Say(TEXT("You need the notebook to read your notes."), 3.f);
	}
}

void ARunDirector::OnToggleDebug()
{
	bShowDebug = !bShowDebug;
}

FString ARunDirector::GetDebugLine() const
{
	if (!Layout || !Rooms.IsValidIndex(CurrentRoom))
	{
		return FString();
	}
	const FRunRoomState& S = Rooms[CurrentRoom];
	const FRunRoomContent& C = CurrentContent();
	const int32 NextKey = Layout->PocketKey(Pocket);
	int32 NextType = 0, NextSw = 0;
	Layout->Look(NextKey, NextType, NextSw);
	const int32 NextAnomaly = Layout->AnomalyOf(NextKey);
	return FString::Printf(TEXT("room #%d %s, anomaly %s%s | next new door with this pocket -> %s, %s"),
		CurrentRoom, RoomTypeName(C.RoomType), AnomalyName(C.Anomaly), S.bAnomalyActive ? TEXT(" (active)") : TEXT(""),
		RoomTypeName(NextType), NextAnomaly ? *FString::Printf(TEXT("ANOMALY %s"), AnomalyName(NextAnomaly)) : TEXT("safe"));
}

void ARunDirector::LogRoom(const TCHAR* Why) const
{
	const FRunRoomState& S = Rooms[CurrentRoom];
	const FRunKeyState& K = Keys.FindChecked(S.Key);
	FString Items;
	for (const FRunPlacedItem& P : K.Items)
	{
		Items += (Items.IsEmpty() ? TEXT("") : TEXT(", ")) + ItemName(P.Item);
	}
	FString PocketNames;
	for (int32 It : Pocket)
	{
		PocketNames += (PocketNames.IsEmpty() ? TEXT("") : TEXT(", ")) + ItemName(It);
	}
	UE_LOG(LogRun, Display, TEXT("Run: %s room=%d type=%s key=%d anomaly=%s notes=%d items=[%s] pocket=[%s] hits=%d doors=[%d,%d,%d,%d]"),
		Why, CurrentRoom, RoomTypeName(K.Content.RoomType), S.Key, AnomalyName(K.Content.Anomaly),
		K.Content.Notes.Num(), *Items, *PocketNames, Hits, S.Doors[0], S.Doors[1], S.Doors[2], S.Doors[3]);
}

void ARunDirector::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);
	const float Now = GetWorld()->GetTimeSeconds();
	if (!bPlayerReady)
	{
		SetupPlayer();
		return;
	}
	if (bBusy && Now >= SwapAt && RoomActor && RoomActor->AllLeavesClosed())
	{
		DoSwap();
	}
	if (Phase != ERunPhase::Playing && Now >= RestartAt && !bSelfTest)
	{
		UGameplayStatics::OpenLevel(this, FName(*UGameplayStatics::GetCurrentLevelName(this)));
		return;
	}
	if (bSelfTest)
	{
		TickSelfTest();
	}
}

// Самопроверка: взять блокнот; пройти на север дважды — обе комнаты должны быть той же рубкой
// с теми же вещами; взять проводника (он лежит в рубке); пройти на север — комната набора {L};
// вернуться назад (S) — снова рубка; выбросить всё; пройти на восток — жилая комната пустого кармана.
// Игрока переносим в центр комнаты, затем в тамбур: дальше работает обычная логика. Итог — строки «Run:».
void ARunDirector::TickSelfTest()
{
	const float Now = GetWorld()->GetTimeSeconds();
	if (bBusy || Now < TestNextAt || !RoomActor)
	{
		return;
	}
	APawn* Pawn = UGameplayStatics::GetPlayerPawn(this, 0);
	auto MoveTo = [&](const FVector& Loc)
	{
		Pawn->SetActorLocation(Loc + FVector(0, 0, 100.f), false, nullptr, ETeleportType::TeleportPhysics);
	};
	auto GoToItem = [&](int32 Item)
	{
		for (ARunItem* A : ItemActors)
		{
			if (A && !A->IsNote() && A->ItemId == Item)
			{
				MoveTo(A->GetActorLocation());
				return;
			}
		}
		UE_LOG(LogRun, Error, TEXT("Run: test: предмета %s в комнате нет"), *ItemName(Item));
	};
	// 100 — подойти к блокноту, 101 — взять, 102 — подойти к проводнику, 103 — выбросить всё,
	// 104 — конец, −1 — встать в центр комнаты, 0..3 — войти в тамбур двери
	static const int32 Steps[] = { 100, 101, -1, 0, -1, 0, 102, 101, -1, 0, -1, 1, 103, -1, 3, 104 };
	if (TestStep >= UE_ARRAY_COUNT(Steps))
	{
		FPlatformMisc::RequestExit(false);
		return;
	}
	TestNextAt = Now + 0.8f;
	const int32 Step = Steps[TestStep++];
	switch (Step)
	{
	case 100: GoToItem(Notebook); break;
	case 101: OnInteract(); UE_LOG(LogRun, Display, TEXT("Run: test took, pocket=%d journal=%d key=%d"), Pocket.Num(), Journal.Num(), Layout->PocketKey(Pocket)); break;
	case 102: GoToItem(Layout->RoleItem[RoleL]); break;
	case 103: while (Pocket.Num() > 0) { OnDrop(0); } UE_LOG(LogRun, Display, TEXT("Run: test dropped all, pocket=%d key=%d"), Pocket.Num(), Layout->PocketKey(Pocket)); break;
	case 104: UE_LOG(LogRun, Display, TEXT("Run: test done rooms=%d sets=%d hits=%d"), Rooms.Num(), Keys.Num(), Hits); break;
	case -1: MoveTo(RoomActor->GetActorLocation() + FVector(-330.f, 120.f, 0.f)); break;
	default: MoveTo(RoomActor->VestibuleCenter(Step)); break;
	}
}
