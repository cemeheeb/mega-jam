// Звук игры по именам (решение автора 15.11: звук и музыка — из генераторов, карточки в Студии, SourceArt/audio).
// «DoorOpen» -> /Game/Audio/S_DoorOpen (tools/ue/import_audio.py). Ассета нет — тишина без ошибок: звуки появляются
// по мере того, как автор их генерирует, код менять не нужно.

#pragma once

#include "CoreMinimal.h"

class AActor;
class UAudioComponent;
class UObject;
class USoundBase;

namespace RunAudio
{
	/** Звук по имени карточки в ПаскальКейсе; nullptr, если его ещё не импортировали. */
	MEGAJAM_API USoundBase* Find(FName Name);
	/** Разовый звук без места в мире: интерфейс, действия героя. */
	MEGAJAM_API void Play(const UObject* WorldContext, FName Name, float Volume = 1.f, float Pitch = 1.f);
	/** Разовый звук из точки мира: тише с расстоянием от камеры (в полную силу до 3 м, тишина с 18 м). */
	MEGAJAM_API void PlayAt(const UObject* WorldContext, FName Name, const FVector& Location, float Volume = 1.f, float Pitch = 1.f);
	/** Петля (музыка, фон комнаты, гул аномалии): компонент на акторе, без места в мире. Играет и на паузе.
	 *  FadeIn — за сколько секунд выйти на громкость Volume. nullptr, если звука нет. */
	MEGAJAM_API UAudioComponent* Loop(AActor* Owner, FName Name, float Volume, float FadeIn = 0.f, float StartTime = 0.f);
}
