#include "RunHUD.h"

#include "Engine/Canvas.h"
#include "Engine/Engine.h"
#include "Engine/Font.h"
#include "Fonts/CompositeFont.h"
#include "Misc/App.h"
#include "Misc/Paths.h"
#include "Engine/Texture2D.h"
#include "EngineUtils.h"
#include "RunDirector.h"
#include "RunGen.h"
#include "RunHUDStyle.h"

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

// Цвет названия вещи: блокнот, оружие и аптечка выделены, остальное белое — какие вещи значимы, не подсказываем.
static FLinearColor ItemInk(int32 Item)
{
	return Item == RunGen::Notebook ? FLinearColor(0.45f, 0.9f, 0.95f)
		: Item == RunGen::Weapon ? FLinearColor(1.f, 0.6f, 0.3f)
		: Item == RunGen::Medkit ? FLinearColor(0.55f, 1.f, 0.55f) : FLinearColor::White;
}

void ARunHUD::DrawShade(float A)
{
	// поверх уже затемнённой и размытой пост-обработкой комнаты; середина, где блокнот, светлее краёв
	const float SX = Canvas->SizeX, SY = Canvas->SizeY;
	DrawRect(FLinearColor(0.004f, 0.01f, 0.018f, 0.5f * A), 0.f, 0.f, SX, SY);
	const int32 Bands = 12;
	const FLinearColor Band(0.f, 0.f, 0.f, 0.05f * A);
	for (int32 I = 1; I <= Bands; ++I)
	{
		const float BX = SX * 0.2f * I / Bands, BY = SY * 0.2f * I / Bands;
		DrawRect(Band, 0.f, 0.f, BX, SY);
		DrawRect(Band, SX - BX, 0.f, BX, SY);
		DrawRect(Band, 0.f, 0.f, SX, BY);
		DrawRect(Band, 0.f, SY - BY, SX, BY);
	}
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

// Меню на Tab (решение автора 15.11): блокнот с закладками записок, справа — где ты и здоровье, карман, записки,
// скафандр. Время под ним стоит (решение автора 15.11, вечер); фон затемнён и размыт (ARunDirector::SetMenuBlend).
// Вид (15.11): блокнот в угловых скобках, боковая панель со срезанными углами; при открытии всё выезжает за 0,18 с.
void ARunHUD::DrawMenu(ARunDirector& D, float S)
{
	UFont* Font = Hud();
	const float SX = Canvas->SizeX, SY = Canvas->SizeY;
	const FLinearColor Teal = RunStyle::Teal, Dim(1.f, 1.f, 1.f, 0.55f);
	const FLinearColor PanelBg(0.012f, 0.03f, 0.045f, 0.93f);
	DrawShade(MenuBlend);
	// выезд: быстро стартует, мягко останавливается
	const float Slide = FMath::Pow(1.f - MenuBlend, 3.f) * 40.f * S;
	const float RealNow = GetWorld()->GetRealTimeSeconds();

	const float M = 18.f * S, PanelW = FMath::Min(300.f * S, SX * 0.26f);
	float H = SY * 0.72f, W = H * 4.f / 3.f;
	if (W > SX - PanelW - 3.f * M)
	{
		W = SX - PanelW - 3.f * M;
		H = W * 0.75f;
	}
	const float X0 = (SX - W - M - PanelW) * 0.5f, Y0 = SY * 0.075f, BookY = Y0 + Slide * 0.6f;
	FString PagesHelp;
	if (D.IsVideoOpen())
	{
		// настройки видео (O) — на месте разворота блокнота; та же панель, что в главном меню
		const float PW = FMath::Min(W, 520.f * S);
		D.GetVideo().Draw(Canvas, Font, X0 + (W - PW) * 0.5f, BookY, PW, S, [](float A) { return A; });
		PagesHelp = TEXT("[Up] [Down] choose      [Left] [Right] change      [Enter] select      [Esc] back      ");
	}
	else if (D.HasNotebook())
	{
		PagesHelp = DrawNotebook(D, S, X0, BookY, W, H) + TEXT("[O] settings      ");
		RunStyle::Brackets(Canvas, X0 - 12.f * S, BookY - 12.f * S, W + 24.f * S, H + 24.f * S, 22.f * S, 2.f * S, RunStyle::A(Teal, 0.8f));
	}
	else
	{
		PagesHelp = TEXT("[O] settings      ");
		RunStyle::Panel(Canvas, X0, BookY, W, H, 18.f * S, PanelBg, RunStyle::A(Teal, 0.35f), 1.f * S);
		RunStyle::Brackets(Canvas, X0 - 12.f * S, BookY - 12.f * S, W + 24.f * S, H + 24.f * S, 22.f * S, 2.f * S, RunStyle::A(Teal, 0.5f));
		const TCHAR* Lines[] = { TEXT("The notebook is not with you."), TEXT("The notes you read are kept in it.") };
		for (int32 I = 0; I < 2; ++I)
		{
			RunStyle::Text(Canvas, Font, Lines[I], X0 + W * 0.5f, BookY + H * 0.45f + I * 30.f * S, 1.2f * S, I == 0 ? FLinearColor::White : Dim, 0.5f);
		}
	}

	// боковая панель: срезанные углы, тонкая кромка, полоски-метки на верхней и нижней кромках
	const float PX = X0 + W + M + Slide, In = 14.f * S, TextW = PanelW - 2.f * In, RowH = 24.f * S, Cut = 14.f * S;
	RunStyle::Panel(Canvas, PX, Y0, PanelW, H, Cut, PanelBg, RunStyle::A(Teal, 0.4f), 1.f * S);
	RunStyle::Rect(Canvas, PX + Cut + 8.f * S, Y0 - 1.f * S, 64.f * S, 3.f * S, Teal);
	RunStyle::Rect(Canvas, PX + PanelW - Cut - 48.f * S, Y0 + H - 2.f * S, 40.f * S, 3.f * S, RunStyle::A(Teal, 0.6f));
	float Y = Y0 + In;
	float LineW = 0.f, LineH = 0.f;
	Canvas->TextSize(Font, TEXT("Ag"), LineW, LineH, 1.f * S, 1.f * S);
	// заголовок раздела: квадратик, название, линия до края и справа счётчик
	const auto Header = [&](const TCHAR* Text, const FString& Count)
	{
		const float Mid = Y + LineH * 0.5f;
		RunStyle::Rect(Canvas, PX + In, Mid - 3.f * S, 6.f * S, 6.f * S, Teal);
		const float TW = RunStyle::Text(Canvas, Font, Text, PX + In + 13.f * S, Y, 1.f * S, Teal);
		const float CW = Count.IsEmpty() ? 0.f : RunStyle::Text(Canvas, Font, Count, PX + In + TextW, Y + 2.f * S, 0.8f * S, Dim, 1.f) + 8.f * S;
		const float LX = PX + In + 13.f * S + TW + 8.f * S;
		RunStyle::Rect(Canvas, LX, Mid, PX + In + TextW - CW - LX, 1.f * S, RunStyle::A(Teal, 0.35f));
		Y += RowH + 6.f * S;
	};
	const auto Row = [&](const FString& Text, const FLinearColor& Color)
	{
		for (const FString& Line : WrapText(this, Text, Font, 0.95f * S, TextW))
		{
			DrawText(Line, Color, PX + In, Y, Font, 0.95f * S);
			Y += RowH * 0.9f;
		}
	};
	// строка с клавишами-кнопками
	const auto Keys = [&](const FString& Text)
	{
		RunStyle::Rich(Canvas, Font, Text, PX + In, Y, 0.85f * S, FLinearColor(1.f, 1.f, 1.f, 0.7f), Teal);
		Y += RowH;
	};
	// выделенная строка: подложка и полоса слева
	const auto Highlight = [&](float Alpha)
	{
		RunStyle::Rect(Canvas, PX + In * 0.4f, Y - 3.f * S, PanelW - In * 0.8f, RowH - 1.f * S, RunStyle::A(Teal, Alpha));
		RunStyle::Rect(Canvas, PX + In * 0.4f, Y - 3.f * S, 2.f * S, RowH - 1.f * S, Teal);
	};

	// где ты и здоровье: нижняя полоса экрана под меню не рисуется, всё нужное — здесь
	{
		const float Hp = D.GetHealth(), MaxHp = ARunDirector::MaxHealth;
		const bool bLow = Hp <= 25.f;
		RunStyle::Text(Canvas, Font, TEXT("SECTOR"), PX + In, Y, 0.7f * S, RunStyle::A(Teal, 0.85f));
		Y += 14.f * S;
		DrawText(FitText(this, D.GetRoomName().ToUpper(), Font, 1.05f * S, TextW - 60.f * S), FLinearColor::White, PX + In, Y, Font, 1.05f * S);
		RunStyle::Text(Canvas, Font, FString::Printf(TEXT("HP %d"), FMath::CeilToInt32(Hp)), PX + In + TextW, Y + 1.f * S, 0.95f * S,
			bLow ? FLinearColor(1.f, 0.4f, 0.3f) : Dim, 1.f);
		Y += RowH;
		DrawHealthCells(PX + In, Y, TextW, 6.f * S, S, Hp / MaxHp, Hp / MaxHp,
			bLow ? FLinearColor(0.9f, 0.25f, 0.18f) : RunStyle::A(Teal, 0.9f));
		Y += 20.f * S;
	}

	// карман: все четыре ячейки с вещами; вещь в руке подсвечена
	const TArray<int32>& Pocket = D.GetPocket();
	Header(TEXT("POCKET"), FString::Printf(TEXT("%d/%d"), Pocket.Num(), RunGen::PocketSlots));
	{
		const int32 Held = D.GetHeldSlot();
		for (int32 I = 0; I < RunGen::PocketSlots; ++I)
		{
			const bool bItem = Pocket.IsValidIndex(I), bHeld = bItem && I == Held;
			if (bHeld)
			{
				Highlight(0.18f);
			}
			RunStyle::Rich(Canvas, Font, FString::Printf(TEXT("[%d]"), I + 1), PX + In - 3.f * S, Y, 0.8f * S, FLinearColor::White,
				bItem ? (bHeld ? Teal : FLinearColor(1.f, 1.f, 1.f, 0.6f)) : FLinearColor(1.f, 1.f, 1.f, 0.25f));
			if (bItem)
			{
				const float TagW = bHeld ? RunStyle::Text(Canvas, Font, TEXT("IN HAND"), PX + In + TextW, Y + 2.f * S, 0.75f * S, Teal, 1.f) : 0.f;
				DrawText(FitText(this, RunGen::ItemName(Pocket[I]), Font, 0.95f * S, TextW - 26.f * S - TagW - 8.f * S), ItemInk(Pocket[I]),
					PX + In + 24.f * S, Y, Font, 0.95f * S);
				if (Pocket[I] == RunGen::Notebook && D.HasUnreadJournal())
				{
					const float Pulse = 0.55f + 0.45f * FMath::Sin(RealNow * 6.f);
					RunStyle::Rect(Canvas, PX + In + TextW - (bHeld ? TagW + 14.f * S : 8.f * S), Y + 6.f * S, 7.f * S, 7.f * S, RunStyle::A(Teal, Pulse));
				}
			}
			else
			{
				DrawText(TEXT("EMPTY"), FLinearColor(1.f, 1.f, 1.f, 0.22f), PX + In + 24.f * S, Y + 1.f * S, Font, 0.8f * S);
			}
			Y += RowH;
		}
		Y += 2.f * S;
		Keys(TEXT("[1]-[4] look closer      [G] drop"));
		Y += RowH * 0.3f;
	}

	// внизу панели — скафандр; записки занимают всё, что между карманом и им
	const float FootH = 4.4f * RowH;
	const float NotesBottom = Y0 + H - FootH;
	const TArray<FString>& Marks = D.GetBookmarks();
	const int32 Chosen = D.GetBookmark();
	Header(TEXT("NOTES"), Marks.Num() > 0 ? FString::FromInt(Marks.Num()) : FString());
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
				Highlight(0.2f);
			}
			RunStyle::Rect(Canvas, PX + In + 4.f * S, Y + 2.f * S, 5.f * S, RowH - 10.f * S, BookmarkColor(I, bBook ? 1.f : 0.4f));
			const FString Label = FString::Printf(TEXT("%d  %s"), I + 1, *Marks[I].Replace(TEXT("\n"), TEXT(" ")));
			DrawText(FitText(this, Label, Font, 0.9f * S, TextW - 18.f * S), bChosen ? FLinearColor::White : (bBook ? FLinearColor(1.f, 1.f, 1.f, 0.8f) : Dim),
				PX + In + 16.f * S, Y, Font, 0.9f * S);
			Y += RowH;
		}
		Y += 2.f * S;
		if (bBook)
		{
			Keys(TEXT("[Up] [Down] open a bookmark"));
		}
		else
		{
			Row(TEXT("Bookmarks are in the notebook"), Dim);
		}
	}

	Y = NotesBottom;
	Header(TEXT("SPACE SUIT"), D.IsSuitOn() ? FString(TEXT("ON")) : FString());
	if (D.IsSuitOn())
	{
		Row(TEXT("You are wearing it."), FLinearColor::White);
		if (D.IsInVacuum())
		{
			Row(TEXT("No air here - keep it on"), FLinearColor(1.f, 0.55f, 0.35f));
		}
		else
		{
			Keys(TEXT("[T] take it off"));
		}
	}
	else
	{
		Row(D.WasSuitWorn() ? TEXT("Left where you took it off.") : TEXT("You have no suit."), Dim);
		Keys(TEXT("[E] next to it - put it on"));
	}

	// подсказка снизу: клавиши-кнопками и метка «время стоит» — две оранжевые черты паузы
	{
		const FString Help = PagesHelp + TEXT("[Tab] close");
		const float HS = 0.95f * S, TagS = 0.8f * S;
		const float HelpW = RunStyle::Rich(Canvas, Font, Help, 0.f, 0.f, HS, Dim, Teal, true);
		float TagW = 0.f, TagH = 0.f, HelpLW = 0.f, HelpH = 0.f;
		Canvas->TextSize(Font, TEXT("TIME STOPPED"), TagW, TagH, TagS, TagS);
		Canvas->TextSize(Font, TEXT("Ag"), HelpLW, HelpH, HS, HS);
		const float Sep = 16.f * S, Icon = 10.f * S, Total = HelpW + 2.f * Sep + Icon + 6.f * S + TagW;
		const float BX = (SX - Total) * 0.5f, BY = Y0 + H + 16.f * S + Slide * 0.5f, BH = HelpH + 14.f * S;
		RunStyle::Panel(Canvas, BX - 16.f * S, BY, Total + 32.f * S, BH, 8.f * S, PanelBg, RunStyle::A(Teal, 0.3f), 1.f * S);
		RunStyle::Rich(Canvas, Font, Help, BX, BY + 7.f * S, HS, Dim, Teal);
		const float SepX = BX + HelpW + Sep;
		RunStyle::Rect(Canvas, SepX, BY + 6.f * S, 1.f * S, BH - 12.f * S, RunStyle::A(Teal, 0.3f));
		const float IX = SepX + Sep, IH = TagH * 0.7f, IY = BY + (BH - IH) * 0.5f;
		RunStyle::Rect(Canvas, IX, IY, 3.f * S, IH, RunStyle::Orange);
		RunStyle::Rect(Canvas, IX + 6.f * S, IY, 3.f * S, IH, RunStyle::Orange);
		RunStyle::Text(Canvas, Font, TEXT("TIME STOPPED"), IX + Icon + 6.f * S, BY + (BH - TagH) * 0.5f, TagS, RunStyle::Orange);
	}
}

