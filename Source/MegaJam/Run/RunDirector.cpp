#include "RunDirector.h"

#include "Animation/AnimSequenceBase.h"
#include "Animation/AnimSingleNodeInstance.h"
#include "Camera/CameraActor.h"
#include "Camera/CameraComponent.h"
#include "Components/InputComponent.h"
#include "Components/PostProcessComponent.h"
#include "Components/SpotLightComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/SkeletalMesh.h"
#include "Engine/StaticMesh.h"
#include "Engine/World.h"
#include "GameFramework/Character.h"
#include "GameFramework/HUD.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "GameFramework/Pawn.h"
#include "GameFramework/PlayerController.h"
#include "GameFramework/SpringArmComponent.h"
#include "InputCoreTypes.h"
#include "Kismet/GameplayStatics.h"
#include "Kismet/KismetSystemLibrary.h"
#include "Materials/MaterialInterface.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"
#include "Misc/Paths.h"
#include "RunEnemy.h"
#include "RunHUD.h"
#include "RunItem.h"
#include "RunRoom.h"
#include "RunThreat.h"
#include "UObject/ConstructorHelpers.h"
#include "UnrealClient.h"

DEFINE_LOG_CATEGORY_STATIC(LogRun, Log, All);

using namespace RunGen;
using namespace RunEnemyTune;

ARunDirector::ARunDirector()
{
	PrimaryActorTick.bCanEverTick = true;
	SetRootComponent(CreateDefaultSubobject<USceneComponent>(TEXT("Root")));
	static ConstructorHelpers::FObjectFinder<USkeletalMesh> Hero(TEXT("/Game/Characters/Engineer/SK_Engineer.SK_Engineer"));
	HeroMesh = Hero.Object;
}

ARunDirector::~ARunDirector() = default;

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
	bShowTest = FParse::Param(FCommandLine::Get(), TEXT("RunShow"));
	bSelfTest = bAutoPlayTest || bShowTest || FParse::Param(FCommandLine::Get(), TEXT("RunSelfTest"));
	bWinTest = FParse::Param(FCommandLine::Get(), TEXT("RunWin"));
	RunStartAt = GetWorld()->GetTimeSeconds();
	FParse::Value(FCommandLine::Get(), TEXT("RunThreat="), ForceThreatKind);
	FParse::Value(FCommandLine::Get(), TEXT("RunBurned="), ForceBurned);
	FParse::Value(FCommandLine::Get(), TEXT("RunEmergency="), ForceEmergency);
	FParse::Value(FCommandLine::Get(), TEXT("RunExposure="), ExposureBias);
	// экспозиция закреплена на весь забег: чёрное остаётся чёрным, аварийная комната — тёмной
	Post = NewObject<UPostProcessComponent>(this, TEXT("Post"));
	Post->SetupAttachment(GetRootComponent());
	Post->bUnbound = true;
	Post->Settings.bOverride_AutoExposureMethod = true;
	Post->Settings.AutoExposureMethod = EAutoExposureMethod::AEM_Manual;
	Post->Settings.bOverride_AutoExposureApplyPhysicalCameraExposure = true;
	Post->Settings.AutoExposureApplyPhysicalCameraExposure = false;
	Post->Settings.bOverride_AutoExposureBias = true;
	Post->Settings.AutoExposureBias = ExposureBias;
	Post->RegisterComponent();
	bShowDebug = bDebugAtStart || FParse::Param(FCommandLine::Get(), TEXT("RunDebug"));

	Layout = MakeUnique<FRunLayout>(Seed);
	// Стартовая рубка — комната набора «только блокнот», в которой ещё лежит сам блокнот.
	FRunKeyState& StartKey = Keys.Add(Anchor);
	StartKey.Content = Layout->StartRoom();
	for (int32 It : StartKey.Content.Items)
	{
		AddPlaced(StartKey, It);
	}
	AddMedkit(StartKey);
	StartKey.NoteRead.Init(false, StartKey.Content.Notes.Num());
	FRunRoomState Start;
	Start.Key = Anchor;
	Start.bVisited = true;
	SeenKeys.Add(Anchor);   // в стартовой рубке игрок уже был
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
		AddPlaced(State, It);
	}
	AddMedkit(State);
	State.NoteRead.Init(false, State.Content.Notes.Num());
	return State;
}

FRunPlacedItem& ARunDirector::AddPlaced(FRunKeyState& State, int32 Item)
{
	FRunPlacedItem& P = State.Items.AddDefaulted_GetRef();
	P.Item = Item;
	P.Spot = State.Items.Num() - 1;
	P.Uid = NextUid++;
	return P;
}

