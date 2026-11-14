#include "RunGenDumpCommandlet.h"

#include "Dom/JsonObject.h"
#include "Misc/FileHelper.h"
#include "Misc/Parse.h"
#include "Misc/Paths.h"
#include "RunGen.h"
#include "Serialization/JsonSerializer.h"
#include "Serialization/JsonWriter.h"

using namespace RunGen;

namespace
{
	using FObj = TSharedRef<FJsonObject>;
	using FArr = TArray<TSharedPtr<FJsonValue>>;

	TSharedPtr<FJsonValue> Num(double V) { return MakeShared<FJsonValueNumber>(V); }
	TSharedPtr<FJsonValue> Str(const FString& V) { return MakeShared<FJsonValueString>(V); }

	FArr Names(const TArray<int32>& Items)
	{
		FArr Out;
		for (int32 It : Items)
		{
			Out.Add(Str(ItemName(It)));
		}
		return Out;
	}

	FArr Ints(const TArray<int32>& Values)
	{
		FArr Out;
		for (int32 V : Values)
		{
			Out.Add(Num(V));
		}
		return Out;
	}

	FString KeyName(int32 Key, int32 NumSig)
	{
		if (Key == 0)
		{
			return TEXT("{} (empty pocket)");
		}
		if (Key == Anchor)
		{
			return TEXT("{} (notebook only)");
		}
		FString S;
		for (int32 R = 0; R < NumSig; ++R)
		{
			if (Key & (1 << R))
			{
				S += (S.IsEmpty() ? TEXT("") : TEXT(", ")) + RoleName(R);
			}
		}
		return TEXT("{") + S + TEXT("}");
	}

	FObj RoomJson(const FRunRoomContent& Room)
	{
		FObj O = MakeShared<FJsonObject>();
		O->SetNumberField(TEXT("key"), Room.Key);
		O->SetStringField(TEXT("type"), RoomTypeName(Room.RoomType));
		O->SetNumberField(TEXT("switches"), Room.Switches);
		O->SetStringField(TEXT("anomaly"), AnomalyName(Room.Anomaly));
		O->SetArrayField(TEXT("items"), Names(Room.Items));
		FArr Notes;
		for (const FRunNote& N : Room.Notes)
		{
			FObj J = MakeShared<FJsonObject>();
			J->SetStringField(TEXT("kind"), NoteKindName(N.Kind));
			J->SetArrayField(TEXT("items"), Names(N.Items));
			J->SetNumberField(TEXT("tpl"), N.Tpl);
			J->SetStringField(TEXT("text"), N.Text());
			Notes.Add(MakeShared<FJsonValueObject>(J));
		}
		O->SetArrayField(TEXT("notes"), Notes);
		return O;
	}

	FObj Dump(uint32 Seed)
	{
		const FRunLayout Layout(Seed);
		const FRunConfig& Cfg = Layout.Cfg;
		const int32 NumSig = Layout.NumSig;
		const TArray<int32>& RI = Layout.RoleItem;
		FObj Root = MakeShared<FJsonObject>();

		FObj Config = MakeShared<FJsonObject>();
		Config->SetNumberField(TEXT("items_in_run"), Cfg.ItemsInRun);
		Config->SetNumberField(TEXT("health"), Cfg.Health);
		Config->SetNumberField(TEXT("p_guess"), Cfg.PGuess);
		Config->SetNumberField(TEXT("filler_min"), Cfg.FillerMin);
		Config->SetNumberField(TEXT("filler_max"), Cfg.FillerMax);
		Config->SetNumberField(TEXT("dummy_weight"), Cfg.DummyWeight);
		Config->SetNumberField(TEXT("extras"), Cfg.Extras);
		Config->SetNumberField(TEXT("extra_weight"), Cfg.ExtraWeight);
		Config->SetNumberField(TEXT("p_extra_note"), Cfg.PExtraNote);
		Config->SetNumberField(TEXT("p_guess_note"), Cfg.PGuessNote);
		Root->SetObjectField(TEXT("config"), Config);

		FObj Desc = MakeShared<FJsonObject>();
		Desc->SetNumberField(TEXT("seed"), Layout.Seed);
		FObj Roles = MakeShared<FJsonObject>();
		for (int32 R = 0; R < NumSig; ++R)
		{
			Roles->SetStringField(RoleName(R), ItemName(RI[R]));
		}
		Desc->SetObjectField(TEXT("roles"), Roles);
		Desc->SetArrayField(TEXT("dummies"), Names(Layout.Dummies));
		Desc->SetArrayField(TEXT("chain"), Names({ RI[RoleL], RI[RoleK1], RI[RoleK2], RI[RoleK3] }));
		Desc->SetArrayField(TEXT("final_set"), Names({ RI[RoleK1], RI[RoleK2], RI[RoleK3] }));
		FObj ChainTypes = MakeShared<FJsonObject>();
		const TPair<const TCHAR*, int32> ChainKeys[] = {
			{ TEXT("notebook only"), Anchor }, { TEXT("empty pocket"), 0 }, { TEXT("L"), MaskL },
			{ TEXT("L,K1"), MaskL | MaskK1 }, { TEXT("K1"), MaskK1 }, { TEXT("L,K1,K2"), MaskL | MaskK1 | MaskK2 },
			{ TEXT("K1,K2"), MaskK1 | MaskK2 }, { TEXT("K1,K2,K3"), FinalMask } };
		for (const auto& P : ChainKeys)
		{
			int32 Type = 0, Sw = 0;
			Layout.Look(P.Value, Type, Sw);
			ChainTypes->SetStringField(P.Key, RoomTypeName(Type));
		}
		Desc->SetObjectField(TEXT("chain_room_types"), ChainTypes);
		Desc->SetStringField(TEXT("notebook_first"), Layout.FirstNote.Text());
		Desc->SetNumberField(TEXT("decompression_level"), Layout.DecompLevel);
		Root->SetObjectField(TEXT("layout"), Desc);

		Root->SetArrayField(TEXT("run_items"), Names(Layout.RunItems));

		FObj SwitchOf = MakeShared<FJsonObject>();
		const int32 OrdinaryTypes[] = { Living, Lab, LifeSupport, Medbay, Cargo, Mess, Computer };
		for (int32 Type : OrdinaryTypes)
		{
			TArray<int32> Perm;
			for (int32 R = 0; R < NumSig; ++R)
			{
				Perm.Add(Layout.SwitchOf[Type][R]);
			}
			SwitchOf->SetArrayField(RoomTypeName(Type), Ints(Perm));
		}
		Root->SetObjectField(TEXT("switch_of"), SwitchOf);
		Root->SetObjectField(TEXT("start_room"), RoomJson(Layout.StartRoom()));

		FArr Looks;
		FObj Rooms = MakeShared<FJsonObject>();
		for (int32 Key : AllKeys(NumSig))
		{
			int32 Type = 0, Sw = 0;
			Layout.Look(Key, Type, Sw);
			FObj J = MakeShared<FJsonObject>();
			J->SetNumberField(TEXT("key"), Key);
			J->SetStringField(TEXT("signature"), KeyName(Key, NumSig));
			J->SetStringField(TEXT("class"), ClassName(RoomClass(Key)));
			J->SetNumberField(TEXT("level"), ChainLevel(Key));
			J->SetStringField(TEXT("type"), RoomTypeName(Type));
			J->SetNumberField(TEXT("switches"), Sw);
			J->SetStringField(TEXT("anomaly"), AnomalyName(Layout.AnomalyOf(Key)));
			Looks.Add(MakeShared<FJsonValueObject>(J));
			const int32 Cls = RoomClass(Key);
			if (Cls == ClsChain || Cls == ClsEngine)
			{
				Rooms->SetObjectField(KeyName(Key, NumSig), RoomJson(Layout.Room(Key)));
			}
		}
		// как в dump.py: все комнаты правильного пути и несколько неправильных наборов
		const int32 E1 = 1 << NumChain, E2 = 1 << (NumChain + 1);   // первые два лишних значимых предмета
		const int32 GuessKeys[] = { E1, MaskL | E2, MaskL | MaskK2, MaskK1 | MaskK2 | MaskK3 | MaskL, E1 | E2 };
		for (int32 Key : GuessKeys)
		{
			Rooms->SetObjectField(KeyName(Key, NumSig), RoomJson(Layout.Room(Key)));
		}
		Root->SetArrayField(TEXT("looks"), Looks);
		Root->SetObjectField(TEXT("rooms"), Rooms);
		return Root;
	}

