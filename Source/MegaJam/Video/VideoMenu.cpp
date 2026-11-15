#include "VideoMenu.h"

#include "CanvasItem.h"
#include "Engine/Canvas.h"
#include "Engine/Engine.h"
#include "Engine/Font.h"
#include "Fonts/CompositeFont.h"
#include "GameFramework/GameUserSettings.h"
#include "Kismet/KismetSystemLibrary.h"
#include "Misc/ConfigCacheIni.h"
#include "Misc/Paths.h"
#include "Scalability.h"
#include "../Run/RunDirector.h"
#include "../Run/RunHUDStyle.h"

// Size — кегль при масштабе 1 (у Roboto движка, под который подобраны все масштабы экрана, он 9).
UFont* MegaJamUI::LoadFileFont(UObject* Outer, const TCHAR* File, int32 Size)
{
	const FString Path = FPaths::ProjectContentDir() / TEXT("Fonts") / File;
	if (!FPaths::FileExists(Path))
	{
		UE_LOG(LogTemp, Warning, TEXT("UI: нет шрифта %s, остаётся шрифт движка"), *Path);
		return nullptr;
	}
	UFont* Font = NewObject<UFont>(Outer);
	Font->FontCacheType = EFontCacheType::Runtime;
	Font->LegacyFontSize = Size;
	Font->LegacyFontName = TEXT("Default");
	Font->GetMutableInternalCompositeFont() = FCompositeFont(TEXT("Default"), Path, EFontHinting::Default, EFontLoadingPolicy::LazyLoad);
	return Font;
}

namespace
{
	const TCHAR* const VideoSection = TEXT("MegaJam.Video");
	const TCHAR* const BrightnessKey = TEXT("BrightnessStep");
	constexpr int32 MaxBrightnessStep = 4;        // ±4 деления по 0,25 ступени экспозиции
	constexpr float BrightnessPerStep = 0.25f;
	int32 GBrightnessStep = TNumericLimits<int32>::Min();   // ещё не прочитано из ini

	const EWindowMode::Type Modes[] = { EWindowMode::Fullscreen, EWindowMode::WindowedFullscreen, EWindowMode::Windowed };
	const float FrameLimits[] = { 30.f, 60.f, 120.f, 144.f, 0.f };   // 0 — без ограничения

	UGameUserSettings* Settings()
	{
		return GEngine ? GEngine->GetGameUserSettings() : nullptr;
	}

	FString QualityName(int32 Level)
	{
		static const TCHAR* const Names[] = { TEXT("Low"), TEXT("Medium"), TEXT("High"), TEXT("Epic"), TEXT("Cinematic") };
		return Level >= 0 && Level < UE_ARRAY_COUNT(Names) ? FString(Names[Level]) : FString(TEXT("Custom"));
	}

	float ScalePercent(const UGameUserSettings* GS, float* OutMin = nullptr, float* OutMax = nullptr)
	{
		float Normalized = 0.f, Current = 100.f, Min = 50.f, Max = 100.f;
		GS->GetResolutionScaleInformationEx(Normalized, Current, Min, Max);
		if (OutMin)
		{
			*OutMin = FMath::Max(50.f, Min);
		}
		if (OutMax)
		{
			*OutMax = FMath::Min(100.f, Max);
		}
		return Current;
	}

	// Пресет, на котором стоит большинство групп качества: при «своих» настройках (обычно — свой масштаб разрешения)
	// строка показывает его с пометкой, и стрелки шагают от него
	int32 MajorityLevel(const UGameUserSettings* GS)
	{
		const Scalability::FQualityLevels& Q = GS->ScalabilityQuality;
		const int32 Groups[] = { Q.ViewDistanceQuality, Q.AntiAliasingQuality, Q.ShadowQuality, Q.GlobalIlluminationQuality, Q.ReflectionQuality,
			Q.PostProcessQuality, Q.TextureQuality, Q.EffectsQuality, Q.FoliageQuality, Q.ShadingQuality, Q.LandscapeQuality };
		int32 Count[5] = {};
		for (const int32 G : Groups)
		{
			++Count[FMath::Clamp(G, 0, 4)];
		}
		int32 Best = 0;
		for (int32 L = 1; L < 4; ++L)   // кинематографический не предлагаем: его нет в списке
		{
			Best = Count[L] >= Count[Best] ? L : Best;
		}
		return Best;
	}