// Аптечка лежит в аварийной нише не в каждой комнате: в какой есть и в какой нише — решают зерно и набор,
// поэтому комната набора всегда выглядит одинаково. Взятая не возвращается, как и любая вещь (решение автора 14.11).
void ARunDirector::AddMedkit(FRunKeyState& State)
{
	const uint32 H = Hash32({ Seed, 301U, static_cast<uint32>(State.Content.Key) });
	if (H % 100U < static_cast<uint32>(FMath::Clamp(MedkitChancePercent, 0, 100)))
	{
		AddPlaced(State, Medkit).Niche = static_cast<int32>((H / 100U) % 1024U);
	}
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

	// герой вместо манекена шаблона: скелет тот же (SK_Mannequin), поэтому смещение меша и анимации шаблона подходят
	ACharacter* Hero = Cast<ACharacter>(Pawn);
	if (Hero && HeroMesh)
	{
		Hero->GetMesh()->SetSkeletalMeshAsset(HeroMesh);
	}
	if (Hero)
	{
		Hero->GetMesh()->SetReceivesDecals(false);   // копоть выгоревшей комнаты на героя не ложится
		// присед для дыма (решение автора 15.11): капсула 2 × 48 см, голова ниже слоя дыма (RunThreatTune::SmokeBottom)
		Hero->GetCharacterMovement()->GetNavAgentPropertiesRef().bCanCrouch = true;
		Hero->GetCharacterMovement()->SetCrouchedHalfHeight(48.f);
	}

	// камера за правым плечом и ближе: в тесной комнате персонаж не должен закрывать пол-экрана
	if (USpringArmComponent* Boom = Pawn->FindComponentByClass<USpringArmComponent>())
	{
		Boom->TargetArmLength = BoomArm;
		Boom->SocketOffset = FVector(0.f, 55.f, BoomRise);
	}

	// вещь в руке: держится за кисть героя. Поворот свой (по направлению героя), а не кисти:
	// оси кости у манекена неочевидны, а так вещь висит под рукой ровно при любой анимации
	if (Hero)
	{
		HandPivot = NewObject<USceneComponent>(this, TEXT("HandPivot"));
		HandPivot->SetupAttachment(Hero->GetMesh(), TEXT("hand_r"));
		HandPivot->SetUsingAbsoluteRotation(true);
		HandPivot->RegisterComponent();
		HandMesh = NewObject<UStaticMeshComponent>(this, TEXT("HandMesh"));
		HandMesh->SetupAttachment(HandPivot);
		HandMesh->SetCollisionEnabled(ECollisionEnabled::NoCollision);
		HandMesh->SetCastShadow(false);
		HandMesh->SetReceivesDecals(false);
		HandMesh->SetVisibility(false);
		HandMesh->RegisterComponent();
		// фонарик (вещь из каталога): в руке светит туда, куда смотрит камера (решение автора 15.11)
		Flashlight = NewObject<USpotLightComponent>(this, TEXT("Flashlight"));
		Flashlight->SetupAttachment(HandPivot);
		Flashlight->SetUsingAbsoluteRotation(true);
		Flashlight->SetMobility(EComponentMobility::Movable);
		Flashlight->SetIntensityUnits(ELightUnits::Unitless);
		Flashlight->SetIntensity(9000.f);
		Flashlight->SetAttenuationRadius(1600.f);
		Flashlight->SetOuterConeAngle(27.f);
		Flashlight->SetInnerConeAngle(11.f);
		Flashlight->SetLightColor(FLinearColor(1.f, 0.94f, 0.82f));
		Flashlight->SetCastShadows(true);
		Flashlight->SetVisibility(false);
		Flashlight->RegisterComponent();
	}
	// вещь на осмотре: перед камерой. Рисуется как «от первого лица» — придвинута к камере и не уходит в стену
	if (UCameraComponent* Camera = Pawn->FindComponentByClass<UCameraComponent>())
	{
		Camera->SetEnableFirstPersonScale(true);
		Camera->SetFirstPersonScale(0.5f);
		InspectPivot = NewObject<USceneComponent>(this, TEXT("InspectPivot"));
		InspectPivot->SetupAttachment(Camera);
		InspectPivot->SetRelativeLocation(FVector(50.f, 0.f, 2.f));
		InspectPivot->RegisterComponent();
		InspectMesh = NewObject<UStaticMeshComponent>(this, TEXT("InspectMesh"));
		InspectMesh->SetupAttachment(InspectPivot);
		InspectMesh->SetCollisionEnabled(ECollisionEnabled::NoCollision);
		InspectMesh->SetCastShadow(false);
		InspectMesh->SetReceivesDecals(false);
		InspectMesh->SetFirstPersonPrimitiveType(EFirstPersonPrimitiveType::FirstPerson);
		InspectMesh->SetVisibility(false);
		InspectMesh->RegisterComponent();
	}

	EnableInput(PC);
	if (InputComponent)
	{
		InputComponent->BindKey(EKeys::E, IE_Pressed, this, &ARunDirector::OnInteract);
		InputComponent->BindKey(EKeys::LeftMouseButton, IE_Pressed, this, &ARunDirector::OnUse);
		InputComponent->BindKey(EKeys::F, IE_Pressed, this, &ARunDirector::OnAttack);
		InputComponent->BindKey(EKeys::Enter, IE_Pressed, this, &ARunDirector::OnConfirm);
		// пауза: Esc в сборке; в редакторе Esc останавливает игру, поэтому есть ещё P. Клавиши паузы работают и на паузе.
		InputComponent->BindKey(EKeys::Escape, IE_Pressed, this, &ARunDirector::OnPause).bExecuteWhenPaused = true;
		InputComponent->BindKey(EKeys::P, IE_Pressed, this, &ARunDirector::OnPause).bExecuteWhenPaused = true;
		InputComponent->BindKey(EKeys::R, IE_Pressed, this, &ARunDirector::OnRestartKey).bExecuteWhenPaused = true;
		InputComponent->BindKey(EKeys::Q, IE_Pressed, this, &ARunDirector::OnQuitKey).bExecuteWhenPaused = true;
		// карман: 1–4 и колесо — взять вещь в руку, G — выбросить её, правая кнопка — рассмотреть,
		// левая — применить (аптечка) или ударить ключом (решение автора 14.11: инвентарь с вещью в руке)
		InputComponent->BindKey(EKeys::One, IE_Pressed, this, &ARunDirector::OnSelect1);
		InputComponent->BindKey(EKeys::Two, IE_Pressed, this, &ARunDirector::OnSelect2);
		InputComponent->BindKey(EKeys::Three, IE_Pressed, this, &ARunDirector::OnSelect3);
		InputComponent->BindKey(EKeys::Four, IE_Pressed, this, &ARunDirector::OnSelect4);
		InputComponent->BindKey(EKeys::MouseScrollUp, IE_Pressed, this, &ARunDirector::OnWheelUp);
		InputComponent->BindKey(EKeys::MouseScrollDown, IE_Pressed, this, &ARunDirector::OnWheelDown);
		InputComponent->BindKey(EKeys::G, IE_Pressed, this, &ARunDirector::OnDropHeld);
		InputComponent->BindKey(EKeys::RightMouseButton, IE_Pressed, this, &ARunDirector::OnInspect);
		InputComponent->BindKey(EKeys::Left, IE_Pressed, this, &ARunDirector::OnPagePrev);
		InputComponent->BindKey(EKeys::Right, IE_Pressed, this, &ARunDirector::OnPageNext);
		InputComponent->BindKey(EKeys::Up, IE_Pressed, this, &ARunDirector::OnBookmarkPrev);
		InputComponent->BindKey(EKeys::Down, IE_Pressed, this, &ARunDirector::OnBookmarkNext);
		InputComponent->BindKey(EKeys::Tab, IE_Pressed, this, &ARunDirector::OnToggleJournal);
		InputComponent->BindKey(EKeys::C, IE_Pressed, this, &ARunDirector::OnCrouchKey);
		InputComponent->BindKey(EKeys::T, IE_Pressed, this, &ARunDirector::TakeOffSuit);
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
	// выгоревшая комната: сразу после появления, пока по полу никто не ходил (сетка обхода строится позже)
	const int32 Key = Rooms[RoomId].Key;
	if (IsBurned(Key))
	{
		const FIntVector Burn = RoomActor->ApplyBurn(Hash32({ Seed, 301U, static_cast<uint32>(Key) }));
		UE_LOG(LogRun, Display, TEXT("Run: burned room=%d key=%d: burnt %d, sooted %d, decals %d"), RoomId, Key, Burn.X, Burn.Y, Burn.Z);
	}
	if (IsEmergency(Key))
	{
		const FIntVector E = RoomActor->ApplyEmergency();
		UE_LOG(LogRun, Display, TEXT("Run: emergency light room=%d key=%d: red %d, dimmed %d, panels %d"), RoomId, Key, E.X, E.Y, E.Z);
	}
	SpawnThreats(ArrivalDoor);
	UpdateDoorSigns();
}

// Аварийный свет (решение автора 15.11): чистый случай по зерну и набору, доля — EmergencyLightPercent.
bool ARunDirector::IsEmergency(int32 Key) const
{
	const FRunKeyState* State = Keys.Find(Key);
	if (!State)
	{
		return false;
	}
	const int32 Kind = State->Content.Anomaly != 0 && ForceThreatKind >= 1 && ForceThreatKind <= NumThreats ? ForceThreatKind : State->Content.Anomaly;
	if (Kind == ThreatFungus)
	{
		return false;   // у заросшей комнаты свой свет — болотный
	}
	if (ForceEmergency != 0)
	{
		return ForceEmergency > 0;
	}
	if (Rooms.Num() > 0 && Key == Rooms[0].Key)
	{
		return false;   // стартовая рубка (и финал в ней же) — с обычным светом: первый взгляд на корабль и контраст
	}
	FRng Rng({ Seed, 310U, static_cast<uint32>(Key) });
	return Rng.Below(100) < static_cast<uint32>(FMath::Clamp(EmergencyLightPercent, 0, 100));
}

bool ARunDirector::IsFlashlight(int32 Item)
{
	return Item >= 0 && ItemName(Item) == TEXT("Flashlight");
}

// Выгорела ли комната набора (DESIGN.md §14, решение автора 14.11): только опасная, чистый случай по зерну и набору,
// доля — BurnedRoomPercent. От вида угрозы и сложности не зависит.
bool ARunDirector::IsBurned(int32 Key) const
{
	const FRunKeyState* State = Keys.Find(Key);
	if (!State || State->Content.Anomaly == 0 || State->Content.Anomaly == ThreatFungus)
	{
		return false;   // заросшая грибами комната не горит: мох поверх копоти не читается
	}
	if (ForceBurned != 0)
	{
		return ForceBurned > 0;
	}
	FRng Rng({ Seed, 300U, static_cast<uint32>(Key) });
	return Rng.Below(100) < static_cast<uint32>(FMath::Clamp(BurnedRoomPercent, 0, 100));
}

static const TCHAR* DisplayRoomName(int32 Type)
{
	static const TCHAR* const Names[] = { TEXT("BRIDGE"), TEXT("CREW QUARTERS"), TEXT("LAB"), TEXT("LIFE SUPPORT"), TEXT("ENGINE ROOM"),
		TEXT("MEDBAY"), TEXT("CARGO"), TEXT("MESS HALL"), TEXT("COMPUTER CORE") };
	return Type >= 0 && Type < UE_ARRAY_COUNT(Names) ? Names[Type] : TEXT("UNKNOWN");
}

// Табло над дверями: раскрытая дверь показывает отсек, куда ведёт; нераскрытая мерцает прочерками.
void ARunDirector::UpdateDoorSigns()
{
	for (int32 D = 0; D < DoorsPerRoom; ++D)
	{
		const int32 To = Rooms[CurrentRoom].Doors[D];
		RoomActor->SetDoorSign(D, To >= 0 ? FString(DisplayRoomName(KeyState(Rooms[To].Key).Content.RoomType)) : FString());
	}
	RoomName = DisplayRoomName(CurrentContent().RoomType);
}

float ARunDirector::GetRunSeconds() const
{
	const float End = RunEndAt >= 0.f ? RunEndAt : (GetWorld() ? GetWorld()->GetTimeSeconds() : 0.f);
	return FMath::Max(0.f, End - RunStartAt);
}

bool ARunDirector::GetFollowerDoor(FVector& Out) const
{
	for (const FRunEnemyState& E : Enemies)
	{
		if (E.ArriveAt >= 0.f && RoomActor && E.ArriveDoor >= 0)
		{
			Out = RoomActor->VestibuleCenter(E.ArriveDoor) + FVector(0.f, 0.f, 120.f);
			return true;
		}
	}
	return false;
}

void ARunDirector::RestartRun()
{
	UGameplayStatics::SetGamePaused(this, false);
	UGameplayStatics::OpenLevel(this, FName(*UGameplayStatics::GetCurrentLevelName(this)));
}

void ARunDirector::OnPause()
{
	if (Phase != ERunPhase::Playing)
	{
		return;
	}
	bMenuPause = !bMenuPause;
	UGameplayStatics::SetGamePaused(this, bMenuPause);
}

void ARunDirector::OnRestartKey()
{
	if (bMenuPause)
	{
		RestartRun();
	}
}

void ARunDirector::OnQuitKey()
{
	if (bMenuPause)
	{
		UKismetSystemLibrary::QuitGame(this, UGameplayStatics::GetPlayerController(this, 0), EQuitPreference::Quit, false);
	}
}

// После смерти или победы: новый забег по клавише, не дожидаясь таймера.
void ARunDirector::OnConfirm()
{
	if (Phase != ERunPhase::Playing && GetWorld()->GetTimeSeconds() > RunEndAt + 1.f)
	{
		RestartRun();
	}
}

void ARunDirector::ShowTip(const FString& Text, float Seconds)
{
	if (GetWorld()->GetTimeSeconds() < TipUntil)
	{
		TipQueue.Add(Text);   // предыдущая ещё на экране
		return;
	}
	Tip = Text;
	TipUntil = GetWorld()->GetTimeSeconds() + Seconds;
}

FString ARunDirector::GetTip() const
{
	return GetWorld() && GetWorld()->GetTimeSeconds() < TipUntil ? Tip : FString();
}

void ARunDirector::OnDoorApproach()
{
	if (!bTipDoor && Pocket.Num() > 0 && Phase == ERunPhase::Playing)
	{
		bTipDoor = true;
		ShowTip(TEXT("Doors lead where your pocket decides."), 8.f);
	}
}

float ARunDirector::GetTransitionAlpha() const
{
	return bBusy && TransitionSeconds > 0.f ? FMath::Clamp((GetWorld()->GetTimeSeconds() - BusySince) / TransitionSeconds, 0.f, 1.f) : -1.f;
}

float ARunDirector::GetRoomTitleAlpha() const
{
	return GetWorld() ? FMath::Clamp(1.f - (GetWorld()->GetTimeSeconds() - RoomTitleAt) / 2.5f, 0.f, 1.f) : 0.f;
}

bool ARunDirector::GetPromptAnchor(FVector& Out) const
{
	if (Phase != ERunPhase::Playing || bBusy)
	{
		return false;
	}
	if (const ARunItem* A = NearestItem())
	{
		Out = A->GetActorLocation();
		return true;
	}
	return false;
}

// Персонаж сам дописывает строку в блокнот, когда есть прогресс (решение автора 13.11).
void ARunDirector::WriteProgress(const FString& Text)
{
	const FString Line = TEXT("+ ") + Text;
	if (!Journal.Contains(Line))
	{
		Journal.Add(Line);
		if (Pocket.Contains(Notebook))
		{
			bJournalUnread = true;
			ShowTip(TEXT("You write it down. [Tab] notebook"), 5.f);
		}
	}
}

int32 ARunDirector::ThreatKindOf(int32 Key)
{
	const int32 Kind = KeyState(Key).Content.Anomaly;
	return Kind != 0 && ForceThreatKind >= 1 && ForceThreatKind <= NumThreats ? ForceThreatKind : Kind;
}

// Что опасного в комнате. Аномалия действует всегда, двери при ней открыты: вернуться можно.
// Противники появляются при первом входе в комнату набора и дальше живут в ней, как вещи:
// кого убили — того нет, кто остался — стоит там, где его оставили (решение автора 13.11).
void ARunDirector::SpawnThreats(int32 ArrivalDoor)
{
	if (ThreatActor)
	{
		ThreatActor->Destroy();
		ThreatActor = nullptr;
	}
	ThreatHint.Reset();
	ThreatMeter = 0.f;
	const int32 Key = Rooms[CurrentRoom].Key;
	const int32 Kind = ThreatKindOf(Key);
	const FVector Origin = RoomActor->GetActorLocation();
	if (Layout->NeedsSuit(Key))
	{
		// разгерметизация — ворота правильного пути, не угроза догадки: вид комнаты и удушье без скафандра
		ThreatActor = GetWorld()->SpawnActor<ARunThreat>(ARunThreat::StaticClass(), Origin, FRotator::ZeroRotator);
		ThreatActor->Setup(ARunThreat::Decompression, this, RoomActor, ArrivalDoor, Hash32({ Seed, 201U, static_cast<uint32>(Key) }));
		UE_LOG(LogRun, Display, TEXT("Run: decompression in room=%d"), CurrentRoom);
	}
	else if (ARunThreat::IsAnomaly(Kind))
	{
		ThreatActor = GetWorld()->SpawnActor<ARunThreat>(ARunThreat::StaticClass(), Origin, FRotator::ZeroRotator);
		ThreatActor->Setup(Kind, this, RoomActor, ArrivalDoor, Hash32({ Seed, 200U, static_cast<uint32>(Key) }));
		UE_LOG(LogRun, Display, TEXT("Run: anomaly %s in room=%d"), ARunThreat::DisplayName(Kind), CurrentRoom);
	}
	else if (Kind != 0 && !KeyState(Key).bEnemiesSpawned)
	{
		KeyState(Key).bEnemiesSpawned = true;
		const int32 Count = Kind == ThreatRats ? RatCount : 1;
		const TArray<FVector> Places = FreeFloorPoints(ArrivalDoor, Count);
		for (int32 I = 0; I < Count; ++I)
		{
			FRunEnemyState E;
			E.Id = NextEnemyId++;
			E.Kind = Kind;
			E.Health = ARunEnemy::StartHealth(Kind);
			E.Key = Key;
			E.LocalPos = Places[I] - Origin;
			Enemies.Add(E);
			UE_LOG(LogRun, Display, TEXT("Run:   enemy id=%d placed at (%.0f, %.0f)"), E.Id, E.LocalPos.X, E.LocalPos.Y);
		}
		UE_LOG(LogRun, Display, TEXT("Run: enemies %s x%d in room=%d"), ARunEnemy::DisplayName(Kind), Count, CurrentRoom);
	}
	for (const FRunEnemyState& E : Enemies)
	{
		if (E.Key == Key && E.ArriveAt < 0.f)
		{
			SpawnEnemyActor(E, 0.8f);   // короткая пауза: игрок успевает осмотреться
		}
	}
}

void ARunDirector::SpawnEnemyActor(const FRunEnemyState& Enemy, float StartStun)
{
	const FVector At = RoomActor->GetActorLocation() + Enemy.LocalPos;
	ARunEnemy* Actor = GetWorld()->SpawnActor<ARunEnemy>(ARunEnemy::StaticClass(), At, FRotator::ZeroRotator);
	Actor->Setup(Enemy.Kind, Enemy.Id, this, At, Enemy.Health, StartStun);
	EnemyActors.Add(Actor);
}

// Свободные точки пола, начиная с самых дальних от двери, через которую вошёл игрок.
TArray<FVector> ARunDirector::FreeFloorPoints(int32 ArrivalDoor, int32 Count) const
{
	const FVector Origin = RoomActor->GetActorLocation();
	const FVector Entry = ArrivalDoor >= 0 ? RoomActor->VestibuleCenter(ArrivalDoor) : Origin + FVector(-200.f, 0.f, 0.f);
	FCollisionQueryParams Params(FName(TEXT("RunEnemySpot")), false);
	if (const APawn* Pawn = UGameplayStatics::GetPlayerPawn(this, 0))
	{
		Params.AddIgnoredActor(Pawn);
	}
	TArray<FVector> Free;
	for (float X = -RunRoomGeo::HalfX + 90.f; X <= RunRoomGeo::HalfX - 90.f; X += 90.f)
	{
		for (float Y = -RunRoomGeo::HalfY + 75.f; Y <= RunRoomGeo::HalfY - 75.f; Y += 75.f)
		{
			const FVector Pt = Origin + FVector(X, Y, 0.f);
			if (!GetWorld()->OverlapBlockingTestByChannel(Pt + FVector(0, 0, 60.f), FQuat::Identity, ECC_WorldStatic, FCollisionShape::MakeSphere(45.f), Params))
			{
				Free.Add(Pt);
			}
		}
	}
	Free.Sort([&Entry](const FVector& A, const FVector& B) { return FVector::Dist2D(A, Entry) > FVector::Dist2D(B, Entry); });
	TArray<FVector> Out;
	for (const FVector& Pt : Free)
	{
		if (Out.Num() >= Count)
		{
			break;
		}
		if (!Out.ContainsByPredicate([&Pt](const FVector& O) { return FVector::Dist2D(O, Pt) < 150.f; }))
		{
			Out.Add(Pt);
		}
	}
	while (Out.Num() < Count)
	{
		Out.Add(Origin - (Entry - Origin).GetSafeNormal2D() * 250.f + FVector(0.f, 60.f * Out.Num(), 0.f));
	}
	return Out;
}

FRunEnemyState* ARunDirector::FindEnemy(int32 Id)
{
	return Enemies.FindByPredicate([Id](const FRunEnemyState& E) { return E.Id == Id; });
}

// Игрок уходит через дверь Door. Кто стоит с ним в тамбуре — проходит вместе с ним. Человек, который не успел,
// идёт следом и войдёт в ту же дверь чуть позже. Остальные остаются в своей комнате там, где стояли.
void ARunDirector::MoveEnemies(int32 Door, int32 NewKey, const FVector& NewLocation)
{
	const float Now = GetWorld()->GetTimeSeconds();
	const FVector OldOrigin = RoomActor->GetActorLocation();
	int32 Through = 0, Following = 0, Stayed = 0;
	for (ARunEnemy* Actor : EnemyActors)
	{
		FRunEnemyState* E = Actor ? FindEnemy(Actor->EnemyId) : nullptr;
		if (E)
		{
			const FVector Local = Actor->GetFloorPos() - OldOrigin;
			if (FVector::DotProduct(Local, RunRoomGeo::Dir(Door)) > RunRoomGeo::OuterFace(Door) - RunRoomGeo::Wall * 0.5f)
			{
				E->Key = NewKey;
				E->LocalPos = Actor->GetFloorPos() - NewLocation;   // тамбур у комнат общий: место в мире то же
				++Through;
			}
			else if (E->Kind == ThreatHuman)
			{
				E->ArriveAt = Now;   // отметка «идёт следом», время ставится ниже
			}
			else
			{
				E->LocalPos = Local;
				++Stayed;
			}
		}
		if (Actor)
		{
			Actor->Destroy();
		}
	}
	EnemyActors.Reset();
	for (FRunEnemyState& E : Enemies)
	{
		if (E.ArriveAt >= 0.f)
		{
			E.Key = NewKey;
			// кто уже шёл следом, не начинает отсчёт заново: он нагоняет, пока не окажется в секунде с небольшим позади
			E.ArriveAt = Now + (E.ArriveAt > Now ? FMath::Max(1.2f, E.ArriveAt - Now) : HumanFollowDelay);
			E.ArriveDoor = RunRoomGeo::Opposite(Door);
			++Following;
		}
	}
	if (Through + Following + Stayed > 0)
	{
		UE_LOG(LogRun, Display, TEXT("Run: enemies through=%d following=%d stayed=%d"), Through, Following, Stayed);
	}
}

// Преследователь входит через дверь, в которую вошёл игрок.
void ARunDirector::TickFollowers()
{
	if (Phase != ERunPhase::Playing || bBusy || !RoomActor)
	{
		return;
	}
	// человек умеет открывать двери: если он в тамбуре, а створка закрылась, она открывается для него.
	// Робот и крысы не умеют — остаются за дверью, пока её не откроет игрок.
	for (const ARunEnemy* A : EnemyActors)
	{
		if (A && A->Kind == ThreatHuman)
		{
			const int32 D = RoomActor->VestibuleOf(A->GetFloorPos());
			if (D >= 0)
			{
				RoomActor->OpenFor(D, 0.5f);
			}
		}
	}
	const float Now = GetWorld()->GetTimeSeconds();
	for (FRunEnemyState& E : Enemies)
	{
		if (E.ArriveAt >= 0.f && Now >= E.ArriveAt)
		{
			const int32 D = E.ArriveDoor;
			E.ArriveAt = -1.f;
			E.LocalPos = RunRoomGeo::Dir(D) * (RunRoomGeo::OuterFace(D) + RunRoomGeo::VestibuleDepth - 70.f);
			SpawnEnemyActor(E, 0.6f);
			RoomActor->OpenFor(D, 4.f);
			Say(TEXT("The door slides open again. The other you steps through."), 4.f);
			UE_LOG(LogRun, Display, TEXT("Run: follower id=%d arrived in room=%d door=%s"), E.Id, CurrentRoom, RunRoomGeo::DoorName(D));
		}
	}
}

int32 ARunDirector::GetFollowers() const
{
	int32 N = 0;
	for (const FRunEnemyState& E : Enemies)
	{
		N += E.ArriveAt >= 0.f ? 1 : 0;
	}
	return N;
}

FVector ARunDirector::SteerTarget(const FVector& From, const FVector& To) const
{
	return RoomActor ? RoomActor->SteerTarget(From, To) : To;
}

float ARunDirector::GetSwingFlash() const
{
	return GetWorld() ? FMath::Clamp(1.f - (GetWorld()->GetTimeSeconds() - SwingAt) / 0.2f, 0.f, 1.f) : 0.f;
}

// Удар разводным ключом: достаёт всех противников перед игроком на расстоянии вытянутой руки.
void ARunDirector::OnAttack()
{
	const float Now = GetWorld()->GetTimeSeconds();
	const APawn* Pawn = UGameplayStatics::GetPlayerPawn(this, 0);
	if (Phase != ERunPhase::Playing || !Pawn || Now < NextAttackAt)
	{
		return;
	}
	if (!HasWeapon())
	{
		if (EnemyActors.Num() > 0)
		{
			Say(TEXT("You have nothing to fight with."), 2.f);
		}
		return;
	}
	NextAttackAt = Now + AttackCooldown;
	SwingAt = Now;
	const FVector P = Pawn->GetActorLocation();
	const FVector Facing = Pawn->GetActorForwardVector().GetSafeNormal2D();
	const FVector Looking = FRotator(0.f, Pawn->GetControlRotation().Yaw, 0.f).Vector();
	const TArray<TObjectPtr<ARunEnemy>> Targets = EnemyActors;   // список меняется, когда противник убит
	for (ARunEnemy* Actor : Targets)
	{
		FRunEnemyState* E = Actor ? FindEnemy(Actor->EnemyId) : nullptr;
		if (!E)
		{
			continue;
		}
		const FVector To(Actor->GetFloorPos().X - P.X, Actor->GetFloorPos().Y - P.Y, 0.f);
		const float Dist = To.Size2D();
		const FVector N = To.GetSafeNormal2D();
		// впереди — это куда смотрит персонаж или камера; вплотную попадает в любом случае
		const bool bAhead = Dist < 75.f || FVector::DotProduct(N, Facing) > 0.2f || FVector::DotProduct(N, Looking) > 0.2f;
		if (Dist > AttackReach + Actor->GetRadius() || !bAhead)
		{
			continue;
		}
		FCollisionQueryParams Sight(FName(TEXT("RunAttack")), false, Pawn);
		if (Dist > 75.f && GetWorld()->LineTraceTestByChannel(P, FVector(Actor->GetFloorPos().X, Actor->GetFloorPos().Y, P.Z), ECC_WorldStatic, Sight))
		{
			continue;   // между игроком и противником стена или закрытая створка
		}
		--E->Health;
		UE_LOG(LogRun, Display, TEXT("Run: attack hit id=%d kind=%s health=%d"), E->Id, ARunEnemy::DisplayName(E->Kind), E->Health);
		if (E->Health <= 0)
		{
			Say(E->Kind == ThreatHuman ? TEXT("The other you goes down and does not get up.")
				: E->Kind == ThreatRobot ? TEXT("The robot sparks and goes still.") : TEXT("One rat less."), 3.f);
			const int32 Id = E->Id;
			Enemies.RemoveAll([Id](const FRunEnemyState& S) { return S.Id == Id; });
			EnemyActors.Remove(Actor);
			Actor->Destroy();
		}
		else
		{
			Actor->ShowHealth(E->Health);
			Actor->Knock(P, AttackStun);
		}
	}
}

float ARunDirector::GetHurtFlash() const
{
	return GetWorld() ? FMath::Clamp(1.f - (GetWorld()->GetTimeSeconds() - HurtAt) / 0.5f, 0.f, 1.f) : 0.f;
}

void ARunDirector::SetThreatHint(const FString& Text, float Meter)
{
	ThreatHint = Text;
	ThreatMeter = FMath::Clamp(Meter, 0.f, 1.f);
}

float ARunDirector::GetHealFlash() const
{
	return GetWorld() ? FMath::Clamp(1.f - (GetWorld()->GetTimeSeconds() - HealAt) / 0.6f, 0.f, 1.f) : 0.f;
}

void ARunDirector::HurtPlayer(const FString& Text, const FVector& From, float Damage, bool bKnockback)
{
	const float Now = GetWorld()->GetTimeSeconds();
	if (Phase != ERunPhase::Playing || Now < InvulnerableUntil || Damage <= 0.f)
	{
		return;
	}
	InvulnerableUntil = Now + HurtGraceSeconds;
	HurtAt = Now;
	const float Took = FMath::Min(Health, Damage);
	Health -= Took;
	DamageTaken += Took;
	UE_LOG(LogRun, Display, TEXT("Run: hurt damage=%.0f health=%.0f (%s)"), Damage, Health, *Text);
	ACharacter* Ch = bKnockback ? Cast<ACharacter>(UGameplayStatics::GetPlayerPawn(this, 0)) : nullptr;
	if (Ch)
	{
		FVector Away = Ch->GetActorLocation() - From;
		Away.Z = 0.f;
		Ch->LaunchCharacter(Away.GetSafeNormal2D() * 520.f + FVector(0, 0, 180.f), true, true);
	}
	// в самопроверке игрок бессмертен, чтобы сценарий дошёл до конца; ключ -RunDie возвращает смерть (проверка экрана смерти)
	if (Health <= 0.f && bSelfTest && !FParse::Param(FCommandLine::Get(), TEXT("RunDie")))
	{
		UE_LOG(LogRun, Display, TEXT("Run: test: here the player would be dead"));
		Health = MaxHealth;
	}
	else if (Health <= 0.f)
	{
		Phase = ERunPhase::Dead;
		RestartAt = Now + 12.f;
		RunEndAt = Now;
		DeathCause = Text;
		SetInspecting(false);
		Say(Text + TEXT(" Everything goes dark. YOU DIED."), 5.f);
	}
	else
	{
		Say(Text, 3.f);
	}
}

bool ARunDirector::IsInVacuum() const
{
	return Layout && Rooms.IsValidIndex(CurrentRoom) && Layout->NeedsSuit(Rooms[CurrentRoom].Key);
}

void ARunDirector::PutOnSuit()
{
	if (bSuitOn)
	{
		return;
	}
	bSuitOn = true;
	bSuitWorn = true;
	if (!Helmet)
	{
		// шлем — стеклянный пузырь на голове героя (пока нет модели скафандра); место — каждый кадр в Tick
		Helmet = NewObject<UStaticMeshComponent>(this, TEXT("SuitHelmet"));
		Helmet->SetupAttachment(GetRootComponent());
		Helmet->SetMobility(EComponentMobility::Movable);
		Helmet->SetCollisionProfileName(TEXT("NoCollision"));
		Helmet->SetCastShadow(false);
		Helmet->RegisterComponent();
		Helmet->SetStaticMesh(LoadObject<UStaticMesh>(nullptr, TEXT("/Engine/BasicShapes/Sphere.Sphere")));
		UMaterialInterface* Glass = LoadObject<UMaterialInterface>(nullptr, TEXT("/Game/FX/Anomalies/MI_TimeBubble.MI_TimeBubble"),
			nullptr, LOAD_NoWarn | LOAD_Quiet);
		Helmet->SetMaterial(0, Glass ? Glass : LoadObject<UMaterialInterface>(nullptr, TEXT("/Game/Game/Materials/MI_Gray_Glow.MI_Gray_Glow")));
		Helmet->SetWorldScale3D(FVector(0.36f));
	}
	Helmet->SetVisibility(true);
	Say(TEXT("You pull on the space suit. The helmet seals with a hiss."), 5.f);
	UE_LOG(LogRun, Display, TEXT("Run: suit on"));
	if (!bTipSuit)
	{
		bTipSuit = true;
		ShowTip(TEXT("The suit takes no pocket slot. [T] takes it off"), 7.f);
	}
}

void ARunDirector::TakeOffSuit()
{
	if (!bSuitOn || Phase != ERunPhase::Playing || bBusy || !RoomActor)
	{
		return;
	}
	if (IsInVacuum())
	{
		Say(TEXT("Not here. There is no air to breathe."), 3.f);
		return;
	}
	const APawn* Pawn = UGameplayStatics::GetPlayerPawn(this, 0);
	if (!Pawn)
	{
		return;
	}
	bSuitOn = false;
	if (Helmet)
	{
		Helmet->SetVisibility(false);
	}
	// ложится у ног, как выброшенная вещь: в той комнате и останется (5.3)
	FRunPlacedItem P;
	P.Item = Suit;
	P.bHasPos = true;
	P.Uid = NextUid++;
	const FVector Feet = Pawn->GetActorLocation() + Pawn->GetActorForwardVector() * 80.f;
	P.LocalPos = FVector(Feet.X, Feet.Y, RoomActor->GetActorLocation().Z + 11.f) - RoomActor->GetActorLocation();
	CurrentKeyState().Items.Add(P);
	SpawnItemActor(Suit, -1, RoomActor->GetActorLocation() + P.LocalPos, P.Uid);
	Say(TEXT("You step out of the space suit and leave it standing."), 3.f);
	UE_LOG(LogRun, Display, TEXT("Run: suit off"));
}

void ARunDirector::KillPlayer(const FString& Text, const FVector& From)
{
	InvulnerableUntil = 0.f;
	HurtPlayer(Text, From, Health + 1.f, false);
}

bool ARunDirector::IsPlayerCrouched() const
{
	const ACharacter* Ch = Cast<ACharacter>(UGameplayStatics::GetPlayerPawn(this, 0));
	return Ch && Ch->bIsCrouched;
}

// Присед (решение автора 15.11, для дыма). Капсулу и камеру опускает движение персонажа движка. Анимации приседа
// (IdlePath и WalkPath ниже) взяты из плагина движка MoverExamples и перенесены на скелет проекта
// (tools/ue/import_crouch.py); герой играет их вместо блюпринта анимации шаблона. Если ассетов нет — просто
// сжимается по высоте, чтобы было видно, что голова ниже дыма.
void ARunDirector::UpdateCrouch(ACharacter* Ch, const APlayerController* PC)
{
	static const TCHAR* const IdlePath = TEXT("/Game/Characters/Mannequins/Anims/Crouch/MM_Crouch_Idle.MM_Crouch_Idle");
	static const TCHAR* const WalkPath = TEXT("/Game/Characters/Mannequins/Anims/Crouch/MM_Crouch_Walk.MM_Crouch_Walk");
	const bool bWant = Phase == ERunPhase::Playing
		&& (bCrouchToggle || PC->IsInputKeyDown(EKeys::LeftControl) || PC->IsInputKeyDown(EKeys::RightControl));
	if (bWant && !Ch->bIsCrouched)
	{
		Ch->Crouch();
	}
	else if (!bWant && Ch->bIsCrouched)
	{
		Ch->UnCrouch();   // под низким потолком не встанет: движение само проверит
	}
	USkeletalMeshComponent* Mesh = Ch->GetMesh();
	UAnimSequenceBase* Idle = LoadObject<UAnimSequenceBase>(nullptr, IdlePath, nullptr, LOAD_NoWarn | LOAD_Quiet);
	UAnimSequenceBase* Walk = LoadObject<UAnimSequenceBase>(nullptr, WalkPath, nullptr, LOAD_NoWarn | LOAD_Quiet);
	if (Ch->bIsCrouched != bCrouchPose)
	{
		bCrouchPose = Ch->bIsCrouched;
		if (bCrouchPose)
		{
			MeshScaleStanding = Mesh->GetRelativeScale3D();
			if (!Idle)
			{
				Mesh->SetRelativeScale3D(FVector(MeshScaleStanding.X, MeshScaleStanding.Y, MeshScaleStanding.Z * 0.62f));
			}
		}
		else
		{
			Mesh->SetRelativeScale3D(MeshScaleStanding);
			if (Mesh->GetAnimationMode() == EAnimationMode::AnimationSingleNode)
			{
				Mesh->SetAnimationMode(EAnimationMode::AnimationBlueprint);
			}
		}
	}
	if (bCrouchPose && Idle)
	{
		const float Speed = Ch->GetVelocity().Size2D();
		UAnimSequenceBase* Want = Speed > 20.f && Walk ? Walk : Idle;
		if (Mesh->GetAnimationMode() != EAnimationMode::AnimationSingleNode || Mesh->GetSingleNodeInstance() == nullptr
			|| Mesh->GetSingleNodeInstance()->GetAnimationAsset() != Want)
		{
			Mesh->PlayAnimation(Want, true);
		}
		if (Want == Walk)
		{
			// в MM_Crouch_Walk корень проходит 540 см за цикл 1,8 с — родная скорость 300 см/с; вприсядку герой идёт
			// 150, значит темп 0,5, иначе ноги скользят
			Mesh->SetPlayRate(FMath::Clamp(Speed / 300.f, 0.25f, 1.6f));
		}
	}
}

ARunItem* ARunDirector::SpawnItemActor(int32 Item, int32 NoteIndex, const FVector& Location, int32 Uid)
{
	ARunItem* Actor = GetWorld()->SpawnActor<ARunItem>(ARunItem::StaticClass(), Location, FRotator::ZeroRotator);
	Actor->Setup(Item, NoteIndex, NoteIndex >= 0 ? FString(TEXT("Note")) : ItemName(Item));
	Actor->PlacedUid = Uid;
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
	const TArray<FTransform> Niches = RoomActor->TakeFirstAidCases();
	// на какие метки лягут вещи, решают зерно и набор: комната набора всегда выглядит одинаково
	const uint32 Shift = Hash32({ Seed, 100U, static_cast<uint32>(State.Content.Key) });
	for (const FRunPlacedItem& P : State.Items)
	{
		// метка закреплена за вещью: взяли одну — остальные лежат, где лежали
		const int32 Spot = FMath::Max(0, P.Spot);
		FVector Loc;
		if (!P.bHasPos && P.Niche >= 0 && Niches.Num() > 0)
		{
			// аптечка стоит в нише ровно там, где стоял спрятанный кейс
			const FTransform& Case = Niches[P.Niche % Niches.Num()];
			SpawnItemActor(P.Item, -1, Case.GetLocation(), P.Uid)->PlaceAt(Case);
			continue;
		}
		if (P.bHasPos)
		{
			Loc = Origin + P.LocalPos;
		}
		else if (P.Item == Suit)
		{
			// скафандр в рост на места предметов не помещается: на свободный пол, всегда в одно место комнаты
			Loc = FreeFloorPoints(-1, 1)[0] + FVector(0, 0, 11.f);
		}
		else if (ItemSpots.Num() > 0)
		{
			Loc = ItemSpots[(Shift + Spot) % ItemSpots.Num()] + FVector(0, 0, 11.f);
		}
		else
		{
			Loc = Origin + FVector(-150.f + 60.f * Spot, 250.f, 11.f);
		}
		SpawnItemActor(P.Item, -1, Loc, P.Uid);
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
	BusySince = GetWorld()->GetTimeSeconds();
	PendingDoor = Door;
	Room->bSealed = true;
	SwapAt = GetWorld()->GetTimeSeconds() + TransitionSeconds;
}

void ARunDirector::CancelTransition()
{
	bBusy = false;
	PendingDoor = -1;
	if (RoomActor)
	{
		RoomActor->bSealed = false;
	}
}

void ARunDirector::DoSwap()
{
	const int32 Door = PendingDoor;
	const int32 From = CurrentRoom;
	int32 To = Rooms[From].Doors[Door];
	// разгерметизация (DESIGN 5.9): шлюз считывает карман, видит пробоину за дверью и без скафандра не открывает.
	// Дверь при этом не раскрывается: с другим набором за ней будет другая комната
	const int32 Peek = To >= 0 ? Rooms[To].Key : Layout->PocketKey(Pocket);
	if (Layout->NeedsSuit(Peek) && !bSuitOn)
	{
		CancelTransition();
		RoomActor->SetArrivalDoor(Door);   // створка открыта; новый переход — когда игрок выйдет из тамбура и вернётся
		RoomActor->SetDoorSign(Door, TEXT("HULL BREACH"));
		Say(TEXT("The airlock reads your pocket and stays shut: HULL BREACH beyond. SUIT REQUIRED."), 6.f);
		UE_LOG(LogRun, Display, TEXT("Run: airlock refused key=%d: hull breach, no suit"), Peek);
		return;
	}
	if (To < 0)
	{
		// нераскрытая дверь: комнату определяет карман в этот момент, дальше дверь не меняется (5.2)
		const int32 Key = Layout->PocketKey(Pocket);
		FRunRoomState State;
		State.Key = Key;
		State.Doors[RunRoomGeo::Opposite(Door)] = From;              // обратный путь ведёт туда, откуда пришёл
		To = Rooms.Add(State);
		Rooms[From].Doors[Door] = To;
	}
	const FVector NewLocation = RoomActor->GetActorLocation() + RunRoomGeo::NeighborOffset(Door);
	ARunRoom* Old = RoomActor;
	MoveEnemies(Door, Rooms[To].Key, NewLocation);
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
	bRoomFamiliar = SeenKeys.Contains(State.Key);
	SeenKeys.Add(State.Key);
	RoomTitleAt = GetWorld()->GetTimeSeconds();
	if (!bRoomFamiliar && RoomClass(State.Key) == ClsChain && State.Key != Anchor && State.Key != 0)
	{
		// первый раз в безопасной комнате правильного пути: что было в кармане и куда привело
		FString Carried;
		for (int32 It : Pocket)
		{
			if (It >= 0)
			{
				Carried += (Carried.IsEmpty() ? TEXT("") : TEXT(", ")) + ItemNoun(It);
			}
		}
		WriteProgress(FString::Printf(TEXT("With %s the door opened to %s. Quiet here."), *Carried, DisplayRoomName(Content.RoomType)));
	}

	if (RoomClass(State.Key) == ClsEngine)
	{
		if (!bEngineFixed)
		{
			bEngineFixed = true;
			WriteProgress(TEXT("The engines are running again. One thing left: get back to the bridge."));
			Say(TEXT("The warp engines hum back to life. Now get back to the bridge."), 8.f);
		}
		return;
	}
	if (bEngineFixed && Content.RoomType == Bridge)
	{
		// концовка наступает раньше, чем сработает аномалия в этой рубке
		Phase = ERunPhase::Won;
		RunEndAt = GetWorld()->GetTimeSeconds();
		RestartAt = RunEndAt + 90.f;   // экран победы с титрами держится, пока игрок не нажмёт клавишу
		SetInspecting(false);
		UE_LOG(LogRun, Display, TEXT("Run: WON doors=%d notes=%d damage=%.0f health=%.0f medkits=%d seconds=%.0f"), GetDoorsOpened(), NotesRead,
			DamageTaken, Health, MedkitsUsed, GetRunSeconds());
		Say(TEXT("You are on the bridge. The ship tears itself free. YOU ESCAPED."), 8.f);
		return;
	}
	const int32 Kind = ThreatKindOf(State.Key);
	if (Layout->NeedsSuit(State.Key))
	{
		Say(TEXT("Hull breach. No air in here, only the hiss of your suit."), 6.f);
	}
	else if (ARunThreat::IsAnomaly(Kind))
	{
		Say(FString::Printf(TEXT("%s. This room is wrong. Nothing stops you from walking back out."), ARunThreat::DisplayName(Kind)), 6.f);
	}
	else if (EnemyActors.Num() > 0)
	{
		bool bHuman = false, bRobot = false;
		for (const ARunEnemy* A : EnemyActors)
		{
			bHuman |= A && A->Kind == ThreatHuman;
			bRobot |= A && A->Kind == ThreatRobot;
		}
		Say(bHuman ? TEXT("Someone is in the room. It has your face. It will not stop following you.")
			: bRobot ? TEXT("A maintenance robot turns towards you. It will not leave this room.")
			: TEXT("Rats. They are fast, but they will not open a door."), 6.f);
		if (!bTipHit && HasWeapon())
		{
			bTipHit = true;
			ShowTip(TEXT("[LMB] or [F] hit with the wrench"), 6.f);
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
		if (A->ItemId == Suit)
		{
			return TEXT("[E] Put on the space suit");
		}
		return Pocket.Num() < PocketSlots ? FString::Printf(TEXT("[E] Take %s"), *ItemNoun(A->ItemId).Replace(TEXT("the "), TEXT("")))
			: FString(TEXT("Pocket is full. [1]-[4] pick an item, [G] drop it"));
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

void ARunDirector::AddBookmark(const FString& Text)
{
	const int32 Was = Bookmarks.IndexOfByKey(Text);
	Bookmark = Was != INDEX_NONE ? Was : Bookmarks.Add(Text);   // последняя прочитанная — выбрана
	if (HasNotebook())
	{
		bJournalUnread = true;
	}
}

// Вверх, вниз в меню: к соседней закладке; блокнот раскрывается на её развороте.
void ARunDirector::StepBookmark(int32 Step)
{
	if (!IsReading() || Bookmarks.Num() == 0 || !HasNotebook())
	{
		return;
	}
	Bookmark = Bookmark < 0 ? (Step > 0 ? 0 : Bookmarks.Num() - 1) : FMath::Clamp(Bookmark + Step, 0, Bookmarks.Num() - 1);
	bBookmarkJump = true;
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
		++NotesRead;
		AddToJournal(Text);   // записки складываются в блокнот (5.6)
		AddBookmark(Text);    // и закладкой в нём, без слота (решение автора 15.11)
		Say(Text, 9.f);
	}
	else if (A->ItemId == Suit)
	{
		// скафандр не в карман, а на себя: слот не нужен (DESIGN 5.3, 5.9)
		const int32 Uid = A->PlacedUid;
		const int32 Index = State.Items.IndexOfByPredicate([Uid](const FRunPlacedItem& P) { return P.Uid == Uid || (Uid == 0 && P.Item == Suit); });
		if (Index != INDEX_NONE)
		{
			State.Items.RemoveAt(Index);
		}
		PutOnSuit();
	}
	else
	{
		if (Pocket.Num() >= PocketSlots)
		{
			Say(TEXT("Pocket is full."), 2.f);
			return;
		}
		const int32 Item = A->ItemId;
		const int32 Uid = A->PlacedUid;
		int32 Index = State.Items.IndexOfByPredicate([Uid](const FRunPlacedItem& P) { return P.Uid == Uid; });
		if (Index == INDEX_NONE)
		{
			Index = State.Items.IndexOfByPredicate([Item](const FRunPlacedItem& P) { return P.Item == Item; });
		}
		if (Index != INDEX_NONE)
		{
			State.Items.RemoveAt(Index);
		}
		Pocket.Add(Item);
		if (GetHeldSlot() < 0)
		{
			HeldSlot = Pocket.Num() - 1;   // руки были пусты — взятое сразу в руке
		}
		if (Item == Notebook && !bFirstNoteRead)
		{
			bFirstNoteRead = true;
			const FString Text = Layout->FirstNote.Text();
			Journal.Insert(Text, 0);
			Bookmarks.Insert(Text, 0);
			Bookmark = Bookmark >= 0 ? Bookmark + 1 : 0;
			Say(Text, 10.f);
			ShowTip(TEXT("[Tab] opens the notebook"), 8.f);
		}
		else if (Item == Medkit && !bTipMedkit)
		{
			bTipMedkit = true;
			ShowTip(TEXT("Medkit: take it in hand with [1]-[4], [LMB] to use"), 7.f);
		}
		else if (Pocket.Num() >= PocketSlots && !bTipDrop)
		{
			bTipDrop = true;
			ShowTip(TEXT("Pocket is full. [1]-[4] takes an item in hand, [G] drops it"), 7.f);
		}
	}
	ItemActors.Remove(A);
	A->Destroy();
}

void ARunDirector::DropSlot(int32 Slot)
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
	RemoveFromPocket(Slot);
	// выброшенный предмет остаётся лежать там, где его выбросили (5.3)
	FVector Loc = Pawn->GetActorLocation() + Pawn->GetActorForwardVector() * 70.f;
	FCollisionQueryParams DropParams(FName(TEXT("RunDrop")), false, Pawn);
	if (GetWorld()->OverlapBlockingTestByChannel(Loc + FVector(0, 0, 20.f), FQuat::Identity, ECC_WorldStatic, FCollisionShape::MakeSphere(14.f), DropParams))
	{
		Loc = Pawn->GetActorLocation();   // перед игроком стена или мебель: предмет падает под ноги
	}
	FHitResult Hit;
	if (GetWorld()->LineTraceSingleByChannel(Hit, Loc + FVector(0, 0, 50.f), Loc - FVector(0, 0, 300.f), ECC_Visibility))
	{
		Loc = Hit.ImpactPoint + FVector(0, 0, 11.f);
	}
	FRunPlacedItem& P = AddPlaced(CurrentKeyState(), Item);
	P.bHasPos = true;
	P.LocalPos = Loc - RoomActor->GetActorLocation();
	SpawnItemActor(Item, -1, Loc, P.Uid);
}

void ARunDirector::RemoveFromPocket(int32 Slot)
{
	Pocket.RemoveAt(Slot);
	if (HeldSlot == Slot)
	{
		HeldSlot = -1;
		SetInspecting(false);
	}
	else if (HeldSlot > Slot)
	{
		--HeldSlot;   // слоты сдвинулись, в руке та же вещь
	}
}

// 1–4: взять вещь этого слота в руку; та же клавиша ещё раз — убрать в карман.
void ARunDirector::SelectSlot(int32 Slot)
{
	if (Phase != ERunPhase::Playing || !Pocket.IsValidIndex(Slot))
	{
		return;
	}
	if (IsReading())
	{
		// в меню 1–4 — рассмотреть вещь: она в руке и крупно перед глазами; блокнот и так раскрыт
		HeldSlot = Slot;
		if (Pocket[Slot] != Notebook)
		{
			SetMenuOpen(false);
			SetInspecting(true);
		}
		return;
	}
	HeldSlot = HeldSlot == Slot ? -1 : Slot;
	SetInspecting(false);
	if (GetHeldSlot() >= 0 && !bTipHeld)
	{
		bTipHeld = true;
		ShowTip(TEXT("[RMB] look closer at what you hold   [G] drop it"), 7.f);
	}
}

void ARunDirector::CycleHeld(int32 Step)
{
	if (Phase != ERunPhase::Playing || Pocket.Num() == 0)
	{
		return;
	}
	// по кругу через все слоты и «пустые руки»
	const int32 N = Pocket.Num() + 1;
	const int32 From = GetHeldSlot() < 0 ? Pocket.Num() : HeldSlot;
	const int32 To = ((From + Step) % N + N) % N;
	HeldSlot = To == Pocket.Num() ? -1 : To;
	SetInspecting(false);
}

void ARunDirector::OnWheelUp()
{
	if (IsReading())
	{
		TurnPage(-1);
	}
	else if (!IsInspecting())
	{
		CycleHeld(-1);
	}
}

void ARunDirector::OnWheelDown()
{
	if (IsReading())
	{
		TurnPage(1);
	}
	else if (!IsInspecting())
	{
		CycleHeld(1);
	}
}

void ARunDirector::OnDropHeld()
{
	if (GetHeldSlot() < 0)
	{
		if (Phase == ERunPhase::Playing && Pocket.Num() > 0)
		{
			Say(TEXT("Your hands are empty. [1]-[4] takes an item in hand."), 3.f);
		}
		return;
	}
	DropSlot(HeldSlot);
}

// Левая кнопка: применить то, что в руке. Применить можно только аптечку; иначе — удар ключом, если он в кармане.
void ARunDirector::OnUse()
{
	if (Phase != ERunPhase::Playing)
	{
		return;
	}
	if (GetHeldSlot() >= 0 && Pocket[HeldSlot] == Medkit)
	{
		UseMedkit(HeldSlot);
		return;
	}
	OnAttack();
}

void ARunDirector::UseMedkit(int32 Slot)
{
	if (Health >= MaxHealth)
	{
		Say(TEXT("You are not hurt. Better keep the medkit."), 2.5f);
		return;
	}
	const float Before = Health;
	Health = FMath::Min(MaxHealth, Health + MedkitHeal);
	HealAt = GetWorld()->GetTimeSeconds();
	++MedkitsUsed;
	RemoveFromPocket(Slot);
	UE_LOG(LogRun, Display, TEXT("Run: medkit used health=%.0f -> %.0f"), Before, Health);
	Say(TEXT("You patch yourself up. It helps."), 3.f);
}

// Правая кнопка: рассмотреть вещь в руке или убрать её от глаз. Блокнот при этом раскрывается для чтения.
void ARunDirector::OnInspect()
{
	if (Phase != ERunPhase::Playing)
	{
		return;
	}
	if (IsReading())
	{
		SetMenuOpen(false);
		return;
	}
	if (GetHeldSlot() < 0)
	{
		if (Pocket.Num() > 0)
		{
			Say(TEXT("Your hands are empty. [1]-[4] takes an item in hand."), 3.f);
		}
		return;
	}
	if (Pocket[HeldSlot] == Notebook)
	{
		SetMenuOpen(true);   // блокнот в руке: правая кнопка раскрывает его, как Tab
		return;
	}
	SetInspecting(!bInspecting);
}

void ARunDirector::SetInspecting(bool bOn)
{
	bOn = bOn && GetHeldSlot() >= 0 && Phase == ERunPhase::Playing && Pocket[HeldSlot] != Notebook;
	bInspecting = bOn;
	// мышь вертит вещь, а не камеру; ходить можно — блокнот и осмотр на время не влияют (решение автора 13.11)
	const bool bLock = IsInspecting();
	if (APlayerController* PC = UGameplayStatics::GetPlayerController(this, 0))
	{
		if (bLock != bLookLocked)
		{
			PC->SetIgnoreLookInput(bLock);
			bLookLocked = bLock;
		}
	}
	if (bLock && InspectPivot)
	{
		InspectPivot->SetRelativeRotation(FRotator(-12.f, 25.f, 0.f));   // чуть сверху и сбоку: видно объём
		InspectIdle = 0.f;
	}
}

void ARunDirector::TurnPage(int32 Step)
{
	if (IsReading())
	{
		JournalPage = FMath::Max(0, JournalPage + Step);
	}
}

// Tab — меню (решение автора 15.11): блокнот с закладками записок, карман, скафандр. Игра не встаёт на паузу.
void ARunDirector::OnToggleJournal()
{
	if (Phase == ERunPhase::Playing)
	{
		SetMenuOpen(!bMenuOpen);
	}
}

void ARunDirector::SetMenuOpen(bool bOpen)
{
	bOpen = bOpen && Phase == ERunPhase::Playing;
	if (bOpen && !bMenuOpen)
	{
		SetInspecting(false);
		JournalPage = TNumericLimits<int32>::Max();   // раскрывается на последних записях; экран поправит номер
		bBookmarkJump = false;
		if (HasNotebook())
		{
			bJournalUnread = false;
		}
	}
	bMenuOpen = bOpen;
}

void ARunDirector::ShowItemMesh(UStaticMeshComponent* Comp, int32 Item, float Fit, bool bHang)
{
	// в руке вещь стоит прямо (кейс — ручкой вверх), на осмотре повёрнута лицом (+Y у мешей Singula) к камере
	const FRotator Pose = bHang ? FRotator::ZeroRotator : FRotator(0.f, 90.f, 0.f);
	UStaticMesh* Mesh = ARunItem::FindModel(ItemName(Item));
	float Scale = 1.f;
	if (!Mesh)
	{
		// у вещи нет модели: оранжевый кубик, как на полу
		Mesh = LoadObject<UStaticMesh>(nullptr, TEXT("/Engine/BasicShapes/Cube.Cube"));
		Comp->SetMaterial(0, LoadObject<UMaterialInterface>(nullptr, TEXT("/Game/Game/Materials/MI_Gray_Door.MI_Gray_Door")));
		Scale = Fit / 100.f;
	}
	else
	{
		Comp->EmptyOverrideMaterials();
	}
	Comp->SetStaticMesh(Mesh);
	if (!Mesh)
	{
		return;
	}
	const FBox Box = Mesh->GetBoundingBox();
	if (!bHang)
	{
		// на осмотре вещь вписана в размер Fit, крутится вокруг своей середины
		Scale = Fit / FMath::Max(1.f, Box.GetSize().GetMax());
	}
	Comp->SetRelativeScale3D(FVector(Scale));
	Comp->SetRelativeRotation(Pose);
	const FVector Center = Pose.RotateVector(Box.GetCenter()) * Scale;
	if (bHang)
	{
		// в руке вещь висит под кистью: её верх на 3 см ниже кости
		const FBox Posed = Box.TransformBy(FTransform(Pose, FVector::ZeroVector, FVector(Scale)));
		Comp->SetRelativeLocation(FVector(-Center.X, -Center.Y, -3.f - Posed.Max.Z));
	}
	else
	{
		Comp->SetRelativeLocation(-Center);
	}
}

void ARunDirector::TickHeldItem(float DeltaSeconds)
{
	if (bLookLocked != IsInspecting())
	{
		SetInspecting(bInspecting);   // вещь пропала из руки не через SetInspecting: вернуть мышь камере
	}
	const int32 Held = GetHeldSlot() >= 0 ? Pocket[HeldSlot] : TNumericLimits<int32>::Min();
	const ACharacter* Ch = Cast<ACharacter>(UGameplayStatics::GetPlayerPawn(this, 0));
	if (HandMesh && HandPivot)
	{
		const bool bShow = Held != TNumericLimits<int32>::Min() && !IsInspecting() && Ch && !Ch->IsHidden() && Phase == ERunPhase::Playing;
		if (bShow && Held != ShownHandItem)
		{
			ShowItemMesh(HandMesh, Held, 10.f, true);
			ShownHandItem = Held;
		}
		HandMesh->SetVisibility(bShow);
		if (Ch)
		{
			HandPivot->SetWorldRotation(FRotator(0.f, Ch->GetActorRotation().Yaw, 0.f));
		}
		if (Flashlight)
		{
			const bool bLit = bShow && IsFlashlight(Held);
			Flashlight->SetVisibility(bLit);
			if (const APlayerController* PC = bLit ? UGameplayStatics::GetPlayerController(this, 0) : nullptr)
			{
				// луч идёт от кисти вдоль взгляда камеры; чуть вынесен вперёд, чтобы герой не затенял его бедром
				const FRotator Aim = PC->GetControlRotation();
				Flashlight->SetWorldLocationAndRotation(HandPivot->GetComponentLocation() + Aim.Vector() * 18.f + FVector(0.f, 0.f, 8.f), Aim);
			}
		}
	}
	if (InspectMesh && InspectPivot)
	{
		const bool bShow = IsInspecting();
		if (bShow && Held != ShownInspectItem)
		{
			ShowItemMesh(InspectMesh, Held, 20.f, false);
			ShownInspectItem = Held;
		}
		InspectMesh->SetVisibility(bShow);
		if (bShow)
		{
			// мышь вертит вещь как шар под ладонью; если мышь не трогать, вещь медленно поворачивается сама
			float DX = 0.f, DY = 0.f;
			if (const APlayerController* PC = UGameplayStatics::GetPlayerController(this, 0))
			{
				PC->GetInputMouseDelta(DX, DY);
			}
			InspectIdle = FMath::Abs(DX) + FMath::Abs(DY) > 0.01f ? 0.f : InspectIdle + DeltaSeconds;
			const float Auto = InspectIdle > 1.5f ? 20.f * DeltaSeconds : 0.f;
			const FQuat Turn = FQuat(FVector::UpVector, FMath::DegreesToRadians(-DX * 0.5f - Auto)) * FQuat(FVector::RightVector, FMath::DegreesToRadians(DY * 0.5f));
			InspectPivot->SetRelativeRotation(Turn * InspectPivot->GetRelativeRotation().Quaternion());
		}
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
	const FRunRoomContent& C = CurrentContent();
	const int32 NextKey = Layout->PocketKey(Pocket);
	int32 NextType = 0, NextSw = 0;
	Layout->Look(NextKey, NextType, NextSw);
	const int32 NextAnomaly = Layout->AnomalyOf(NextKey);
	return FString::Printf(TEXT("room #%d %s, threat %s, enemies here %d, following %d | next new door with this pocket -> %s, %s"),
		CurrentRoom, RoomTypeName(C.RoomType), AnomalyName(C.Anomaly), EnemyActors.Num(), GetFollowers(),
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
	UE_LOG(LogRun, Display, TEXT("Run: %s room=%d type=%s key=%d anomaly=%s notes=%d items=[%s] pocket=[%s] health=%.0f doors=[%d,%d,%d,%d]"),
		Why, CurrentRoom, RoomTypeName(K.Content.RoomType), S.Key, AnomalyName(K.Content.Anomaly),
		K.Content.Notes.Num(), *Items, *PocketNames, Health, S.Doors[0], S.Doors[1], S.Doors[2], S.Doors[3]);
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
	if (ACharacter* Ch = Cast<ACharacter>(UGameplayStatics::GetPlayerPawn(this, 0)))
	{
		if (BaseWalkSpeed <= 0.f)
		{
			BaseWalkSpeed = Ch->GetCharacterMovement()->MaxWalkSpeed;
		}
		// по умолчанию шаг, бег — пока зажат Shift (решение автора 14.11); скорость бега — из персонажа шаблона.
		// Клавиша опрашивается каждый кадр, а не ловится нажатием: отпущенная на паузе не залипнет.
		const APlayerController* PC = UGameplayStatics::GetPlayerController(this, 0);
		const bool bRun = PC && (PC->IsInputKeyDown(EKeys::LeftShift) || PC->IsInputKeyDown(EKeys::RightShift));
		const float Gait = bRun ? BaseWalkSpeed : FMath::Min(WalkSpeed, BaseWalkSpeed);
		Ch->GetCharacterMovement()->MaxWalkSpeed = Gait * SpeedRequest;
		// вприсядку — медленнее шага, Shift не помогает
		Ch->GetCharacterMovement()->MaxWalkSpeedCrouched = FMath::Min(WalkSpeed, BaseWalkSpeed) * 0.6f * SpeedRequest;
		if (PC)
		{
			UpdateCrouch(Ch, PC);
		}
		if (Helmet && bSuitOn)
		{
			Helmet->SetWorldLocation(Ch->GetMesh()->GetSocketLocation(TEXT("head")) + FVector(0.f, 0.f, 9.f));
			Helmet->SetHiddenInGame(Ch->IsHidden() || !Ch->GetMesh()->IsVisible());
		}
		SpeedRequest = 1.f;   // угроза просит замедление каждый кадр заново
		// дым: камера героя вприсядку прижата под слой — штанга опускается и укорачивается, когда игрок смотрит вниз
		if (USpringArmComponent* Boom = Ch->FindComponentByClass<USpringArmComponent>())
		{
			float Arm = BoomArm, Rise = BoomRise;
			if (CameraCeiling < TNumericLimits<float>::Max() && IsPlayerCrouched() && PC)
			{
				const float Room = FMath::Max(0.f, CameraCeiling - Boom->GetComponentLocation().Z);   // сколько можно подняться над осью штанги
				const float Down = FMath::DegreesToRadians(-FRotator::NormalizeAxis(PC->GetControlRotation().Pitch));   // > 0 — взгляд вниз
				Rise = FMath::Min(BoomRise, Room * 0.5f);
				if (Down > 0.01f)
				{
					Arm = FMath::Clamp((Room - Rise * FMath::Cos(Down)) / FMath::Sin(Down), 110.f, BoomArm);
				}
			}
			Boom->TargetArmLength = FMath::FInterpTo(Boom->TargetArmLength, Arm, DeltaSeconds, 6.f);
			Boom->SocketOffset.Z = FMath::FInterpTo(Boom->SocketOffset.Z, Rise, DeltaSeconds, 6.f);
		}
		CameraCeiling = TNumericLimits<float>::Max();   // и потолок камеры — тоже каждый кадр
		// у стены камера упирается и въезжает в персонажа: на это время он скрыт, иначе его спина закрывает весь экран
		if (const APlayerCameraManager* Cam = UGameplayStatics::GetPlayerCameraManager(this, 0))
		{
			const float Near = FVector::Dist(Cam->GetCameraLocation(), Ch->GetActorLocation() + FVector(0.f, 0.f, 40.f));
			if (Near < 105.f && !Ch->IsHidden())
			{
				Ch->SetActorHiddenInGame(true);
			}
			else if (Near > 130.f && Ch->IsHidden())
			{
				Ch->SetActorHiddenInGame(false);
			}
		}
	}
	if (bBusy && Phase != ERunPhase::Playing)
	{
		CancelTransition();   // погиб в шлюзе: комната не меняется, экран смерти не превращается в победу
	}
	else if (bBusy && Now >= SwapAt && RoomActor && RoomActor->AllLeavesClosed())
	{
		const APawn* Pawn = UGameplayStatics::GetPlayerPawn(this, 0);
		if (Pawn && RoomActor->VestibuleOf(Pawn->GetActorLocation()) != PendingDoor)
		{
			CancelTransition();   // игрока выбило из тамбура, пока створки закрывались: старую комнату убирать нельзя
		}
		else
		{
			DoSwap();
		}
	}
	TickFollowers();
	TickHeldItem(DeltaSeconds);
	if (Now >= TipUntil && TipQueue.Num() > 0)
	{
		Tip = TipQueue[0];
		TipQueue.RemoveAt(0);
		TipUntil = Now + 5.f;
	}
	if (Phase != ERunPhase::Playing && Now >= RestartAt && !bSelfTest)
	{
		RestartRun();
		return;
	}
	if (bSelfTest)
	{
		TickSelfTest();
	}
}

// Самопроверка, три сценария. Игрока переносим в центр комнаты, затем в тамбур: дальше работает обычная логика.
// Итог — строки «Run:» в журнале.
// 1. Путь: взять блокнот; дважды на север — обе комнаты та же рубка с теми же вещами; взять проводника;
//    на север — комната набора {L}; назад — снова рубка; выбросить всё; на восток — жилая комната.
// 2. Аномалия (-RunThreat=1..4): войти в опасную комнату, постоять, вернуться той же дверью.
// 3. Противник (-RunThreat=5..7): войти с ключом, уйти назад; человек должен прийти следом, остальные — остаться;
//    добить пришедшего, вернуться и добить оставшихся.
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
	auto GoToTrap = [&]()
	{
		for (ARunItem* A : ItemActors)
		{
			const int32 Role = A && !A->IsNote() ? Layout->RoleOf(A->ItemId) : RoleNotInRun;
			if (Role >= NumChain && Role < Layout->NumSig)
			{
				MoveTo(A->GetActorLocation());
				return;
			}
		}
		UE_LOG(LogRun, Error, TEXT("Run: test: в комнате нет лишнего значимого предмета"));
	};
	// 100 — подойти к блокноту, 101 — взять, 102 — подойти к проводнику, 103 — выбросить всё, 104 — конец,
	// 105 — подойти к оружию, 110 — подойти к предмету-ловушке, 111 — отчёт об угрозах, 112 — ждать,
	// 120 — встать вплотную к ближайшему противнику и ударить, −1 — встать в центр комнаты, 0..3 — войти в тамбур двери
	// 130 — инвентарь: блокнот раскрыть и полистать, аптечку взять в руку и применить после ушиба
	static const int32 PathSteps[] = { 100, 101, 130, -1, 0, -1, 0, 102, 101, -1, 0, -1, 1, 103, -1, 3, 104 };
	static const int32 AnomalySteps[] = { 100, 101, 110, 101, -1, 0, -1, 111, 112, 112, 112, 1, -1, 111, 104 };
	// выгоревшая комната (-RunBurned=1): камера в каждом дверном проёме (113), снимок окна игры (114),
	// камера обратно за героя (115). Снимки — Saved/Screenshots/Burned/seed<зерно>_t<угроза>_key<набор>_<дверь>.png; с ключом -RunShots — и без пожара
	// 116 — снимок с камеры игрока (в дыму и при -RunEmergency=1), 117 — присесть или встать (только в дыму:
	// видно ли под слоем), 118 — фонарик в руку (только при -RunEmergency=1)
	static const int32 BurnedSteps[] = { 100, 101, 110, 101, -1, 0, -1, 111, 113, 114, 113, 114, 113, 114, 113, 114, 115,
		116, 117, 116, 117, 118, 116, 1, -1, 104 };
	static const int32 EnemySteps[] = { 100, 101, 105, 101, 110, 101, -1, 0, -1, 111, 112, 112, 1, -1, 111,
		112, 112, 112, 112, 112, 112, 112, 112, 112, 112, 111, 120, 120, 120, 120, 120, 111,
		-1, 0, -1, 111, 120, 120, 120, 120, 120, 120, 120, 120, 111, 104 };
	// полный забег по шпаргалке (-RunWin): 200+R — подойти к предмету роли R, 210 — выбросить проводника,
	// 220 — выбросить всё, кроме блокнота, 106 — отчёт о состоянии
	// 230 — надеть скафандр, если он в комнате (уровни 1 и 2: разгерметизация на 2 или 3)
	static const int32 WinSteps[] = { 100, 101, 200, 101, -1, 0, -1, 201, 101, 230, -1, 0, -1, 202, 101, 230, -1, 0, -1,
		210, 203, 101, -1, 0, -1, 106, 220, -1, 0, -1, 106, 104 };
	// показ для снимков (-RunShow; в редакторе — ключ запуска самого редактора): прочитать записки рубки,
	// аптечка в руке после ушиба, осмотр, меню на Tab (144 — снимок в Saved/Screenshots/Menu, 145 — закладка выше).
	// 199 — пауза, каждое состояние держится несколько секунд
	static const int32 ShowSteps[] = { 100, 101, 140, -1, 141, 199, 199, 199, 199, 199, 199, 199, 142, 199, 199, 199, 144, 199, 199, 199,
		143, 199, 199, 144, 199, 145, 199, 199, 144, 199, 199, 199, 199 };
	const int32* Steps = PathSteps;
	int32 NumSteps = UE_ARRAY_COUNT(PathSteps);
	if (bShowTest)
	{
		Steps = ShowSteps;
		NumSteps = UE_ARRAY_COUNT(ShowSteps);
	}
	else if (bWinTest)
	{
		Steps = WinSteps;
		NumSteps = UE_ARRAY_COUNT(WinSteps);
	}
	// -RunShots: те же снимки из проёмов для любой аномалии, не только в выгоревшей комнате
	else if (ForceThreatKind > 0 && ARunThreat::IsAnomaly(ForceThreatKind) && (ForceBurned > 0 || FParse::Param(FCommandLine::Get(), TEXT("RunShots"))))
	{
		Steps = BurnedSteps;
		NumSteps = UE_ARRAY_COUNT(BurnedSteps);
	}
	else if (ForceThreatKind > 0 && ARunThreat::IsAnomaly(ForceThreatKind))
	{
		Steps = AnomalySteps;
		NumSteps = UE_ARRAY_COUNT(AnomalySteps);
	}
	else if (ForceThreatKind > 0)
	{
		Steps = EnemySteps;
		NumSteps = UE_ARRAY_COUNT(EnemySteps);
	}
	if (TestStep >= NumSteps)
	{
		bSelfTest = false;
		if (!GIsEditor)
		{
			FPlatformMisc::RequestExit(false);   // игра без окна закрывается сама; редактор не трогаем
		}
		return;
	}
	TestNextAt = Now + 0.8f;
	const int32 Step = Steps[TestStep++];
	switch (Step)
	{
	case 100: GoToItem(Notebook); break;
	case 101: OnInteract(); UE_LOG(LogRun, Display, TEXT("Run: test took, pocket=%d journal=%d key=%d"), Pocket.Num(), Journal.Num(), Layout->PocketKey(Pocket)); break;
	case 102: GoToItem(Layout->RoleItem[RoleL]); break;
	case 103: while (Pocket.Num() > 0) { DropSlot(0); } UE_LOG(LogRun, Display, TEXT("Run: test dropped all, pocket=%d key=%d"), Pocket.Num(), Layout->PocketKey(Pocket)); break;
	case 104: UE_LOG(LogRun, Display, TEXT("Run: test done rooms=%d sets=%d health=%.0f damage=%.0f medkits=%d"), Rooms.Num(), Keys.Num(), Health, DamageTaken, MedkitsUsed); break;
	case 105: GoToItem(Weapon); break;
	case 106:
		UE_LOG(LogRun, Display, TEXT("Run: test state room=%d type=%s engine=%d phase=%s pocket=%d journal=%d health=%.0f"), CurrentRoom,
			RoomTypeName(CurrentContent().RoomType), bEngineFixed ? 1 : 0,
			Phase == ERunPhase::Won ? TEXT("WON") : Phase == ERunPhase::Dead ? TEXT("DEAD") : TEXT("playing"), Pocket.Num(), Journal.Num(), Health);
		break;
	case 200: case 201: case 202: case 203: GoToItem(Layout->RoleItem[Step - 200]); break;
	case 230:
		// скафандр в этой комнате — подойти и надеть (разгерметизация уровнем дальше). -RunNoSuit — не надевать:
		// проверка, что шлюз без него не пускает
		for (ARunItem* A : FParse::Param(FCommandLine::Get(), TEXT("RunNoSuit")) ? TArray<ARunItem*>() : ItemActors)
		{
			if (A && !A->IsNote() && A->ItemId == Suit)
			{
				MoveTo(A->GetActorLocation());
				OnInteract();
				UE_LOG(LogRun, Display, TEXT("Run: test suit=%d"), bSuitOn ? 1 : 0);
				break;
			}
		}
		break;
	case 210:
	{
		const int32 Slot = Pocket.IndexOfByKey(Layout->RoleItem[RoleL]);
		DropSlot(Slot);
		UE_LOG(LogRun, Display, TEXT("Run: test dropped the loop item, pocket=%d"), Pocket.Num());
		break;
	}
	case 220:
		for (int32 I = Pocket.Num() - 1; I >= 0; --I)
		{
			if (Pocket[I] != Notebook)
			{
				DropSlot(I);
			}
		}
		UE_LOG(LogRun, Display, TEXT("Run: test dropped all but the notebook, pocket=%d key=%d"), Pocket.Num(), Layout->PocketKey(Pocket));
		break;
	case 110: GoToTrap(); break;
	case 140:
	{
		const TArray<TObjectPtr<ARunItem>> Here = ItemActors;
		for (ARunItem* A : Here)
		{
			if (A && A->IsNote())
			{
				MoveTo(A->GetActorLocation());
				OnInteract();
			}
		}
		UE_LOG(LogRun, Display, TEXT("Run: show notes read, journal=%d"), Journal.Num());
		break;
	}
	case 141:
		Pocket.Add(Medkit);
		HeldSlot = Pocket.Num() - 1;
		HurtPlayer(TEXT("Show bruise."), Pawn->GetActorLocation() + FVector(-100.f, 0.f, 0.f), 45.f);
		break;
	case 142: OnInspect(); UE_LOG(LogRun, Display, TEXT("Run: show inspecting=%d"), IsInspecting() ? 1 : 0); break;
	case 143: OnToggleJournal(); UE_LOG(LogRun, Display, TEXT("Run: show reading=%d"), IsReading() ? 1 : 0); break;
	case 144:
	{
		static int32 MenuShot = 0;
		const FString Path = FPaths::ProjectSavedDir() / FString::Printf(TEXT("Screenshots/Menu/show_%d.png"), MenuShot++);
		FScreenshotRequest::RequestScreenshot(Path, true, false);
		UE_LOG(LogRun, Display, TEXT("Run: show shot %s menu=%d bookmarks=%d"), *Path, IsReading() ? 1 : 0, Bookmarks.Num());
		break;
	}
	case 145: StepBookmark(-1); UE_LOG(LogRun, Display, TEXT("Run: show bookmark=%d"), GetBookmark()); break;
	case 199: break;
	case 130:
	{
		OnToggleJournal();
		const bool bRead = IsReading();
		TurnPage(-1);
		OnToggleJournal();
		const int32 Was = Pocket.Num();
		Pocket.Add(Medkit);   // аптечку из ниши заменяет выданная: в стартовой рубке её может не быть
		SelectSlot(Pocket.Num() - 1);
		OnInspect();
		const bool bLook = IsInspecting();
		HurtPlayer(TEXT("Test bruise."), Pawn->GetActorLocation() + FVector(100.f, 0.f, 0.f), 30.f);
		const float Hurt = Health;
		OnUse();
		UE_LOG(LogRun, Display, TEXT("Run: test inventory reading=%d inspecting=%d health %.0f -> %.0f pocket %d -> %d held=%d looklock=%d"),
			bRead ? 1 : 0, bLook ? 1 : 0, Hurt, Health, Was, Pocket.Num(), GetHeldSlot(), bLookLocked ? 1 : 0);
		break;
	}
	case 111:
		UE_LOG(LogRun, Display, TEXT("Run: test threats room=%d key=%d kind=%s anomaly=%d enemies_here=%d following=%d alive=%d health=%.0f"),
			CurrentRoom, Rooms[CurrentRoom].Key, AnomalyName(ThreatKindOf(Rooms[CurrentRoom].Key)), ThreatActor ? 1 : 0,
			EnemyActors.Num(), GetFollowers(), Enemies.Num(), Health);
		break;
	case 113:
	{
		// камера в дверном проёме (проёмы в любой комнате свободны), выше головы, смотрит на противоположную стену;
		// герой — в середине комнаты, для масштаба
		const FVector Mid = RoomActor->GetActorLocation();
		Pawn->SetActorLocation(FVector(Mid.X, Mid.Y, Pawn->GetActorLocation().Z), false, nullptr, ETeleportType::TeleportPhysics);
		const int32 Door = TestShot % 4;
		const FVector Out = RunRoomGeo::Dir(Door);
		// в дыму камера под слоем (иначе в кадре одна пелена): вприсядку, с пола вверх, у нижней кромки, по плечи в дыму
		static const float SmokeEye[] = { 85.f, 50.f, 100.f, 135.f }, SmokeAim[] = { 110.f, 200.f, 100.f, 95.f };
		const bool bLow = ForceThreatKind == ThreatSmoke;
		const FVector From = Mid + Out * (RunRoomGeo::InnerFace(Door) - 20.f) + FVector(0.f, 0.f, bLow ? SmokeEye[Door] : 215.f);
		const FRotator Look = (Mid - Out * RunRoomGeo::InnerFace(Door) + FVector(0.f, 0.f, bLow ? SmokeAim[Door] : 70.f) - From).Rotation();
		ACameraActor* Cam = Cast<ACameraActor>(TestCam.Get());
		if (!Cam)
		{
			Cam = GetWorld()->SpawnActor<ACameraActor>(From, Look);
			Cam->GetCameraComponent()->bConstrainAspectRatio = false;   // без чёрных полей по бокам
			Cam->GetCameraComponent()->SetFieldOfView(90.f);
			TestCam = Cam;
		}
		Cam->SetActorLocationAndRotation(From, Look);
		if (APlayerController* PC = UGameplayStatics::GetPlayerController(this, 0))
		{
			PC->SetViewTargetWithBlend(Cam, 0.f);
			if (PC->MyHUD)
			{
				PC->MyHUD->bShowHUD = false;
			}
		}
		TestNextAt = Now + 1.f;
		break;
	}
	case 114:
	{
		const FString Path = FPaths::ProjectSavedDir() / FString::Printf(TEXT("Screenshots/Burned/seed%u_t%d_key%d_%d.png"),
			static_cast<uint32>(Seed), ForceThreatKind, Rooms[CurrentRoom].Key, TestShot % 4);
		FScreenshotRequest::RequestScreenshot(Path, false, false);
		UE_LOG(LogRun, Display, TEXT("Run: test shot %s"), *Path);
		++TestShot;
		TestNextAt = Now + 0.5f;
		break;
	}
	case 115:
		if (APlayerController* PC = UGameplayStatics::GetPlayerController(this, 0))
		{
			PC->SetViewTargetWithBlend(Pawn, 0.f);
			if (PC->MyHUD)
			{
				PC->MyHUD->bShowHUD = true;
			}
		}
		break;
	case 118:
		if (ForceEmergency > 0 && Pocket.Num() < PocketSlots)
		{
			Pocket.Add(0);   // фонарик — первая вещь каталога
			HeldSlot = Pocket.Num() - 1;
			UE_LOG(LogRun, Display, TEXT("Run: test flashlight in hand=%d"), IsFlashlight(Pocket[HeldSlot]) ? 1 : 0);
			TestNextAt = Now + 1.2f;
		}
		break;
	case 116:
		if (ForceThreatKind == ThreatSmoke || ForceEmergency > 0)
		{
			const bool bFlash = GetHeldSlot() >= 0 && IsFlashlight(Pocket[HeldSlot]);
			const FString Path = FPaths::ProjectSavedDir() / FString::Printf(TEXT("Screenshots/Burned/seed%u_t%d_key%d_player_%s.png"),
				static_cast<uint32>(Seed), ForceThreatKind, Rooms[CurrentRoom].Key, bFlash ? TEXT("flashlight") : IsPlayerCrouched() ? TEXT("crouch") : TEXT("stand"));
			FScreenshotRequest::RequestScreenshot(Path, true, false);
			UE_LOG(LogRun, Display, TEXT("Run: test shot %s"), *Path);
			TestNextAt = Now + 0.5f;
		}
		break;
	case 117:
		if (ForceThreatKind == ThreatSmoke)
		{
			OnCrouchKey();
			TestNextAt = Now + 1.2f;
		}
		break;
	case 112:
	{
		const FVector Local = Pawn->GetActorLocation() - RoomActor->GetActorLocation();
		UE_LOG(LogRun, Display, TEXT("Run: test wait, pawn at (%.0f, %.0f, %.0f) health=%.0f"), Local.X, Local.Y, Local.Z, Health);
		for (const ARunEnemy* A : EnemyActors)
		{
			const FVector At = A->GetFloorPos() - RoomActor->GetActorLocation();
			UE_LOG(LogRun, Display, TEXT("Run: test   enemy id=%d at (%.0f, %.0f)"), A->EnemyId, At.X, At.Y);
		}
		break;
	}
	case 120:
	{
		ARunEnemy* Near = nullptr;
		for (ARunEnemy* A : EnemyActors)
		{
			if (A && (!Near || FVector::Dist2D(A->GetFloorPos(), Pawn->GetActorLocation()) < FVector::Dist2D(Near->GetFloorPos(), Pawn->GetActorLocation())))
			{
				Near = A;
			}
		}
		if (Near)
		{
			MoveTo(Near->GetFloorPos() + (RoomActor->GetActorLocation() - Near->GetFloorPos()).GetSafeNormal2D() * 60.f);
			OnAttack();
		}
		else
		{
			UE_LOG(LogRun, Display, TEXT("Run: test: no enemy here to hit"));
		}
		break;
	}
	case -1: MoveTo(RoomActor->GetActorLocation() + FVector(-330.f, 120.f, 0.f)); break;
	default: MoveTo(RoomActor->VestibuleCenter(Step)); break;
	}
}
