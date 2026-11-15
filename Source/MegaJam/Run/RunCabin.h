// Каюта героя (решение автора 15.11, вечер): маленькая комната вне генератора, с неё начинается каждый забег.
// Северная дверь заперта кодовым замком; код — цифры, они же зерно забега (решение автора: цифры, а не слова),
// пустой код — новый корабль. Геометрию даёт блюпринт BP_Room_Cabin (tools/ue/build_rooms.py, cabin()), поведение — этот класс.
// За дверью такой же тамбур, как у комнат: когда створка за игроком закрылась, ведущий забега ставит рубку так,
// что её южный тамбур совпадает с тамбуром каюты, а каюту убирает (ARunDirector::LeaveCabin) — как при смене комнат.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "RunCabin.generated.h"

class ARunDirector;
class UStaticMeshComponent;
class UTextRenderComponent;

/** Размеры каюты. Должны совпадать с cabin() в tools/ue/build_rooms.py. Дверь — на оси y = 0. */
namespace RunCabinGeo
{
	constexpr float InnerFace = 225.f;    // от середины каюты до лица колонок северной стены
	constexpr float OuterFace = 300.f;    // до внешней грани северной стены: дальше тамбур
	constexpr float KeypadY = -112.5f;    // панель замка — на колонке слева от двери
	/** Где стоит рубка относительно каюты: её южный тамбур совпадает с тамбуром каюты. */
	MEGAJAM_API FVector BridgeOffset();
}

UCLASS()
class MEGAJAM_API ARunCabin : public AActor
{
	GENERATED_BODY()

public:
	ARunCabin();

	virtual void BeginPlay() override;
	virtual void Tick(float DeltaSeconds) override;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Run")
	TObjectPtr<USceneComponent> Root;

	TWeakObjectPtr<ARunDirector> Director;

	/** Код принят: створка открывается, когда игрок подходит; табло над дверью — OPEN. */
	void Unlock();
	bool IsUnlocked() const { return bUnlocked; }

	/** Панель замка у двери (мировые координаты) и стоит ли игрок рядом с ней. */
	FVector KeypadLocation() const;
	bool IsNearKeypad(const FVector& PawnPos) const;

	/** Середина стекла зеркала (мировые координаты); стекло смотрит в каюту, на +Y. */
	FVector MirrorCenter() const;

	/** Где игрок приходит в себя: у спальной капсулы, лицом к двери. */
	FVector WakeLocation() const;

	/** Игрок в тамбуре, створка за ним закрывается: каюту вот-вот сменит рубка. */
	bool IsLeaving() const { return bLeaving; }

private:
	UPROPERTY()
	TObjectPtr<UStaticMeshComponent> Leaf;

	UPROPERTY()
	TObjectPtr<USceneComponent> Keypad;

	UPROPERTY()
	TObjectPtr<UTextRenderComponent> Sign;

	// Зеркало (просьба автора 15.11): камера стоит в отражённой точке камеры игрока, смотрит из-за стекла в каюту,
	// пирамида видимости проходит ровно через края стекла — кадр ложится на стекло один в один, а ближняя плоскость
	// совпадает с плоскостью зеркала и отрезает стену за ним. Стекло — плоскость с M_Mirror (кадр как свечение).
	UPROPERTY()
	TObjectPtr<class USceneCaptureComponent2D> MirrorCapture;

	UPROPERTY()
	TObjectPtr<class UTextureRenderTarget2D> MirrorTarget;

	UPROPERTY()
	TObjectPtr<UStaticMeshComponent> MirrorGlass;

	FVector2D MirrorHalf = FVector2D(30.f, 50.f);   // половины ширины и высоты стекла
	void SetupMirror(UStaticMeshComponent* Backing);
	void UpdateMirror();

	FVector LeafClosed = FVector::ZeroVector;
	float LeafOpen = 0.f;
	bool bLeafWanted = false;
	bool bUnlocked = false;
	bool bLeaving = false;
	bool bLeft = false;

	void UpdateSign();
};
