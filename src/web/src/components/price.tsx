"use client";

import { memo } from "react";

interface PriceProps {
  amount: number;
  className?: string;
  strikethrough?: boolean;
}

export const Price = memo(function Price({
  amount,
  className = "",
  strikethrough = false,
}: PriceProps) {
  const formatted = amount.toLocaleString("ru-RU");
  return (
    <span className={`${className} ${strikethrough ? "line-through" : ""}`}>
      {formatted}&nbsp;<span style={{ fontWeight: 300 }}>{"₽"}</span>
    </span>
  );
});
