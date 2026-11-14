// Сгенерировано tools/rungen/export_cpp.py из content.py и config.py. Не править руками.

#define RUNGEN_DEFAULT_ITEMS_IN_RUN 16
#define RUNGEN_DEFAULT_HEALTH 4
#define RUNGEN_DEFAULT_P_GUESS 1.0
#define RUNGEN_DEFAULT_FILLER_MIN 3
#define RUNGEN_DEFAULT_FILLER_MAX 4
#define RUNGEN_DEFAULT_EXTRAS 8
#define RUNGEN_DEFAULT_DUMMY_WEIGHT 2
#define RUNGEN_DEFAULT_EXTRA_WEIGHT 5
#define RUNGEN_DEFAULT_P_EXTRA_NOTE 0.5
#define RUNGEN_DEFAULT_P_GUESS_NOTE 0.3

static const FRunItemDef GRunCatalog[] = {
	{ TEXT("Flashlight"), TEXT("the flashlight"), TEXT("tool") },
	{ TEXT("Duct Tape"), TEXT("the duct tape"), TEXT("tool") },
	{ TEXT("Sealant Can"), TEXT("the sealant can"), TEXT("tool") },
	{ TEXT("Pressure Gauge"), TEXT("the pressure gauge"), TEXT("tool") },
	{ TEXT("Fuse"), TEXT("the fuse"), TEXT("part") },
	{ TEXT("Power Cell"), TEXT("the power cell"), TEXT("part") },
	{ TEXT("Circuit Board"), TEXT("the circuit board"), TEXT("part") },
	{ TEXT("Gyroscope"), TEXT("the gyroscope"), TEXT("part") },
	{ TEXT("Coolant Valve"), TEXT("the coolant valve"), TEXT("part") },
	{ TEXT("Data Cartridge"), TEXT("the data cartridge"), TEXT("part") },
	{ TEXT("Voice Recorder"), TEXT("the voice recorder"), TEXT("personal") },
	{ TEXT("Rubber Duck"), TEXT("the rubber duck"), TEXT("personal") },
	{ TEXT("Family Photo"), TEXT("the family photo"), TEXT("personal") },
	{ TEXT("Dog Tag"), TEXT("the dog tag"), TEXT("personal") },
	{ TEXT("Snow Globe"), TEXT("the snow globe"), TEXT("personal") },
	{ TEXT("Ration Tin"), TEXT("the ration tin"), TEXT("personal") },
};

static const TCHAR* const GRunNotebookName = TEXT("Notebook");
static const TCHAR* const GRunWeaponName = TEXT("Pipe Wrench");

static const TCHAR* const GRunTemplates0[] = {
	TEXT("Everything you add, the singularity will erase. Only this remains.\nCarry {item}. It breaks the first loop."),
};
static const TCHAR* const GRunTemplates1[] = {
	TEXT("Same rooms, over and over. {Item} is what breaks this loop."),
	TEXT("I walked these rooms for hours before I got it. Carry {item} and the doors let you go."),
	TEXT("This loop only lets go of those who carry {item}."),
};
static const TCHAR* const GRunTemplates2[] = {
	TEXT("{Item} only shows up for someone carrying {prereq}."),
	TEXT("You won't find {item} unless you carry {prereq}. Don't ask me how I know."),
	TEXT("Looked everywhere for {item}. It was never there until I picked up {prereq}."),
};
static const TCHAR* const GRunTemplates3[] = {
	TEXT("{Item} is junk. The doors don't care about it."),
	TEXT("Carried {item} through a dozen doors. Nothing changed. Drop it."),
	TEXT("Don't waste a slot on {item}."),
};
static const TCHAR* const GRunTemplates4[] = {
	TEXT("I carried {item} and {item2} through a door. The room behind it nearly killed me."),
	TEXT("{Item} with {item2}, and nothing else that matters. That door hurts."),
	TEXT("Tried {item} together with {item2}. Bad room. Don't."),
};
static const TCHAR* const GRunTemplates5[] = {
	TEXT("The engine room answers to three things: {item}, {item2} and {item3}. Keep the notebook. {Leader} has done its job. Let it go."),
	TEXT("Engines. {Item}, {item2}, {item3}. Nothing else but this notebook. Drop {leader} when the time comes."),
};
static const TCHAR* const GRunTemplates6[] = {
	TEXT("Remember how you got to the bridge."),
	TEXT("The engines are humming. Now remember how you got to the bridge."),
	TEXT("It's fixed. Remember how you got to the bridge, and do it once more."),
};

static const FRunTemplateList GRunTemplates[] = {
	{ GRunTemplates0, 1 },
	{ GRunTemplates1, 3 },
	{ GRunTemplates2, 3 },
	{ GRunTemplates3, 3 },
	{ GRunTemplates4, 3 },
	{ GRunTemplates5, 2 },
	{ GRunTemplates6, 3 },
};

static const TCHAR* const GRunNoteKindNames[] = {
	TEXT("notebook_first"),
	TEXT("loop_exit"),
	TEXT("next_key"),
	TEXT("useless"),
	TEXT("danger"),
	TEXT("engine_set"),
	TEXT("finale"),
};
