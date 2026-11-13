// Выгрузка раскладок забега в JSON в том же виде, что tools/rungen/dump.py.
// Нужна только для проверки переноса: tools/ue/check_port.py.

#pragma once

#include "Commandlets/Commandlet.h"
#include "RunGenDumpCommandlet.generated.h"

UCLASS()
class URunGenDumpCommandlet : public UCommandlet
{
	GENERATED_BODY()

public:
	virtual int32 Main(const FString& Params) override;
};
