// Ведущий забега: раскладка, состояние комнат и кармана, смена комнат вокруг игрока.
// Один актор на уровне. Правила — DESIGN.md, разделы 4 и 5.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "RunGen.h"
#include "RunDirector.generated.h"

class ARunEnemy;
class ARunItem;
class ARunRoom;
class ARunThreat;
class FRunLayout;
class USceneComponent;
class USkeletalMesh;
class UStaticMeshComponent;

/** Предмет, лежащий в комнате. Брошенный игроком помнит место. */
struct FRunPlacedItem
{
	int32 Item = 0;
	bool bHasPos = false;
	FVector LocalPos = FVector::ZeroVector;
	int32 Spot = -1;   // номер метки в комнате: закреплён за вещью, чтобы остальные не переезжали, когда одну взяли
	int32 Uid = 0;     // своя у каждой записи: по ней взятая вещь вычёркивается (аптечек в комнате может быть несколько)
	int32 Niche = -1;  // >= 0: аптечка в аварийной нише, номер ниши по модулю их числа в комнате
};

/** Комната набора: вещи и записки. Одна на набор — через какую бы дверь в неё ни вошли,
 *  в ней лежит одно и то же; взятое не возвращается, выброшенное остаётся (решение автора 13.11). */
struct FRunKeyState
{
	FRunRoomContent Content;
	TArray<FRunPlacedItem> Items;
	TArray<bool> NoteRead;
	bool bEnemiesSpawned = false;   // противники этой комнаты уже появлялись: убитые не возвращаются
};

/** Комната за конкретной дверью. Свои у неё только двери. */
struct FRunRoomState
{
	int32 Key = 0;
	int32 Doors[4] = { -1, -1, -1, -1 };   // куда ведёт дверь: номер комнаты или −1, если не раскрыта
	bool bVisited = false;
};

/** Противник. Живёт в комнате своего набора, как и вещи; человек идёт за игроком (решение автора 13.11). */
struct FRunEnemyState
{
	int32 Id = 0;
	int32 Kind = 0;                        // RunGen::ThreatHuman, ThreatRobot или ThreatRats
	int32 Health = 0;
	int32 Key = 0;                         // комната какого набора; у идущего следом — та, куда он войдёт
	FVector LocalPos = FVector::ZeroVector;
	float ArriveAt = -1.f;                 // >= 0: идёт следом за игроком и войдёт в это время
	int32 ArriveDoor = -1;
};

UENUM()
enum class ERunPhase : uint8 { Playing, Dead, Won };

UCLASS()
class MEGAJAM_API ARunDirector : public AActor
{
	GENERATED_BODY()

public:
	ARunDirector();
	virtual ~ARunDirector();

	virtual void BeginPlay() override;
	virtual void Tick(float DeltaSeconds) override;

	/** Игрок зашёл в глубину тамбура: закрыть створки и после паузы сменить комнату. */
	void BeginTransition(ARunRoom* Room, int32 Door);

	// --- то, что вызывают аномалии и противники ---
	/** Попадание: Damage из 100. После него игрок недолго неуязвим; From — откуда пришёл удар, для отброса.
	 *  bKnockback = false — урон без толчка (дым, споры: медленное отравление). */
	void HurtPlayer(const FString& Text, const FVector& From, float Damage, bool bKnockback = true);
	/** Смерть сразу, без неуязвимости после прошлого попадания (чёрная дыра). */
	void KillPlayer(const FString& Text, const FVector& From);
	/** Герой вприсядку (C — переключить, Ctrl — пока зажат): под дымом (решение автора 15.11). */
	bool IsPlayerCrouched() const;
	/** Скафандр надет: споры и разгерметизация не вредят (DESIGN.md 5.9). */
	bool IsSuitOn() const { return bSuitOn; }
	/** Надеть (подобрать с пола) и снять (ложится у ног, как выброшенная вещь; слот не нужен — решение автора 15.11).
	 *  В комнате без воздуха снять нельзя: иначе скафандр останется там, а войти за ним без него не выйдет. */
	void PutOnSuit();
	void TakeOffSuit();
	/** Комната, где игрок, — разгерметизация. */
	bool IsInVacuum() const;
	/** Подпись и шкала угрозы на экране (счётчик радиации, направление гравитации). */
	void SetThreatHint(const FString& Text, float Meter);
	/** Замедлить игрока на этот кадр. */
	void RequestSpeedFactor(float Factor) { SpeedRequest = FMath::Min(SpeedRequest, Factor); }
	/** На этот кадр: камера героя вприсядку не поднимается выше этой высоты (мир, см) — она под слоем дыма. */
	void RequestCameraCeiling(float WorldZ) { CameraCeiling = FMath::Min(CameraCeiling, WorldZ); }
	/** Куда противнику идти, чтобы добраться до игрока: с учётом стен тамбуров. */
	FVector SteerTarget(const FVector& From, const FVector& To) const;
	/** Игрок подошёл к двери: повод один раз сказать главное правило. */
	void OnDoorApproach();

