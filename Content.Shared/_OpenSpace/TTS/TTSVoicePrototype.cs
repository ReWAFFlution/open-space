
using System.ComponentModel;
using Content.Shared.Humanoid;
using Robust.Shared.Prototypes;

namespace Content.Shared._OpenSpace.TTS;

/// <summary>
/// Prototype represent available TTS voices
/// </summary>
[Prototype("voice")]
// ReSharper disable once InconsistentNaming
public sealed partial class TTSVoicePrototype : IPrototype
{
    [IdDataField]
    public string ID { get; private set; } = default!;

    [DataField("name")]
    public string Name { get; private set; } = string.Empty;

    [DataField("sex", required: true)]
    public Sex Sex { get; private set; } = default!;

    /// <summary>
    /// Whether the species is available "at round start" (In the character editor)
    /// </summary>
    [DataField("roundStart")]
    public bool RoundStart { get; private set; } = true;
}
