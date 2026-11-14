// Аномалия опасной комнаты: разряды, радиация, сбой гравитации, замедление времени или эхо (DESIGN.md 5.9).
// Пока всё схематично, из блоков. Аномалия живёт в своей комнате; двери при ней открыты, вернуться можно
// всегда (решение автора 13.11). Противники — отдельно, в RunEnemy.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "RunThreat.generated.h"

class ARunDirector;
class UMaterialInterface;
class UStaticMesh;
class UStaticMeshComponent;

/** Числа угроз. Правятся здесь, пока идёт подбор ощущений. */
namespace RunThreatTune
{
	// эхо: повторяет путь игрока с задержкой
	constexpr float EchoDelay = 3.5f;
	constexpr float EchoReach = 60.f;
	// первые секунды в комнате разряды и луч не бьют: игрок должен успеть оглядеться
	constexpr float EntryGrace = 2.0f;
	// застывший момент: разряды включаются по циклу
	constexpr float BarCycle = 2.8f;
	constexpr float BarOn = 0.9f;
	constexpr float BarWarn = 0.7f;
	constexpr float BarHalfWidth = 30.f;
	// радиация: урон, если простоять в зонах в сумме столько секунд
	constexpr float RadiationDose = 1.3f;
	constexpr float RadiationRadius = 130.f;
	constexpr int32 RadiationZones = 5;
	// сбой гравитации: тянет к стене, у стены бьёт
	constexpr float GravityCycle = 5.f;
	constexpr float GravityWarn = 1.2f;
	constexpr float GravityPull = 270.f;
	constexpr float GravityWallReach = 70.f;
	// замедление времени: в зонах игрок медленный, а луч вращается вокруг центра комнаты с обычной скоростью
	constexpr float SlowFactor = 0.3f;
	constexpr float SlowRadius = 180.f;
	constexpr int32 SlowZones = 3;
	constexpr float ArmDegPerSec = 40.f;
	constexpr float ArmLength = 430.f;
	constexpr float ArmInner = 70.f;   // у самого центра луч не бьёт
	// урон по игроку, из 100 (решение автора 14.11: у каждой угрозы свой; числа — допущение).
	// Среднее около 25 — как прежние четыре попадания на забег, под которые подбирался баланс
	constexpr float EchoDamage = 20.f;
	constexpr float BarDamage = 30.f;
	constexpr float RadiationDamage = 20.f;   // за каждую набранную дозу
	constexpr float GravityDamage = 30.f;
	constexpr float BeamDamage = 25.f;
}

UCLASS()
class MEGAJAM_API ARunThreat : public AActor
{
	GENERATED_BODY()

public:
	ARunThreat();

	/** Kind — номер аномалии из RunGen. Origin — центр пола комнаты. */
	void Setup(int32 InKind, ARunDirector* InDirector, const FVector& InOrigin, int32 ArrivalDoor, uint32 Seed);

	/** Аномалии и эхо остаются в комнате; человек, робот и крысы — противники (RunEnemy). */
	static bool IsAnomaly(int32 InKind);

	virtual void Tick(float DeltaSeconds) override;

	static const TCHAR* DisplayName(int32 Kind);

private:
	struct FBody
	{
		UStaticMeshComponent* Mesh = nullptr;
		FVector Pos = FVector::ZeroVector;
		FVector Dir = FVector(1, 0, 0);
		float Stun = 0.f;
		float Radius = 30.f;
		float HalfHeight = 50.f;
	};

	struct FZone
	{
		FVector Center = FVector::ZeroVector;
		float Radius = 100.f;
		UStaticMeshComponent* Mesh = nullptr;
	};

	struct FBar
	{
		bool bSpansY = true;   // true: полоса тянется вдоль Y и стоит на координате X = Coord
		float Coord = 0.f;
		float Phase = 0.f;
		UStaticMeshComponent* Mesh = nullptr;
	};

	int32 Kind = 0;
	FVector Origin = FVector::ZeroVector;
	float Age = 0.f;
	uint32 Rand = 1;
	TWeakObjectPtr<ARunDirector> Director;

	TArray<FBody> Bodies;
	TArray<FZone> Zones;
	TArray<FBar> Bars;
	TArray<TPair<float, FVector>> Trail;   // путь игрока для эха: время, место
	float Exposure = 0.f;
	float ArmAngle = 0.f;
	int32 GravityDir = 0;
	int32 GravityStep = -1;

	UPROPERTY() TArray<TObjectPtr<UStaticMeshComponent>> Shapes;
	UPROPERTY() TObjectPtr<UStaticMesh> Cube;
	UPROPERTY() TObjectPtr<UStaticMesh> Cylinder;
	UPROPERTY() TObjectPtr<UMaterialInterface> MatHot;
	UPROPERTY() TObjectPtr<UMaterialInterface> MatDark;
	UPROPERTY() TObjectPtr<UMaterialInterface> MatGlow;
	UPROPERTY() TObjectPtr<UMaterialInterface> MatGreen;
	UPROPERTY() TObjectPtr<UMaterialInterface> MatLight;

	UStaticMeshComponent* AddShape(UStaticMesh* Mesh, UMaterialInterface* Mat, const FVector& SizeCm, const FVector& WorldPos);
	float Random01();
	FVector RandomFloorPoint(const FVector& Avoid, float AvoidRadius);
	void Hurt(const TCHAR* Text, const FVector& From, float Damage);

	void TickEcho(float Dt, const FVector& P);
	void TickBars(const FVector& Local);
	void TickRadiation(float Dt, const FVector& P);
	void TickGravity(float Dt, APawn* Pawn, const FVector& Local);
	void TickSlowTime(float Dt, const FVector& P, const FVector& Local);
};
