#include "RunHUD.h"

#include "Engine/Canvas.h"
#include "Engine/Engine.h"
#include "EngineUtils.h"
#include "RunDirector.h"
#include "RunGen.h"

void ARunHUD::Centered(const FString& Text, float Y, const FLinearColor& Color, float Scale)
{
	float W = 0.f, H = 0.f;
	GetTextSize(Text, W, H, GEngine->GetMediumFont(), Scale);
	DrawText(Text, Color, (Canvas->SizeX - W) * 0.5f, Y, GEngine->GetMediumFont(), Scale);
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
	UFont* Font = GEngine->GetMediumFont();
	const float SX = Canvas->SizeX, SY = Canvas->SizeY;
	const float S = FMath::Max(1.f, SY / 720.f);   // масштаб под высоту экрана

	// карман: четыре слота снизу по центру
	const float SlotW = 170.f * S, SlotH = 44.f * S, Gap = 10.f * S;
	const float X0 = (SX - 4.f * SlotW - 3.f * Gap) * 0.5f, Y0 = SY - SlotH - 28.f * S;
	const TArray<int32>& Pocket = D.GetPocket();
	for (int32 I = 0; I < RunGen::PocketSlots; ++I)
	{
		const float X = X0 + I * (SlotW + Gap);
		DrawRect(FLinearColor(0.f, 0.f, 0.f, 0.55f), X, Y0, SlotW, SlotH);
		DrawText(FString::Printf(TEXT("%d"), I + 1), FLinearColor(1.f, 1.f, 1.f, 0.45f), X + 6.f * S, Y0 + 3.f * S, Font, 0.9f * S);
		if (Pocket.IsValidIndex(I))
		{
			const FLinearColor Ink = Pocket[I] == RunGen::Notebook ? FLinearColor(0.45f, 0.9f, 0.95f)
				: Pocket[I] == RunGen::Weapon ? FLinearColor(1.f, 0.6f, 0.3f) : FLinearColor::White;
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

	// здоровье: сколько попаданий ещё можно пережить
	const int32 Health = D.GetHealth(), Left = FMath::Max(0, Health - D.GetHits());
	for (int32 I = 0; I < Health; ++I)
	{
		DrawRect(I < Left ? FLinearColor(0.85f, 0.2f, 0.15f, 0.9f) : FLinearColor(0.f, 0.f, 0.f, 0.5f),
			28.f * S + I * 30.f * S, 28.f * S, 24.f * S, 24.f * S);
	}
	if (Left == 1 && D.GetPhase() == ERunPhase::Playing)
	{
		// последнее деление: края экрана пульсируют красным
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

	if (D.IsJournalOpen())
	{
		const float JX = SX * 0.2f, JY = SY * 0.1f, JW = SX * 0.6f, JH = SY * 0.76f;
		DrawRect(FLinearColor(0.02f, 0.03f, 0.04f, 0.92f), JX, JY, JW, JH);
		DrawText(TEXT("NOTEBOOK"), FLinearColor(0.45f, 0.9f, 0.95f), JX + 20.f * S, JY + 14.f * S, Font, 1.3f * S);
		float Y = JY + 54.f * S;
		// новые записи сверху: если блокнот не помещается, за краем остаются старые, а не свежие
		const TArray<FString>& Journal = D.GetJournal();
		for (int32 E = Journal.Num() - 1; E >= 0; --E)
		{
			const FString& Entry = Journal[E];
			const TArray<FString> Lines = WrapText(this, Entry, Font, 1.0f * S, JW - 40.f * S);
			if (Y + Lines.Num() * 22.f * S > JY + JH - 16.f * S)
			{
				break;
			}
			for (const FString& Line : Lines)
			{
				// свои строки персонажа («+ …») выделены бирюзовым
				DrawText(Line, Entry.StartsWith(TEXT("+ ")) ? FLinearColor(0.37f, 0.78f, 0.79f) : FLinearColor::White, JX + 20.f * S, Y, Font, 1.0f * S);
				Y += 22.f * S;
			}
			Y += 12.f * S;
		}
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
		Centered(FString::Printf(TEXT("Doors opened: %d      Notes read: %d      Hits taken: %d      Time: %s"), D.GetDoorsOpened(), D.GetNotesRead(), D.GetHits(), *Clock), SY * 0.2f + 124.f * S, Dim, 1.1f * S);
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
			TEXT("WASD walk      [Shift] run      Mouse look"), TEXT("[E] take / read      [1]-[4] drop      [Tab] notebook"), TEXT("[LMB] or [F] hit with the wrench") };
		for (int32 I = 0; I < UE_ARRAY_COUNT(Lines); ++I)
		{
			Centered(Lines[I], SY * 0.2f + (90.f + I * 34.f) * S, I < 3 ? Teal : Dim, 1.2f * S);
		}
		DrawText(FString::Printf(TEXT("Run seed: %u"), D.GetSeed()), Dim, 28.f * S, SY - 34.f * S, Font, 0.95f * S);
	}
}
