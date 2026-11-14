export type Mode = "quick" | "team";

export const modeDescription = {
  quick: "One AI router selects the calculator, transcript search, or both. Use it for a focused question.",
  team: "A supervisor agent delegates to financial and management investigators, which can make follow-up tool calls. Use it for questions that need several pieces of evidence.",
};

export function ResearchMode({ name, label, mode, onChange, disabled = false }: {
  name: string;
  label: string;
  mode: Mode;
  onChange: (mode: Mode) => void;
  disabled?: boolean;
}) {
  return <fieldset disabled={disabled} aria-describedby={`${name}-description`}>
    <legend>{label}</legend>
    <div className="segments">
      <label><input type="radio" name={name} checked={mode === "quick"} onChange={() => onChange("quick")} /><span>Quick research</span></label>
      <label><input type="radio" name={name} checked={mode === "team"} onChange={() => onChange("team")} /><span>Research team</span></label>
    </div>
    <p id={`${name}-description`} className="mode-description">{modeDescription[mode]}</p>
  </fieldset>;
}