	int32 IndexOfMode(EWindowMode::Type Mode)
	{
		for (int32 I = 0; I < UE_ARRAY_COUNT(Modes); ++I)
		{
			if (Modes[I] == Mode)
			{
				return I;
			}
		}
		return 1;
	}
}

int32 FVideoMenu::BrightnessStep()
{
	if (GBrightnessStep == TNumericLimits<int32>::Min())
	{
		int32 Step = 0;
		if (GConfig)
		{
			GConfig->GetInt(VideoSection, BrightnessKey, Step, GGameUserSettingsIni);
		}
		GBrightnessStep = FMath::Clamp(Step, -MaxBrightnessStep, MaxBrightnessStep);
	}
	return GBrightnessStep;
}

float FVideoMenu::GetBrightness()
{
	return BrightnessStep() * BrightnessPerStep;
}

void FVideoMenu::Open()
{
	Selected = 0;
	Note = TEXT("If the game stutters, lower Quality or Resolution Scale.");
	Resolutions.Reset();
	TArray<FIntPoint> All;
	UKismetSystemLibrary::GetSupportedFullscreenResolutions(All);
	if (const UGameUserSettings* GS = Settings())
	{
		All.Add(GS->GetScreenResolution());
		All.Add(GS->GetDesktopResolution());
	}
	for (const FIntPoint& R : All)
	{
		if (R.X >= 1024 && R.Y >= 576)
		{
			Resolutions.AddUnique(R);
		}
	}
	Resolutions.Sort([](const FIntPoint& A, const FIntPoint& B) { return A.X != B.X ? A.X < B.X : A.Y < B.Y; });
}

void FVideoMenu::Move(int32 Step)
{
	Selected = (Selected + Step + NumRows) % NumRows;
}

void FVideoMenu::Select(int32 Row)
{
	if (Row >= 0 && Row < NumRows)
	{
		Selected = Row;
	}
}

FString FVideoMenu::Label(int32 Row)
{
	static const TCHAR* const Labels[] = { TEXT("Quality"), TEXT("Resolution Scale"), TEXT("Display Mode"), TEXT("Resolution"),
		TEXT("VSync"), TEXT("Frame Limit"), TEXT("Brightness"), TEXT("Training Hints"), TEXT("Auto-Detect"), TEXT("Back") };
	return Row >= 0 && Row < NumRows ? FString(Labels[Row]).ToUpper() : FString();
}

bool FVideoMenu::IsEnabled(int32 Row) const
{
	const UGameUserSettings* GS = Settings();
	if (!GS)
	{
		return Row == Back;
	}
	// в окне без рамки разрешение — всегда разрешение рабочего стола
	return Row != Resolution || GS->GetFullscreenMode() != EWindowMode::WindowedFullscreen;
}

FString FVideoMenu::Value(int32 Row) const
{
	const UGameUserSettings* GS = Settings();
	if (!GS)
	{
		return FString();
	}
	switch (Row)
	{
	case Quality:
	{
		const int32 Level = GS->GetOverallScalabilityLevel();
		return Level >= 0 ? QualityName(Level) : QualityName(MajorityLevel(GS)) + TEXT(" (custom)");
	}
	case Scale:
	{
		// 0 у движка — «авто»: процент выбирается по разрешению экрана (r.ScreenPercentage.Default.Desktop.Mode)
		const float Percent = ScalePercent(GS);
		return Percent <= 0.f ? FString(TEXT("Auto")) : FString::Printf(TEXT("%d%%"), FMath::RoundToInt32(Percent));
	}
	case Mode:
	{
		static const TCHAR* const Names[] = { TEXT("Fullscreen"), TEXT("Borderless"), TEXT("Windowed") };
		return Names[IndexOfMode(GS->GetFullscreenMode())];
	}
	case Resolution:
	{
		if (!IsEnabled(Resolution))
		{
			return TEXT("Desktop");
		}
		const FIntPoint R = GS->GetScreenResolution();
		return FString::Printf(TEXT("%d x %d"), R.X, R.Y);
	}
	case VSync: return GS->IsVSyncEnabled() ? TEXT("On") : TEXT("Off");
	case FrameLimit:
	{
		const float Limit = GS->GetFrameRateLimit();
		return Limit <= 0.f ? FString(TEXT("Unlimited")) : FString::Printf(TEXT("%d"), FMath::RoundToInt32(Limit));
	}
	case Brightness:
	{
		const int32 Step = BrightnessStep();
		return Step == 0 ? FString(TEXT("0")) : FString::Printf(TEXT("%+d"), Step);
	}
	case Training: return ARunDirector::IsTrainingOn() ? TEXT("On") : TEXT("Off");
	case Detect: return TEXT("Run test");
	default: return FString();
	}
}