// Полоса здоровья из ячеек: 20 делений по 5 единиц. Lag — светлый хвост после попадания (доля 0..1).
void ARunHUD::DrawHealthCells(float X, float Y, float W, float H, float S, float Frac, float Lag, const FLinearColor& Color)
{
	const int32 Cells = 20;
	const float Gap = 2.f * S, CW = (W - (Cells - 1) * Gap) / Cells;
	Frac = FMath::Clamp(Frac, 0.f, 1.f);
	Lag = FMath::Clamp(Lag, Frac, 1.f);
	for (int32 I = 0; I < Cells; ++I)
	{
		const float CX = X + I * (CW + Gap);
		// доля этой ячейки, которая ещё полна: последняя тает частично
		const float Full = FMath::Clamp(Frac * Cells - I, 0.f, 1.f), Trail = FMath::Clamp(Lag * Cells - I, 0.f, 1.f);
		RunStyle::Rect(Canvas, CX, Y, CW, H, FLinearColor(1.f, 1.f, 1.f, 0.1f));
		if (Trail > Full)
		{
			RunStyle::Rect(Canvas, CX + CW * Full, Y, CW * (Trail - Full), H, FLinearColor(1.f, 0.85f, 0.7f, 0.85f));
		}
		RunStyle::Rect(Canvas, CX, Y, CW * Full, H, Color);
	}
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

	// меню на Tab: фон темнеет и расплывается за 0,18 с. Часы реальные: на паузе время мира стоит
	MenuBlend = FMath::FInterpConstantTo(MenuBlend, D.IsReading() ? 1.f : 0.f, FApp::GetDeltaTime(), 1.f / 0.18f);
	Director->SetMenuBlend(MenuBlend);
	if (D.IsReading())
	{
		DrawMenu(*Director, S);   // карман, здоровье и где ты — в самом меню; остальное под ним не нужно
		return;
	}
	if (MenuBlend > 0.f)
	{
		DrawShade(MenuBlend);   // меню закрыли: затемнение уходит плавно, экран игры уже поверх
	}

	// карман: четыре ячейки снизу по центру (стиль 15.11). Вещь в руке приподнята, в яркой кромке и скобках, со свечением;
	// пустая ячейка — пунктиром. Полоска снизу — вид вещи (блокнот, оружие, аптечка); значимые вещи не выделяются
	const float SlotW = 150.f * S, SlotH = 54.f * S, Gap = 12.f * S, Cut = 9.f * S, Lift = 6.f * S;
	const float X0 = (SX - 4.f * SlotW - 3.f * Gap) * 0.5f, Y0 = SY - SlotH - 34.f * S;
	const TArray<int32>& Pocket = D.GetPocket();
	const int32 Held = D.GetHeldSlot();
	const float RealNow = GetWorld()->GetRealTimeSeconds();
	for (int32 I = 0; I < RunGen::PocketSlots; ++I)
	{
		const bool bItem = Pocket.IsValidIndex(I), bHeld = bItem && I == Held;
		const float X = X0 + I * (SlotW + Gap), Y = Y0 - (bHeld ? Lift : 0.f);
		const FString Num = FString::Printf(TEXT("[%d]"), I + 1);
		if (!bItem)
		{
			RunStyle::Rect(Canvas, X, Y, SlotW, SlotH, RunStyle::A(RunStyle::Fill, 0.5f));
			RunStyle::Dashed(Canvas, X, Y, SlotW, SlotH, 6.f * S, 1.5f * S, RunStyle::A(RunStyle::Teal, 0.45f));
			RunStyle::Rich(Canvas, Font, Num, X + 4.f * S, Y + 5.f * S, 0.85f * S, FLinearColor::White, FLinearColor(1.f, 1.f, 1.f, 0.4f));
			RunStyle::Text(Canvas, Font, TEXT("EMPTY"), X + SlotW * 0.5f, Y + SlotH * 0.5f - 6.f * S, 0.8f * S, FLinearColor(1.f, 1.f, 1.f, 0.4f), 0.5f);
			continue;
		}
		const int32 Item = Pocket[I];
		const FLinearColor Ink = ItemInk(Item);
		if (bHeld)
		{
			RunStyle::Glow(Canvas, X, Y, SlotW, SlotH, S, RunStyle::Teal);
		}
		RunStyle::Panel(Canvas, X, Y, SlotW, SlotH, Cut, bHeld ? FLinearColor(0.02f, 0.09f, 0.11f, 0.94f) : RunStyle::Fill,
			RunStyle::A(RunStyle::Teal, bHeld ? 0.95f : 0.35f), (bHeld ? 2.f : 1.f) * S);
		RunStyle::Rich(Canvas, Font, Num, X + 4.f * S, Y + 5.f * S, 0.85f * S, FLinearColor::White, bHeld ? RunStyle::Teal : FLinearColor(1.f, 1.f, 1.f, 0.6f));
		float TagW = 0.f;
		if (bHeld)
		{
			RunStyle::Brackets(Canvas, X - 5.f * S, Y - 5.f * S, SlotW + 10.f * S, SlotH + 10.f * S, 10.f * S, 2.f * S, RunStyle::Teal);
			TagW = RunStyle::Text(Canvas, Font, TEXT("IN HAND"), X + SlotW - 8.f * S, Y + 6.f * S, 0.7f * S, RunStyle::Teal, 1.f);
		}
		if (Item == RunGen::Notebook || Item == RunGen::Weapon || Item == RunGen::Medkit)
		{
			RunStyle::Rect(Canvas, X + 8.f * S, Y + SlotH - 6.f * S, SlotW - Cut - 16.f * S, 2.f * S, RunStyle::A(Ink, 0.85f));
		}
		RunStyle::Text(Canvas, Font, FitText(this, RunGen::ItemName(Item), Font, 1.05f * S, SlotW - 20.f * S), X + SlotW * 0.5f, Y + SlotH * 0.5f - 5.f * S,
			1.05f * S, bHeld ? Ink : RunStyle::A(Ink, 0.85f), 0.5f);
		if (Item == RunGen::Notebook && D.HasUnreadJournal())
		{
			// есть новая запись: точка пульсирует
			const float Pulse = 0.55f + 0.45f * FMath::Sin(RealNow * 6.f);
			RunStyle::Rect(Canvas, X + SlotW - (bHeld ? TagW + 20.f * S : 16.f * S), Y + 8.f * S, 7.f * S, 7.f * S, RunStyle::A(RunStyle::Teal, Pulse));
		}
	}

	// под карманом — как сменить вещь в руке и что с ней делать (автор, 15.11: «надо показать игроку как это делать»)
	if (Pocket.Num() > 0 && D.GetPhase() == ERunPhase::Playing && !D.IsReading() && !D.IsInspecting())
	{
		TArray<FString> Keys;
		if (Pocket.Num() > 1)
		{
			Keys.Add(TEXT("[WHEEL] or [1]-[4] switch"));
		}
		else if (Held < 0)
		{
			Keys.Add(TEXT("[1] take in hand"));
		}
		if (Held >= 0)
		{
			if (Pocket[Held] == RunGen::Medkit)
			{
				Keys.Add(TEXT("[LMB] use"));
			}
			else if (D.HasWeapon())
			{
				Keys.Add(TEXT("[LMB] hit"));
			}
			Keys.Add(TEXT("[RMB] look closer"));
			Keys.Add(TEXT("[G] drop"));
		}
		else if (D.HasWeapon())
		{
			Keys.Add(TEXT("[LMB] hit"));
		}
		if (D.HasFlashlight())
		{
			Keys.Add(TEXT("[V] light"));
		}
		// на тёмной полосе: на светлом полу без подложки строка не читается
		const FString Line = FString::Join(Keys, TEXT("     "));
		const float KS = 0.8f * S, KY = Y0 + SlotH + 9.f * S;
		const float KW = RunStyle::Rich(Canvas, Font, Line, 0.f, 0.f, KS, FLinearColor::White, FLinearColor::White, true);
		float KLW = 0.f, KH = 0.f;
		GetTextSize(TEXT("Ag"), KLW, KH, Font, KS);
		RunStyle::Panel(Canvas, (SX - KW) * 0.5f - 12.f * S, KY - 3.f * S, KW + 24.f * S, KH + 6.f * S, 5.f * S, RunStyle::A(RunStyle::Fill, 0.6f),
			FLinearColor::Transparent, 0.f);
		RunStyle::Rich(Canvas, Font, Line, (SX - KW) * 0.5f, KY, KS, FLinearColor(1.f, 1.f, 1.f, 0.75f), FLinearColor(1.f, 1.f, 1.f, 0.8f));
	}

	// шлюз считывает карман: пока створки закрыты, ячейки по очереди вспыхивают и по ним проходит луч — все, без разбора
	const float Scan = D.GetTransitionAlpha();
	if (Scan >= 0.f)
	{
		const float Pos = Scan * RunGen::PocketSlots;
		const int32 Lit = FMath::Min(RunGen::PocketSlots - 1, FMath::FloorToInt32(Pos));
		const float X = X0 + Lit * (SlotW + Gap), Y = Y0 - (Lit == Held && Pocket.IsValidIndex(Lit) ? Lift : 0.f);
		RunStyle::Glow(Canvas, X, Y, SlotW, SlotH, S, RunStyle::Teal);
		RunStyle::Frame(Canvas, X - 2.f * S, Y - 2.f * S, SlotW + 4.f * S, SlotH + 4.f * S, 2.f * S, RunStyle::Teal);
		RunStyle::Rect(Canvas, X, Y + SlotH * FMath::Min(Pos - Lit, 1.f) - 1.f * S, SlotW, 2.f * S, RunStyle::A(RunStyle::Teal, 0.9f));
	}
	// где я: мелко справа вверху, крупно на пару секунд при входе — с расходящимися от названия линиями
	if (!D.GetRoomName().IsEmpty())
	{
		RunStyle::Text(Canvas, Font, TEXT("SECTOR"), SX - 28.f * S, 22.f * S, 0.7f * S, RunStyle::A(RunStyle::Teal, 0.85f), 1.f);
		RunStyle::Text(Canvas, Font, D.GetRoomName().ToUpper(), SX - 28.f * S, 36.f * S, 1.1f * S, FLinearColor(1.f, 1.f, 1.f, 0.85f), 1.f);
		const float Title = D.GetRoomTitleAlpha();
		if (Title > 0.f && Scan < 0.f)
		{
			const float A = FMath::Min(1.f, Title * 3.f);
			float TW = 0.f, TH = 0.f;
			GetTextSize(D.GetRoomName(), TW, TH, Font, 2.6f * S);
			Centered(D.GetRoomName(), SY * 0.27f, FLinearColor(1.f, 1.f, 1.f, A), 2.6f * S);
			const float LineLen = 140.f * S * FMath::Min(1.f, (1.f - Title) * 6.f + 0.2f), LineY = SY * 0.27f + TH * 0.55f;
			RunStyle::Rect(Canvas, (SX - TW) * 0.5f - 24.f * S - LineLen, LineY, LineLen, 1.5f * S, RunStyle::A(RunStyle::Teal, A * 0.8f));
			RunStyle::Rect(Canvas, (SX + TW) * 0.5f + 24.f * S, LineY, LineLen, 1.5f * S, RunStyle::A(RunStyle::Teal, A * 0.8f));
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
		// 20 ячеек по 5 единиц на тёмной подложке со срезанными углами (вид 15.11)
		const float BX = 28.f * S, BY = 30.f * S, BW = 240.f * S, BH = 12.f * S;
		RunStyle::Panel(Canvas, BX - 8.f * S, BY - 7.f * S, BW + 58.f * S, BH + 14.f * S, 7.f * S, RunStyle::A(RunStyle::Fill, 0.6f),
			RunStyle::A(RunStyle::Teal, 0.25f), 1.f * S);
		const FLinearColor Fill = FLinearColor::LerpUsingHSV(FLinearColor(0.85f, 0.2f, 0.15f, 0.95f), FLinearColor(0.3f, 0.9f, 0.4f, 0.95f), D.GetHealFlash());
		DrawHealthCells(BX, BY, BW, BH, S, Hp / MaxHp, LagHealth / MaxHp, Fill);
		DrawText(FString::Printf(TEXT("%d"), FMath::CeilToInt32(Hp)), FLinearColor::White, BX + BW + 10.f * S, BY - 5.f * S, Font, 1.0f * S);
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
	// обучение (автор 15.11): слева под здоровьем — цель забега и, в режиме обучения, что делать сейчас
	if (D.GetPhase() == ERunPhase::Playing)
	{
		const FString Goal = D.GetGoal();
		const FString Step = ARunDirector::IsTrainingOn() ? D.GetStep() : FString();
		if (!Goal.IsEmpty())
		{
			const float PX = 28.f * S, PY = 58.f * S, PW = 430.f * S, LineH = 20.f * S;
			const TArray<FString> Lines = Step.IsEmpty() ? TArray<FString>() : WrapText(this, Step, Font, 1.0f * S, PW - 24.f * S);
			// вид 15.11: панель со срезанными углами, бирюзовая черта у цели, тонкий разделитель перед шагом обучения
			const float BoxH = 30.f * S + Lines.Num() * LineH;
			RunStyle::Panel(Canvas, PX - 8.f * S, PY - 6.f * S, PW, BoxH, 9.f * S, RunStyle::A(RunStyle::Fill, 0.75f), RunStyle::A(RunStyle::Teal, 0.3f), 1.f * S);
			RunStyle::Rect(Canvas, PX - 8.f * S, PY - 1.f * S, 3.f * S, 18.f * S, RunStyle::Teal);
			if (Lines.Num() > 0)
			{
				RunStyle::Rect(Canvas, PX, PY + 21.f * S, PW - 24.f * S, 1.f * S, RunStyle::A(RunStyle::Teal, 0.25f));
			}
			DrawText(Goal, FLinearColor(0.45f, 0.9f, 0.95f), PX, PY, Font, 0.95f * S);
			for (int32 I = 0; I < Lines.Num(); ++I)
			{
				DrawText(Lines[I], FLinearColor::White, PX, PY + 24.f * S + I * LineH, Font, 1.0f * S);
			}
		}
	}
	// клавиши не висят на экране постоянно: каждая показывается один раз, когда впервые нужна
	const FString Tip = D.GetTip();
	if (!Tip.IsEmpty())
	{
		// панель со срезанными углами, бирюзовая черта слева; клавиши — кнопками
		const float TS = 1.1f * S;
		float LW = 0.f, TH = 0.f;
		GetTextSize(TEXT("Ag"), LW, TH, Font, TS);
		const float TW = RunStyle::Rich(Canvas, Font, Tip, 0.f, 0.f, TS, FLinearColor::White, RunStyle::Teal, true);
		const float TX = (SX - TW) * 0.5f, TY = SY * 0.115f;
		RunStyle::Panel(Canvas, TX - 18.f * S, TY - 7.f * S, TW + 36.f * S, TH + 14.f * S, 8.f * S, RunStyle::A(RunStyle::Fill, 0.8f),
			RunStyle::A(RunStyle::Teal, 0.35f), 1.f * S);
		RunStyle::Rect(Canvas, TX - 18.f * S, TY + 1.f * S, 3.f * S, TH - 2.f * S, RunStyle::Teal);
		RunStyle::Rich(Canvas, Font, Tip, TX, TY, TS, FLinearColor::White, RunStyle::Teal);
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
	// обучение: в опасной комнате — метка двери, через которую вошёл (обратный путь ведёт туда, откуда пришёл)
	FVector Back;
	if (D.GetBackDoor(Back))
	{
		const FLinearColor Way(0.45f, 0.9f, 0.95f);
		const FVector Scr = Project(Back);
		const float Pad = 70.f * S;
		float X = Scr.X, Y = Scr.Y;
		if (Scr.Z <= 0.f)
		{
			X = SX - X;      // дверь за спиной: метка прижимается к низу
			Y = SY;
		}
		X = FMath::Clamp(X, Pad, SX - Pad);
		Y = FMath::Clamp(Y, Pad + 40.f * S, Y0 - 130.f * S);   // выше субтитров рассказчика
		const float M = 11.f * S;
		DrawLine(X, Y - M, X + M, Y, Way, 3.f * S);
		DrawLine(X + M, Y, X, Y + M, Way, 3.f * S);
		DrawLine(X, Y + M, X - M, Y, Way, 3.f * S);
		DrawLine(X - M, Y, X, Y - M, Way, 3.f * S);
		DrawText(TEXT("WAY BACK"), Way, X + 18.f * S, Y - 9.f * S, Font, 0.95f * S);
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
		float PLW = 0.f, PH = 0.f;
		GetTextSize(TEXT("Ag"), PLW, PH, Font, 1.1f * S);
		const float PW = RunStyle::Rich(Canvas, Font, Prompt, 0.f, 0.f, 1.1f * S, FLinearColor::White, RunStyle::Teal, true);
		const bool bInWorld = Scr.Z > 0.f && Scr.X > PW * 0.5f + 20.f * S && Scr.X < SX - PW * 0.5f - 20.f * S && Scr.Y > 80.f * S && Scr.Y < Y0 - 60.f * S;
		const float PX = bInWorld ? Scr.X - PW * 0.5f : (SX - PW) * 0.5f;
		const float PY = bInWorld ? Scr.Y - PH - 26.f * S : Y0 - 34.f * S;
		RunStyle::Panel(Canvas, PX - 12.f * S, PY - 6.f * S, PW + 24.f * S, PH + 12.f * S, 7.f * S, RunStyle::A(RunStyle::Fill, 0.8f),
			RunStyle::A(RunStyle::Teal, 0.5f), 1.f * S);
		RunStyle::Rich(Canvas, Font, Prompt, PX, PY, 1.1f * S, FLinearColor::White, RunStyle::Teal);
	}

	const FString Message = D.GetPhase() == ERunPhase::Playing ? D.GetMessage() : FString();
	if (!Message.IsEmpty())
	{
		const TArray<FString> Lines = WrapText(this, Message, Font, 1.25f * S, SX * 0.76f - 40.f * S);
		// строка рассказчика — как субтитры, над карманом
		const float LineH = 24.f * S, BoxH = Lines.Num() * LineH + 20.f * S, BoxY = Y0 - BoxH - 62.f * S;
		RunStyle::Panel(Canvas, SX * 0.12f, BoxY, SX * 0.76f, BoxH, 10.f * S, RunStyle::A(RunStyle::Fill, 0.7f), RunStyle::A(RunStyle::Teal, 0.2f), 1.f * S);
		for (int32 I = 0; I < Lines.Num(); ++I)
		{
			Centered(Lines[I], BoxY + 10.f * S + I * LineH, D.GetPhase() == ERunPhase::Dead ? FLinearColor(1.f, 0.35f, 0.3f) : FLinearColor::White, 1.25f * S);
		}
	}

	if (D.IsInspecting())
	{
		// вещь крупно перед камерой (её рисует ведущий забега), здесь — название и клавиши
		const int32 Item = Pocket[Held];
		const FString Name = RunGen::ItemName(Item);
		float NW = 0.f, NH = 0.f;
		GetTextSize(Name, NW, NH, Font, 1.5f * S);
		// одна панель на имя и клавиши: вещь крупно позади, текст поверх неё без подложки теряется
		const FString Help = Item == RunGen::Medkit ? TEXT("Move the mouse to turn it      [LMB] use it      [RMB] put it down")
			: TEXT("Move the mouse to turn it      [RMB] put it down");
		const float HelpW = RunStyle::Rich(Canvas, Font, Help, 0.f, 0.f, 1.0f * S, FLinearColor::White, RunStyle::Teal, true);
		float HLW = 0.f, HH = 0.f;
		GetTextSize(TEXT("Ag"), HLW, HH, Font, 1.0f * S);
		const float BoxW = FMath::Max(NW, HelpW) + 40.f * S, BoxY = SY * 0.72f - 8.f * S, BoxH = NH + HH + 30.f * S;
		RunStyle::Panel(Canvas, (SX - BoxW) * 0.5f, BoxY, BoxW, BoxH, 10.f * S, RunStyle::A(RunStyle::Fill, 0.85f), RunStyle::A(RunStyle::Teal, 0.4f), 1.f * S);
		RunStyle::Brackets(Canvas, (SX - BoxW) * 0.5f - 5.f * S, BoxY - 5.f * S, BoxW + 10.f * S, BoxH + 10.f * S, 12.f * S, 2.f * S, RunStyle::A(RunStyle::Teal, 0.8f));
		Centered(Name, SY * 0.72f, ItemInk(Item), 1.5f * S);
		RunStyle::RichCentered(Canvas, Font, Help, SX * 0.5f, SY * 0.72f + NH + 10.f * S, 1.0f * S, FLinearColor(1.f, 1.f, 1.f, 0.8f), RunStyle::Teal);
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
	const FString ShipCode = D.GetShipCode();   // зерно цифрами: этот код на двери каюты возвращает на тот же корабль

	if (D.IsCodeOpen())
	{
		// окно кода двери каюты (решение автора 15.11, вечер): цифры корабля, на котором уже был; пусто — новый
		const float W = 640.f * S, H = 250.f * S, X = (SX - W) * 0.5f, Y = SY * 0.3f;
		DrawRect(FLinearColor(0.f, 0.02f, 0.03f, 0.88f), X, Y, W, H);
		const float B = 2.f * S;
		DrawRect(Teal, X, Y, W, B);
		DrawRect(Teal, X, Y + H - B, W, B);
		DrawRect(Teal, X, Y, B, H);
		DrawRect(Teal, X + W - B, Y, B, H);
		Centered(TEXT("DOOR CODE"), Y + 16.f * S, Teal, 1.6f * S);
		Centered(TEXT("The code of a ship you have already been on takes you back to it."), Y + 54.f * S, FLinearColor::White, 1.0f * S);
		Centered(TEXT("Leave it empty for a new ship."), Y + 76.f * S, FLinearColor::White, 1.0f * S);
		const float FieldY = Y + 106.f * S;
		DrawRect(FLinearColor(0.f, 0.f, 0.f, 0.9f), X + 40.f * S, FieldY, W - 80.f * S, 44.f * S);
		const bool bCaret = FMath::Fmod(FPlatformTime::Seconds(), 1.0) < 0.55;   // реальное время: мигает и без хода мира
		FString Shown;   // цифры вразрядку, как на табло замка
		for (const TCHAR C : D.GetCodeText())
		{
			Shown.AppendChar(C);
			Shown += TEXT(" ");
		}
		Centered(Shown + (bCaret ? TEXT("_") : TEXT(" ")), FieldY + 9.f * S, FLinearColor::White, 1.5f * S);
		if (!D.GetCodeError().IsEmpty())
		{
			Centered(D.GetCodeError(), FieldY + 54.f * S, FLinearColor(1.f, 0.35f, 0.3f), 1.0f * S);
		}
		Centered(TEXT("[0]-[9] digits      [Enter] open      [Backspace] erase      [Esc] step back"), Y + H - 52.f * S, Dim, 0.95f * S);
		if (!D.GetLastCode().IsEmpty())
		{
			Centered(FString::Printf(TEXT("[Up] last ship: %s"), *D.GetLastCode()), Y + H - 28.f * S, Teal, 0.95f * S);
		}
	}
	if (D.GetPhase() == ERunPhase::Dead)
	{
		for (int32 I = 0; I < 3; ++I)   // три слоя: игровой экран под итогами почти не просвечивает
		{
			DrawRect(FLinearColor(0.05f, 0.f, 0.f, 0.82f), 0.f, 0.f, SX, SY);
		}
		Centered(TEXT("YOU DIED"), SY * 0.26f, FLinearColor(1.f, 0.3f, 0.25f), 3.4f * S);
		Centered(D.GetDeathCause(), SY * 0.26f + 78.f * S, FLinearColor::White, 1.25f * S);
		Centered(D.GetDeathAdvice(), SY * 0.26f + 112.f * S, Teal, 1.1f * S);   // обучение: что делать в следующий раз
		Centered(FString::Printf(TEXT("Doors opened: %d      Notes read: %d      Time: %s"), D.GetDoorsOpened(), D.GetNotesRead(), *Clock), SY * 0.26f + 156.f * S, Dim, 1.1f * S);
		Centered(FString::Printf(TEXT("Ship code: %s  -  type it at your cabin door to come back to this ship"), *ShipCode), SY * 0.26f + 184.f * S, Dim, 1.0f * S);
		Centered(TEXT("Another you wakes up."), SY * 0.26f + 226.f * S, Teal, 1.25f * S);
		Centered(TEXT("[Enter] try again"), SY * 0.26f + 268.f * S, Dim, 1.1f * S);
	}
	else if (D.GetPhase() == ERunPhase::Won)
	{
		// концовка — сценой в меню (ARunDirector::StartEnding): здесь только затемнение перед ней
		if (const float Fade = D.GetWinFade(); Fade > 0.f)
		{
			DrawRect(FLinearColor(0.f, 0.f, 0.f, Fade * Fade * (3.f - 2.f * Fade)), 0.f, 0.f, SX, SY);
		}
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
		if (!D.IsInCabin())   // в каюте код ещё не набран
		{
			DrawText(FString::Printf(TEXT("Ship code: %s"), *ShipCode), Dim, 28.f * S, SY - 34.f * S, Font, 0.95f * S);
		}
	}
}
