#include "RunGen.h"

struct FRunItemDef
{
	const TCHAR* Name;
	const TCHAR* Noun;
	const TCHAR* Category;
};

struct FRunTemplateList
{
	const TCHAR* const* Items;
	int32 Num;
};

#include "RunGenData.inl"

namespace RunGen
{
	uint32 Mix32(uint32 X)
	{
		X ^= X >> 16;
		X *= 0x7FEB352DU;
		X ^= X >> 15;
		X *= 0x846CA68BU;
		X ^= X >> 16;
		return X;
	}

	uint32 Hash32(std::initializer_list<uint32> Values)
	{
		uint32 H = 0x811C9DC5U;
		for (uint32 V : Values)
		{
			H = Mix32((H ^ V) + 0x9E3779B9U);
		}
		return H;
	}

	uint32 FRng::NextU32()
	{
		++Counter;
		return Hash32({ Base, Counter });
	}

	uint32 FRng::Below(uint32 N)
	{
		check(N > 0);
		return NextU32() % N;
	}

	bool FRng::Chance(double P)
	{
		// Порог в 16 битах, как prob16 в эталоне: без сравнения дробных чисел.
		int64 T = static_cast<int64>(P * 65536.0 + 0.5);
		T = FMath::Clamp<int64>(T, 0, 65536);
		return static_cast<int64>(NextU32() >> 16) < T;
	}

	void FRng::Shuffle(TArray<int32>& Arr)
	{
		for (int32 I = Arr.Num() - 1; I > 0; --I)
		{
			const int32 J = static_cast<int32>(Below(static_cast<uint32>(I + 1)));
			Arr.Swap(I, J);
		}
	}

	int32 FRng::Weighted(const TArray<int32>& Weights)
	{
		int32 Total = 0;
		for (int32 W : Weights)
		{
			Total += W;
		}
		const int32 R = static_cast<int32>(Below(static_cast<uint32>(Total)));
		int32 Acc = 0;
		for (int32 I = 0; I < Weights.Num(); ++I)
		{
			Acc += Weights[I];
			if (R < Acc)
			{
				return I;
			}
		}
		checkNoEntry();
		return 0;
	}

	int32 PopCount(int32 X)
	{
		return static_cast<int32>(FMath::CountBits64(static_cast<uint64>(static_cast<uint32>(X))));
	}

	int32 RoomKey(int32 RoleMask, bool bHasNotebook)
	{
		if (RoleMask != 0)
		{
			return RoleMask;
		}
		return bHasNotebook ? Anchor : 0;
	}

	int32 ChainLevel(int32 Key)
	{
		if (Key == 0 || Key == Anchor)
		{
			return 0;
		}
		if (Key >> NumChain)   // в наборе есть лишний значимый предмет
		{
			return -1;
		}
		if (Key & MaskK3)
		{
			return Key == FinalMask ? 4 : -1;
		}
		if (Key & MaskK2)
		{
			return (Key & MaskK1) ? 3 : -1;
		}
		if (Key & MaskK1)
		{
			return 2;
		}
		if (Key & MaskL)
		{
			return 1;
		}
		return -1;
	}

	int32 RoomClass(int32 Key)
	{
		const int32 Level = ChainLevel(Key);
		if (Level == 4)
		{
			return ClsEngine;
		}
		return Level >= 0 ? ClsChain : ClsGuess;
	}

	TArray<int32> AllKeys(int32 NumSig)
	{
		TArray<int32> Keys = { 0, Anchor };
		for (int32 M = 1; M < (1 << NumSig); ++M)
		{
			if (PopCount(M) <= PocketSlots)
			{
				Keys.Add(M);
			}
		}
		return Keys;
	}

	int32 CatalogSize()
	{
		return UE_ARRAY_COUNT(GRunCatalog);
	}

	FString ItemName(int32 Item)
	{
		if (Item == Notebook)
		{
			return FString(GRunNotebookName);
		}
		return Item == Weapon ? FString(GRunWeaponName) : FString(GRunCatalog[Item].Name);
	}

