// Противник: человек (другая версия игрока), робот-ремонтник или крыса-мутант.
// Правила (решение автора 13.11): человек преследует игрока из комнаты в комнату, пока его не убьют;
// остальные остаются в своей комнате, если не успели проскочить в дверь вместе с игроком.
// Кто где находится и сколько у кого здоровья, знает ведущий забега; этот актор — только тело в текущей комнате.
//
// Бой (запрос автора 15.11: «как в классических играх от третьего лица: замах, удар, способы избежать урона»).
// Противник не бьёт касанием. Он подходит, замахивается — это видно и слышно, — бьёт туда, где игрок был в конце
// замаха, и после удара на время открыт. Избежать урона: выйти из-под удара шагом или рывком (ARunDirector, Space),
// сорвать замах ударом ключа, бить в паузу после его удара.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "RunEnemy.generated.h"

class ARunDirector;
class UAnimSequenceBase;
class UAudioComponent;
class UMaterialInterface;
class UPointLightComponent;
class USkeletalMesh;
class USkeletalMeshComponent;
class UStaticMeshComponent;
class UTextRenderComponent;

/** Числа противников. Правятся здесь, пока идёт подбор ощущений. Шаг игрока — 250, бег — 500. */
namespace RunEnemyTune
{
	// человек: идёт следом через двери; бьёт рукой с коротким замахом (анимации манекена шаблона)
	constexpr float HumanSpeed = 330.f;
	constexpr float HumanStartRange = 150.f;   // с этого расстояния начинает удар
	constexpr float HumanReach = 125.f;        // достаёт в момент удара
	constexpr float HumanHitAt = 0.38f;        // момент удара — доля длины анимации
	constexpr float HumanRecover = 0.55f;      // пауза после удара
	constexpr float HumanStun = 1.0f;
	constexpr int32 HumanHealth = 3;
	constexpr float HumanFollowDelay = 3.0f;   // через сколько секунд после игрока он входит в ту же дверь
	// робот-ремонтник: медленный, замах долгий и заметный (откидывается, искрит горелка), бьёт рывком и сильно,
	// после удара надолго замирает
	constexpr float RobotSpeed = 230.f;
	constexpr float RobotStartRange = 190.f;
	constexpr float RobotWindup = 0.8f;
	constexpr float RobotLunge = 150.f;        // рывок вперёд, см
	constexpr float RobotLungeTime = 0.22f;
	constexpr float RobotReach = 115.f;
	constexpr float RobotRecover = 1.5f;
	constexpr float RobotStun = 1.6f;
	constexpr int32 RobotHealth = 4;
	// крысы-мутанты: две, медленнее шага игрока, зато прыгают с трёх-пяти метров; вблизи кусают
	constexpr int32 RatCount = 2;
	constexpr float RatSpeed = 240.f;
	constexpr float RatBiteRange = 135.f;
	constexpr float RatBiteWindup = 0.3f;      // в анимации укуса (0,8 с) крыса сначала подаётся назад
	constexpr float RatBiteAt = 0.4f;          // укус от начала анимации
	constexpr float RatBiteLunge = 45.f;
	constexpr float RatReach = 105.f;
	constexpr float RatLeapMin = 260.f;
	constexpr float RatLeapMax = 520.f;
	constexpr float RatLeapWindup = 0.4f;      // присела — сейчас прыгнет
	constexpr float RatLeapAir = 0.6f;         // в воздухе с 0,4 по 1,0 с анимации прыжка (1,4 с)
	constexpr float RatLeapHitAt = 0.67f;      // укус в прыжке от начала анимации
	constexpr float RatLeapCooldown = 4.f;
	constexpr float RatRecover = 0.45f;
	constexpr float RatStun = 0.6f;
	constexpr int32 RatHealth = 2;
	// урон по игроку, из 100 (шкала 0–100 и свой урон у каждой угрозы — решение автора 14.11; числа — допущение)
	constexpr float HumanDamage = 25.f;
	constexpr float RobotDamage = 35.f;
	constexpr float RatDamage = 12.f;
	constexpr float RatLeapDamage = 18.f;
	// удар игрока
	constexpr float AttackReach = 150.f;
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

	/** Удар игрока: отбросить от From, оглушить, сорвать замах. */
	void Knock(const FVector& From, float StunSeconds);
	/** Убит: анимация смерти, тело остаётся лежать и исчезает само. Ведущий забега сам вычёркивает его из списков. */
	void Die();
	void ShowHealth(int32 Health);

	virtual void Tick(float DeltaSeconds) override;

