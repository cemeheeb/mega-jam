#include "RunEnemy.h"

#include "Animation/AnimSequenceBase.h"
#include "Components/AudioComponent.h"
#include "Components/PointLightComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Components/TextRenderComponent.h"
#include "Engine/SkeletalMesh.h"
#include "Engine/StaticMesh.h"
#include "Engine/World.h"
#include "GameFramework/Pawn.h"
#include "Kismet/GameplayStatics.h"
#include "Materials/MaterialInterface.h"
#include "PhysicsEngine/PhysicsAsset.h"
#include "RunAudio.h"
#include "RunDirector.h"
#include "RunGen.h"
#include "UObject/ConstructorHelpers.h"

using namespace RunGen;
using namespace RunEnemyTune;

namespace
{
	template <typename T>
	T* LoadQuiet(const TCHAR* Path)
	{
		return LoadObject<T>(nullptr, Path, nullptr, LOAD_NoWarn | LOAD_Quiet);
	}
}

ARunEnemy::ARunEnemy()
{
	PrimaryActorTick.bCanEverTick = true;
	SetRootComponent(CreateDefaultSubobject<USceneComponent>(TEXT("Root")));
	static ConstructorHelpers::FObjectFinder<UStaticMesh> Cube(TEXT("/Engine/BasicShapes/Cube.Cube"));
	static ConstructorHelpers::FObjectFinder<UMaterialInterface> Dark(TEXT("/Game/Game/Materials/MI_Gray_Dark.MI_Gray_Dark"));
	static ConstructorHelpers::FObjectFinder<UMaterialInterface> Hot(TEXT("/Game/Game/Materials/MI_Gray_Door.MI_Gray_Door"));
	static ConstructorHelpers::FObjectFinder<UMaterialInterface> Pale(TEXT("/Game/Game/Materials/MI_Gray_Linen.MI_Gray_Linen"));
	MatDark = Dark.Succeeded() ? Dark.Object : nullptr;
	MatHot = Hot.Succeeded() ? Hot.Object : nullptr;
	MatPale = Pale.Succeeded() ? Pale.Object : nullptr;

	Body = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("Body"));
	Head = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("Head"));
	for (UStaticMeshComponent* M : { Body.Get(), Head.Get() })
	{
		M->SetupAttachment(RootComponent);
		M->SetMobility(EComponentMobility::Movable);
		M->SetCollisionProfileName(TEXT("NoCollision"));
		M->SetReceivesDecals(false);
		if (Cube.Succeeded())
		{
			M->SetStaticMesh(Cube.Object);
		}
	}
	Label = CreateDefaultSubobject<UTextRenderComponent>(TEXT("Label"));
	Label->SetupAttachment(RootComponent);
	Label->SetHorizontalAlignment(EHTA_Center);
	Label->SetWorldSize(16.f);
	Label->SetTextRenderColor(FColor(255, 70, 40));
}

const TCHAR* ARunEnemy::DisplayName(int32 InKind)
{
	return InKind == ThreatHuman ? TEXT("Another you") : InKind == ThreatRobot ? TEXT("Mad maintenance robot") : TEXT("Rat");
}

int32 ARunEnemy::StartHealth(int32 InKind)
{
	return InKind == ThreatHuman ? HumanHealth : InKind == ThreatRobot ? RobotHealth : RatHealth;
}

void ARunEnemy::MakeSkeletal(USkeletalMesh* Mesh)
{
	Skel = NewObject<USkeletalMeshComponent>(this);
	Skel->SetupAttachment(RootComponent);
	Skel->SetCollisionProfileName(TEXT("NoCollision"));
	Skel->SetReceivesDecals(false);
	Skel->SetSkeletalMeshAsset(Mesh);
	Skel->SetAnimationMode(EAnimationMode::AnimationSingleNode);
	Skel->VisibilityBasedAnimTickOption = EVisibilityBasedAnimTickOption::AlwaysTickPoseAndRefreshBones;
	Skel->RegisterComponent();
	Body->SetVisibility(false);
	Head->SetVisibility(false);
}

void ARunEnemy::PlayAnim(UAnimSequenceBase* Anim, bool bLoop, float Rate)
{
	if (!Skel || !Anim)
	{
		return;
	}
	if (AnimNow != Anim)
	{
		AnimNow = Anim;
		Skel->PlayAnimation(Anim, bLoop);
	}
	Skel->SetPlayRate(Rate);
}

