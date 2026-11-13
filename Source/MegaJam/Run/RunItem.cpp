#include "RunItem.h"

#include "Components/StaticMeshComponent.h"
#include "Components/TextRenderComponent.h"
#include "Kismet/GameplayStatics.h"
#include "Materials/MaterialInterface.h"
#include "UObject/ConstructorHelpers.h"

ARunItem::ARunItem()
{
	PrimaryActorTick.bCanEverTick = true;
	Mesh = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("Mesh"));
	SetRootComponent(Mesh);
	static ConstructorHelpers::FObjectFinder<UStaticMesh> Cube(TEXT("/Engine/BasicShapes/Cube.Cube"));
	if (Cube.Succeeded())
	{
		Mesh->SetStaticMesh(Cube.Object);
	}
	// предметы оранжевые, записки светлые: серые кубики на серых столах не видно
	static ConstructorHelpers::FObjectFinder<UMaterialInterface> ItemMat(TEXT("/Game/Game/Materials/MI_Gray_Door.MI_Gray_Door"));
	static ConstructorHelpers::FObjectFinder<UMaterialInterface> NoteMat(TEXT("/Game/Game/Materials/MI_Gray_Linen.MI_Gray_Linen"));
	ItemMaterial = ItemMat.Succeeded() ? ItemMat.Object : nullptr;
	NoteMaterial = NoteMat.Succeeded() ? NoteMat.Object : nullptr;
	Mesh->SetCollisionProfileName(TEXT("NoCollision"));
	Mesh->SetMobility(EComponentMobility::Movable);

	Label = CreateDefaultSubobject<UTextRenderComponent>(TEXT("Label"));
	Label->SetupAttachment(Mesh);
	Label->SetHorizontalAlignment(EHTA_Center);
	Label->SetWorldSize(14.f);
	Label->SetTextRenderColor(FColor(255, 120, 0));
	Label->SetAbsolute(false, true, true);
}

void ARunItem::Setup(int32 InItemId, int32 InNoteIndex, const FString& Caption)
{
	ItemId = InItemId;
	NoteIndex = InNoteIndex;
	// записка — плоский листок, предмет — кубик
	Mesh->SetWorldScale3D(IsNote() ? FVector(0.22f, 0.16f, 0.01f) : FVector(0.22f, 0.22f, 0.22f));
	if (UMaterialInterface* Mat = IsNote() ? NoteMaterial : ItemMaterial)
	{
		Mesh->SetMaterial(0, Mat);
	}
	Label->SetText(FText::FromString(Caption));
	Label->SetRelativeLocation(FVector(0, 0, IsNote() ? 2600.f : 130.f));
	Label->SetWorldScale3D(FVector(1.f));
}

void ARunItem::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);
	// подпись всегда смотрит на камеру
	if (const APlayerCameraManager* Cam = UGameplayStatics::GetPlayerCameraManager(this, 0))
	{
		const FVector ToCam = Cam->GetCameraLocation() - Label->GetComponentLocation();
		Label->SetWorldRotation(FRotator(0.f, ToCam.Rotation().Yaw, 0.f));
	}
}
