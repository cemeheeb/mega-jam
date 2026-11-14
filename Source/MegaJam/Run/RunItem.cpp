#include "RunItem.h"

#include "Components/StaticMeshComponent.h"
#include "Components/TextRenderComponent.h"
#include "Engine/StaticMesh.h"
#include "Kismet/GameplayStatics.h"
#include "Materials/MaterialInterface.h"
#include "UObject/ConstructorHelpers.h"

namespace
{
	// Модели предметов из наборов Singula (tools/blender/export_singula.py): имя предмета -> меш, как он лежит
	// и на сколько его начало выше поверхности. У остальных предметов моделей пока нет — оранжевые кубики.
	// Папка /Game/Environment упаковывается целиком (Config/DefaultGame.ini): меши грузятся по пути.
	struct FItemModel
	{
		const TCHAR* Name;
		const TCHAR* Mesh;
		FRotator Pose;
		float Lift;
	};
	const FItemModel GItemModels[] = {
		// фонарь лежит на боку вдоль X: меш стоит на торце, радиус 2,5 см
		{ TEXT("Flashlight"), TEXT("/Game/Environment/Common/SafetyEquipment/SM_Flashlight.SM_Flashlight"), FRotator(-90.f, 0.f, 0.f), 2.5f },
		// блокнот — книга-чеклист плашмя, обложкой (+Y меша) вверх; толщина 5,4 см
		{ TEXT("Notebook"), TEXT("/Game/Environment/Bridge/CrewItems/SM_ChecklistBook.SM_ChecklistBook"), FRotator(0.f, 0.f, -90.f), 2.7f },
		// аптечка — кейс первой помощи из аварийной ниши; стоит на дне, ручкой вверх
		{ TEXT("Medkit"), TEXT("/Game/Environment/Common/SafetyEquipment/SM_FirstAidCase.SM_FirstAidCase"), FRotator::ZeroRotator, 0.f },
	};
	// предмет ставится на 11 см выше поверхности — под кубик 22 см (ARunDirector::SpawnRoomContents)
	constexpr float CubeLift = 11.f;
}

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

UStaticMesh* ARunItem::FindModel(const FString& Name, FRotator* OutPose, float* OutLift)
{
	for (const FItemModel& M : GItemModels)
	{
		if (Name == M.Name)
		{
			if (OutPose)
			{
				*OutPose = M.Pose;
			}
			if (OutLift)
			{
				*OutLift = M.Lift;
			}
			return LoadObject<UStaticMesh>(nullptr, M.Mesh);
		}
	}
	return nullptr;
}

void ARunItem::PlaceAt(const FTransform& Where)
{
	SetActorLocationAndRotation(Where.GetLocation(), Where.GetRotation());
	Label->SetWorldLocation(GetActorLocation() + FVector(0, 0, 34.f));
}

void ARunItem::Setup(int32 InItemId, int32 InNoteIndex, const FString& Caption)
{
	ItemId = InItemId;
	NoteIndex = InNoteIndex;
	FRotator Pose;
	float Lift = 0.f;
	if (UStaticMesh* ModelMesh = IsNote() ? nullptr : FindModel(Caption, &Pose, &Lift))
	{
		// модель со своим материалом: опустить на её опору и уложить; подпись — над ней
		Mesh->SetStaticMesh(ModelMesh);
		Mesh->SetWorldScale3D(FVector(1.f));
		SetActorLocationAndRotation(GetActorLocation() - FVector(0, 0, CubeLift - Lift), Pose);
		Label->SetText(FText::FromString(Caption));
		Label->SetWorldLocation(GetActorLocation() + FVector(0, 0, 28.f));
		Label->SetWorldScale3D(FVector(1.f));
		return;
	}
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
