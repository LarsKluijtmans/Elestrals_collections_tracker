import {
  Badge, Box, Button, Chip, Divider, IconButton, Stack, TextField, Tooltip, Typography,
} from "@mui/material";
import { useState } from "react";
import type { SavedView } from "../api/backend";
import {
  activeFilterCount, cycleTristate, humanise, toggleValue,
  MULTI_VALUE, type Filters, type MultiKey,
} from "./filters";

/**
 * The filter rail — story 020.
 *
 * Every control writes through to the URL via `onChange`; nothing is held here. That is the whole
 * design: the URL is the state, so a filtered view is shareable, the back button works, and a
 * reload lands where you were.
 *
 * The vocabulary is passed in rather than hardcoded, because "which rarities exist" is a catalog
 * question and a rail that lists rarities the catalog does not have offers filters that can only
 * ever return nothing.
 */

export type Vocabulary = {
  set_code: string[];
  element: string[];
  rarity: string[];
  condition: string[];
  finish: string[];
  language: string[];
};

const LABELS: Record<MultiKey, string> = {
  set_code: "Set",
  element: "Element",
  rarity: "Rarity",
  condition: "Condition",
  finish: "Finish",
  language: "Language",
};

export function FilterRail({
  filters, vocabulary, total, views, onChange, onClear, onSaveView, onDeleteView, onApplyView,
}: {
  filters: Filters;
  vocabulary: Vocabulary;
  total: number;
  views: SavedView[];
  onChange: (next: Filters) => void;
  onClear: () => void;
  onSaveView: (name: string) => void;
  onDeleteView: (id: string) => void;
  onApplyView: (view: SavedView) => void;
}) {
  const [viewName, setViewName] = useState("");
  const active = activeFilterCount(filters);

  return (
    <Stack component="aside" aria-label="Filters" sx={{ gap: 2, minWidth: 240, maxWidth: 280 }}>
      <Stack direction="row" sx={{ alignItems: "center", justifyContent: "space-between" }}>
        <Badge badgeContent={active} color="primary">
          <Typography sx={{ fontWeight: 600 }}>Filters</Typography>
        </Badge>
        {/* Always visible when anything is active. Story 020: clearing is one action. */}
        {active > 0 ? (
          <Button size="small" onClick={onClear}>
            Clear all
          </Button>
        ) : null}
      </Stack>

      {/* The result count is always on screen, filtered or not — a table that says how many rows
          match is a table you can trust when it shows you fifty. */}
      <Typography aria-live="polite" sx={{ fontSize: 13, color: "text.secondary" }}>
        {total === 1 ? "1 card" : `${total.toLocaleString()} cards`}
        {active > 0 ? " match" : ""}
      </Typography>

      <TextField
        size="small"
        label="Search names"
        value={filters.q ?? ""}
        onChange={(event) => {
          const q = event.target.value;
          const next = { ...filters };
          if (q) next.q = q;
          else delete next.q;
          onChange(next);
        }}
      />

      {MULTI_VALUE.map((key) => {
        const options = vocabulary[key];
        if (!options.length) return null;
        return (
          <Box key={key}>
            <Typography sx={{ fontSize: 12, color: "text.disabled", mb: 0.5 }}>
              {LABELS[key]}
            </Typography>
            <Stack direction="row" sx={{ gap: 0.5, flexWrap: "wrap" }}>
              {options.map((option) => {
                const selected = (filters[key] ?? []).includes(option);
                return (
                  <Chip
                    key={option}
                    size="small"
                    label={humanise(option)}
                    color={selected ? "primary" : "default"}
                    variant={selected ? "filled" : "outlined"}
                    onClick={() => onChange(toggleValue(filters, key, option))}
                    // The pressed state has to be programmatic, not only a colour — colour alone
                    // is not an accessible way to say "this filter is on".
                    aria-pressed={selected}
                  />
                );
              })}
            </Stack>
          </Box>
        );
      })}

      <Box>
        <Typography sx={{ fontSize: 12, color: "text.disabled", mb: 0.5 }}>Flags</Typography>
        <Stack direction="row" sx={{ gap: 0.5, flexWrap: "wrap" }}>
          <TristateChip
            label="Graded"
            value={filters.is_graded}
            onClick={() => onChange(cycleTristate(filters, "is_graded"))}
          />
          <TristateChip
            label="For trade"
            value={filters.is_for_trade}
            onClick={() => onChange(cycleTristate(filters, "is_for_trade"))}
          />
        </Stack>
      </Box>

      <Divider />

      <Box>
        <Typography sx={{ fontSize: 12, color: "text.disabled", mb: 0.5 }}>Saved views</Typography>
        {views.length === 0 ? (
          <Typography sx={{ fontSize: 12, color: "text.disabled" }}>
            Save the filters you keep coming back to.
          </Typography>
        ) : (
          <Stack sx={{ gap: 0.5 }}>
            {views.map((view) => (
              <Stack
                key={view.id}
                direction="row"
                sx={{ alignItems: "center", justifyContent: "space-between" }}
              >
                <Button size="small" sx={{ justifyContent: "flex-start", flex: 1 }}
                        onClick={() => onApplyView(view)}>
                  {view.name}
                </Button>
                <IconButton
                  size="small"
                  aria-label={`Delete view ${view.name}`}
                  onClick={() => onDeleteView(view.id)}
                >
                  ×
                </IconButton>
              </Stack>
            ))}
          </Stack>
        )}

        <Stack direction="row" sx={{ gap: 1, mt: 1 }}>
          <TextField
            size="small"
            placeholder="Name this view"
            value={viewName}
            onChange={(event) => setViewName(event.target.value)}
            slotProps={{ htmlInput: { "aria-label": "Name this view" } }}
          />
          <Tooltip title={active === 0 ? "Set some filters first" : "Save these filters"}>
            <span>
              <Button
                size="small"
                disabled={!viewName.trim() || active === 0}
                onClick={() => {
                  onSaveView(viewName.trim());
                  setViewName("");
                }}
              >
                Save
              </Button>
            </span>
          </Tooltip>
        </Stack>
      </Box>
    </Stack>
  );
}

/**
 * Three states in one control, and the label says which — "Graded", "Graded: yes", "Graded: no".
 *
 * A checkbox cannot express this: unchecked would have to mean both "not filtering" and
 * "ungraded only", and those are different queries.
 */
function TristateChip({
  label, value, onClick,
}: { label: string; value: boolean | undefined; onClick: () => void }) {
  const text = value === undefined ? label : `${label}: ${value ? "yes" : "no"}`;
  return (
    <Chip
      size="small"
      label={text}
      color={value === undefined ? "default" : "primary"}
      variant={value === undefined ? "outlined" : "filled"}
      onClick={onClick}
      aria-pressed={value !== undefined}
    />
  );
}