float FVideoMenu::Fill(int32 Row) const
{
	const UGameUserSettings* GS = Settings();
	if (!GS)
	{
		return -1.f;
	}
	if (Row == Scale)
	{
		float Min = 50.f, Max = 100.f;
		const float Current = ScalePercent(GS, &Min, &Max);
		return Current <= 0.f || Max <= Min ? 1.f : FMath::Clamp((Current - Min) / (Max - Min), 0.f, 1.f);
	}
	if (Row == Brightness)
	{
		return (BrightnessStep() + MaxBrightnessStep) / (2.f * MaxBrightnessStep);
	}
	return -1.f;
}

void FVideoMenu::ApplyAndSave(bool bResolution)
{
	UGameUserSettings* GS = Settings();
	if (!GS)
	{
		return;
	}
	if (bResolution)
	{
		GS->ApplyResolutionSettings(false);
		GS->ConfirmVideoMode();   // иначе при следующем запуске движок вернёт прежний режим
	}
	GS->ApplyNonResolutionSettings();
	GS->SaveSettings();
}

void FVideoMenu::Change(int32 Step)
{
	UGameUserSettings* GS = Settings();
	if (!GS || Step == 0 || !IsEnabled(Selected))
	{
		return;
	}
	switch (Selected)
	{
	case Quality:
	{
		const int32 Was = GS->GetOverallScalabilityLevel();
		const int32 Level = FMath::Clamp((Was < 0 ? MajorityLevel(GS) : Was) + Step, 0, 3);
		if (Level == Was)
		{
			return;
		}
		// пресет движка задаёт и масштаб разрешения (у низкого он меньше): строка ниже его покажет, её можно поправить
		GS->SetOverallScalabilityLevel(Level);
		ApplyAndSave(false);
		break;
	}
	case Scale:
	{
		float Min = 50.f, Max = 100.f;
		float Current = ScalePercent(GS, &Min, &Max);
		if (Current <= 0.f)
		{
			Current = Max;   // из «авто» — от полного разрешения: влево 95%, вправо остаётся 100%
		}
		const float Next = FMath::Clamp(FMath::RoundToFloat(Current / 5.f) * 5.f + 5.f * Step, Min, Max);
		GS->SetResolutionScaleValueEx(Next);
		ApplyAndSave(false);
		break;
	}
	case Mode:
	{
		const int32 Index = FMath::Clamp(IndexOfMode(GS->GetFullscreenMode()) + Step, 0, UE_ARRAY_COUNT(Modes) - 1);
		const EWindowMode::Type NewMode = Modes[Index];
		if (NewMode == GS->GetFullscreenMode())
		{
			return;
		}
		const FIntPoint Desktop = GS->GetDesktopResolution();
		FIntPoint Res = GS->GetScreenResolution();
		if (NewMode == EWindowMode::WindowedFullscreen)
		{
			Res = Desktop;
		}
		else if (NewMode == EWindowMode::Windowed && (Res.X >= Desktop.X || Res.Y >= Desktop.Y))
		{
			// окно размером с экран спрячет рамку за краями: берём самое большое разрешение меньше рабочего стола
			Res = FIntPoint(1280, 720);
			for (const FIntPoint& R : Resolutions)
			{
				if (R.X < Desktop.X && R.Y < Desktop.Y)
				{
					Res = R;
				}
			}
		}
		GS->SetFullscreenMode(NewMode);
		GS->SetScreenResolution(Res);
		ApplyAndSave(true);
		break;
	}
	case Resolution:
	{
		if (Resolutions.Num() == 0)
		{
			return;
		}
		const FIntPoint Current = GS->GetScreenResolution();
		int32 Nearest = 0;
		for (int32 I = 0; I < Resolutions.Num(); ++I)
		{
			if (FMath::Abs(Resolutions[I].X * Resolutions[I].Y - Current.X * Current.Y) < FMath::Abs(Resolutions[Nearest].X * Resolutions[Nearest].Y - Current.X * Current.Y))
			{
				Nearest = I;
			}
		}
		const int32 Index = FMath::Clamp(Nearest + Step, 0, Resolutions.Num() - 1);
		if (Resolutions[Index] == Current)
		{
			return;
		}
		GS->SetScreenResolution(Resolutions[Index]);
		ApplyAndSave(true);
		break;
	}
	case VSync:
		GS->SetVSyncEnabled(!GS->IsVSyncEnabled());
		ApplyAndSave(false);
		break;
	case Training:
		ARunDirector::SetTrainingOn(!ARunDirector::IsTrainingOn());   // логика обучения — у ведущего забега
		break;
	case FrameLimit:
	{
		const float Limit = GS->GetFrameRateLimit();
		int32 Index = UE_ARRAY_COUNT(FrameLimits) - 1;
		for (int32 I = 0; I < UE_ARRAY_COUNT(FrameLimits) - 1; ++I)
		{
			if (Limit > 0.f && Limit <= FrameLimits[I] + 0.5f)
			{
				Index = I;
				break;
			}
		}
		Index = FMath::Clamp(Index + Step, 0, UE_ARRAY_COUNT(FrameLimits) - 1);
		GS->SetFrameRateLimit(FrameLimits[Index]);
		ApplyAndSave(false);
		break;
	}
	case Brightness:
	{
		GBrightnessStep = FMath::Clamp(BrightnessStep() + Step, -MaxBrightnessStep, MaxBrightnessStep);
		if (GConfig)
		{
			GConfig->SetInt(VideoSection, BrightnessKey, GBrightnessStep, GGameUserSettingsIni);
			GConfig->Flush(false, GGameUserSettingsIni);
		}
		break;
	}
	default:
		break;
	}
}

