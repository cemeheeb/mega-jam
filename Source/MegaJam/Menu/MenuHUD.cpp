#include "MenuHUD.h"

#include "MenuDirector.h"
#include "CanvasItem.h"
#include "Engine/Canvas.h"
#include "Engine/Engine.h"
#include "Engine/Font.h"
#include "EngineUtils.h"
#include "Fonts/SlateFontInfo.h"
#include "GameFramework/PlayerController.h"

namespace
{
	const FLinearColor Paper(0.93f, 0.92f, 0.89f);      // off-white #ECEAE4
	const FLinearColor Teal(0.37f, 0.78f, 0.79f);       // #5FC6C9
	const FLinearColor Orange(0.95f, 0.42f, 0.13f);     // #F26A21

	/** Текст шрифтом движка Roboto нужного размера (кэш Slate: буквы чёткие на любом разрешении). */
	FVector2D DrawMenuText(UCanvas* Canvas, const FString& Text, FVector2D At, float Size, FName Face, int32 Spacing,
		const FLinearColor& Color, bool bMeasureOnly = false)
	{
		FSlateFontInfo Info(GEngine->GetLargeFont(), Size, Face);
		Info.LetterSpacing = Spacing;
		FCanvasTextItem Item(At, FText::FromString(Text), Info, Color);
		Item.EnableShadow(FLinearColor(0.f, 0.f, 0.f, 0.55f * Color.A), FVector2D(1.f, 1.f));
		if (bMeasureOnly)
		{
			Item.SetColor(FLinearColor::Transparent);
			Item.DisableShadow();
		}
		Canvas->DrawItem(Item);
		return Item.DrawnSize;
	}
}

int32 AMenuHUD::ItemUnderMouse() const
{
	float X = 0.f, Y = 0.f;
	if (!PlayerOwner || !PlayerOwner->GetMousePosition(X, Y))
	{
		return -1;
	}
	for (int32 I = 0; I < ItemBoxes.Num(); ++I)
	{
		if (ItemBoxes[I].IsInside(FVector2D(X, Y)))
		{
			return I;
		}
	}
	return -1;
}

void AMenuHUD::DrawHUD()
{
	Super::DrawHUD();
	if (!Canvas)
	{
		return;
	}
	if (!Director.IsValid())
	{
		TActorIterator<AMenuDirector> It(GetWorld());
		if (It)
		{
			Director = *It;
		}
	}
	AMenuDirector* D = Director.Get();
	if (!D)
	{
		return;
	}
	const float SX = Canvas->SizeX, SY = Canvas->SizeY;
	const float S = SY / 1080.f;
	const float T = D->GetClock();
	const float Dt = GetWorld()->GetDeltaSeconds();

	// мышь двигается — выделяется пункт под ней; клавиши выделяют сами (ведущий меню)
	float MX = 0.f, MY = 0.f;
	if (PlayerOwner && PlayerOwner->GetMousePosition(MX, MY))
	{
		const FVector2D Mouse(MX, MY);
		if (!Mouse.Equals(LastMouse, 0.5f))
		{
			LastMouse = Mouse;
			const int32 Item = ItemUnderMouse();
			if (Item >= 0)
			{
				D->Hover(Item);
			}
		}
	}

	const float X0 = 132.f * S;
	// название — когда автор его выберет; под ним короткая оранжевая черта
	const float Appear = FMath::Clamp((T - 1.2f) / 1.5f, 0.f, 1.f);
	if (!D->GetTitle().IsEmpty())
	{
		FLinearColor C = Paper;
		C.A = Appear;
		const FVector2D Size = DrawMenuText(Canvas, D->GetTitle().ToUpper(), FVector2D(X0, SY * 0.26f), 64.f * S, TEXT("Light"), 260, C);
		FLinearColor Bar = Orange;
		Bar.A = Appear;
		DrawRect(Bar, X0 + 4.f * S, SY * 0.26f + Size.Y + 14.f * S, 72.f * S, 3.f * S);
	}

	// пункты внизу слева
	Glow.SetNum(AMenuDirector::ItemCount);
	ItemBoxes.SetNum(AMenuDirector::ItemCount);
	const float ItemsAppear = FMath::Clamp((T - 1.6f) / 1.2f, 0.f, 1.f);
	const float Y0 = SY * 0.70f;
	const float Step = 62.f * S;
	for (int32 I = 0; I < AMenuDirector::ItemCount; ++I)
	{
		const bool bOn = I == D->GetSelected();
		Glow[I] = FMath::FInterpTo(Glow[I], bOn ? 1.f : 0.f, Dt, 10.f);
		const float G = Glow[I];
		const FVector2D At(X0 + 14.f * S * G, Y0 + I * Step);
		FLinearColor C = FLinearColor::LerpUsingHSV(FLinearColor(Paper.R, Paper.G, Paper.B), Teal, G);
		C.A = (0.55f + 0.45f * G) * ItemsAppear;
		const FVector2D Size = DrawMenuText(Canvas, AMenuDirector::ItemName(I), At, 26.f * S, TEXT("Regular"), 420, C);
		ItemBoxes[I] = FBox2D(FVector2D(X0 - 30.f * S, At.Y - 8.f * S), FVector2D(At.X + Size.X + 30.f * S, At.Y + Size.Y + 8.f * S));
		if (G > 0.01f)
		{
			FLinearColor Bar = Orange;
			Bar.A = G * ItemsAppear;
			DrawRect(Bar, X0 - 16.f * S, At.Y + Size.Y * 0.18f, 4.f * S, Size.Y * 0.64f);
		}
	}
	// подсказка
	FLinearColor Hint = Paper;
	Hint.A = 0.38f * ItemsAppear;
	DrawMenuText(Canvas, TEXT("W / S  CHOOSE      ENTER  SELECT"), FVector2D(X0, Y0 + AMenuDirector::ItemCount * Step + 26.f * S),
		12.f * S, TEXT("Regular"), 300, Hint);

	// затемнение: появление и уход
	const float Fade = D->GetFade();
	if (Fade > 0.001f)
	{
		DrawRect(FLinearColor(0.f, 0.f, 0.f, Fade), 0.f, 0.f, SX, SY);
	}
}
