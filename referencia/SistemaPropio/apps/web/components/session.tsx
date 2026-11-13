"use client";

import { createContext, useContext } from "react";
import type { Me } from "@/lib/api";

export const SessionContext = createContext<Me | null>(null);

export function useMe(): Me {
  const me = useContext(SessionContext);
  if (!me) throw new Error("useMe fuera de una sesión");
  return me;
}