	FString ItemNoun(int32 Item)
	{
		if (Item < 0)
		{
			return TEXT("the ") + ItemName(Item).ToLower();
		}
		return FString(GRunCatalog[Item].Noun);
	}

	int32 TemplateCount(int32 Kind)
	{
		return GRunTemplates[Kind].Num;
	}

	static FString Cap(const FString& S)
	{
		return S.IsEmpty() ? S : S.Left(1).ToUpper() + S.Mid(1);
	}

	FString RenderNote(int32 Kind, int32 Tpl, const TArray<int32>& Items)
	{
		FString Out(GRunTemplates[Kind].Items[Tpl]);
		TArray<FString> Nouns;
		for (int32 It : Items)
		{
			Nouns.Add(ItemNoun(It));
		}
		auto Put = [&Out](const TCHAR* Token, const FString& Value)
		{
			Out = Out.Replace(Token, *Value, ESearchCase::CaseSensitive);
		};
		if (Nouns.Num() > 0)
		{
			Put(TEXT("{item}"), Nouns[0]);
			Put(TEXT("{Item}"), Cap(Nouns[0]));
		}
		if (Kind == NoteNextKey)
		{
			FString Prereq;
			for (int32 I = 1; I < Nouns.Num(); ++I)
			{
				Prereq += (I > 1 ? TEXT(" and ") : TEXT("")) + Nouns[I];
			}
			Put(TEXT("{prereq}"), Prereq);
		}
		if (Kind == NoteDanger)
		{
			Put(TEXT("{item2}"), Nouns[1]);
		}
		if (Kind == NoteEngineSet)
		{
			Put(TEXT("{item2}"), Nouns[1]);
			Put(TEXT("{item3}"), Nouns[2]);
			Put(TEXT("{leader}"), Nouns[3]);
			Put(TEXT("{Leader}"), Cap(Nouns[3]));
		}
		return Out;
	}

	const TCHAR* RoomTypeName(int32 Type)
	{
		static const TCHAR* const Names[] = { TEXT("Bridge"), TEXT("Living"), TEXT("Lab"), TEXT("LifeSupport"), TEXT("Engine"),
			TEXT("Medbay"), TEXT("Cargo"), TEXT("Mess"), TEXT("Computer") };
		return Names[Type];
	}

	const TCHAR* ClassName(int32 Cls)
	{
		static const TCHAR* const Names[] = { TEXT("start"), TEXT("chain"), TEXT("guess"), TEXT("engine") };
		return Names[Cls];
	}

	const TCHAR* AnomalyName(int32 Anomaly)
	{
		static const TCHAR* const Names[] = { TEXT("none"), TEXT("FrozenMoment"), TEXT("Radiation"), TEXT("GravityFailure"), TEXT("SlowTime"),
			TEXT("Robot"), TEXT("Rats"), TEXT("Echo"), TEXT("Human") };
		return Names[Anomaly];
	}

	FString RoleName(int32 Role)
	{
		static const TCHAR* const Names[] = { TEXT("L"), TEXT("K1"), TEXT("K2"), TEXT("K3") };
		if (Role == RoleDummy)
		{
			return TEXT("dummy");
		}
		return Role < NumChain ? FString(Names[Role]) : FString::Printf(TEXT("E%d"), Role - NumChain + 1);
	}

	const TCHAR* NoteKindName(int32 Kind)
	{
		return GRunNoteKindNames[Kind];
	}
}

using namespace RunGen;

FRunConfig::FRunConfig()
	: ItemsInRun(RUNGEN_DEFAULT_ITEMS_IN_RUN)
	, Health(RUNGEN_DEFAULT_HEALTH)
	, PGuess(RUNGEN_DEFAULT_P_GUESS)
	, FillerMin(RUNGEN_DEFAULT_FILLER_MIN)
	, FillerMax(RUNGEN_DEFAULT_FILLER_MAX)
	, Extras(RUNGEN_DEFAULT_EXTRAS)
	, DummyWeight(RUNGEN_DEFAULT_DUMMY_WEIGHT)
	, ExtraWeight(RUNGEN_DEFAULT_EXTRA_WEIGHT)
	, PExtraNote(RUNGEN_DEFAULT_P_EXTRA_NOTE)
	, PGuessNote(RUNGEN_DEFAULT_P_GUESS_NOTE)
{
}