	// --- то, что читает экранный интерфейс ---
	const TArray<int32>& GetPocket() const { return Pocket; }
	/** Здоровье, от 0 до MaxHealth (решение автора 14.11: шкала 0–100 вместо счёта попаданий). */
	float GetHealth() const { return Health; }
	static constexpr float MaxHealth = 100.f;
	float GetDamageTaken() const { return DamageTaken; }
	int32 GetMedkitsUsed() const { return MedkitsUsed; }
	/** Слот кармана, вещь из которого в руке; −1 — руки пусты. */
	int32 GetHeldSlot() const { return Pocket.IsValidIndex(HeldSlot) ? HeldSlot : -1; }
	/** Осмотр вещи в руке: она крупно перед камерой, мышь её вертит. Блокнот не осматривают — он раскрывается в меню. */
	bool IsInspecting() const { return bInspecting && GetHeldSlot() >= 0 && !IsReading(); }
	/** Меню на Tab открыто (решение автора 15.11): блокнот с закладками записок, карман, скафандр. Время идёт. */
	bool IsReading() const { return bMenuOpen && Phase == ERunPhase::Playing; }
	bool HasNotebook() const { return Pocket.Contains(RunGen::Notebook); }
	/** Какой разворот блокнота открыт. Экран знает, сколько их, и сам поправляет номер (ClampJournalPage). */
	int32 GetJournalPage() const { return JournalPage; }
	void ClampJournalPage(int32 NumSpreads) { JournalPage = FMath::Clamp(JournalPage, 0, FMath::Max(0, NumSpreads - 1)); }
	void SetJournalPage(int32 Spread) { JournalPage = FMath::Max(0, Spread); }
	/** Закладки блокнота: прочитанные записки по порядку (текст — как в блокноте). Записки слота не занимают. */
	const TArray<FString>& GetBookmarks() const { return Bookmarks; }
	/** Выбранная закладка; −1 — ни одной. */
	int32 GetBookmark() const { return Bookmarks.IsValidIndex(Bookmark) ? Bookmark : -1; }
	/** Закладку только что выбрали: экран один раз раскрывает блокнот на её развороте. */
	bool ConsumeBookmarkJump() { const bool b = bBookmarkJump; bBookmarkJump = false; return b; }
	/** Скафандр надевали хоть раз (снятый лежит там, где его сняли). */
	bool WasSuitWorn() const { return bSuitWorn; }
	ERunPhase GetPhase() const { return Phase; }
	bool IsEngineFixed() const { return bEngineFixed; }
	const TArray<FString>& GetJournal() const { return Journal; }
	FString GetMessage() const;
	FString GetPrompt() const;
	/** Где в мире лежит то, к чему относится подсказка действия. false — показывать нечего. */
	bool GetPromptAnchor(FVector& Out) const;
	/** Подсказка управления: показывается один раз, когда клавиша впервые нужна. */
	FString GetTip() const;
	/** 0..1, пока шлюз закрыт и «считывает» карман; меньше нуля — перехода нет. */
	float GetTransitionAlpha() const;
	/** Название отсека, в котором игрок. */
	FString GetRoomName() const { return RoomName; }
	/** 1 сразу после входа в комнату, 0 через две с половиной секунды: для крупной надписи. */
	float GetRoomTitleAlpha() const;
	bool IsRoomFamiliar() const { return bRoomFamiliar; }
	bool HasUnreadJournal() const { return bJournalUnread; }
	// --- итоги забега и пауза ---
	int32 GetDoorsOpened() const { return FMath::Max(0, Rooms.Num() - 1); }
	int32 GetNotesRead() const { return NotesRead; }
	/** Сколько секунд идёт забег; после смерти или победы время стоит. */
	float GetRunSeconds() const;
	const FString& GetDeathCause() const { return DeathCause; }
	uint32 GetSeed() const { return Seed; }
	bool IsPausedByMenu() const { return bMenuPause; }
	/** Где дверь, через которую войдёт преследователь. false — никто следом не идёт. */
	bool GetFollowerDoor(FVector& Out) const;
	FString GetDebugLine() const;
	/** Отладочная шпаргалка: все наборы, ведущие к победе, и что в их комнатах брать. */
	const TArray<FString>& GetSolution() const { return Solution; }
	bool IsDebugShown() const { return bShowDebug; }
	int32 GetEnemiesHere() const { return EnemyActors.Num(); }
	/** Сколько преследователей сейчас идёт следом и ещё не вошло. */
	int32 GetFollowers() const;
	bool HasWeapon() const { return Pocket.Contains(RunGen::Weapon); }
	/** 1 в момент удара, 0 через 0,2 с: для росчерка на экране. */
	float GetSwingFlash() const;
	const FString& GetThreatHint() const { return ThreatHint; }
	float GetThreatMeter() const { return ThreatMeter; }
	/** 1 сразу после попадания, 0 через полсекунды: для красной вспышки. */
	float GetHurtFlash() const;
	/** 1 сразу после аптечки, 0 через 0,6 с: для зелёной вспышки. */
	float GetHealFlash() const;

