#include "MenuHUD.h"

#include "MenuDirector.h"
#include "LogoDust.h"
#include "CanvasItem.h"
#include "Engine/Canvas.h"
#include "Engine/Engine.h"
#include "Engine/Font.h"
#include "Engine/Texture2D.h"
#include "EngineUtils.h"
#include "Fonts/SlateFontInfo.h"
#include "GameFramework/PlayerController.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"
#include "Misc/Paths.h"
#include "UnrealClient.h"

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
	float ItemsRight = X0;
	float ItemsBottom = Y0;
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
		ItemsRight = FMath::Max(ItemsRight, X0 + 14.f * S + Size.X);   // с запасом на сдвиг выделенного: логотип не дёргается
		ItemsBottom = At.Y + Size.Y;
		if (G > 0.01f)
		{
			FLinearColor Bar = Orange;
			Bar.A = G * ItemsAppear;
			DrawRect(Bar, X0 - 16.f * S, At.Y + Size.Y * 0.18f, 4.f * S, Size.Y * 0.64f);
		}
	}
	// логотип справа от пунктов: высота букв — от верха первого пункта до низа последнего, между ними тонкая черта
	if (!bLogoLoaded)
	{
		bLogoLoaded = true;
		Logo = LoadObject<UTexture2D>(nullptr, TEXT("/Game/UI/T_Logo.T_Logo"));
	}
	if (Logo && Logo->GetSizeY() > 0)
	{
		const float LettersShare = 132.f / 156.f;   // буквы занимают по высоте столько текстуры (поля по 12 px)
		const float BlockH = ItemsBottom - Y0;
		float H = BlockH / LettersShare;
		float W = H * Logo->GetSizeX() / Logo->GetSizeY();
		const float Gap = 88.f * S;
		const float Left = ItemsRight + Gap;
		const float MaxW = SX - Left - 96.f * S;     // не шире экрана с полем справа
		if (W > MaxW && MaxW > 0.f)
		{
			H *= MaxW / W;
			W = MaxW;
		}
		const float MidY = (Y0 + ItemsBottom) * 0.5f;
		FLinearColor Line = Paper;
		Line.A = 0.22f * ItemsAppear;
		DrawRect(Line, ItemsRight + Gap * 0.45f, Y0 - 6.f * S, 1.5f * S, BlockH + 12.f * S);
		DrawLogo(D, FVector2D(Left, MidY - H * 0.5f), FVector2D(W, H), ItemsAppear, T);
	}

	// подсказка
	FLinearColor Hint = Paper;
	Hint.A = 0.38f * ItemsAppear;
	DrawMenuText(Canvas, TEXT("W / S  CHOOSE      ENTER  SELECT"), FVector2D(X0, Y0 + AMenuDirector::ItemCount * Step + 26.f * S),
		12.f * S, TEXT("Regular"), 300, Hint);

	// проверка без рук (-MenuShot): снимки меню на 6-й и 40-й секунде
	if (MenuShots < 2 && FParse::Param(FCommandLine::Get(), TEXT("MenuShot")) && T > (MenuShots == 0 ? 6.f : 40.f))
	{
		FScreenshotRequest::RequestScreenshot(FPaths::ProjectSavedDir() / FString::Printf(TEXT("Screenshots/Menu/menu_%d.png"), MenuShots),
			false, false);
		UE_LOG(LogTemp, Display, TEXT("Menu: shot %d at %.1f s, screen %.0f x %.0f, hole at %.0f, %.0f, shadow radius %.0f"), MenuShots, T,
			SX, SY, DustCenter.X, DustCenter.Y, DustRadius);
		++MenuShots;
	}

	// затемнение: появление и уход
	const float Fade = D->GetFade();
	if (Fade > 0.001f)
	{
		DrawRect(FLinearColor(0.f, 0.f, 0.f, Fade), 0.f, 0.f, SX, SY);
	}
}

namespace
{
	uint32 DustHash(uint32 A, uint32 B)
	{
		uint32 H = A * 0x9E3779B1u ^ (B + 0x7F4A7C15u + (A << 6) + (A >> 2));
		H ^= H >> 16;
		H *= 0x85EBCA6Bu;
		H ^= H >> 13;
		H *= 0xC2B2AE35u;
		H ^= H >> 16;
		return H;
	}

	float DustUnit(uint32 H)
	{
		return (H & 0xFFFFFF) / 16777216.f;
	}
}

