// Ведущий забега: раскладка, состояние комнат и кармана, смена комнат вокруг игрока.
// Один актор на уровне. Правила — DESIGN.md, разделы 4 и 5.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "RunGen.h"
#include "RunDirector.generated.h"

class ARunItem;
class ARunRoom;
class FRunLayout;

/** Предмет, лежащий в комнате. Брошенный игроком помнит место. */
struct FRunPlacedItem
{
	int32 Item = 0;
	bool bHasPos = false;
	FVector LocalPos = FVector::ZeroVector;
};

/** Комната набора: вещи и записки. Одна на набор — через какую бы дверь в неё ни вошли,
 *  в ней лежит одно и то же; взятое не возвращается, выброшенное остаётся (решение автора 13.11). */
struct FRunKeyState
{
	FRunRoomContent Content;
	TArray<FRunPlacedItem> Items;
	TArray<bool> NoteRead;
};

/** Комната за конкретной дверью. Свои у неё только двери и состояние аномалии. */
struct FRunRoomState
{
	int32 Key = 0;
	int32 Doors[4] = { -1, -1, -1, -1 };   // куда ведёт дверь: номер комнаты или −1, если не раскрыта
	bool bAnomalyActive = false;
	bool bVisited = false;
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

	// --- то, что читает экранный интерфейс ---
	const TArray<int32>& GetPocket() const { return Pocket; }
	int32 GetHits() const { return Hits; }
	int32 GetHealth() const;
	ERunPhase GetPhase() const { return Phase; }
	bool IsEngineFixed() const { return bEngineFixed; }
	bool IsJournalOpen() const { return bShowJournal; }
	const TArray<FString>& GetJournal() const { return Journal; }
	FString GetMessage() const;
	FString GetPrompt() const;
	FString GetDebugLine() const;
	/** Отладочная шпаргалка: все наборы, ведущие к победе, и что в их комнатах брать. */
	const TArray<FString>& GetSolution() const { return Solution; }
	bool IsDebugShown() const { return bShowDebug; }

	/** Время от закрытия створок до смены комнаты, секунды. */
	UPROPERTY(EditAnywhere, Category = "Run")
	float TransitionSeconds = 1.6f;

	/** Показывать отладочную шпаргалку с самого старта, не дожидаясь клавиши H. Ключ запуска -RunDebug делает то же. */
	UPROPERTY(EditAnywhere, Category = "Run")
	bool bDebugAtStart = false;

	/** Зерно забега. 0 — случайное. Ключ запуска -RunSeed=N важнее. */
	UPROPERTY(EditAnywhere, Category = "Run")
	int32 FixedSeed = 0;

private:
	TUniquePtr<FRunLayout> Layout;
	uint32 Seed = 0;
	TArray<FRunRoomState> Rooms;
	TMap<int32, FRunKeyState> Keys;   // состояние комнаты каждого набора, где игрок уже был
	int32 CurrentRoom = 0;
	TArray<int32> Pocket;
	TArray<FString> Journal;
	int32 Hits = 0;
	bool bEngineFixed = false;
	bool bFirstNoteRead = false;
	ERunPhase Phase = ERunPhase::Playing;

	UPROPERTY()
	TObjectPtr<ARunRoom> RoomActor;

	UPROPERTY()
	TArray<TObjectPtr<ARunItem>> ItemActors;

	bool bPlayerReady = false;
	bool bBusy = false;
	int32 PendingDoor = -1;
	float SwapAt = 0.f;
	float RestartAt = 0.f;
	FString Message;
	float MessageUntil = 0.f;
	bool bShowJournal = false;
	bool bShowDebug = false;

	TArray<FString> Solution;
	void BuildSolution();
	FRunKeyState& KeyState(int32 Key);
	FRunKeyState& CurrentKeyState() { return KeyState(Rooms[CurrentRoom].Key); }
	const FRunRoomContent& CurrentContent() const { return Keys.FindChecked(Rooms[CurrentRoom].Key).Content; }
	void SetupPlayer();
	void SpawnRoom(int32 RoomId, const FVector& Location, int32 ArrivalDoor);
	void SpawnRoomContents();
	ARunItem* SpawnItemActor(int32 Item, int32 NoteIndex, const FVector& Location);
	void DoSwap();
	void EnterRoom(int32 RoomId);
	void Say(const FString& Text, float Seconds = 5.f);
	ARunItem* NearestItem() const;
	void AddToJournal(const FString& Text);

	void OnInteract();
	void OnDrop(int32 Slot);
	void OnDrop1() { OnDrop(0); }
	void OnDrop2() { OnDrop(1); }
	void OnDrop3() { OnDrop(2); }
	void OnDrop4() { OnDrop(3); }
	void OnToggleJournal();
	void OnToggleDebug();

	// --- самопроверка без окна: ключ запуска -RunSelfTest ---
	bool bSelfTest = false;
	int32 TestStep = 0;
	float TestNextAt = 0.f;
	void TickSelfTest();
	void LogRoom(const TCHAR* Why) const;
};
