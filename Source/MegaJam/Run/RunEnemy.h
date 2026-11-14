// Противник: человек (другая версия игрока), робот-инженер или крыса. Пока схематично, из блоков.
// Правила (решение автора 13.11): человек преследует игрока из комнаты в комнату, пока его не убьют;
// остальные остаются в своей комнате, если не успели проскочить в дверь вместе с игроком.
// Кто где находится и сколько у кого здоровья, знает ведущий забега; этот актор — только тело в текущей комнате.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "RunEnemy.generated.h"

class ARunDirector;
class UMaterialInterface;
class UStaticMeshComponent;
class UTextRenderComponent;

/** Числа противников. Правятся здесь, пока идёт подбор ощущений. Скорость бега игрока — 500. */
namespace RunEnemyTune
{
	// человек: медленнее игрока, но не отстаёт и идёт следом через двери
	constexpr float HumanSpeed = 380.f;
	constexpr float HumanReach = 85.f;
	constexpr float HumanStun = 1.0f;
	constexpr int32 HumanHealth = 3;
	constexpr float HumanFollowDelay = 3.0f;   // через сколько секунд после игрока он входит в ту же дверь
	// робот-инженер: медленный, бьёт сильно, после удара замирает
	constexpr float RobotSpeed = 300.f;
	constexpr float RobotReach = 90.f;
	constexpr float RobotStun = 1.6f;
	constexpr int32 RobotHealth = 4;
	// крысы: быстрые, но поворачивают с запаздыванием и проскакивают мимо
	constexpr int32 RatCount = 4;
	constexpr float RatSpeed = 420.f;
	constexpr float RatTurnDegPerSec = 150.f;
	constexpr float RatReach = 55.f;
	constexpr float RatScatter = 1.5f;
	constexpr int32 RatHealth = 1;
	// урон по игроку, из 100 (шкала 0–100 и свой урон у каждой угрозы — решение автора 14.11; числа — допущение).
	// Робот медленный и бьёт сильнее всех, крыса кусает слабо, но их четыре
	constexpr float HumanDamage = 25.f;
	constexpr float RobotDamage = 35.f;
	constexpr float RatDamage = 10.f;
	// удар игрока
	constexpr float AttackReach = 175.f;
	constexpr float AttackCooldown = 0.55f;
	constexpr float AttackStun = 0.7f;
}

UCLASS()
class MEGAJAM_API ARunEnemy : public AActor
{
	GENERATED_BODY()

public:
	ARunEnemy();

	/** Kind — RunGen::ThreatHuman, ThreatRobot или ThreatRats. FloorPos — точка на полу. */
	void Setup(int32 InKind, int32 InEnemyId, ARunDirector* InDirector, const FVector& FloorPos, int32 Health, float StartStun);

	/** Удар игрока: отбросить от From и оглушить. */
	void Knock(const FVector& From, float StunSeconds);
	void ShowHealth(int32 Health);

	virtual void Tick(float DeltaSeconds) override;

	int32 Kind = 0;
	int32 EnemyId = 0;
	FVector GetFloorPos() const { return Pos; }
	float GetRadius() const { return Radius; }

	static const TCHAR* DisplayName(int32 InKind);
	static int32 StartHealth(int32 InKind);

private:
	TWeakObjectPtr<ARunDirector> Director;
	FVector Pos = FVector::ZeroVector;
	FVector Dir = FVector(1, 0, 0);
	FVector Push = FVector::ZeroVector;   // остаток отброса после удара игрока
	float Stun = 0.f;
	float StuckTime = 0.f;                // сколько времени упирается в препятствие
	float DetourLeft = 0.f;               // сколько ещё идёт в обход
	FVector DetourDir = FVector::ZeroVector;
	bool bDetourFlip = false;
	bool bFlee = false;                   // крыса отбегает после укуса
	float Radius = 30.f;
	float HalfHeight = 50.f;

	UPROPERTY(VisibleAnywhere) TObjectPtr<UStaticMeshComponent> Body;
	UPROPERTY(VisibleAnywhere) TObjectPtr<UStaticMeshComponent> Head;
	UPROPERTY(VisibleAnywhere) TObjectPtr<UTextRenderComponent> Label;
	UPROPERTY() TObjectPtr<UMaterialInterface> MatDark;
	UPROPERTY() TObjectPtr<UMaterialInterface> MatHot;
	UPROPERTY() TObjectPtr<UMaterialInterface> MatPale;

	/** Возвращает пройденное расстояние. */
	float Move(const FVector& Delta, const AActor* Ignore);
	/** Шаг к цели; упёрся надолго — немного идёт вбок. */
	void Walk(const FVector& WantDir, float Speed, float Dt, const AActor* Ignore);
	void Place();
};