	/** Сколько секунд после попадания игрок неуязвим. */
	UPROPERTY(EditAnywhere, Category = "Run")
	float HurtGraceSeconds = 1.5f;

	/** Время от закрытия створок до смены комнаты, секунды. */
	UPROPERTY(EditAnywhere, Category = "Run")
	float TransitionSeconds = 1.6f;

	/** Показывать отладочную шпаргалку с самого старта, не дожидаясь клавиши H. Ключ запуска -RunDebug делает то же. */
	UPROPERTY(EditAnywhere, Category = "Run")
	bool bDebugAtStart = false;

	/** Для отладки: игра сама проходит сценарий самопроверки (как с ключом -RunSelfTest), в редакторе тоже. */
	UPROPERTY(EditAnywhere, Category = "Run")
	bool bAutoPlayTest = false;

	/** Для отладки: какая угроза будет в любой опасной комнате (1–7, см. RunGen::Threat...). 0 — как решит набор.
	 *  Ключ запуска -RunThreat=N делает то же. */
	UPROPERTY(EditAnywhere, Category = "Run")
	int32 ForceThreatKind = 0;

	/** Зерно забега. 0 — случайное. Ключ запуска -RunSeed=N важнее. */
	UPROPERTY(EditAnywhere, Category = "Run")
	int32 FixedSeed = 0;

	/** Меш героя, который ставится персонажу игрока вместо манекена шаблона. Должен стоять на скелете SK_Mannequin. */
	UPROPERTY(EditAnywhere, Category = "Run")
	TObjectPtr<USkeletalMesh> HeroMesh;

	/** Скорость шага игрока, см/с: так он ходит по умолчанию. Бег на Shift — скорость персонажа шаблона (500).
	 *  В блендспейсе шаблона ходьба стоит на 300, бег на 600: при 250 на экране шаг. */
	UPROPERTY(EditAnywhere, Category = "Run")
	float WalkSpeed = 250.f;

	/** Сколько здоровья возвращает аптечка (из 100). */
	UPROPERTY(EditAnywhere, Category = "Run")
	float MedkitHeal = 40.f;

	/** В скольких комнатах наборов из ста в аварийной нише есть аптечка. Какие это комнаты — решает зерно. */
	UPROPERTY(EditAnywhere, Category = "Run")
	int32 MedkitChancePercent = 35;

	/** Сколько опасных комнат из ста выгорели (DESIGN.md §14). Какие — чистый случай по зерну и набору;
	 *  что в них сгорело — тоже по зерну и набору. Безопасные комнаты не горят. */
	UPROPERTY(EditAnywhere, Category = "Run", meta = (ClampMin = "0", ClampMax = "100"))
	int32 BurnedRoomPercent = 50;

	/** Для отладки: 1 — выгорают все опасные комнаты, −1 — ни одна, 0 — по BurnedRoomPercent.
	 *  Ключ запуска -RunBurned=N делает то же. */
	UPROPERTY(EditAnywhere, Category = "Run")
	int32 ForceBurned = 0;

	/** Выгорела ли комната этого набора. */
	bool IsBurned(int32 Key) const;

	/** В скольких комнатах наборов из ста горит только аварийный свет (решение автора 15.11: 80). Какие — по зерну
	 *  и набору. Стартовая рубка (она же финальная) и заросшая грибами комната — всегда с обычным светом. */
	UPROPERTY(EditAnywhere, Category = "Run", meta = (ClampMin = "0", ClampMax = "100"))
	int32 EmergencyLightPercent = 80;

	/** Для отладки: 1 — аварийный свет везде (и в стартовой рубке), −1 — нигде, 0 — по EmergencyLightPercent.
	 *  Ключ запуска -RunEmergency=N делает то же. */
	UPROPERTY(EditAnywhere, Category = "Run")
	int32 ForceEmergency = 0;

