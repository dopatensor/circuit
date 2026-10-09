import { type ThemeChoice, setTheme, useTheme } from "../theme";
import { Icon, type IconName } from "./ds";

const OPTIONS: [ThemeChoice, string, IconName][] = [
  ["light", "Light", "sun"],
  ["dark", "Dark", "moon"],
  ["system", "Same as device", "info"],
];

/** Light, dark, or follow the phone's setting (a radio group). */
export function ThemePicker() {
  const theme = useTheme();
  return (
    <fieldset className="flex flex-col gap-3">
      <legend className="mb-3 font-semibold">Appearance</legend>
      <div className="grid grid-cols-3 gap-2">
        {OPTIONS.map(([key, label, icon]) => (
          <label
            key={key}
            className={`flex min-h-11 cursor-pointer items-center justify-center gap-2 rounded-lg px-2 text-center text-sm font-semibold transition-colors ${
              theme === key ? "bg-panel text-fg ring-[1.5px] ring-fg ring-inset" : "bg-raised text-fg2 hover:text-fg"
            }`}
          >
            <input type="radio" name="theme" value={key} checked={theme === key} onChange={() => setTheme(key)} className="sr-only" />
            <Icon name={icon} size={16} className="hidden sm:block" />
            {label}
          </label>
        ))}
      </div>
    </fieldset>
  );
}