	FObj RngVectors()
	{
		FObj Root = MakeShared<FJsonObject>();
		FObj Mix = MakeShared<FJsonObject>();
		for (uint32 X : { 0U, 1U, 2U, 0xFFFFFFFFU, 123456789U })
		{
			Mix->SetNumberField(FString::Printf(TEXT("%u"), X), Mix32(X));
		}
		Root->SetObjectField(TEXT("mix32"), Mix);
		Root->SetNumberField(TEXT("hash32(1,2,3)"), Hash32({ 1, 2, 3 }));
		Root->SetNumberField(TEXT("hash32()"), Hash32({}));
		FRng R({ 7, 3, 2026 });
		FArr Seq;
		for (int32 I = 0; I < 5; ++I)
		{
			Seq.Add(Num(R.NextU32()));
		}
		Root->SetArrayField(TEXT("Rng(7,3,2026).next_u32 x5"), Seq);
		TArray<int32> Arr = { 0, 1, 2, 3, 4, 5, 6, 7, 8, 9 };
		FRng({ 1 }).Shuffle(Arr);
		Root->SetArrayField(TEXT("Rng(1).shuffle(0..9)"), Ints(Arr));
		return Root;
	}

	bool Save(const FObj& Obj, const FString& Path)
	{
		FString Text;
		const TSharedRef<TJsonWriter<>> Writer = TJsonWriterFactory<>::Create(&Text);
		return FJsonSerializer::Serialize(Obj, Writer) && FFileHelper::SaveStringToFile(Text, *Path, FFileHelper::EEncodingOptions::ForceUTF8WithoutBOM);
	}
}

int32 URunGenDumpCommandlet::Main(const FString& Params)
{
	FString Out, SeedList;
	if (!FParse::Value(*Params, TEXT("Out="), Out) || !FParse::Value(*Params, TEXT("Seeds="), SeedList, false))
	{
		UE_LOG(LogTemp, Error, TEXT("RunGenDump: нужны -Out=<папка> и -Seeds=1,2,3"));
		return 1;
	}
	TArray<FString> Seeds;
	SeedList.ParseIntoArray(Seeds, TEXT(","));
	bool bOk = Save(RngVectors(), Out / TEXT("rng_vectors.json"));
	for (const FString& S : Seeds)
	{
		const uint32 Seed = static_cast<uint32>(FCString::Strtoui64(*S, nullptr, 10));
		bOk &= Save(Dump(Seed), Out / FString::Printf(TEXT("seed_%u.json"), Seed));
	}
	UE_LOG(LogTemp, Display, TEXT("RunGenDump: %d зёрен -> %s (%s)"), Seeds.Num(), *Out, bOk ? TEXT("ok") : TEXT("ошибка записи"));
	return bOk ? 0 : 1;
}
