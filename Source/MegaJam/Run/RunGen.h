// Генератор забега: зерно -> раскладка. Перенос tools/rungen (Python) один в один.
// Эталон и спецификация: tools/rungen/README.md. Проверка переноса: tools/ue/check_port.py.

#pragma once

#include "CoreMinimal.h"
#include <initializer_list>
#include "RunGen.generated.h"

namespace RunGen
{
	// Роли значимых предметов = номера битов в маске сигнатуры. Первые четыре — правильный путь,
	// дальше идут лишние значимые предметы: 4, 5, ... Опасных предметов нет, аномалию несёт набор целиком.
	enum : int32 { RoleL = 0, RoleK1 = 1, RoleK2 = 2, RoleK3 = 3, NumChain = 4, MaxSig = 12, RoleDummy = 99, RoleNotInRun = -1 };
	enum : int32 { MaskL = 1, MaskK1 = 2, MaskK2 = 4, MaskK3 = 8, FinalMask = 14, Anchor = 1 << MaxSig };
	enum : int32 { NumSwitches = 6 };
	enum : int32 { Notebook = -1, PocketSlots = 4, DoorsPerRoom = 4 };
	// Типы отсеков, DESIGN.md 5.1
	enum : int32 { Bridge = 0, Living = 1, Lab = 2, LifeSupport = 3, Engine = 4, Medbay = 5, Cargo = 6, Mess = 7, Computer = 8, NumRoomTypes = 9 };
	// Класс комнаты. ClsStart — только стартовая рубка (копия 0)
	enum : int32 { ClsStart = 0, ClsChain = 1, ClsGuess = 2, ClsEngine = 3 };
	enum : int32 { NoteNotebookFirst = 0, NoteLoopExit, NoteNextKey, NoteUseless, NoteDanger, NoteEngineSet, NoteFinale };
	// Домены ГСЧ. Номера 2 и 6 свободны, как в эталоне
	enum : uint32 { DRoles = 1, DRoomType = 3, DSwitch = 4, DAnomaly = 5, DItems = 7, DNotes = 8, DGuarantee = 9, DCosmetic = 10, DStart = 11 };

	MEGAJAM_API uint32 Mix32(uint32 X);
	MEGAJAM_API uint32 Hash32(std::initializer_list<uint32> Values);

	/** Детерминированный ГСЧ: n-й вызов возвращает Hash32(Base, n). */
	struct MEGAJAM_API FRng
	{
		uint32 Base;
		uint32 Counter = 0;

		FRng(std::initializer_list<uint32> Key) : Base(Hash32(Key)) {}
		uint32 NextU32();
		uint32 Below(uint32 N);
		bool Chance(double P);
		void Shuffle(TArray<int32>& Arr);
		int32 Weighted(const TArray<int32>& Weights);
	};

	MEGAJAM_API int32 PopCount(int32 X);
	MEGAJAM_API int32 RoomKey(int32 RoleMask, bool bHasNotebook);
	MEGAJAM_API int32 ChainLevel(int32 Key);
	MEGAJAM_API int32 RoomClass(int32 Key);
	MEGAJAM_API TArray<int32> AllKeys(int32 NumSig);

	MEGAJAM_API int32 CatalogSize();
	MEGAJAM_API FString ItemName(int32 Item);
	MEGAJAM_API FString ItemNoun(int32 Item);
	MEGAJAM_API int32 TemplateCount(int32 Kind);
	MEGAJAM_API FString RenderNote(int32 Kind, int32 Tpl, const TArray<int32>& Items);

	MEGAJAM_API const TCHAR* RoomTypeName(int32 Type);
	MEGAJAM_API const TCHAR* ClassName(int32 Cls);
	MEGAJAM_API const TCHAR* AnomalyName(int32 Anomaly);
	MEGAJAM_API FString RoleName(int32 Role);
	MEGAJAM_API const TCHAR* NoteKindName(int32 Kind);
}

/** Числа баланса. Значения по умолчанию выгружены из tools/rungen/config.py. */
struct MEGAJAM_API FRunConfig
{
	int32 ItemsInRun;
	int32 Health;
	double PGuess;
	int32 FillerMin;
	int32 FillerMax;
	int32 Extras;        // лишних значимых предметов
	int32 DummyWeight;
	int32 ExtraWeight;
	double PExtraNote;
	double PGuessNote;