// Цепочка: уровень петли -> роль предмета, который из неё выводит
static const int32 GChainTarget[4] = { RoleL, RoleK1, RoleK2, RoleK3 };
// Обычные типы: их получает набор по хешу. Порядок тот же, что ORDINARY_TYPES в эталоне.
static const int32 GOrdinaryTypes[] = { Living, Lab, LifeSupport, Medbay, Cargo, Mess, Computer };

FRunLayout::FRunLayout(uint32 InSeed, const FRunConfig& InCfg)
	: Seed(InSeed)
	, Cfg(InCfg)
{
	NumSig = NumChain + Cfg.Extras;
	const int32 N = CatalogSize();
	check(Cfg.Extras >= 0 && NumSig <= MaxSig);
	check(Cfg.ItemsInRun >= NumSig + 2 && Cfg.ItemsInRun <= N);

	// 1. Роли: перемешать каталог, первые ItemsInRun идут в забег
	TArray<int32> Order;
	for (int32 I = 0; I < N; ++I)
	{
		Order.Add(I);
	}
	FRng({ Seed, DRoles }).Shuffle(Order);
	ItemRole.Init(RoleNotInRun, N);
	for (int32 I = 0; I < Cfg.ItemsInRun; ++I)
	{
		RunItems.Add(Order[I]);
		if (I < NumSig)
		{
			RoleItem.Add(Order[I]);
			ItemRole[Order[I]] = I;
		}
		else
		{
			Dummies.Add(Order[I]);
			ItemRole[Order[I]] = RoleDummy;
		}
	}

	// 3. Переключатели: в каждом обычном типе каждый значимый предмет включает ровно один из шести
	// Переключателей шесть. Первые шесть ролей получают разные, остальные делят их: комната
	// может выглядеть так же, но быть другой.
	for (int32 Type : GOrdinaryTypes)
	{
		FRng SRng({ Seed, DSwitch, static_cast<uint32>(Type) });
		TArray<int32> Perm = { 0, 1, 2, 3, 4, 5 };
		SRng.Shuffle(Perm);                                          // rng: перестановка
		for (int32 R = 0; R < FMath::Min(NumSig, static_cast<int32>(NumSwitches)); ++R)
		{
			SwitchOf[Type].Add(Perm[R]);
		}
		for (int32 R = NumSwitches; R < NumSig; ++R)
		{
			SwitchOf[Type].Add(static_cast<int32>(SRng.Below(NumSwitches)));   // rng: по одному на роль
		}
	}
	BridgeSwitches = static_cast<int32>(Hash32({ Seed, DCosmetic, static_cast<uint32>(Bridge) }) & 63U);
	EngineSwitches = static_cast<int32>(Hash32({ Seed, DCosmetic, static_cast<uint32>(Engine) }) & 63U);

	// 4. Прочие предметы для раскладки: пустышки и ложные
	FillerPool = Dummies;
	FillerWeights.Init(Cfg.DummyWeight, Dummies.Num());
	for (int32 R = NumChain; R < NumSig; ++R)
	{
		FillerPool.Add(RoleItem[R]);
		FillerWeights.Add(Cfg.ExtraWeight);
	}

	FirstNote.Kind = NoteNotebookFirst;
	FirstNote.Items = { RoleItem[RoleL] };
	FirstNote.Tpl = 0;

	// 5. Опасные пары для записок: опасны не предметы, а сочетания
	for (int32 A = 0; A < NumSig; ++A)
	{
		for (int32 B = A + 1; B < NumSig; ++B)
		{
			if (AnomalyOf((1 << A) | (1 << B)) != 0)
			{
				DangerPairs.Add(TPair<int32, int32>(RoleItem[A], RoleItem[B]));
			}
		}
	}
}

