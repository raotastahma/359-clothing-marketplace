"use client";

import { FileText, HelpCircle, LogOut, User } from "lucide-react";
import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";

import { Button } from "@/src/components/ui/button";
import { useCart } from "@/src/components/providers/cart-context";
import { useContact } from "@/src/components/providers/contact-context";
import { useUser } from "@/src/components/providers/user-context";

function getInitials(name: string): string {
  return name
    .split(" ")
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0])
    .join("")
    .toUpperCase();
}

export default function ProfilePage() {
  const { cartCount, setCartOpen } = useCart();
  const { setContactOpen } = useContact();
  const {
    accountError,
    favorites,
    isAccountLoading,
    logout,
    orders,
    updateProfile,
    user,
  } = useUser();
  const [name, setName] = useState("");
  const [profileError, setProfileError] = useState<string | null>(null);
  const [profileMessage, setProfileMessage] = useState<string | null>(null);
  const [isSavingProfile, setSavingProfile] = useState(false);

  useEffect(() => {
    setName(user?.name ?? "");
  }, [user?.name]);

  async function onProfileSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const nextName = name.trim();
    if (!nextName || nextName === user?.name) return;

    setSavingProfile(true);
    setProfileError(null);
    setProfileMessage(null);

    try {
      await updateProfile(nextName);
      setProfileMessage("Профиль обновлен");
    } catch (nextError) {
      setProfileError(
        nextError instanceof Error ? nextError.message : "Не удалось обновить профиль.",
      );
    } finally {
      setSavingProfile(false);
    }
  }

  if (isAccountLoading && !user) {
    return (
      <section className="mx-auto flex min-h-[60vh] max-w-md flex-col items-center justify-center px-6 py-20 text-center">
        <h1 className="mb-10 self-start text-3xl tracking-tight">Профиль</h1>
        <p className="text-sm text-black/50">Загружаем профиль...</p>
      </section>
    );
  }

  if (!user) {
    return (
      <section className="mx-auto flex min-h-[60vh] max-w-md flex-col items-center justify-center px-6 py-20 text-center">
        <h1 className="mb-10 self-start text-3xl tracking-tight">Профиль</h1>
        <div className="flex h-20 w-20 items-center justify-center border border-black/15">
          <User size={34} strokeWidth={1.2} className="text-black/45" />
        </div>
        <h2 className="mt-6 text-xl">Войдите в аккаунт</h2>
        <p className="mt-3 text-sm leading-relaxed text-black/55">
          Сохраняйте избранное, отслеживайте заказы и быстрее оформляйте покупки.
        </p>
        <Button asChild className="mt-7 h-12 w-full bg-black text-white">
          <Link href="/login">Войти / Зарегистрироваться</Link>
        </Button>
        {accountError ? <p className="mt-4 text-sm text-destructive">{accountError}</p> : null}
      </section>
    );
  }

  return (
    <section className="mx-auto max-w-3xl px-4 py-10 sm:px-6 lg:py-14">
      <h1 className="text-3xl tracking-tight">Профиль</h1>

      <div className="mt-8 border border-black/10 p-5 sm:p-6">
        <div className="flex items-center gap-4">
          <div className="flex h-16 w-16 shrink-0 items-center justify-center bg-black text-lg text-white">
            {getInitials(user.name)}
          </div>
          <div className="min-w-0">
            <p className="truncate text-lg">{user.name}</p>
            <p className="mt-1 text-sm text-black/50">{user.phone}</p>
          </div>
        </div>
        <form onSubmit={onProfileSubmit} className="mt-5 grid gap-3 sm:grid-cols-[1fr_auto]">
          <input
            value={name}
            onChange={(event) => {
              setName(event.target.value);
              setProfileError(null);
              setProfileMessage(null);
            }}
            className="h-11 w-full border border-black/15 bg-white px-3 text-sm outline-none focus:border-black"
            aria-label="Имя"
          />
          <Button
            type="submit"
            disabled={isSavingProfile || !name.trim() || name.trim() === user.name}
            className="h-11 bg-black px-5 text-white disabled:bg-black/20 disabled:text-black/40"
          >
            {isSavingProfile ? "Сохраняем" : "Сохранить"}
          </Button>
        </form>
        {profileError ? <p className="mt-3 text-sm text-destructive">{profileError}</p> : null}
        {profileMessage ? <p className="mt-3 text-sm text-black/50">{profileMessage}</p> : null}
        {accountError ? <p className="mt-3 text-sm text-destructive">{accountError}</p> : null}
      </div>

      <div className="mt-5 grid grid-cols-3 border border-black/10">
        <Link
          href="/profile/orders"
          className="border-r border-black/10 p-4 text-left transition-colors hover:bg-black hover:text-white"
        >
          <span className="block text-2xl">{orders.length}</span>
          <span className="mt-1 block text-xs tracking-[1.5px] uppercase">Заказы</span>
        </Link>
        <Link
          href="/favorites"
          className="border-r border-black/10 p-4 text-left transition-colors hover:bg-black hover:text-white"
        >
          <span className="block text-2xl">{favorites.length}</span>
          <span className="mt-1 block text-xs tracking-[1.5px] uppercase">Избранное</span>
        </Link>
        <button
          type="button"
          onClick={() => setCartOpen(true)}
          className="p-4 text-left transition-colors hover:bg-black hover:text-white"
        >
          <span className="block text-2xl">{cartCount}</span>
          <span className="mt-1 block text-xs tracking-[1.5px] uppercase">В корзине</span>
        </button>
      </div>

      <div className="mt-8 border-y border-black/10">
        <button
          type="button"
          onClick={() => setContactOpen(true)}
          className="flex w-full items-center gap-3 border-b border-black/10 py-4 text-left transition-opacity hover:opacity-60"
        >
          <HelpCircle size={20} strokeWidth={1.5} />
          <span className="text-sm">Помощь и поддержка</span>
        </button>
        <button
          type="button"
          className="flex w-full items-center gap-3 py-4 text-left transition-opacity hover:opacity-60"
        >
          <FileText size={20} strokeWidth={1.5} />
          <span className="text-sm">Документы</span>
        </button>
      </div>

      <button
        type="button"
        onClick={logout}
        className="mt-8 flex w-full items-center justify-center gap-2 border border-black bg-black py-4 text-sm text-white transition-colors hover:bg-white hover:text-black"
      >
        <LogOut size={18} strokeWidth={1.5} />
        Выйти
      </button>

      <footer className="mt-10 text-center text-xs text-black/35">
        359 Clothing · Версия 1.0.0
      </footer>
    </section>
  );
}
