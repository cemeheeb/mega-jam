using UnrealBuildTool;

public class MegaJam : ModuleRules
{
	public MegaJam(ReadOnlyTargetRules Target) : base(Target)
	{
		PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;
		// RenderCore — рендер-таргет зеркала каюты (ARunCabin): без него не линкуется GWhiteTexture
		PublicDependencyModuleNames.AddRange(new string[] { "Core", "CoreUObject", "Engine", "InputCore", "Json", "SlateCore", "RenderCore" });
	}
}