void FRunLayout::DangerNote(FRng& Rng, int32& OutKind, TArray<int32>& OutItems) const
{
	if (DangerPairs.Num() > 0)
	{
		const TPair<int32, int32>& P = DangerPairs[static_cast<int32>(Rng.Below(static_cast<uint32>(DangerPairs.Num())))];
		OutKind = NoteDanger;
		OutItems = { P.Key, P.Value };
	}
	else
	{
		OutKind = NoteUseless;
		OutItems = { Dummies[static_cast<int32>(Rng.Below(static_cast<uint32>(Dummies.Num())))] };
	}
}

int32 FRunLayout::RoleOf(int32 Item) const
{
	return Item < 0 ? RoleNotInRun : ItemRole[Item];   // блокнот и оружие вне каталога
}

int32 FRunLayout::RoleMask(const TArray<int32>& Pocket) const
{
	int32 M = 0;
	for (int32 It : Pocket)
	{
		const int32 R = RoleOf(It);
		if (R >= 0 && R < NumSig)
		{
			M |= 1 << R;
		}
	}
	return M;
}

int32 FRunLayout::PocketKey(const TArray<int32>& Pocket) const
{
	return RoomKey(RoleMask(Pocket), Pocket.Contains(Notebook));
}

void FRunLayout::Look(int32 Key, int32& OutType, int32& OutSwitches) const
{
	if (Key == Anchor)
	{
		OutType = Bridge;
		OutSwitches = BridgeSwitches;
		return;
	}
	if (Key == 0)
	{
		OutType = Living;
		OutSwitches = 0;
		return;
	}
	if (Key == FinalMask)
	{
		OutType = Engine;
		OutSwitches = EngineSwitches;
		return;
	}
	OutType = GOrdinaryTypes[Hash32({ Seed, DRoomType, static_cast<uint32>(Key) }) % static_cast<uint32>(UE_ARRAY_COUNT(GOrdinaryTypes))];
	OutSwitches = 0;
	for (int32 R = 0; R < NumSig; ++R)
	{
		if (Key & (1 << R))
		{
			OutSwitches |= 1 << SwitchOf[OutType][R];
		}
	}
}

int32 FRunLayout::AnomalyOf(int32 Key) const
{
	if (RoomClass(Key) != ClsGuess)
	{
		return 0;
	}
	FRng Rng({ Seed, DAnomaly, static_cast<uint32>(Key) });
	if (!Rng.Chance(Cfg.PGuess))                                     // rng: есть ли аномалия у набора
	{
		return 0;
	}
	return 1 + static_cast<int32>(Rng.Below(NumThreats));            // rng: вид
}

void FRunLayout::AheadNote(int32 Level, int32& OutKind, TArray<int32>& OutItems) const
{
	const TArray<int32>& RI = RoleItem;
	if (Level == 0)
	{
		OutKind = NoteNextKey;
		OutItems = { RI[RoleK1], RI[RoleL] };
	}
	else if (Level == 1)
	{
		OutKind = NoteNextKey;
		OutItems = { RI[RoleK2], RI[RoleK1] };
	}
	else if (Level == 2)
	{
		OutKind = NoteNextKey;
		OutItems = { RI[RoleK3], RI[RoleK1], RI[RoleK2] };
	}
	else
	{
		OutKind = NoteEngineSet;
		OutItems = { RI[RoleK1], RI[RoleK2], RI[RoleK3], RI[RoleL] };
	}
}

FRunNote FRunLayout::MakeNote(FRng& Rng, int32 Kind, const TArray<int32>& Items) const
{
	FRunNote Note;
	Note.Kind = Kind;
	Note.Items = Items;
	Note.Tpl = static_cast<int32>(Rng.Below(static_cast<uint32>(TemplateCount(Kind))));
	return Note;
}

