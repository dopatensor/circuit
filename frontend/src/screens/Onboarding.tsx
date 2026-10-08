import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useNavigate } from "react-router";
import { api, type Schemas, unwrap } from "../api/client";
import { useCapabilities, useMyProfile, useTraits } from "../api/hooks";
import { useAuth } from "../auth";
import { ChipPicker } from "../components/Chips";
import { Page } from "../components/Shell";
import {
  Card,
  ErrorState,
  Muted,
  PrimaryButton,
  SecondaryButton,
  Skeleton,
  Title,
} from "../components/ui";

type Profile = Schemas["MemberMe"];
type Suggest = Schemas["OnboardingSuggestOut"];

// The most of each the API accepts (OnboardingConfirmIn).
const MAX = { needs: 10, offers: 10, skills: 15, traits: 10 };

/** What you picked: capability or trait ids, plus the text that goes with a need or
 *  offer (kept from your profile or from the suggestion). */
type Picks = {
  needs: string[];
  offers: string[];
  skills: string[];
  traits: string[];
  texts: Record<string, string>; // "need:<id>" / "offer:<id>" -> text
};

function picksFrom(p: Profile): Picks {
  const texts: Record<string, string> = {};
  for (const n of p.needs) if (n.active) texts[`need:${n.capability_id}`] = n.text;
  for (const o of p.offers) if (o.active) texts[`offer:${o.capability_id}`] = o.text;
  return {
    needs: p.needs.filter((n) => n.active).map((n) => n.capability_id),
    offers: p.offers.filter((o) => o.active).map((o) => o.capability_id),
    skills: p.skills.map((s) => s.capability_id),
    traits: p.trait_ids,
    texts,
  };
}

function picksFromSuggestion(suggestions: Suggest["suggestions"]): Picks {
  const s = { needs: [], offers: [], skills: [], traits: [], ...suggestions };
  const texts: Record<string, string> = {};
  for (const n of s.needs) texts[`need:${n.capability_id}`] = n.text;
  for (const o of s.offers) texts[`offer:${o.capability_id}`] = o.text;
  return {
    needs: s.needs.map((n) => n.capability_id).slice(0, MAX.needs),
    offers: s.offers.map((o) => o.capability_id).slice(0, MAX.offers),
    skills: s.skills.slice(0, MAX.skills),
    traits: s.traits.slice(0, MAX.traits),
    texts,
  };
}

const toggle = (list: string[], id: string) =>
  list.includes(id) ? list.filter((x) => x !== id) : [...list, id];

/** Smart onboarding (F1): describe yourself in your own words, get chips suggested
 *  from our fixed lists, then tap to confirm or change them. Without an AI key the
 *  same chips are picked by hand. */
export default function Onboarding() {
  const profile = useMyProfile();
  return (
    <Page>
      <div className="flex flex-col gap-1">
        <Link to="/me" className="text-sm text-blue hover:underline">
          Me
        </Link>
        <Title>What you need and offer</Title>
        <Muted>We match you on this, not on job titles or college names.</Muted>
      </div>
      {profile.isPending ? (
        <Skeleton lines={3} className="h-40" />
      ) : profile.isError ? (
        <ErrorState error={profile.error} retry={profile.refetch} />
      ) : (
        <Editor profile={profile.data} />
      )}
    </Page>
  );
}