bool FVideoMenu::Activate()
{
	if (Selected == Back)
	{
		return true;
	}
	if (Selected == VSync || Selected == Training)
	{
		Change(1);
	}
	else if (Selected == Detect)
	{
		if (UGameUserSettings* GS = Settings())
		{
			// замер процессора и видеокарты (секунда-две, кадр замирает) и подбор пресета под машину
			GS->RunHardwareBenchmark();
			GS->ApplyHardwareBenchmarkResults();
			Note = FString::Printf(TEXT("Detected for this machine: %s, %d%% scale."), *QualityName(GS->GetOverallScalabilityLevel()),
				FMath::RoundToInt32(ScalePercent(GS)));
			UE_LOG(LogTemp, Display, TEXT("Video: benchmark -> %s"), *Note);
		}
	}
	return false;
}

float FVideoMenu::Draw(UCanvas* C, UFont* Font, float X, float Y, float W, float U, TFunctionRef<float(float)> Alpha, FLayout* Out) const
{
	const FLinearColor Teal(0.37f, 0.78f, 0.79f), Panel(0.012f, 0.03f, 0.045f, 0.93f), Dim(1.f, 1.f, 1.f, 0.6f);
	const float Pad = 18.f * U, RowH = 30.f * U, HeadH = 36.f * U, NoteH = 30.f * U;
	const float H = 2.f * Pad + HeadH + NumRows * RowH + NoteH;
	auto Rect = [&](FLinearColor Col, float RX, float RY, float RW, float RH)
	{
		Col.A = Alpha(Col.A);
		FCanvasTileItem Tile(FVector2D(RX, RY), FVector2D(RW, RH), Col);
		Tile.BlendMode = SE_BLEND_AlphaBlend;
		C->DrawItem(Tile);
	};
	// Align: 0 — от X влево направо, 1 — правый край в X, 0.5 — середина в X
	auto Text = [&](const FString& Str, float TX, float TY, float Scale, FLinearColor Col, float Align = 0.f)
	{
		float TW = 0.f, TH = 0.f;
		C->TextSize(Font, Str, TW, TH, Scale, Scale);
		Col.A = Alpha(Col.A);
		FCanvasTextItem Item(FVector2D(TX - TW * Align, TY), FText::FromString(Str), Font, Col);
		Item.Scale = FVector2D(Scale, Scale);
		C->DrawItem(Item);
	};

	// панель в общем стиле экрана (RunHUDStyle): срезанные углы, тонкая кромка, метка-полоска сверху
	const auto Faded = [&](FLinearColor Col)
	{
		Col.A = Alpha(Col.A);
		return Col;
	};
	const float Cut = 16.f * U;
	RunStyle::Panel(C, X, Y, W, H, Cut, Faded(Panel), Faded(FLinearColor(Teal.R, Teal.G, Teal.B, 0.4f)), 1.f * U);
	RunStyle::Rect(C, X + Cut + 8.f * U, Y - 1.f * U, 64.f * U, 3.f * U, Faded(Teal));
	Text(TEXT("SETTINGS"), X + Pad, Y + Pad, 1.25f * U, Teal);
	Rect(FLinearColor(Teal.R, Teal.G, Teal.B, 0.45f), X + Pad, Y + Pad + 26.f * U, W - 2.f * Pad, 1.5f * U);

	const float ValueL = X + W * 0.5f, ValueR = X + W - Pad, Mid = (ValueL + ValueR) * 0.5f;
	if (Out)
	{
		Out->Rows.Reset();
		Out->ValueLeft = ValueL;
		Out->ValueMid = Mid;
	}
	float RY = Y + Pad + HeadH;
	for (int32 Row = 0; Row < NumRows; ++Row, RY += RowH)
	{
		const bool bOn = Row == Selected, bEnabled = IsEnabled(Row);
		const float TextY = RY + 6.f * U;
		if (Out)
		{
			Out->Rows.Add(FBox2D(FVector2D(X, RY), FVector2D(X + W, RY + RowH)));
		}
		if (Row == Detect)
		{
			Rect(FLinearColor(1.f, 1.f, 1.f, 0.08f), X + Pad, RY - 1.f * U, W - 2.f * Pad, 1.f * U);   // действия отделены от значений
		}
		if (bOn)
		{
			Rect(FLinearColor(Teal.R, Teal.G, Teal.B, 0.2f), X + 6.f * U, RY + 2.f * U, W - 12.f * U, RowH - 4.f * U);
			Rect(Teal, X + 6.f * U, RY + 2.f * U, 3.f * U, RowH - 4.f * U);
		}
		const float A = bEnabled ? 1.f : 0.35f;
		Text(Label(Row), X + Pad, TextY, 1.0f * U, bOn ? FLinearColor(1.f, 1.f, 1.f, A) : FLinearColor(1.f, 1.f, 1.f, 0.75f * A));
		const FString Val = Value(Row);
		const float F = Fill(Row);
		if (F >= 0.f)
		{
			// полоса и число справа
			const float BarL = ValueL + 18.f * U, BarR = ValueR - 64.f * U, BarY = RY + RowH * 0.5f - 3.f * U;
			Rect(FLinearColor(1.f, 1.f, 1.f, 0.12f), BarL, BarY, BarR - BarL, 6.f * U);
			Rect(FLinearColor(Teal.R, Teal.G, Teal.B, bOn ? 1.f : 0.7f), BarL, BarY, (BarR - BarL) * F, 6.f * U);
			Text(Val, ValueR - 18.f * U, TextY, 1.0f * U, FLinearColor(1.f, 1.f, 1.f, A), 1.f);
		}
		else if (!Val.IsEmpty())
		{
			Text(Val, Mid, TextY, 1.0f * U, Row == Detect ? FLinearColor(Teal.R, Teal.G, Teal.B, A) : FLinearColor(1.f, 1.f, 1.f, A), 0.5f);
		}
		if (bOn && bEnabled && Row < Detect)
		{
			Text(TEXT("<"), ValueL, TextY, 1.0f * U, Teal);
			Text(TEXT(">"), ValueR, TextY, 1.0f * U, Teal, 1.f);
		}
	}
	Text(Note, X + Pad, RY + 8.f * U, 0.85f * U, Dim);
	return H;
}
