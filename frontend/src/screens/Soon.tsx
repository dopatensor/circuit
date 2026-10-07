import { Page } from "../components/Shell";
import { Empty, Title } from "../components/ui";

// The tab is there so the navigation is real; its screen arrives in a later build.

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