void ARunEnemy::Setup(int32 InKind, int32 InEnemyId, ARunDirector* InDirector, const FVector& FloorPos, int32 Health, float StartStun)
{
	Kind = InKind;
	EnemyId = InEnemyId;
	Director = InDirector;
	Pos = FloorPos;
	if (const APawn* Pawn = UGameplayStatics::GetPlayerPawn(this, 0))
	{
		const FVector To = (Pawn->GetActorLocation() - Pos).GetSafeNormal2D();   // сразу лицом к игроку
		Dir = To.IsNearlyZero() ? Dir : To;
	}
	// размеры тела и головы в сантиметрах — для заглушек из блоков, если модели нет
	FVector BodySize(70, 70, 150), HeadSize(46, 46, 30);
	UMaterialInterface* BodyMat = MatDark;
	UMaterialInterface* HeadMat = MatHot;
	if (Kind == ThreatHuman)
	{
		BodySize = FVector(34, 52, 140);
		HeadSize = FVector(26, 26, 28);
		HeadMat = MatPale;
		Radius = 32.f;
		LabelZ = 200.f;
		// «другой ты»: модель злого двойника (/Game/Characters/OldEnemy/SK_OldEnemy), когда она появится;
		// пока её нет — тот же герой. Обе стоят на скелете манекена шаблона и играют его анимации
		USkeletalMesh* Mesh = LoadQuiet<USkeletalMesh>(TEXT("/Game/Characters/OldEnemy/SK_OldEnemy.SK_OldEnemy"));
		Mesh = Mesh ? Mesh : LoadQuiet<USkeletalMesh>(TEXT("/Game/Characters/Engineer/SK_Engineer.SK_Engineer"));
		if (Mesh)
		{
			MakeSkeletal(Mesh);
			AnimIdle = LoadQuiet<UAnimSequenceBase>(TEXT("/Game/Characters/Mannequins/Anims/Unarmed/MM_Idle.MM_Idle"));
			AnimMove = LoadQuiet<UAnimSequenceBase>(TEXT("/Game/Characters/Mannequins/Anims/Unarmed/Jog/MF_Unarmed_Jog_Fwd.MF_Unarmed_Jog_Fwd"));
			AnimAttack = LoadQuiet<UAnimSequenceBase>(TEXT("/Game/Characters/Mannequins/Anims/Unarmed/Attack/MM_Attack_02.MM_Attack_02"));
			// реакции на попадание в шаблоне аддитивные и одним клипом не играются: оглушённый он отшатывается (Place)
			AnimDeath = LoadQuiet<UAnimSequenceBase>(TEXT("/Game/Characters/Mannequins/Anims/Death/MM_Death_Front_01.MM_Death_Front_01"));
			MoveRate = HumanSpeed / 450.f;
		}
	}
	else if (Kind == ThreatRats)
	{
		BodySize = FVector(42, 18, 18);
		HeadSize = FVector(12, 12, 12);
		HeadMat = MatDark;
		Radius = 16.f;
		LabelZ = 60.f;
		// крыса-мутант автора (SourceArt/characters/mutant-rat): 2 м с хвостом, свой скелет и семь анимаций
		if (USkeletalMesh* Mesh = LoadQuiet<USkeletalMesh>(TEXT("/Game/Characters/MutantRat/SK_MutantRat.SK_MutantRat")))
		{
			MakeSkeletal(Mesh);
			Radius = 30.f;
			LabelZ = 115.f;
			AnimIdle = LoadQuiet<UAnimSequenceBase>(TEXT("/Game/Characters/MutantRat/A_MutantRat_Aggro.A_MutantRat_Aggro"));
			AnimMove = LoadQuiet<UAnimSequenceBase>(TEXT("/Game/Characters/MutantRat/A_MutantRat_Walk.A_MutantRat_Walk"));
			AnimAttack = LoadQuiet<UAnimSequenceBase>(TEXT("/Game/Characters/MutantRat/A_MutantRat_Attack.A_MutantRat_Attack"));
			AnimLeap = LoadQuiet<UAnimSequenceBase>(TEXT("/Game/Characters/MutantRat/A_MutantRat_Leap.A_MutantRat_Leap"));
			AnimHit = LoadQuiet<UAnimSequenceBase>(TEXT("/Game/Characters/MutantRat/A_MutantRat_Hit.A_MutantRat_Hit"));
			AnimDeath = LoadQuiet<UAnimSequenceBase>(TEXT("/Game/Characters/MutantRat/A_MutantRat_Death.A_MutantRat_Death"));
			MoveRate = RatSpeed / 120.f;   // цикл рыси — 1 м/с; чуть медленнее пути, чтобы лапы не мельтешили
		}
	}
	else
	{
		Radius = 38.f;
		LabelZ = 165.f;
		// робот-ремонтник на гусеницах (модель автора из Tripo, 15.11): 130 × 114 × 130 см, лицо меша — +Y
		if (UStaticMesh* Model = LoadQuiet<UStaticMesh>(TEXT("/Game/Characters/MaintenanceRobot/SM_MaintenanceRobot.SM_MaintenanceRobot")))
		{
			bModel = true;
			Body->SetStaticMesh(Model);
			Body->EmptyOverrideMaterials();
			BodySize = FVector(100, 100, Model->GetBoundingBox().Max.Z);
			BodyMat = nullptr;
			Head->SetVisibility(false);
		}
		// горелка: на замахе вспыхивает бело-голубым — по ней замах виден и в красной аварийной комнате
		Torch = NewObject<UPointLightComponent>(this);
		Torch->SetupAttachment(Body);
		Torch->SetRelativeLocation(FVector(0.f, 62.f, 78.f));
		Torch->SetIntensityUnits(ELightUnits::Unitless);
		Torch->SetIntensity(0.f);
		Torch->SetAttenuationRadius(520.f);
		Torch->SetLightColor(FLinearColor(0.55f, 0.8f, 1.f));
		Torch->SetCastShadows(false);
		Torch->RegisterComponent();
		MoveLoop = RunAudio::Loop(this, TEXT("RobotMove"), 0.3f, 0.5f);
	}
	HalfHeight = BodySize.Z * 0.5f;
	Body->SetWorldScale3D(bModel ? FVector(1.f) : BodySize / 100.f);
	Head->SetWorldScale3D(HeadSize / 100.f);
	if (BodyMat)
	{
		Body->SetMaterial(0, BodyMat);
	}
	if (HeadMat)
	{
		Head->SetMaterial(0, HeadMat);
	}
	ShowHealth(Health);
	StunFor = StartStun;
	State = EState::Stun;
	StateT = 0.f;
	PlayAnim(AnimIdle, true);
	Place();
}

