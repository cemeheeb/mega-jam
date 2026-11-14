// Комната: геометрию даёт блюпринт BP_Room_<Тип> (tools/ue/build_rooms.py), поведение — этот класс.
// Двери: 0 — север (+X), 1 — юг (−X), 2 — запад (−Y), 3 — восток (+Y). DESIGN.md 5.2.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "RunRoom.generated.h"

class ARunDirector;
class UStaticMeshComponent;
class UTextRenderComponent;

/** Размеры коробки комнаты. Должны совпадать с tools/ue/build_rooms.py. */
namespace RunRoomGeo
{
	constexpr float HalfX = 450.f;        // пол-комнаты с юга на север
	constexpr float HalfY = 375.f;        // пол-комнаты с запада на восток
	constexpr float Wall = 30.f;          // толщина стены
	constexpr float DoorWidth = 150.f;
	constexpr float VestibuleWidth = 450.f;
	constexpr float VestibuleDepth = 300.f;

	MEGAJAM_API FVector Dir(int32 Door);              // наружу из комнаты
	MEGAJAM_API FVector Slide(int32 Door);            // куда уезжает створка
	MEGAJAM_API float OuterFace(int32 Door);          // от центра до внешней грани стены
	MEGAJAM_API int32 Opposite(int32 Door);
	/** Где стоит соседняя комната: её тамбур противоположной двери совпадает с тамбуром этой. */
	MEGAJAM_API FVector NeighborOffset(int32 Door);
	MEGAJAM_API const TCHAR* DoorName(int32 Door);
}

UCLASS()
class MEGAJAM_API ARunRoom : public AActor
{
	GENERATED_BODY()

public:
	ARunRoom();

	virtual void BeginPlay() override;
	virtual void Tick(float DeltaSeconds) override;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Run")
	TObjectPtr<USceneComponent> Root;

	UPROPERTY(BlueprintReadOnly, Category = "Run")
	int32 RoomId = -1;

	TWeakObjectPtr<ARunDirector> Director;

	/** Все створки закрыты, идёт переход. */
	bool bSealed = false;

	/** Игрок только что прибыл в тамбур этой двери: створка открыта, обратный переход не начинается, пока он не выйдет в комнату. */
	void SetArrivalDoor(int32 Door);

	/** Мировые координаты центра тамбура двери, на уровне пола. */
	FVector VestibuleCenter(int32 Door) const;

	/** Мировые координаты компонентов-меток, имя которых начинается с Prefix (ItemSpot, NoteSpot). */
	TArray<FVector> GetSpots(const TCHAR* Prefix) const;

	bool AllLeavesClosed() const;

	/** Табло над дверью: название отсека, куда она ведёт. Пустая строка — дверь ещё не раскрыта, табло мерцает прочерками. */
	void SetDoorSign(int32 Door, const FString& Text);

	/** Открыть створку на несколько секунд: через эту дверь входит преследователь. */
	void OpenFor(int32 Door, float Seconds);

	/** Номер двери, в проёме или тамбуре которой стоит точка; −1 — точка в самой комнате. */
	int32 VestibuleOf(const FVector& WorldPos) const;

	/** Свободен ли прямой путь по полу между двумя точками (стены, мебель, закрытые створки). */
	bool ClearWay(const FVector& From, const FVector& To) const;

	/** Куда идти из From, чтобы попасть в To: прямо, если путь свободен; иначе в обход мебели по сетке пола,
	 *  а между комнатой и тамбуром — через проём двери. */
	FVector SteerTarget(const FVector& From, const FVector& To);

private:
	UPROPERTY()
	TObjectPtr<UStaticMeshComponent> Leaf[4];

	FVector LeafClosed[4];
	float LeafOpen[4] = { 0.f, 0.f, 0.f, 0.f };
	bool bArrival[4] = { false, false, false, false };
	float ForcedOpenLeft[4] = { 0.f, 0.f, 0.f, 0.f };

	UPROPERTY()
	TObjectPtr<UTextRenderComponent> Sign[4];
	bool bSignKnown[4] = { false, false, false, false };

	// Сетка пола для обхода мебели: клетка 50 см, свободна та, где помещается противник.
	// Навигационной сетки движка нет: комнаты появляются и исчезают на ходу.
	enum { NavNX = 18, NavNY = 15, NavCells = NavNX * NavNY };
	bool bNavBuilt = false;
	bool NavFree[NavCells];
	int32 NavGoal = -1;          // для какой клетки цели посчитаны расстояния
	int32 NavDist[NavCells];
	void BuildNav();
	int32 NavCellAt(const FVector& Local) const;
	FVector NavCenter(int32 Cell) const;
	void NavFlood(int32 Goal);

};
