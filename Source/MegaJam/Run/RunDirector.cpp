#include "RunDirector.h"

#include "Animation/AnimInstance.h"
#include "Animation/AnimMontage.h"
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
#include "Components/AudioComponent.h"
#include "RunAudio.h"
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
		Hero->JumpMaxCount = 0;   // Space — рывок-уклонение (OnDodge), прыжка нет
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
		HandPivot->SetupAttachment(Hero->GetMesh(), TEXT("hand_l"));
		HandPivot->SetUsingAbsoluteRotation(true);
		HandPivot->RegisterComponent();
		// инструменты в руках: оружие — у правой кисти, фонарик — у левой; как лежит каждый — GripInHand
		auto MakeGrip = [this, Hero](const TCHAR* Name, const TCHAR* Bone)
		{
			UStaticMeshComponent* Grip = NewObject<UStaticMeshComponent>(this, Name);
			Grip->SetupAttachment(Hero->GetMesh(), Bone);
			Grip->SetCollisionEnabled(ECollisionEnabled::NoCollision);
			Grip->SetReceivesDecals(false);
			Grip->SetVisibility(false);
			Grip->RegisterComponent();
			return Grip;
		};
		GripMesh = MakeGrip(TEXT("GripMesh"), TEXT("hand_r"));
		GripMeshLeft = MakeGrip(TEXT("GripMeshLeft"), TEXT("hand_l"));
		{
			FString Text;
			TArray<FString> V;
			if (FParse::Value(FCommandLine::Get(), TEXT("RunGrip="), Text, false) && Text.ParseIntoArray(V, TEXT(",")) == 6)
			{
				bGripOverride = true;
				bGripOverrideFlash = FParse::Param(FCommandLine::Get(), TEXT("RunGripFlash"));
				for (int32 I = 0; I < 6; ++I)
				{
					GripOverride[I] = FCString::Atof(*V[I]);
				}
			}
			V.Reset();
			if (FParse::Value(FCommandLine::Get(), TEXT("RunFist="), Text, false) && Text.ParseIntoArray(V, TEXT(",")) == 5)
			{
				for (int32 I = 0; I < 3; ++I)
				{
					FistCurl[I] = FCString::Atof(*V[I]);
				}
				FistThumb[0] = FCString::Atof(*V[3]);
				FistThumb[1] = FCString::Atof(*V[4]);
			}
		}
		// кулак: пальцы догибаются после того, как анимация посчитала кости кадра
		FistMesh = Hero->GetMesh();
		Hero->GetMesh()->RegisterOnBoneTransformsFinalizedDelegate(
			FOnBoneTransformsFinalizedMultiCast::FDelegate::CreateUObject(this, &ARunDirector::ApplyFist));
		if (FParse::Param(FCommandLine::Get(), TEXT("RunGripTest")))
		{
			GripTestStep = 0;
			GripTestAt = GetWorld()->GetTimeSeconds() + 2.5f;
		}
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
		// клавиши меню работают и на паузе: меню на Tab останавливает время. На паузе Esc их глушат сами обработчики (bMenuPause)
		InputComponent->BindKey(EKeys::One, IE_Pressed, this, &ARunDirector::OnSelect1).bExecuteWhenPaused = true;
		InputComponent->BindKey(EKeys::Two, IE_Pressed, this, &ARunDirector::OnSelect2).bExecuteWhenPaused = true;
		InputComponent->BindKey(EKeys::Three, IE_Pressed, this, &ARunDirector::OnSelect3).bExecuteWhenPaused = true;
		InputComponent->BindKey(EKeys::Four, IE_Pressed, this, &ARunDirector::OnSelect4).bExecuteWhenPaused = true;
		InputComponent->BindKey(EKeys::V, IE_Pressed, this, &ARunDirector::OnToggleLight);
		InputComponent->BindKey(EKeys::MouseScrollUp, IE_Pressed, this, &ARunDirector::OnWheelUp).bExecuteWhenPaused = true;
		InputComponent->BindKey(EKeys::MouseScrollDown, IE_Pressed, this, &ARunDirector::OnWheelDown).bExecuteWhenPaused = true;
		InputComponent->BindKey(EKeys::G, IE_Pressed, this, &ARunDirector::OnDropHeld).bExecuteWhenPaused = true;
		InputComponent->BindKey(EKeys::RightMouseButton, IE_Pressed, this, &ARunDirector::OnInspect).bExecuteWhenPaused = true;
		InputComponent->BindKey(EKeys::Left, IE_Pressed, this, &ARunDirector::OnPagePrev).bExecuteWhenPaused = true;
		InputComponent->BindKey(EKeys::Right, IE_Pressed, this, &ARunDirector::OnPageNext).bExecuteWhenPaused = true;
		InputComponent->BindKey(EKeys::Up, IE_Pressed, this, &ARunDirector::OnBookmarkPrev).bExecuteWhenPaused = true;
		InputComponent->BindKey(EKeys::Down, IE_Pressed, this, &ARunDirector::OnBookmarkNext).bExecuteWhenPaused = true;
		InputComponent->BindKey(EKeys::Tab, IE_Pressed, this, &ARunDirector::OnToggleJournal).bExecuteWhenPaused = true;
		InputComponent->BindKey(EKeys::C, IE_Pressed, this, &ARunDirector::OnCrouchKey);
		// рывок-уклонение; прыжок шаблона на Space выключен (SetupPlayer): в отсеках он не нужен
		InputComponent->BindKey(EKeys::SpaceBar, IE_Pressed, this, &ARunDirector::OnDodge);
		InputComponent->BindKey(EKeys::LeftAlt, IE_Pressed, this, &ARunDirector::OnDodge);
		InputComponent->BindKey(EKeys::T, IE_Pressed, this, &ARunDirector::TakeOffSuit).bExecuteWhenPaused = true;
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
	// мертвецы: в стартовой рубке (она же финальная) их нет; -RunCorpses=N — столько в каждой комнате, для проверки
	if (Rooms.Num() == 0 || Key != Rooms[0].Key || FParse::Param(FCommandLine::Get(), TEXT("RunCorpsesStart")))
	{
		FRunKeyState& Bodies = KeyState(Key);
		if (Bodies.bCorpsesPlaced)
		{
			RoomActor->SpawnCorpses(Bodies.Corpses);
		}
		else
		{
			// первый вход: тела ложатся туда, где сейчас ничего не лежит, и это место за ними остаётся
			Bodies.bCorpsesPlaced = true;
			int32 Force = -1;
			FParse::Value(FCommandLine::Get(), TEXT("RunCorpses="), Force);
			TArray<FVector> Occupied;
			for (const ARunItem* Thing : ItemActors)
			{
				if (Thing)
				{
					Occupied.Add(Thing->GetActorLocation());
				}
			}
			RoomActor->ApplyCorpses(Hash32({ Seed, 320U, static_cast<uint32>(Key) }), Force, Occupied, Bodies.Corpses);
		}
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

bool ARunDirector::IsWeapon(int32 Item)
{
	return Item == Weapon;
}

int32 ARunDirector::FlashlightItem() const
{
	const int32 Slot = Pocket.IndexOfByPredicate([](int32 Item) { return IsFlashlight(Item); });
	return Slot != INDEX_NONE ? Pocket[Slot] : TNumericLimits<int32>::Min();
}

void ARunDirector::OnToggleLight()
{
	if (Phase == ERunPhase::Playing && HasFlashlight() && !IsReading())
	{
		bLightOn = !bLightOn;
	}
}

bool ARunDirector::GripInHand(int32 Item, bool bLeft, const USkeletalMeshComponent* Mesh, FTransform& Out) const
{
	const USkeletalMesh* Asset = Mesh ? Mesh->GetSkeletalMeshAsset() : nullptr;
	if (!Asset)
	{
		return false;
	}
	// Место рукояти — в осях кости кисти, по позе покоя меша: суставы оснований пальцев дают линию костяшек (ось хвата),
	// направление пальцев и сторону ладони. Пальцы потом обжимают рукоять сами (ApplyFist).
	const FReferenceSkeleton& Ref = Asset->GetRefSkeleton();
	const TCHAR* Side = bLeft ? TEXT("l") : TEXT("r");
	const int32 Hand = Ref.FindBoneIndex(*FString::Printf(TEXT("hand_%s"), Side));
	auto At = [&Ref, Hand, Side](const TCHAR* Bone, FVector& OutAt)
	{
		int32 I = Ref.FindBoneIndex(*FString::Printf(TEXT("%s_%s"), Bone, Side));
		if (I == INDEX_NONE || Hand == INDEX_NONE)
		{
			return false;
		}
		FTransform T = FTransform::Identity;
		for (; I != INDEX_NONE && I != Hand; I = Ref.GetParentIndex(I))
		{
			T = T * Ref.GetRefBonePose()[I];
		}
		OutAt = T.GetLocation();
		return I == Hand;
	};
	FVector I1, M1, M2, R1, P1, Th;
	if (!At(TEXT("index_01"), I1) || !At(TEXT("middle_01"), M1) || !At(TEXT("middle_02"), M2) || !At(TEXT("ring_01"), R1)
		|| !At(TEXT("pinky_01"), P1) || !At(TEXT("thumb_02"), Th))
	{
		return false;
	}
	const FVector Knuckles = (P1 - I1).GetSafeNormal();                 // ось хвата: от указательного к мизинцу
	const FVector Fingers = (M2 - M1).GetSafeNormal();                  // куда смотрят пальцы
	FVector Palm = FVector::CrossProduct(Knuckles, Fingers).GetSafeNormal();
	if (FVector::DotProduct(Palm, Th - M1) < 0.f)
	{
		Palm = -Palm;                                                   // ладонь — с той стороны, где большой палец
	}
	// Что у инструмента где: GripZ — место хвата по длине меша (см от начала), Tilt — наклон оси от трубы пальцев
	// к пальцам, Depth и Reach — сдвиг от середины трубы к ладони и вдоль пальцев, Roll — поворот вокруг своей оси,
	// Side — куда смотрит рабочий конец: 1 — со стороны мизинца, −1 — большого пальца.
	// Ключ (меш рукоятью вверх, губки в начале): прямой хват, как молоток, губки со стороны большого пальца — вверх,
	// когда рука в стойке (автор, 15.11: обратный хват «технически возможен, но абсурден»). Фонарик (линза в конце
	// меша): тоже со стороны большого пальца, с наклоном к пальцам — при опущенном вперёд предплечье смотрит вперёд.
	// Бластер (переделанный сварочный аппарат, автор 15.11) — сюда же, когда появится в игре: пистолетный хват.
	// Ось и середина хвата — «труба», которую образуют согнутые пальцы (FistPose этой руки: его строит BuildFist
	// под толщину рукояти перед тем, как сюда прийти). Пальцы разной длины, поэтому труба наклонена к линии костяшек.
	const FRunFist& Pose = FistPose[bLeft ? 1 : 0];
	if (!Pose.bValid)
	{
		return false;
	}
	const FVector Along = Pose.Along;                                    // ось трубы: от мизинца к указательному
	const bool bFlash = IsFlashlight(Item);
	// ключ: рукоять свободна от 21 до 39 см от губок, дальше отверстие для подвеса (39,5–43 см) — кулак шириной
	// 9 см стоит ниже него, иначе мизинец попадает в отверстие; середина сечения рукояти там смещена от оси меша
	float GripZ = bFlash ? 6.f : 33.5f, Tilt = bFlash ? 38.f : 0.f, Depth = 0.f, Reach = 0.f, Roll = 0.f;
	const FVector2D Core = bFlash ? FVector2D::ZeroVector : FVector2D(0.3f, 0.2f);
	float Head = -1.f;
	if (bGripOverride && bFlash == bGripOverrideFlash)
	{
		GripZ = GripOverride[0];
		Tilt = GripOverride[1];
		Depth = GripOverride[2];
		Reach = GripOverride[3];
		Roll = GripOverride[4];
		Head = GripOverride[5] < 0.f ? -1.f : 1.f;
	}
	const FVector Center = Pose.Center + Palm * Depth + Fingers * Reach;
	// куда смотрит рабочий конец: вдоль трубы пальцев (к большому пальцу при Head = −1), с наклоном к пальцам
	const FVector Base = Along * -Head;
	const FVector Work = Base.RotateAngleAxis(Tilt, FVector::CrossProduct(Base, Fingers).GetSafeNormal());
	const FVector Z = bFlash ? Work : -Work;                            // ось меша: от начала к концу
	FVector Y = (Palm - Z * FVector::DotProduct(Palm, Z)).GetSafeNormal();   // плоская сторона ключа — к ладони
	Y = Y.RotateAngleAxis(Roll, Z);
	const FVector X = FVector::CrossProduct(Y, Z);
	const FQuat Rot = FMatrix(X, Y, Z, FVector::ZeroVector).ToQuat();
	Out = FTransform(Rot, Center - Rot.RotateVector(FVector(Core.X, Core.Y, GripZ)));
	return true;
}

void ARunDirector::PoseArm(TArray<FTransform>& CS, USkeletalMeshComponent* Mesh, int32 S, float Weight, const FVector& Upper, const FVector& Fore, const FVector& Thumb)
{
	const TCHAR* Side = S == 0 ? TEXT("r") : TEXT("l");
	const USkeletalMesh* Asset = Mesh->GetSkeletalMeshAsset();
	if (!Asset)
	{
		return;
	}
	const FReferenceSkeleton& Ref = Asset->GetRefSkeleton();
	const int32 Root[3] = { Ref.FindBoneIndex(*FString::Printf(TEXT("upperarm_%s"), Side)), Ref.FindBoneIndex(*FString::Printf(TEXT("lowerarm_%s"), Side)),
		Ref.FindBoneIndex(*FString::Printf(TEXT("hand_%s"), Side)) };
	if (Root[0] == INDEX_NONE || Root[1] == INDEX_NONE || Root[2] == INDEX_NONE || !CS.IsValidIndex(Root[2]))
	{
		return;
	}
	if (ArmTree[S][0].Num() == 0)
	{
		// кости плеча, предплечья и кисти вместе с потомками (скручивающие кости, пальцы): поворачиваются целиком
		for (int32 B = 0; B < Ref.GetNum(); ++B)
		{
			for (int32 P = B; P != INDEX_NONE; P = Ref.GetParentIndex(P))
			{
				for (int32 K = 0; K < 3; ++K)
				{
					if (P == Root[K])
					{
						ArmTree[S][K].Add(B);
					}
				}
			}
		}
	}
	if (!bHandFrame[S])
	{
		// оси кисти в её собственных осях: X — вдоль пальцев, Y — вдоль костяшек к мизинцу (по позе покоя, как в GripInHand)
		auto At = [&Ref, &Root](const FString& Bone)
		{
			FTransform T = FTransform::Identity;
			for (int32 I = Ref.FindBoneIndex(*Bone); I != INDEX_NONE && I != Root[2]; I = Ref.GetParentIndex(I))
			{
				T = T * Ref.GetRefBonePose()[I];
			}
			return T.GetLocation();
		};
		HandKnuckles[S] = (At(FString::Printf(TEXT("pinky_01_%s"), Side)) - At(FString::Printf(TEXT("index_01_%s"), Side))).GetSafeNormal();
		HandFingers[S] = (At(FString::Printf(TEXT("middle_02_%s"), Side)) - At(FString::Printf(TEXT("middle_01_%s"), Side))).GetSafeNormal();
		bHandFrame[S] = true;
		// скручивающие кости предплечья: докручиваются за кистью, чтобы запястье не перекручивалось одним швом
		for (int32 B = 0; B < Ref.GetNum(); ++B)
		{
			if (Ref.GetParentIndex(B) == Root[1] && Ref.GetBoneName(B).ToString().Contains(TEXT("twist")))
			{
				TwistBones[S].Add(B);
			}
		}
	}
	auto Turn = [&CS](const TArray<int32>& Tree, const FVector& Pivot, const FQuat& Q)
	{
		for (const int32 B : Tree)
		{
			if (CS.IsValidIndex(B))
			{
				CS[B].SetLocation(Pivot + Q.RotateVector(CS[B].GetLocation() - Pivot));
				CS[B].SetRotation(Q * CS[B].GetRotation());
			}
		}
	};
	// плечо: от плечевого сустава к локтю — по Upper; предплечье: от локтя к запястью — по Fore
	const FVector Shoulder = CS[Root[0]].GetLocation();
	Turn(ArmTree[S][0], Shoulder, FQuat::Slerp(FQuat::Identity, FQuat::FindBetweenNormals((CS[Root[1]].GetLocation() - Shoulder).GetSafeNormal(), Upper), Weight));
	const FVector Elbow = CS[Root[1]].GetLocation();
	Turn(ArmTree[S][1], Elbow, FQuat::Slerp(FQuat::Identity, FQuat::FindBetweenNormals((CS[Root[2]].GetLocation() - Elbow).GetSafeNormal(), Fore), Weight));
	// кисть: инструмент в кулаке смотрит точно по Thumb, пальцы — по предплечью, насколько позволяет инструмент
	// (разница — излом запястья). Ось инструмента в осях кисти — та, по которой он лежит в кулаке (GripInHand);
	// без инструмента — линия костяшек к большому пальцу.
	const FVector Yh = ToolAxis[S].IsNearlyZero() ? HandKnuckles[S] : -ToolAxis[S];
	const FVector Xh = (HandFingers[S] - Yh * FVector::DotProduct(HandFingers[S], Yh)).GetSafeNormal();
	const FQuat HandFrame = FMatrix(Xh, Yh, FVector::CrossProduct(Xh, Yh), FVector::ZeroVector).ToQuat();
	const FVector Y = -Thumb.GetSafeNormal();
	const FVector X = (Fore - Y * FVector::DotProduct(Fore, Y)).GetSafeNormal();
	const FQuat Want = FMatrix(X, Y, FVector::CrossProduct(X, Y), FVector::ZeroVector).ToQuat() * HandFrame.Inverse();
	const FTransform Old = CS[Root[2]];
	const FTransform New(FQuat::Slerp(Old.GetRotation(), Want, Weight), Old.GetLocation(), Old.GetScale3D());
	for (const int32 B : ArmTree[S][2])
	{
		if (CS.IsValidIndex(B))
		{
			CS[B] = CS[B].GetRelativeTransform(Old) * New;
		}
	}
	// насколько кисть провернулась вокруг предплечья относительно прежнего — на столько же, по доле длины, скручивающие кости
	FQuat Swing, Twist;
	(New.GetRotation() * Old.GetRotation().Inverse()).ToSwingTwist(Fore, Swing, Twist);
	const float Length = FMath::Max((Old.GetLocation() - Elbow).Size(), 1.f);
	for (const int32 B : TwistBones[S])
	{
		if (CS.IsValidIndex(B))
		{
			const float Share = FMath::Clamp(FVector::DotProduct(CS[B].GetLocation() - Elbow, Fore) / Length, 0.f, 1.f);
			CS[B].SetRotation(FQuat::Slerp(FQuat::Identity, Twist, Share) * CS[B].GetRotation());
		}
	}
}

void ARunDirector::SwingPose(float Along, int32 Kind, FVector& Upper, FVector& Fore, FVector& Tool, float& Twist, float& Lean) const
{
	// Поза — в осях героя: X вперёд, Y вправо, Z вверх. Upper — от плеча к локтю, Fore — от локтя к кисти, Tool — куда
	// смотрят губки ключа; Twist — поворот корпуса вправо, Lean — наклон вперёд, градусы.
	struct FKey { float At; FVector Upper, Fore, Tool; float Twist, Lean; };
	static const FKey GuardKey = { 0.f, FVector(0.2f, 0.22f, -0.95f), FVector(0.88f, -0.25f, 0.42f), FVector(-0.2f, 0.f, 0.98f), 0.f, 0.f };
	// Удар быстрый (замечание автора 15.11: «как будто медленный»): замах — четверть времени, губки доходят до цели
	// к 0,46; корпус заметно уходит назад на замахе и проворачивается за ударом (Twist до 50 градусов).
	static const FKey Poses[3][4] = {
		{   // наискось сверху: из-за правого плеча вперёд и влево-вниз
			{ 0.26f, FVector(-0.25f, 0.75f, 0.35f), FVector(-0.35f, 0.15f, 0.9f), FVector(-0.95f, 0.2f, 0.1f), 40.f, -6.f },
			{ 0.37f, FVector(0.45f, 0.45f, 0.1f), FVector(0.7f, 0.1f, 0.6f), FVector(-0.1f, 0.2f, 0.97f), 12.f, 2.f },
			{ 0.46f, FVector(0.8f, -0.1f, -0.45f), FVector(0.75f, -0.35f, -0.5f), FVector(0.85f, -0.3f, 0.35f), -34.f, 14.f },
			{ 0.62f, FVector(0.45f, -0.5f, -0.7f), FVector(0.2f, -0.85f, -0.3f), FVector(0.6f, -0.25f, -0.75f), -46.f, 16.f },
		},
		{   // сбоку: справа налево на уровне груди
			{ 0.26f, FVector(-0.15f, 0.85f, -0.35f), FVector(-0.2f, 0.9f, 0.3f), FVector(-0.8f, -0.1f, 0.5f), 48.f, 0.f },
			{ 0.37f, FVector(0.3f, 0.8f, -0.5f), FVector(0.75f, 0.3f, -0.2f), FVector(0.15f, 0.95f, 0.2f), 18.f, 2.f },
			{ 0.46f, FVector(0.5f, 0.5f, -0.7f), FVector(0.6f, 0.7f, -0.15f), FVector(0.97f, -0.15f, 0.05f), -28.f, 6.f },
			{ 0.62f, FVector(0.6f, -0.2f, -0.75f), FVector(0.75f, -0.3f, -0.2f), FVector(0.3f, -0.9f, 0.1f), -50.f, 8.f },
		},
		{   // тяжёлый сверху вниз: из-за головы прямо перед собой
			{ 0.30f, FVector(0.1f, 0.35f, 0.9f), FVector(-0.3f, 0.05f, 0.9f), FVector(-0.9f, 0.f, 0.1f), 14.f, -12.f },
			{ 0.40f, FVector(0.5f, 0.25f, 0.6f), FVector(0.75f, 0.05f, 0.55f), FVector(0.05f, 0.f, 1.f), 4.f, 0.f },
			{ 0.48f, FVector(0.85f, 0.05f, -0.35f), FVector(0.8f, -0.1f, -0.55f), FVector(0.9f, -0.05f, 0.3f), -10.f, 24.f },
			{ 0.64f, FVector(0.6f, 0.f, -0.8f), FVector(0.5f, -0.1f, -0.85f), FVector(0.95f, -0.05f, -0.15f), -12.f, 30.f },
		},
	};
	const FKey* A = &GuardKey;
	const FKey* B = &GuardKey;
	float T = 0.f;
	if (Along >= 0.f && Along < 1.f)
	{
		const FKey* Row = Poses[FMath::Clamp(Kind, 0, 2)];
		float From = 0.f, To = 1.f;
		for (int32 K = 0; K <= 4; ++K)
		{
			const FKey* Next = K < 4 ? &Row[K] : &GuardKey;
			const float NextAt = K < 4 ? Row[K].At : 1.f;
			if (Along <= NextAt)
			{
				B = Next;
				To = NextAt;
				break;
			}
			A = Next;
			From = NextAt;
		}
		T = FMath::Clamp((Along - From) / FMath::Max(To - From, 0.001f), 0.f, 1.f);
		// из стойки в замах и из проводки в стойку — плавно; сам удар разгоняется от замаха
		if (A == &GuardKey || B == &GuardKey)
		{
			T = T * T * (3.f - 2.f * T);
		}
		else if (A == &Row[0])
		{
			T = T * T;
		}
	}
	auto Mix = [T](const FVector& From, const FVector& To)
	{
		const FVector N0 = From.GetSafeNormal(), N1 = To.GetSafeNormal();
		return FQuat::Slerp(FQuat::Identity, FQuat::FindBetweenNormals(N0, N1), T).RotateVector(N0);
	};
	Upper = Mix(A->Upper, B->Upper);
	Fore = Mix(A->Fore, B->Fore);
	Tool = Mix(A->Tool, B->Tool);
	Twist = FMath::Lerp(A->Twist, B->Twist, T);
	Lean = FMath::Lerp(A->Lean, B->Lean, T);
}

void ARunDirector::TurnTorso(TArray<FTransform>& CS, USkeletalMeshComponent* Mesh, float Weight, float Twist, float Lean, const FVector& F, const FVector& R, const FVector& U)
{
	if (FMath::Abs(Twist) < 0.2f && FMath::Abs(Lean) < 0.2f)
	{
		return;
	}
	const USkeletalMesh* Asset = Mesh->GetSkeletalMeshAsset();
	if (!Asset)
	{
		return;
	}
	const FReferenceSkeleton& Ref = Asset->GetRefSkeleton();
	// поворот делится пополам между низом и верхом спины: корпус закручивается, а не ломается в одном месте
	const int32 Root[2] = { Ref.FindBoneIndex(TEXT("spine_02")), Ref.FindBoneIndex(TEXT("spine_04")) };
	if (Root[0] == INDEX_NONE || Root[1] == INDEX_NONE)
	{
		return;
	}
	if (TorsoTree[0].Num() == 0)
	{
		for (int32 B = 0; B < Ref.GetNum(); ++B)
		{
			for (int32 P = B; P != INDEX_NONE; P = Ref.GetParentIndex(P))
			{
				for (int32 K = 0; K < 2; ++K)
				{
					if (P == Root[K])
					{
						TorsoTree[K].Add(B);
					}
				}
			}
		}
	}
	if (HeadTree.Num() == 0)
	{
		const int32 Neck = Ref.FindBoneIndex(TEXT("neck_01"));
		for (int32 B = 0; B < Ref.GetNum(); ++B)
		{
			for (int32 P = B; P != INDEX_NONE; P = Ref.GetParentIndex(P))
			{
				if (P == Neck)
				{
					HeadTree.Add(B);
				}
			}
		}
	}
	const float Yaw = FMath::DegreesToRadians(Twist * 0.5f * Weight), Pitch = FMath::DegreesToRadians(Lean * 0.5f * Weight);
	const FQuat Q = FQuat::FindBetweenNormals(F, (F * FMath::Cos(Yaw) + R * FMath::Sin(Yaw)).GetSafeNormal())
		* FQuat::FindBetweenNormals(U, (U * FMath::Cos(Pitch) + F * FMath::Sin(Pitch)).GetSafeNormal());
	for (int32 K = 0; K < 2; ++K)
	{
		if (!CS.IsValidIndex(Root[K]))
		{
			continue;
		}
		const FVector Pivot = CS[Root[K]].GetLocation();
		for (const int32 B : TorsoTree[K])
		{
			if (CS.IsValidIndex(B))
			{
				CS[B].SetLocation(Pivot + Q.RotateVector(CS[B].GetLocation() - Pivot));
				CS[B].SetRotation(Q * CS[B].GetRotation());
			}
		}
	}
	// голова смотрит туда же, куда герой: возвращается на две трети поворота корпуса
	if (HeadTree.Num() > 0 && CS.IsValidIndex(HeadTree[0]))
	{
		const float Back = -2.f * Yaw * 0.65f;
		const FQuat Qh = FQuat::FindBetweenNormals(F, (F * FMath::Cos(Back) + R * FMath::Sin(Back)).GetSafeNormal());
		const FVector Pivot = CS[HeadTree[0]].GetLocation();
		for (const int32 B : HeadTree)
		{
			if (CS.IsValidIndex(B))
			{
				CS[B].SetLocation(Pivot + Qh.RotateVector(CS[B].GetLocation() - Pivot));
				CS[B].SetRotation(Qh * CS[B].GetRotation());
			}
		}
	}
}

bool ARunDirector::BuildFist(const USkeletalMeshComponent* Mesh, bool bLeft, float HandleRadius, FRunFist& Out) const
{
	Out = FRunFist();
	const USkeletalMesh* Asset = Mesh ? Mesh->GetSkeletalMeshAsset() : nullptr;
	if (!Asset)
	{
		return false;
	}
	// Кулак задаётся целиком, в осях кости кисти, от позы покоя меша: от анимации не зависит, поэтому пальцы
	// не расходятся веером на рывке и рукоять всегда лежит в них одинаково (замечание автора 15.11).
	const FReferenceSkeleton& Ref = Asset->GetRefSkeleton();
	const TCHAR* Side = bLeft ? TEXT("l") : TEXT("r");
	const int32 Hand = Ref.FindBoneIndex(*FString::Printf(TEXT("hand_%s"), Side));
	static const TCHAR* Names[5] = { TEXT("thumb"), TEXT("index"), TEXT("middle"), TEXT("ring"), TEXT("pinky") };
	FTransform Rest[5][3];
	int32 Bone[5][3];
	FVector Base[5];      // откуда растёт первая фаланга: пясть (у большого пальца — сама кисть)
	auto InHand = [&Ref, Hand](int32 I, FTransform& T)
	{
		T = FTransform::Identity;
		for (; I != INDEX_NONE && I != Hand; I = Ref.GetParentIndex(I))
		{
			T = T * Ref.GetRefBonePose()[I];
		}
		return I == Hand;
	};
	for (int32 F = 0; F < 5; ++F)
	{
		for (int32 J = 0; J < 3; ++J)
		{
			Bone[F][J] = Ref.FindBoneIndex(*FString::Printf(TEXT("%s_0%d_%s"), Names[F], J + 1, Side));
			if (Hand == INDEX_NONE || Bone[F][J] == INDEX_NONE || !InHand(Bone[F][J], Rest[F][J]))
			{
				return false;
			}
		}
		FTransform Parent;
		Base[F] = InHand(Ref.GetParentIndex(Bone[F][0]), Parent) ? Parent.GetLocation() : FVector::ZeroVector;
	}
	const FVector Knuckles = (Rest[4][0].GetLocation() - Rest[1][0].GetLocation()).GetSafeNormal();
	const FVector Fingers = (Rest[2][1].GetLocation() - Rest[2][0].GetLocation()).GetSafeNormal();
	FVector Palm = FVector::CrossProduct(Knuckles, Fingers).GetSafeNormal();
	if (FVector::DotProduct(Palm, Rest[0][1].GetLocation() - Rest[2][0].GetLocation()) < 0.f)
	{
		Palm = -Palm;     // ладонь — с той стороны, где большой палец
	}
	// Ось сгиба четырёх пальцев — линия костяшек, поставленная поперёк первой фаланги пальца. Раньше ось бралась
	// у каждого пальца своя, по излому его фаланг: у почти прямого пальца это шум, оси соседей расходились на 40°,
	// и в кулаке пальцы скрещивались и сминались (замечание автора 15.11, проверено на модели в Blender).
	FVector Axis[5];
	for (int32 F = 1; F < 5; ++F)
	{
		const FVector D1 = (Rest[F][1].GetLocation() - Rest[F][0].GetLocation()).GetSafeNormal();
		FVector A = (Knuckles - D1 * FVector::DotProduct(Knuckles, D1)).GetSafeNormal();
		if (FVector::DotProduct(FVector::CrossProduct(A, D1), Palm) < 0.f)
		{
			A = -A;       // так, чтобы палец шёл к ладони
		}
		Axis[F] = A;
	}
	Axis[0] = FVector::ZeroVector;     // большой палец кладётся отдельно, после остальных (см. ниже)

	FTransform Bent[5][3];
	FVector Nail[5];
	// Согнуть четыре пальца: углы хвата FistCurl, умноженные на K. Возвращает средний радиус дуги пальцев
	// и её середину с осью (середины дуг указательного и мизинца).
	auto Curl = [&](float K, FVector& Center, FVector& Along)
	{
		float Sum = 0.f;
		int32 Count = 0;
		FVector Mid[5];
		for (int32 F = 0; F < 5; ++F)
		{
			const FVector P1 = Rest[F][0].GetLocation(), P2 = Rest[F][1].GetLocation(), P3 = Rest[F][2].GetLocation();
			const FVector D0 = (P1 - Base[F]).GetSafeNormal(), D1 = (P2 - P1).GetSafeNormal(), D2 = (P3 - P2).GetSafeNormal();
			const FVector& A = Axis[F];
			auto Angle = [&A](const FVector& From, const FVector& To)
			{
				return FMath::RadiansToDegrees(FMath::Atan2(FVector::DotProduct(FVector::CrossProduct(From, To), A), FVector::DotProduct(From, To)));
			};
			const float Middle = Angle(D1, D2);
			const float Have[3] = { F > 0 ? Angle(D0, D1) : 0.f, F > 0 ? Middle : 0.f, F > 0 ? 0.6f * Middle : 0.f };
			const float Want[3] = { F > 0 ? FistCurl[0] * K : 0.f, F > 0 ? FistCurl[1] * K : 0.f, F > 0 ? FistCurl[2] * K : 0.f };
			for (int32 J = 0; J < 3; ++J)
			{
				Bent[F][J] = Rest[F][J];
			}
			Nail[F] = P3 + D2 * (P3 - P2).Size() * 0.9f;      // кости кончика нет: продолжение последней фаланги
			for (int32 J = 0; J < 3; ++J)
			{
				const FQuat Turn(A, FMath::DegreesToRadians(FMath::Max(0.f, Want[J] - Have[J])));
				const FVector Pivot = Bent[F][J].GetLocation();
				for (int32 M = J; M < 3; ++M)
				{
					Bent[F][M].SetLocation(Pivot + Turn.RotateVector(Bent[F][M].GetLocation() - Pivot));
					Bent[F][M].SetRotation(Turn * Bent[F][M].GetRotation());
				}
				Nail[F] = Pivot + Turn.RotateVector(Nail[F] - Pivot);
			}
			if (F == 0)
			{
				continue;
			}
			// дуга пальца: окружности через тройки его суставов и кончик
			const FVector Pt[4] = { Bent[F][0].GetLocation(), Bent[F][1].GetLocation(), Bent[F][2].GetLocation(), Nail[F] };
			FVector C = FVector::ZeroVector;
			float R = 0.f;
			int32 N = 0;
			for (int32 T = 0; T < 2; ++T)
			{
				const FVector AB = Pt[T + 1] - Pt[T], AC = Pt[T + 2] - Pt[T];
				const FVector Nrm = FVector::CrossProduct(AB, AC);
				if (Nrm.SizeSquared() < 0.01f)
				{
					continue;
				}
				const FVector O = Pt[T] + (FVector::CrossProduct(Nrm, AB) * AC.SizeSquared() + FVector::CrossProduct(AC, Nrm) * AB.SizeSquared()) / (2.f * Nrm.SizeSquared());
				C += O;
				R += (O - Pt[T]).Size();
				++N;
			}
			Mid[F] = N > 0 ? C / N : (Pt[0] + Pt[1] + Pt[2] + Pt[3]) / 4.f;
			Sum += N > 0 ? R / N : 10.f;
			++Count;
		}
		Center = (Mid[1] + Mid[2] + Mid[3] + Mid[4]) / 4.f;
		Along = (Mid[1] - Mid[4]).GetSafeNormal();
		return Count > 0 ? Sum / Count : 10.f;
	};
	// раскрытие кулака — под рукоять: дуга пальцев по суставам шире рукояти на полтолщины пальца
	constexpr float FingerHalf = 0.8f;
	float Lo = 0.4f, Hi = 1.3f;
	for (int32 I = 0; I < 14; ++I)
	{
		const float K = 0.5f * (Lo + Hi);
		(Curl(K, Out.Center, Out.Along) > HandleRadius + FingerHalf ? Lo : Hi) = K;      // дуга велика — сжать сильнее
	}
	Out.Curl = 0.5f * (Lo + Hi);
	Out.Radius = Curl(Out.Curl, Out.Center, Out.Along);
	// Большой палец ложится на рукоять сверху, вдоль неё: каждая фаланга поворачивается к оси рукояти или от неё,
	// пока её дальний конец не окажется на поверхности (радиус рукояти плюс полтолщины пальца, FistThumb[0]).
	{
		const FVector Center = Out.Center, Along = Out.Along;
		auto Away = [&Center, &Along](const FVector& P)
		{
			const FVector D = P - Center;
			return D - Along * FVector::DotProduct(D, Along);
		};
		const float Surface = HandleRadius + FistThumb[0];
		const int32 Limit = FMath::RoundToInt(FistThumb[1]);
		for (int32 J = 0; J < 3; ++J)
		{
			const FVector Pivot = Bent[0][J].GetLocation();
			const FVector End = J < 2 ? Bent[0][J + 1].GetLocation() : Nail[0];
			const FVector A = FVector::CrossProduct(End - Pivot, Away(End).GetSafeNormal()).GetSafeNormal();
			if (A.IsNearlyZero())
			{
				continue;
			}
			int32 Best = 0;
			float BestScore = TNumericLimits<float>::Max();
			for (int32 Step = -Limit; Step <= Limit; ++Step)
			{
				const FVector Moved = Pivot + FQuat(A, FMath::DegreesToRadians(float(Step))).RotateVector(End - Pivot);
				const float Score = FMath::Abs(Away(Moved).Size() - Surface) + 0.004f * FMath::Abs(Step);
				if (Score < BestScore)
				{
					BestScore = Score;
					Best = Step;
				}
			}
			const FQuat Turn(A, FMath::DegreesToRadians(float(Best)));
			for (int32 M = J; M < 3; ++M)
			{
				Bent[0][M].SetLocation(Pivot + Turn.RotateVector(Bent[0][M].GetLocation() - Pivot));
				Bent[0][M].SetRotation(Turn * Bent[0][M].GetRotation());
			}
			Nail[0] = Pivot + Turn.RotateVector(Nail[0] - Pivot);
		}
	}
	Out.Hand = Hand;
	for (int32 F = 0; F < 5; ++F)
	{
		for (int32 J = 0; J < 3; ++J)
		{
			Out.Bones.Add(Bone[F][J]);
			Out.InHand.Add(Bent[F][J]);
		}
	}
	Out.bValid = true;
	return true;
}

void ARunDirector::ApplyFist()
{
	USkeletalMeshComponent* Mesh = FistMesh.Get();
	if (!Mesh)
	{
		return;
	}
	// кости кадра уже отданы на чтение; правим их на месте — до того, как меш отправит кадр на отрисовку
	TArray<FTransform>& CS = const_cast<TArray<FTransform>&>(Mesh->GetComponentSpaceTransforms());
	// стойки рук — до кулаков: кулак считается уже от поставленной кисти. Направления заданы в осях героя.
	if (const AActor* Hero = Mesh->GetOwner())
	{
		const FTransform& ToWorld = Mesh->GetComponentTransform();
		const FVector F = ToWorld.InverseTransformVectorNoScale(Hero->GetActorForwardVector());
		const FVector R = ToWorld.InverseTransformVectorNoScale(Hero->GetActorRightVector());
		const FVector U = ToWorld.InverseTransformVectorNoScale(FVector::UpVector);
		const int32 Probe = Mesh->GetBoneIndex(TEXT("hand_r"));
		// те же кости второй раз не правим (см. ниже про кулак): стойка уже стоит
		if (!(bArmMarked && CS.IsValidIndex(Probe) && CS[Probe].Equals(ArmMark, 0.f)))
		{
			if (Guard[0] > 0.01f)
			{
				// правая: стойка (локоть у бока, кулак перед грудью, ключ вверх) или замах — по времени с начала удара
				FVector Upper, Fore, Tool;
				float Twist = 0.f, Lean = 0.f;
				const float NowS = Hero->GetWorld() ? Hero->GetWorld()->GetTimeSeconds() : 0.f;
				float Along = (NowS - SwingStart) / FMath::Max(SwingLen, 0.1f);
				float Settle = 0.f;
				if (BounceAt > SwingStart)
				{
					// ключ упёрся: за 0,09 с отлетает назад по своей дуге, потом рука плавно встаёт в стойку
					const float T = NowS - BounceAt;
					const float Back = FMath::Clamp(T / 0.09f, 0.f, 1.f);
					Along = BouncePhase - 0.15f * (1.f - (1.f - Back) * (1.f - Back));
					Settle = FMath::SmoothStep(0.f, 1.f, (T - 0.09f) / 0.26f);
				}
				SwingPose(Along, SwingKind, Upper, Fore, Tool, Twist, Lean);
				if (Settle > 0.f)
				{
					FVector GUpper, GFore, GTool;
					float GTwist = 0.f, GLean = 0.f;
					SwingPose(2.f, SwingKind, GUpper, GFore, GTool, GTwist, GLean);
					auto Mix = [Settle](const FVector& From, const FVector& To)
					{
						return FQuat::Slerp(FQuat::Identity, FQuat::FindBetweenNormals(From.GetSafeNormal(), To.GetSafeNormal()), Settle).RotateVector(From.GetSafeNormal());
					};
					Upper = Mix(Upper, GUpper);
					Fore = Mix(Fore, GFore);
					Tool = Mix(Tool, GTool);
					Twist = FMath::Lerp(Twist, GTwist, Settle);
					Lean = FMath::Lerp(Lean, GLean, Settle);
				}
				TurnTorso(CS, Mesh, Guard[0], Twist, Lean, F, R, U);
				auto Dir = [&F, &R, &U](const FVector& V)
				{
					return (F * V.X + R * V.Y + U * V.Z).GetSafeNormal();
				};
				PoseArm(CS, Mesh, 0, Guard[0], Dir(Upper), Dir(Fore), Dir(Tool));
			}
			if (Guard[1] > 0.01f)
			{
				// левая: предплечье вперёд-вниз, фонарик в кулаке смотрит вперёд; за взглядом камеры идёт, пока хватает кисти
				const FVector Aim = ToWorld.InverseTransformVectorNoScale(LightAim.Vector());
				const float Yaw = FMath::Clamp(FMath::RadiansToDegrees(FMath::Atan2(FVector::DotProduct(Aim, R), FVector::DotProduct(Aim, F))), -55.f, 55.f);
				const float Pitch = FMath::Clamp(FMath::RadiansToDegrees(FMath::Asin(FMath::Clamp(FVector::DotProduct(Aim, U), -1.f, 1.f))), -35.f, 35.f);
				const FVector Ahead = F.RotateAngleAxis(Yaw, U);
				const FVector Side = FVector::CrossProduct(U, Ahead);
				const FVector Fore = (Ahead * 0.76f - U * 0.6f - Side * 0.12f).GetSafeNormal().RotateAngleAxis(-Pitch, Side);
				// сам фонарик смотрит туда же, куда луч: вперёд по взгляду (в пределах поворота кисти)
				PoseArm(CS, Mesh, 1, Guard[1], (-U * 0.97f + Ahead * 0.16f - R * 0.14f).GetSafeNormal(), Fore,
					Ahead.RotateAngleAxis(-Pitch, Side));
			}
			if (CS.IsValidIndex(Probe))
			{
				ArmMark = CS[Probe];
				bArmMarked = Guard[0] > 0.01f || Guard[1] > 0.01f;
			}
		}
	}
	// кулаки: кости пальцев встают на свои места в осях кисти (FistPose), с весом Fist
	for (int32 S = 0; S < 2; ++S)
	{
		const FRunFist& Pose = FistPose[S];
		if (Fist[S] < 0.01f || !Pose.bValid || !CS.IsValidIndex(Pose.Hand))
		{
			continue;
		}
		const FTransform HandNow = CS[Pose.Hand];
		for (int32 I = 0; I < Pose.Bones.Num(); ++I)
		{
			if (CS.IsValidIndex(Pose.Bones[I]))
			{
				FTransform Mixed;
				Mixed.Blend(CS[Pose.Bones[I]], Pose.InHand[I] * HandNow, Fist[S]);
				CS[Pose.Bones[I]] = Mixed;
			}
		}
	}
}

// Проверка рук без игрока: ключ в правой, фонарик в левой; крупные кадры обеих кистей, обычный вид и замах.
void ARunDirector::TickGripTest()
{
	const float Now = GetWorld()->GetTimeSeconds();
	APlayerController* PC = UGameplayStatics::GetPlayerController(this, 0);
	ACharacter* Ch = Cast<ACharacter>(UGameplayStatics::GetPlayerPawn(this, 0));
	if (!PC || !Ch || Now < GripTestAt)
	{
		return;
	}
	auto Shot = [this](const TCHAR* Name)
	{
		const FString Path = FPaths::ProjectSavedDir() / FString::Printf(TEXT("Screenshots/Grip/%s.png"), Name);
		FScreenshotRequest::RequestScreenshot(Path, false, false);
		UE_LOG(LogRun, Display, TEXT("Run: grip shot %s"), *Path);
	};
	auto Close = [&](const TCHAR* Bone, float Right, float Fwd, float Up)
	{
		const FVector Hand = Ch->GetMesh()->GetSocketLocation(Bone);
		const FVector At = Hand + Ch->GetActorRightVector() * Right + Ch->GetActorForwardVector() * Fwd + FVector(0.f, 0.f, Up);
		if (!GripTestCam)
		{
			GripTestCam = GetWorld()->SpawnActor<ACameraActor>();
			GripTestCam->GetCameraComponent()->SetFieldOfView(45.f);
			GripTestCam->GetCameraComponent()->bConstrainAspectRatio = false;
		}
		GripTestCam->SetActorLocationAndRotation(At, (Hand - FVector(0.f, 0.f, 8.f) - At).Rotation());
		PC->SetViewTarget(GripTestCam);
	};
	auto Held = [this]()
	{
		return GetHeldSlot() >= 0 ? ItemName(Pocket[HeldSlot]) : FString(TEXT("nothing"));
	};
	float Wait = 0.45f;
	if (GripTestStep >= 300 && GripTestStep < 320)
	{
		// в движении: герой идёт (300–309) или стоит после рывка (310–319), камера держится спереди-справа от правой кисти
		if (GripTestStep < 310)
		{
			Ch->AddMovementInput(Ch->GetActorForwardVector(), 1.f);
		}
		const FVector Hand = Ch->GetMesh()->GetSocketLocation(TEXT("hand_r"));
		const FVector Eye = Hand + Ch->GetActorRightVector() * 45.f + Ch->GetActorForwardVector() * 95.f + FVector(0.f, 0.f, 30.f);
		GripTestCam->SetActorLocationAndRotation(Eye, (Hand - Eye).Rotation());
		if (Now < GripTestWalkAt)
		{
			return;
		}
		static const TCHAR* Names[] = { TEXT("walk_1"), TEXT("walk_2"), TEXT("walk_3"), TEXT("walk_4") };
		if (GripTestStep < 304)
		{
			Shot(Names[GripTestStep - 300]);
			UE_LOG(LogRun, Display, TEXT("Run: grip walking: fist %.2f %.2f guard %.2f %.2f speed %.0f"), Fist[0], Fist[1], Guard[0], Guard[1], Ch->GetVelocity().Size());
			GripTestWalkAt = Now + 0.35f;
			++GripTestStep;
			return;
		}
		if (GripTestStep == 304)
		{
			OnDodge();
			GripTestStep = 310;
			GripTestWalkAt = Now + 0.18f;
			return;
		}
		if (GripTestStep == 310 || GripTestStep == 311 || GripTestStep == 312)
		{
			Shot(GripTestStep == 310 ? TEXT("dodge_1") : GripTestStep == 311 ? TEXT("dodge_2") : TEXT("dodge_3"));
			UE_LOG(LogRun, Display, TEXT("Run: grip after dodge: fist %.2f %.2f guard %.2f %.2f"), Fist[0], Fist[1], Guard[0], Guard[1]);
			GripTestWalkAt = Now + (GripTestStep == 310 ? 0.3f : 0.6f);
			++GripTestStep;
			return;
		}
		GripTestStep = 9;
		GripTestAt = Now + 0.5f;
		return;
	}
	switch (GripTestStep++)
	{
	case 0:
		// герой уходит от поста капитана на свободное место: камеры у кистей не упираются в мебель
		Ch->SetActorLocation(RoomActor->GetActorLocation() + FVector(-330.f, 0.f, Ch->GetActorLocation().Z - RoomActor->GetActorLocation().Z), false, nullptr, ETeleportType::TeleportPhysics);
		for (const int32 Item : { static_cast<int32>(Weapon), 0 })   // 0 — фонарик, первая вещь каталога
		{
			if (!Pocket.Contains(Item) && !FParse::Param(FCommandLine::Get(), TEXT("RunGripEmpty")))   // -RunGripEmpty: пустые руки
			{
				Pocket.Add(Item);
			}
		}
		HeldSlot = Pocket.IndexOfByKey(Weapon);
		Wait = 1.3f;     // руки встают в стойку
		break;
	case 1: Close(TEXT("hand_r"), 70.f, 25.f, 12.f); break;
	case 2: Shot(TEXT("right_side")); break;
	case 3: Close(TEXT("hand_r"), 25.f, 65.f, 20.f); break;
	case 4: Shot(TEXT("right_front")); break;
	case 5: Close(TEXT("hand_l"), -70.f, 25.f, 12.f); break;
	case 6: Shot(TEXT("left_side")); break;
	case 7: Close(TEXT("hand_l"), -25.f, 65.f, 20.f); break;
	case 8:
		Shot(TEXT("left_front"));
		PC->SetViewTarget(GripTestCam);
		GripTestStep = 300;
		GripTestWalkAt = Now + 0.5f;
		GripTestAt = Now;
		return;
	case 9: PC->SetViewTarget(Ch); break;
	case 10:
	{
		Shot(TEXT("back"));
		Wait = 0.3f;
		break;
	}
	case 11:
	{
		// подмышка правой руки в стойке — сзади-справа: здесь вылезали вершины тела с весами костей предплечья
		const FVector Pit = Ch->GetMesh()->GetSocketLocation(TEXT("upperarm_r")) - FVector(0.f, 0.f, 18.f);
		const FVector At = Pit - Ch->GetActorRightVector() * 60.f - Ch->GetActorForwardVector() * 100.f + FVector(0.f, 0.f, 15.f);
		GripTestCam->SetActorLocationAndRotation(At, (Pit - At).Rotation());
		PC->SetViewTarget(GripTestCam);
		GripTestAt = Now + 0.4f;
		GripTestStep = 100;      // снимки и дальше по порядку
		return;
	}
	case 100: Shot(TEXT("armpit")); GripTestAt = Now + 0.4f; GripTestStep = 102; return;
	case 102:
	{
		const FVector Pit = Ch->GetMesh()->GetSocketLocation(TEXT("upperarm_r")) - FVector(0.f, 0.f, 18.f);
		const FVector At = Pit + Ch->GetActorRightVector() * 45.f - Ch->GetActorForwardVector() * 90.f + FVector(0.f, 0.f, 25.f);
		GripTestCam->SetActorLocationAndRotation(At, (Pit - At).Rotation());
		GripTestAt = Now + 0.4f;
		GripTestStep = 103;
		return;
	}
	case 103: Shot(TEXT("armpit2")); GripTestAt = Now + 0.4f; GripTestStep = 101; return;
	case 101:
	{
		// три удара серии — вид сбоку-спереди: видно дугу ключа
		const FVector Chest = Ch->GetActorLocation() + FVector(0.f, 0.f, 35.f);
		const FVector At = Chest + Ch->GetActorRightVector() * 190.f + Ch->GetActorForwardVector() * 150.f + FVector(0.f, 0.f, 25.f);
		GripTestCam->GetCameraComponent()->SetFieldOfView(60.f);
		GripTestCam->SetActorLocationAndRotation(At, (Chest - At).Rotation());
		PC->SetViewTarget(GripTestCam);
		GripTestAt = Now + 0.45f;
		GripTestStep = 12;
		return;
	}
	// удар длится полсекунды: кадры — замах, середина, удар, проводка
	case 12: OnAttack(); Wait = 0.05f; break;
	case 13: Shot(TEXT("k0_1")); Wait = 0.04f; break;
	case 14: Shot(TEXT("k0_2")); Wait = 0.04f; break;
	case 15: Shot(TEXT("k0_3")); Wait = 0.06f; break;
	case 16: Shot(TEXT("k0_4")); Wait = 0.4f; break;
	case 17: OnAttack(); Wait = 0.05f; break;
	case 18: Shot(TEXT("k1_1")); Wait = 0.04f; break;
	case 19: Shot(TEXT("k1_2")); Wait = 0.04f; break;
	case 20: Shot(TEXT("k1_3")); Wait = 0.06f; break;
	case 21: Shot(TEXT("k1_4")); Wait = 0.4f; break;
	case 22: OnAttack(); Wait = 0.08f; break;
	case 23: Shot(TEXT("k2_1")); Wait = 0.05f; break;
	case 24: Shot(TEXT("k2_2")); Wait = 0.04f; break;
	case 25: Shot(TEXT("k2_3")); Wait = 0.07f; break;
	case 26: Shot(TEXT("k2_4")); Wait = 0.5f; break;
	case 27: PC->SetViewTarget(Ch); Wait = 1.6f; break;
	case 28: OnAttack(); Wait = 0.05f; break;
	case 29: Shot(TEXT("swing_1")); Wait = 0.04f; break;
	case 30: Shot(TEXT("swing_2")); Wait = 0.04f; break;
	case 31: Shot(TEXT("swing_3")); Wait = 0.06f; break;
	case 32: Shot(TEXT("swing_4")); GripTestAt = Now + 1.6f; GripTestStep = 200; return;
	case 200:
	{
		// удар в стену: герой встаёт лицом к стене (не к створке шлюза: та уезжает), в 55 см от неё; вид сбоку
		FHitResult Wall;
		bool bWall = false;
		FCollisionQueryParams Q(FName(TEXT("RunGripWall")), false, Ch);
		const float Yaw0 = Ch->GetActorRotation().Yaw;
		for (const float Turn : { 90.f, -90.f, 180.f, 0.f })
		{
			const FVector Dir = FRotator(0.f, Yaw0 + Turn, 0.f).Vector();
			const FVector From = Ch->GetActorLocation() + FVector(0.f, 0.f, 30.f);
			if (GetWorld()->LineTraceSingleByChannel(Wall, From, From + Dir * 900.f, ECC_WorldStatic, Q)
				&& !GetNameSafe(Wall.GetComponent()).Contains(TEXT("Door")))
			{
				bWall = true;
				Ch->SetActorRotation(FRotator(0.f, Yaw0 + Turn, 0.f));
				PC->SetControlRotation(FRotator(-10.f, Yaw0 + Turn, 0.f));
				Ch->SetActorLocation(Ch->GetActorLocation() + Dir * (Wall.Distance - 55.f), false, nullptr, ETeleportType::TeleportPhysics);
				break;
			}
		}
		UE_LOG(LogRun, Display, TEXT("Run: grip wall %s at %.0f cm"), bWall ? *GetNameSafe(Wall.GetComponent()) : TEXT("none"), bWall ? Wall.Distance : -1.f);
		const FVector Chest = Ch->GetActorLocation() + FVector(0.f, 0.f, 35.f) + Ch->GetActorForwardVector() * 35.f;
		// камера — с той стороны, где до стены дальше
		FHitResult Side;
		const FVector Eye = Ch->GetActorLocation() + FVector(0.f, 0.f, 40.f);
		const bool bRightTight = GetWorld()->LineTraceSingleByChannel(Side, Eye, Eye + Ch->GetActorRightVector() * 230.f, ECC_WorldStatic, Q);
		const FVector At = Chest + Ch->GetActorRightVector() * (bRightTight ? -190.f : 190.f) - Ch->GetActorForwardVector() * 50.f + FVector(0.f, 0.f, 20.f);
		GripTestCam->GetCameraComponent()->SetFieldOfView(55.f);
		GripTestCam->SetActorLocationAndRotation(At, (Chest - At).Rotation());
		PC->SetViewTarget(GripTestCam);
		GripTestAt = Now + 0.8f;
		GripTestStep = 201;
		return;
	}
	case 201: OnAttack(); GripTestAt = Now + 0.09f; GripTestStep = 202; return;
	case 202: Shot(TEXT("wall_1")); GripTestAt = Now + 0.07f; GripTestStep = 203; return;
	case 203: Shot(TEXT("wall_2")); GripTestAt = Now + 0.05f; GripTestStep = 204; return;
	case 204: Shot(TEXT("wall_3")); GripTestAt = Now + 0.12f; GripTestStep = 205; return;
	case 205: Shot(TEXT("wall_4")); GripTestAt = Now + 1.2f; GripTestStep = 33; return;
	case 33:
	{
		// выбор: активная вещь листается колесом по занятым слотам; удар её не меняет; фонарик светит сам по себе
		FString Line = FString::Printf(TEXT("active %s, right hand %s, light %d; wheel:"), *Held(),
			RightItem != TNumericLimits<int32>::Min() ? *ItemName(RightItem) : TEXT("nothing"), bFlashlightLit ? 1 : 0);
		for (int32 I = 0; I < 3; ++I)
		{
			OnWheelDown();
			Line += TEXT(" ") + Held();
		}
		OnAttack();
		Line += TEXT("; after a hit: ") + Held();
		OnToggleLight();
		UE_LOG(LogRun, Display, TEXT("Run: grip %s (pocket %d)"), *Line, Pocket.Num());
		Wait = 0.3f;
		break;
	}
	case 34: UE_LOG(LogRun, Display, TEXT("Run: grip light after [V]: %d"), bFlashlightLit ? 1 : 0); break;
	default:
		UE_LOG(LogRun, Display, TEXT("Run: grip test done"));
		GripTestStep = -1;
		FPlatformMisc::RequestExit(false);
		return;
	}
	GripTestAt = Now + Wait;
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
	if (bMenuOpen)
	{
		SetMenuOpen(false);   // Esc из меню на Tab закрывает меню, а не открывает паузу поверх
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

// Удар разводным ключом: достаёт всех противников перед игроком на расстоянии вытянутой руки.
void ARunDirector::OnAttack()
{
	const float Now = GetWorld()->GetTimeSeconds();
	const APawn* Pawn = UGameplayStatics::GetPlayerPawn(this, 0);
	if (Phase != ERunPhase::Playing || !Pawn)
	{
		return;
	}
	if (!HasWeapon())
	{
		if (EnemyActors.Num() > 0 && Now >= NextAttackAt)
		{
			NextAttackAt = Now + 1.f;
			RunAudio::Play(this, TEXT("UiDeny"));
			Say(TEXT("You have nothing to fight with."), 2.f);
		}
		return;
	}
	if (Now < AttackBusyUntil)
	{
		bAttackQueued = Now > AttackBusyUntil - 0.35f;   // нажатие под конец замаха — следующий удар серии
		return;
	}
	StartSwing();
}

// Замах: анимация удара манекена (три разных по кругу — серия), ключ в руке, на время замаха герой почти стоит.
void ARunDirector::StartSwing()
{
	const float Now = GetWorld()->GetTimeSeconds();
	ACharacter* Ch = Cast<ACharacter>(UGameplayStatics::GetPlayerPawn(this, 0));
	if (!Ch)
	{
		return;
	}
	if (Now > ComboResetAt)
	{
		ComboStep = 0;
	}
	bCrouchToggle = false;   // бьют стоя
	SetInspecting(false);    // оружие всегда в правой руке: удар не меняет активную вещь
	// замах — свой, по ключевым позам (SwingPose): клипы удара шаблона бьют кулаком, а не ключом
	SwingKind = ComboStep % 3;
	SwingLen = SwingKind == 2 ? 0.62f : 0.5f;     // третий удар серии — тяжёлый, сверху вниз
	SwingStart = Now;
	BounceAt = -100.f;
	const float Len = SwingLen;
	AttackHitTime = Now + Len * 0.44f;            // губки доходят до цели чуть раньше половины замаха
	AttackBusyUntil = Now + Len * 0.8f;
	ComboResetAt = AttackBusyUntil + 0.7f;
	NextAttackAt = AttackBusyUntil;
	++ComboStep;
	bAttackQueued = false;
	RunAudio::Play(this, TEXT("WrenchSwing"), 0.8f, FMath::FRandRange(0.92f, 1.08f));
}

// Есть ли сейчас противник, по которому придётся удар (те же условия, что в ResolveSwing): если есть, ключ не
// отскакивает от стены рядом — удар доходит до него.
bool ARunDirector::EnemyInReach() const
{
	const APawn* Pawn = UGameplayStatics::GetPlayerPawn(this, 0);
	if (!Pawn)
	{
		return false;
	}
	const FVector P = Pawn->GetActorLocation();
	const FVector Facing = Pawn->GetActorForwardVector().GetSafeNormal2D();
	const FVector Looking = FRotator(0.f, Pawn->GetControlRotation().Yaw, 0.f).Vector();
	for (const ARunEnemy* Actor : EnemyActors)
	{
		if (!Actor)
		{
			continue;
		}
		const FVector To(Actor->GetFloorPos().X - P.X, Actor->GetFloorPos().Y - P.Y, 0.f);
		const float Dist = To.Size2D();
		const FVector N = To.GetSafeNormal2D();
		const bool bAhead = Dist < 75.f || FVector::DotProduct(N, Facing) > 0.2f || FVector::DotProduct(N, Looking) > 0.2f;
		if (Dist <= AttackReach + Actor->GetRadius() && bAhead)
		{
			return true;
		}
	}
	return false;
}

// Пока идёт сам удар (от замаха до конца проводки), дуга ключа просчитывается на кадр вперёд: где на ней ключ
// (от запястья до губок) впервые упрётся в стену, створку или мебель. Упрётся до следующего кадра — замах обрывается
// на этой доле, ключ останавливается у самой поверхности и отлетает назад.
void ARunDirector::TickSwingContact()
{
	const float Now = GetWorld()->GetTimeSeconds();
	const float Along = (Now - SwingStart) / FMath::Max(SwingLen, 0.1f);
	const ACharacter* Ch = Cast<ACharacter>(UGameplayStatics::GetPlayerPawn(this, 0));
	if (!Ch || !Ch->GetMesh() || !GripMesh || !GripMesh->IsVisible() || !IsWeapon(RightItem) || BounceAt > SwingStart || Along > 0.63f
		|| Phase != ERunPhase::Playing)
	{
		return;
	}
	const USkeletalMeshComponent* Mesh = Ch->GetMesh();
	const FVector Shoulder = Mesh->GetSocketLocation(TEXT("upperarm_r")), Elbow = Mesh->GetSocketLocation(TEXT("lowerarm_r")),
		Wrist = Mesh->GetSocketLocation(TEXT("hand_r"));
	const float UpperLen = FVector::Dist(Shoulder, Elbow), ForeLen = FVector::Dist(Elbow, Wrist);
	const FVector F = Ch->GetActorForwardVector(), R = Ch->GetActorRightVector(), U = FVector::UpVector;
	FCollisionQueryParams World(FName(TEXT("RunSwingContact")), false, Ch);
	for (const ARunEnemy* Actor : EnemyActors)
	{
		World.AddIgnoredActor(Actor);
	}
	// до какой доли замах дойдёт к следующему кадру (с запасом в полкадра)
	const float Ahead = FMath::Min(0.63f, Along + 1.5f * GetWorld()->GetDeltaSeconds() / FMath::Max(SwingLen, 0.1f));
	for (float At = FMath::Max(Along, 0.31f); At <= Ahead; At += 0.015f)
	{
		FVector Upper, Fore, Tool;
		float Twist = 0.f, Lean = 0.f;
		SwingPose(At, SwingKind, Upper, Fore, Tool, Twist, Lean);
		auto Dir = [&F, &R, &U](const FVector& V)
		{
			return (F * V.X + R * V.Y + U * V.Z).GetSafeNormal();
		};
		// запястье — по длинам плеча и предплечья от нынешнего плечевого сустава; кулак в 8 см дальше, губки в 37 см от кулака
		const FVector ToolDir = Dir(Tool), ForeDir = Dir(Fore);
		const FVector Hand = Shoulder + Dir(Upper) * UpperLen + ForeDir * ForeLen;
		const FVector Grip = Hand + (ForeDir - ToolDir * FVector::DotProduct(ForeDir, ToolDir)).GetSafeNormal() * 8.f;
		const FVector Jaws = Grip + ToolDir * 37.f;
		FHitResult Hit;
		if (!GetWorld()->LineTraceSingleByChannel(Hit, Hand, Jaws, ECC_WorldStatic, World))
		{
			continue;
		}
		if (EnemyInReach())
		{
			return;      // рядом противник: удар доходит до него, а не отскакивает от стены
		}
		BounceAt = Now;
		BouncePhase = FMath::Max(At - 0.015f, 0.28f);
		AttackHitTime = -1.f;                 // удар оборван: до противника он уже не дойдёт
		AttackBusyUntil = Now + 0.3f;
		ComboResetAt = AttackBusyUntil + 0.7f;
		NextAttackAt = AttackBusyUntil;
		bAttackQueued = false;
		RunAudio::Play(this, TEXT("WrenchHit"));
		UE_LOG(LogRun, Display, TEXT("Run: attack hit object %s part %s, bounce at %.2f of the swing"), *GetNameSafe(Hit.GetActor()),
			*GetNameSafe(Hit.GetComponent()), BouncePhase);
		return;
	}
}

// Момент удара: кто в этот миг перед героем и в пределах досягаемости — получает.
void ARunDirector::ResolveSwing()
{
	const float Now = GetWorld()->GetTimeSeconds();
	const APawn* Pawn = UGameplayStatics::GetPlayerPawn(this, 0);
	if (Phase != ERunPhase::Playing || !Pawn)
	{
		return;
	}
	int32 Hits = 0;
	bool bFlesh = false, bMetal = false;   // во что попали: в живое (человек, крыса) или в металл робота
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
		++Hits;
		(E->Kind == ThreatRobot ? bMetal : bFlesh) = true;
		UE_LOG(LogRun, Display, TEXT("Run: attack hit id=%d kind=%s health=%d"), E->Id, ARunEnemy::DisplayName(E->Kind), E->Health);
		if (E->Health <= 0)
		{
			Say(E->Kind == ThreatHuman ? TEXT("The other you goes down and does not get up.")
				: E->Kind == ThreatRobot ? TEXT("The robot sparks and goes still.") : TEXT("One rat less."), 3.f);
			const int32 Id = E->Id;
			Enemies.RemoveAll([Id](const FRunEnemyState& S) { return S.Id == Id; });
			EnemyActors.Remove(Actor);
			TestKillAt = Actor->GetFloorPos();
			Actor->Die();   // анимация смерти; тело остаётся лежать и исчезает само
		}
		else
		{
			Actor->ShowHealth(E->Health);
			Actor->Knock(P, AttackStun);
		}
	}
	// У удара три звука (автор, 15.11): по живому, по металлу робота и по предмету обстановки (прежний WrenchHit;
	// его играет TickSwingContact, когда ключ упёрся в стену или мебель).
	if (bFlesh)
	{
		RunAudio::Play(this, TEXT("WrenchHitFlesh"));
	}
	if (bMetal)
	{
		RunAudio::Play(this, TEXT("WrenchHitMetal"));
	}
	if (Hits > 0)
	{
		UE_LOG(LogRun, Display, TEXT("Run: attack sound flesh=%d metal=%d"), bFlesh ? 1 : 0, bMetal ? 1 : 0);
	}
}

bool ARunDirector::TestStepWasDodge()
{
	// шаг 123 самопроверки только ждёт; рывок делается здесь, перед самым кадром, чтобы снять его середину
	if (bSelfTest && TestStep > 0 && GetWorld()->GetTimeSeconds() >= DodgeReadyAt && FParse::Param(FCommandLine::Get(), TEXT("RunShots")) && ComboStep > 0 && DodgeUntil < 0.f)
	{
		OnDodge();
	}
	return GetWorld()->GetTimeSeconds() < DodgeUntil;
}

// Рывок-уклонение: короткий бросок туда, куда идёт герой (стоя на месте — назад), удары в это время не проходят.
void ARunDirector::OnDodge()
{
	const float Now = GetWorld()->GetTimeSeconds();
	ACharacter* Ch = Cast<ACharacter>(UGameplayStatics::GetPlayerPawn(this, 0));
	if (Phase != ERunPhase::Playing || !Ch || Now < DodgeReadyAt || !Ch->GetCharacterMovement()->IsMovingOnGround())
	{
		return;
	}
	FVector Want = Ch->GetLastMovementInputVector();
	Want.Z = 0.f;
	DodgeDir = Want.IsNearlyZero(0.05f) ? -Ch->GetActorForwardVector().GetSafeNormal2D() : Want.GetSafeNormal2D();
	DodgeUntil = Now + DodgeSeconds;
	DodgeSafeUntil = Now + DodgeSafeSeconds;
	DodgeReadyAt = Now + DodgeCooldown;
	AttackHitTime = -1.f;        // рывок срывает свой же замах
	bAttackQueued = false;
	AttackBusyUntil = Now;
	if (UAnimSequenceBase* Clip = LoadObject<UAnimSequenceBase>(nullptr, TEXT("/Game/Characters/Mannequins/Anims/Unarmed/Jump/MM_Dash.MM_Dash"), nullptr, LOAD_NoWarn | LOAD_Quiet))
	{
		if (UAnimInstance* Anim = Ch->GetMesh() ? Ch->GetMesh()->GetAnimInstance() : nullptr)
		{
			Anim->PlaySlotAnimationAsDynamicMontage(Clip, TEXT("DefaultSlot"), 0.06f, 0.15f, FMath::Max(1.f, Clip->GetPlayLength() / (DodgeSeconds + 0.12f)));
		}
	}
	RunAudio::Play(this, TEXT("Dodge"), 0.7f);
	UE_LOG(LogRun, Display, TEXT("Run: dodge"));
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
	if (bKnockback)
	{
		RunAudio::Play(this, TEXT("Hurt"));   // у дыма, спор и вакуума свои звуки (ARunThreat)
	}
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
		if (ACharacter* Fallen = bNoDeathAnim ? nullptr : Cast<ACharacter>(UGameplayStatics::GetPlayerPawn(this, 0)))
		{
			// герой падает: вперёд, если ударили в спину, иначе навзничь; последний кадр остаётся
			const bool bFromBehind = FVector::DotProduct((From - Fallen->GetActorLocation()).GetSafeNormal2D(), Fallen->GetActorForwardVector()) < -0.2f;
			if (UAnimSequenceBase* Clip = LoadObject<UAnimSequenceBase>(nullptr, bFromBehind
				? TEXT("/Game/Characters/Mannequins/Anims/Death/MM_Death_Back_01.MM_Death_Back_01")
				: TEXT("/Game/Characters/Mannequins/Anims/Death/MM_Death_Front_01.MM_Death_Front_01"), nullptr, LOAD_NoWarn | LOAD_Quiet))
			{
				Fallen->GetMesh()->SetAnimationMode(EAnimationMode::AnimationSingleNode);
				Fallen->GetMesh()->PlayAnimation(Clip, false);
			}
			Fallen->GetCharacterMovement()->DisableMovement();
		}
		RunAudio::Play(this, TEXT("Death"));
		RunAudio::Play(this, TEXT("DeathSting"), 0.8f);
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
		// модель шлема (автор, Tripo, 15.11): 37 см, привязка — середина; нет её — прозрачный шар
		if (UStaticMesh* Model = LoadObject<UStaticMesh>(nullptr, TEXT("/Game/Environment/Common/SpaceSuitHelmet/SM_SpaceSuitHelmet.SM_SpaceSuitHelmet"),
			nullptr, LOAD_NoWarn | LOAD_Quiet))
		{
			Helmet->SetStaticMesh(Model);
			Helmet->SetCastShadow(true);
		}
		else
		{
			Helmet->SetStaticMesh(LoadObject<UStaticMesh>(nullptr, TEXT("/Engine/BasicShapes/Sphere.Sphere")));
			UMaterialInterface* Glass = LoadObject<UMaterialInterface>(nullptr, TEXT("/Game/FX/Anomalies/MI_TimeBubble.MI_TimeBubble"),
				nullptr, LOAD_NoWarn | LOAD_Quiet);
			Helmet->SetMaterial(0, Glass ? Glass : LoadObject<UMaterialInterface>(nullptr, TEXT("/Game/Game/Materials/MI_Gray_Glow.MI_Gray_Glow")));
			Helmet->SetWorldScale3D(FVector(0.36f));
		}
	}
	Helmet->SetVisibility(true);
	RunAudio::Play(this, TEXT("SuitOn"));
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
	if (!bSuitOn || Phase != ERunPhase::Playing || bBusy || !RoomActor || bMenuPause)
	{
		return;
	}
	if (IsInVacuum())
	{
		RunAudio::Play(this, TEXT("UiDeny"));
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
	RunAudio::Play(this, TEXT("SuitOff"));
	Say(TEXT("You step out of the space suit and leave it standing."), 3.f);
	UE_LOG(LogRun, Display, TEXT("Run: suit off"));
}

void ARunDirector::KillPlayer(const FString& Text, const FVector& From)
{
	InvulnerableUntil = 0.f;
	bNoDeathAnim = true;
	HurtPlayer(Text, From, Health + 1.f, false);
	bNoDeathAnim = false;
}

bool ARunDirector::IsPlayerCrouched() const
{
	const ACharacter* Ch = Cast<ACharacter>(UGameplayStatics::GetPlayerPawn(this, 0));
	return Ch && Ch->bIsCrouched;
}

// Присед (решение автора 15.11, для дыма). Капсулу и камеру опускает движение персонажа движка. Анимации приседа
// (IdlePath и WalkPath ниже) взяты из плагина движка MoverExamples и перенесены на скелет проекта
// (tools/ue/import_crouch.py). Позы у них разные: на месте глубокий присед (таз на 42 см), в шаге полуприсед (75 см).
// Поэтому они играют монтажом в слоте DefaultSlot блюпринта анимации шаблона (ABP_Unarmed), а не заменяют его:
// у монтажа есть время смешивания, и вход в присед, выход из него и смена «на месте ↔ шаг» идут плавным переходом,
// а не скачком. Если ассетов нет — герой просто сжимается по высоте, чтобы было видно, что голова ниже дыма.
void ARunDirector::UpdateCrouch(ACharacter* Ch, const APlayerController* PC)
{
	static const TCHAR* const IdlePath = TEXT("/Game/Characters/Mannequins/Anims/Crouch/MM_Crouch_Idle.MM_Crouch_Idle");
	static const TCHAR* const WalkPath = TEXT("/Game/Characters/Mannequins/Anims/Crouch/MM_Crouch_Walk.MM_Crouch_Walk");
	static const FName CrouchSlot(TEXT("DefaultSlot"));
	constexpr float CrouchBlend = 0.3f;   // с, переход между позами
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
	UAnimInstance* Anim = Mesh->GetAnimInstance();
	UAnimSequenceBase* Idle = LoadObject<UAnimSequenceBase>(nullptr, IdlePath, nullptr, LOAD_NoWarn | LOAD_Quiet);
	UAnimSequenceBase* Walk = LoadObject<UAnimSequenceBase>(nullptr, WalkPath, nullptr, LOAD_NoWarn | LOAD_Quiet);
	if (Ch->bIsCrouched != bCrouchPose)
	{
		bCrouchPose = Ch->bIsCrouched;
		if (bCrouchPose)
		{
			MeshScaleStanding = Mesh->GetRelativeScale3D();
			if (!Idle || !Anim)
			{
				Mesh->SetRelativeScale3D(FVector(MeshScaleStanding.X, MeshScaleStanding.Y, MeshScaleStanding.Z * 0.62f));
			}
		}
		else
		{
			Mesh->SetRelativeScale3D(MeshScaleStanding);
			if (Anim && CrouchMontage.IsValid())
			{
				Anim->Montage_Stop(CrouchBlend, CrouchMontage.Get());   // плавно обратно в походку шаблона
			}
			CrouchMontage.Reset();
			CrouchClip.Reset();
		}
	}
	if (bCrouchPose && Idle && Anim)
	{
		const float Speed = Ch->GetVelocity().Size2D();
		// порог с запасом в обе стороны, чтобы на грани скорости клипы не перещёлкивались туда-сюда
		const bool bWalking = Walk && (CrouchClip.Get() == Walk ? Speed > 10.f : Speed > 30.f);
		UAnimSequenceBase* Want = bWalking ? Walk : Idle;
		if (CrouchClip.Get() != Want || !CrouchMontage.IsValid() || !Anim->Montage_IsPlaying(CrouchMontage.Get()))
		{
			// новый монтаж в том же слоте сам уводит прежний за CrouchBlend — получается перекрёстный переход;
			// повторов с запасом, чтобы клип не кончался
			CrouchMontage = Anim->PlaySlotAnimationAsDynamicMontage(Want, CrouchSlot, CrouchBlend, CrouchBlend, 1.f, 100000);
			CrouchClip = Want;
		}
		if (Want == Walk && CrouchMontage.IsValid())
		{
			// в MM_Crouch_Walk корень проходит 540 см за цикл 1,8 с — родная скорость 300 см/с; вприсядку герой идёт
			// 150, значит темп 0,5, иначе ноги скользят
			Anim->Montage_SetPlayRate(CrouchMontage.Get(), FMath::Clamp(Speed / 300.f, 0.25f, 1.6f));
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
	RunAudio::Play(this, TEXT("AirlockScan"));
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
		RunAudio::Play(this, TEXT("AirlockRefused"));
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
	RunAudio::Play(this, TEXT("AirlockShift"));
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
			RunAudio::Play(this, TEXT("EnginesOnline"));
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
		RunAudio::Play(this, TEXT("Win"), 0.8f);
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
			: TEXT("Rats. Huge ones. They leap - do not stand still."), 6.f);
		if (!bTipDodge)
		{
			bTipDodge = true;
			ShowTip(TEXT("[Space] dodge - it strikes where you stood"), 7.f);
		}
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
	RunAudio::Play(this, TEXT("PageTurn"));
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
		RunAudio::Play(this, TEXT("NotePaper"));
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
			RunAudio::Play(this, TEXT("UiDeny"));
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
		RunAudio::Play(this, TEXT("ItemPickup"));
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
			ShowTip(TEXT("Medkit: take it in hand with the mouse wheel or [1]-[4], [LMB] to use"), 7.f);
		}
		else if (Pocket.Num() >= PocketSlots && !bTipDrop)
		{
			bTipDrop = true;
			ShowTip(TEXT("Pocket is full. Mouse wheel or [1]-[4] takes an item in hand, [G] drops it"), 7.f);
		}
		else if (IsFlashlight(Item) && !bTipLight)
		{
			bTipLight = true;
			ShowTip(TEXT("The flashlight goes to your left hand. [V] switches it on and off"), 7.f);
		}
		else if (Pocket.Num() >= 2 && !bTipWheel)
		{
			bTipWheel = true;
			ShowTip(TEXT("[Mouse wheel] or [1]-[4] switches the active item"), 7.f);
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
	RunAudio::Play(this, TEXT("ItemDrop"));
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
	if (Phase != ERunPhase::Playing || !Pocket.IsValidIndex(Slot) || bMenuPause)
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
	if (Phase != ERunPhase::Playing || Pocket.Num() == 0 || bMenuPause)
	{
		return;
	}
	// по кругу через занятые слоты: каждый щелчок колеса — следующая вещь. Убрать вещь из руки — её цифра ещё раз
	const int32 N = Pocket.Num();
	const int32 From = GetHeldSlot() < 0 ? (Step > 0 ? -1 : N) : HeldSlot;
	HeldSlot = ((From + Step) % N + N) % N;
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
	if (bMenuPause)
	{
		return;
	}
	if (GetHeldSlot() < 0)
	{
		if (Phase == ERunPhase::Playing && Pocket.Num() > 0)
		{
			Say(TEXT("Your hands are empty. Mouse wheel or [1]-[4] takes an item in hand."), 3.f);
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
	RunAudio::Play(this, TEXT("MedkitUse"));
	RemoveFromPocket(Slot);
	UE_LOG(LogRun, Display, TEXT("Run: medkit used health=%.0f -> %.0f"), Before, Health);
	Say(TEXT("You patch yourself up. It helps."), 3.f);
}

// Правая кнопка: рассмотреть вещь в руке или убрать её от глаз. Блокнот при этом раскрывается для чтения.
void ARunDirector::OnInspect()
{
	if (Phase != ERunPhase::Playing || bMenuPause)
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
			Say(TEXT("Your hands are empty. Mouse wheel or [1]-[4] takes an item in hand."), 3.f);
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
		RunAudio::Play(this, TEXT("PageTurn"));
	}
}

// Tab — меню (решение автора 15.11): блокнот с закладками записок, карман, скафандр. Время в меню стоит
// (решение автора 15.11, вечер; раньше шло).
void ARunDirector::OnToggleJournal()
{
	if (Phase == ERunPhase::Playing && !bMenuPause)
	{
		SetMenuOpen(!bMenuOpen);
	}
}

void ARunDirector::SetMenuBlend(float Alpha)
{
	Alpha = FMath::Clamp(Alpha, 0.f, 1.f);
	if (!Post || Alpha == MenuBlend)
	{
		return;
	}
	MenuBlend = Alpha;
	// фон под меню: на 1,6 ступени темнее, почти без цвета, с виньеткой и размытием — текст блокнота не спорит с комнатой.
	// Размытие — глубина резкости: фокус у самой камеры, широкий «сенсор» и открытая диафрагма, всё дальше расплывается
	const bool bOn = Alpha > 0.f;
	FPostProcessSettings& P = Post->Settings;
	P.AutoExposureBias = ExposureBias - 1.6f * Alpha;
	P.bOverride_ColorSaturation = bOn;
	P.ColorSaturation = FVector4(1.f, 1.f, 1.f, FMath::Lerp(1.f, 0.2f, Alpha));
	P.bOverride_VignetteIntensity = bOn;
	P.VignetteIntensity = FMath::Lerp(0.4f, 1.f, Alpha);
	P.bOverride_DepthOfFieldFocalDistance = bOn;
	P.DepthOfFieldFocalDistance = 15.f;
	P.bOverride_DepthOfFieldSensorWidth = bOn;
	P.DepthOfFieldSensorWidth = 150.f;
	P.bOverride_DepthOfFieldFstop = bOn;
	P.DepthOfFieldFstop = 0.7f / FMath::Max(Alpha, 0.02f);   // размытие растёт с Alpha
	P.bOverride_DepthOfFieldMinFstop = bOn;
	P.DepthOfFieldMinFstop = 0.7f;
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
	if (bOpen != bMenuOpen)
	{
		RunAudio::Play(this, TEXT("NotebookOpen"));   // звук интерфейса: на паузе слышен
		// время в меню стоит. Не в самопроверке: её шаги идут по времени мира и встали бы вместе с ним
		if (!bSelfTest)
		{
			UGameplayStatics::SetGamePaused(this, bOpen);
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
	if (HandPivot && Ch)
	{
		const bool bAlive = !Ch->IsHidden() && Phase == ERunPhase::Playing;
		// правая рука — оружие: активная вещь, если она оружие, иначе последнее выбранное, иначе любое из кармана
		if (GetHeldSlot() >= 0 && IsWeapon(Held))
		{
			RightItem = Held;
		}
		if (!Pocket.Contains(RightItem))
		{
			const int32 Slot = Pocket.IndexOfByPredicate([](int32 Item) { return IsWeapon(Item); });
			RightItem = Slot != INDEX_NONE ? Pocket[Slot] : TNumericLimits<int32>::Min();
		}
		const int32 LeftItem = FlashlightItem();
		// вещь на осмотре — перед глазами, в руке её в это время нет
		const bool bRight = bAlive && RightItem != TNumericLimits<int32>::Min() && !(IsInspecting() && Held == RightItem);
		const bool bLeft = bAlive && LeftItem != TNumericLimits<int32>::Min() && !(IsInspecting() && Held == LeftItem);
		auto Show = [this, Ch](UStaticMeshComponent* Grip, bool bOn, int32 Item, bool bLeftHand, int32& Shown)
		{
			if (!Grip)
			{
				return;
			}
			if (bOn && Item != Shown)
			{
				Grip->EmptyOverrideMaterials();
				Grip->SetStaticMesh(ARunItem::FindModel(ItemName(Item)));
				// рукоять ключа — 4,1 × 2,5 см, фонарика — круглая, 3,9 см: кулак раскрыт под неё
				BuildFist(Ch->GetMesh(), bLeftHand, IsFlashlight(Item) ? 1.95f : 1.85f, FistPose[bLeftHand ? 1 : 0]);
				FTransform At;
				if (GripInHand(Item, bLeftHand, Ch->GetMesh(), At))
				{
					Grip->SetRelativeTransform(At);
					// куда смотрит рабочий конец в осях кисти: у ключа губки в начале меша, у фонарика линза в конце
					ToolAxis[bLeftHand ? 1 : 0] = At.GetRotation().GetAxisZ() * (IsFlashlight(Item) ? 1.f : -1.f);
				}
				Shown = Item;
			}
			Grip->SetVisibility(bOn && Grip->GetStaticMesh() != nullptr);
		};
		Show(GripMesh, bRight, RightItem, false, ShownGripItem);
		Show(GripMeshLeft, bLeft, LeftItem, true, ShownLeftItem);
		Fist[0] = FMath::FInterpTo(Fist[0], bRight ? 1.f : 0.f, DeltaSeconds, 12.f);
		Fist[1] = FMath::FInterpTo(Fist[1], bLeft ? 1.f : 0.f, DeltaSeconds, 12.f);
		// стойки: правая отпускает руку анимации на время рывка, левая поднята, пока фонарик светит
		const float NowT = GetWorld()->GetTimeSeconds();
		const bool bFree = NowT < DodgeUntil;        // на рывке руку ведёт клип рывка; удар ведёт сама стойка (SwingPose)
		Guard[0] = FMath::FInterpTo(Guard[0], bRight && !bFree ? 1.f : 0.f, DeltaSeconds, bFree ? 16.f : 7.f);
		Guard[1] = FMath::FInterpTo(Guard[1], bLeft && bLightOn && NowT >= DodgeUntil ? 1.f : 0.f, DeltaSeconds, 7.f);
		if (const APlayerController* PC = UGameplayStatics::GetPlayerController(this, 0))
		{
			LightAim = PC->GetControlRotation();
		}
		HandPivot->SetWorldRotation(FRotator(0.f, Ch->GetActorRotation().Yaw, 0.f));
		if (Flashlight)
		{
			const bool bLit = bLeft && bLightOn;
			if (bLit != bFlashlightLit)
			{
				bFlashlightLit = bLit;
				RunAudio::Play(this, TEXT("FlashlightClick"));
			}
			Flashlight->SetVisibility(bLit);
			if (const APlayerController* PC = bLit ? UGameplayStatics::GetPlayerController(this, 0) : nullptr)
			{
				// луч идёт от левой кисти вдоль взгляда камеры; чуть вынесен вперёд, чтобы герой не затенял его бедром
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

// Музыка, фон комнаты, шаги, сердце. Вызывается каждый кадр, пока у игрока есть персонаж.
void ARunDirector::UpdateAudio(float DeltaSeconds, ACharacter* Ch)
{
	// музыка: спокойный трек идёт весь забег; боевой входит плавно, когда на игрока вышел противник
	// (в комнате живой враг или кто-то идёт следом), и уходит через несколько секунд после боя
	if (!MusicCalm)
	{
		MusicCalm = RunAudio::Loop(this, TEXT("RunBed"), MusicVolume, 4.f);
	}
	bool bHostile = GetFollowers() > 0;
	for (const ARunEnemy* E : EnemyActors)
	{
		bHostile |= E && E->IsHostile();
	}
	CombatHold = Phase == ERunPhase::Playing && bHostile ? 5.f : CombatHold - DeltaSeconds;
	const bool bWant = CombatHold > 0.f && Phase == ERunPhase::Playing;
	if (bWant != bCombatMusic)
	{
		bCombatMusic = bWant;
		if (bWant)
		{
			if (MusicCombat)
			{
				MusicCombat->FadeIn(1.2f, CombatMusicVolume, 0.f);
			}
			else
			{
				MusicCombat = RunAudio::Loop(this, TEXT("Danger"), CombatMusicVolume, 1.2f);
			}
		}
		else if (MusicCombat)
		{
			MusicCombat->FadeOut(4.f, 0.f);
		}
		if (MusicCalm)
		{
			// спокойный трек под боем не выключается, а уходит под него: возврат без шва
			MusicCalm->AdjustVolume(bWant ? 1.5f : 4.f, bWant ? MusicVolume * 0.12f : MusicVolume);
		}
		UE_LOG(LogRun, Display, TEXT("Run: music %s"), bWant ? TEXT("combat") : TEXT("calm"));
	}
	if (Phase != ERunPhase::Playing && !bEndMusic)
	{
		bEndMusic = true;   // смерть или победа: музыка уходит вниз, слышны звук события и тишина
		if (MusicCalm)
		{
			MusicCalm->AdjustVolume(3.f, MusicVolume * 0.35f);
		}
	}

	// фон комнаты: гул корабля или гул на аварийном питании — по свету комнаты
	const FName Tone = RoomActor && RoomActor->IsEmergency() ? FName(TEXT("EmergencyHum")) : FName(TEXT("ShipHum"));
	if (Tone != RoomToneName && RunAudio::Find(Tone))
	{
		RoomToneName = Tone;
		if (RoomTone)
		{
			RoomTone->FadeOut(1.5f, 0.f);
		}
		RoomTone = RunAudio::Loop(this, Tone, 0.5f, 1.5f);
	}

	// сердце: здоровья на одно-два попадания
	const bool bLow = Phase == ERunPhase::Playing && Health > 0.f && Health <= 25.f;
	if (bLow && !Heartbeat)
	{
		Heartbeat = RunAudio::Loop(this, TEXT("Heartbeat"), 0.8f, 1.f);
	}
	else if (!bLow && Heartbeat)
	{
		Heartbeat->FadeOut(1.5f, 0.f);
		Heartbeat = nullptr;
	}

	// шаги: по пройденному пути. Бегом шаг длиннее и громче, вприсядку — тише
	if (Ch && Ch->GetCharacterMovement() && Ch->GetCharacterMovement()->IsMovingOnGround() && Phase == ERunPhase::Playing)
	{
		const float Speed = Ch->GetVelocity().Size2D();
		StepLeft -= Speed * DeltaSeconds;
		if (Speed > 30.f && StepLeft <= 0.f)
		{
			const bool bRun = Speed > WalkSpeed + 40.f;
			StepLeft = bRun ? 105.f : IsPlayerCrouched() ? 60.f : 72.f;
			RunAudio::Play(this, TEXT("Footstep"), IsPlayerCrouched() ? 0.25f : bRun ? 0.7f : 0.45f, FMath::FRandRange(0.9f, 1.1f));
		}
	}
}

void ARunDirector::Tick(float DeltaSeconds)
{
	if (TestDeathShotAt > 0.f && GetWorld()->GetTimeSeconds() >= TestDeathShotAt)
	{
		TestDeathShotAt = -1.f;
		FScreenshotRequest::RequestScreenshot(FPaths::ProjectSavedDir() / TEXT("Screenshots/Burned/player_dead.png"), true, false);
		UE_LOG(LogRun, Display, TEXT("Run: test shot of the dead player, phase=%d"), static_cast<int32>(Phase));
	}
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
		{
			const float NowT = GetWorld()->GetTimeSeconds();
			if (AttackHitTime >= 0.f && NowT >= AttackHitTime)
			{
				AttackHitTime = -1.f;
				ResolveSwing();
			}
			if (bAttackQueued && NowT >= AttackBusyUntil && Phase == ERunPhase::Playing)
			{
				StartSwing();
			}
			if (NowT < AttackBusyUntil)
			{
				RequestSpeedFactor(0.35f);   // на замахе герой почти стоит
			}
			if (NowT < DodgeUntil && Phase == ERunPhase::Playing)
			{
				// рывок: скорость задаётся напрямую и гаснет к концу
				const float A = (DodgeUntil - NowT) / FMath::Max(DodgeSeconds, 0.05f);
				const FVector V = DodgeDir * (320.f + 620.f * A);
				Ch->GetCharacterMovement()->Velocity = FVector(V.X, V.Y, Ch->GetCharacterMovement()->Velocity.Z);
			}
		}
		const float Gait = bRun ? BaseWalkSpeed : FMath::Min(WalkSpeed, BaseWalkSpeed);
		Ch->GetCharacterMovement()->MaxWalkSpeed = Gait * SpeedRequest;
		// вприсядку — медленнее шага, Shift не помогает
		Ch->GetCharacterMovement()->MaxWalkSpeedCrouched = FMath::Min(WalkSpeed, BaseWalkSpeed) * 0.6f * SpeedRequest;
		if (PC && Phase == ERunPhase::Playing)
		{
			UpdateCrouch(Ch, PC);   // после смерти героя анимацией правит падение (HurtPlayer)
		}
		if (Helmet && bSuitOn)
		{
			// забрало (+Y модели) смотрит туда же, куда герой; середина шлема — чуть выше и впереди основания черепа
			Helmet->SetWorldLocationAndRotation(Ch->GetMesh()->GetSocketLocation(TEXT("head")) + FVector(0.f, 0.f, 9.f) + Ch->GetActorForwardVector() * 2.f,
				FRotator(0.f, Ch->GetActorRotation().Yaw - 90.f, 0.f));
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
		UpdateAudio(DeltaSeconds, Ch);
		// у стены камера упирается и въезжает в персонажа: на это время он скрыт, иначе его спина закрывает весь экран
		if (const APlayerCameraManager* Cam = UGameplayStatics::GetPlayerCameraManager(this, 0))
		{
			// в проверке рук (-RunGripTest) камера нарочно стоит у самой кисти
			const float Near = GripTestStep >= 0 ? 1000.f : FVector::Dist(Cam->GetCameraLocation(), Ch->GetActorLocation() + FVector(0.f, 0.f, 40.f));
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
	TickSwingContact();
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
	if (GripTestStep >= 0)
	{
		TickGripTest();
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
	// 122 — замах ключом и кадр в его середине, 123 — рывок и кадр в нём (только с -RunShots)
	static const int32 EnemySteps[] = { 100, 101, 105, 101, 110, 101, -1, 0, -1, 111, 116, 122, 116, 123, 116, 124, 112, 112, 1, -1, 111,
		112, 112, 112, 112, 112, 112, 112, 112, 112, 112, 111, 120, 120, 120, 120, 120, 111,
		-1, 0, -1, 111, 120, 120, 120, 120, 120, 120, 120, 120, 111, 199, 199, 125, 116, 104 };   // 125, 116 — кадр убитого после боя
	// полный забег по шпаргалке (-RunWin): 200+R — подойти к предмету роли R, 210 — выбросить проводника,
	// 220 — выбросить всё, кроме блокнота, 106 — отчёт о состоянии
	// 230 — надеть скафандр, если он в комнате (уровни 1 и 2: разгерметизация на 2 или 3)
	static const int32 WinSteps[] = { 100, 101, 200, 101, -1, 0, -1, 201, 101, 230, -1, 0, -1, 202, 101, 230, -1, 0, -1,
		210, 203, 101, -1, 0, -1, 106, 220, -1, 0, -1, 106, 104 };
	// показ для снимков (-RunShow; в редакторе — ключ запуска самого редактора): прочитать записки рубки,
	// аптечка в руке после ушиба, осмотр, меню на Tab (144 — снимок в Saved/Screenshots/Menu, 145 — закладка выше).
	// 199 — пауза, каждое состояние держится несколько секунд
	static const int32 ShowSteps[] = { 100, 101, 140, -1, 141, 199, 199, 199, 199, 199, 199, 199, 142, 199, 199, 199, 144, 199, 199, 199,
		143, 199, 199, 144, 199, 145, 199, 199, 144, 199, 143, 146, 199, 199, 144, 199, 199, 199 };
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
	case 146:
	{
		// витрина моделей: все вещи каталога, ключ и записка сеткой на полу перед героем, скафандр сбоку, шлем надет;
		// камера сверху, чтобы мелкие вещи было видно
		FVector Floor = Pawn->GetActorLocation() - FVector(0.f, 0.f, 90.f);
		FHitResult Hit;
		FCollisionQueryParams Params(FName(TEXT("RunShow")), false, Pawn);
		if (GetWorld()->LineTraceSingleByChannel(Hit, Pawn->GetActorLocation(), Pawn->GetActorLocation() - FVector(0.f, 0.f, 300.f), ECC_Visibility, Params))
		{
			Floor = Hit.ImpactPoint;
		}
		const FVector Fwd = Pawn->GetActorForwardVector(), Side = Pawn->GetActorRightVector();
		const FVector Mid = Floor + Fwd * 95.f;
		TArray<int32> List;
		for (int32 I = 0; I < 16; ++I)
		{
			List.Add(I);
		}
		List.Add(Weapon);
		for (int32 I = 0; I < List.Num(); ++I)
		{
			SpawnItemActor(List[I], -1, Mid + Fwd * (45.f - 30.f * (I / 5)) + Side * (-60.f + 30.f * (I % 5)) + FVector(0.f, 0.f, 11.f));
		}
		SpawnItemActor(0, 0, Mid - Fwd * 75.f + Side * 30.f + FVector(0.f, 0.f, 1.f));    // записка
		SpawnItemActor(Suit, -1, Mid + Side * 130.f + FVector(0.f, 0.f, 11.f));
		PutOnSuit();
		const FVector From = Mid - Fwd * 70.f + FVector(0.f, 0.f, 150.f);
		ACameraActor* Cam = GetWorld()->SpawnActor<ACameraActor>(From, (Mid - From).Rotation());
		Cam->GetCameraComponent()->bConstrainAspectRatio = false;
		Cam->GetCameraComponent()->SetFieldOfView(70.f);
		if (APlayerController* PC = UGameplayStatics::GetPlayerController(this, 0))
		{
			PC->SetViewTargetWithBlend(Cam, 0.f);
		}
		UE_LOG(LogRun, Display, TEXT("Run: show models %d, suit on=%d"), List.Num(), bSuitOn ? 1 : 0);
		break;
	}
	case 141:
	{
		int32 ShowItem = Medkit;
		FParse::Value(FCommandLine::Get(), TEXT("RunShowItem="), ShowItem);   // какую вещь показать на осмотре
		Pocket.Add(ShowItem);
		HeldSlot = Pocket.Num() - 1;
		HurtPlayer(TEXT("Show bruise."), Pawn->GetActorLocation() + FVector(-100.f, 0.f, 0.f), 45.f);
		break;
	}
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
	case 125:
		// камера на место, где упал последний убитый противник (только с -RunShots)
		if (FParse::Param(FCommandLine::Get(), TEXT("RunShots")) && !TestKillAt.IsZero())
		{
			const FVector From = TestKillAt + (Pawn->GetActorLocation() - TestKillAt).GetSafeNormal2D() * 230.f + FVector(0.f, 0.f, 150.f);
			ACameraActor* Cam = GetWorld()->SpawnActor<ACameraActor>(From, (TestKillAt + FVector(0.f, 0.f, 25.f) - From).Rotation());
			Cam->GetCameraComponent()->bConstrainAspectRatio = false;
			Cam->GetCameraComponent()->SetFieldOfView(75.f);
			if (APlayerController* PC = UGameplayStatics::GetPlayerController(this, 0))
			{
				PC->SetViewTargetWithBlend(Cam, 0.f);
			}
			TestNextAt = Now + 0.6f;
		}
		break;
	case 124:
		// проверка смерти героя (-RunDie -RunShots): удар насмерть спереди, кадр через полторы секунды
		if (FParse::Param(FCommandLine::Get(), TEXT("RunDie")) && FParse::Param(FCommandLine::Get(), TEXT("RunShots")) && Phase == ERunPhase::Playing)
		{
			InvulnerableUntil = 0.f;
			TestDeathShotAt = Now + 1.6f;
			HurtPlayer(TEXT("Test death."), Pawn->GetActorLocation() + Pawn->GetActorForwardVector() * 100.f, 1000.f);
		}
		break;
	case 122:
		if (FParse::Param(FCommandLine::Get(), TEXT("RunShots")))
		{
			// в середину комнаты: в тесном тамбуре камера въезжает в героя и прячет его
			const FVector Mid = RoomActor->GetActorLocation();
			Pawn->SetActorLocation(FVector(Mid.X, Mid.Y, Pawn->GetActorLocation().Z), false, nullptr, ETeleportType::TeleportPhysics);
			OnAttack();
			TestNextAt = Now + 0.22f;
		}
		break;
	case 123:
		if (FParse::Param(FCommandLine::Get(), TEXT("RunShots")))
		{
			TestNextAt = Now + 1.2f;   // дождаться конца замаха, потом рывок — следующим шагом через 0,15 с
			DodgeReadyAt = 0.f;
		}
		break;
	case 118:
		if (ForceEmergency > 0 && Pocket.Num() < PocketSlots)
		{
			Pocket.Add(0);   // фонарик — первая вещь каталога: он в левой руке и светит сам
			UE_LOG(LogRun, Display, TEXT("Run: test flashlight in hand=%d"), HasFlashlight() ? 1 : 0);
			TestNextAt = Now + 1.2f;
		}
		break;
	case 116:
		if (ForceThreatKind == ThreatSmoke || ForceEmergency > 0 || (ForceThreatKind > NumThreats - 3 && FParse::Param(FCommandLine::Get(), TEXT("RunShots"))))
		{
			const bool bFlash = HasFlashlight() && bLightOn;
			const FString Path = FPaths::ProjectSavedDir() / FString::Printf(TEXT("Screenshots/Burned/seed%u_t%d_key%d_player_%s.png"),
				static_cast<uint32>(Seed), ForceThreatKind, Rooms[CurrentRoom].Key, bFlash ? TEXT("flashlight") : IsPlayerCrouched() ? TEXT("crouch")
				: Now < AttackBusyUntil ? TEXT("swing") : TestStepWasDodge() ? TEXT("dodge") : TestStandShots++ == 0 ? TEXT("stand") : TEXT("later"));
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
