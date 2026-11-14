#include "RunHUD.h"

#include "Engine/Canvas.h"
#include "Engine/Engine.h"
#include "Engine/Font.h"
#include "Fonts/CompositeFont.h"
#include "Misc/Paths.h"
#include "Engine/Texture2D.h"
#include "EngineUtils.h"
#include "RunDirector.h"
#include "RunGen.h"

// Шрифт из файла Content/Fonts: объект шрифта на время игры, буквы рисует кэш Slate — чёткие при любом масштабе.
// Size — кегль при масштабе 1 (у Roboto движка, под который подобраны все масштабы экрана, он 9).
static UFont* LoadFileFont(UObject* Outer, const TCHAR* File, int32 Size)
{
	const FString Path = FPaths::ProjectContentDir() / TEXT("Fonts") / File;
	if (!FPaths::FileExists(Path))
	{
		UE_LOG(LogTemp, Warning, TEXT("Run: нет шрифта %s, остаётся шрифт движка"), *Path);
		return nullptr;
	}
	UFont* Font = NewObject<UFont>(Outer);
	Font->FontCacheType = EFontCacheType::Runtime;
	Font->LegacyFontSize = Size;
	Font->LegacyFontName = TEXT("Default");
	Font->GetMutableInternalCompositeFont() = FCompositeFont(TEXT("Default"), Path, EFontHinting::Default, EFontLoadingPolicy::LazyLoad);
	return Font;
}

UFont* ARunHUD::Hud()
{
	if (!bFontsLoaded)
	{
		bFontsLoaded = true;
		HudFont = LoadFileFont(this, TEXT("ChakraPetch-Medium.ttf"), 9);
		HandFont = LoadFileFont(this, TEXT("Kalam-Regular.ttf"), 10);
	}
	return HudFont ? HudFont.Get() : GEngine->GetMediumFont();
}

UFont* ARunHUD::Hand()
{
	Hud();
	return HandFont ? HandFont.Get() : GEngine->GetMediumFont();
}

void ARunHUD::Centered(const FString& Text, float Y, const FLinearColor& Color, float Scale)
{
	float W = 0.f, H = 0.f;
	GetTextSize(Text, W, H, Hud(), Scale);
	DrawText(Text, Color, (Canvas->SizeX - W) * 0.5f, Y, Hud(), Scale);
}

// Разбивает текст на строки не шире MaxWidth: длинная записка не уезжает за край экрана.
static TArray<FString> WrapText(AHUD* Hud, const FString& Text, UFont* Font, float Scale, float MaxWidth)
{
	TArray<FString> Out, Paragraphs;
	Text.ParseIntoArrayLines(Paragraphs);
	for (const FString& Paragraph : Paragraphs)
	{
		TArray<FString> Words;
		Paragraph.ParseIntoArray(Words, TEXT(" "));
		FString Line;
		for (const FString& Word : Words)
		{
			const FString Try = Line.IsEmpty() ? Word : Line + TEXT(" ") + Word;
			float W = 0.f, H = 0.f;
			Hud->GetTextSize(Try, W, H, Font, Scale);
			if (W > MaxWidth && !Line.IsEmpty())
			{
				Out.Add(Line);
				Line = Word;
			}
			else
			{
				Line = Try;
			}
		}
		Out.Add(Line);
	}
	return Out;
}

// Цвета закладок: по кругу, у записки в блокноте полоска того же цвета.
static FLinearColor BookmarkColor(int32 Index, float Alpha)
{
	static const FLinearColor Colors[] = { FLinearColor(0.85f, 0.25f, 0.2f), FLinearColor(0.95f, 0.7f, 0.15f), FLinearColor(0.3f, 0.65f, 0.35f),
		FLinearColor(0.25f, 0.5f, 0.85f), FLinearColor(0.65f, 0.35f, 0.75f) };
	FLinearColor C = Colors[((Index % 5) + 5) % 5];
	C.A = Alpha;
	return C;
}

// Обрезает строку до ширины, с многоточием.
static FString FitText(AHUD* Hud, FString Text, UFont* Font, float Scale, float MaxWidth)
{
	float W = 0.f, H = 0.f;
	Hud->GetTextSize(Text, W, H, Font, Scale);
	if (W <= MaxWidth)
	{
		return Text;
	}
	while (Text.Len() > 1)
	{
		Text.LeftChopInline(1);
		Hud->GetTextSize(Text + TEXT("..."), W, H, Font, Scale);
		if (W <= MaxWidth)
		{
			break;
		}
	}
	return Text.TrimEnd() + TEXT("...");
}

