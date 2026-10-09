import { useNavigate } from "react-router";
import { BottomSheet, Icon, type IconName } from "./ds";

/** The founder's centre button: what do you want to post? */
export function PostSheet({ open, onClose }: { open: boolean; onClose: () => void }) {
  const navigate = useNavigate();
  const go = (to: string) => {
    onClose();
    navigate(to);
  };
  const options: { to: string; icon: IconName; title: string; text: string }[] = [
    {
      to: "/jobs/new",
      icon: "briefcase",
      title: "Post a job",
      text: "An internship or a full-time role. Students see it on the map and in their matches.",
    },
    {
      to: "/me/profile",
      icon: "hand",
      title: "Update what you need",
      text: "Say what help you're looking for, so we can match you with people who offer it.",
    },
  ];
  return (
    <BottomSheet open={open} onClose={onClose} title="What do you want to post?">
      <ul className="flex flex-col gap-2">
        {options.map((o) => (
          <li key={o.to}>
            <button
              type="button"
              onClick={() => go(o.to)}
              className="flex w-full cursor-pointer items-start gap-3 rounded-xl border border-line p-4 text-left transition-colors hover:border-line2 hover:bg-raised/60"
            >
              <span className="flex size-10 shrink-0 items-center justify-center rounded-lg bg-raised">
                <Icon name={o.icon} />
              </span>
              <span className="flex flex-col">
                <span className="font-semibold">{o.title}</span>
                <span className="text-sm text-fg2">{o.text}</span>
              </span>
            </button>
          </li>
        ))}
      </ul>
    </BottomSheet>
  );
}
