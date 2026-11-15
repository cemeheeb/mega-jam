#include "RunAudio.h"

#include "Camera/PlayerCameraManager.h"
#include "Components/AudioComponent.h"
#include "GameFramework/Actor.h"
#include "Kismet/GameplayStatics.h"
#include "Sound/SoundBase.h"

namespace
{
	// что уже искали: найденное держится слабой ссылкой, отсутствующее запоминается, чтобы не искать каждый кадр
	TMap<FName, TWeakObjectPtr<USoundBase>> GFound;
	TMap<FName, double> GMissingAt;
}

USoundBase* RunAudio::Find(FName Name)
{
	if (const TWeakObjectPtr<USoundBase>* Hit = GFound.Find(Name))
	{
		if (Hit->IsValid())
		{
			return Hit->Get();
		}
	}
	// В редакторе отсутствующий звук ищем заново не чаще раза в 10 секунд: автор может импортировать его, не закрывая
	// игру. В упакованной сборке набор звуков не меняется: чего нет — того нет, второй раз не ищем.
	const double Now = FPlatformTime::Seconds();
	if (const double* At = GMissingAt.Find(Name))
	{
#if WITH_EDITOR
		if (Now - *At < 10.0)
#endif
		{
			return nullptr;
		}
	}
	const FString Id = Name.ToString();
	USoundBase* Sound = LoadObject<USoundBase>(nullptr, *FString::Printf(TEXT("/Game/Audio/S_%s.S_%s"), *Id, *Id), nullptr, LOAD_NoWarn | LOAD_Quiet);
	if (Sound)
	{
		GFound.Add(Name, Sound);
		GMissingAt.Remove(Name);
	}
	else
	{
		if (!GMissingAt.Contains(Name))
		{
			// один раз на имя: по журналу видно, какого звука игре не хватило
			UE_LOG(LogTemp, Display, TEXT("Run: sound S_%s is missing"), *Id);
		}
		GMissingAt.Add(Name, Now);
	}
	return Sound;
}

void RunAudio::Play(const UObject* WorldContext, FName Name, float Volume, float Pitch)
{
	if (USoundBase* Sound = WorldContext ? Find(Name) : nullptr)
	{
		UGameplayStatics::PlaySound2D(WorldContext, Sound, Volume, Pitch);
	}
}

void RunAudio::PlayAt(const UObject* WorldContext, FName Name, const FVector& Location, float Volume, float Pitch)
{
	USoundBase* Sound = WorldContext ? Find(Name) : nullptr;
	if (!Sound)
	{
		return;
	}
	float Near = 1.f;
	if (const APlayerCameraManager* Cam = UGameplayStatics::GetPlayerCameraManager(WorldContext, 0))
	{
		Near = 1.f - FMath::Clamp((FVector::Dist(Cam->GetCameraLocation(), Location) - 300.f) / 1500.f, 0.f, 1.f);
	}
	if (Near > 0.02f)
	{
		UGameplayStatics::PlaySound2D(WorldContext, Sound, Volume * Near, Pitch);
	}
}

UAudioComponent* RunAudio::Loop(AActor* Owner, FName Name, float Volume, float FadeIn, float StartTime)
{
	USoundBase* Sound = Owner ? Find(Name) : nullptr;
	if (!Sound)
	{
		return nullptr;
	}
	UAudioComponent* C = NewObject<UAudioComponent>(Owner);
	C->SetSound(Sound);
	C->bAllowSpatialization = false;
	C->bIsUISound = true;          // не замолкает на паузе
	C->bAutoDestroy = false;
	C->bStopWhenOwnerDestroyed = true;
	C->RegisterComponent();
	if (FadeIn > 0.f)
	{
		C->FadeIn(FadeIn, Volume, StartTime);
	}
	else
	{
		C->SetVolumeMultiplier(Volume);
		C->Play(StartTime);
	}
	return C;
}