void ARunEnemy::ShowHealth(int32 Health)
{
	Pips.Reset();
	for (int32 I = 0; I < Health; ++I)
	{
		Pips += TEXT("#");
	}
	if (State != EState::Windup)
	{
		Label->SetText(FText::FromString(Pips));
	}
}

float ARunEnemy::WindupTime() const
{
	if (Kind == ThreatRats)
	{
		return bLeap ? RatLeapWindup : RatBiteWindup;
	}
	if (Kind == ThreatHuman)
	{
		return (AnimAttack ? AnimAttack->GetPlayLength() : 1.f) * HumanHitAt - 0.06f;
	}
	return RobotWindup;
}

float ARunEnemy::StrikeTime() const
{
	if (Kind == ThreatRats)
	{
		return bLeap ? RatLeapAir : (AnimAttack ? AnimAttack->GetPlayLength() : 0.8f) - RatBiteWindup;
	}
	if (Kind == ThreatHuman)
	{
		return (AnimAttack ? AnimAttack->GetPlayLength() : 1.f) * 0.75f - WindupTime();
	}
	return RobotLungeTime;
}

float ARunEnemy::HitTime() const
{
	if (Kind == ThreatRats)
	{
		return bLeap ? RatLeapHitAt - RatLeapWindup : RatBiteAt - RatBiteWindup;
	}
	return Kind == ThreatHuman ? 0.06f : RobotLungeTime * 0.6f;
}

