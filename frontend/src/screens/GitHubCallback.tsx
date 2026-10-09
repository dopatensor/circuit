import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef } from "react";
import { useNavigate, useSearchParams } from "react-router";
import { api, unwrap } from "../api/client";
import { ButtonLink, ErrorBlock, SkeletonBlock, useToast } from "../components/ds";
import { Page, PageHeader } from "../components/Shell";

/** GitHub sends the student back here with a one-time code. We hand it to our API,
 *  which asks GitHub whose account it is (the ownership check) and starts the import. */
export default function GitHubCallback() {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const toast = useToast();
  const code = params.get("code");
  const state = params.get("state");
  const denied = params.get("error") === "access_denied";
  const finish = useMutation({
    mutationFn: () => unwrap(api.POST("/api/proof/github/finish", { body: { code: code ?? "", state: state ?? "" } })),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["proof", "me"] });
      void queryClient.invalidateQueries({ queryKey: ["members", "me"] });
      toast({ message: "GitHub connected. Importing your public repos." });
      navigate("/me/proof", { replace: true });
    },
  });
  const sent = useRef(false); // the code works once; never send it twice
  useEffect(() => {
    if (sent.current || !code || !state) return;
    sent.current = true;
    finish.mutate();
  }, [code, state, finish]);

  const back = (
    <ButtonLink to="/me/proof" className="self-start">
      Back to proof of work
    </ButtonLink>
  );
  return (
    <Page>
      <PageHeader title="Connecting GitHub" intro="Checking with GitHub which account you signed in with." />
      {denied ? (
        <>
          <p>You didn't give access on GitHub, so nothing was connected.</p>
          {back}
        </>
      ) : !code || !state ? (
        <>
          <p>This link is missing GitHub's answer. Start again from your proof of work.</p>
          {back}
        </>
      ) : finish.isError ? (
        <>
          <ErrorBlock error={finish.error} />
          {back}
        </>
      ) : (
        <SkeletonBlock className="h-24 w-full rounded-xl" />
      )}
    </Page>
  );
}