function Editor({ profile }: { profile: Profile }) {
  const { member } = useAuth();
  const caps = useCapabilities();
  const traits = useTraits();
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const student = profile.role === "student";
  const [about, setAbout] = useState(profile.bio);
  const [picks, setPicks] = useState<Picks>(() => picksFrom(profile));
  const [suggested, setSuggested] = useState<Picks | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const suggest = useMutation({
    mutationFn: () =>
      unwrap(
        api.POST("/api/onboarding/suggest", {
          body: { text: about, role: profile.role === "partner_admin" ? null : profile.role },
        }),
      ),
    onSuccess: (out) => {
      if (out.source === "llm") {
        const next = picksFromSuggestion(out.suggestions);
        // Students are matched on skills; everyone else on needs and offers.
        const count = (student ? next.skills.length : next.needs.length + next.offers.length) +
          next.traits.length;
        setPicks({ ...next, ...(student ? { needs: picks.needs, offers: picks.offers } : {}) });
        setSuggested(next);
        setNotice(`We picked ${count} from what you wrote. Tap any chip to change it.`);
      } else {
        setNotice("Automatic suggestions are off right now, so pick from the lists below.");
      }
    },
  });

  const save = useMutation({
    mutationFn: async () => {
      const text = (kind: "need" | "offer", id: string) => picks.texts[`${kind}:${id}`] ?? "";
      const level = new Map(profile.skills.map((s) => [s.capability_id, s.level]));
      await unwrap(
        api.POST("/api/onboarding/confirm", {
          body: {
            bio: about.trim() || null,
            needs: picks.needs.map((id) => ({ capability_id: id, text: text("need", id) })),
            offers: picks.offers.map((id) => ({ capability_id: id, text: text("offer", id) })),
            skills: picks.skills.map((id) => ({ capability_id: id, level: level.get(id) ?? 2 })),
            trait_ids: picks.traits,
          },
        }),
      );
      // Matches use what you just saved straight away (if you can see matches yet).
      if ((member?.verification_level ?? 0) >= 2) await unwrap(api.POST("/api/matches/refresh"));
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["members", "me"] });
      await queryClient.invalidateQueries({ queryKey: ["matches"] });
      await queryClient.invalidateQueries({ queryKey: ["me-stat"] });
      navigate("/matches", { state: { saved: true } });
    },
  });

  if (caps.isPending || traits.isPending) return <Skeleton lines={3} className="h-40" />;
  if (caps.isError) return <ErrorState error={caps.error} retry={caps.refetch} />;
  if (traits.isError) return <ErrorState error={traits.error} retry={traits.refetch} />;

  const capOptions = caps.data.map((c) => ({ id: c.id, name: c.name, group: c.category }));
  const traitOptions = traits.data.map((t) => ({ id: t.id, name: t.name }));
  const nothingYet = !student
    ? picks.needs.length + picks.offers.length === 0
    : picks.skills.length === 0;
  const set = (key: keyof Omit<Picks, "texts">) => (id: string) =>
    setPicks((p) => ({ ...p, [key]: toggle(p[key], id) }));

  return (
    <>
      <Card className="flex flex-col gap-4">
        <label className="flex flex-col gap-2">
          <span className="font-semibold">
            {student ? "Tell us what you can do" : "Describe yourself or your startup"}
          </span>
          <span className="text-sm text-muted">
            {student
              ? "Projects, languages, tools. We'll suggest skills from our list."
              : "Paste a bio or a few lines. We'll suggest what you need and offer."}
          </span>
          <textarea
            value={about}
            onChange={(e) => setAbout(e.target.value)}
            maxLength={2000}
            rows={5}
            className="rounded-xl border border-line bg-raised p-3 placeholder:text-muted"
            placeholder={
              student
                ? "I build Python APIs and have shipped a React app for my college fest."
                : "We make lab-grown leather for fashion brands and need help with marketing."
            }
          />
        </label>
        <SecondaryButton
          className="self-start"
          disabled={about.trim().length < 10 || suggest.isPending}
          onClick={() => suggest.mutate()}
        >
          {suggest.isPending ? "Reading…" : "Suggest chips"}
        </SecondaryButton>
        {suggest.isError && <ErrorState error={suggest.error} />}
        {notice && (
          <p role="status" className="text-sm text-green">
            {notice}
          </p>
        )}
      </Card>

      {student ? (
        <Card>
          <ChipPicker
            label="Your skills"
            hint="Jobs are matched to these."
            options={capOptions}
            selected={picks.skills}
            suggested={suggested?.skills}
            max={MAX.skills}
            onToggle={set("skills")}
            startOpen={nothingYet}
          />
        </Card>
      ) : (
        <>
          <Card>
            <ChipPicker
              label="What you need"
              hint="Help you're looking for right now."
              options={capOptions}
              selected={picks.needs}
              suggested={suggested?.needs}
              max={MAX.needs}
              onToggle={set("needs")}
              startOpen={nothingYet}
            />
          </Card>
          <Card>
            <ChipPicker
              label="What you offer"
              hint="Help you can give others."
              options={capOptions}
              selected={picks.offers}
              suggested={suggested?.offers}
              max={MAX.offers}
              onToggle={set("offers")}
              startOpen={nothingYet}
            />
          </Card>
        </>
      )}
      <Card>
        <ChipPicker
          label="How you work"
          hint="Shared traits make a match stronger, even across sectors."
          options={traitOptions}
          selected={picks.traits}
          suggested={suggested?.traits}
          max={MAX.traits}
          onToggle={set("traits")}
          startOpen={picks.traits.length === 0}
        />
      </Card>

      {save.isError && <ErrorState error={save.error} />}
      <div className="sticky bottom-[calc(4.5rem+env(safe-area-inset-bottom))] z-10 md:bottom-6">
        <PrimaryButton
          className="min-h-14 w-full"
          disabled={save.isPending}
          onClick={() => save.mutate()}
        >
          {save.isPending ? "Saving…" : "Save and see matches"}
        </PrimaryButton>
      </div>
    </>
  );
}