float ARunEnemy::RecoverTime() const
{
	if (Kind == ThreatRats)
	{
		return bLeap ? 0.4f + RatRecover : RatRecover;   // после прыжка ещё доигрывает приземление
	}
	return Kind == ThreatHuman ? HumanRecover : RobotRecover;
}

void ARunEnemy::Enter(EState Next)
{
	State = Next;
	StateT = 0.f;
	// замах виден и над головой: жёлтый знак вместо полоски здоровья
	const bool bWarn = Next == EState::Windup;
	Label->SetText(bWarn ? FText::FromString(TEXT("!")) : FText::FromString(Pips));
	Label->SetTextRenderColor(bWarn ? FColor(255, 215, 40) : FColor(255, 70, 40));
	Label->SetWorldSize(bWarn ? 38.f : 16.f);
	switch (Next)
	{
	case EState::Chase:
		PlayAnim(AnimMove, true, MoveRate);
		break;
	case EState::Windup:
		bStruck = false;
		AnimNow = nullptr;   // удар всегда с начала анимации
		PlayAnim(bLeap && AnimLeap ? AnimLeap.Get() : AnimAttack.Get(), false);
		if (Kind == ThreatRobot)
		{
			RunAudio::PlayAt(this, TEXT("RobotAttack"), Pos, 0.9f);
		}
		break;
	case EState::Strike:
		if (Kind == ThreatRats)
		{
			RunAudio::PlayAt(this, TEXT("RatAttack"), Pos, 0.9f, FMath::FRandRange(0.92f, 1.08f));
		}
		break;
	case EState::Recover:
		if (Kind == ThreatHuman)
		{
			PlayAnim(AnimIdle, true);
		}
		break;
	case EState::Stun:
		AnimNow = nullptr;
		PlayAnim(AnimHit ? AnimHit.Get() : AnimIdle.Get(), false);
		break;
	case EState::Dead:
		break;
	}
}

void ARunEnemy::Knock(const FVector& From, float StunSeconds)
{
	if (State == EState::Dead)
	{
		return;
	}
	StunFor = FMath::Max(State == EState::Stun ? StunFor - StateT : 0.f, StunSeconds);
	Push = FVector(Pos.X - From.X, Pos.Y - From.Y, 0.f).GetSafeNormal2D() * 420.f;
	Enter(EState::Stun);   // замах сорван
	if (Kind == ThreatRobot)
	{
		RunAudio::PlayAt(this, TEXT("RobotHit"), Pos);
	}
}

void ARunEnemy::Die()
{
	if (State == EState::Dead)
	{
		return;
	}
	State = EState::Dead;
	StateT = 0.f;
	Push = FVector::ZeroVector;
	AnimNow = nullptr;
	PlayAnim(AnimDeath, false);
	if (Skel && Kind == ThreatRats)
	{
		// у шерсти крысы лоскуты с изнаночными двойниками: у лежащей на боку они смотрят вверх и уходят в собственную
		// тень чёрными клочьями (кадр самопроверки 15.11). Убитая тени не отбрасывает
		Skel->SetCastShadow(false);
	}
	Label->SetVisibility(false);
	if (Torch)
	{
		Torch->SetIntensity(0.f);
	}
	if (MoveLoop)
	{
		MoveLoop->FadeOut(0.4f, 0.f);
	}
	// у каждого своя смерть (автор, 15.11): крыса, робот, человек; Death — только смерть героя
	RunAudio::PlayAt(this, Kind == ThreatRobot ? TEXT("RobotDeath") : Kind == ThreatRats ? TEXT("RatDeath") : TEXT("HumanDeath"), Pos, 0.9f);
	SetLifeSpan(45.f);   // тело лежит, пока игрок в комнате; потом исчезает само
}