// Разворот блокнота: лист 4:3 из карточки ui/notebook-page, левая и правая страницы — его половины.
// Записи по порядку, старые в начале; не влезшая на страницу запись целиком переносится на следующую.
// Записки — закладки: ярлычки над правой страницей, у самой записки цветная полоска на полях.
FString ARunHUD::DrawNotebook(ARunDirector& D, float S, float X0, float Y0, float W, float H)
{
	UFont* Font = Hand();   // в блокноте пишут от руки
	if (!bPageLoaded)
	{
		PageTexture = LoadObject<UTexture2D>(nullptr, TEXT("/Game/UI/T_NotebookPage.T_NotebookPage"));
		bPageLoaded = true;
	}
	const float Pad = W * 0.05f, PageW = W * 0.5f - 2.f * Pad;
	const TArray<FString>& Marks = D.GetBookmarks();
	const int32 Chosen = D.GetBookmark();
	// ярлычки закладок торчат над листом; выбранный выше остальных
	if (Marks.Num() > 0)
	{
		const float Gap = 4.f * S, TabW = FMath::Min(28.f * S, (W * 0.5f - Pad) / Marks.Num() - Gap);
		for (int32 I = 0; I < Marks.Num(); ++I)
		{
			const float TH = (I == Chosen ? 30.f : 20.f) * S, TX = X0 + W * 0.5f + Pad * 0.5f + I * (TabW + Gap);
			DrawRect(BookmarkColor(I, I == Chosen ? 1.f : 0.75f), TX, Y0 - TH + 4.f * S, TabW, TH);
			const FString Num = FString::FromInt(I + 1);
			float NW = 0.f, NH = 0.f;
			GetTextSize(Num, NW, NH, Font, 0.8f * S);
			if (NW < TabW)
			{
				DrawText(Num, FLinearColor::White, TX + (TabW - NW) * 0.5f, Y0 - TH + 6.f * S, Font, 0.8f * S);
			}
		}
	}
	DrawRect(FLinearColor(0.f, 0.f, 0.f, 0.45f), X0 + 8.f * S, Y0 + 10.f * S, W, H);   // тень под блокнотом
	if (PageTexture)
	{
		DrawTexture(PageTexture, X0, Y0, W, H, 0.f, 0.f, 1.f, 1.f);
	}
	else
	{
		DrawRect(FLinearColor(0.93f, 0.92f, 0.88f), X0, Y0, W, H);
	}
	// корешок между страницами
	DrawRect(FLinearColor(0.f, 0.f, 0.f, 0.08f), X0 + W * 0.5f - 12.f * S, Y0, 24.f * S, H);
	DrawRect(FLinearColor(0.f, 0.f, 0.f, 0.2f), X0 + W * 0.5f - 1.5f * S, Y0, 3.f * S, H);

	const float Top = Y0 + Pad + 36.f * S, Bottom = Y0 + H - Pad - 22.f * S;
	const float LineH = 21.f * S, Scale = 0.95f * S;
	struct FLine
	{
		FString Text;
		bool bOwn;
		float Y;
		int32 Mark;   // номер закладки, если строка — из записки
	};
	TArray<TArray<FLine>> Pages;
	Pages.AddDefaulted();
	float Y = Top;
	int32 ChosenPage = -1;
	for (const FString& Entry : D.GetJournal())
	{
		// свои строки персонажа («+ …») — бирюзовыми чернилами, записки — тёмными
		const bool bOwn = Entry.StartsWith(TEXT("+ "));
		const int32 Mark = bOwn ? INDEX_NONE : Marks.IndexOfByKey(Entry);
		const TArray<FString> Lines = WrapText(this, bOwn ? Entry.Mid(2) : Entry, Font, Scale, PageW);
		if (Y + Lines.Num() * LineH > Bottom && Y > Top)
		{
			Pages.AddDefaulted();
			Y = Top;
		}
		if (Mark != INDEX_NONE && Mark == Chosen)
		{
			ChosenPage = Pages.Num() - 1;
		}
		for (const FString& Line : Lines)
		{
			if (Y + LineH > Bottom)
			{
				Pages.AddDefaulted();   // запись длиннее страницы: продолжается на следующей
				Y = Top;
			}
			Pages.Last().Add({ Line, bOwn, Y, Mark });
			Y += LineH;
		}
		Y += LineH * 0.7f;
	}
	const int32 NumSpreads = (Pages.Num() + 1) / 2;
	if (D.ConsumeBookmarkJump() && ChosenPage >= 0)
	{
		D.SetJournalPage(ChosenPage / 2);
	}
	D.ClampJournalPage(NumSpreads);
	const int32 Spread = D.GetJournalPage();
	const FLinearColor Ink(0.12f, 0.15f, 0.21f), OwnInk(0.05f, 0.4f, 0.43f), Faint(0.12f, 0.15f, 0.21f, 0.5f);
	for (int32 Side = 0; Side < 2; ++Side)
	{
		const int32 Page = Spread * 2 + Side;
		const float PX = X0 + Side * W * 0.5f + Pad;
		if (Page == 0)
		{
			DrawText(TEXT("NOTEBOOK"), OwnInk, PX, Y0 + Pad, Font, 1.2f * S);
		}
		if (!Pages.IsValidIndex(Page))
		{
			continue;
		}
		for (const FLine& L : Pages[Page])
		{
			if (L.Mark != INDEX_NONE)
			{
				const bool bChosen = L.Mark == Chosen;
				DrawRect(BookmarkColor(L.Mark, bChosen ? 0.95f : 0.45f), PX - (bChosen ? 13.f : 11.f) * S, L.Y, (bChosen ? 6.f : 3.f) * S, LineH);
			}
			DrawText(L.Text, L.bOwn ? OwnInk : Ink, PX, L.Y, Font, Scale);
		}
		const FString Num = FString::FromInt(Page + 1);
		float NW = 0.f, NH = 0.f;
		GetTextSize(Num, NW, NH, Font, 0.85f * S);
		DrawText(Num, Faint, Side == 0 ? PX : PX + PageW - NW, Y0 + H - Pad - 4.f * S, Font, 0.85f * S);
	}
	return NumSpreads > 1 ? FString::Printf(TEXT("Pages %d-%d of %d      [Wheel] or [Left] [Right] turn the page      "),
		Spread * 2 + 1, FMath::Min(Spread * 2 + 2, Pages.Num()), Pages.Num()) : FString();
}