	FRunConfig();
};

USTRUCT(BlueprintType)
struct MEGAJAM_API FRunNote
{
	GENERATED_BODY()

	UPROPERTY(BlueprintReadOnly, Category = "Run") int32 Kind = 0;
	/** id предметов; порядок зависит от вида записки, см. generator.Note в эталоне */
	UPROPERTY(BlueprintReadOnly, Category = "Run") TArray<int32> Items;
	UPROPERTY(BlueprintReadOnly, Category = "Run") int32 Tpl = 0;

	FString Text() const { return RunGen::RenderNote(Kind, Tpl, Items); }
};

/** Комната набора. Всё в ней определяет набор в кармане, а не дверь: сколько бы дверей ни раскрыли
 *  с одним набором, за ними одна и та же комната с теми же вещами (решение автора 13.11). */
USTRUCT(BlueprintType)
struct MEGAJAM_API FRunRoomContent
{
	GENERATED_BODY()

	UPROPERTY(BlueprintReadOnly, Category = "Run") int32 Key = 0;
	UPROPERTY(BlueprintReadOnly, Category = "Run") int32 RoomType = 0;
	UPROPERTY(BlueprintReadOnly, Category = "Run") int32 Switches = 0;
	UPROPERTY(BlueprintReadOnly, Category = "Run") int32 Anomaly = 0;
	/** id предметов; RunGen::Notebook (-1) — блокнот */
	UPROPERTY(BlueprintReadOnly, Category = "Run") TArray<int32> Items;
	UPROPERTY(BlueprintReadOnly, Category = "Run") TArray<FRunNote> Notes;
};

/** Раскладка забега. Всё вычисляется из зерна и чисел баланса. */
class MEGAJAM_API FRunLayout
{
public:
	explicit FRunLayout(uint32 InSeed, const FRunConfig& InCfg = FRunConfig());

	uint32 Seed;
	FRunConfig Cfg;
	TArray<int32> RunItems;    // предметы забега: первые шесть — L, K1, K2, K3, X, Y, остальные — пустышки
	TArray<int32> RoleItem;    // роль -> предмет
	TArray<int32> Dummies;
	TArray<int32> ItemRole;    // предмет -> роль
	int32 NumSig;              // значимых предметов в забеге: NumChain + Cfg.Extras
	TArray<int32> SwitchOf[RunGen::NumRoomTypes]; // [тип отсека][роль] -> номер переключателя; заполнено для обычных типов
	int32 BridgeSwitches;
	int32 EngineSwitches;
	FRunNote FirstNote;
	/** Опасные пары значимых предметов: набор ровно из этих двух даёт комнату с аномалией. Для записок. */
	TArray<TPair<int32, int32>> DangerPairs;

	int32 RoleOf(int32 Item) const;
	int32 RoleMask(const TArray<int32>& Pocket) const;
	int32 PocketKey(const TArray<int32>& Pocket) const;
	void Look(int32 Key, int32& OutType, int32& OutSwitches) const;
	/** Аномалия набора: зависит только от зерна и сигнатуры. На правильном пути аномалий нет. */
	int32 AnomalyOf(int32 Key) const;
	/** Предмет правильного пути, который лежит в комнате этого набора. false — такого нет. */
	bool TargetOf(int32 Key, int32& OutItem) const;
	/** Комната набора: вид, аномалия, предметы, записки. */
	FRunRoomContent Room(int32 Key) const;
	/** Стартовая рубка: комната набора «только блокнот», в которой ещё лежит сам блокнот. */
	FRunRoomContent StartRoom() const;

private:
	TArray<int32> FillerPool;
	TArray<int32> FillerWeights;

	void AheadNote(int32 Level, int32& OutKind, TArray<int32>& OutItems) const;
	void DangerNote(RunGen::FRng& Rng, int32& OutKind, TArray<int32>& OutItems) const;
	FRunNote MakeNote(RunGen::FRng& Rng, int32 Kind, const TArray<int32>& Items) const;
	TArray<FRunNote> ChainNotes(int32 Key) const;
	TArray<FRunNote> GuessNotes(int32 Key) const;
	TArray<int32> DrawFiller(RunGen::FRng& Rng, int32 N) const;
};
