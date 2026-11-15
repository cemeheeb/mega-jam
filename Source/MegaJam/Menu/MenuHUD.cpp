#include "MenuHUD.h"

#include "MenuDirector.h"
#include "CanvasItem.h"
#include "CanvasTypes.h"
#include "Engine/Canvas.h"
#include "Engine/Engine.h"
#include "Engine/Font.h"
#include "Engine/Texture2D.h"
#include "Engine/TextureRenderTarget2D.h"
#include "EngineUtils.h"
#include "Fonts/SlateFontInfo.h"
#include "GameFramework/PlayerController.h"
#include "Kismet/KismetRenderingLibrary.h"
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

	/** Прямоугольник одного цвета на заданном холсте (DrawRect у AHUD рисует только на экран). */
	void Fill(UCanvas* Canvas, const FLinearColor& Color, float X, float Y, float W, float H)
	{
		FCanvasTileItem Tile(FVector2D(X, Y), FVector2D(W, H), Color);
		Tile.BlendMode = SE_BLEND_AlphaBlend;      // как Translucent, но пишет и прозрачность: слою меню она нужна
		Canvas->DrawItem(Tile);
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

	// Всё меню рисуется в слой (см. Layer), на экран он ложится в конце со сдвигом цветов. Слоя нет — рисуется прямо.
	UCanvas* Ui = Canvas;
	FDrawToRenderTargetContext LayerContext;
	bool bLayer = false;
	if (!Layer || Layer->SizeX != Canvas->SizeX || Layer->SizeY != Canvas->SizeY)
	{
		Layer = UKismetRenderingLibrary::CreateRenderTarget2D(this, FMath::Max(Canvas->SizeX, 1), FMath::Max(Canvas->SizeY, 1),
			RTF_RGBA16f, FLinearColor::Transparent, false);
	}
	if (Layer)
	{
		UKismetRenderingLibrary::ClearRenderTarget2D(this, Layer, FLinearColor::Transparent);
		UCanvas* To = nullptr;
		FVector2D ToSize;
		UKismetRenderingLibrary::BeginDrawCanvasToRenderTarget(this, Layer, To, ToSize, LayerContext);
		if (To && To->Canvas)
		{
			Ui = To;
			bLayer = true;
			To->Canvas->SetWriteDestinationAlpha(true);   // буквы пишут в слой и прозрачность: по ней гасится кадр под меню
		}
	}
	// Слой хранит линейный цвет, экран — кодированный гаммой: полупрозрачное в слое вышло бы светлее, чем при рисовании
	// прямо на экран. Прозрачность в степени гаммы возвращает прежнюю яркость (на чёрном — точно).
	auto Alpha = [bLayer](float A)
	{
		return bLayer ? FMath::Pow(FMath::Clamp(A, 0.f, 1.f), 2.2f) : A;
	};

	const float X0 = 132.f * S;
	// название — когда автор его выберет; под ним короткая оранжевая черта
	const float Appear = FMath::Clamp((T - 1.2f) / 1.5f, 0.f, 1.f);
	if (!D->GetTitle().IsEmpty())
	{
		FLinearColor C = Paper;
		C.A = Alpha(Appear);
		const FVector2D Size = DrawMenuText(Ui, D->GetTitle().ToUpper(), FVector2D(X0, SY * 0.26f), 64.f * S, TEXT("Light"), 260, C);
		FLinearColor Bar = Orange;
		Bar.A = Alpha(Appear);
		Fill(Ui, Bar, X0 + 4.f * S, SY * 0.26f + Size.Y + 14.f * S, 72.f * S, 3.f * S);
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
		C.A = Alpha((0.55f + 0.45f * G) * ItemsAppear);
		const FVector2D Size = DrawMenuText(Ui, AMenuDirector::ItemName(I), At, 26.f * S, TEXT("Regular"), 420, C);
		ItemBoxes[I] = FBox2D(FVector2D(X0 - 30.f * S, At.Y - 8.f * S), FVector2D(At.X + Size.X + 30.f * S, At.Y + Size.Y + 8.f * S));
		ItemsRight = FMath::Max(ItemsRight, X0 + 14.f * S + Size.X);   // с запасом на сдвиг выделенного: логотип не дёргается
		ItemsBottom = At.Y + Size.Y;
		if (G > 0.01f)
		{
			FLinearColor Bar = Orange;
			Bar.A = Alpha(G * ItemsAppear);
			Fill(Ui, Bar, X0 - 16.f * S, At.Y + Size.Y * 0.18f, 4.f * S, Size.Y * 0.64f);
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
		Line.A = Alpha(0.22f * ItemsAppear);
		Fill(Ui, Line, ItemsRight + Gap * 0.45f, Y0 - 6.f * S, 1.5f * S, BlockH + 12.f * S);
		FCanvasTileItem Tile(FVector2D(Left, MidY - H * 0.5f), Logo->GetResource(), FVector2D(W, H),
			FLinearColor(Paper.R, Paper.G, Paper.B, Alpha(ItemsAppear)));
		Tile.BlendMode = SE_BLEND_AlphaBlend;
		Ui->DrawItem(Tile);
	}

	// подсказка
	FLinearColor Hint = Paper;
	Hint.A = Alpha(0.38f * ItemsAppear);
	DrawMenuText(Ui, TEXT("W / S  CHOOSE      ENTER  SELECT"), FVector2D(X0, Y0 + AMenuDirector::ItemCount * Step + 26.f * S),
		12.f * S, TEXT("Regular"), 300, Hint);

	// Слой — на экран: красный канал уходит от линзы, синий — к ней, зелёный на месте. Под курсором каналы сходятся,
	// дальше расходятся (AMenuDirector::LensShift, как у сцены в M_MenuLens). Сначала кадр под меню гасится
	// по прозрачности слоя (как при обычном рисовании поверх), потом каналы слоя прибавляются.
	if (bLayer)
	{
		UKismetRenderingLibrary::EndDrawCanvasToRenderTarget(this, LayerContext);
		const FTexture* Tex = Layer->GetResource();
		const FVector2D Screen(SX, SY);
		const FVector2D Mid = D->GetLens() * Screen;
		auto Flat = [&](const FLinearColor& Color, ESimpleElementBlendMode Mode)
		{
			FCanvasTileItem Tile(FVector2D::ZeroVector, Tex, Screen, Color);
			Tile.BlendMode = Mode;
			Canvas->DrawItem(Tile);
		};
		// сдвиг у каждой точки свой, поэтому слой натянут на сетку: её узлы сдвинуты, между ними картинка тянется
		auto Warped = [&](float Sign, const FLinearColor& Color)
		{
			constexpr int32 NX = 32, NY = 18;
			auto Node = [&](int32 X, int32 Y, FVector2D& Pos, FVector2D& UV)
			{
				UV = FVector2D(float(X) / NX, float(Y) / NY);
				const FVector2D At = UV * Screen;
				Pos = At + D->LensShift(At - Mid, SY) * Sign;
			};
			TArray<FCanvasUVTri> Tris;
			Tris.Reserve(NX * NY * 2);
			for (int32 Y = 0; Y < NY; ++Y)
			{
				for (int32 X = 0; X < NX; ++X)
				{
					FCanvasUVTri A, B;
					A.V0_Color = A.V1_Color = A.V2_Color = B.V0_Color = B.V1_Color = B.V2_Color = Color;
					Node(X, Y, A.V0_Pos, A.V0_UV);
					Node(X + 1, Y, A.V1_Pos, A.V1_UV);
					Node(X + 1, Y + 1, A.V2_Pos, A.V2_UV);
					B.V0_Pos = A.V0_Pos;
					B.V0_UV = A.V0_UV;
					B.V1_Pos = A.V2_Pos;
					B.V1_UV = A.V2_UV;
					Node(X, Y + 1, B.V2_Pos, B.V2_UV);
					Tris.Add(A);
					Tris.Add(B);
				}
			}
			FCanvasTriangleItem Item(Tris, Tex);
			Item.BlendMode = SE_BLEND_Additive;
			Canvas->DrawItem(Item);
		};
		Flat(FLinearColor::White, SE_BLEND_AlphaHoldout);
		Warped(1.f, FLinearColor(1.f, 0.f, 0.f));
		Flat(FLinearColor(0.f, 1.f, 0.f), SE_BLEND_Additive);
		Warped(-1.f, FLinearColor(0.f, 0.f, 1.f));
	}

	// проверка без рук (-MenuShot): снимки меню на 6-й и 40-й секунде
	if (MenuShots < 2 && FParse::Param(FCommandLine::Get(), TEXT("MenuShot")) && T > (MenuShots == 0 ? 6.f : 40.f))
	{
		FScreenshotRequest::RequestScreenshot(FPaths::ProjectSavedDir() / FString::Printf(TEXT("Screenshots/Menu/menu_%d.png"), MenuShots),
			false, false);
		UE_LOG(LogTemp, Display, TEXT("Menu: shot %d at %.1f s, screen %.0f x %.0f, lens at %.0f, %.0f, shift at the far corner %.1f px, layer %d"),
			MenuShots, T, SX, SY, D->GetLens().X * SX, D->GetLens().Y * SY,
			D->LensShift(FVector2D(SX, SY), SY).Size(), bLayer ? 1 : 0);
		++MenuShots;
	}

	// затемнение: появление и уход
	const float Fade = D->GetFade();
	if (Fade > 0.001f)
	{
		DrawRect(FLinearColor(0.f, 0.f, 0.f, Fade), 0.f, 0.f, SX, SY);
	}
}