// Меню на Tab (решение автора 15.11): блокнот с закладками записок, справа — список записок, скафандр, карман.
// Игра под ним идёт: время не останавливается.
void ARunHUD::DrawMenu(ARunDirector& D, float S)
{
	UFont* Font = Hud();
	const float SX = Canvas->SizeX, SY = Canvas->SizeY;
	const FLinearColor Teal(0.37f, 0.78f, 0.79f), Dim(1.f, 1.f, 1.f, 0.55f);
	DrawRect(FLinearColor(0.f, 0.f, 0.f, 0.35f), 0.f, 0.f, SX, SY);

	const float M = 18.f * S, PanelW = FMath::Min(300.f * S, SX * 0.26f);
	float H = SY * 0.72f, W = H * 4.f / 3.f;
	if (W > SX - PanelW - 3.f * M)
	{
		W = SX - PanelW - 3.f * M;
		H = W * 0.75f;
	}
	const float X0 = (SX - W - M - PanelW) * 0.5f, Y0 = SY * 0.075f;
	FString PagesHelp;
	if (D.HasNotebook())
	{
		PagesHelp = DrawNotebook(D, S, X0, Y0, W, H);
	}
	else
	{
		DrawRect(FLinearColor(0.f, 0.f, 0.f, 0.6f), X0, Y0, W, H);
		const TCHAR* Lines[] = { TEXT("The notebook is not with you."), TEXT("The notes you read are kept in it.") };
		for (int32 I = 0; I < 2; ++I)
		{
			float TW = 0.f, TH = 0.f;
			GetTextSize(Lines[I], TW, TH, Font, 1.2f * S);
			DrawText(Lines[I], I == 0 ? FLinearColor::White : Dim, X0 + (W - TW) * 0.5f, Y0 + H * 0.45f + I * 30.f * S, Font, 1.2f * S);
		}
	}

	// боковая панель
	const float PX = X0 + W + M, In = 14.f * S, TextW = PanelW - 2.f * In, RowH = 24.f * S;
	DrawRect(FLinearColor(0.f, 0.f, 0.f, 0.7f), PX, Y0, PanelW, H);
	float Y = Y0 + In;
	const auto Header = [&](const TCHAR* Text)
	{
		DrawText(Text, Teal, PX + In, Y, Font, 1.05f * S);
		Y += RowH;
		DrawRect(FLinearColor(0.37f, 0.78f, 0.79f, 0.5f), PX + In, Y - 3.f * S, TextW, 1.5f * S);
		Y += 5.f * S;
	};
	const auto Row = [&](const FString& Text, const FLinearColor& Color)
	{
		for (const FString& Line : WrapText(this, Text, Font, 0.95f * S, TextW))
		{
			DrawText(Line, Color, PX + In, Y, Font, 0.95f * S);
			Y += RowH * 0.9f;
		}
	};

	// внизу панели — скафандр и карман; записки занимают всё, что выше
	const float FootH = 9.6f * RowH;
	const float NotesBottom = Y0 + H - FootH;
	Header(TEXT("NOTES"));
	const TArray<FString>& Marks = D.GetBookmarks();
	const int32 Chosen = D.GetBookmark();
	if (Marks.Num() == 0)
	{
		Row(TEXT("No notes read yet."), Dim);
	}
	else
	{
		const bool bBook = D.HasNotebook();
		const int32 Fit = FMath::Max(1, FMath::FloorToInt32((NotesBottom - Y - RowH) / RowH));
		const int32 First = FMath::Clamp(FMath::Max(Chosen, 0) - Fit / 2, 0, FMath::Max(0, Marks.Num() - Fit));
		for (int32 I = First; I < Marks.Num() && I < First + Fit; ++I)
		{
			const bool bChosen = bBook && I == Chosen;
			if (bChosen)
			{
				DrawRect(FLinearColor(0.37f, 0.78f, 0.79f, 0.25f), PX + In * 0.4f, Y - 2.f * S, PanelW - In * 0.8f, RowH - 2.f * S);
			}
			DrawRect(BookmarkColor(I, bBook ? 1.f : 0.4f), PX + In, Y + 2.f * S, 5.f * S, RowH - 10.f * S);
			const FString Label = FString::Printf(TEXT("%d  %s"), I + 1, *Marks[I].Replace(TEXT("\n"), TEXT(" ")));
			DrawText(FitText(this, Label, Font, 0.9f * S, TextW - 12.f * S), bChosen ? FLinearColor::White : (bBook ? FLinearColor(1.f, 1.f, 1.f, 0.8f) : Dim),
				PX + In + 12.f * S, Y, Font, 0.9f * S);
			Y += RowH;
		}
		Y += 2.f * S;
		DrawText(bBook ? TEXT("[Up] [Down] open a bookmark") : TEXT("Bookmarks are in the notebook"), Teal, PX + In, Y, Font, 0.85f * S);
	}

	Y = NotesBottom;
	Header(TEXT("SPACE SUIT"));
	if (D.IsSuitOn())
	{
		Row(TEXT("You are wearing it."), FLinearColor::White);
		Row(D.IsInVacuum() ? TEXT("No air here - keep it on") : TEXT("[T] take it off"), Teal);
	}
	else
	{
		Row(D.WasSuitWorn() ? TEXT("Left where you took it off.") : TEXT("You have no suit."), Dim);
		Row(TEXT("[E] next to it - put it on"), Teal);
	}
	Y += RowH * 0.5f;
	Header(TEXT("POCKET"));
	Row(TEXT("[1]-[4] look closer at an item"), Teal);
	Row(TEXT("[G] drop what is in your hand"), Teal);

	const FString Help = PagesHelp + TEXT("[Tab] close");
	float HW = 0.f, HH = 0.f;
	GetTextSize(Help, HW, HH, Font, 1.0f * S);
	DrawRect(FLinearColor(0.f, 0.f, 0.f, 0.6f), (SX - HW) * 0.5f - 12.f * S, Y0 + H + 12.f * S, HW + 24.f * S, HH + 10.f * S);
	Centered(Help, Y0 + H + 17.f * S, Teal, 1.0f * S);
}

