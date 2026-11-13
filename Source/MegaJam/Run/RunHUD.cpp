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
			const bool bNotebook = Pocket[I] == RunGen::Notebook;
			DrawText(RunGen::ItemName(Pocket[I]), bNotebook ? FLinearColor(0.45f, 0.9f, 0.95f) : FLinearColor::White,
				X + 24.f * S, Y0 + 13.f * S, Font, 1.1f * S);
		}
	}

	// здоровье: сколько попаданий ещё можно пережить
	const int32 Health = D.GetHealth(), Left = FMath::Max(0, Health - D.GetHits());
	for (int32 I = 0; I < Health; ++I)
	{
		DrawRect(I < Left ? FLinearColor(0.85f, 0.2f, 0.15f, 0.9f) : FLinearColor(0.f, 0.f, 0.f, 0.5f),
			28.f * S + I * 30.f * S, 28.f * S, 24.f * S, 24.f * S);
	}
	if (D.IsEngineFixed())
	{
		DrawText(TEXT("ENGINES ONLINE - return to the bridge"), FLinearColor(0.45f, 0.9f, 0.95f), 28.f * S, 62.f * S, Font, 1.1f * S);
	}
	DrawText(TEXT("[E] take / read   [1]-[4] drop   [Tab] notebook   [H] debug: solution"), FLinearColor(1.f, 1.f, 1.f, 0.4f), 28.f * S, SY - 24.f * S, Font, 0.85f * S);

	const FString Prompt = D.GetPrompt();
	if (!Prompt.IsEmpty())
	{
		Centered(Prompt, Y0 - 34.f * S, FLinearColor::White, 1.2f * S);
	}

	const FString Message = D.GetMessage();
	if (!Message.IsEmpty())
	{
		TArray<FString> Lines;
		Message.ParseIntoArrayLines(Lines);
		const float LineH = 24.f * S, BoxH = Lines.Num() * LineH + 20.f * S, BoxY = SY * 0.18f;
		DrawRect(FLinearColor(0.f, 0.f, 0.f, 0.6f), SX * 0.12f, BoxY, SX * 0.76f, BoxH);
		for (int32 I = 0; I < Lines.Num(); ++I)
		{
			Centered(Lines[I], BoxY + 10.f * S + I * LineH, D.GetPhase() == ERunPhase::Dead ? FLinearColor(1.f, 0.35f, 0.3f) : FLinearColor::White, 1.25f * S);
		}
	}

	if (D.IsJournalOpen())
	{
		const float JX = SX * 0.2f, JY = SY * 0.12f, JW = SX * 0.6f, JH = SY * 0.7f;
		DrawRect(FLinearColor(0.02f, 0.03f, 0.04f, 0.92f), JX, JY, JW, JH);
		DrawText(TEXT("NOTEBOOK"), FLinearColor(0.45f, 0.9f, 0.95f), JX + 20.f * S, JY + 14.f * S, Font, 1.3f * S);
		float Y = JY + 54.f * S;
		for (const FString& Entry : D.GetJournal())
		{
			TArray<FString> Lines;
			Entry.ParseIntoArrayLines(Lines);
			for (const FString& Line : Lines)
			{
				DrawText(Line, FLinearColor::White, JX + 20.f * S, Y, Font, 1.0f * S);
				Y += 22.f * S;
			}
			Y += 12.f * S;
			if (Y > JY + JH - 30.f * S)
			{
				break;
			}
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
}
