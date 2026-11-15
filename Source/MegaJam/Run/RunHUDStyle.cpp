#include "RunHUDStyle.h"

#include "CanvasItem.h"
#include "CanvasTypes.h"
#include "Engine/Canvas.h"
#include "Engine/Font.h"
#include "GlobalRenderResources.h"

namespace RunStyle
{
	void Rect(UCanvas* C, float X, float Y, float W, float H, const FLinearColor& Color)
	{
		if (W <= 0.f || H <= 0.f || Color.A <= 0.f)
		{
			return;
		}
		FCanvasTileItem Tile(FVector2D(X, Y), FVector2D(W, H), Color);
		Tile.BlendMode = SE_BLEND_AlphaBlend;   // как Translucent; слой главного меню берёт и прозрачность
		C->DrawItem(Tile);
	}

	void Frame(UCanvas* C, float X, float Y, float W, float H, float T, const FLinearColor& Color)
	{
		Rect(C, X, Y, W, T, Color);
		Rect(C, X, Y + H - T, W, T, Color);
		Rect(C, X, Y + T, T, H - 2.f * T, Color);
		Rect(C, X + W - T, Y + T, T, H - 2.f * T, Color);
	}

	void Poly(UCanvas* C, TArrayView<const FVector2D> Pts, const FLinearColor& Color)
	{
		if (Pts.Num() < 3 || Color.A <= 0.f)
		{
			return;
		}
		TArray<FCanvasUVTri> Tris;
		for (int32 I = 1; I + 1 < Pts.Num(); ++I)
		{
			FCanvasUVTri T;
			T.V0_Pos = Pts[0];
			T.V1_Pos = Pts[I];
			T.V2_Pos = Pts[I + 1];
			T.V0_Color = T.V1_Color = T.V2_Color = Color;
			Tris.Add(T);
		}
		FCanvasTriangleItem Item(Tris, GWhiteTexture);
		Item.BlendMode = SE_BLEND_AlphaBlend;
		C->DrawItem(Item);
	}

	void Outline(UCanvas* C, TArrayView<const FVector2D> Pts, const FLinearColor& Color, float Thick)
	{
		if (Color.A <= 0.f)
		{
			return;
		}
		for (int32 I = 0; I < Pts.Num(); ++I)
		{
			FCanvasLineItem Line(Pts[I], Pts[(I + 1) % Pts.Num()]);
			Line.SetColor(Color);
			Line.LineThickness = Thick;
			Line.BlendMode = SE_BLEND_AlphaBlend;
			C->DrawItem(Line);
		}
	}

	void Panel(UCanvas* C, float X, float Y, float W, float H, float Cut, const FLinearColor& FillColor, const FLinearColor& Edge, float EdgeThick)
	{
		Cut = FMath::Min(Cut, FMath::Min(W, H) * 0.5f);
		const FVector2D Pts[] = { FVector2D(X + Cut, Y), FVector2D(X + W, Y), FVector2D(X + W, Y + H - Cut), FVector2D(X + W - Cut, Y + H),
			FVector2D(X, Y + H), FVector2D(X, Y + Cut) };
		Poly(C, Pts, FillColor);
		Outline(C, Pts, Edge, EdgeThick);
	}

	void Brackets(UCanvas* C, float X, float Y, float W, float H, float Len, float T, const FLinearColor& Color)
	{
		Len = FMath::Min(Len, FMath::Min(W, H) * 0.5f);
		// левый верхний, правый верхний, левый нижний, правый нижний
		Rect(C, X, Y, Len, T, Color);
		Rect(C, X, Y, T, Len, Color);
		Rect(C, X + W - Len, Y, Len, T, Color);
		Rect(C, X + W - T, Y, T, Len, Color);
		Rect(C, X, Y + H - T, Len, T, Color);
		Rect(C, X, Y + H - Len, T, Len, Color);
		Rect(C, X + W - Len, Y + H - T, Len, T, Color);
		Rect(C, X + W - T, Y + H - Len, T, Len, Color);
	}

