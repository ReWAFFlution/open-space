using Content.Shared.Humanoid;

namespace Content.Shared._Art.TTS;

public sealed class TTSConfig
{
    public const string DefaultVoice = "gman";
    public static readonly Dictionary<Sex, string> DefaultSexVoice = new()
    {
        {Sex.Male, "Eugene"},
        {Sex.Female, "Kseniya"},
        {Sex.Unsexed, "Xenia"}
    };
    public const int VoiceRange = 10; // how far voice goes in world units
    public const int WhisperClearRange = 2; // how far whisper goes while still being understandable, in world units
    public const int WhisperMuffledRange = 5; // how far whisper goes at all, in world units
}