	/** Экспозиция забега закреплена (ручная, как в меню): автоэкспозиция высветляла тёмное — чёрный дым становился
	 *  серым, аварийная комната — светлой. 1,8 — при этом числе обычная комната выглядит как при автоэкспозиции.
	 *  Ключ запуска -RunExposure=N — проба другого числа. */
	UPROPERTY(EditAnywhere, Category = "Run")
	float ExposureBias = 1.8f;

	bool IsEmergency(int32 Key) const;
	/** Фонарик из каталога вещей: в руке он светит туда, куда смотрит камера. */
	static bool IsFlashlight(int32 Item);

private:
	TUniquePtr<FRunLayout> Layout;
	uint32 Seed = 0;
	TArray<FRunRoomState> Rooms;
	TMap<int32, FRunKeyState> Keys;   // состояние комнаты каждого набора, где игрок уже был
	int32 CurrentRoom = 0;
	TArray<int32> Pocket;
	TArray<FString> Journal;
	float Health = MaxHealth;
	bool bSuitOn = false;
	bool bSuitWorn = false;
	bool bTipSuit = false;
	// меню на Tab и закладки записок
	bool bMenuOpen = false;
	TArray<FString> Bookmarks;
	int32 Bookmark = -1;
	bool bBookmarkJump = false;
	void AddBookmark(const FString& Text);
	void StepBookmark(int32 Step);
	void OnBookmarkPrev() { StepBookmark(-1); }
	void OnBookmarkNext() { StepBookmark(1); }
	UPROPERTY() TObjectPtr<UStaticMeshComponent> Helmet;
	UPROPERTY() TObjectPtr<class UPostProcessComponent> Post;
	UPROPERTY() TObjectPtr<class USpotLightComponent> Flashlight;
	// присед: C переключает, Ctrl держит; без анимаций приседа герой сжимается по высоте (UpdateCrouch)
	bool bCrouchToggle = false;
	bool bCrouchPose = false;
	FVector MeshScaleStanding = FVector::OneVector;
	void OnCrouchKey() { bCrouchToggle = !bCrouchToggle; }
	void UpdateCrouch(class ACharacter* Ch, const class APlayerController* PC);
	float DamageTaken = 0.f;
	int32 MedkitsUsed = 0;
	float HealAt = -100.f;
	int32 NextUid = 1;
	// вещь в руке, осмотр и чтение
	int32 HeldSlot = -1;
	bool bInspecting = false;
	bool bLookLocked = false;
	int32 JournalPage = 0;
	float InspectIdle = 0.f;
	bool bTipHeld = false, bTipMedkit = false;
	bool bEngineFixed = false;
	bool bFirstNoteRead = false;
	ERunPhase Phase = ERunPhase::Playing;

	UPROPERTY()
	TObjectPtr<ARunRoom> RoomActor;

	UPROPERTY()
	TArray<TObjectPtr<ARunItem>> ItemActors;

	UPROPERTY()
	TObjectPtr<ARunThreat> ThreatActor;

	/** Вещь в руке героя: держится за кисть (кость hand_r), висит под ней. */
	UPROPERTY()
	TObjectPtr<USceneComponent> HandPivot;
	UPROPERTY()
	TObjectPtr<UStaticMeshComponent> HandMesh;
	/** Вещь на осмотре: перед камерой, крутится вокруг своей середины. */
	UPROPERTY()
	TObjectPtr<USceneComponent> InspectPivot;
	UPROPERTY()
	TObjectPtr<UStaticMeshComponent> InspectMesh;
	int32 ShownHandItem = TNumericLimits<int32>::Min();
	int32 ShownInspectItem = TNumericLimits<int32>::Min();

	TArray<FRunEnemyState> Enemies;
	int32 NextEnemyId = 1;

	UPROPERTY()
	TArray<TObjectPtr<ARunEnemy>> EnemyActors;   // тела противников в текущей комнате

	FString RoomName;
	float RoomTitleAt = -100.f;
	bool bRoomFamiliar = false;
	TSet<int32> SeenKeys;          // в комнатах каких наборов игрок уже был
	float BusySince = 0.f;
	FString Tip;
	TArray<FString> TipQueue;     // подсказки показываются по очереди, не затирая друг друга
	float TipUntil = 0.f;
	bool bTipDoor = false, bTipDrop = false, bTipHit = false;
	bool bJournalUnread = false;
	int32 NotesRead = 0;
	float RunStartAt = 0.f;
	float RunEndAt = -1.f;
	FString DeathCause;
	bool bMenuPause = false;
	bool bWinTest = false;
	void ShowTip(const FString& Text, float Seconds = 6.f);
	void WriteProgress(const FString& Text);
	void UpdateDoorSigns();

