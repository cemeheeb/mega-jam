using UnrealBuildTool;

public class MegaJamTarget : TargetRules
{
	public MegaJamTarget(TargetInfo Target) : base(Target)
	{
		Type = TargetType.Game;
		DefaultBuildSettings = BuildSettingsVersion.Latest;
		IncludeOrderVersion = EngineIncludeOrderVersion.Latest;
		ExtraModuleNames.Add("MegaJam");
	}
}