TArray<FRunNote> FRunLayout::ChainNotes(int32 Key) const
{
	// Порядок вызовов Rng повторяет эталон.
	const int32 Level = ChainLevel(Key);
	FRng Rng({ Seed, DNotes, static_cast<uint32>(Key) });
	TArray<FRunNote> Notes;
	int32 Kind = 0;
	TArray<int32> Items;
	AheadNote(Level, Kind, Items);                                   // записка на шаг вперёд есть всегда
	Notes.Add(MakeNote(Rng, Kind, Items));                           // rng: шаблон
	if (Rng.Chance(Cfg.PExtraNote))                                  // rng: есть ли вторая записка
	{
		const int32 Pick = Rng.Weighted({ 2, 2, 1 });                // rng: вид
		if (Pick == 0)
		{
			Kind = NoteLoopExit;
			Items = { RoleItem[GChainTarget[Level]] };
		}
		else if (Pick == 1)
		{
			Kind = NoteUseless;
			Items = { Dummies[static_cast<int32>(Rng.Below(static_cast<uint32>(Dummies.Num())))] };   // rng: предмет
		}
		else
		{
			DangerNote(Rng, Kind, Items);                            // rng: пара или пустышка
		}
		Notes.Add(MakeNote(Rng, Kind, Items));                       // rng: шаблон
	}
	return Notes;
}

TArray<FRunNote> FRunLayout::GuessNotes(int32 Key) const
{
	FRng Rng({ Seed, DNotes, static_cast<uint32>(Key) });
	TArray<FRunNote> Notes;
	if (!Rng.Chance(Cfg.PGuessNote))
	{
		return Notes;
	}
	int32 Kind = 0;
	TArray<int32> Items;
	if (Rng.Weighted({ 2, 1 }) == 0)
	{
		Kind = NoteUseless;
		Items = { Dummies[static_cast<int32>(Rng.Below(static_cast<uint32>(Dummies.Num())))] };
	}
	else
	{
		DangerNote(Rng, Kind, Items);
	}
	Notes.Add(MakeNote(Rng, Kind, Items));
	return Notes;
}

TArray<int32> FRunLayout::DrawFiller(FRng& Rng, int32 N) const
{
	TArray<int32> Pool = FillerPool;
	TArray<int32> Weights = FillerWeights;
	TArray<int32> Out;
	const int32 Count = FMath::Min(N, Pool.Num());
	for (int32 K = 0; K < Count; ++K)
	{
		const int32 I = Rng.Weighted(Weights);
		Out.Add(Pool[I]);
		Pool.RemoveAt(I);
		Weights.RemoveAt(I);
	}
	return Out;
}

bool FRunLayout::TargetOf(int32 Key, int32& OutItem) const
{
	if (Key == 0 || RoomClass(Key) != ClsChain)
	{
		return false;
	}
	OutItem = RoleItem[GChainTarget[ChainLevel(Key)]];
	return true;
}

FRunRoomContent FRunLayout::Room(int32 Key) const
{
	FRunRoomContent Out;
	Out.Key = Key;
	Look(Key, Out.RoomType, Out.Switches);
	const int32 Cls = RoomClass(Key);
	const uint32 UKey = static_cast<uint32>(Key);

	if (Cls == ClsEngine)
	{
		FRng Rng({ Seed, DNotes, UKey });
		Out.Notes.Add(MakeNote(Rng, NoteFinale, {}));
		return Out;
	}

	FRng IRng({ Seed, DItems, UKey });
	int32 Target = 0;
	if (TargetOf(Key, Target))
	{
		Out.Items.Add(Target);
	}
	const int32 NFill = Cfg.FillerMin + static_cast<int32>(IRng.Below(static_cast<uint32>(Cfg.FillerMax - Cfg.FillerMin + 1)));   // rng: сколько прочих
	Out.Items.Append(DrawFiller(IRng, NFill));                                                                                  // rng: какие
	Out.Notes = Cls == ClsChain ? ChainNotes(Key) : GuessNotes(Key);
	Out.Anomaly = AnomalyOf(Key);
	return Out;
}

FRunRoomContent FRunLayout::StartRoom() const
{
	FRunRoomContent Out = Room(Anchor);
	Out.Items.Insert(Weapon, 0);
	Out.Items.Insert(Notebook, 0);
	return Out;
}