void ARunEnemy::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);
	StateT += DeltaSeconds;
	if (State == EState::Dead)
	{
		if (Skel && Kind == ThreatHuman && !bRagdoll && StateT >= 0.3f)
		{
			StartRagdoll();
		}
		if (!bRagdoll)
		{
			Place();   // робот заваливается; у остальных играет анимация смерти
		}
		return;
	}
	APawn* Pawn = UGameplayStatics::GetPlayerPawn(this, 0);
	if (!Pawn || !Director.IsValid() || Director->GetPhase() != ERunPhase::Playing)
	{
		PlayAnim(AnimIdle, true);
		return;
	}
	const FVector P = Pawn->GetActorLocation();
	const FVector To(P.X - Pos.X, P.Y - Pos.Y, 0.f);
	const float Dist = To.Size2D();
	const FVector ToDir = To.GetSafeNormal2D();
	LeapCooldown -= DeltaSeconds;

	if (!Push.IsNearlyZero(1.f))
	{
		Move(Push * DeltaSeconds, Pawn);
		Push *= FMath::Max(0.f, 1.f - 6.f * DeltaSeconds);
	}

	switch (State)
	{
	case EState::Stun:
		if (StateT >= StunFor)
		{
			Enter(EState::Chase);
		}
		break;

	case EState::Chase:
	{
		// куда идти: прямо к игроку или сначала к двери, если между ними стена тамбура
		const FVector Aim = Director->SteerTarget(Pos, P);
		const FVector Want = FVector(Aim.X - Pos.X, Aim.Y - Pos.Y, 0.f).GetSafeNormal2D();
		if (!Want.IsNearlyZero())
		{
			// поворот не мгновенный: противника можно обойти
			const float Turn = Kind == ThreatRobot ? 200.f : 420.f;
			const float Have = Dir.Rotation().Yaw;
			Dir = FRotator(0.f, Have + FMath::Clamp(FMath::FindDeltaAngleDegrees(Have, Want.Rotation().Yaw), -Turn * DeltaSeconds, Turn * DeltaSeconds), 0.f).Vector();
		}
		const float Speed = Kind == ThreatHuman ? HumanSpeed : Kind == ThreatRobot ? RobotSpeed : RatSpeed;
		Walk(Dir, Speed, DeltaSeconds, Pawn);
		PlayAnim(AnimMove, true, MoveRate);
		if (Kind == ThreatRats)
		{
			VoiceIn -= DeltaSeconds;
			if (VoiceIn <= 0.f)
			{
				VoiceIn = FMath::FRandRange(4.f, 8.f);
				RunAudio::PlayAt(this, TEXT("RatIdle"), Pos, 0.7f);
			}
		}
		// чем бить: крыса издалека прыгает (если смотрит на игрока), вблизи все бьют с замаха
		const bool bFacing = FVector::DotProduct(Dir, ToDir) > 0.8f;
		const float Start = Kind == ThreatHuman ? HumanStartRange : Kind == ThreatRobot ? RobotStartRange : RatBiteRange;
		if (Kind == ThreatRats && AnimLeap && bFacing && LeapCooldown <= 0.f && Dist > RatLeapMin && Dist < RatLeapMax)
		{
			bLeap = true;
			Enter(EState::Windup);
		}
		else if (Dist < Start + Radius && FVector::DotProduct(Dir, ToDir) > 0.3f)
		{
			bLeap = false;
			Enter(EState::Windup);
		}
		break;
	}

	case EState::Windup:
		// стоит и целится: доворачивается за игроком. Это время игрока — уйти или ударить первым
		if (Dist > 1.f)
		{
			const float Have = Dir.Rotation().Yaw;
			Dir = FRotator(0.f, Have + FMath::Clamp(FMath::FindDeltaAngleDegrees(Have, ToDir.Rotation().Yaw), -260.f * DeltaSeconds, 260.f * DeltaSeconds), 0.f).Vector();
		}
		if (StateT >= WindupTime())
		{
			StrikeDir = Dir;
			if (bLeap)
			{
				LeapCooldown = RatLeapCooldown;
				LeapSpeed = FMath::Clamp(Dist - 70.f, 120.f, RatLeapMax) / RatLeapAir;   // долетает до места, где игрок был
			}
			Enter(EState::Strike);
		}
		break;

	case EState::Strike:
	{
		// бросок по запомненному направлению; за игроком уже не доворачивает
		const float Speed = Kind == ThreatRobot ? RobotLunge / RobotLungeTime : Kind == ThreatHuman ? 160.f : bLeap ? LeapSpeed : RatBiteLunge / 0.15f;
		const bool bMoving = Kind != ThreatRats || bLeap || StateT < 0.15f;
		if (bMoving)
		{
			Move(StrikeDir * Speed * DeltaSeconds, Pawn);
		}
		if (!bStruck && StateT >= HitTime())
		{
			bStruck = true;
			const float Reach = (Kind == ThreatHuman ? HumanReach : Kind == ThreatRobot ? RobotReach : RatReach) + Radius;
			const FVector Now(P.X - Pos.X, P.Y - Pos.Y, 0.f);
			if (Now.Size2D() < Reach && FVector::DotProduct(Now.GetSafeNormal2D(), StrikeDir) > 0.25f && !Director->IsDodging())
			{
				Director->HurtPlayer(Kind == ThreatHuman ? TEXT("The other you lands a blow.") : Kind == ThreatRobot ? TEXT("The maintenance robot slams into you.")
					: bLeap ? TEXT("A rat hits you in mid-leap, teeth first.") : TEXT("A rat bites you."), Pos,
					Kind == ThreatHuman ? HumanDamage : Kind == ThreatRobot ? RobotDamage : bLeap ? RatLeapDamage : RatDamage);
			}
		}
		if (StateT >= StrikeTime())
		{
			Enter(EState::Recover);
		}
		break;
	}

	case EState::Recover:
		if (StateT >= RecoverTime())
		{
			Enter(EState::Chase);
		}
		break;

	case EState::Dead:
		break;
	}
	Place();
}

