import { Page } from "../components/Shell";
import { Empty, Title } from "../components/ui";

/** Placeholder for tabs whose screens arrive in Phases 9-11. */
export function soon(title: string, sentence: string) {
  return function Soon() {
    return (
      <Page>
        <Title>{title}</Title>
        <Empty>{sentence}</Empty>
      </Page>
    );
  };
}
