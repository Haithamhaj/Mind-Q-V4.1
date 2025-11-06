"use client";

import React from "react";

import {
  KpiCard as BaseKpiCard,
} from "../../components/KpiCard";

export type Layer1KpiCardProps = React.ComponentProps<typeof BaseKpiCard>;

export const Layer1KpiCard: React.FC<Layer1KpiCardProps> = (props) => {
  return <BaseKpiCard {...props} />;
};

export default Layer1KpiCard;