	int32 Kind = 0;
	int32 EnemyId = 0;
	FVector GetFloorPos() const { return Pos; }
	float GetRadius() const { return Radius; }
	/** Противник жив и идёт на игрока: по этому включается боевая музыка. */
	bool IsHostile() const { return State != EState::Dead; }
	/** Замахивается или бьёт прямо сейчас. */
	bool IsAttacking() const { return State == EState::Windup || State == EState::Strike; }

	static const TCHAR* DisplayName(int32 InKind);
	static int32 StartHealth(int32 InKind);

private:
	enum class EState : uint8 { Chase, Windup, Strike, Recover, Stun, Dead };

	TWeakObjectPtr<ARunDirector> Director;
	FVector Pos = FVector::ZeroVector;
	FVector Dir = FVector(1, 0, 0);
	FVector Push = FVector::ZeroVector;   // остаток отброса после удара игрока
	EState State = EState::Stun;
	float StateT = 0.f;                   // сколько секунд в этом состоянии
	float StunFor = 0.f;
	bool bLeap = false;                   // крыса: этот удар — прыжок
	bool bStruck = false;                 // удар этого замаха уже состоялся (попал или нет)
	float LeapCooldown = 0.f;
	float LeapSpeed = 0.f;
	FVector StrikeDir = FVector(1, 0, 0);
	float VoiceIn = 3.f;                  // крыса: через сколько секунд подаст голос
	float StuckTime = 0.f;                // сколько времени упирается в препятствие
	float DetourLeft = 0.f;               // сколько ещё идёт в обход
	FVector DetourDir = FVector::ZeroVector;
	bool bDetourFlip = false;
	float Radius = 30.f;
	float HalfHeight = 50.f;
	float LabelZ = 150.f;
	FString Pips;                         // подпись здоровья; на замахе её сменяет жёлтый знак «!»
	bool bModel = false;                  // робот: тело — статичный меш с привязкой в центре дна, голова-куб скрыта
	bool bRagdoll = false;                // убитый человек: тело отдано физике и падает само (StartRagdoll)

	UPROPERTY(VisibleAnywhere) TObjectPtr<UStaticMeshComponent> Body;
	UPROPERTY(VisibleAnywhere) TObjectPtr<UStaticMeshComponent> Head;
	UPROPERTY(VisibleAnywhere) TObjectPtr<UTextRenderComponent> Label;
	UPROPERTY() TObjectPtr<UMaterialInterface> MatDark;
	UPROPERTY() TObjectPtr<UMaterialInterface> MatHot;
	UPROPERTY() TObjectPtr<UMaterialInterface> MatPale;
	/** Человек и крыса: скелетный меш, анимации играются по одной (без блюпринта анимации). */
	UPROPERTY() TObjectPtr<USkeletalMeshComponent> Skel;
	UPROPERTY() TObjectPtr<UAnimSequenceBase> AnimIdle;
	UPROPERTY() TObjectPtr<UAnimSequenceBase> AnimMove;
	UPROPERTY() TObjectPtr<UAnimSequenceBase> AnimAttack;
	UPROPERTY() TObjectPtr<UAnimSequenceBase> AnimLeap;
	UPROPERTY() TObjectPtr<UAnimSequenceBase> AnimHit;
	UPROPERTY() TObjectPtr<UAnimSequenceBase> AnimDeath;
	UPROPERTY() TObjectPtr<UAnimSequenceBase> AnimNow;
	float MoveRate = 1.f;                 // скорость проигрывания анимации хода под скорость противника
	/** Робот: горелка вспыхивает на замахе. */
	UPROPERTY() TObjectPtr<UPointLightComponent> Torch;
	UPROPERTY() TObjectPtr<UAudioComponent> MoveLoop;

	void MakeSkeletal(USkeletalMesh* Mesh);
	void PlayAnim(UAnimSequenceBase* Anim, bool bLoop, float Rate = 1.f);
	void Enter(EState Next);
	float WindupTime() const;
	float StrikeTime() const;
	float HitTime() const;                // от начала удара (после замаха)
	float RecoverTime() const;
	/** Возвращает пройденное расстояние. */
	float Move(const FVector& Delta, const AActor* Ignore);
	/** Шаг к цели; упёрся надолго — немного идёт вбок. */
	void Walk(const FVector& WantDir, float Speed, float Dt, const AActor* Ignore);
	void Place();
	/** Человек: клип смерти шаблона кончается не лёжа, и тело застывало согнутым (автор, 15.11). После начала клипа
	 *  тело уходит в рэгдолл на физассете манекена и ложится на пол само. */
	void StartRagdoll();
};
