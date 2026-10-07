import { PersonaList } from "../components/PersonaList";
import { Page } from "../components/Shell";
import { Muted, SecondaryButton, Title, VerificationBadge } from "../components/ui";
import { useAuth } from "../auth";
import { ROLE_LABEL } from "../nav";

export default function Me() {
  const { member, isDemo, logout } = useAuth();
  if (!member) return null;
  return (
    <Page>
      <div className="flex flex-col gap-2">
        <Title>{member.display_name}</Title>
        <Muted>{[ROLE_LABEL[member.role], member.sector, member.city].filter(Boolean).join(" · ")}</Muted>
        <div>
          <VerificationBadge level={member.verification_level} />
        </div>
      </div>
      {isDemo && (
        <div className="flex flex-col gap-3">
          <h2 className="text-base font-semibold">Switch demo person</h2>
          <PersonaList />
        </div>
      )}
      <div>
        <SecondaryButton onClick={() => void logout()}>Sign out</SecondaryButton>
      </div>
    </Page>
  );
}