void ARunHUD::DrawHUD()
{
	Super::DrawHUD();
	if (!Canvas)
	{
		return;
	}
	if (!Director.IsValid())
	{
		TActorIterator<ARunDirector> It(GetWorld());
		if (It)
		{
			Director = *It;
		}
		if (!Director.IsValid())
		{
			return;
		}
	}
	const ARunDirector& D = *Director;
	UFont* Font = Hud();
	const float SX = Canvas->SizeX, SY = Canvas->SizeY;
	const float S = FMath::Max(1.f, SY / 720.f);   // масштаб под высоту экрана

	// карман: четыре слота снизу по центру
	const float SlotW = 170.f * S, SlotH = 44.f * S, Gap = 10.f * S;
	const float X0 = (SX - 4.f * SlotW - 3.f * Gap) * 0.5f, Y0 = SY - SlotH - 28.f * S;
	const TArray<int32>& Pocket = D.GetPocket();
	const int32 Held = D.GetHeldSlot();
	for (int32 I = 0; I < RunGen::PocketSlots; ++I)
	{
		const float X = X0 + I * (SlotW + Gap);
		DrawRect(FLinearColor(0.f, 0.f, 0.f, I == Held ? 0.75f : 0.55f), X, Y0, SlotW, SlotH);
		if (I == Held)
		{
			// вещь в руке: слот в бирюзовой рамке и чуть приподнят надписью
			const float B = 2.f * S;
			const FLinearColor Frame(0.37f, 0.78f, 0.79f, 0.95f);
			DrawRect(Frame, X, Y0, SlotW, B);
			DrawRect(Frame, X, Y0 + SlotH - B, SlotW, B);
			DrawRect(Frame, X, Y0, B, SlotH);
			DrawRect(Frame, X + SlotW - B, Y0, B, SlotH);
			DrawText(TEXT("IN HAND"), Frame, X + 4.f * S, Y0 - 18.f * S, Font, 0.8f * S);
		}
		DrawText(FString::Printf(TEXT("%d"), I + 1), FLinearColor(1.f, 1.f, 1.f, 0.45f), X + 6.f * S, Y0 + 3.f * S, Font, 0.9f * S);
		if (Pocket.IsValidIndex(I))
		{
			const FLinearColor Ink = Pocket[I] == RunGen::Notebook ? FLinearColor(0.45f, 0.9f, 0.95f)
				: Pocket[I] == RunGen::Weapon ? FLinearColor(1.f, 0.6f, 0.3f)
				: Pocket[I] == RunGen::Medkit ? FLinearColor(0.55f, 1.f, 0.55f) : FLinearColor::White;
			if (Pocket[I] == RunGen::Notebook && D.HasUnreadJournal())
			{
				DrawRect(FLinearColor(0.37f, 0.78f, 0.79f), X + SlotW - 16.f * S, Y0 + 6.f * S, 9.f * S, 9.f * S);   // есть новая запись
			}
			DrawText(RunGen::ItemName(Pocket[I]), Ink,
				X + 24.f * S, Y0 + 13.f * S, Font, 1.1f * S);
		}
	}

	// шлюз считывает карман: пока створки закрыты, слоты вспыхивают по очереди — все, без разбора
	const float Scan = D.GetTransitionAlpha();
	if (Scan >= 0.f)
	{
		const int32 Lit = FMath::Min(RunGen::PocketSlots - 1, FMath::FloorToInt32(Scan * RunGen::PocketSlots));
		const float X = X0 + Lit * (SlotW + Gap), B = 3.f * S;
		const FLinearColor Teal(0.37f, 0.78f, 0.79f, 0.95f);
		DrawRect(Teal, X - B, Y0 - B, SlotW + 2 * B, B);
		DrawRect(Teal, X - B, Y0 + SlotH, SlotW + 2 * B, B);
		DrawRect(Teal, X - B, Y0, B, SlotH);
		DrawRect(Teal, X + SlotW, Y0, B, SlotH);
	}
	// где я: мелко справа от кармана, крупно на пару секунд при входе
	if (!D.GetRoomName().IsEmpty())
	{
		DrawText(D.GetRoomName(), FLinearColor(1.f, 1.f, 1.f, 0.6f), X0 + 4.f * SlotW + 3.f * Gap + 22.f * S, Y0 + 13.f * S, Font, 1.0f * S);
		const float Title = D.GetRoomTitleAlpha();
		if (Title > 0.f && Scan < 0.f)
		{
			const float A = FMath::Min(1.f, Title * 3.f);
			Centered(D.GetRoomName(), SY * 0.27f, FLinearColor(1.f, 1.f, 1.f, A), 2.6f * S);
			if (D.IsRoomFamiliar())
			{
				Centered(TEXT("You have been here"), SY * 0.27f + 46.f * S, FLinearColor(0.37f, 0.78f, 0.79f, A), 1.1f * S);
			}
		}
	}

	// здоровье: полоса из 100 (решение автора 14.11). Светлый хвост тает через полсекунды после попадания —
	// видно, сколько отняло; после аптечки полоса на миг зеленеет
	const float Hp = D.GetHealth(), MaxHp = ARunDirector::MaxHealth;
	if (Hp >= LagHealth)
	{
		LagHealth = Hp;
	}
	else if (D.GetHurtFlash() <= 0.f)
	{
		LagHealth = FMath::Max(Hp, LagHealth - 60.f * GetWorld()->GetDeltaSeconds());
	}
	{
		const float BX = 28.f * S, BY = 30.f * S, BW = 240.f * S, BH = 14.f * S, B = 2.f * S;
		DrawRect(FLinearColor(0.f, 0.f, 0.f, 0.55f), BX - B, BY - B, BW + 2.f * B, BH + 2.f * B);
		DrawRect(FLinearColor(1.f, 0.85f, 0.7f, 0.85f), BX, BY, BW * LagHealth / MaxHp, BH);
		const FLinearColor Fill = FLinearColor::LerpUsingHSV(FLinearColor(0.85f, 0.2f, 0.15f, 0.95f), FLinearColor(0.3f, 0.9f, 0.4f, 0.95f), D.GetHealFlash());
		DrawRect(Fill, BX, BY, BW * Hp / MaxHp, BH);
		DrawText(FString::Printf(TEXT("%d"), FMath::CeilToInt32(Hp)), FLinearColor::White, BX + BW + 10.f * S, BY - 4.f * S, Font, 1.0f * S);
	}
	if (Hp > 0.f && Hp <= 25.f && D.GetPhase() == ERunPhase::Playing)
	{
		// здоровья на одно-два попадания: края экрана пульсируют красным
		const float Pulse = 0.18f + 0.14f * FMath::Sin(GetWorld()->GetTimeSeconds() * 5.f);
		const float E = 26.f * S;
		const FLinearColor Red(0.8f, 0.05f, 0.02f, Pulse);
		DrawRect(Red, 0.f, 0.f, SX, E);
		DrawRect(Red, 0.f, SY - E, SX, E);
		DrawRect(Red, 0.f, E, E, SY - 2.f * E);
		DrawRect(Red, SX - E, E, E, SY - 2.f * E);
	}
	if (D.IsEngineFixed())
	{
		DrawText(TEXT("ENGINES ONLINE - return to the bridge"), FLinearColor(0.45f, 0.9f, 0.95f), 28.f * S, 62.f * S, Font, 1.1f * S);
	}
	// клавиши не висят на экране постоянно: каждая показывается один раз, когда впервые нужна
	const FString Tip = D.GetTip();
	if (!Tip.IsEmpty())
	{
		float TW = 0.f, TH = 0.f;
		GetTextSize(Tip, TW, TH, Font, 1.15f * S);
		DrawRect(FLinearColor(0.f, 0.f, 0.f, 0.6f), (SX - TW) * 0.5f - 14.f * S, SY * 0.115f - 6.f * S, TW + 28.f * S, TH + 12.f * S);
		Centered(Tip, SY * 0.115f, FLinearColor(0.37f, 0.78f, 0.79f), 1.15f * S);
	}

	// попадание: красная вспышка
	const float Flash = D.GetHurtFlash();
	if (Flash > 0.f)
	{
		DrawRect(FLinearColor(0.8f, 0.05f, 0.02f, 0.4f * Flash), 0.f, 0.f, SX, SY);
	}
	const float Heal = D.GetHealFlash();
	if (Heal > 0.f)
	{
		DrawRect(FLinearColor(0.2f, 0.85f, 0.4f, 0.22f * Heal), 0.f, 0.f, SX, SY);
	}
	// удар: короткий белый росчерк поперёк экрана
	const float Swing = D.GetSwingFlash();
	if (Swing > 0.f)
	{
		const float CX = SX * 0.5f, CY = SY * 0.55f, R = 150.f * S, Sweep = (1.f - Swing) * 2.f - 1.f;
		DrawLine(CX + Sweep * R - 60.f * S, CY - 50.f * S, CX + Sweep * R + 60.f * S, CY + 50.f * S, FLinearColor(1.f, 1.f, 1.f, Swing), 5.f * S);
	}
	// преследователь ещё за дверью: предупреждение и метка двери, через которую он войдёт
	if (D.GetFollowers() > 0)
	{
		Centered(TEXT("IT IS COMING AFTER YOU"), 26.f * S, FLinearColor(1.f, 0.4f, 0.25f), 1.25f * S);
		FVector Door;
		if (D.GetFollowerDoor(Door))
		{
			const FLinearColor Warn(1.f, 0.4f, 0.25f);
			const FVector Scr = Project(Door);
			const float Pad = 70.f * S;
			float X = Scr.X, Y = Scr.Y;
			if (Scr.Z <= 0.f)
			{
				X = SX - X;      // дверь за спиной: проекция зеркальная, метка прижимается к низу
				Y = SY;
			}
			X = FMath::Clamp(X, Pad, SX - Pad);
			Y = FMath::Clamp(Y, Pad + 40.f * S, Y0 - 90.f * S);
			const float M = 11.f * S;
			DrawLine(X, Y - M, X + M, Y, Warn, 3.f * S);
			DrawLine(X + M, Y, X, Y + M, Warn, 3.f * S);
			DrawLine(X, Y + M, X - M, Y, Warn, 3.f * S);
			DrawLine(X - M, Y, X, Y - M, Warn, 3.f * S);
			DrawText(TEXT("THIS DOOR"), Warn, X + 18.f * S, Y - 9.f * S, Font, 0.95f * S);
		}
	}
	else if (D.GetEnemiesHere() > 0 && !D.HasWeapon())
	{
		Centered(TEXT("You are unarmed"), 26.f * S, FLinearColor(1.f, 0.55f, 0.1f), 1.1f * S);
	}
	if (!D.GetThreatHint().IsEmpty())
	{
		Centered(D.GetThreatHint(), 54.f * S, FLinearColor(1.f, 0.85f, 0.3f), 1.1f * S);
		const float BW = 260.f * S, BH = 8.f * S, BX = (SX - BW) * 0.5f, BY = 80.f * S;
		DrawRect(FLinearColor(0.f, 0.f, 0.f, 0.55f), BX, BY, BW, BH);
		DrawRect(FLinearColor(1.f, 0.35f, 0.1f, 0.95f), BX, BY, BW * D.GetThreatMeter(), BH);
	}

	const FString Prompt = D.GetPrompt();
	if (!Prompt.IsEmpty())
	{
		// подсказка действия висит у самого предмета; если он за краем экрана — над карманом
		FVector At;
		FVector Scr(0.f, 0.f, -1.f);
		if (D.GetPromptAnchor(At))
		{
			Scr = Project(At + FVector(0.f, 0.f, 38.f));
		}
		float PW = 0.f, PH = 0.f;
		GetTextSize(Prompt, PW, PH, Font, 1.1f * S);
		const bool bInWorld = Scr.Z > 0.f && Scr.X > PW * 0.5f + 20.f * S && Scr.X < SX - PW * 0.5f - 20.f * S && Scr.Y > 80.f * S && Scr.Y < Y0 - 60.f * S;
		const float PX = bInWorld ? Scr.X - PW * 0.5f : (SX - PW) * 0.5f;
		const float PY = bInWorld ? Scr.Y - PH - 26.f * S : Y0 - 34.f * S;
		DrawRect(FLinearColor(0.f, 0.f, 0.f, 0.65f), PX - 10.f * S, PY - 5.f * S, PW + 20.f * S, PH + 10.f * S);
		DrawText(Prompt, FLinearColor(0.37f, 0.78f, 0.79f), PX, PY, Font, 1.1f * S);
	}

	const FString Message = D.GetPhase() == ERunPhase::Playing ? D.GetMessage() : FString();
	if (!Message.IsEmpty())
	{
		const TArray<FString> Lines = WrapText(this, Message, Font, 1.25f * S, SX * 0.76f - 40.f * S);
		// строка рассказчика — как субтитры, над карманом
		const float LineH = 24.f * S, BoxH = Lines.Num() * LineH + 20.f * S, BoxY = Y0 - BoxH - 62.f * S;
		DrawRect(FLinearColor(0.f, 0.f, 0.f, 0.6f), SX * 0.12f, BoxY, SX * 0.76f, BoxH);
		for (int32 I = 0; I < Lines.Num(); ++I)
		{
			Centered(Lines[I], BoxY + 10.f * S + I * LineH, D.GetPhase() == ERunPhase::Dead ? FLinearColor(1.f, 0.35f, 0.3f) : FLinearColor::White, 1.25f * S);
		}
	}

	if (D.IsReading())
	{
		DrawMenu(*Director, S);
	}
	else if (D.IsInspecting())
	{
		// вещь крупно перед камерой (её рисует ведущий забега), здесь — название и клавиши
		const int32 Item = Pocket[Held];
		const FString Name = RunGen::ItemName(Item);
		float NW = 0.f, NH = 0.f;
		GetTextSize(Name, NW, NH, Font, 1.5f * S);
		DrawRect(FLinearColor(0.f, 0.f, 0.f, 0.6f), (SX - NW) * 0.5f - 16.f * S, SY * 0.72f - 6.f * S, NW + 32.f * S, NH + 12.f * S);
		Centered(Name, SY * 0.72f, FLinearColor::White, 1.5f * S);
		Centered(Item == RunGen::Medkit ? TEXT("Move the mouse to turn it      [LMB] use it      [RMB] put it down")
			: TEXT("Move the mouse to turn it      [RMB] put it down"), SY * 0.72f + NH + 14.f * S, FLinearColor(0.37f, 0.78f, 0.79f), 1.0f * S);
	}

	if (D.IsDebugShown())
	{
		// отладочная шпаргалка: текущее состояние и все наборы, ведущие к победе
		const TArray<FString>& Lines = D.GetSolution();
		const float LineH = 17.f * S, X = 28.f * S, Y = 92.f * S;
		DrawRect(FLinearColor(0.f, 0.f, 0.f, 0.7f), X - 8.f * S, Y - 6.f * S, 760.f * S, (Lines.Num() + 2) * LineH + 12.f * S);
		DrawText(D.GetDebugLine(), FLinearColor(1.f, 0.9f, 0.3f), X, Y, Font, 0.85f * S);
		for (int32 I = 0; I < Lines.Num(); ++I)
		{
			const bool bHead = !Lines[I].StartsWith(TEXT("  "));
			DrawText(Lines[I], bHead ? FLinearColor(0.45f, 0.9f, 0.95f) : FLinearColor::White, X, Y + (I + 1.5f) * LineH, Font, 0.8f * S);
		}
	}

	// --- экраны: смерть, победа, пауза ---
	const int32 Secs = FMath::RoundToInt32(D.GetRunSeconds());
	const FString Clock = FString::Printf(TEXT("%d:%02d"), Secs / 60, Secs % 60);
	const FLinearColor Teal(0.37f, 0.78f, 0.79f), Dim(1.f, 1.f, 1.f, 0.65f);
	if (D.GetPhase() == ERunPhase::Dead)
	{
		for (int32 I = 0; I < 3; ++I)   // три слоя: игровой экран под итогами почти не просвечивает
		{
			DrawRect(FLinearColor(0.05f, 0.f, 0.f, 0.82f), 0.f, 0.f, SX, SY);
		}
		Centered(TEXT("YOU DIED"), SY * 0.26f, FLinearColor(1.f, 0.3f, 0.25f), 3.4f * S);
		Centered(D.GetDeathCause(), SY * 0.26f + 78.f * S, FLinearColor::White, 1.25f * S);
		Centered(FString::Printf(TEXT("Doors opened: %d      Notes read: %d      Time: %s"), D.GetDoorsOpened(), D.GetNotesRead(), *Clock), SY * 0.26f + 124.f * S, Dim, 1.1f * S);
		Centered(TEXT("Another you wakes up on the bridge."), SY * 0.26f + 190.f * S, Teal, 1.25f * S);
		Centered(TEXT("[Enter] try again"), SY * 0.26f + 236.f * S, Dim, 1.1f * S);
	}
	else if (D.GetPhase() == ERunPhase::Won)
	{
		for (int32 I = 0; I < 3; ++I)
		{
			DrawRect(FLinearColor(0.f, 0.02f, 0.03f, 0.84f), 0.f, 0.f, SX, SY);
		}
		Centered(TEXT("YOU ESCAPED"), SY * 0.2f, Teal, 3.4f * S);
		Centered(TEXT("The ship tears itself free of the singularity."), SY * 0.2f + 78.f * S, FLinearColor::White, 1.25f * S);
		Centered(FString::Printf(TEXT("Doors opened: %d      Notes read: %d      Damage taken: %d      Medkits used: %d      Time: %s"), D.GetDoorsOpened(), D.GetNotesRead(),
			FMath::RoundToInt32(D.GetDamageTaken()), D.GetMedkitsUsed(), *Clock), SY * 0.2f + 124.f * S, Dim, 1.1f * S);
		Centered(FString::Printf(TEXT("Run seed: %u"), D.GetSeed()), SY * 0.2f + 152.f * S, Dim, 1.0f * S);
		Centered(TEXT("Made for Epic AI MegaJam 2026 by one person."), SY * 0.2f + 220.f * S, FLinearColor::White, 1.1f * S);
		Centered(TEXT("Tools: Unreal Engine 5, Claude Code, Tripo, Nano Banana, Blender."), SY * 0.2f + 248.f * S, Dim, 1.0f * S);
		Centered(TEXT("[Enter] play again"), SY * 0.2f + 310.f * S, Dim, 1.1f * S);
	}
	else if (D.IsPausedByMenu())
	{
		for (int32 I = 0; I < 2; ++I)
		{
			DrawRect(FLinearColor(0.f, 0.f, 0.f, 0.78f), 0.f, 0.f, SX, SY);
		}
		Centered(TEXT("PAUSED"), SY * 0.2f, FLinearColor::White, 3.0f * S);
		static const TCHAR* const Lines[] = { TEXT("[Esc] resume"), TEXT("[R] restart the run"), TEXT("[Q] quit"), TEXT(""),
			TEXT("WASD walk      [Shift] run      Mouse look"), TEXT("[E] take / read      [1]-[4] or [Wheel] take in hand      [G] drop"),
			TEXT("[RMB] look closer      [LMB] use / hit      [F] hit with the wrench      [Tab] notebook") };
		for (int32 I = 0; I < UE_ARRAY_COUNT(Lines); ++I)
		{
			Centered(Lines[I], SY * 0.2f + (90.f + I * 34.f) * S, I < 3 ? Teal : Dim, 1.2f * S);
		}
		DrawText(FString::Printf(TEXT("Run seed: %u"), D.GetSeed()), Dim, 28.f * S, SY - 34.f * S, Font, 0.95f * S);
	}
}
