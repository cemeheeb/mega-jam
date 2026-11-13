// Предмет или записка, лежащие в комнате. Пока серый кубик с подписью.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "RunItem.generated.h"

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

	void Setup(int32 InItemId, int32 InNoteIndex, const FString& Caption);
	virtual void Tick(float DeltaSeconds) override;

	bool IsNote() const { return NoteIndex >= 0; }

private:
	UPROPERTY()
	TObjectPtr<UMaterialInterface> ItemMaterial;

	UPROPERTY()
	TObjectPtr<UMaterialInterface> NoteMaterial;
};
