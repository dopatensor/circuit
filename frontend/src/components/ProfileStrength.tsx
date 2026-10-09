import type { components } from "../api/schema";
import { useMyProfile } from "../api/hooks";
import { ButtonLink, Card, Checklist, Icon, SkeletonBlock } from "./ds";

type Me = components["schemas"]["MemberMe"];
type Item = { label: string; done: boolean; fix: { to: string; label: string } };

/** What makes a profile strong, by role. Each step says how to do it. */
export function strengthItems(me: Me): Item[] {
  const edit = (label: string) => ({ to: "/me/profile", label });
  const bio = { label: "Write a short bio", done: me.bio.trim().length >= 40, fix: edit("Write your bio") };
  const verified = {
    label: "Verify a work email or link LinkedIn",
    done: me.verification_level >= 2,
    fix: { to: "/me", label: "See how to verify" },
  };
  switch (me.role) {
    case "student":
      return [
        { label: "Add your skills", done: me.skills.length > 0, fix: edit("Add your skills") },
        bio,
        { label: "Add at least three skills", done: me.skills.length >= 3, fix: edit("Add more skills") },
        verified,
      ];
    case "founder":
      return [
        { label: "Say what you need", done: me.needs.length > 0, fix: edit("Add what you need") },
        { label: "Say what you can offer", done: me.offers.length > 0, fix: edit("Add what you offer") },
        bio,
        { label: "Claim your startup's page", done: me.startups.some((s) => s.is_claimer), fix: { to: "/startups", label: "Find your startup" } },
        verified,
      ];
    case "partner_admin":
      return [];
    default: // mentor, investor
      return [
        { label: "Say what you can offer", done: me.offers.length > 0, fix: edit("Add what you offer") },
        bio,
        { label: "Pick traits that describe you", done: me.trait_ids.length > 0, fix: edit("Pick your traits") },
        verified,
      ];
  }
}

/** Profile strength as a checklist, with a button for the next step. */
export function ProfileStrength({ hideWhenDone = false }: { hideWhenDone?: boolean }) {
  const q = useMyProfile();
  if (q.isPending) return <SkeletonBlock className="h-56 w-full rounded-xl" />;
  if (q.isError) return null; // the rest of the page still works; Me shows the error
  const items = strengthItems(q.data);
  if (items.length === 0) return null;
  const next = items.find((i) => !i.done);
  if (!next) {
    if (hideWhenDone) return null;
    return (
      <Card aria-label="Profile strength" className="flex items-center gap-3">
        <Icon name="check" size={18} />
        <p className="text-sm">
          <span className="font-semibold">Profile complete.</span>{" "}
          <span className="text-fg2">It has everything founders look for.</span>
        </p>
      </Card>
    );
  }
  return (
    <Card aria-label="Profile strength">
      <Checklist title="Profile strength" items={items.map((i) => ({ ...i, next: i === next }))} />
      <ButtonLink to={next.fix.to} className="mt-3 w-full">
        {next.fix.label}
      </ButtonLink>
    </Card>
  );
}
