// Аномалия опасной комнаты (DESIGN.md 5.9, решение автора 15.11): мини чёрная дыра, дым, замедление времени,
// заражение грибами. Аномалия живёт в своей комнате; двери при ней открыты, вернуться можно всегда (решение 13.11).
// Противники — отдельно, в RunEnemy. Разгерметизация — не угроза догадки, а ворота правильного пути (ведущий забега).

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "RunThreat.generated.h"

class ARunDirector;
class ARunRoom;
class UInstancedStaticMeshComponent;
class UMaterialInterface;
class UStaticMesh;
class UStaticMeshComponent;

/** Числа угроз. Правятся здесь, пока идёт подбор ощущений. */
namespace RunThreatTune
{
	// чёрная дыра: шар-линза в углу комнаты, подошёл близко — смерть (решение автора 15.11)
	constexpr float HoleRadius = 85.f;        // шар-линза: искажение плавно сходит на нет к его краю
	constexpr float HoleHeight = 140.f;       // центр над полом
	constexpr float HoleInset = 140.f;        // от лица колонок обеих стен угла до центра
	constexpr float HoleKill = 120.f;         // от центра дыры до середины капсулы: ближе — затянуло
	constexpr float HoleKillMin = 80.f;       // если рядом место предмета, радиус ужимается, но не меньше
	constexpr float HoleClearance = 70.f;     // столько остаётся от края смерти до ближайшего места предмета
	constexpr float HoleWarn = 360.f;         // отсюда подсказка на экране
	constexpr float SpaghettiTime = 1.4f;     // вытягивание и падение в дыру
	constexpr int32 HoleDust = 14;            // соринки на орбитах вокруг дыры: по ним её замечают
	// дым: слой от груди до потолка в комнате и в тамбурах; стоя — урон, вприсядку — нет (решение автора 15.11).
	// Нижняя кромка ниже головы стоящего героя (замечание автора 15.11: «ниже головы, ещё ниже»)
	constexpr float SmokeBottom = 110.f;
	constexpr float SmokeCameraGap = 8.f;     // камера героя вприсядку держится на столько ниже кромки

	constexpr int32 SmokeLayers = 7;
	constexpr float SmokeTick = 2.f;          // стоя в дыму: урон каждые столько секунд
	constexpr float SmokeDamage = 6.f;
	// замедление времени: урона нет, у середины комнаты время почти стоит (не ниже SlowMin, DESIGN 5.9)
	constexpr float SlowMin = 0.1f;
	constexpr float SlowCore = 60.f;          // ближе к середине — SlowMin
	constexpr float SlowRadius = 420.f;       // дальше — обычное время
	constexpr int32 SlowDebris = 18;          // обломки на орбитах: по их скорости видно, где время гуще
	// разгерметизация: без скафандра душит быстро (снять его там нельзя, но шлюз мог открыться при другом раскладе)
	constexpr float VacuumTick = 1.f;
	constexpr float VacuumDamage = 8.f;
	// грибы: без скафандра, если ходить долго, — урон (решение автора 15.11)
	constexpr float SporeGrace = 6.f;         // первые секунды в комнате без урона
	constexpr float SporeTick = 3.f;
	constexpr float SporeDamage = 5.f;
}

UCLASS()
class MEGAJAM_API ARunThreat : public AActor
{
	GENERATED_BODY()

public:
	ARunThreat();

	/** Kind — номер угрозы из RunGen. Room — комната, в которой она живёт (центр пола — её положение). */
	void Setup(int32 InKind, ARunDirector* InDirector, ARunRoom* InRoom, int32 ArrivalDoor, uint32 Seed);

	/** Аномалии остаются в комнате; человек, робот и крысы — противники (RunEnemy). */
	static bool IsAnomaly(int32 InKind);
	/** Разгерметизация: не из RunGen (там её нет — это ворота правильного пути), ставит ведущий забега. */
	static constexpr int32 Decompression = 100;

	virtual void Tick(float DeltaSeconds) override;
	virtual void EndPlay(const EEndPlayReason::Type Reason) override;

	static const TCHAR* DisplayName(int32 Kind);

private:
	struct FDebris
	{
		UStaticMeshComponent* Mesh = nullptr;
		float Radius = 100.f;
		float Angle = 0.f;
		float Height = 100.f;
		float Spin = 0.f;
		float Speed = 45.f;                    // градусов в секунду
		FRotator Tilt = FRotator::ZeroRotator; // наклон орбиты (у дыры)
	};

	int32 Kind = 0;
	FVector Origin = FVector::ZeroVector;
	float Age = 0.f;
	uint32 Rand = 1;
	TWeakObjectPtr<ARunDirector> Director;
	TWeakObjectPtr<ARunRoom> Room;
	float Exposure = 0.f;
	float Ticker = 0.f;

	// чёрная дыра
	FVector HolePos = FVector::ZeroVector;
	float KillRadius = RunThreatTune::HoleKill;
	float SwallowT = -1.f;                 // ≥ 0 — героя затягивает
	FVector SwallowFeet = FVector::ZeroVector;
	FTransform MeshRelative;

	TArray<FDebris> Debris;

	UPROPERTY() TArray<TObjectPtr<UStaticMeshComponent>> Shapes;
	UPROPERTY() TObjectPtr<UStaticMesh> Cube;
	UPROPERTY() TObjectPtr<UStaticMesh> Sphere;
	UPROPERTY() TObjectPtr<UStaticMesh> Plane;
	UPROPERTY() TObjectPtr<UMaterialInterface> MatDark;
	UPROPERTY() TObjectPtr<UMaterialInterface> MatLight;

	UStaticMeshComponent* AddShape(UStaticMesh* Mesh, UMaterialInterface* Mat, const FVector& SizeCm, const FVector& WorldPos);
	float Random01();
	void Hurt(const TCHAR* Text, const FVector& From, float Damage, bool bKnockback);
	/** Игрок в этой комнате или в одном из её тамбуров. */
	bool PlayerHere(const FVector& P) const;

	void SetupBlackHole();
	void SetupSmoke();
	void SetupSlowTime();
	void TickBlackHole(float Dt, APawn* Pawn);
	void TickSmoke(float Dt, const FVector& P);
	void TickSlowTime(float Dt, APawn* Pawn, const FVector& P);
	void TickFungus(float Dt, const FVector& P);
	void SetupVacuum();
	void TickVacuum(float Dt, const FVector& P);
};
