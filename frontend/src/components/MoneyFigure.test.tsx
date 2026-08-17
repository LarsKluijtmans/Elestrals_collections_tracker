import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { statusLabel } from "../api/harvest";
import { MoneyFigure } from "./MoneyFigure";

describe("MoneyFigure", () => {
  it("renders an honest empty state rather than a zero", () => {
    // "€0.00" reads as "this card is worthless", which is a different and false claim from
    // "we have not seen one sell". The distinction is invisible to a reader unless we draw it.
    render(
      <MoneyFigure cents={null} currency="EUR" confidence="low" observationCount={0} />,
    );

    expect(screen.getByText("No sales seen")).toBeInTheDocument();
    expect(screen.queryByText(/0\.00/)).not.toBeInTheDocument();
  });

  it("always shows the confidence next to the figure", () => {
    // Standards §8, and the reason `confidence` is a required prop: a figure without one should
    // fail to compile rather than ship and be noticed later, or never.
    render(
      <MoneyFigure cents={1234} currency="EUR" confidence="high" observationCount={6} />,
    );

    expect(screen.getByText("high")).toBeInTheDocument();
  });

  it("formats cents as money without floating point", () => {
    render(
      <MoneyFigure cents={1999} currency="EUR" confidence="medium" observationCount={2} />,
    );

    expect(screen.getByText(/19[.,]99/)).toBeInTheDocument();
  });
});

describe("statusLabel", () => {
  it("never describes an unexplained ending as a sale", () => {
    // The whole invariant chain — connector, runner, fact table — can be undone here by one
    // loose label. A listing that vanished may have sold, expired, been cancelled or been
    // relisted, and only one of those is a sale.
    const label = statusLabel("ended_unknown");

    expect(label).toBe("Ended, reason unknown");
    expect(label.toLowerCase()).not.toContain("sold");
  });

  it("says sold only when the source actually reported a sale", () => {
    expect(statusLabel("ended_sold")).toBe("Sold");
    expect(statusLabel("ended_unsold")).toBe("Ended, unsold");
    expect(statusLabel("active")).toBe("Live");
  });
});