void AMenuHUD::DrawLogo(const AMenuDirector* D, FVector2D Pos, FVector2D Size, float Appear, float Clock)
{
	using namespace LogoDust;
	const FTexture* Tex = Logo->GetResource();
	const FVector2D Texel(Size.X / TexW, Size.Y / TexH);
	auto Piece = [&](FVector2D At, FVector2D TexAt, FVector2D TexSize, FVector2D ScreenSize, const FLinearColor& Color, float Angle)
	{
		FCanvasTileItem Tile(At, Tex, ScreenSize, TexAt / FVector2D(TexW, TexH), (TexAt + TexSize) / FVector2D(TexW, TexH), Color);
		Tile.BlendMode = SE_BLEND_Translucent;
		if (Angle != 0.f)
		{
			Tile.Rotation = FRotator(0.f, Angle, 0.f);
			Tile.PivotPoint = FVector2D(0.5f, 0.5f);
		}
		Canvas->DrawItem(Tile);
	};
	const FLinearColor Base(Paper.R, Paper.G, Paper.B, Appear);
	// буквы до разреза — как есть
	Piece(Pos, FVector2D::ZeroVector, FVector2D(SplitX, TexH), FVector2D(SplitX * Texel.X, Size.Y), Base, 0.f);

	// чёрная дыра на экране: середина тени и её радиус (тень — b = 3√3/2 радиуса горизонта, дыра в HoleDistance)
	FVector2D C(Canvas->SizeX * 0.5f, Canvas->SizeY * 0.4f);
	float Rs = 0.08f * Canvas->SizeY;
	if (APlayerController* PC = GetOwningPlayerController())
	{
		FVector Eye;
		FRotator View;
		PC->GetPlayerViewPoint(Eye, View);
		const FVector Dir = D->HoleDirection();
		const float Dist = FMath::Max(D->HoleDistance, 3.f);
		const float Alpha = FMath::Asin(FMath::Min(2.598f * FMath::Sqrt(1.f - 1.f / Dist) / Dist, 0.9f));
		const FVector Side = Dir.RotateAngleAxis(FMath::RadiansToDegrees(Alpha), View.Quaternion().GetUpVector());
		FVector2D A, B;
		if (PC->ProjectWorldLocationToScreen(Eye + Dir * 1.0e6f, A, false) && PC->ProjectWorldLocationToScreen(Eye + Side * 1.0e6f, B, false))
		{
			C = A;
			Rs = FMath::Max(FVector2D::Distance(A, B), 8.f);
		}
	}

	// порог съеденности: от начального к пределу, никогда его не достигая
	const float Thr = LimitThreshold + (StartThreshold - LimitThreshold) / (1.f + Clock / 60.f);
	constexpr float Loose = 0.08f;     // столько выше порога куски ещё висят рядом, оторванные
	constexpr float EdgeBand = 0.03f;  // столько ниже порога — край, из него идёт поток
	if (DustEdgeAt < 0.f || FMath::Abs(DustEdgeAt - Thr) > 0.002f)
	{
		DustEdgeAt = Thr;
		DustEdge.Reset();
		for (int32 I = 0; I < Num; ++I)
		{
			const float E = Chunks[I].Eat / 65535.f;
			if (E <= Thr && E > Thr - EdgeBand)
			{
				DustEdge.Add(I);
			}
		}
	}
	const FVector2D CellTex(Cell, Cell);
	const FVector2D CellScreen = CellTex * Texel;
	for (int32 I = 0; I < Num; ++I)
	{
		const FChunk& K = Chunks[I];
		const float E = K.Eat / 65535.f;
		const FVector2D Home = Pos + FVector2D(K.X, K.Y) * Texel;
		if (E <= Thr)
		{
			// размер — разность краёв, посчитанных так же, как у соседей: швов между кусками нет
			const FVector2D Far = Pos + FVector2D(K.X + Cell, K.Y + Cell) * Texel;
			Piece(Home, FVector2D(K.X, K.Y), CellTex, Far - Home, Base, 0.f);
		}
		else if (E < Thr + Loose)
		{
			// оторванный кусок: чем дальше за порогом, тем дальше от места к дыре и прозрачнее; чуть дрожит
			const float L = (E - Thr) / Loose;
			const uint32 H = DustHash(I, 77u);
			const FVector2D To = (C - Home).GetSafeNormal();
			const FVector2D Wobble(FMath::Sin(Clock * (0.6f + DustUnit(H)) + I), FMath::Cos(Clock * (0.5f + DustUnit(H >> 3)) + I));
			const FVector2D At = Home + To * (L * 34.f * Texel.X) + Wobble * (1.2f * Texel.X * L);
			FLinearColor Color = Base;
			Color.A *= FMath::Pow(1.f - L, 1.5f);
			Piece(At, FVector2D(K.X, K.Y), CellTex, CellScreen, Color, (DustUnit(H >> 7) - 0.5f) * 40.f * L);
		}
	}
	if (DustEdge.Num() == 0)
	{
		return;
	}

	// поток: у каждой пылинки свой срок жизни; по истечении она рождается снова в другом месте края. Положение —
	// формула возраста, поэтому поток полный с первого кадра. Путь — спираль в плоскости диска (сплющенный эллипс,
	// наклонённый как диск на экране); у горизонта эллипс раскрывается в круг фотонного кольца: линза дыры
	// показывает падающее вещество по кольцу.
	const float Roll = FMath::DegreesToRadians(D->DiskRoll);
	const float Ring = Rs * RingScale;
	const FVector2D Ax(FMath::Cos(Roll), FMath::Sin(Roll)), Ay(-FMath::Sin(Roll), FMath::Cos(Roll));
	constexpr float Flat0 = 0.35f;         // сплющенность пути вдали (диск почти с ребра; меньше — не читается)
	constexpr int32 NumDust = 1400;
	constexpr int32 Trail = 3;             // хвост: столько копий позади, всё прозрачнее
	for (int32 P = 0; P < NumDust; ++P)
	{
		const uint32 H = DustHash(P, 1u);
		const float Life = 25.f + 20.f * DustUnit(H);   // очень медленно: путь занимает полминуты
		const float Run = Clock + DustUnit(H >> 5) * Life * 40.f;
		const uint32 Cycle = static_cast<uint32>(Run / Life);
		const float S = (Run - Cycle * Life) / Life;
		const FChunk& K = Chunks[DustEdge[DustHash(P, Cycle) % DustEdge.Num()]];
		const FVector2D Home = Pos + (FVector2D(K.X, K.Y) + CellTex * 0.5f) * Texel;
		const FVector2D D0 = Home - C;
		const FVector2D V0(FVector2D::DotProduct(D0, Ax), FVector2D::DotProduct(D0, Ay));   // путь начинается кругом: F = 1
		const float R0 = FMath::Max(V0.Size(), Ring * 1.3f);
		const float A0 = FMath::Atan2(V0.Y, V0.X);
		const float Turns = 0.6f + 0.5f * DustUnit(DustHash(P, Cycle + 7u));
		const float Bright = 0.45f + 0.35f * DustUnit(H >> 11);
		const float MyRing = Ring * (0.92f + 0.3f * DustUnit(DustHash(P, Cycle + 3u)));     // кольцо толще одной линии
		const float Spread = (DustUnit(DustHash(P, Cycle + 5u)) - 0.5f) * 0.12f * R0;      // разлёт поперёк пути
		auto At = [&](float X)
		{
			X = FMath::Clamp(X, 0.f, 1.f);
			// к дыре быстро вначале и всё медленнее у горизонта (там почти застывает); угол, наоборот, набирается
			// к концу: пыль сначала уходит от букв вверх и вправо, потом ложится в диск и обвивает кольцо
			const float G = FMath::Pow(1.f - X, 1.6f);
			const float R = MyRing + (R0 - MyRing) * G + Spread * FMath::Sin(X * UE_PI);
			const float A = A0 - Turns * UE_TWO_PI * FMath::Pow(X, 1.5f);
			const float F = FMath::Lerp(FMath::Lerp(1.f, Flat0, FMath::SmoothStep(0.f, 0.35f, X)), 1.f, FMath::SmoothStep(0.6f, 1.f, X));
			return C + Ax * (FMath::Cos(A) * R) + Ay * (FMath::Sin(A) * R * F);
		};
		for (int32 J = Trail; J >= 0; --J)
		{
			const float X = S - 0.006f * J;
			if (X <= 0.f)
			{
				continue;
			}
			const FVector2D Now = At(X);
			const FVector2D Ahead = At(X + 0.01f);
			const float Angle = FMath::RadiansToDegrees(FMath::Atan2(Ahead.Y - Now.Y, Ahead.X - Now.X));
			// цвет: буквы -> оранжевый -> тёмно-красный (красное смещение у горизонта), в конце гаснет
			FLinearColor Color = FMath::Lerp(Base, FLinearColor(1.f, 0.6f, 0.28f), FMath::SmoothStep(0.3f, 0.7f, X));
			Color = FMath::Lerp(Color, FLinearColor(0.75f, 0.12f, 0.05f), FMath::SmoothStep(0.72f, 1.f, X));
			Color.A = Appear * Bright * FMath::SmoothStep(0.f, 0.05f, X) * (1.f - FMath::SmoothStep(0.8f, 1.f, X))
				* FMath::Lerp(0.45f, 1.f, FMath::SmoothStep(0.15f, 0.5f, X))           // у букв тусклее: там все пути рядом
				* (1.f - J / (Trail + 1.f));
			const float Grow = 1.f + 2.5f * X * X * X;                         // у горизонта тянется вдоль орбиты
			const FVector2D Sz = CellScreen * FVector2D(Grow, 1.f) * (1.7f - 0.8f * X);
			FCanvasTileItem Tile(Now - Sz * 0.5f, Tex, Sz, FVector2D(K.X, K.Y) / FVector2D(TexW, TexH),
				(FVector2D(K.X, K.Y) + CellTex) / FVector2D(TexW, TexH), Color);
			Tile.BlendMode = SE_BLEND_Additive;
			Tile.Rotation = FRotator(0.f, Angle, 0.f);
			Tile.PivotPoint = FVector2D(0.5f, 0.5f);
			Canvas->DrawItem(Tile);
		}
	}
	DustCenter = C;
	DustRadius = Rs;
}
