import { Box } from "@mui/material";
import { useAddSession } from "../../session/AddSessionContext";

/**
 * The live regions for the whole session.
 *
 * `ux-guide.md` §237 binds it: *"live regions announce optimistic saves and their failures"*, and
 * the add flow is keyboard-only end to end because that is how anyone entering 200 cards will
 * actually use it — which means a sighted-mouse-user assumption in this flow is not a small
 * accessibility gap, it is the whole flow.
 *
 * The announcements are the stage-1 domain events. Keeping them one list rather than two is the
 * cheapest guarantee that a new state transition cannot ship silent: adding a case to the reducer
 * without an announcement is visible in the reducer, not discovered by a screen-reader user.
 *
 * Failures are `assertive` — a collector who does not notice a failed add has a wrong collection
 * and no way to find out. Successes are `polite` so a fast run of adds does not interrupt itself.
 *
 * **Why there are four regions and not two.** A screen reader announces a live region when its
 * *content changes*. Two identical adds in a row produce identical text, so a single region is
 * mutated from "Added Atlas ×1" to "Added Atlas ×1" — no change, no announcement, silence. That is
 * not an edge case: it is a collector emptying a box of duplicates, which is the flow's main use.
 *
 * So each politeness level is double-buffered. Consecutive announcements alternate slots on the
 * parity of `seq`, which means every announcement lands in a region that was empty and empties the
 * region that held the last one. Two changes, one of them empty→text, which is what gets read out.
 * The stage-1 design had a timestamp in the state for this and it did not work — the state object
 * differed, so React re-rendered, but the *text* was identical and the DOM never mutated.
 */
export function LiveAnnouncer() {
  const { announcement } = useAddSession();

  const slot = (announcement?.seq ?? 0) % 2;

  function textFor(assertive: boolean, forSlot: number): string {
    if (!announcement) return "";
    if (announcement.assertive !== assertive) return "";
    return slot === forSlot ? announcement.message : "";
  }

  return (
    <>
      <Box component="output" aria-live="polite" aria-atomic="true" sx={visuallyHidden}>
        {textFor(false, 0)}
      </Box>
      <Box component="output" aria-live="polite" aria-atomic="true" sx={visuallyHidden}>
        {textFor(false, 1)}
      </Box>
      <Box component="output" aria-live="assertive" aria-atomic="true" sx={visuallyHidden}>
        {textFor(true, 0)}
      </Box>
      <Box component="output" aria-live="assertive" aria-atomic="true" sx={visuallyHidden}>
        {textFor(true, 1)}
      </Box>
    </>
  );
}

// Not `display: none` and not `visibility: hidden` — both remove the element from the
// accessibility tree, which would silence the very thing this component exists to say.
const visuallyHidden = {
  position: "absolute",
  width: 1,
  height: 1,
  padding: 0,
  margin: -1,
  overflow: "hidden",
  clip: "rect(0 0 0 0)",
  whiteSpace: "nowrap",
  border: 0,
} as const;
