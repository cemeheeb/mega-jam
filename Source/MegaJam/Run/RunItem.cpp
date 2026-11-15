#include "RunItem.h"

#include "Components/StaticMeshComponent.h"
#include "Components/TextRenderComponent.h"
#include "Engine/StaticMesh.h"
#include "Kismet/GameplayStatics.h"
#include "Materials/MaterialInterface.h"
#include "RunGen.h"
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
		// скафандр на стойке (модель автора из Tripo, 15.11): стоит на полу, привязка — центр дна
		{ TEXT("Space Suit"), TEXT("/Game/Environment/Common/SpaceSuit/SM_SpaceSuit.SM_SpaceSuit"), FRotator::ZeroRotator, 0.f },
		// разводной ключ: меш стоит рукоятью вверх (так он висит в руке за её конец), на полу лежит плашмя;
		// толщина 4,9 см
		{ TEXT("Pipe Wrench"), TEXT("/Game/Items/PipeWrench/SM_PipeWrench.SM_PipeWrench"), FRotator(0.f, 0.f, 90.f), 2.45f },
	};
	// предмет ставится на 11 см выше поверхности — под кубик 22 см (ARunDirector::SpawnRoomContents)
	constexpr float CubeLift = 11.f;
}

ARunItem::ARunItem()
{
	PrimaryActorTick.bCanEverTick = true;
	Mesh = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("Mesh"));
	SetRootComponent(Mesh);
	Mesh->SetReceivesDecals(false);   // вещь на столе выгоревшей комнаты не покрывается копотью стола
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
			return LoadObject<UStaticMesh>(nullptr, M.Mesh, nullptr, LOAD_NoWarn | LOAD_Quiet);
		}
	}
	// Остальные предметы — по правилу имён (tools/ue/import_props.py): «Coolant Valve» ->
	// /Game/Items/CoolantValve/SM_CoolantValve. Привязка — центр дна, лежит как смоделирован. Нет модели — кубик.
	const FString Id = Name.Replace(TEXT(" "), TEXT("")).Replace(TEXT("'"), TEXT(""));   // «Captain's Card» -> CaptainsCard
	if (OutPose)
	{
		*OutPose = FRotator::ZeroRotator;
	}
	if (OutLift)
	{
		*OutLift = 0.f;
	}
	return LoadObject<UStaticMesh>(nullptr, *FString::Printf(TEXT("/Game/Items/%s/SM_%s.SM_%s"), *Id, *Id, *Id), nullptr, LOAD_NoWarn | LOAD_Quiet);
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
	// записка — листок из блокнота (модель «Paper Note»), вещь — модель по своему имени
	if (UStaticMesh* ModelMesh = FindModel(IsNote() ? FString(TEXT("Paper Note")) : Caption, &Pose, &Lift))
	{
		// модель со своим материалом: опустить на её опору и уложить; подпись — над ней
		Mesh->SetStaticMesh(ModelMesh);
		Mesh->SetWorldScale3D(FVector(1.f));
		// вещь ставят на 11 см выше опоры (под кубик), записку — на 1 см
		SetActorLocationAndRotation(GetActorLocation() - FVector(0, 0, IsNote() ? 1.f : CubeLift - Lift), Pose);
		Mesh->EmptyOverrideMaterials();
		Mesh->SetCollisionProfileName(TEXT("NoCollision"));
		Label->SetText(FText::FromString(Caption));
		// подпись — над верхом модели: у скафандра это почти два метра
		const float Top = ModelMesh->GetBoundingBox().TransformBy(FTransform(Pose)).Max.Z;   // с учётом позы: ключ лежит плашмя
		Label->SetWorldLocation(GetActorLocation() + FVector(0, 0, FMath::Max(28.f, Top + 14.f)));
		Label->SetWorldScale3D(FVector(1.f));
		return;
	}
	if (ItemId == RunGen::Suit)
	{
		SetupSuitPlaceholder(Caption);
		return;
	}
	if (ItemId == RunGen::Card)
	{
		// карточка капитана (лор 15.11): модели пока нет — оранжевая пластина 11 × 7 см плашмя на опоре
		Mesh->SetWorldScale3D(FVector(0.11f, 0.07f, 0.006f));
		SetActorLocation(GetActorLocation() - FVector(0, 0, CubeLift - 0.3f));
		if (ItemMaterial)
		{
			Mesh->SetMaterial(0, ItemMaterial);
		}
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

void ARunItem::SetupSuitPlaceholder(const FString& Caption)
{
	// скафандр стоит в рост на полу (DESIGN 5.9): корпус, ноги, шлем с тёмным стеклом. Модели пока нет — базовые фигуры
	UStaticMesh* Cyl = LoadObject<UStaticMesh>(nullptr, TEXT("/Engine/BasicShapes/Cylinder.Cylinder"));
	UStaticMesh* Ball = LoadObject<UStaticMesh>(nullptr, TEXT("/Engine/BasicShapes/Sphere.Sphere"));
	UMaterialInterface* White = NoteMaterial;
	UMaterialInterface* Dark = LoadObject<UMaterialInterface>(nullptr, TEXT("/Game/Game/Materials/MI_Gray_Dark.MI_Gray_Dark"));
	const FVector Floor = GetActorLocation() - FVector(0, 0, CubeLift);
	SetActorLocationAndRotation(Floor, FRotator::ZeroRotator);
	Mesh->SetStaticMesh(nullptr);
	auto Part = [&](UStaticMesh* Shape, UMaterialInterface* Mat, const FVector& SizeCm, const FVector& Local)
	{
		UStaticMeshComponent* C = NewObject<UStaticMeshComponent>(this);
		C->SetStaticMesh(Shape);
		C->SetMaterial(0, Mat);
		C->SetCollisionProfileName(TEXT("NoCollision"));
		C->SetReceivesDecals(false);
		C->SetupAttachment(Mesh);
		C->RegisterComponent();
		C->SetRelativeLocation(Local);
		C->SetWorldScale3D(SizeCm / 100.f);
	};
	Part(Cyl, White, FVector(50.f, 36.f, 70.f), FVector(0, 0, 112.f));       // корпус
	Part(Cyl, ItemMaterial, FVector(40.f, 20.f, 50.f), FVector(-22.f, 0, 115.f));   // ранец, оранжевый
	Part(Cyl, White, FVector(17.f, 17.f, 78.f), FVector(0, -11.f, 39.f));    // ноги
	Part(Cyl, White, FVector(17.f, 17.f, 78.f), FVector(0, 11.f, 39.f));
	Part(Cyl, White, FVector(14.f, 14.f, 60.f), FVector(0, -32.f, 115.f));   // руки
	Part(Cyl, White, FVector(14.f, 14.f, 60.f), FVector(0, 32.f, 115.f));
	Part(Ball, White, FVector(36.f), FVector(0, 0, 165.f));                   // шлем
	Part(Ball, Dark, FVector(30.f, 30.f, 22.f), FVector(8.f, 0, 166.f));      // стекло
	Label->SetText(FText::FromString(Caption));
	Label->SetWorldLocation(Floor + FVector(0, 0, 200.f));
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
