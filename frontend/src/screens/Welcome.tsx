import { PersonaList } from "../components/PersonaList";
import { Page } from "../components/Shell";
import { Muted, Title } from "../components/ui";

export default function Welcome() {
  return (
    <main className="pt-safe mx-auto w-full max-w-[720px] px-4 md:px-8">
      <Page>
        <div className="flex flex-col gap-2 pt-6">
          <Title>Circuit</Title>
          <p>Find people who need what you offer, and offer what you need.</p>
        </div>
        <div className="flex flex-col gap-3">
          <Muted>Choose a demo person to look around.</Muted>
          <PersonaList />
        </div>
      </Page>
    </main>
  );
}
