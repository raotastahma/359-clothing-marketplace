"use client";

import { createContext, useContext, useMemo, useState } from "react";

interface ContactContextValue {
  isContactOpen: boolean;
  setContactOpen: (open: boolean) => void;
}

const ContactContext = createContext<ContactContextValue | null>(null);

interface ContactProviderProps {
  children: React.ReactNode;
}

export function ContactProvider({ children }: ContactProviderProps) {
  const [isContactOpen, setContactOpen] = useState<boolean>(false);

  const value = useMemo<ContactContextValue>(
    () => ({
      isContactOpen,
      setContactOpen,
    }),
    [isContactOpen],
  );

  return <ContactContext.Provider value={value}>{children}</ContactContext.Provider>;
}

export function useContact(): ContactContextValue {
  const context = useContext(ContactContext);
  if (!context) throw new Error("useContact must be used inside ContactProvider");
  return context;
}
