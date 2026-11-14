// Предмет или записка, лежащие в комнате. Пока серый кубик с подписью.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "RunItem.generated.h"

class UStaticMesh;
class UStaticMeshComponent;
class UTextRenderComponent;

UCLASS()
class MEGAJAM_API ARunItem : public AActor
{
	GENERATED_BODY()

public:
	ARunItem();

	/** id предмета из каталога, −1 — блокнот. Для записки не используется. */
	UPROPERTY(BlueprintReadOnly, Category = "Run")
	int32 ItemId = 0;

	/** Номер записки в комнате, −1 — это предмет. */
	UPROPERTY(BlueprintReadOnly, Category = "Run")
	int32 NoteIndex = -1;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Run")
	TObjectPtr<UStaticMeshComponent> Mesh;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Run")
	TObjectPtr<UTextRenderComponent> Label;

	/** Какая запись комнаты (FRunPlacedItem::Uid) лежит здесь: по ней взятая вещь вычёркивается из комнаты. */
	int32 PlacedUid = 0;

	void Setup(int32 InItemId, int32 InNoteIndex, const FString& Caption);
	/** Поставить ровно так, как стоял меш в комнате (аптечка в аварийной нише). */
	void PlaceAt(const FTransform& Where);

	virtual void Tick(float DeltaSeconds) override;

	bool IsNote() const { return NoteIndex >= 0; }

	/** Модель предмета по имени: меш, как он лежит на полу, на сколько его начало выше поверхности.
	 *  nullptr — модели нет, предмет остаётся кубиком. Нужна и для предмета в руке, и для осмотра. */
	static UStaticMesh* FindModel(const FString& Name, FRotator* OutPose = nullptr, float* OutLift = nullptr);

private:
	UPROPERTY()
	TObjectPtr<UMaterialInterface> ItemMaterial;

	UPROPERTY()
	TObjectPtr<UMaterialInterface> NoteMaterial;
};