	void Glow(UCanvas* C, float X, float Y, float W, float H, float U, const FLinearColor& Color)
	{
		static const float Alphas[] = { 0.22f, 0.11f, 0.05f };
		for (int32 I = 0; I < UE_ARRAY_COUNT(Alphas); ++I)
		{
			const float O = (I + 1) * 2.f * U;
			Frame(C, X - O, Y - O, W + 2.f * O, H + 2.f * O, 2.f * U, A(Color, Color.A * Alphas[I]));
		}
	}

	void Dashed(UCanvas* C, float X, float Y, float W, float H, float Dash, float T, const FLinearColor& Color)
	{
		for (float P = 0.f; P < W; P += 2.f * Dash)
		{
			const float L = FMath::Min(Dash, W - P);
			Rect(C, X + P, Y, L, T, Color);
			Rect(C, X + P, Y + H - T, L, T, Color);
		}
		for (float P = 0.f; P < H; P += 2.f * Dash)
		{
			const float L = FMath::Min(Dash, H - P);
			Rect(C, X, Y + P, T, L, Color);
			Rect(C, X + W - T, Y + P, T, L, Color);
		}
	}

	float Text(UCanvas* C, UFont* Font, const FString& Str, float X, float Y, float Scale, const FLinearColor& Color, float Align)
	{
		float TW = 0.f, TH = 0.f;
		C->TextSize(Font, Str, TW, TH, Scale, Scale);
		if (Color.A > 0.f && !Str.IsEmpty())
		{
			FCanvasTextItem Item(FVector2D(X - TW * Align, Y), FText::FromString(Str), Font, Color);
			Item.Scale = FVector2D(Scale, Scale);
			C->DrawItem(Item);
		}
		return TW;
	}

	float Rich(UCanvas* C, UFont* Font, const FString& Str, float X, float Y, float Scale, const FLinearColor& TextColor,
		const FLinearColor& KeyColor, bool bMeasure)
	{
		float LineW = 0.f, LineH = 0.f;
		C->TextSize(Font, TEXT("Ag"), LineW, LineH, Scale, Scale);
		const float KeyScale = Scale * 0.82f, PadX = 5.f * Scale, Gap = 3.f * Scale;
		float At = X;
		int32 I = 0;
		while (I < Str.Len())
		{
			const int32 Open = Str.Find(TEXT("["), ESearchCase::CaseSensitive, ESearchDir::FromStart, I);
			const int32 Close = Open >= 0 ? Str.Find(TEXT("]"), ESearchCase::CaseSensitive, ESearchDir::FromStart, Open) : -1;
			const int32 PlainEnd = Close > Open ? Open : Str.Len();
			if (PlainEnd > I)
			{
				const FString Plain = Str.Mid(I, PlainEnd - I);
				At += bMeasure ? Text(C, Font, Plain, At, Y, Scale, FLinearColor::Transparent) : Text(C, Font, Plain, At, Y, Scale, TextColor);
			}
			if (Close <= Open)
			{
				break;
			}
			// кнопка: рамка, лёгкая заливка, надпись капсом
			const FString Key = Str.Mid(Open + 1, Close - Open - 1).ToUpper();
			float KW = 0.f, KH = 0.f;
			C->TextSize(Font, Key, KW, KH, KeyScale, KeyScale);
			const float BoxW = KW + 2.f * PadX, BoxH = LineH * 0.95f, BoxY = Y + (LineH - BoxH) * 0.5f;
			if (!bMeasure)
			{
				Rect(C, At + Gap, BoxY, BoxW, BoxH, A(KeyColor, 0.14f * KeyColor.A));
				Frame(C, At + Gap, BoxY, BoxW, BoxH, FMath::Max(1.f, Scale), A(KeyColor, 0.85f * KeyColor.A));
				Text(C, Font, Key, At + Gap + PadX, BoxY + (BoxH - KH) * 0.5f, KeyScale, KeyColor);
			}
			At += BoxW + 2.f * Gap;
			I = Close + 1;
		}
		return At - X;
	}

	float RichCentered(UCanvas* C, UFont* Font, const FString& Str, float X, float Y, float Scale, const FLinearColor& TextColor,
		const FLinearColor& KeyColor)
	{
		const float W = Rich(C, Font, Str, 0.f, Y, Scale, TextColor, KeyColor, true);
		Rich(C, Font, Str, X - W * 0.5f, Y, Scale, TextColor, KeyColor);
		return W;
	}
}
