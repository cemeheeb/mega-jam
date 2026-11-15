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
	constexpr float HalfX = 450.f;        // пол-комнаты с юга на север, до лица колонок у стен
	constexpr float HalfY = 375.f;        // пол-комнаты с запада на восток, до лица колонок у стен
	constexpr float Lining = 45.f;        // колонки-шкафы вдоль стен (environment/common/wall-columns): стена за ними
	constexpr float Wall = 30.f;          // толщина стены
	constexpr float DoorWidth = 150.f;
	constexpr float VestibuleWidth = 450.f;
	constexpr float VestibuleDepth = 300.f;
	constexpr float Height = 300.f;       // от пола до потолка

	MEGAJAM_API FVector Dir(int32 Door);              // наружу из комнаты
	MEGAJAM_API FVector Slide(int32 Door);            // куда уезжает створка
	MEGAJAM_API float InnerFace(int32 Door);          // от центра до лица колонок: дальше только проём и тамбур
	MEGAJAM_API float OuterFace(int32 Door);          // от центра до внешней грани стены
	MEGAJAM_API int32 Opposite(int32 Door);
	/** Где стоит соседняя комната: её тамбур противоположной двери совпадает с тамбуром этой. */
	MEGAJAM_API FVector NeighborOffset(int32 Door);
	MEGAJAM_API const TCHAR* DoorName(int32 Door);
}

/** Тело на уровне: поза (имя меша SM_DeadMan_<Поза>) и место относительно комнаты. */
struct FRunCorpsePlace
{
	FString Pose;
	FVector Local = FVector::ZeroVector;
	float Yaw = 0.f;
};

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

	/** Кейсы первой помощи в аварийных нишах (меши *_FirstAid из build_rooms.py): где стоят, по порядку имён.
	 *  Сами меши прячутся: аптечку, которую можно взять, ставит ведущий забега (решение автора 14.11). */
	TArray<FTransform> TakeFirstAidCases();

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

	/** Выгоревшая комната (DESIGN.md §14, решение автора 14.11). Seed — от зерна забега и набора, поэтому один набор
	 *  даёт одну и ту же картину. Элемент комнаты — компонент вместе с деталями по имени (Rack1 с Rack1_Strip1,
	 *  колонка Lining_N_L1 с аварийным постом в нише). Часть элементов сгорает: меш заменяется на <меш>_Burned
	 *  из той же папки (если версий несколько — _Burned2 и дальше, — одна из них по Seed). Остальное и то, у чего сгоревшей версии нет, покрывается декалями копоти, как пол и потолок.
	 *  Вызывать сразу после появления комнаты: сетка пола строится позже, по коллизии сгоревших мешей.
	 *  Возвращает (сгорело элементов, покрыто копотью, декалей). */
	FIntVector ApplyBurn(uint32 Seed);

	/** Комната, заражённая грибами (DESIGN.md 5.9, решение автора 15.11): мох декалями (маски копоти цветом мха) на стенах,
	 *  полу, потолке и мебели, кучки грибов у колонок, на мебели и по полу, свет тусклее и зеленее. Seed — от зерна и
	 *  набора. Возвращает (заросших элементов, грибов, декалей). */
	FIntVector ApplyFungus(uint32 Seed);

	/** Аварийное освещение (решение автора 15.11): общий свет и потолочные панели — тусклый красный, маячки тамбуров
	 *  красные, остальные источники едва тлеют — видны только очертания. Красный свет медленно «дышит».
	 *  Возвращает (красных источников, притушенных, панелей). */
	FIntVector ApplyEmergency();
	bool IsEmergency() const { return bEmergency; }

	/** Мертвецы (запрос автора 15.11): позы /Game/Characters/DeadMan/SM_DeadMan_<Поза> (SourceArt/characters/dead-man).
	 *  По зерну и набору: на свободном полу (Floor, Curl), у колонок стен (Wall — сидит у стены, Embed — торчит из
	 *  неё, «телепортировало в стену»), на койках, столешницах и пультах, где сейчас ничего не лежит (Table, Console).
	 *  Двери и места на полу у меток остаются свободными. Occupied — где лежат вещи и записки комнаты.
	 *  Count < 0 — число тел решает зерно (от нуля до трёх). Коллизии у тел нет.
	 *  Out — что и куда поставлено: ведущий забега хранит это за комнатой набора и при возвращении ставит тела
	 *  на те же места (SpawnCorpses), даже если вещи с тех пор забрали. Возвращает, сколько тел поставлено. */
	int32 ApplyCorpses(uint32 Seed, int32 Count, const TArray<FVector>& Occupied, TArray<FRunCorpsePlace>& Out);
	void SpawnCorpses(const TArray<FRunCorpsePlace>& Places);

private:
	bool bEmergency = false;
	struct FPulse
	{
		TWeakObjectPtr<class ULightComponent> Light;
		float Base = 0.f;
	};
	TArray<FPulse> PulseLights;
	UPROPERTY()
	TArray<TObjectPtr<class UMaterialInstanceDynamic>> PulsePanels;

	UPROPERTY()
	TObjectPtr<UStaticMeshComponent> Leaf[4];

	FVector LeafClosed[4];
	float LeafOpen[4] = { 0.f, 0.f, 0.f, 0.f };
	bool bLeafWanted[4] = { false, false, false, false };   // куда едет створка: по смене — звук
	bool bArrival[4] = { false, false, false, false };
	float ForcedOpenLeft[4] = { 0.f, 0.f, 0.f, 0.f };

	UPROPERTY()
	TObjectPtr<UTextRenderComponent> Sign[4];

	int32 Decals = 0;
	/** Цвет декалей AddSoot; A = 0 — свой цвет материала (чёрная копоть). */
	FLinearColor DecalColor = FLinearColor(0.f, 0.f, 0.f, 0.f);
	/** Элементы комнаты для пожара и грибов: компонент со всеми, чьё имя продолжает его имя через «_». Оболочка, створки,
	 *  метки мест, панели потолка не входят. Names — по алфавиту, чтобы раскладка не зависела от порядка компонентов. */
	void CollectElements(TArray<FString>& Names, TMap<FString, TArray<UStaticMeshComponent*>>& Groups) const;
	/** Декаль копоти: Pos и Rot — центр и поворот коробки (проекция вдоль её оси X), HalfSize — половины сторон.
	 *  Mask — имя экземпляра MI_Soot_<Mask>: A, B, C — пятна без верха и низа (поворачиваются как попало);
	 *  D, Band<N>, Plume<N> — дымовые следы с верхом у потолка. Пустое имя — декали нет. */
	void AddSoot(const FVector& Pos, const FRotator& Rot, const FVector& HalfSize, uint32 Hash, const FString& Mask, float Opacity);
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