void ARunEnemy::StartRagdoll()
{
	bRagdoll = true;
	UPhysicsAsset* Phys = Skel->GetPhysicsAsset();
	Phys = Phys ? Phys : LoadQuiet<UPhysicsAsset>(TEXT("/Game/Characters/Mannequins/Rigs/PA_Mannequin.PA_Mannequin"));
	if (!Phys)
	{
		bRagdoll = false;   // без физассета остаётся клип, как раньше
		return;
	}
	// лежит на полу и стенах; игрок, камера и лучи взаимодействия проходят сквозь тело
	Skel->SetCollisionProfileName(TEXT("Ragdoll"));
	Skel->SetCollisionResponseToChannel(ECC_Pawn, ECR_Ignore);
	Skel->SetCollisionResponseToChannel(ECC_Camera, ECR_Ignore);
	Skel->SetCollisionResponseToChannel(ECC_Visibility, ECR_Ignore);
	Skel->SetPhysicsAsset(Phys, true);
	Skel->SetSimulatePhysics(true);
	Skel->WakeAllRigidBodies();
	if (const APawn* Pawn = UGameplayStatics::GetPlayerPawn(this, 0))
	{
		// чуть назад от удара, чтобы не оседал строго на месте
		Skel->SetAllPhysicsLinearVelocity((Pos - Pawn->GetActorLocation()).GetSafeNormal2D() * 120.f);
	}
}

void ARunEnemy::Place()
{
	SetActorLocation(Pos);
	const FRotator Rot(0.f, Dir.Rotation().Yaw, 0.f);
	if (Skel)
	{
		// лицо скелетных мешей — +Y; оглушённый человек отшатывается назад и возвращается
		const float Reel = Kind == ThreatHuman && State == EState::Stun ? -16.f * FMath::Max(0.f, 1.f - StateT / 0.5f) : 0.f;
		Skel->SetWorldLocationAndRotation(Pos, FRotator(0.f, Rot.Yaw - 90.f, Reel));
	}
	else if (bModel)
	{
		// робот: на ходу дрожит от мотора; на замахе откидывается назад и трясётся, в ударе клюёт вперёд,
		// после удара медленно выпрямляется; убитый заваливается набок
		float Lean = 0.f, Tilt = 0.f, Shake = 0.f, Light = 0.f;
		if (State == EState::Windup)
		{
			const float A = FMath::Clamp(StateT / RobotWindup, 0.f, 1.f);
			Lean = -13.f * FMath::Sqrt(A);
			Shake = 2.5f * A * FMath::Sin(GetWorld()->GetTimeSeconds() * 70.f);
			Light = (5000.f + 9000.f * A) * (0.55f + 0.45f * FMath::Sin(GetWorld()->GetTimeSeconds() * 53.f));
		}
		else if (State == EState::Strike)
		{
			Lean = 16.f;
			Light = 14000.f;
		}
		else if (State == EState::Recover)
		{
			Lean = 16.f * FMath::Max(0.f, 1.f - StateT / 0.9f);
		}
		else if (State == EState::Dead)
		{
			Tilt = 82.f * FMath::Min(1.f, FMath::Square(StateT / 0.55f));
		}
		const float Hum = State == EState::Dead ? 0.f : 0.5f + 0.5f * FMath::Sin(GetWorld()->GetTimeSeconds() * 31.f);
		// лицо меша — +Y: наклон вперёд-назад — это крен (вокруг X меша), завал набок — тангаж
		Body->SetWorldLocationAndRotation(Pos + FVector(0, 0, Hum + (State == EState::Dead ? 22.f * Tilt / 82.f : 0.f)),
			FRotator(Tilt, Rot.Yaw - 90.f + Shake, Lean));
		if (Torch)
		{
			Torch->SetIntensity(Light);
		}
	}
	else
	{
		Body->SetWorldLocationAndRotation(Pos + FVector(0, 0, HalfHeight), Rot);
		const float HeadZ = Kind == ThreatRats ? HalfHeight : HalfHeight * 2.f + Head->GetComponentScale().Z * 50.f;
		Head->SetWorldLocationAndRotation(Pos + (Kind == ThreatRats ? Dir * 24.f : FVector::ZeroVector) + FVector(0, 0, HeadZ), Rot);
	}
	Label->SetWorldLocation(Pos + FVector(0, 0, LabelZ));
	if (const APlayerCameraManager* Cam = UGameplayStatics::GetPlayerCameraManager(this, 0))
	{
		Label->SetWorldRotation(FRotator(0.f, (Cam->GetCameraLocation() - Label->GetComponentLocation()).Rotation().Yaw, 0.f));
	}
}