	float NextAttackAt = 0.f;
	float SwingAt = -100.f;

	float InvulnerableUntil = 0.f;
	float HurtAt = -100.f;
	FString ThreatHint;
	float ThreatMeter = 0.f;
	float SpeedRequest = 1.f;
	float CameraCeiling = TNumericLimits<float>::Max();
	static constexpr float BoomArm = 270.f, BoomRise = 45.f;   // камера за правым плечом: длина штанги и подъём
	float BaseWalkSpeed = 0.f;

	bool bPlayerReady = false;
	bool bBusy = false;
	int32 PendingDoor = -1;
	float SwapAt = 0.f;
	float RestartAt = 0.f;
	FString Message;
	float MessageUntil = 0.f;
	bool bShowDebug = false;

	TArray<FString> Solution;
	void BuildSolution();
	FRunKeyState& KeyState(int32 Key);
	FRunKeyState& CurrentKeyState() { return KeyState(Rooms[CurrentRoom].Key); }
	const FRunRoomContent& CurrentContent() const { return Keys.FindChecked(Rooms[CurrentRoom].Key).Content; }
	void SetupPlayer();
	void SpawnRoom(int32 RoomId, const FVector& Location, int32 ArrivalDoor);
	void SpawnRoomContents();
	ARunItem* SpawnItemActor(int32 Item, int32 NoteIndex, const FVector& Location, int32 Uid = 0);
	/** Записать вещь в комнату набора. Аптечка в нише получает Niche, остальные — метку по порядку. */
	FRunPlacedItem& AddPlaced(FRunKeyState& State, int32 Item);
	/** Аптечка в нише: есть ли она в комнате набора, решают зерно и набор. */
	void AddMedkit(FRunKeyState& State);
	/** Вид угрозы комнаты набора: 0 — безопасно. Учитывает отладочную подмену ForceThreatKind. */
	int32 ThreatKindOf(int32 Key);
	void SpawnThreats(int32 ArrivalDoor);
	void SpawnEnemyActor(const FRunEnemyState& Enemy, float StartStun);
	TArray<FVector> FreeFloorPoints(int32 ArrivalDoor, int32 Count) const;
	FRunEnemyState* FindEnemy(int32 Id);
	void MoveEnemies(int32 Door, int32 NewKey, const FVector& NewLocation);
	void TickFollowers();
	void DoSwap();
	void CancelTransition();
	void EnterRoom(int32 RoomId);
	void Say(const FString& Text, float Seconds = 5.f);
	ARunItem* NearestItem() const;
	void AddToJournal(const FString& Text);

	void OnInteract();
	void OnAttack();
	void OnPause();
	void OnRestartKey();
	void OnQuitKey();
	void OnConfirm();
	void RestartRun();
	/** Выбросить вещь из слота: ложится перед игроком и остаётся в комнате (5.3). */
	void DropSlot(int32 Slot);
	/** Слот кармана опустел: поправить номер слота в руке. */
	void RemoveFromPocket(int32 Slot);
	void SelectSlot(int32 Slot);
	void OnSelect1() { SelectSlot(0); }
	void OnSelect2() { SelectSlot(1); }
	void OnSelect3() { SelectSlot(2); }
	void OnSelect4() { SelectSlot(3); }
	void CycleHeld(int32 Step);
	void OnWheelUp();
	void OnWheelDown();
	void OnDropHeld();
	void OnUse();
	void OnInspect();
	void SetInspecting(bool bOn);
	void TurnPage(int32 Step);
	void OnPagePrev() { TurnPage(-1); }
	void OnPageNext() { TurnPage(1); }
	void UseMedkit(int32 Slot);
	/** Tab: открыть или закрыть меню. */
	void OnToggleJournal();
	void SetMenuOpen(bool bOpen);
	/** Каждый кадр: вещь в руке и вещь на осмотре — какой меш показать, где и как повёрнут. */
	void TickHeldItem(float DeltaSeconds);
	void ShowItemMesh(UStaticMeshComponent* Comp, int32 Item, float Fit, bool bHang);
	void OnToggleDebug();

	// --- самопроверка без окна: ключ запуска -RunSelfTest ---
	bool bSelfTest = false;
	bool bShowTest = false;
	int32 TestStep = 0;
	float TestNextAt = 0.f;
	int32 TestShot = 0;                       // кадр выгоревшей комнаты из угла (шаги 113–115)
	TWeakObjectPtr<AActor> TestCam;
	void TickSelfTest();
	void LogRoom(const TCHAR* Why) const;
};