float ARunEnemy::Move(const FVector& Delta, const AActor* Ignore)
{
	const FVector Before = Pos;
	// Шаг с проверкой препятствий: упёрся — скользит вдоль стены или мебели. Навигационной сетки нет.
	FCollisionQueryParams Params(FName(TEXT("RunEnemy")), false, this);
	if (Ignore)
	{
		Params.AddIgnoredActor(Ignore);
	}
	const FCollisionShape Shape = FCollisionShape::MakeSphere(Radius);
	// низ сферы на 16 см от пола — как у сетки обхода: низкий подиум не мешает, мебель мешает
	const FVector Lift(0, 0, Radius + 16.f);
	FVector Step(Delta.X, Delta.Y, 0.f);
	for (int32 Pass = 0; Pass < 2 && !Step.IsNearlyZero(0.01f); ++Pass)
	{
		FHitResult Hit;
		const FVector From = Pos + Lift;
		if (!GetWorld()->SweepSingleByChannel(Hit, From, From + Step, FQuat::Identity, ECC_WorldStatic, Shape, Params))
		{
			Pos += Step;
			break;
		}
		if (Hit.bStartPenetrating)
		{
			Pos += Step;   // застрял внутри препятствия (например, на нём закрылась створка): дать выйти
			break;
		}
		Pos += Step * FMath::Max(0.f, Hit.Time - 0.02f);
		const FVector N = FVector(Hit.ImpactNormal.X, Hit.ImpactNormal.Y, 0.f).GetSafeNormal2D();
		const FVector Rest = Step * (1.f - Hit.Time);
		Step = Rest - N * FVector::DotProduct(Rest, N);
	}
	return FVector::Dist2D(Before, Pos);
}

void ARunEnemy::Walk(const FVector& WantDir, float Speed, float Dt, const AActor* Ignore)
{
	if (DetourLeft > 0.f)
	{
		DetourLeft -= Dt;
		Move(DetourDir * Speed * Dt, Ignore);
		return;
	}
	const float Want = Speed * Dt;
	const float Done = Move(WantDir * Want, Ignore);
	StuckTime = Done < Want * 0.3f ? StuckTime + Dt : FMath::Max(0.f, StuckTime - Dt);
	if (StuckTime > 0.35f)
	{
		// прямой путь закрыт мебелью: полсекунды идём вбок, каждый раз в другую сторону
		StuckTime = 0.f;
		DetourLeft = 0.6f;
		bDetourFlip = !bDetourFlip;
		DetourDir = FVector(-WantDir.Y, WantDir.X, 0.f) * (bDetourFlip ? 1.f : -1.f);
	}
}
